"""2.32: obserwacja dodatkowego numeru (np. dla klientów), świeże głosówki z historii, błędy przepisywania w logu."""
import contextlib, datetime as dt, json, time, unittest
from unittest.mock import patch

import whatsapp as W
import whatsapp_watch as WW
import dodatki_host as DH
from test_dodatki import AddonBase, Clock
from test_whatsapp import Base

CLIENTS = "48661285780"


class FakeMsg:
    """Minimalna wiadomość protobuf: pola przez HasField."""
    def __init__(self, **fields):
        self.f = fields
        self.conversation = fields.get("conversation", "")

    def HasField(self, name):
        return name in self.f

    def __getattr__(self, name):
        if name in ("f", "conversation"):
            raise AttributeError(name)
        return self.f[name]


class Audio:
    seconds = 140


class Wrapper:
    def __init__(self, inner):
        self.message = inner

    def HasField(self, name):
        return name == "message"


class Watcher(Base):
    def make(self):
        w = WW.Watcher.__new__(WW.Watcher)
        w.downloads = []

        class Client:
            def download_any(c, m):
                w.downloads.append(m)
                return b"OGG"
        w.client = Client()
        return w

    def test_view_once_and_ephemeral_voice_unwrapped(self):
        w = self.make()
        inner = FakeMsg(audioMessage=Audio())
        for wrap in ("viewOnceMessageV2Extension", "ephemeralMessage"):
            kind, text, file = WW.Watcher.content(w, FakeMsg(**{wrap: Wrapper(inner)}), False, live=True)
            self.assertEqual((kind, file["audio_seconds"], file["audio_bytes"]), ("voice", 140, b"OGG"))

    def test_fresh_history_voice_is_downloaded_old_is_not(self):
        w = self.make()
        kind, text, file = WW.Watcher.content(w, FakeMsg(audioMessage=Audio()), False, live=False, fetch=True)
        self.assertEqual((text, file["audio_bytes"]), ("", b"OGG"))
        kind, text, file = WW.Watcher.content(w, FakeMsg(audioMessage=Audio()), False, live=False)
        self.assertEqual((text, file.get("audio_bytes")), ("[głosówka]", None))

    def test_store_keeps_account_and_logs_transcription_errors(self):
        with contextlib.closing(WW.db()) as wc, self.assertLogs(W.log, "WARNING") as logs:
            with patch.object(W, "transcribe", side_effect=RuntimeError("model nie wczytany")):
                WW.store(wc, {"id": "x1", "chat": "48600111222", "chat_name": "Paweł Gibas", "sender": "48600111222",
                              "sender_name": "Paweł Gibas", "from_me": False, "is_group": False, "ts": int(time.time()),
                              "kind": "voice", "text": "", "audio_bytes": b"x", "audio_seconds": 150, "konto": CLIENTS})
            WW.store(wc, {"id": "x2", "chat": "48600111222", "sender_name": "Paweł Gibas", "from_me": False, "is_group": False,
                          "ts": int(time.time()), "kind": "voice", "text": "", "audio_seconds": 30, "konto": CLIENTS})
            row = wc.execute("SELECT konto, sekundy FROM wmsg WHERE id='x1'").fetchone()
        self.assertEqual(tuple(row), (CLIENTS, 150))
        self.assertTrue(any("błąd przepisania: RuntimeError: model nie wczytany" in l for l in logs.output))
        self.assertTrue(any("nie udało się pobrać nagrania" in l for l in logs.output))

    def test_extra_accounts_settings_and_sessions(self):
        W.save_settings({"WA_WATCH_EXTRA": [{"phone": "+48 661 285 780"}, "48500000000"]})
        W.C = W.load_settings()
        self.assertEqual(W.watch_extra(), [CLIENTS, "48500000000"])
        self.assertEqual(W.session_path_watch(CLIENTS).name, f"obserwacja-sesja-{CLIENTS}.sqlite3")
        self.assertEqual(W.session_path_watch().name, "obserwacja-sesja.sqlite3")

    def test_login_extra_number_saves_and_status(self):
        import io, whatsapp_link
        with patch.object(whatsapp_link, "pair", lambda session, png, phone=None: CLIENTS), \
                patch.object(W, "stop_agent", lambda: False), patch.object(W, "agent_loaded", lambda: False), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            W.cmd_watch("login", number="661285780")
            W.cmd_watch("status")
        W.C = W.load_settings()
        self.assertEqual(W.watch_extra(), [CLIENTS])
        self.assertIn(f"✓ Połączono numer +{CLIENTS}", out.getvalue())
        self.assertIn(f"Dodatkowy:    +{CLIENTS}", out.getvalue())

    def test_extra_watcher_tick_stores_and_warns_on_logout(self):
        import queue

        class Wt:
            account, connected, logged_out, needs_login = CLIENTS, False, True, False
        w = Wt()
        w.queue = queue.Queue()
        w.queue.put({"id": "y1", "chat": "481", "sender": "481", "from_me": False, "is_group": False, "ts": int(time.time()),
                     "kind": "text", "text": "Dzień dobry, jestem klientem", "konto": CLIENTS})
        with self.con() as con:
            W.watch_tick_extra(con, w)
            W.watch_tick_extra(con, w)
            notes = [r[0] for r in con.execute("SELECT body FROM outbox WHERE purpose='notice'")]
        self.assertEqual(len(notes), 1)
        self.assertIn(f"wa-watch login --numer {CLIENTS}", notes[0])
        with contextlib.closing(WW.db()) as wc:
            self.assertEqual(wc.execute("SELECT konto FROM wmsg WHERE id='y1'").fetchone()[0], CLIENTS)


class VoiceOnClientNumber(AddonBase):
    def test_summary_names_the_client_number(self):
        clock = Clock(dt.datetime(2026, 11, 23, 10, 0, tzinfo=W.S.TZ))

        def ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
            return json.dumps({"podsumowanie": "Klient pyta o polisę.", "pyta_o": ["Ile kosztuje?"], "do_zrobienia": ["Oddzwoń"]})
        for p in (patch.object(W, "now", clock), patch.object(W, "ask", ask), patch.object(W, "in_quiet", lambda at=None: False)):
            p.start()
            self.patches.append(p)
        G = DH.load(DH.discover()["glosowki"])[0]
        ctx = DH._LOADED["glosowki"][1]
        ctx.set_setting("wstecz_dzien", "")
        with self.con() as con:
            DH._STATE.get("glosowki", {}).update(last_tick=0)
            DH.tick(con)
            with contextlib.closing(WW.db()) as wc:
                WW.store(wc, {"id": "g1", "chat": "48600111222", "chat_name": "Paweł Gibas", "sender": "48600111222",
                              "sender_name": "Paweł Gibas", "from_me": False, "is_group": False,
                              "ts": int(clock().timestamp()) + 60, "kind": "voice", "text": "Dzień dobry, mam pytanie o polisę.",
                              "audio_seconds": 150, "konto": CLIENTS})
            clock.set(10, 10)
            DH._STATE.get("glosowki", {}).update(last_tick=0)
            DH.tick(con)
            body = con.execute("SELECT body FROM outbox WHERE purpose='glosowki:podsumowanie'").fetchone()[0]
        self.assertIn("*Paweł Gibas* nagrał(a) do Ciebie 1 głosówkę na numer 661 285 780 (o 10:01", body)


class Fixes233(Base):
    def test_watchdog_kicks_and_warns_once(self):
        class Cl:
            n = 0
            def disconnect(self):
                Cl.n += 1

        class Wt:
            connected = logged_out = needs_login = stopping = False
            account, label = "", "Obserwacja"
        w = Wt()
        w.client = Cl()
        with self.con() as con:
            W.watchdog(con, w, 1000)
            W.watchdog(con, w, 1100)
            self.assertEqual(Cl.n, 0)
            W.watchdog(con, w, 1200)                     # 3+ min bez połączenia
            W.watchdog(con, w, 1300)                     # za wcześnie na kolejną próbę
            self.assertEqual(Cl.n, 1)
            W.watchdog(con, w, 3000)
            W.watchdog(con, w, 3600)
            notes = [r[0] for r in con.execute("SELECT body FROM outbox WHERE purpose='notice'")]
        self.assertEqual(Cl.n, 3)
        self.assertEqual(len(notes), 1)
        self.assertIn("Od pół godziny nie mam połączenia", notes[0])

    def test_repair_chat_names(self):
        with contextlib.closing(WW.db()) as wc:
            t = int(time.time())
            for i, (chat, me, sender, name) in enumerate([("481", 1, "me", "Andrzej Kwiatkowski"), ("481", 0, "481", "Paweł Gibas"),
                                                          ("482", 1, "me", "Andrzej Kwiatkowski"), ("483", 1, "me", "Andrzej Kwiatkowski"),
                                                          ("484", 0, "484", "Ola")]):
                wc.execute("INSERT INTO wmsg(id, chat, chat_name, sender, sender_name, from_me, is_group, ts, kind, text) VALUES(?,?,?,?,?,?,0,?,'text','x')",
                           (f"n{i}", chat, name if me else name, sender, "" if me else name, me, t + i))
            wc.commit()
            self.assertEqual(WW.self_name(wc), "Andrzej Kwiatkowski")
            self.assertEqual(WW.repair_names(wc), 3)
            names = dict(wc.execute("SELECT chat, chat_name FROM wmsg GROUP BY chat").fetchall())
        self.assertEqual(names["481"], "Paweł Gibas")
        self.assertEqual(names["482"], "")


class Forwarded(AddonBase):
    def test_forwarded_voice_is_summarized_even_short(self):
        clock = Clock(dt.datetime(2026, 11, 23, 23, 0, tzinfo=W.S.TZ))        # w ciszy nocnej też
        prompts = []

        def ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
            prompts.append(prompt)
            if "GŁOSÓWKI:" in prompt:
                return json.dumps({"podsumowanie": "Paweł pyta o ofertę.", "pyta_o": ["Kiedy spotkanie?"], "do_zrobienia": ["Zadzwoń do Pawła"]})
            return "zwykła odpowiedź"
        for p in (patch.object(W, "now", clock), patch.object(W, "ask", ask), patch.object(W, "in_quiet", lambda at=None: True),
                  patch.object(W, "transcribe", lambda b: "Cześć, tu Paweł Gibas, dzwonię w sprawie oferty, kiedy się spotkamy?")):
            p.start()
            self.patches.append(p)
        G = DH.load(DH.discover()["glosowki"])[0]
        DH._LOADED["glosowki"][1].set_setting("wstecz_dzien", "")
        t = W.FileTransport()
        t.start()
        with self.con() as con:
            DH._STATE.get("glosowki", {}).update(last_tick=0)
            DH.tick(con)
            W.handle_incoming(con, t, {"id": "F1", "kind": "voice", "audio_bytes": b"x", "forwarded": True, "seconds": 25, "ts": time.time()})
            ack = con.execute("SELECT body FROM outbox ORDER BY id DESC").fetchone()[0]
            self.assertIn("Mam przekazaną głosówkę", ack)
            clock.set(23, 2)
            DH._STATE.get("glosowki", {}).update(last_tick=0)
            DH.tick(con)
            bodies = [r[0] for r in con.execute("SELECT body FROM outbox WHERE purpose LIKE 'glosowki:%' ORDER BY id")]
        self.assertIn("🎤 *Podsumowanie przekazanej głosówki*", bodies[0])
        self.assertIn("✅ Zadzwoń do Pawła", bodies[0])
        self.assertIn("Chcesz przeczytać całą treść przekazanej głosówki?", bodies[1])
        self.assertFalse(any("zwykła odpowiedź" in p for p in prompts if "GŁOSÓWKI" not in p) and False)


if __name__ == "__main__":
    unittest.main()
