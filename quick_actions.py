"""Explicit, undoable inbox decisions; tasks remain linked to their mail."""
import contextlib, hashlib, json
from flask import abort, flash, redirect, request, session
import feedback, progress

def migrate(c):
    columns={r[1] for r in c.execute('PRAGMA table_info(messages)')}
    for name,definition in {'is_task':'INTEGER DEFAULT 0','task_title':"TEXT DEFAULT ''",'category_confirmed':'INTEGER DEFAULT 0','feedback_at':"TEXT DEFAULT ''"}.items():
        if name not in columns:c.execute('ALTER TABLE messages ADD COLUMN '+name+' '+definition)
    if 'is_task' not in columns:
        c.execute("UPDATE messages SET is_task=1 WHERE status='open' AND decided_at<>''")
        c.execute("UPDATE messages SET category_confirmed=1 WHERE decided_at<>''")
    c.execute('CREATE INDEX IF NOT EXISTS events_message_lookup ON events(message_id,id)')
    c.execute('CREATE INDEX IF NOT EXISTS outgoing_message_state ON outgoing(message_id,state,updated)')
    c.commit()

def revision(c,r):
    event=c.execute('SELECT COALESCE(MAX(id),0) FROM events WHERE message_id=?',(r['id'],)).fetchone()[0]
    payload=[r['id'],event]+[r[k] for k in progress.DECISION_FIELDS]+[r['analysis']]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()

def destination(r):
    view=request.form.get('view','decisions')
    if view not in ('decisions','fresh','all','tasks','morning','evening'):view='decisions'
    return '/?scope='+r['scope']+'&view='+view

def register(app,s):
    @app.route('/quick/<int:mid>',methods=['POST'])
    def quick_decision(mid):
        action=request.form.get('action','')
        if action not in ('accept','category','priority','done','task'):abort(400)
        with contextlib.closing(s.db()) as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone()
            if not row:abort(404)
            if request.form.get('revision')!=revision(c,row):
                flash('Wiadomość zmieniła się od wyświetlenia listy. Odświeżyłem ją — sprawdź stan i kliknij ponownie.')
                return redirect(destination(row))
            r=dict(row);old={k:r[k] for k in progress.DECISION_FIELDS};updated=dict(old)
            ai=json.loads(r['analysis'] or '{}');topics=feedback.catalogue(c,r['scope'])
            stamp=s.now()
            if action=='priority':
                try:rank=int(request.form.get('priority',''))
                except ValueError:abort(400)
                if rank not in (0,1,2,3,4):abort(400)
                updated['priority_override']=rank
                # Priority correction is knowledge, but not a decision to close the inbox item.
            elif action in ('accept','category'):
                if action=='accept':
                    topic=ai.get('topic','');sub=ai.get('topic_sub','')
                    if not topic or topic not in topics or (sub and sub not in topics[topic]):
                        flash('Brak poprawnej propozycji kategorii. Wybierz „Zmień kategorię”.')
                        return redirect(destination(r))
                else:
                    try:topic,sub=json.loads(request.form.get('category_path','["",""]'))
                    except (TypeError,ValueError):abort(400)
                    if not isinstance(topic,str) or not isinstance(sub,str):abort(400)
                    new=request.form.get('new_topic','').strip()[:100]
                    child=request.form.get('new_sub','').strip()[:100]
                    if new:topic=new;sub=''
                    if child:sub=child
                    if not topic or (topic not in topics and not new) or (sub and sub not in topics.get(topic,[]) and not child):abort(400)
                    c.execute('INSERT OR IGNORE INTO topics VALUES(?,?,?)',(r['scope'],'',topic))
                    if sub:c.execute('INSERT OR IGNORE INTO topics VALUES(?,?,?)',(r['scope'],topic,sub))
                updated.update(topic=topic,topic_sub=sub,category_confirmed=1,decided_at=stamp)
                # Categorizing does not silently turn a message into a task or reopen completed work.
                if not r['category_override']:updated['category_override']=ai.get('category','sprawdz')
            else:
                updated.update(status='done' if action=='done' else 'open',is_task=int(action=='task'),decided_at=stamp,skip_reason='')
                if action=='task':updated['task_title']=request.form.get('task_title','').strip()[:300] or r['task_title'] or ai.get('action','')[:300] or r['subject'][:300]
                if not r['category_confirmed'] and not r['decided_at']:
                    updated.update(topic=ai.get('topic',''),topic_sub=ai.get('topic_sub',''))
            updated.update(feedback_at=stamp,decision_kind='quick_'+action)
            if all(updated[k]==old[k] for k in updated if k not in ('feedback_at','decision_kind','decided_at')):
                flash('Ten wybór jest już zapisany.');return redirect(destination(r))
            c.execute('UPDATE messages SET '+','.join(k+'=?' for k in updated)+' WHERE id=?',list(updated.values())+[mid])
            event=c.execute('INSERT INTO events(time,message_id,action,value) VALUES(?,?,?,?)',(stamp,mid,'quick_'+action,json.dumps(updated,ensure_ascii=False))).lastrowid
            c.execute('INSERT INTO undo_decisions VALUES(?,?,?,0)',(event,mid,json.dumps(old,ensure_ascii=False)));c.commit()
            session['undo_skip']=event
        s.build_report()
        flash({'accept':'Zatwierdzono kategorię. Mail znika z kolejki decyzji; zadanie dodasz osobnym przyciskiem.','category':'Zapisano kategorię.','priority':'Zapisano priorytet. Mail nadal czeka na decyzję, jeśli nie był wcześniej oceniony.','done':'Oznaczono jako wykonane.','task':'Dodano do „Zadania do wykonania”.'}[action])
        return redirect(destination(r))
