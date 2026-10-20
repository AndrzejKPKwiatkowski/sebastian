"""Testy modułu WhatsApp (Sebastian 2.3). Bez WhatsAppa, bez Ollamy — model i połączenie są udawane."""
import contextlib, datetime as dt, json, os, pathlib, queue, re, shutil, tempfile, time, unittest
from unittest.mock import patch
from types import SimpleNamespace

import sebastian as s
import whatsapp as W

BASE = "http://127.0.0.1:8765"
OWNER = "48600111222"
WIFE = "48500999888"


def fake_ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
    if "Przygotuj" in prompt:
        assert "Dziś:" in prompt
        return json.dumps({"tekst": "Dzień dobry, Andrzej! Wtorek.\n• *Umowa* — termin jutro\n• 2 zadania otwarte",
                           "glos": "Hej Andrzej! Dziś wtorek. Najważniejsza jest umowa z klientem, termin mija jutro, więc "
                                   "proponuję zacząć od niej zaraz po kawie. Poza tym masz dwa otwarte zadania. Miłego dnia!"})
    if "Pytanie:" in prompt:
        return "Według poczty: dokumenty do spotkania czekają na potwierdzenie."
    raise AssertionError(prompt[:80])


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = s.DATA
        s.DATA = pathlib.Path(self.temp.name)
        s.init()
        s.demo()
        cfg = s.config()
        cfg["model"] = "test-model"
        s.write_json(s.DATA / "config.json", cfg)
        W.bind(s)
        W.STOP = False
        W.save_settings({"WA_ENABLED": True, "WA_TRANSPORT": "plik", "WA_OWNER_PHONE": OWNER, "WA_OWNER_NAME": "Andrzej",
                         "WA_VOICE": False})
        with contextlib.closing(s.db()) as c:
            due = (dt.date.today() + dt.timedelta(days=1)).isoformat()
            r = c.execute("SELECT id, analysis FROM messages WHERE subject='Dokumenty do spotkania'").fetchone()
            ai = json.loads(r["analysis"]); ai["due"] = due
            c.execute("UPDATE messages SET is_task=1, status='open', decided_at=?, task_title='Potwierdzić dokumenty', "
                      "analysis=?, arrival='new', imported=? WHERE id=?", (s.now(), json.dumps(ai), s.now(), r["id"]))
            c.execute("UPDATE messages SET arrival='new', imported=?", (s.now(),))
            c.commit()
        self.patches = [patch.object(W, "ask", fake_ask)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        W.STOP = False
        s.DATA = self.old
        self.temp.cleanup()

    def con(self):
        return contextlib.closing(W.db())


class WhatsAppTests(Base):

    # ---------------------------------------------------------------- przegląd

    def test_brief_from_model_and_fallback(self):
        data = W.gather("rano")
        self.assertEqual(len(data["tasks"]), 1)
        self.assertIn("Potwierdzić dokumenty", W.context_text(data))
        text, voice, source = W.compose("rano", data)
        self.assertEqual(source, "model")
        self.assertTrue(voice.startswith("Hej Andrzej!"))
        with patch.object(W, "ask", lambda *a, **k: None):
            text, voice, source = W.compose("rano", data)
        self.assertEqual(source, "awaryjny")
        self.assertIn("Zadania otwarte: 1", text)
        self.assertTrue(voice.startswith("Hej Andrzej!"))

    def test_scopes_filter_work_mail(self):
        W.save_settings({"WA_SCOPES": ["private"]})
        data = W.gather("rano")
        self.assertEqual(data["tasks"], [])            # zadanie było w zakresie „work”
        self.assertNotIn("Dokumenty do spotkania", W.context_text(data))

    def test_brief_is_queued_and_sent_with_voice(self):
        W.save_settings({"WA_VOICE": True})
        fake_ogg = W.home() / "nagrania" / "x.ogg"
        fake_ogg.parent.mkdir(parents=True, exist_ok=True)
        fake_ogg.write_bytes(b"OggS")
        with patch.object(W, "synthesize", lambda text, base: (fake_ogg, fake_ogg.with_suffix(".wav"))):
            with self.con() as con:
                W.make_brief(con, "rano", send=True)
                kinds = [r["kind"] for r in con.execute("SELECT kind FROM outbox ORDER BY id")]
                self.assertEqual(kinds, ["text", "voice"])
                t = W.FileTransport()
                t.start()
                self.assertEqual(W.flush(con, t), 2)
                self.assertEqual(W.meta_get(con, "sent:rano"), W.now().date().isoformat())
        files = sorted(p.suffix for p in (W.home() / "wyslane").iterdir())
        self.assertEqual(files, [".ogg", ".txt"])

    def test_schedule(self):
        tz = s.TZ
        at = lambda h, m=0: dt.datetime.combine(dt.date(2026, 10, 20), dt.time(h, m), tz)  # wtorek  # noqa: E731
        with self.con() as con, patch.object(W, "morning_running", lambda: False):
            self.assertIsNone(W.due_kind(con, at(6, 50)))
            self.assertEqual(W.due_kind(con, at(7, 5)), "rano")
            self.assertIsNone(W.due_kind(con, at(12, 0)))           # po WA_BRIEF_LATEST już nie
            W.meta_set(con, "sent:rano", "2026-10-20")
            self.assertIsNone(W.due_kind(con, at(7, 30)))
            W.save_settings({"WA_EVENING": True})
            self.assertEqual(W.due_kind(con, at(20, 45)), "wieczor")
            W.meta_set(con, "sent:rano", "")
            W.save_settings({"WA_BRIEF_DAYS": [1, 3, 4, 5]})          # bez wtorku
            self.assertIsNone(W.due_kind(con, at(7, 5)))
        W.save_settings({"WA_BRIEF_DAYS": [1, 2, 3, 4, 5, 6, 7]})
        with self.con() as con, patch.object(W, "morning_running", lambda: True):
            self.assertIsNone(W.due_kind(con, at(7, 30)))            # czeka na poranną analizę…
            self.assertEqual(W.due_kind(con, at(8, 1)), "rano")      # …ale najwyżej godzinę

    def test_service_tick_sends_due_brief_and_requested_brief(self):
        t = W.FileTransport()
        t.start()
        with self.con() as con, patch.object(W, "due_kind", lambda con: "rano"):
            W.tick(con, t, queue.Queue(), {"beat": 0})
            purposes = [r[0] for r in con.execute("SELECT purpose FROM outbox WHERE status='sent' ORDER BY id")]
            self.assertEqual(purposes, ["welcome", "brief:rano"])       # powitanie tylko raz, potem przegląd
            W.tick(con, t, queue.Queue(), {"beat": 0})
            self.assertEqual(con.execute("SELECT COUNT(*) FROM outbox WHERE purpose='welcome'").fetchone()[0], 1)
        with self.con() as con, patch.object(W, "due_kind", lambda con: None):
            W.enqueue(con, "make", "wieczor", purpose="manual")
            W.tick(con, t, queue.Queue(), {"beat": 0})
            self.assertEqual(con.execute("SELECT COUNT(*) FROM briefs WHERE kind='wieczor'").fetchone()[0], 1)
            self.assertFalse(con.execute("SELECT 1 FROM outbox WHERE status='pending'").fetchone())
            self.assertTrue(W.meta_get(con, "heartbeat"))

    # ---------------------------------------------------------------- rozmowa

    def test_commands(self):
        with self.con() as con:
            self.assertIn("zrobione 2", W.handle(con, "Pomoc")[0])
            text = W.handle(con, "zadania")[0]
            self.assertIn("1. Potwierdzić dokumenty", text)
            self.assertIn("termin: jutro", text)
            self.assertIn("Zrobione", W.handle(con, "Zrobione 1")[0])
            self.assertIn("już zamknięte", W.handle(con, "zrobione 1")[0])
            self.assertIn("Nie znam zadania", W.handle(con, "zrobione 7")[0])
            self.assertEqual(W.handle(con, "przegląd")[2], "rano")
            self.assertEqual(W.handle(con, "Co dziś")[2], "rano")
            self.assertIn("Zapamiętane", W.handle(con, "Zapamiętaj: klient X woli telefon")[0])
            self.assertIn("Wyciszone", W.handle(con, "cisza do 14")[0])
            self.assertTrue(W.muted(con))
            W.handle(con, "wznów")
            self.assertFalse(W.muted(con))
            self.assertIn("Nowe maile", W.handle(con, "poczta")[0])
            self.assertIn("dokumenty do spotkania", W.handle(con, "Co z dokumentami do spotkania?")[0])
        with contextlib.closing(s.db()) as c:
            r = c.execute("SELECT * FROM messages WHERE task_title='Potwierdzić dokumenty'").fetchone()
            self.assertEqual((r["status"], r["decision_kind"]), ("done", "whatsapp_done"))
            self.assertTrue(c.execute("SELECT 1 FROM events WHERE action='whatsapp_done'").fetchone())
            self.assertTrue(c.execute("SELECT 1 FROM undo_decisions WHERE message_id=?", (r["id"],)).fetchone())
            note = c.execute("SELECT * FROM knowledge_notes WHERE body LIKE 'klient X%'").fetchone()
            self.assertEqual((note["scope"], note["active"]), ("private", 1))

    def test_calendar_command(self):
        today = dt.date.today()
        ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//t//PL\r\nBEGIN:VEVENT\r\nUID:a@b\r\nDTSTAMP:20260101T000000Z\r\n"
               f"DTSTART;TZID=Europe/Warsaw:{today:%Y%m%d}T101500\r\nDTEND;TZID=Europe/Warsaw:{today:%Y%m%d}T110000\r\n"
               "SUMMARY:Spotkanie z klientem\r\nLOCATION:Biuro\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        with contextlib.closing(s.db()) as c:
            c.execute("INSERT INTO calendar_sources(name,content,imported) VALUES(?,?,?)", ("Praca", ics, s.now()))
            c.commit()
        with self.con() as con:
            text = W.handle(con, "kalendarz")[0]
        self.assertIn("10:15 Spotkanie z klientem — Biuro", text)
        self.assertIn("10:15 Spotkanie z klientem", W.context_text(W.gather("rano")))

    def test_incoming_flow(self):
        t = W.FileTransport()
        t.start()
        with self.con() as con:
            W.handle_incoming(con, t, {"id": "A1", "kind": "text", "text": "zadania", "ts": time.time()})
            sent = (W.home() / "wyslane")
            self.assertTrue(any("Potwierdzić" in p.read_text() for p in sent.glob("*.txt")))
            before = len(list(sent.iterdir()))
            W.handle_incoming(con, t, {"id": "A1", "kind": "text", "text": "zadania", "ts": time.time()})   # duplikat
            W.handle_incoming(con, t, {"id": "OLD", "kind": "text", "text": "pomoc", "ts": time.time() - 8 * 3600})  # stara
            own = con.execute("SELECT wa_id FROM outbox WHERE status='sent' LIMIT 1").fetchone()["wa_id"]
            W.handle_incoming(con, t, {"id": own, "kind": "text", "text": "echo", "ts": time.time()})   # nasza własna
            self.assertEqual(len(list(sent.iterdir())), before)
            W.handle_incoming(con, t, {"id": "V1", "kind": "voice", "audio_bytes": b"x", "ts": time.time()})
            self.assertTrue(any("głosówkę" in p.read_text() for p in sent.glob("*.txt")))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 3)   # echo nie trafia do skrzynki

    def test_voice_reply_to_voice(self):
        fake_ogg = W.home() / "nagrania" / "r.ogg"
        fake_ogg.parent.mkdir(parents=True, exist_ok=True)
        fake_ogg.write_bytes(b"OggS")
        W.save_settings({"WA_VOICE": True})
        with self.con() as con, patch.object(W, "transcribe", lambda b: "co z dokumentami do spotkania"), \
                patch.object(W, "synthesize", lambda text, base: (fake_ogg, None)):
            ft = W.FileTransport()
            ft.start()
            W.handle_incoming(con, ft, {"id": "V2", "kind": "voice", "audio_bytes": b"x", "ts": time.time()})
            kinds = [r["kind"] for r in con.execute("SELECT kind FROM outbox WHERE purpose='reply' ORDER BY id")]
            self.assertEqual(kinds, ["text", "voice"])
            self.assertEqual(con.execute("SELECT text FROM inbox WHERE wa_id='V2'").fetchone()[0], "co z dokumentami do spotkania")

    # ---------------------------------------------------------------- powiadomienia

    def test_notices_quiet_hours_dedupe_and_learner_hook(self):
        import learner
        with patch.object(W, "in_quiet", lambda at=None: True):
            oid = W.notice("Dokument gotowy", "KW Kraków")
        self.assertIsNotNone(oid)
        self.assertIsNone(W.notice("Dokument gotowy", "KW Kraków"))          # bez powtórzeń w ciągu doby
        with self.con() as con:
            r = con.execute("SELECT * FROM outbox WHERE id=?", (oid,)).fetchone()
            self.assertGreater(r["not_before"], W.now().isoformat(timespec="seconds"))
            W.meta_set(con, "mute_until", (W.now() + dt.timedelta(hours=2)).isoformat())
        self.assertIsNone(W.notice("Inne", "x"))
        with self.con() as con:
            W.meta_set(con, "mute_until", "")
        learner.bind(s)
        with patch.object(learner.sys, "platform", "linux"):
            learner.notify("Sebastian — dokumenty", "Błąd przy „KW”.")
        with self.con() as con:
            self.assertTrue(con.execute("SELECT 1 FROM outbox WHERE body LIKE '%dokumenty%Błąd%'").fetchone())
        W.save_settings({"WA_ENABLED": False})
        self.assertIsNone(W.notice("x", "y"))

    # ---------------------------------------------------------------- głos (prawdziwy ffmpeg)

    @unittest.skipUnless(shutil.which("ffmpeg"), "brak ffmpeg")
    def test_synthesize_converts_to_opus(self):
        import subprocess, wave, struct, math
        real_run = subprocess.run

        def fake_run(args, *a, **k):
            if "-m" in args and "piper" in args:          # „Piper”: zapisuje 1 s tonu
                wav = args[args.index("-f") + 1]
                with wave.open(wav, "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
                    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 10))) for i in range(22050)))
                return subprocess.CompletedProcess(args, 0, "", "")
            return real_run(args, *a, **k)
        with patch.object(W, "voice_engine", lambda: "piper"), patch.object(W, "piper_model", lambda: pathlib.Path("x.onnx")), \
                patch.object(W.subprocess, "run", fake_run):
            ogg, wav = W.synthesize("Hej *Andrzej*! https://x.pl Test.", W.home() / "nagrania" / "t")
        self.assertTrue(ogg.exists() and wav.exists())
        probe = real_run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(ogg)],
                         capture_output=True, text=True).stdout.strip()
        self.assertEqual(probe, "opus")
        self.assertEqual(W.speakable("Hej *Andrzej*! https://x.pl a@b.pl Test."), "Hej Andrzej ! Test.")

    # ---------------------------------------------------------------- panel

    def test_panel(self):
        app = s.make_app()
        app.testing = True
        c = app.test_client()
        c.post("/login", data={"token": (s.DATA / "panel.token").read_text()}, base_url=BASE)
        with c.session_transaction(base_url=BASE) as sess:
            csrf = sess["csrf"]
        self.assertEqual(c.get("/whatsapp", base_url=BASE).status_code, 200)
        self.assertEqual(c.post("/whatsapp/akcja", data={"akcja": "preview", "rodzaj": "rano", "csrf": "zly"}, base_url=BASE).status_code, 403)
        r = c.post("/whatsapp/akcja", data={"akcja": "preview", "rodzaj": "rano", "csrf": csrf}, base_url=BASE)
        self.assertEqual(r.status_code, 302)
        page = c.get("/whatsapp", base_url=BASE).get_data(as_text=True)
        self.assertIn("Najważniejsza jest umowa", page)
        with self.con() as con:
            self.assertFalse(con.execute("SELECT 1 FROM outbox").fetchone())           # podgląd niczego nie wysyła
        c.post("/whatsapp/akcja", data={"akcja": "send", "rodzaj": "rano", "csrf": csrf}, base_url=BASE)
        with self.con() as con:
            self.assertEqual(con.execute("SELECT kind, body FROM outbox").fetchone()[:], ("make", "rano"))
        self.assertEqual(c.get("/whatsapp/nagranie/1", base_url=BASE).status_code, 404)  # podgląd bez głosu

    def test_cli_routing_and_settings(self):
        with patch("sys.argv", ["sebastian.py", "wa-status"]), patch.object(W, "cmd_status") as st:
            s.main()
            st.assert_called_once()
        self.assertEqual(W.coerce("WA_OWNER_PHONE", "+48 600-111-222"), OWNER)
        self.assertEqual(W.coerce("WA_OWNER_PHONE", "600111222"), OWNER)
        self.assertEqual(W.coerce("WA_BRIEF_DAYS", "1,2,3"), [1, 2, 3])
        self.assertEqual(W.coerce("WA_BRIEF_TIME", "7:30"), "07:30")
        with self.assertRaises(ValueError):
            W.coerce("WA_OWNER_PHONE", "123")


class FamilyTests(Base):
    """2.3.1: żona może pisać do Sebastiana — widzi tylko sprawy prywatne."""
    def setUp(self):
        super().setUp()
        with patch.object(W, "agent_loaded", lambda: False):
            W.cmd_user("dodaj", WIFE, "Kasia", "Kasiu", "żona", "tak", "tak")
        self.wife = W.user_by_phone(WIFE)
        with contextlib.closing(s.db()) as c:       # prywatne zadanie (demo: Gmail = private)
            r = c.execute("SELECT id FROM messages WHERE scope='private' LIMIT 1").fetchone()
            c.execute("UPDATE messages SET is_task=1, status='open', decided_at=?, task_title='Opłacić przedszkole' WHERE id=?",
                      (s.now(), r["id"]))
            c.commit()

    def test_family_sees_only_private(self):
        self.assertEqual((self.wife["role"], self.wife["call"], self.wife["brief"]), ("rodzina", "Kasiu", True))
        prompts = []

        def spy(prompt, **k):
            prompts.append(prompt)
            return fake_ask(prompt, **k) if "Przygotuj" in prompt else "Według kalendarza dziś nic."
        with self.con() as con, patch.object(W, "ask", spy):
            text = W.handle(con, "zadania", user=self.wife)[0]
            self.assertIn("Opłacić przedszkole", text)
            self.assertNotIn("Potwierdzić dokumenty", text)         # zadanie firmowe
            self.assertNotIn("zrobione", text)
            self.assertIn("tylko", W.handle(con, "zrobione 1", user=self.wife)[0])
            self.assertIn("tylko", W.handle(con, "dokumenty", user=self.wife)[0])
            self.assertIn("Sprawy firmowe są poza", W.handle(con, "pomoc", user=self.wife)[0])
            W.handle(con, "Co z dokumentami do spotkania?", user=self.wife)
            self.assertIn("Rozmawiasz z Kasia (żona Andrzej)", prompts[-1])
            self.assertNotIn("Dokumenty do spotkania", prompts[-1])
            W.handle(con, "zapamiętaj: kupić prezent dla mamy", user=self.wife)
            # właściciel dalej widzi wszystko
            self.assertIn("Potwierdzić dokumenty", W.handle(con, "zadania")[0])
        with contextlib.closing(s.db()) as c:
            self.assertTrue(c.execute("SELECT 1 FROM knowledge_notes WHERE body='Od Kasia: kupić prezent dla mamy'").fetchone())

    def test_family_brief_welcome_and_routing(self):
        tz = s.TZ
        at = dt.datetime.combine(dt.date(2026, 10, 20), dt.time(7, 5), tz)
        t = W.FileTransport()
        t.start()
        with self.con() as con, patch.object(W, "morning_running", lambda: False):
            self.assertEqual([u["phone"] for u in W.due_family(con, at)], [WIFE])
            W.make_brief(con, "rano", send=True, user=self.wife)
            r = con.execute("SELECT * FROM outbox").fetchone()
            self.assertEqual((r["to_phone"], r["purpose"]), (WIFE, f"brief:rano:{WIFE}"))
            W.flush(con, t)
            self.assertEqual(W.meta_get(con, f"sent:rano:{WIFE}"), W.now().date().isoformat())
            self.assertIsNone(W.meta_get(con, "sent:rano"))            # przegląd właściciela osobno
            self.assertEqual(W.due_family(con, at), [])
            b = con.execute("SELECT * FROM briefs").fetchone()
            self.assertEqual(b["for_phone"], WIFE)
        self.assertTrue(any(p.name.startswith(WIFE) for p in (W.home() / "wyslane").iterdir()))
        with self.con() as con, patch.object(W, "due_kind", lambda con: None), patch.object(W, "due_family", lambda con: []):
            W.tick(con, t, queue.Queue(), {"beat": 0})
            welcomes = {r["to_phone"]: r["body"] for r in con.execute("SELECT * FROM outbox WHERE purpose='welcome'")}
            self.assertIn("Cześć, Kasiu!", welcomes[WIFE])
            self.assertIn("spraw firmowych nie znam", welcomes[WIFE])
            W.handle_incoming(con, t, {"id": "K1", "kind": "text", "text": "kalendarz", "ts": time.time(), "from": WIFE})
            self.assertEqual(con.execute("SELECT to_phone FROM outbox WHERE purpose='reply'").fetchone()[0], WIFE)
            self.assertEqual(con.execute("SELECT from_phone FROM inbox WHERE wa_id='K1'").fetchone()[0], WIFE)
            W.handle_incoming(con, t, {"id": "X1", "kind": "text", "text": "pomoc", "ts": time.time(), "from": "48111"})
            self.assertFalse(con.execute("SELECT 1 FROM inbox WHERE wa_id='X1'").fetchone())
        with patch.object(W, "agent_loaded", lambda: False):
            W.cmd_user("usun", WIFE)
        self.assertIsNone(W.user_by_phone(WIFE))


class FullAccessTests(Base):
    """2.5: numer z dostępem „pełny” — jak właściciel (np. żona), a inne numery dalej ignorowane."""
    def setUp(self):
        super().setUp()
        with patch.object(W, "agent_loaded", lambda: False):
            W.cmd_user("dodaj", WIFE, "Kasia", "Kasiu", "żona", "nie", "nie", "pelny")
        self.wife = W.user_by_phone(WIFE)

    def test_full_access_like_owner(self):
        self.assertEqual(self.wife["role"], "pelny")
        self.assertTrue(W.full(self.wife))
        self.assertFalse(W.is_owner(self.wife))
        prompts = []

        def spy(prompt, **k):
            prompts.append(prompt)
            return "OK."
        with self.con() as con, patch.object(W, "ask", spy):
            text = W.handle(con, "zadania", user=self.wife)[0]
            self.assertIn("Potwierdzić dokumenty", text)                 # zadanie firmowe też
            self.assertNotIn("tylko", W.handle(con, "dokumenty", user=self.wife)[0][:80])
            W.handle(con, "Co z dokumentami do spotkania?", user=self.wife)
            self.assertIn("pełny dostęp", prompts[-1])
            self.assertIn("✓ Zrobione", W.handle(con, "zrobione 1", user=self.wife)[0])
            # numeracja zadań osobna dla każdej osoby
            self.assertTrue(W.meta_get(con, f"task_numbers:{WIFE}"))
        with W.as_user(self.wife):
            self.assertEqual(sorted(W.allowed_scopes()), sorted(W.C.WA_SCOPES))
        t = W.FileTransport()
        t.start()
        with self.con() as con, patch.object(W, "due_kind", lambda con: None), patch.object(W, "due_family", lambda con: []):
            W.tick(con, t, queue.Queue(), {"beat": 0})
            body = con.execute("SELECT body FROM outbox WHERE purpose='welcome' AND to_phone=?", (WIFE,)).fetchone()[0]
            self.assertIn("taki sam dostęp", body)
            W.handle_incoming(con, t, {"id": "X2", "kind": "text", "text": "zadania", "ts": time.time(), "from": "48777"})
            self.assertFalse(con.execute("SELECT 1 FROM inbox WHERE wa_id='X2'").fetchone())   # spoza listy — ignorowany
        with patch.object(W, "agent_loaded", lambda: False), self.assertRaises(RuntimeError):
            W.cmd_user("dodaj", "48555666777", "X", "X", "", "nie", "nie", "admin")


class WatchTests(Base):
    """2.4: Sebastian czyta Twojego WhatsAppa (tylko odczyt) i podpowiada, komu odpisać / do kogo oddzwonić."""
    def setUp(self):
        super().setUp()
        import whatsapp_watch as WW
        self.WW = WW
        W.save_settings({"WA_WATCH": True, "WA_WATCH_IGNORE": ["kurier"]})
        h = 3600
        nowt = int(time.time())
        msgs = [
            ("a1", "48111", "Jan Nowak", False, nowt - 20 * h, "text", "Cześć, potwierdzisz termin spotkania w piątek?"),
            ("b1", "48222", "Ola", False, nowt - 10 * h, "call", "połączenie przychodzące"),
            ("c1", "48333", "Marek", False, nowt - 9 * h, "text", "Wysłałem umowę"),
            ("c2", "48333", "Marek", True, nowt - 8 * h, "text", "Dzięki, przeczytam"),
            ("k1", "48999", "Kurier DPD", False, nowt - 5 * h, "text", "Paczka dziś"),
        ] + [(f"q{i}", "48444", "Tomek", i % 2 == 0, nowt - (30 + i) * 86400, "text", "hej") for i in range(12)]
        with contextlib.closing(WW.db()) as con:
            for mid, chat, name, me, ts, kind, text in msgs:
                WW.store(con, {"id": mid, "chat": chat, "chat_name": name, "sender": "48999000" if me else chat,
                               "sender_name": "" if me else name, "from_me": me, "is_group": False, "ts": ts,
                               "kind": kind, "text": text})

    def fake_digest_ask(self, prompt, **k):
        if "rozmowy z WhatsAppa" in prompt:
            ids = re.findall(r"\[(R\d+)\] ([^\n\[]+)", prompt)
            out = []
            for rid, name in ids:
                if "Jan" in name:
                    out.append({"id": rid, "o_czym": "Jan pyta o termin spotkania w piątek.", "co_zrobic": "odpisz",
                                "dlaczego": "czeka na potwierdzenie"})
                if "Marek" in name:
                    out.append({"id": rid, "o_czym": "Marek wysłał umowę.", "co_zrobic": "nic", "dlaczego": ""})
            return json.dumps({"rozmowy": out}, ensure_ascii=False)
        if "Oto rozmowa" in prompt:
            assert "potwierdzisz termin" in prompt
            return "Rozmawialiście o terminie spotkania — warto odpisać."
        return fake_ask(prompt, **k)

    def test_flags_without_model(self):
        with contextlib.closing(self.WW.db()) as con:
            cs = {c["name"]: c for c in self.WW.chats(con, int(time.time()) - 86400)}
            self.assertTrue(cs["Jan Nowak"]["waiting"])
            self.assertFalse(cs["Marek"]["waiting"])                     # odpisałeś
            self.assertEqual(len(cs["Ola"]["callback"]), 1)               # nieodebrane, brak kontaktu potem
            self.assertNotIn("Kurier DPD", cs)                            # na liście pomijanych
            quiet = self.WW.quiet_friends(con)
        self.assertEqual([q["name"] for q in quiet], ["Tomek"])
        with patch.object(W, "ask", lambda *a, **k: None):
            d = self.WW.digest(since=int(time.time()) - 86400, cache=False)
        acts = {it["name"]: it["co_zrobic"] for it in d["items"]}
        self.assertEqual(acts, {"Ola": "oddzwoń", "Jan Nowak": "odpisz", "Marek": "nic"})

    def test_digest_text_brief_and_commands(self):
        with patch.object(W, "ask", self.fake_digest_ask):
            d = self.WW.digest(since=int(time.time()) - 86400, cache=False)
            text = self.WW.digest_text(d)
            self.assertIn("Jan Nowak — Jan pyta o termin", text)
            self.assertIn("📞 *Oddzwoń:* Ola", text)
            self.assertIn("✉️ *Odpisz:* Jan Nowak", text)
            self.assertIn("Tomek (cisza od", text)
            data = W.gather("rano")
            self.assertIn("Jan pyta o termin", W.context_text(data))
            with self.con() as con:
                W.make_brief(con, "rano", send=True)
                purposes = [r[0] for r in con.execute("SELECT purpose FROM outbox ORDER BY id")]
                self.assertEqual(purposes, ["brief:rano", "digest"])
                self.assertIn("Oddzwoń", W.handle(con, "do kogo?")[0])
                self.assertIn("Jan Nowak", W.handle(con, "kto pisał")[0])
                self.assertIn("Jan Nowak", W.handle(con, "rozmowa jan")[0])
                self.assertIn("Nie widzę rozmowy", W.handle(con, "rozmowa Zenon")[0])
        with patch.object(W, "agent_loaded", lambda: False):
            W.cmd_user("dodaj", WIFE, "Kasia", "Kasiu", "żona", "tak", "tak")
        with self.con() as con:
            self.assertIn("tylko", W.handle(con, "kto pisał", user=W.user_by_phone(WIFE))[0])
            self.assertIn("tylko", W.handle(con, "whatsapp", user=W.user_by_phone(WIFE))[0])
        with patch.object(W, "ask", self.fake_digest_ask), W.as_user(W.user_by_phone(WIFE)):
            self.assertIsNone(W.gather("rano")["whatsapp"])                 # żona nie widzi Twojego WhatsAppa

    def test_watch_off_and_cleanup(self):
        W.save_settings({"WA_WATCH": False})
        with self.con() as con:
            self.assertIn("wa-watch login", W.handle(con, "whatsapp")[0])
        W.save_settings({"WA_WATCH_KEEP_DAYS": 7})
        with contextlib.closing(self.WW.db()) as con:
            self.assertEqual(self.WW.cleanup(con), 12)                     # wiadomości z Tomkiem sprzed 30+ dni

    def test_watch_tick_stores_queue(self):
        class FakeWatcher:
            connected, logged_out, needs_login = True, False, False
            queue = queue.Queue()
        w = FakeWatcher()
        w.queue.put({"id": "n1", "chat": "48555", "chat_name": "Ewa", "sender": "48555", "from_me": False,
                     "is_group": False, "ts": int(time.time()), "kind": "text", "text": "Zadzwoń proszę"})
        with self.con() as con:
            W.watch_tick(con, w)
            self.assertEqual(W.meta_get(con, "watch_connected"), "1")
            w.logged_out = True
            W.watch_tick(con, w)
            self.assertTrue(con.execute("SELECT 1 FROM outbox WHERE body LIKE '%Straciłem wgląd%'").fetchone())
        with contextlib.closing(self.WW.db()) as con:
            self.assertEqual(con.execute("SELECT text FROM wmsg WHERE id='n1'").fetchone()[0], "Zadzwoń proszę")


class MemoryTests(WatchTests):
    """2.5: rozmowy na stałe, załączniki, nauka z rozmów, akta osób."""
    def test_permanent_by_default(self):
        W.save_settings({"WA_WATCH_KEEP_DAYS": 0})
        with contextlib.closing(self.WW.db()) as con:
            self.assertEqual(self.WW.cleanup(con), 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM wmsg WHERE chat='48444'").fetchone()[0], 12)
        self.assertEqual(W.DEFAULTS["WA_WATCH_KEEP_DAYS"], 0)

    def pdf(self, text):
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), text)
        return doc.tobytes()

    def test_attachments_read_once_and_in_transcript(self):
        pdf = self.pdf("Umowa najmu lokalu. Czynsz miesieczny 2500 zl, termin platnosci do 10 dnia miesiaca.")
        with contextlib.closing(self.WW.db()) as con:
            for mid in ("f1", "f2"):
                self.WW.store(con, {"id": mid, "chat": "48111", "chat_name": "Jan Nowak", "sender": "48111", "from_me": False,
                                    "is_group": False, "ts": int(time.time()), "kind": "doc", "text": "[dokument: umowa.pdf]",
                                    "file_bytes": pdf, "file_name": "umowa.pdf", "file_mime": "application/pdf"})
            self.assertEqual(con.execute("SELECT COUNT(*) FROM wattach").fetchone()[0], 1)        # ten sam plik raz
            self.assertIn("Czynsz", con.execute("SELECT text FROM wattach").fetchone()[0])
            text = self.WW.transcript(con, "48111")
            self.assertIn("📎 Załącznik: umowa.pdf", text)
            self.assertIn("ten sam plik co wyżej", text)
            self.assertIn("Czynsz", " ".join(c["lines"][-1] for c in self.WW.chats(con, 0) if c["chat"] == "48111"))
        self.assertFalse((W.home() / "pliki").exists())                                        # domyślnie tylko tekst

    def test_learning_from_conversations(self):
        import learner as L
        L.bind(s)
        with contextlib.closing(self.WW.db()) as con:
            for i, (me, txt) in enumerate([(False, "Czy możesz podpisać umowę do piątku?"), (True, "Tak, podpiszę w czwartek"),
                                           (False, "Super, dzięki")]):
                self.WW.store(con, {"id": f"l{i}", "chat": "48111", "chat_name": "Jan Nowak", "sender": "48111", "from_me": me,
                                    "is_group": False, "ts": int(time.time()) - 100 + i, "kind": "text", "text": txt})
        self.assertGreaterEqual(self.WW.sync_learning(), 1)
        month = dt.datetime.now(s.TZ).strftime("%Y-%m")
        fid = f"wa:48111:{month}"
        with contextlib.closing(L.db()) as lc:
            f = lc.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
            self.assertEqual((f["status"], f["scope"]), ("new", "whatsapp"))
        self.assertEqual(self.WW.sync_learning(), 0)                                              # bez zmian — bez pracy
        text = self.WW.learning_text(fid)
        self.assertIn("WYSŁANE PRZEZE MNIE: Tak, podpiszę w czwartek", text)
        facts = json.dumps({"fakty": [{"kategoria": L.CURRENT_CAT, "fakt": "Andrzej podpisze umowę z Janem Nowakiem w czwartek."}]})
        # 2.5.1: w osobnym procesie nauki moduł WhatsAppa nie jest podłączony (W.S = None) — nauka podłącza go sama
        with patch.object(L, "ask", lambda *a, **k: facts), patch.object(W, "S", None), contextlib.closing(L.db()) as lc:
            L.process_file(lc, None, lc.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone())
            self.assertEqual(lc.execute("SELECT status FROM files WHERE id=?", (fid,)).fetchone()[0], "done")
            st = L.stats(lc)
            self.assertEqual((st["wa_done"], st["drive_all"]), (1, 0))
        with contextlib.closing(self.WW.db()) as con:
            self.WW.store(con, {"id": "l9", "chat": "48111", "chat_name": "Jan Nowak", "sender": "48111", "from_me": False,
                                "is_group": False, "ts": int(time.time()), "kind": "text", "text": "Jeszcze jedno"})
        self.WW.sync_learning()
        with contextlib.closing(L.db()) as lc:
            self.assertEqual(lc.execute("SELECT status FROM files WHERE id=?", (fid,)).fetchone()[0], "new")   # nowa wiadomość → ponownie
        with patch.object(W, "agent_loaded", lambda: False):
            W.cmd_user("dodaj", WIFE, "Kasia", "Kasiu", "żona", "nie", "nie")
        with W.as_user(W.user_by_phone(WIFE)):
            self.assertNotIn("czwartek", W.search_context("kiedy podpisze umowę Jan"))            # rodzina nie widzi WhatsAppa
        self.assertIn("czwartek", W.search_context("kiedy podpisze umowę Jan"))

    def test_people_notes(self):
        def ask(prompt, **k):
            if "Prowadzisz akta" in prompt:
                if "WhatsAppie: Jan Nowak" not in prompt:
                    return "**Kim jest dla Andrzej** Znajomy."
                self.assertIn("potwierdzisz termin", prompt)
                return "**Kim jest dla Andrzej** Klient.\n**Otwarte / do zrobienia** Potwierdzić termin w piątek."
            if "Pytanie:" in prompt:
                self.assertIn("Akta: Jan Nowak", prompt)
                return "Jan czeka na potwierdzenie terminu."
            return self.fake_digest_ask(prompt, **k)
        with patch.object(W, "ask", ask):
            self.assertGreaterEqual(self.WW.update_people(limit=5), 1)
            self.assertIn("Potwierdzić termin", self.WW.person_text("jan"))
            with self.con() as con:
                self.assertIn("Klient", W.handle(con, "kto to Jan?")[0])
                self.assertIn("Jan czeka", W.handle(con, "Co mam ustalić z Jan?")[0])
            self.assertEqual(self.WW.update_people(limit=5), 0)                                  # nic nowego
        self.assertTrue(any("Jan Nowak" in p.name for p in (W.home() / "ludzie").iterdir()))
        with patch.object(W, "agent_loaded", lambda: False):
            W.cmd_user("dodaj", WIFE, "Kasia", "Kasiu", "żona", "nie", "nie")
        with self.con() as con:
            self.assertIn("tylko", W.handle(con, "kto to Jan", user=W.user_by_phone(WIFE))[0])
            self.assertIn("tylko", W.handle(con, "co wiem o Janie", user=W.user_by_phone(WIFE))[0])


# ---------------------------------------------------------------- filtr nadawcy na prawdziwych strukturach neonize

try:
    from neonize.proto import Neonize_pb2 as N
    from neonize.proto.waE2E import WAWebProtobufsE2E_pb2 as E
    import whatsapp_link
    HAVE_NEONIZE = True
except Exception:
    HAVE_NEONIZE = False


class FakeClient:
    def __init__(self):
        self.sent = []

    def download_any(self, m):
        return b"OGGDATA"

    def mark_read(self, *a, **k):
        self.marked = True

    def get_pn_from_lid(self, jid):
        return N.JID(User=OWNER if jid.User == "999" else "1", Server="s.whatsapp.net")

    def send_message(self, jid, msg):
        self.sent.append((jid.User, msg))
        return type("R", (), {"ID": f"OUT{len(self.sent)}"})()

    def build_audio_message(self, data, ptt=False):
        return E.Message(audioMessage=E.AudioMessage(PTT=ptt, mimetype="audio/ogg"))


@unittest.skipUnless(HAVE_NEONIZE, "brak biblioteki neonize")
class WatcherParseTests(unittest.TestCase):
    """Obserwacja: odczyt prawdziwych struktur neonize — bez wysyłania czegokolwiek."""
    def watcher(self):
        import whatsapp_watch as WW
        w = WW.Watcher.__new__(WW.Watcher)
        client = FakeClient()
        client.contact = type("CS", (), {"get_contact": lambda self, jid: N.ContactInfo(FullName="Jan Nowak" if jid.User == "48111" else "")})()
        client.get_group_info = lambda jid: N.GroupInfo(GroupName=N.GroupName(Name="Rodzina"))
        w.client, w.groups, w.names, w.me = client, False, {}, OWNER
        return w

    def ev(self, sender, msg, chat=None, from_me=False, group=False, server="s.whatsapp.net", push="Janek"):
        src = N.MessageSource(Chat=N.JID(User=chat or sender, Server="g.us" if group else server),
                              Sender=N.JID(User=sender, Server=server), IsFromMe=from_me, IsGroup=group)
        return N.Message(Info=N.MessageInfo(MessageSource=src, ID="W1", Timestamp=int(time.time()), Pushname=push), Message=msg)

    def test_parse(self):
        w = self.watcher()
        m = w.parse(self.ev("48111", E.Message(conversation="Hej")))
        self.assertEqual((m["chat"], m["chat_name"], m["kind"], m["from_me"]), ("48111", "Jan Nowak", "text", False))
        m = w.parse(self.ev("48777", E.Message(conversation="Hej")))
        self.assertEqual(m["chat_name"], "Janek")                         # brak w kontaktach → nazwa z profilu
        v = w.parse(self.ev("48111", E.Message(audioMessage=E.AudioMessage(PTT=True))))
        self.assertEqual((v["kind"], v["audio_bytes"]), ("voice", b"OGGDATA"))
        i = w.parse(self.ev("48111", E.Message(imageMessage=E.ImageMessage(caption="faktura"))))
        self.assertEqual((i["kind"], i["text"]), ("image", "faktura"))
        mine = w.parse(self.ev(OWNER, E.Message(conversation="Jasne"), chat="48111", from_me=True))
        self.assertTrue(mine["from_me"])
        self.assertEqual(mine["chat"], "48111")
        lid = w.parse(self.ev("999", E.Message(conversation="x"), server="lid"))
        self.assertEqual(lid["chat"], OWNER)                              # LID przeliczony na numer
        self.assertIsNone(w.parse(self.ev("48111", E.Message(conversation="x"), chat="120363", group=True)))
        self.assertIsNone(w.parse(self.ev("48111", E.Message(conversation="x"), chat="status", server="broadcast")))
        self.assertIsNone(w.parse(self.ev("48111", E.Message(reactionMessage=E.ReactionMessage(text="👍")))))
        w.groups = True
        g = w.parse(self.ev("48111", E.Message(conversation="x"), chat="120363", group=True))
        self.assertEqual((g["chat_name"], g["is_group"]), ("Rodzina", True))
        self.assertFalse(hasattr(w.client, "marked"))                     # nic nie jest oznaczane jako przeczytane

    def test_history_sync(self):
        from neonize.proto.waHistorySync import WAWebProtobufsHistorySync_pb2 as H
        from neonize.proto.waWeb import WAWebProtobufsWeb_pb2 as Wb
        from neonize.proto.waCommon import WACommon_pb2 as Cm
        w = self.watcher()

        def wm(mid, from_me, msg, ts=1760000000):
            return H.HistorySyncMsg(message=Wb.WebMessageInfo(key=Cm.MessageKey(remoteJID="48111@s.whatsapp.net", fromMe=from_me, ID=mid),
                                                               message=msg, messageTimestamp=ts, pushName="Janek"))
        data = H.HistorySync(syncType=H.HistorySync.INITIAL_BOOTSTRAP, conversations=[
            H.Conversation(ID="48111@s.whatsapp.net", name="Jan Nowak", messages=[
                wm("h1", False, E.Message(conversation="Pamiętasz o spotkaniu?")),
                wm("h2", True, E.Message(conversation="Tak, będę")),
                wm("h3", False, E.Message(audioMessage=E.AudioMessage(PTT=True))),
                wm("h4", False, E.Message(documentMessage=E.DocumentMessage(fileName="oferta.pdf", fileLength=1000))),
                wm("h5", False, E.Message(reactionMessage=E.ReactionMessage(text="👍")))]),
            H.Conversation(ID="status@broadcast", messages=[wm("s1", False, E.Message(conversation="x"))]),
            H.Conversation(ID="120363@g.us", messages=[wm("g1", False, E.Message(conversation="x"))])])
        got = {m["id"]: m for m in w.parse_history(data)}
        self.assertEqual(sorted(got), ["h1", "h2", "h3", "h4"])
        self.assertEqual((got["h1"]["chat"], got["h1"]["chat_name"], got["h1"]["from_me"]), ("48111", "Jan Nowak", False))
        self.assertTrue(got["h2"]["from_me"])
        self.assertEqual((got["h3"]["kind"], got["h3"]["text"], got["h3"]["audio_bytes"]), ("voice", "[głosówka]", None))
        self.assertEqual((got["h4"]["kind"], got["h4"]["file_name"], got["h4"]["file_bytes"]), ("doc", "oferta.pdf", b"OGGDATA"))


@unittest.skipUnless(HAVE_NEONIZE, "brak biblioteki neonize")
class LinkFilterTests(unittest.TestCase):
    def transport(self, me):
        t = whatsapp_link.LinkedTransport.__new__(whatsapp_link.LinkedTransport)
        t.client, t.owner, t.me, t.me_lid, t.sent_ids = FakeClient(), OWNER, me, "555", set()
        t.phones, t.lids = [OWNER, WIFE], {}
        t.log = None
        t.on_skip, t.skipped = None, {}
        return t

    def ev(self, sender, chat=None, from_me=False, group=False, text="pomoc", sender_server="s.whatsapp.net", alt="",
           audio=False, mid="M1"):
        src = N.MessageSource(Chat=N.JID(User=chat or sender, Server="s.whatsapp.net"),
                              Sender=N.JID(User=sender, Server=sender_server), IsFromMe=from_me, IsGroup=group,
                              SenderAlt=N.JID(User=alt, Server="s.whatsapp.net"))
        msg = E.Message(audioMessage=E.AudioMessage(PTT=True)) if audio else E.Message(conversation=text)
        return N.Message(Info=N.MessageInfo(MessageSource=src, ID=mid, Timestamp=int(time.time())), Message=msg)

    def test_separate_number_accepts_only_owner(self):
        t = self.transport(me="48700000000")
        self.assertEqual(t.parse(self.ev(OWNER))["text"], "pomoc")
        self.assertIsNone(t.parse(self.ev("48111111111")))                       # obcy
        self.assertIsNone(t.parse(self.ev(OWNER, group=True)))                   # grupa
        self.assertIsNone(t.parse(self.ev(OWNER, from_me=True)))                 # wysłane przez Sebastiana
        self.assertEqual(t.parse(self.ev("777", sender_server="lid", alt=OWNER))["kind"], "text")   # LID + numer
        self.assertEqual(t.lids["777"], OWNER)
        self.assertIsNotNone(t.parse(self.ev("777", sender_server="lid")))         # zapamiętany LID
        self.assertIsNotNone(t.parse(self.ev("999", sender_server="lid")))         # LID rozpoznany przez bibliotekę
        self.assertIsNone(t.parse(self.ev("888", sender_server="lid")))
        v = t.parse(self.ev(OWNER, audio=True))
        self.assertEqual((v["kind"], v["audio_bytes"]), ("voice", b"OGGDATA"))

    def test_family_number_accepted_with_sender(self):
        t = self.transport(me="48700000000")
        self.assertEqual(t.parse(self.ev(WIFE))["from"], WIFE)
        self.assertEqual(t.parse(self.ev(OWNER))["from"], OWNER)
        t.send_text("x", WIFE)
        self.assertEqual(t.client.sent[-1][0], WIFE)
        t.me = OWNER                                                   # Sebastian na numerze właściciela
        self.assertIsNone(t.parse(self.ev(WIFE, chat=WIFE)))
        self.assertFalse(t.family_ok)
        with self.assertRaises(RuntimeError):
            t.send_text("x", WIFE)

    def test_skipped_sender_is_logged_once(self):
        """2.5.1: obcy numer — bez odpowiedzi, ale w logu i w wa-status widać, kto pisał (bez treści)."""
        t = self.transport(me="48700000000")
        logs, seen = [], []
        t.log = SimpleNamespace(info=logs.append, warning=logs.append)
        t.on_skip = seen.append
        self.assertIsNone(t.parse(self.ev("48123456789", text="tajne")))
        self.assertIsNone(t.parse(self.ev("48123456789")))                      # drugi raz w ciągu godziny — cisza
        self.assertEqual(len(logs), 1)
        self.assertIn("+48123***789", logs[0])
        self.assertNotIn("tajne", logs[0])
        self.assertIsNone(t.parse(self.ev("4321", sender_server="lid")))
        self.assertIn("numer ukryty", logs[-1])
        self.assertEqual(seen[0]["number"], "48123456789")
        tmp = tempfile.mkdtemp()
        with patch.object(W.S, "DATA", tmp):
            for item in seen + seen:
                W.remember_skip(item)
            with contextlib.closing(W.db()) as con:
                lines = W.skipped_lines(con)
        self.assertEqual(len(lines), 2)
        self.assertIn("+48123***789", lines[0] + lines[1])

    def test_self_chat_mode(self):
        t = self.transport(me=OWNER)
        self.assertIsNone(t.parse(self.ev("48111111111", chat="48111111111")))    # ktoś pisze do właściciela
        self.assertIsNone(t.parse(self.ev(OWNER, chat="48111111111", from_me=True)))  # właściciel pisze do kogoś
        self.assertIsNotNone(t.parse(self.ev(OWNER, chat=OWNER, from_me=True)))     # czat „Ty”
        t.sent_ids.add("ECHO")
        self.assertIsNone(t.parse(self.ev(OWNER, chat=OWNER, from_me=True, mid="ECHO")))  # nasza odpowiedź

    def test_send_voice_marks_ptt_opus(self):
        t = self.transport(me="48700000000")
        f = pathlib.Path(tempfile.mkdtemp()) / "a.ogg"
        f.write_bytes(b"OggS")
        self.assertEqual(t.send_voice(f), "OUT1")
        to, msg = t.client.sent[0]
        self.assertEqual(to, OWNER)
        self.assertTrue(msg.audioMessage.PTT)
        self.assertEqual(msg.audioMessage.mimetype, "audio/ogg; codecs=opus")
        self.assertIn("OUT1", t.sent_ids)
        t.send_text("x")
        self.assertEqual(t.client.sent[1][0], OWNER)
        t.me = OWNER                                                               # czat „Ty”
        t.send_text("y")
        self.assertEqual(t.client.sent[2][0], OWNER)


if __name__ == "__main__":
    unittest.main()
