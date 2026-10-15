"""On-demand MIME downloads and explicit, previewed SMTP replies."""
import contextlib, datetime as dt, email, email.policy, email.utils, html, io, json
import re, secrets, smtplib, ssl
from email.message import EmailMessage

MAX_MESSAGE=25*1024*1024
SMTP_DEFAULTS={'gmail':('smtp.gmail.com',587),'murena':('mail.ecloud.global',587),'partners':('webmail.inpartners.pl',587)}

class UserError(Exception): pass

def migrate(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS identities(account TEXT PRIMARY KEY,name TEXT,signature TEXT,font TEXT,color TEXT,sent_copy INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS outgoing(id TEXT PRIMARY KEY,message_id INTEGER,account TEXT,recipient TEXT,subject TEXT,body TEXT,raw BLOB,state TEXT,created TEXT,updated TEXT,result TEXT);
    CREATE TABLE IF NOT EXISTS calendar_sources(id INTEGER PRIMARY KEY,name TEXT UNIQUE,content BLOB,imported TEXT,enabled INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS calendar_drafts(message_id INTEGER PRIMARY KEY,uid TEXT,data TEXT,sequence INTEGER DEFAULT 0,updated TEXT,reserved INTEGER DEFAULT 0);
    ''')
    if 'input_body' not in {r[1] for r in c.execute('PRAGMA table_info(outgoing)')}:
        c.execute("ALTER TABLE outgoing ADD COLUMN input_body TEXT DEFAULT ''")
    c.commit()

def identity(c,a):
    row=c.execute('SELECT * FROM identities WHERE account=?',(a['id'],)).fetchone()
    return dict(row) if row else {'account':a['id'],'name':'','signature':'','font':'Arial','color':'#172b39','sent_copy':0}

def single_header(value,limit=300):
    value=value.strip()
    if len(value)>limit or any(ord(x)<32 or ord(x)==127 for x in value):
        raise UserError('Nagłówek jest zbyt długi lub zawiera niedozwolony znak.')
    return value

def recipients(value):
    value=single_header(value,2000)
    parsed=email.utils.getaddresses([value])
    addresses=[]
    for _,addr in parsed:
        # ASCII envelope addresses only; no silently truncated malformed recipients.
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",addr):
            raise UserError('Sprawdź pełny adres odbiorcy. Ta wersja obsługuje standardowe adresy ASCII.')
        if addr not in addresses: addresses.append(addr)
    if not 1<=len(addresses)<=20: raise UserError('Podaj od 1 do 20 adresów odbiorców.')
    return addresses

def original(s,r):
    if r['account'] not in SMTP_DEFAULTS or r['source']!='email':
        raise UserError('Ta pozycja nie jest wiadomością z obsługiwanej skrzynki IMAP.')
    m=s.connect(s.account(r['account']))
    try:
        typ,_=m.select('"'+r['folder'].replace('\\','\\\\').replace('"','\\"')+'"',readonly=True)
        if typ!='OK': raise UserError('Nie można otworzyć folderu źródłowego.')
        validity=m.response('UIDVALIDITY')[1]
        if not validity or validity[0].decode()!=str(r['validity']):
            raise UserError('Serwer zmienił identyfikatory folderu. Pobierz aktualną wiadomość przed dalszą pracą.')
        typ,data=m.uid('fetch',str(r['uid']),'(RFC822.SIZE)')
        meta=b' '.join(x if isinstance(x,bytes) else x[0] for x in (data or []) if x)
        size=re.search(rb'RFC822.SIZE\s+(\d+)',meta)
        if typ!='OK' or not size: raise UserError('Nie znaleziono wiadomości na serwerze.')
        if int(size[1])>MAX_MESSAGE: raise UserError('Wiadomość przekracza limit 25 MiB. Pobierz załącznik w webmailu.')
        typ,data=m.uid('fetch',str(r['uid']),'(BODY.PEEK[])')
        blobs=[x[1] for x in (data or []) if isinstance(x,tuple) and len(x)>1 and isinstance(x[1],bytes)]
        if typ!='OK' or not blobs: raise UserError('Nie udało się pobrać wiadomości. Mogła zostać przeniesiona lub usunięta.')
        raw=blobs[0]
        if len(raw)>MAX_MESSAGE: raise UserError('Wiadomość przekracza limit 25 MiB.')
        msg=email.message_from_bytes(raw,policy=email.policy.default)
        if r['mid'] and str(msg.get('Message-ID','')).strip()!=r['mid']:
            raise UserError('Identyfikator wiadomości nie zgadza się ze źródłem. Przerwano pobieranie.')
        return msg
    finally:
        with contextlib.suppress(Exception): m.logout()

def attachments(msg):
    found=[]
    def visit(part):
        disposition=part.get_content_disposition()
        name=part.get_filename()
        if name or disposition=='attachment':
            if part.get_content_type()=='message/rfc822':
                content=b'\r\n'.join(x.as_bytes(policy=email.policy.SMTP) for x in part.get_payload())
            elif part.is_multipart(): content=part.as_bytes(policy=email.policy.SMTP)
            else: content=part.get_payload(decode=True) or b''
            name=name or ('wiadomosc.eml' if part.get_content_type()=='message/rfc822' else 'zalacznik.bin')
            safe=re.sub(r'[\x00-\x1f\x7f/\\]','_',str(name))[:180] or 'zalacznik.bin'
            found.append({'index':len(found),'name':safe,'size':len(content),'content':content})
            return
        if part.is_multipart():
            for child in part.iter_parts(): visit(child)
    visit(msg)
    return found

def reply_headers(msg):
    target=str(msg.get('Reply-To') or msg.get('From') or '')
    addresses=recipients(target)
    mid=str(msg.get('Message-ID','')).strip()
    if not re.fullmatch(r'<[^<>\s]+>',mid): mid=''
    refs=re.findall(r'<[^<>\s]+>',str(msg.get('References','')))[-20:]
    if mid and mid not in refs: refs.append(mid)
    return ', '.join(addresses),mid,' '.join(refs)

def compose(s,r,profile,to,subject,body,headers):
    a=s.account(r['account']); target=recipients(to)
    subject=single_header(subject)
    if not subject or not body.strip() or len(body)>20000: raise UserError('Uzupełnij temat i odpowiedź (do 20 000 znaków).')
    name=single_header(profile['name'],150)
    msg=EmailMessage(policy=email.policy.SMTP)
    msg['From']=email.utils.formataddr((name,a['user']))
    msg['To']=', '.join(target); msg['Subject']=subject
    msg['Date']=email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    msg['Message-ID']=email.utils.make_msgid(domain=a['user'].split('@')[-1])
    if headers[1]: msg['In-Reply-To']=headers[1]
    if headers[2]: msg['References']=headers[2]
    quote='\n\n--- Wiadomość źródłowa ---\nOd: '+r['sender']+'\nData: '+r['date']+'\n'+r['body']
    if r['truncated']: quote+='\n[Treść źródłowa została skrócona.]'
    full=body.strip()+ ('\n\n'+profile['signature'] if profile['signature'] else '')+quote
    msg.set_content(full)
    font=profile['font'] if profile['font'] in ('Arial','Georgia','Verdana') else 'Arial'
    color=profile['color'] if re.fullmatch(r'#[0-9A-Fa-f]{6}',profile['color']) else '#172b39'
    rendered='<div style="font-family:'+font+';font-size:14px;color:'+color+'">'+html.escape(body.strip()).replace('\n','<br>')
    if profile['signature']: rendered+='<p>'+html.escape(profile['signature']).replace('\n','<br>')+'</p>'
    rendered+='<hr><blockquote>'+html.escape(quote).replace('\n','<br>')+'</blockquote></div>'
    msg.add_alternative(rendered,subtype='html')
    return msg,full

def send(s,c,draft):
    # One transaction claims the immutable preview; repeated clicks cannot send again.
    changed=c.execute("UPDATE outgoing SET state='sending',updated=? WHERE id=? AND state='draft'",(s.now(),draft['id'])).rowcount
    c.commit()
    if not changed: raise UserError('Ten podgląd został już obsłużony. Sprawdź status poniżej.')
    a=s.account(draft['account']); smtp=None; phase='connect'; state='failed'; note=''
    try:
        secret=s.keyring_module().get_password('SebastianMail',a['id'])
        if not secret: raise UserError('Brak hasła do skrzynki w Pęku kluczy.')
        host,port=SMTP_DEFAULTS[a['id']]
        smtp=smtplib.SMTP(host,port,timeout=45)
        smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
        smtp.login(a['user'],secret)
        phase='sending'
        refused=smtp.sendmail(a['user'],recipients(draft['recipient']),bytes(draft['raw']))
        state='partial' if refused else 'sent'
        note='Serwer przyjął wiadomość do wysłania.' if not refused else 'Częściowe wysłanie. Serwer odrzucił: '+', '.join(refused)
    except (smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError) as exc:
        state='failed'; note='Serwer odrzucił wysyłkę ('+type(exc).__name__+').'
    except Exception as exc:
        state='unknown' if phase=='sending' else 'failed'
        note=('Nie wiadomo, czy serwer przyjął wiadomość. Sprawdź webmail i odbiorcę przed ponowną próbą.' if state=='unknown' else 'Nie wysłano: '+type(exc).__name__+'. Sprawdź hasło i dostęp SMTP.')
    finally:
        if smtp:
            with contextlib.suppress(Exception): smtp.quit()
    # No IMAP mutation unless explicitly configured by owner; Gmail normally stores its copy.
    if state in ('sent','partial'):
        profile=identity(c,a)
        if profile['sent_copy'] and a.get('sent_folder'):
            imap=None
            try:
                imap=s.connect(a)
                folder='"'+a['sent_folder'].replace('\\','\\\\').replace('"','\\"')+'"'
                typ,_=imap.append(folder,'(\\Seen)',None,bytes(draft['raw']))
                if typ!='OK': raise UserError('APPEND')
                note+=' Zapisano kopię w folderze wysłanych.'
            except Exception:
                note+=' Wysyłka została przyjęta, ale nie potwierdzono kopii w folderze wysłanych. Nie wysyłaj ponownie z tego powodu.'
            finally:
                if imap:
                    with contextlib.suppress(Exception): imap.logout()
        else: note+=' Lokalna kopia jest dostępna jako EML; sprawdź, czy dostawca zapisał kopię w Wysłanych.'
    c.execute('UPDATE outgoing SET state=?,result=?,updated=? WHERE id=?',(state,note,s.now(),draft['id'])); c.commit()
    return state,note
