"""Editable local calendar drafts, ICS export and snapshot-based conflict checks."""
import datetime as dt, email.utils, json, re, uuid
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event
import recurring_ical_events
from mail_actions import UserError
TZ=ZoneInfo('Europe/Warsaw')
UTC=dt.timezone.utc
FIELDS=['calendar_date','calendar_time','calendar_end_time','calendar_location','calendar_title','calendar_evidence']

def extend_schema(schema):
    for key in FIELDS:
        schema['properties'][key]={'type':'string'}
        if key not in schema['required']: schema['required'].append(key)

def policy():
    return (' Dla daty spotkania, wydarzenia lub terminu uzupełnij calendar_date YYYY-MM-DD, '
            'calendar_time HH:MM i calendar_end_time HH:MM tylko jeśli podano godziny, '
            'calendar_location tylko z treści, calendar_title i calendar_evidence jako dosłowny cytat '
            'potwierdzający termin. Daty względne odnieś do daty maila. Przy niejednoznaczności '
            'lub braku roku nie zgaduj; zostaw puste pola. Nie zgaduj końca, miejsca ani dojazdu. '
            'Propozycja zawsze wymaga sprawdzenia przez użytkownika.')

def validate_hint(value,body):
    for key in FIELDS: value.setdefault(key,'')
    quote=value.get('calendar_evidence','')
    if not quote or quote not in body:
        for key in FIELDS: value[key]=''
        return value
    try: dt.date.fromisoformat(value['calendar_date'])
    except (TypeError,ValueError): value['calendar_date']=''
    for key in ('calendar_time','calendar_end_time'):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value.get(key,'')): value[key]=''
    return value

def base_draft(r,hint=None):
    ai=hint if hint is not None else json.loads(r['analysis'] or '{}')
    date=ai.get('calendar_date') or ai.get('due','')
    time=ai.get('calendar_time','')
    contacts=email.utils.parseaddr(r['sender'])[1]
    return {'title':ai.get('calendar_title') or r['subject'],'date':date,'time':time,
            'end_date':date,'end_time':ai.get('calendar_end_time',''),
            'all_day':not bool(time),'location':ai.get('calendar_location',''),
            'description':ai.get('summary','')+'\n\nNadawca: '+r['sender']+'\nData wiadomości: '+r['date']+
                '\nKonto: '+r['account']+'\nTemat: '+r['subject']+'\nŹródło: http://127.0.0.1:8765/message/'+str(r['id'])+
                '\nMessage-ID: '+r['mid']+'\nCytat: '+(ai.get('calendar_evidence') or ai.get('evidence','')),
            'contact':contacts,'busy':True,'origin':'','car_minutes':'','train_minutes':'',
            'travel_minutes':0,'return_minutes':0,'travel_mode':'unknown','travel_notes':'',
            'evidence':ai.get('calendar_evidence') or ai.get('evidence',''),
            'uid':str(uuid.uuid4())+'@sebastian.local','sequence':0,'reserved':0}

def read_draft(c,r):
    saved=c.execute('SELECT * FROM calendar_drafts WHERE message_id=?',(r['id'],)).fetchone()
    if saved:
        value=json.loads(saved['data']); value.update(uid=saved['uid'],sequence=saved['sequence'],reserved=saved['reserved'])
        return value
    return base_draft(r)

def local_time(date,time):
    value=dt.datetime.fromisoformat(date+'T'+time)
    aware=value.replace(tzinfo=TZ)
    # Do not silently choose an ambiguous DST hour or normalize a nonexistent hour.
    if aware.astimezone(UTC).astimezone(TZ).replace(tzinfo=None)!=value:
        raise UserError('Ta godzina nie istnieje przy zmianie czasu. Wybierz inną godzinę.')
    if value.replace(tzinfo=TZ,fold=0).utcoffset()!=value.replace(tzinfo=TZ,fold=1).utcoffset():
        raise UserError('Ta godzina występuje dwa razy przy zmianie czasu. Wybierz jednoznaczną godzinę.')
    return aware

def interval(d):
    try:
        if d['all_day']:
            start=dt.datetime.combine(dt.date.fromisoformat(d['date']),dt.time(),TZ)
            # Form uses inclusive last day; RFC5545 DTEND is exclusive.
            end=dt.datetime.combine(dt.date.fromisoformat(d['end_date'])+dt.timedelta(days=1),dt.time(),TZ)
        else:
            start=local_time(d['date'],d['time']); end=local_time(d['end_date'],d['end_time'])
        if not start<end or end-start>dt.timedelta(days=31): raise ValueError()
        return start,end
    except (ValueError,KeyError,TypeError):
        raise UserError('Uzupełnij poprawny początek i koniec. Koniec musi wypadać po początku; maksymalnie 31 dni.')

def from_form(form,old):
    value=dict(old)
    limits={'title':300,'date':10,'time':5,'end_date':10,'end_time':5,'location':500,'description':10000,
            'contact':500,'origin':500,'travel_mode':20,'travel_notes':2000}
    for key,limit in limits.items(): value[key]=form.get(key,'').strip()[:limit]
    value['all_day']=form.get('all_day')=='yes'; value['busy']=form.get('busy')=='yes'
    if not value['title']: raise UserError('Wpisz tytuł wydarzenia.')
    for key in ('travel_minutes','return_minutes','car_minutes','train_minutes'):
        text=form.get(key,'').strip()
        if not text and key in ('car_minutes','train_minutes'): value[key]=''; continue
        try: number=int(text or 0)
        except ValueError: raise UserError('Czas dojazdu wpisz w pełnych minutach.')
        if not 0<=number<=2880: raise UserError('Czas dojazdu musi mieścić się między 0 a 2880 minut.')
        value[key]=number
    if value['travel_mode'] not in ('unknown','car','train','other'): raise UserError('Wybierz sposób dojazdu.')
    interval(value)
    return value

def save(c,s,r,value):
    previous=c.execute('SELECT * FROM calendar_drafts WHERE message_id=?',(r['id'],)).fetchone()
    if previous:
        value['uid']=previous['uid']; value['sequence']=previous['sequence']+1; value['reserved']=previous['reserved']
    c.execute('INSERT OR REPLACE INTO calendar_drafts(message_id,uid,data,sequence,updated,reserved) VALUES(?,?,?,?,?,?)',
              (r['id'],value['uid'],json.dumps(value,ensure_ascii=False),value['sequence'],s.now(),value['reserved']))
    c.commit()

def travel(d):
    result={'advice':'Brak danych do porównania. Sprawdź trasę i rozkład na dzień wydarzenia.', 'links':{},'leave':''}
    if d.get('location'):
        for key,mode in [('car','driving'),('train','transit')]:
            args={'api':1,'destination':d['location'],'travelmode':mode}
            if d.get('origin'): args['origin']=d['origin']
            result['links'][key]='https://www.google.com/maps/dir/?'+urlencode(args)
    car=d.get('car_minutes',''); train=d.get('train_minutes','')
    if car!='' and train!='':
        winner='samochód' if int(car)<int(train) else 'pociąg / transport publiczny' if int(train)<int(car) else 'oba warianty'
        result['advice']='Według wpisanych przez Ciebie czasów krótszy dojazd: '+winner+'. Uwzględnij dojście, parking, przesiadki, koszt i aktualny rozkład.'
    try:
        start,_=interval(d)
        if not d['all_day'] and d.get('travel_minutes'):
            result['leave']=(start-dt.timedelta(minutes=int(d['travel_minutes']))).isoformat(timespec='minutes')
    except UserError: pass
    return result

def to_ics(d):
    start,end=interval(d)
    cal=Calendar(); cal.add('prodid','-//Sebastian//Centrum spraw 1.2//PL'); cal.add('version','2.0')
    event=Event(); event.add('uid',d['uid']); event.add('sequence',d['sequence']); event.add('dtstamp',dt.datetime.now(UTC))
    event.add('summary',d['title']); event.add('location',d['location'])
    if d['all_day']:
        event.add('dtstart',start.date()); event.add('dtend',end.date())
    else:
        event.add('dtstart',start.astimezone(UTC)); event.add('dtend',end.astimezone(UTC))
    event.add('transp','OPAQUE' if d['busy'] else 'TRANSPARENT'); event.add('status','CONFIRMED')
    route=travel(d)
    description=d['description']+'\n\nKontakt: '+d['contact']+'\nDojazd od: '+d['origin']+'\nNotatki o dojeździe: '+d['travel_notes']
    description+='\nPorównanie: '+route['advice']
    if route['leave']: description+='\nPlanowane wyjście (wg wpisanego czasu): '+route['leave']
    for mode,url in route['links'].items(): description+='\nTrasa '+mode+': '+url
    event.add('description',description)
    # Contact is informational; no ORGANIZER/ATTENDEE/METHOD:REQUEST, so no invitations.
    if d['contact']: event.add('contact',d['contact'])
    cal.add_component(event)
    if not d['all_day']:
        for key,minutes,a,b in [
            ('dojazd',int(d.get('travel_minutes',0)),start-dt.timedelta(minutes=int(d.get('travel_minutes',0))),start),
            ('powrot',int(d.get('return_minutes',0)),end,end+dt.timedelta(minutes=int(d.get('return_minutes',0))))]:
            if minutes:
                buffer=Event(); buffer.add('uid',key+'-'+d['uid']); buffer.add('sequence',d['sequence']); buffer.add('dtstamp',dt.datetime.now(UTC))
                buffer.add('summary',('Dojazd: ' if key=='dojazd' else 'Powrót: ')+d['title'])
                buffer.add('dtstart',a.astimezone(UTC)); buffer.add('dtend',b.astimezone(UTC)); buffer.add('transp','OPAQUE' if d['busy'] else 'TRANSPARENT')
                buffer.add('description','Czas wpisany ręcznie przez użytkownika. '+d['travel_notes']); cal.add_component(buffer)
    return cal.to_ical()

def parse_source(raw):
    if len(raw)>5*1024*1024: raise UserError('Plik kalendarza przekracza 5 MiB.')
    try:
        cal=Calendar.from_ical(raw)
        if cal.name!='VCALENDAR': raise ValueError()
        events=cal.walk('VEVENT')
        if not events: raise UserError('Brak wydarzeń VEVENT w pliku. Sam FREEBUSY nie jest obsługiwany.')
        if len(events)>20000: raise UserError('Za dużo wydarzeń w jednym pliku (limit 20 000).')
        for event in events:
            rule=event.get('RRULE')
            if rule and str(rule.get('FREQ',[''])[0]).upper() in ('SECONDLY','MINUTELY'):
                raise UserError('Cykle co sekundę lub minutę nie są obsługiwane. Import przerwany, aby uniknąć niepełnej kontroli.')
            if event.errors: raise UserError('Plik zawiera błędy pól wydarzenia; import przerwany, aby nie pominąć konfliktów.')
            if not event.get('DTSTART') and str(event.get('STATUS','')).upper()!='CANCELLED':
                raise UserError('Wydarzenie nie ma daty początku; import przerwany.')
        return cal
    except UserError: raise
    except Exception: raise UserError('Nie można odczytać pliku ICS. Wyeksportuj kalendarz ponownie.')

def aware(value):
    if isinstance(value,dt.datetime): return value.replace(tzinfo=TZ) if value.tzinfo is None else value.astimezone(TZ)
    return dt.datetime.combine(value,dt.time(),TZ)

def contacts(event):
    result=[]
    owner=event.get('ORGANIZER')
    if owner:
        result.append('Organizator: '+str(owner.params.get('CN',''))+' '+str(owner).removeprefix('mailto:').removeprefix('MAILTO:'))
    people=event.get('ATTENDEE',[])
    if not isinstance(people,list): people=[people]
    for person in people[:5]:
        if str(person.params.get('PARTSTAT','')).upper()=='DECLINED': continue
        result.append('Uczestnik: '+str(person.params.get('CN',''))+' '+str(person).removeprefix('mailto:').removeprefix('MAILTO:'))
    if not result and event.get('CONTACT'): result.append(str(event['CONTACT']))
    return result

def conflicts(c,d,mid):
    start,end=interval(d)
    if not d['all_day']:
        start-=dt.timedelta(minutes=int(d.get('travel_minutes',0))); end+=dt.timedelta(minutes=int(d.get('return_minutes',0)))
    results=[]; errors=[]; sources=[]; seen={}
    def inspect(cal,label):
        try:
            events=recurring_ical_events.of(cal).between(start-dt.timedelta(days=1),end+dt.timedelta(days=1))
            for event in events:
                uid=str(event.get('UID',''))
                if uid in (d['uid'],'dojazd-'+d['uid'],'powrot-'+d['uid']): continue
                if str(event.get('STATUS','')).upper()=='CANCELLED': continue
                a=aware(event.decoded('DTSTART'))
                if event.get('DTEND'): b=aware(event.decoded('DTEND'))
                elif event.get('DURATION'): b=a+event.decoded('DURATION')
                else: b=a+(dt.timedelta(days=1) if not isinstance(event.decoded('DTSTART'),dt.datetime) else dt.timedelta())
                if a<end and b>start:
                    key=(uid or str(event.get('SUMMARY','')),a.isoformat(),b.isoformat())
                    busy=str(event.get('TRANSP','OPAQUE')).upper()!='TRANSPARENT'
                    if key in seen:
                        previous=results[seen[key]]
                        previous['busy']=previous['busy'] or busy
                        previous['conflict']=previous['busy'] and d['busy']
                        previous['contacts']=list(dict.fromkeys(previous['contacts']+contacts(event)))
                        if label not in previous['source']: previous['source']+=' / '+label
                        continue
                    seen[key]=len(results)
                    results.append({'title':str(event.get('SUMMARY','Bez tytułu')),'start':a.isoformat(timespec='minutes'),
                                    'end':b.isoformat(timespec='minutes'),'busy':busy,'conflict':busy and d['busy'],
                                    'source':label,'status':str(event.get('STATUS','CONFIRMED')),
                                    'contacts':contacts(event)})
        except Exception:
            errors.append('Nie udało się w pełni sprawdzić: '+label+'. Nie można wykluczyć konfliktu.')
    for row in c.execute('SELECT * FROM calendar_sources WHERE enabled=1'):
        sources.append({'name':row['name'],'imported':row['imported']})
        try: inspect(parse_source(row['content']),row['name'])
        except UserError: errors.append('Nie można odczytać: '+row['name'])
    for row in c.execute('SELECT * FROM calendar_drafts WHERE reserved=1 AND message_id<>?',(mid,)):
        other=json.loads(row['data']); other['uid']=row['uid']; other['sequence']=row['sequence']
        try: inspect(Calendar.from_ical(to_ics(other)),'Eksport Sebastiana #'+str(row['message_id']))
        except UserError: errors.append('Nie można sprawdzić lokalnego wydarzenia #'+str(row['message_id']))
    return {'items':results,'errors':errors,'sources':sources,'blocking':sum(x['conflict'] for x in results)}
