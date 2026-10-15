"""Review shortcuts, auditable progress, and explicit priority heuristics."""
import contextlib, datetime as dt, email.utils, json, unicodedata
from flask import abort, flash, redirect, render_template, request, session

LABELS={1:'Pilne i ważne',2:'Pilne i mniej ważne',3:'Niepilne i ważne',4:'Niepilne i mniej ważne'}
DECISION_FIELDS=['status','category_override','topic','topic_sub','comment','skip_reason','learn','decided_at','priority_override','decision_kind','is_task','task_title','category_confirmed','feedback_at']

def migrate(c):
    cols={r[1] for r in c.execute('PRAGMA table_info(messages)')}
    for key,definition in {'sender_name':"TEXT DEFAULT ''",'priority_override':'INTEGER DEFAULT 0','decision_kind':"TEXT DEFAULT ''",'arrival':"TEXT DEFAULT 'archive'"}.items():
        if key not in cols:c.execute('ALTER TABLE messages ADD COLUMN '+key+' '+definition)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS undo_decisions(event_id INTEGER PRIMARY KEY,message_id INTEGER,previous TEXT,used INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS important_senders(account TEXT,address TEXT,PRIMARY KEY(account,address));
    CREATE TABLE IF NOT EXISTS morning_runs(id INTEGER PRIMARY KEY,started TEXT,finished TEXT,state TEXT,details TEXT);
    CREATE TABLE IF NOT EXISTS morning_items(run_id INTEGER,message_id INTEGER,PRIMARY KEY(run_id,message_id));
    ''');c.commit()

def normalized(value):
    return ''.join(ch for ch in unicodedata.normalize('NFKD',value.casefold().replace('ł','l')) if not unicodedata.combining(ch))

def protected(r,extra=()):
    if (r['account'],r['sender'].casefold()) in extra:return True
    text=normalized(r.get('sender_name','')+' '+r['sender'])
    return r['account']=='partners' and (('dawid' in text and 'koziol' in text) or ('tomasz' in text and 'pustow' in text))

def priority(d,today,extra=()):
    ai=d['ai'];is_protected=protected(d,extra)
    try:due=dt.date.fromisoformat(ai.get('due') or ai.get('calendar_date') or '')
    except ValueError:due=None
    days=(due-today).days if due else None
    urgent=days is not None and 0<=days<=3
    important=d['category'] not in ('newsletter','informacja')
    if ai.get('importance') in ('important','low') and ai.get('priority_evidence'):
        important=ai['importance']=='important'
    if is_protected:important=True
    manual=int(d.get('priority_override') or 0)
    suggested=ai.get('priority_suggestion',0)
    if suggested in LABELS and ai.get('priority_evidence'):
        urgent=suggested in (1,2);important=suggested in (1,3) or is_protected
        if days is not None and days<0:urgent=False
    rank=manual if manual in LABELS else (1 if urgent and important else 2 if urgent else 3 if important else 4)
    reason='Twój ręczny wybór.' if manual else ('Ważny nadawca. ' if is_protected else '')+('Termin w ciągu 3 dni.' if urgent else 'Termin minął — sprawdź aktualność.' if days is not None and days<0 else 'Termin odległy.' if days is not None else 'Brak potwierdzonego bliskiego terminu.')
    if not manual and suggested in LABELS and ai.get('priority_evidence') and not (days is not None and days<0):
        reason=('Ważny nadawca. ' if is_protected else '')+'Propozycja AI: '+ai.get('priority_reason','sprawdź cytat w karcie.')[:250]
    d.update(priority=rank,priority_label=LABELS[rank],priority_reason=reason,protected_sender=is_protected,stale_due=days is not None and days<0)
    if is_protected and not manual:d['ai']={**ai,'suggest_skip':False}
    return d

def extend_schema(schema):
    schema['properties'].update(importance={'type':'string','enum':['important','low','unknown']},priority_evidence={'type':'string'})
    schema['properties'].update(priority_suggestion={'type':'integer','enum':[0,1,2,3,4]},priority_reason={'type':'string'})
    schema['required']+=['importance','priority_evidence','priority_suggestion','priority_reason']

def policy():
    return (' Dodatkowo importance: important, low lub unknown, oraz priority_evidence: dosłowny cytat uzasadniający wagę. '
            'Ważne są zobowiązania, klienci, zespół, kwestie prawne, rodzina i majątek. Reklamy i newslettery zwykle low, '
            'ale ważne ogłoszenia firmowe nie są automatycznie mało ważne. Zwróć priority_suggestion: 0 gdy brak podstaw, 1 pilne i ważne, 2 pilne i mniej ważne, 3 niepilne i ważne, 4 niepilne i mniej ważne; priority_reason to krótkie uzasadnienie. Uwzględniaj poprawki priority_override w podobnych przykładach jako preferencje, ale nie przenoś dawnych terminów i statusu wykonania na nowy mail. Pilność wymaga podstaw w bieżącej treści, nie zgaduj. priority_evidence musi być dosłownym cytatem z bieżącego body.')

def validate(value,body):
    if value.get('importance') not in ('important','low','unknown'):value['importance']='unknown'
    if not value.get('priority_evidence') or value['priority_evidence'] not in body:
        value['importance']='unknown';value['priority_evidence']=''
    if type(value.get('priority_suggestion')) is not int or value.get('priority_suggestion') not in range(5) or not value.get('priority_evidence'):
        value['priority_suggestion']=0
    value['priority_reason']=str(value.get('priority_reason',''))[:300]
    return value

def scope_arg(s):
    scope=request.values.get('scope','private')
    if scope not in s.SCOPES:abort(400)
    return scope

def register(app,s):
    @app.route('/quick-skip/<int:mid>',methods=['POST'])
    def quick_skip(mid):
        with contextlib.closing(s.db()) as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone()
            if not r:abort(404)
            if r['decided_at']:
                flash('Ta wiadomość ma już zapisaną decyzję. Nic nie zmieniono.')
                return redirect('/?scope='+r['scope'])
            previous={key:r[key] for key in DECISION_FIELDS}
            reason='Szybkie pominięcie: mało ważne według użytkownika, bez pełnej lektury.'
            stamp=s.now()
            c.execute("UPDATE messages SET status='ignored',skip_reason=?,decided_at=?,decision_kind='quick',is_task=0,feedback_at=? WHERE id=?",(reason,stamp,stamp,mid))
            event=c.execute('INSERT INTO events(time,message_id,action,value) VALUES(?,?,?,?)',(stamp,mid,'decision',json.dumps({'status':'ignored','skip_reason':reason,'learn':bool(r['learn']),'kind':'quick'},ensure_ascii=False))).lastrowid
            c.execute('INSERT INTO undo_decisions VALUES(?,?,?,0)',(event,mid,json.dumps(previous,ensure_ascii=False)));c.commit()
            session['undo_skip']=event
        s.build_report();flash('Pominięto wiadomość. Możesz cofnąć tę decyzję przyciskiem poniżej.')
        view=request.form.get('view','decisions');view=view if view in ('decisions','fresh','all') else 'decisions'
        return redirect('/?scope='+r['scope']+'&view='+view)

    @app.route('/quick-undo/<int:eid>',methods=['POST'])
    def quick_undo(eid):
        with contextlib.closing(s.db()) as c:
            c.execute('BEGIN IMMEDIATE')
            undo=c.execute('SELECT * FROM undo_decisions WHERE event_id=?',(eid,)).fetchone()
            if not undo or undo['used']:abort(400)
            r=c.execute('SELECT * FROM messages WHERE id=?',(undo['message_id'],)).fetchone()
            latest=c.execute('SELECT MAX(id) FROM events WHERE message_id=?',(undo['message_id'],)).fetchone()[0]
            if not r or latest!=eid:
                flash('Od tego czasu zapisano nowszą zmianę. Otwórz kartę, aby ją poprawić.')
                return redirect('/message/'+str(undo['message_id']))
            old=json.loads(undo['previous']);assign=','.join(k+'=?' for k in DECISION_FIELDS)
            c.execute('UPDATE messages SET '+assign+' WHERE id=?',[old.get(k,r[k]) for k in DECISION_FIELDS]+[r['id']])
            c.execute('UPDATE undo_decisions SET used=1 WHERE event_id=?',(eid,))
            c.execute('INSERT INTO events(time,message_id,action,value) VALUES(?,?,?,?)',(s.now(),r['id'],'undo_quick',str(eid)));c.commit()
            session.pop('undo_skip',None)
        s.build_report();flash('Cofnięto szybką zmianę. Przywrócono poprzedni stan wiadomości.')
        return redirect('/?scope='+r['scope'])

    @app.route('/summary')
    def summary():
        scope=scope_arg(s);today=dt.datetime.now(s.TZ).date();start=today.isoformat()
        with contextlib.closing(s.db()) as c:
            rows=[dict(r) for r in c.execute('SELECT id,subject,account,sender,analysis,status,decided_at,learn,comment,skip_reason,topic,topic_sub,decision_kind,arrival,imported,is_task,feedback_at,priority_override FROM messages WHERE scope=?',(scope,))]
            stats={'total':len(rows),'analyzed':sum(bool(r['analysis']) for r in rows),'reviewed':sum(bool(r['decided_at']) for r in rows),'eligible':sum(bool(r['decided_at'] and r['learn']) for r in rows),'done':sum(r['status']=='done' for r in rows),'ignored':sum(r['status']=='ignored' for r in rows),'open':sum(r['status']=='open' and bool(r['is_task']) for r in rows)}
            replies={r['message_id']:dict(r) for r in c.execute("SELECT o.id,o.message_id,o.input_body,o.updated FROM outgoing o JOIN messages m ON m.id=o.message_id WHERE m.scope=? AND o.state='sent' ORDER BY o.updated",(scope,))}
            for r in rows:r['reply']=replies.get(r['id'],{})
            stats['eligible']=sum(bool(r['learn'] and (r['decided_at'] or r['feedback_at'] or r['reply'])) for r in rows)
            stats['waiting']=stats['total']-stats['reviewed'];stats['percent']=round(100*stats['reviewed']/max(1,stats['total']))
            stats['today']=sum(bool(r['decided_at'] and r['decided_at'][:10]==start) for r in rows)
            stats['sent']=c.execute("SELECT count(*) FROM outgoing o JOIN messages m ON m.id=o.message_id WHERE m.scope=? AND o.state='sent'",(scope,)).fetchone()[0]
            stats['calendar']=c.execute('SELECT count(*) FROM calendar_drafts d JOIN messages m ON m.id=d.message_id WHERE m.scope=?',(scope,)).fetchone()[0]
            used={};using=[]
            for r in rows:
                if not r['analysis']:continue
                ai=json.loads(r['analysis']);ids=ai.get('feedback_ids',[])
                if ids:
                    using.append({'id':r['id'],'subject':r['subject'],'ids':ids,'time':ai.get('analyzed_at','')})
                    for mid in set(ids):used[mid]=used.get(mid,0)+1
            stats['using']=len(using)
            examples=sorted([dict(r,uses=used.get(r['id'],0)) for r in rows if (r['decided_at'] or r['feedback_at'] or r['reply']) and r['learn']],key=lambda r:max(r['decided_at'],r['feedback_at'],r['reply'].get('updated','')),reverse=True)[:40]
            knowledge=sorted([r for r in rows if ((r['decided_at'] or r['feedback_at']) and (r['comment'] or r['topic'] or r['skip_reason'] or r['priority_override'])) or r['reply']],key=lambda r:max(r['decided_at'],r['feedback_at'],r['reply'].get('updated','')),reverse=True)[:30]
            recent=sorted([r for r in rows if r['decided_at']],key=lambda r:r['decided_at'],reverse=True)[:30]
            daily=[]
            for i in range(6,-1,-1):
                day=(today-dt.timedelta(days=i)).isoformat()
                daily.append({'date':day,'count':sum(r['decided_at'][:10]==day for r in rows)})
            jobs=[dict(r) for r in c.execute('SELECT * FROM morning_runs ORDER BY id DESC LIMIT 7')]
            for job in jobs:job['data']=json.loads(job['details'] or '{}')
            protected_rows=[dict(r) for r in c.execute('SELECT * FROM important_senders')]
            cursor_rows=[dict(r) for r in c.execute('SELECT * FROM cursors')]
        automation={}
        path=s.DATA/'automation.json'
        if path.exists():automation=json.loads(path.read_text())
        return render_template('summary.html',scope=scope,stats=stats,examples=examples,knowledge=knowledge,recent=recent,daily=daily,using=sorted(using,key=lambda x:x['time'],reverse=True)[:20],jobs=jobs,automation=automation,protected_rows=protected_rows,cursors=cursor_rows,csrf=session['csrf'])

    @app.route('/important-sender',methods=['POST'])
    def important_sender():
        aid=request.form.get('account','');address=request.form.get('address','').strip().casefold()
        if aid not in ('gmail','murena','partners') or '@' not in address or email.utils.parseaddr(address)[1]!=address or any(ch.isspace() for ch in address):abort(400)
        with contextlib.closing(s.db()) as c:
            if request.form.get('remove')=='yes':c.execute('DELETE FROM important_senders WHERE account=? AND address=?',(aid,address))
            else:c.execute('INSERT OR IGNORE INTO important_senders VALUES(?,?)',(aid,address))
            c.commit()
        return redirect('/summary?scope='+scope_arg(s))
