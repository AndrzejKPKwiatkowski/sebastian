"""Testy modułu WhatsApp (Sebastian 2.3). Bez WhatsAppa, bez Ollamy — model i połączenie są udawane."""
import contextlib, datetime as dt, json, os, pathlib, queue, shutil, tempfile, time, unittest
from unittest.mock import patch

import sebastian as s
import whatsapp as W

BASE = "http://127.0.0.1:8765"
OWNER = "48600111222"


def fake_ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
    if "Przygotuj" in prompt:
        assert "Dziś:" in prompt
        return json.dumps({"tekst": "Dzień dobry, Andrzej! Wtorek.\n• *Umowa* — termin jutro\n• 2 zadania otwarte",
                           "glos": "Hej Andrzej! Dziś wtorek. Najważniejsza jest umowa z klientem, termin mija jutro, więc "
                                   "proponuję zacząć od niej zaraz po kawie. Poza tym masz dwa otwarte zadania. Miłego dnia!"})
    if "Pytanie:" in prompt:
        return "Według poczty: dokumenty do spotkania czekają na potwierdzenie."
    raise AssertionError(prompt[:80])


class WhatsAppTests(unittest.TestCase):
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
        pass

    def get_pn_from_lid(self, jid):
        return N.JID(User=OWNER if jid.User == "999" else "1", Server="s.whatsapp.net")

    def send_message(self, jid, msg):
        self.sent.append((jid.User, msg))
        return type("R", (), {"ID": f"OUT{len(self.sent)}"})()

    def build_audio_message(self, data, ptt=False):
        return E.Message(audioMessage=E.AudioMessage(PTT=ptt, mimetype="audio/ogg"))


@unittest.skipUnless(HAVE_NEONIZE, "brak biblioteki neonize")
class LinkFilterTests(unittest.TestCase):
    def transport(self, me):
        t = whatsapp_link.LinkedTransport.__new__(whatsapp_link.LinkedTransport)
        t.client, t.owner, t.me, t.me_lid, t.owner_lid, t.sent_ids = FakeClient(), OWNER, me, "555", None, set()
        t.log = None
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
        self.assertEqual(t.owner_lid, "777")
        self.assertIsNotNone(t.parse(self.ev("777", sender_server="lid")))         # zapamiętany LID
        self.assertIsNotNone(t.parse(self.ev("999", sender_server="lid")))         # LID rozpoznany przez bibliotekę
        self.assertIsNone(t.parse(self.ev("888", sender_server="lid")))
        v = t.parse(self.ev(OWNER, audio=True))
        self.assertEqual((v["kind"], v["audio_bytes"]), ("voice", b"OGGDATA"))

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
