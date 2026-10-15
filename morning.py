"""Local launchd worker: new mail only, 06:30, bounded retries, visible run history."""
import contextlib, datetime as dt, json, os, pathlib, plistlib, subprocess, sys, time

def ensure_ollama(s):
    def check():
        response=s.requests.get('http://127.0.0.1:11434/api/tags',timeout=5);response.raise_for_status()
        names=[m['name'] for m in response.json()['models']]
        if s.config()['model'] not in names:raise RuntimeError('Wybranego modelu nie ma w lokalnej Ollamie.')
    try:check();return
    except Exception:
        if sys.platform!='darwin':raise
    subprocess.run(['open','-gja','Ollama'],capture_output=True,timeout=10)
    for _ in range(10):
        time.sleep(2)
        try:check();return
        except Exception:pass
    raise RuntimeError('Ollama lub wybrany model nie jest gotowy. Uruchom Ollamę i sprawdź python sebastian.py doctor.')

def plans(s):
    now=dt.datetime.now(s.TZ)
    previous={}
    if (s.DATA/'automation.json').exists():previous=json.loads((s.DATA/'automation.json').read_text())
    start=previous.get('start_date') if previous.get('enabled') else None
    return {'enabled':False,'hour':6,'minute':30,'start_date':start or (now.date()+dt.timedelta(days=1)).isoformat(),'prepared':s.now(),'accounts':[],'warnings':[]}

def timezone_ok(s):
    return dt.datetime.now().astimezone().utcoffset()==dt.datetime.now(s.TZ).utcoffset()

def prepare(s):
    if sys.platform!='darwin':raise RuntimeError('Harmonogram wymaga Maca. Uruchom to polecenie na swoim Macu.')
    if not timezone_ok(s):
        raise RuntimeError('Ustaw strefę czasową Maca na Warszawa przed włączeniem harmonogramu 06:30.')
    cfg=s.config()
    if cfg['ollama']!='http://127.0.0.1:11434' or not cfg['model'] or 'cloud' in cfg['model'].lower():raise RuntimeError('Wybierz lokalny model Ollamy.')
    ensure_ollama(s)
    plan=plans(s)
    for a in cfg['accounts']:
        m=None;ready=[]
        try:
            m=s.connect(a)
            for folder in a['folders']:
                try:
                    typ,_=m.select('"'+folder.replace('\\','\\\\').replace('"','\\"')+'"',readonly=True)
                    if typ!='OK':raise RuntimeError('Nie można otworzyć folderu.')
                    _,values=m.response('UIDVALIDITY')
                    if not values or not values[0]:raise RuntimeError('Brak UIDVALIDITY.')
                    validity=values[0].decode()
                    with contextlib.closing(s.db()) as c:
                        cursor=c.execute('SELECT * FROM cursors WHERE account=? AND folder=?',(a['id'],folder)).fetchone()
                        if cursor and cursor['validity']!=validity:
                            raise RuntimeError('Zmieniło się UIDVALIDITY — wykonaj pilot folderu i ponów przygotowanie.')
                        if not cursor:
                            typ,data=m.uid('search',None,'ALL')
                            if typ!='OK':raise RuntimeError('Nie można ustalić granicy nowych maili.')
                            high=max([int(x) for x in data[0].split()],default=0)
                            c.execute('INSERT INTO cursors VALUES(?,?,?,?)',(a['id'],folder,validity,high));c.commit()
                            print(a['id'],folder,': nowa granica; wcześniejsze maile zostają w archiwum.')
                        ready.append(folder)
                except Exception as exc:
                    plan['warnings'].append(a['id']+' / '+folder+': '+str(exc)[:200])
            if ready:plan['accounts'].append({'id':a['id'],'folders':ready})
        except Exception as exc:plan['warnings'].append(a['id']+': '+type(exc).__name__+'. Sprawdź hasło i połączenie.')
        finally:
            if m:
                with contextlib.suppress(Exception):m.logout()
    if not plan['accounts']:raise RuntimeError('Żadna skrzynka nie jest gotowa. Sprawdź komendy folders i hasła; harmonogram nie został włączony.')
    return plan

def job_definitions(s):
    base={'WorkingDirectory':str(s.ROOT),'EnvironmentVariables':{'SEBASTIAN_DATA':str(s.DATA),'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'}}
    result={}
    for kind in ('panel','jobs'):
        label='pl.sebastian.'+kind
        job={**base,'Label':label,'ProgramArguments':[str(s.ROOT/'.venv/bin/python'),str(s.ROOT/'sebastian.py'),'serve' if kind=='panel' else 'morning-run'],
             'StandardOutPath':str(s.DATA/'logs'/(kind+'.log')),'StandardErrorPath':str(s.DATA/'logs'/(kind+'.err'))}
        if kind=='panel':job.update(RunAtLoad=True,KeepAlive=True,ThrottleInterval=15)
        else:job.update(StartCalendarInterval={'Hour':6,'Minute':30},StartInterval=900,RunAtLoad=True)
        result[label]=job
    return result

def install(s,plan):
    agents=pathlib.Path.home()/'Library/LaunchAgents';agents.mkdir(parents=True,exist_ok=True)
    (s.DATA/'logs').mkdir(exist_ok=True)
    # Disable previous jobs while replacing definitions. No old 07:00/20:30 job remains.
    previous={};loaded=[]
    for label in job_definitions(s):
        path=agents/(label+'.plist');previous[label]=path.read_bytes() if path.exists() else None
    s.write_json(s.DATA/'automation.json',plan)
    try:
        for label,job in job_definitions(s).items():
            path=agents/(label+'.plist')
            subprocess.run(['launchctl','bootout','gui/'+str(os.getuid()),str(path)],capture_output=True)
            path.write_bytes(plistlib.dumps(job));subprocess.run(['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)],check=True,capture_output=True);loaded.append(label)
        plan['enabled']=True;s.write_json(s.DATA/'automation.json',plan)
    except Exception:
        for label in loaded:subprocess.run(['launchctl','bootout','gui/'+str(os.getuid())+'/'+label],capture_output=True)
        for label,data in previous.items():
            path=agents/(label+'.plist')
            if data is None:path.unlink(missing_ok=True)
            else:
                path.write_bytes(data);subprocess.run(['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)],capture_output=True)
        plan['enabled']=False;s.write_json(s.DATA/'automation.json',plan)
        raise RuntimeError('Nie udało się uruchomić launchd; przywrócono wcześniejsze pliki harmonogramu. Podeślij komunikat.')
    print('OK — poranek od '+plan['start_date']+' o 06:30 czasu Maca. Panel działa w tle.')
    print('Konta:',', '.join(a['id'] for a in plan['accounts']))
    for warning in plan['warnings']:print('UWAGA:',warning)
    print('Mac musi być włączony, zalogowany, z dostępnym Pękiem kluczy i Internetem. Przy uśpieniu praca ruszy później, po wybudzeniu.')

def should_run(c,plan,now,force=False):
    if force:return True
    if not plan.get('enabled') or now.date().isoformat()<plan['start_date'] or (now.hour,now.minute)<(6,30):return False
    rows=c.execute('SELECT state FROM morning_runs WHERE substr(started,1,10)=?',(now.date().isoformat(),)).fetchall()
    return not any(r['state']=='ok' for r in rows) and len(rows)<4

def execute(s,force=False):
    path=s.DATA/'automation.json'
    if not path.exists():raise RuntimeError('Najpierw python sebastian.py morning-setup')
    plan=json.loads(path.read_text());clock=dt.datetime.now(s.TZ)
    with contextlib.closing(s.db()) as c:
        if not should_run(c,plan,clock,force):
            try:s.build_report();s.bridge()
            except Exception as ex:print('Odświeżenie pamięci WebUI:',type(ex).__name__)
            return
        c.execute("UPDATE morning_runs SET state='interrupted',finished=? WHERE state='running'",(s.now(),))
        job=c.execute("INSERT INTO morning_runs(started,state,details) VALUES(?,'running','{}')",(s.now(),)).lastrowid;c.commit()
        boundary=c.execute('SELECT COALESCE(MAX(id),0) FROM runs').fetchone()[0]
    details={'errors':[],'accounts':[],'new':0,'analyzed':0,'pending':0,'limited':False};state='failed';awake=None
    try:
        if sys.platform=='darwin':awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for ready in plan['accounts']:
            a=next((a for a in s.config()['accounts'] if a['id']==ready['id']),None)
            if not a:continue
            try:s.ingest({**a,'folders':ready['folders']},'sync',200)
            except Exception as ex:details['errors'].append(a['id']+': '+type(ex).__name__)
        with contextlib.closing(s.db()) as c:
            runs=[dict(r) for r in c.execute('SELECT * FROM runs WHERE id>?',(boundary,))]
            details['accounts']=[{key:r[key] for key in ('account','folder','added','selected','error')} for r in runs]
            details['new']=sum(r['added'] for r in runs)
            details['limited']=any(r['selected']>=200 for r in runs)
            details['errors'] += [r['account']+'/'+r['folder']+': '+r['error'][:180] for r in runs if r['error']]
            before=c.execute("SELECT count(*) FROM messages WHERE arrival='new' AND analysis IS NOT NULL").fetchone()[0]
            c.execute("INSERT OR IGNORE INTO morning_items SELECT ?,id FROM messages WHERE arrival='new' AND (analysis IS NULL OR imported>=?)",(job,clock.isoformat(timespec='seconds')));c.commit()
        ensure_ollama(s)
        s.analyze(200,retry=True,new_only=True)
        with contextlib.closing(s.db()) as c:
            after=c.execute("SELECT count(*) FROM messages WHERE arrival='new' AND analysis IS NOT NULL").fetchone()[0]
            details['analyzed']=after-before
            details['pending']=c.execute("SELECT count(*) FROM messages WHERE arrival='new' AND analysis IS NULL").fetchone()[0]
        state='partial' if details['errors'] or details['pending'] or details['limited'] else 'ok'
    except Exception as ex:details['errors'].append(type(ex).__name__+': '+str(ex)[:200])
    finally:
        if awake:awake.terminate()
        with contextlib.closing(s.db()) as c:
            details['pending']=c.execute("SELECT count(*) FROM messages WHERE arrival='new' AND analysis IS NULL").fetchone()[0]
            c.execute('UPDATE morning_runs SET finished=?,state=?,details=? WHERE id=?',(s.now(),state,json.dumps(details,ensure_ascii=False),job));c.commit()
        s.build_report()
        try:s.bridge()
        except Exception:print('Kopia WebUI nie została odświeżona; raport lokalny pozostaje dostępny.')
        print('Poranek:',state,'nowe:',details['new'],'analizy:',details['analyzed'],'oczekujące:',details['pending'])
