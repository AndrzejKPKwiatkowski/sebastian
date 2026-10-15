import importlib.util,json,os,pathlib,tempfile,unittest
from unittest.mock import patch
import sebastian as s

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old=s.DATA; s.DATA=pathlib.Path(self.temp.name); s.init()
    def tearDown(self): s.DATA=self.old; self.temp.cleanup()
    def test_sample(self):
        ids=list(range(1,501)); result=s.choose_uids(ids,'pilot',100,set(),0)
        self.assertEqual(len(result),100); self.assertEqual(len(set(result)),100)
        self.assertTrue(set(range(431,501)).issubset(result))
        self.assertEqual(s.choose_uids(ids,'sync',2,{1,2,4},2),[3,5])
    def test_mime_html_and_truncation(self):
        raw=b'Subject: Test\r\nFrom: X <x@example.org>\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Hello</p><script>bad()</script><img src="https://remote">world'
        m=s.parse_mail(raw,7); self.assertNotIn('bad',m['body']); self.assertEqual(m['truncated'],1)
    def test_unsubstantiated_due(self):
        v={'summary':'x','category':'termin','action':'x','due':'2026-11-01','evidence':'made up'}
        self.assertEqual(s.validate_result(v,'source')['due'],'')
        with self.assertRaises(ValueError): s.validate_result({'category':'x'},'')
    def test_imap_readonly_dedupe_and_incremental(self):
        class Fake:
            ids=list(range(1,11)); calls=[]
            def select(self,folder,readonly=False):
                assert readonly is True; return 'OK',[b'10']
            def response(self,key): return key,[b'1']
            def uid(self,cmd,*args):
                self.calls.append((cmd,args))
                if cmd=='search': return 'OK',[' '.join(map(str,self.ids)).encode()]
                assert 'BODY.PEEK[]' in args[1]
                uid=args[0]
                return 'OK',[(b'FLAGS ()',('Message-ID: <'+uid+'@test>\r\nSubject: Test '+uid+'\r\nContent-Type: text/plain\r\n\r\nHello').encode())]
            def logout(self): pass
        fake=Fake(); a=s.account('gmail')
        with patch.object(s,'connect',return_value=fake):
            s.ingest(a,'pilot',5); s.ingest(a,'pilot',5)
            c=s.db(); self.assertEqual(c.execute('select count(*) from messages').fetchone()[0],5); c.close()
            fake.ids+=list(range(11,16))
            s.ingest(a,'sync',2); s.ingest(a,'sync',2); s.ingest(a,'sync',2)
            c=s.db(); self.assertEqual(c.execute('select count(*) from messages where uid>10').fetchone()[0],5); c.close()
            s.ingest(a,'backfill',100)
            c=s.db(); self.assertEqual(c.execute('select count(*) from messages').fetchone()[0],15); c.close()
        self.assertEqual({x[0] for x in fake.calls},{'search','fetch'})
    def test_panel_csrf_and_decision(self):
        s.demo(); app=s.make_app(); app.testing=True; client=app.test_client(); base='http://127.0.0.1:8765'
        self.assertEqual(client.get('/',base_url=base).status_code,302)
        client.post('/login',data={'token':(s.DATA/'panel.token').read_text()},base_url=base)
        self.assertEqual(client.get('/',base_url=base).status_code,200)
        self.assertEqual(client.post('/decision/1',data={},base_url=base).status_code,403)
        # Cookie domain/session access needs same host for session_transaction.
        with client.session_transaction(base_url=base) as sess: csrf=sess['csrf']
        response=client.post('/decision/1',data={'csrf':csrf,'status':'done','category':'informacja','project':'Moj cel'},base_url=base)
        self.assertEqual(response.status_code,302)
        c=s.db(); self.assertEqual(c.execute('select status from messages where id=1').fetchone()[0],'done'); c.close()
        self.assertEqual(client.get('/',base_url='http://evil.example').status_code,403)
    def test_import_idempotent(self):
        f=s.DATA/'note.txt'; f.write_text('Hello '*3000)
        s.import_text(f,'private','note'); s.import_text(f,'private','note')
        c=s.db(); self.assertEqual(c.execute('select count(*) from messages').fetchone()[0],2); c.close()
    def test_ai_success_failure_retry(self):
        f=s.DATA/'note.txt'; f.write_text('Prosze o odpowiedz.')
        s.import_text(f,'private','note')
        cfg=s.config(); cfg['model']='local-test'; s.write_json(s.DATA/'config.json',cfg)
        with patch.object(s.requests,'post',side_effect=ValueError('broken')):
            s.analyze(10)
        c=s.db(); self.assertEqual(c.execute('select error from messages').fetchone()[0],'ValueError'); c.close()
        with patch.object(s.requests,'post') as post:
            s.analyze(10); post.assert_not_called()
            post.return_value.json.return_value={'message':{'content':json.dumps({'summary':'Prosba','category':'odpowiedz','action':'Odpowiedz','due':'','evidence':'Prosze o odpowiedz.'})}}
            s.analyze(10,retry=True)
            self.assertEqual(post.call_args.kwargs['json']['model'],'local-test')
        c=s.db(); row=c.execute('select analysis,error from messages').fetchone(); self.assertIsNone(row['error']); self.assertEqual(json.loads(row['analysis'])['category'],'odpowiedz'); c.close()
    def test_webui_access_scope(self):
        import openwebui_tool as t
        s.demo(); tool=t.Tools(); tool.valves.REPORT_PATH=str(s.DATA/'exports/bridge.json')
        self.assertIn('Brak dostepu',tool.moje_sprawy(__user__={'email':'me@example.org'}))
        tool.valves.ALLOWED_EMAIL='me@example.org'
        result=json.loads(tool.moje_sprawy(__user__={'email':'me@example.org'}))
        self.assertTrue(all(x['scope']=='private' for x in result['records']))
        result=json.loads(tool.moje_sprawy(message_id=2,__user__={'email':'me@example.org'}))
        self.assertEqual(result['records'],[])
if __name__=='__main__': unittest.main()
