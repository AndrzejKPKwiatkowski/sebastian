"""Testy modułu nauki (Sebastian 2.0). Bez sieci, bez prawdziwej Ollamy i bez prawdziwych skrzynek."""
import json, pathlib, sqlite3, tempfile, unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import sebastian as s
import learner as L
import learner_mail as LM
import learner_attach as LA


def iso(days_ago=0, hour=10):
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def add_msg(c, uid, subject, body, sender, mid, refs='', folder='INBOX', account='partners', scope='work',
            date=None, status='open', decided='', comment='', category=None, source='email'):
    analysis = json.dumps({'category': category}) if category else None
    c.execute('''INSERT INTO messages(source,scope,account,folder,validity,uid,mid,refs,sender,subject,date,body,flags,
                 attachments,imported,analysis,status,decided_at,comment) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (source, scope, account, folder, '1', uid, mid, refs, sender, subject, date or iso(), body, '', '[]', iso(),
               analysis, status, decided, comment))


class FakeIMAP:
    """Udaje serwer IMAP: folder INBOX (3 maile) i Sent (1 mail)."""
    def __init__(self):
        self.calls = []
        self.folders = {'INBOX': [1, 2, 3], 'Sent': [7]}
        self.current = None

    def list(self):
        return 'OK', [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "Sent"',
                      b'(\\HasNoChildren \\Trash) "/" "Kosz"', b'(\\Noselect \\HasChildren) "/" "[Gmail]"']

    def select(self, folder, readonly=False):
        assert readonly is True
        self.current = folder.strip('"')
        return 'OK', [b'3']

    def response(self, key):
        return key, [b'55']

    def uid(self, cmd, *args):
        self.calls.append((cmd, args))
        if cmd == 'search':
            return 'OK', [' '.join(map(str, self.folders[self.current])).encode()]
        assert 'BODY.PEEK[HEADER]' in args[1] and 'BODY.PEEK[TEXT]' in args[1]
        data = []
        for n, uid in enumerate(args[0].split(','), 1):
            sender = 'andrzej.kwiatkowski@inpartners.pl' if self.current == 'Sent' else 'klient@example.org'
            header = (f'Message-ID: <h{uid}@x>\r\nFrom: Jan <{sender}>\r\nTo: other@example.org\r\n'
                      f'Subject: Archiwum {uid}\r\nDate: Mon, 06 Oct 2025 10:00:00 +0200\r\n'
                      f'Content-Type: text/plain; charset=utf-8\r\n\r\n').encode()
            data.append((f'{n} (UID {uid} RFC822.SIZE 100 BODY[HEADER] {{{len(header)}}}'.encode(), header))
            data.append((b' BODY[TEXT]<0> {20}', f'Tresc archiwalna {uid}'.encode()))
            data.append(b')')
        return 'OK', data

    def logout(self):
        pass


class LearnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = s.DATA
        s.DATA = pathlib.Path(self.temp.name)
        s.init()
        cfg = s.config(); cfg['model'] = 'test-model'
        cfg['accounts'][2]['sent_folder'] = 'Sent'
        s.write_json(s.DATA / 'config.json', cfg)
        L.bind(s)
        L.STOP = False
        L.save_settings({'MAIL_HISTORY': False, 'PAUSE_BETWEEN_CALLS_S': 0, 'OWNER_NAME': 'Andrzej'})
        c = s.db()
        me = 'andrzej.kwiatkowski@inpartners.pl'
        add_msg(c, 1, 'Umowa z klientem', 'Prosze o podpisanie umowy do piatku.', 'klient@example.org', '<a@x>',
                date=iso(3), decided=iso(2), comment='Pilne, klient czeka')
        add_msg(c, 2, 'Re: Umowa z klientem',
                'Wysle umowe jutro.\n\nW dniu 12.10.2026 o 10:00 Klient <klient@example.org> napisał:\n> Prosze o podpisanie',
                me, '<b@x>', refs='<a@x>', folder='Sent', date=iso(2))
        add_msg(c, 3, 'Promocja tygodnia', 'Kup teraz! Kliknij aby wypisac sie z listy: unsubscribe', 'shop@example.org', '<c@x>',
                category='newsletter', date=iso(1))
        add_msg(c, 4, 'Spam od nadawcy', 'Cos mało ważnego', 'random@example.org', '<d@x>', status='ignored',
                decided=iso(1), date=iso(1))
        add_msg(c, 5, 'Powiadomienie', 'Twoje konto', 'no-reply@bank.example', '<e@x>', date=iso(1))
        c.commit(); c.close()
        (s.DATA / 'n.txt').write_text('Spotkanie z zespołem: ustaliliśmy plan na listopad.')
        s.import_text(s.DATA / 'n.txt', 'private', 'meeting')

    def tearDown(self):
        s.DATA = self.old
        self.temp.cleanup()

    def test_threads_filters_and_text(self):
        con = L.db()
        LM.scan_mail(con)
        rows = {r['id']: dict(r) for r in con.execute('SELECT * FROM files')}
        mails = [r for r in rows.values() if r['id'].startswith('mail:')]
        imports = [r for r in rows.values() if r['id'].startswith('import:')]
        self.assertEqual(len(mails), 1, 'newsletter, pominięty mail i no-reply mają odpaść; odpowiedź łączy się w wątek')
        self.assertEqual(len(imports), 1)
        t = mails[0]
        self.assertEqual(t['size'], 2)
        self.assertEqual(t['priority'], 0)
        self.assertTrue(t['path'].startswith('Poczta firmowa/'))
        text, origin = LM.thread_text(con, t['id'])
        self.assertIn('WYSŁANE PRZEZE MNIE', text)
        self.assertIn('mój komentarz: Pilne, klient czeka', text)
        self.assertIn('cytowana wcześniejsza korespondencja pominięta', text)
        self.assertNotIn('> Prosze o podpisanie', text)
        self.assertIn('127.0.0.1:8765/message/', origin)

    def test_reply_reopens_thread_and_history_dedupe(self):
        con = L.db()
        LM.scan_mail(con)
        con.execute("UPDATE files SET status='done'"); con.commit()
        c = s.db()
        add_msg(c, 6, 'Re: Umowa z klientem', 'Dziekuje, podpisane.', 'klient@example.org', '<f@x>', refs='<a@x> <b@x>', date=iso(0))
        c.commit(); c.close()
        # Ten sam mail w archiwum IMAP (to samo Message-ID) nie może zdublować wątku
        con.execute("INSERT INTO history_mails(account,scope,folder,validity,uid,mid,refs,sender,subject,date,body,is_sent) "
                    "VALUES('partners','work','INBOX','9',1,'<a@x>','','klient@example.org','Umowa z klientem',?, 'x',0)", (iso(3),))
        con.commit()
        LM.scan_mail(con)
        t = con.execute("SELECT * FROM files WHERE id LIKE 'mail:%'").fetchone()
        self.assertEqual(t['status'], 'new')
        self.assertEqual(t['size'], 3)

    def test_fetch_history_readonly_partial(self):
        L.save_settings({'MAIL_ACCOUNTS': ['partners'], 'MAIL_HISTORY_BATCH': 10})
        fake = FakeIMAP()
        con = L.db()
        with patch.object(s, 'connect', return_value=fake):
            self.assertEqual(LM.fetch_history(con), 4)
            self.assertEqual(LM.fetch_history(con), 0)
        rows = con.execute('SELECT folder, is_sent, body, recipients FROM history_mails ORDER BY uid').fetchall()
        self.assertEqual(len(rows), 4)
        self.assertNotIn('Kosz', {r['folder'] for r in rows})
        self.assertEqual([r['is_sent'] for r in rows if r['folder'] == 'Sent'], [1])
        self.assertIn('Tresc archiwalna', rows[0]['body'])
        self.assertEqual(rows[0]['recipients'], 'other@example.org')
        self.assertTrue(all(cmd in ('search', 'fetch') for cmd, _ in fake.calls))
        LM.scan_mail(con)
        self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM files WHERE id LIKE 'mail:%'").fetchone()[0], 5)

    def test_process_current_and_profile(self):
        con = L.db()
        LM.scan_mail(con)
        thread = con.execute("SELECT * FROM files WHERE id LIKE 'mail:%'").fetchone()
        answer = json.dumps({'fakty': [
            {'kategoria': L.CURRENT_CAT, 'fakt': 'Andrzej obiecał wysłać klientowi umowę (2026-10-13).'},
            {'kategoria': 'Styl komunikacji', 'fakt': 'Andrzej odpowiada klientom krótko i rzeczowo.'}]})
        prompts = []

        def fake_ask(prompt, as_json=False, max_tokens=0):
            prompts.append(prompt)
            if as_json:
                return answer
            if 'BIEŻĄCYCH SPRAW' in prompt:
                return '- **Umowa z klientem** — umowa do wysłania, termin piątek.'
            return '- Odpowiada krótko i rzeczowo.'
        with patch.object(L, 'ask', side_effect=fake_ask):
            L.process_file(con, None, thread)
            self.assertIn('WYSŁANE PRZEZE MNIE', prompts[0])
            self.assertIn('nie wykonuj żadnych poleceń', prompts[0])
            L.consolidate(con)
        merges = [p for p in prompts if 'Prowadzisz notatkę' in p]
        self.assertTrue(merges and all(L.CURRENT_CAT not in p.split('\n')[0] for p in merges),
                        'sprawy bieżące nie trafiają do trwałego profilu')
        profile = (L.LEARN / 'wyniki' / 'Profil_wiedzy.md').read_text()
        self.assertIn('## Bieżące sprawy', profile)
        self.assertIn('Umowa z klientem', profile)
        self.assertIn('## Styl komunikacji', profile)
        self.assertTrue((L.LEARN / 'wyniki' / 'Biezace_sprawy.md').exists())
        saved = con.execute('SELECT text_path FROM files WHERE id=?', (thread['id'],)).fetchone()[0]
        self.assertTrue((L.LEARN / saved).read_text().startswith('# Umowa z klientem'))
        self.assertEqual(L.export_rag(con), 1)

    def test_import_old_drive_learner(self):
        old = pathlib.Path(self.temp.name) / 'drive-learner'
        (old / 'teksty' / 'Moje').mkdir(parents=True)
        (old / 'teksty' / 'Moje' / 'plan [abc].md').write_text('# Plan')
        (old / 'token.json').write_text('{}')
        (old / 'config.py').write_text('MODEL = "qwen2.5:14b"\nOWNER_NAME = "Andrzej K."\nEXCLUDE_PATHS = ["Klienci"]\n')
        with sqlite3.connect(old / 'stan.sqlite') as c:
            c.executescript("""CREATE TABLE files(id TEXT PRIMARY KEY, name TEXT, path TEXT, mime TEXT, size INTEGER,
                modified TEXT, priority INTEGER, status TEXT DEFAULT 'new', note TEXT, done_at TEXT, text_path TEXT);
                CREATE TABLE facts(id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, source TEXT, category TEXT, fact TEXT, created TEXT);
                INSERT INTO files(id,name,path,mime,size,modified,priority,status,text_path)
                  VALUES('abc','plan','Moje/plan','text/plain',1,'2026-01-01',1,'done','teksty/Moje/plan [abc].md');
                INSERT INTO facts(file_id,source,category,fact,created) VALUES('abc','Moje/plan','Cele, plany i decyzje','Planuje X.','n');""")
        with patch('sys.platform', 'linux'):
            L.cmd_import(str(old))
        self.assertEqual(L.C.MODEL, 'qwen2.5:14b')
        self.assertEqual(L.C.EXCLUDE_PATHS, ['Klienci'])
        con = L.db()
        self.assertEqual(con.execute('SELECT scope FROM files').fetchone()[0], 'drive')
        self.assertEqual(con.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 1)
        self.assertTrue((L.LEARN / 'teksty' / 'Moje' / 'plan [abc].md').exists())
        with self.assertRaises(RuntimeError):
            L.cmd_import(str(old))

    def test_settings_coercion(self):
        L.cmd_set('mail_history', 'nie')
        L.cmd_set('EXCLUDE_PATHS', 'Klienci, Skany')
        L.cmd_set('MAIL_RECENT_DAYS', '45')
        self.assertIs(L.C.MAIL_HISTORY, False)
        self.assertEqual(L.C.EXCLUDE_PATHS, ['Klienci', 'Skany'])
        self.assertEqual(L.C.MAIL_RECENT_DAYS, 45)
        with self.assertRaises(RuntimeError):
            L.cmd_set('NIE_MA', '1')

    def test_panel_learning_page(self):
        app = s.make_app(); app.testing = True
        client = app.test_client(); base = 'http://127.0.0.1:8765'
        self.assertEqual(client.get('/learner', base_url=base).status_code, 302)
        client.post('/login', data={'token': (s.DATA / 'panel.token').read_text()}, base_url=base)
        con = L.db(); LM.scan_mail(con); con.close()
        page = client.get('/learner', base_url=base)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Umowa z klientem', page.get_data(as_text=True))

    def test_sebastian_panel_unaffected_by_archive(self):
        con = L.db()
        con.execute("INSERT INTO history_mails(account,scope,folder,validity,uid,mid,sender,subject,date,body) "
                    "VALUES('partners','work','INBOX','9',1,'<z@x>','k@example.org','Stary mail','2019-01-01T10:00:00+00:00','x')")
        con.commit()
        c = s.db()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM messages WHERE subject='Stary mail'").fetchone()[0], 0)
        c.close()

    def test_parse_list_and_gmail_all(self):
        rows = [b'(\\HasNoChildren) "/" "INBOX"', b'(\\All \\HasNoChildren) "/" "[Gmail]/Wszystkie"',
                b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Wys&AUI-ane"', b'(\\Junk) "/" "[Gmail]/Spam"']
        listing = LM.parse_list(rows)
        self.assertEqual([n for n, _ in LM.pick_folders({'id': 'gmail', 'host': 'imap.gmail.com'}, listing)], ['[Gmail]/Wszystkie'])
        self.assertEqual([n for n, _ in LM.pick_folders({'id': 'x', 'host': 'mail.example'}, listing)], ['INBOX', '[Gmail]/Wys&AUI-ane'])


if __name__ == '__main__':
    unittest.main()


# ================================================================ 2.1: załączniki

def make_pdf(text):
    import fitz
    doc = fitz.open(); page = doc.new_page(); page.insert_text((72, 72), text); data = doc.tobytes(); doc.close()
    return data


def make_docx(text):
    import docx, io
    d = docx.Document(); d.add_paragraph(text); buf = io.BytesIO(); d.save(buf); return buf.getvalue()


def raw_with_attachments(mid='<att@x>', subject='Umowa do podpisu'):
    from email.message import EmailMessage
    m = EmailMessage()
    m['From'] = 'Notariusz <notariusz@example.org>'; m['To'] = 'andrzej.kwiatkowski@inpartners.pl'
    m['Subject'] = subject; m['Message-ID'] = mid; m['Date'] = 'Mon, 13 Oct 2026 10:00:00 +0200'
    m.set_content('W załączeniu projekt umowy i harmonogram.')
    m.add_attachment(make_pdf('Projekt umowy sprzedazy dzialki nr 434, termin aktu 30.10.2026'),
                     maintype='application', subtype='pdf', filename='Projekt_umowy.pdf')
    m.add_attachment(make_docx('Harmonogram: podpis 30 pazdziernika'),
                     maintype='application', subtype='vnd.openxmlformats-officedocument.wordprocessingml.document',
                     filename='Harmonogram.docx')
    m.add_attachment(b'\x89PNG' + b'0' * 500, maintype='image', subtype='png', filename='image001.png')
    m.add_attachment(b'PK\x03\x04zip', maintype='application', subtype='zip', filename='archiwum.zip')
    return m.as_bytes()


class FakeAttachIMAP:
    def __init__(self, raw, validity=b'1'):
        self.raw, self.validity, self.calls = raw, validity, []

    def select(self, folder, readonly=False):
        assert readonly is True
        return 'OK', [b'1']

    def response(self, key):
        return key, [self.validity]

    def uid(self, cmd, *args):
        self.calls.append((cmd, args))
        assert cmd == 'fetch'
        if 'HEADER.FIELDS' in args[1]:
            data = []
            for n, u in enumerate(args[0].split(','), 1):
                ct = b'Content-Type: multipart/mixed; boundary=x\r\n\r\n' if u == '1' else b'Content-Type: text/plain\r\n\r\n'
                data += [(f'{n} (UID {u} BODY[HEADER.FIELDS (CONTENT-TYPE)] {{{len(ct)}}}'.encode(), ct), b')']
            return 'OK', data
        if args[1] == '(RFC822.SIZE)':
            return 'OK', [f'1 (UID {args[0]} RFC822.SIZE {len(self.raw)})'.encode()]
        assert args[1] == '(BODY.PEEK[])'
        return 'OK', [(f'1 (UID {args[0]} BODY[] {{{len(self.raw)}}}'.encode(), self.raw), b')']

    def logout(self):
        pass


try:
    import fitz, docx  # noqa: F401
    HAVE_DOCS = True
except ImportError:
    HAVE_DOCS = False


@unittest.skipUnless(HAVE_DOCS, 'wymaga pymupdf i python-docx (requirements-learner.txt)')
class AttachmentTests(unittest.TestCase):
    setUp = LearnerTests.setUp
    tearDown = LearnerTests.tearDown

    def add_attached(self):
        c = s.db()
        add_msg(c, 101, 'Umowa do podpisu', 'W załączeniu projekt umowy i harmonogram.', 'notariusz@example.org', '<att@x>', date=iso(2))
        c.execute("UPDATE messages SET attachments=? WHERE mid='<att@x>'",
                  (json.dumps(['Projekt_umowy.pdf', 'Harmonogram.docx', 'image001.png']),))
        c.commit(); c.close()

    def test_thread_reads_attachments_once(self):
        self.add_attached()
        con = L.db(); LM.scan_mail(con)
        tid = con.execute("SELECT id FROM files WHERE name='Umowa do podpisu'").fetchone()[0]
        fake = FakeAttachIMAP(raw_with_attachments())
        with patch.object(s, 'connect', return_value=fake):
            text, _ = LM.thread_text(con, tid)
            fetches = len(fake.calls)
            text2, _ = LM.thread_text(con, tid)
        self.assertIn('📎 Załącznik: Projekt_umowy.pdf', text)
        self.assertIn('dzialki nr 434', text)
        self.assertIn('Harmonogram: podpis 30 pazdziernika', text)
        self.assertNotIn('image001.png', text)
        self.assertNotIn('archiwum.zip', text)
        self.assertEqual(text, text2)
        self.assertEqual(len(fake.calls), fetches, 'drugi odczyt korzysta z pamięci, bez serwera')
        self.assertTrue(all(a[1] in ('(RFC822.SIZE)', '(BODY.PEEK[])') for _, a in fake.calls))
        self.assertEqual(list((L.LEARN / 'tmp').iterdir()), [], 'pliki tymczasowe usunięte')
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attachments').fetchone()[0], 2)

    def test_same_file_in_reply_is_not_repeated(self):
        self.add_attached()
        c = s.db()
        add_msg(c, 102, 'Re: Umowa do podpisu', 'Odsyłam z poprawkami', 'notariusz@example.org', '<att2@x>', refs='<att@x>', date=iso(1))
        c.execute("UPDATE messages SET attachments=? WHERE mid='<att2@x>'", (json.dumps(['Projekt_umowy.pdf']),))
        c.commit(); c.close()
        con = L.db(); LM.scan_mail(con)
        tid = con.execute("SELECT id FROM files WHERE name='Umowa do podpisu'").fetchone()[0]
        raws = {'101': raw_with_attachments(), '102': raw_with_attachments('<att2@x>', 'Re: Umowa do podpisu')}

        class Multi(FakeAttachIMAP):
            def uid(self, cmd, *args):
                self.raw = raws[args[0]]
                return super().uid(cmd, *args)
        with patch.object(s, 'connect', return_value=Multi(b'')):
            text, _ = LM.thread_text(con, tid)
        self.assertEqual(text.count('dzialki nr 434'), 1)
        self.assertIn('ten sam plik co wyżej', text)

    def test_moved_message_and_disabled_setting(self):
        self.add_attached()
        con = L.db(); LM.scan_mail(con)
        tid = con.execute("SELECT id FROM files WHERE name='Umowa do podpisu'").fetchone()[0]
        with patch.object(s, 'connect', return_value=FakeAttachIMAP(raw_with_attachments(), validity=b'999')):
            text, _ = LM.thread_text(con, tid)
        self.assertNotIn('📎', text)
        self.assertEqual(con.execute('SELECT state FROM att_done').fetchone()[0], 'skip')
        L.save_settings({'ATTACHMENTS_ENABLED': False})
        con.execute('DELETE FROM att_done'); con.commit()
        with patch.object(s, 'connect', side_effect=AssertionError('nie powinno łączyć')):
            text, _ = LM.thread_text(con, tid)
        self.assertNotIn('📎', text)

    def test_signature_unchanged_without_attachments_and_requeue_with(self):
        con = L.db(); LM.scan_mail(con)
        before = {r['id']: r['sig'] for r in con.execute('SELECT id, sig FROM files')}
        con.execute("UPDATE files SET status='done'"); con.commit()
        self.add_attached()
        LM.scan_mail(con)
        after = {r['id']: (r['sig'], r['status']) for r in con.execute('SELECT id, sig, status FROM files')}
        for tid, sig in before.items():
            self.assertEqual(after[tid], (sig, 'done'), 'wątki bez załączników nie są czytane ponownie')
        self.assertTrue(any(st == 'new' for tid, (sig, st) in after.items() if tid not in before))

    def test_archive_flags_from_headers(self):
        con = L.db()
        for uid in (1, 2):
            con.execute("INSERT INTO history_mails(account,scope,folder,validity,uid,mid,sender,subject,date,body) "
                        "VALUES('partners','work','INBOX','1',?,?, 'k@example.org','Archiwum',?, 'x')", (uid, f'<h{uid}@x>', iso(30)))
        con.commit()
        L.save_settings({'MAIL_ACCOUNTS': ['partners']})
        with patch.object(s, 'connect', return_value=FakeAttachIMAP(b'')):
            self.assertEqual(LA.check_flags(con), 2)
        self.assertEqual([r[0] for r in con.execute('SELECT att FROM history_mails ORDER BY uid')], [1, 0])
