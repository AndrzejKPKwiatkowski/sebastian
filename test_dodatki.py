"""Testy 2.7: gniazdo na dodatki + Przypominacz. Bez WhatsAppa, bez Ollamy, bez Twilio — wszystko udawane."""
import contextlib, datetime as dt, io, json, time, unittest
from unittest.mock import patch

import sebastian as s
import whatsapp as W
import dodatki_host as DH
from test_whatsapp import Base, OWNER

TZ = s.TZ
DAY = dt.date(2026, 11, 9)            # poniedziałek


class Clock:
    def __init__(self, when):
        self.t = when

    def __call__(self):
        return self.t

    def set(self, hh, mm, day=None):
        self.t = dt.datetime.combine(day or self.t.date(), dt.time(hh, mm), TZ)

    def add(self, minutes):
        self.t += dt.timedelta(minutes=minutes)


def ics(*events):
    body = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//t//PL\r\n"
    for i, (a, b, title) in enumerate(events):
        body += (f"BEGIN:VEVENT\r\nUID:e{i}@t\r\nDTSTAMP:20260101T000000Z\r\nDTSTART;TZID=Europe/Warsaw:{DAY:%Y%m%d}T{a.replace(':', '')}00\r\n"
                 f"DTEND;TZID=Europe/Warsaw:{DAY:%Y%m%d}T{b.replace(':', '')}00\r\nSUMMARY:{title}\r\nEND:VEVENT\r\n")
    return body + "END:VCALENDAR\r\n"


class Model:
    """Udawany model: odpowiada wg rodzaju polecenia; zapisuje, o co go pytano."""

    def __init__(self):
        self.detect = None          # dict albo None (= model nie odpowiada)
        self.context = {"kontekst": "Kowalski 3.11 przysłał projekt umowy (mail od Kowalskiego 03.11)"}
        self.answer = None
        self.calls = []

    def __call__(self, prompt, as_json=False, max_tokens=1200, temperature=0.4):
        self.calls.append(prompt[:60])
        if "PRZYPOMNIENIE" in prompt:
            return json.dumps(self.detect) if self.detect is not None else None
        if "ISTOTNE dla tej sprawy" in prompt:
            return json.dumps(self.context)
        if "Andrzej odpisał" in prompt:
            return json.dumps(self.answer) if self.answer is not None else json.dumps({"odpowiedz": False, "akcje": []})
        if "Pytanie:" in prompt:
            return "Zwykła odpowiedź Sebastiana."
        if "Przygotuj" in prompt:
            return json.dumps({"tekst": "Przegląd", "glos": "Hej " * 20})
        raise AssertionError(prompt[:80])


class AddonBase(Base):
    def setUp(self):
        super().setUp()
        DH._LOADED.clear()
        DH._STATE.clear()
        DH.bind(W)

    def tearDown(self):
        DH._LOADED.clear()
        DH._STATE.clear()
        super().tearDown()


class HostTests(AddonBase):
    def test_builtin_discovered_and_enabled(self):
        found = DH.discover()
        self.assertIn("przypominacz", found)
        self.assertEqual(found["przypominacz"]["problems"], [])
        self.assertTrue(DH.is_enabled(found["przypominacz"]))
        self.assertIn("przypomnij mi", DH.help_text())
        with self.con() as con:
            self.assertIn("Dodatki:", W.handle(con, "pomoc")[0])

    def test_switch_off_and_broken_user_addon(self):
        broken = DH.data_root() / "zepsuty"
        broken.mkdir(parents=True)
        (broken / "dodatek.json").write_text('{"id": "zepsuty", "nazwa": "x", "wersja": "1", "opis": "x", "uprawnienia": ["root"]}')
        (broken / "__init__.py").write_text("raise RuntimeError('nie')")
        found = DH.discover()
        self.assertTrue(found["zepsuty"]["problems"])
        self.assertFalse(DH.is_enabled(found["zepsuty"]))
        with self.assertRaises(DH.AddonError):
            DH.set_enabled("zepsuty", True)
        DH.set_enabled("przypominacz", False)
        self.assertNotIn("przypominacz", [ctx.id for _, ctx in DH.active()])
        with self.con() as con:
            self.assertFalse(DH.on_message(con, "text", "przypomnij mi o fakturze"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            DH.cmd_list()
        self.assertIn("przypominacz", out.getvalue())
        self.assertIn("wyłączony", out.getvalue())

    def test_user_addon_permissions_and_errors_pause(self):
        own = DH.data_root() / "moj"
        own.mkdir(parents=True)
        (own / "dodatek.json").write_text(json.dumps({"id": "moj", "nazwa": "Mój", "wersja": "0.1", "opis": "próba",
                                                      "uprawnienia": [], "tik_co_sekund": 0}))
        (own / "__init__.py").write_text(
            "def on_message(ctx, msg):\n    return 'echo: ' + msg['text'] if msg['text'].startswith('echo') else None\n"
            "def tick(ctx):\n    ctx.send_text('nie wolno')\n")
        self.assertFalse(DH.is_enabled(DH.discover()["moj"]))          # Twój dodatek: domyślnie wyłączony
        DH.set_enabled("moj", True)
        DH.set_enabled("przypominacz", False)
        with self.con() as con:
            self.assertTrue(DH.on_message(con, "text", "echo 1"))
            self.assertEqual(con.execute("SELECT body FROM outbox ORDER BY id DESC").fetchone()[0], "echo: echo 1")
            for _ in range(3):
                DH.tick(con)                                             # brak uprawnienia → błąd → po 3 pauza
            self.assertTrue(DH._paused("moj"))
            self.assertFalse(con.execute("SELECT 1 FROM outbox WHERE body='nie wolno'").fetchone())

    def test_calendar_end_times_from_ics(self):
        with contextlib.closing(s.db()) as c:
            c.execute("INSERT INTO calendar_sources(name,content,imported) VALUES(?,?,?)",
                      ("Praca", ics(("10:00", "11:00", "Rano"), ("16:00", "17:30", "Klient Nowak")), s.now()))
            c.commit()
        mod, ctx = DH.load(DH.discover()["przypominacz"])
        ev = ctx.calendar(DAY)
        self.assertEqual([(e["start"].strftime("%H:%M"), e["end"].strftime("%H:%M"), e["title"]) for e in ev],
                         [("10:00", "11:00", "Rano"), ("16:00", "17:30", "Klient Nowak")])


class ReminderTests(AddonBase):
    def setUp(self):
        super().setUp()
        self.clock = Clock(dt.datetime.combine(DAY, dt.time(11, 40), TZ))
        self.model = Model()
        self.ogg = W.home() / "nagrania" / "fake.ogg"
        self.ogg.parent.mkdir(parents=True, exist_ok=True)
        self.ogg.write_bytes(b"OggS")
        self.voices = []

        def synth(text, base):
            self.voices.append(text)
            return self.ogg, None
        for p in (patch.object(W, "now", self.clock), patch.object(W, "ask", self.model), patch.object(W, "synthesize", synth),
                  patch.object(W, "in_quiet", lambda at=None: (at or self.clock()).time() >= dt.time(22) or (at or self.clock()).time() < dt.time(7))):
            p.start()
            self.patches.append(p)
        with contextlib.closing(s.db()) as c:
            c.execute("INSERT INTO calendar_sources(name,content,imported) VALUES(?,?,?)",
                      ("Praca", ics(("10:00", "11:00", "Rano"), ("16:00", "17:30", "Klient Nowak")), s.now()))
            c.commit()
        self.P = DH.load(DH.discover()["przypominacz"])[0]
        self.ctx = DH._LOADED["przypominacz"][1]
        self.t = W.FileTransport()
        self.t.start()

    # ---------------------------------------------------------------- pomocnicze
    def voice(self, con, text, mid=None):
        with patch.object(W, "transcribe", lambda b: text):
            W.handle_incoming(con, self.t, {"id": mid or f"V{time.time_ns()}", "kind": "voice", "audio_bytes": b"x",
                                            "ts": time.time()})

    def write(self, con, text):
        W.handle_incoming(con, self.t, {"id": f"T{time.time_ns()}", "kind": "text", "text": text, "ts": time.time()})

    def last(self, con, n=1):
        return [r["body"] for r in con.execute("SELECT body FROM outbox WHERE kind='text' ORDER BY id DESC LIMIT ?", (n,))]

    def items(self):
        with contextlib.closing(self.P.db(self.ctx)) as c:
            return [dict(r) for r in c.execute("SELECT * FROM sprawy ORDER BY id")]

    def tick(self, con, times=1):
        for _ in range(times):
            DH._STATE.get("przypominacz", {}).update(last_tick=0)
            DH.tick(con)

    # ---------------------------------------------------------------- kiedy
    def test_evening_slot_rules(self):
        slot, last = self.P.evening_slot(self.ctx, DAY)
        self.assertEqual((f"{slot:%H:%M}", last["title"]), ("17:45", "Klient Nowak"))
        self.P._CAL_CACHE.clear()
        slot, last = self.P.evening_slot(self.ctx, DAY + dt.timedelta(days=1))           # bez spotkań
        self.assertEqual((f"{slot:%H:%M}", last), ("18:00", None))
        with patch.object(self.ctx, "calendar", lambda day: [{"start": dt.datetime.combine(day, dt.time(8), TZ),
                                                              "end": dt.datetime.combine(day, dt.time(9), TZ), "title": "x"}]):
            self.P._CAL_CACHE.clear()
            self.assertEqual(f"{self.P.evening_slot(self.ctx, DAY)[0]:%H:%M}", "17:00")      # najwcześniej
        with patch.object(self.ctx, "calendar", lambda day: [{"start": dt.datetime.combine(day, dt.time(20), TZ),
                                                              "end": dt.datetime.combine(day, dt.time(23), TZ), "title": "x"}]):
            self.P._CAL_CACHE.clear()
            self.assertEqual(f"{self.P.evening_slot(self.ctx, DAY)[0]:%H:%M}", "21:30")      # najpóźniej
        s_ = self.ctx.settings()
        self.P._CAL_CACHE.clear()
        self.assertEqual(self.P.plan_day(self.ctx, dt.datetime.combine(DAY, dt.time(18, 30), TZ), s_), DAY)
        self.assertEqual(self.P.plan_day(self.ctx, dt.datetime.combine(DAY, dt.time(21, 0), TZ), s_), DAY + dt.timedelta(days=1))

    def test_explicit_when(self):
        now = dt.datetime.combine(DAY, dt.time(11, 40), TZ)
        ew = self.P.explicit_when
        self.assertEqual(ew("przypomnij mi jutro o fakturze", now), (DAY + dt.timedelta(days=1), None))
        self.assertEqual(ew("przypomnij mi o 16 żeby zadzwonić", now), (None, "16:00"))
        self.assertEqual(ew("przypomnij o 9:30", now), (DAY + dt.timedelta(days=1), "09:30"))
        self.assertEqual(ew("za 2 godziny przypomnij", now), (DAY, "13:40"))
        self.assertEqual(ew("za pół godziny", now), (DAY, "12:10"))
        self.assertEqual(ew("w piątek przypomnij o 10", now), (DAY + dt.timedelta(days=4), "10:00"))
        self.assertEqual(ew("przypomnij mi o umowie", now), (None, None))

    # ---------------------------------------------------------------- rozpoznanie
    def test_trigger_without_model_and_clean_text(self):
        with self.con() as con:
            self.voice(con, "Sebastian, przypomnij mi, żeby oddzwonić do pani Kowalskiej w sprawie umowy.")
            msg = self.last(con)[0]
        self.assertIn("✓ Przyjąłem — przypomnę dziś o 17:45 (po spotkaniu „Klient Nowak”, do 17:30)", msg)
        self.assertIn("• Oddzwonić do pani Kowalskiej w sprawie umowy", msg)
        it = self.items()[0]
        self.assertEqual((it["status"], it["dzien"], it["zrodlo"]), ("czeka", DAY.isoformat(), "głosówka"))
        with self.con() as con:
            self.assertFalse(con.execute("SELECT 1 FROM outbox WHERE purpose='reply'").fetchone())   # bez zwykłej odpowiedzi

    def test_model_splits_and_classifies_voice(self):
        self.model.detect = {"przypomnienie": True, "sprawy": [{"tresc": "Zadzwonić do Kowalskiego", "slowa": ["Kowalski"]},
                                                              {"tresc": "Kupić tonery", "slowa": ["toner"]}]}
        with self.con() as con:
            self.voice(con, "aha i jeszcze Kowalski i tonery się kończą, wieczorem do tego wróćmy")
            self.assertIn("• Kupić tonery", self.last(con)[0])
        self.assertEqual([i["tresc"] for i in self.items()], ["Zadzwonić do Kowalskiego", "Kupić tonery"])
        self.model.detect = {"przypomnienie": False, "sprawy": []}
        with self.con() as con:
            self.voice(con, "co mam jutro w kalendarzu")
            self.assertTrue(con.execute("SELECT 1 FROM outbox WHERE purpose='reply'").fetchone())   # zwykła odpowiedź
        self.assertEqual(len(self.items()), 2)

    def test_text_needs_trigger_and_zapamietaj_untouched(self):
        with self.con() as con:
            self.write(con, "jaki mam plan na dziś")
            self.write(con, "zapamiętaj: klient Y woli maile")
        self.assertEqual(self.items(), [])
        self.assertNotIn("PRZYPO", " ".join(self.model.calls))

    # ---------------------------------------------------------------- cały wieczór
    def test_full_evening_with_escalation_and_rollover(self):
        import whatsapp_watch as WW
        with contextlib.closing(WW.db()) as wc:
            wc.execute("INSERT INTO wmsg(id, chat, chat_name, sender, sender_name, from_me, is_group, ts, kind, text) "
                       "VALUES('w1','c','Jan Kowalski','c','Jan Kowalski',0,0,?,'text','Przesyłam poprawiony projekt umowy')",
                       (int(time.time()) - 3600,))
            wc.commit()
        with self.con() as con:
            self.voice(con, "przypomnij mi zadzwonić do Kowalskiego w sprawie umowy")
            self.clock.set(12, 0)
            self.tick(con)                                             # kontekst w tle
            it = self.items()[0]
            self.assertEqual((it["kontekst_stan"], it["kontekst"][:8]), ("ok", "Kowalski"))
            self.clock.set(17, 40)
            self.tick(con)
            self.assertFalse(con.execute("SELECT 1 FROM outbox WHERE purpose='przypominacz:wieczor'").fetchone())
            self.clock.set(17, 45)
            self.tick(con)
            msg = con.execute("SELECT body FROM outbox WHERE purpose='przypominacz:wieczor'").fetchone()[0]
            self.assertIn("Hej Andrzej 👋 O tym miałeś pamiętać", msg)
            self.assertIn("*1.* Zadzwonić do Kowalskiego w sprawie umowy", msg)
            self.assertIn("↳ Kowalski 3.11", msg)
            self.assertIn("Hej Andrzeju! Tu Sebastian. Masz jedną sprawę, którą odłożyłeś na później. "
                          "Zadzwonić do Kowalskiego w sprawie umowy. Teraz spójrz na WhatsAppa", self.voices[-1])
            self.clock.add(59)
            self.tick(con)
            self.assertEqual(len(self.voices), 1)
            self.clock.add(2)
            self.tick(con)
            self.assertIn("Andrzej, przypominam. Czeka na Ciebie jedna sprawa", self.voices[-1])
            self.clock.add(14)
            self.tick(con)
            self.assertNotIn("Olewasz", " ".join(self.last(con, 3)))
            self.clock.add(2)
            self.tick(con, 3)
            self.assertEqual(sum("Olewasz mnie :'(" in b for b in self.last(con, 5)), 1)     # minka raz
            # następny dzień: wraca wieczorem z dopiskiem
            self.clock.set(9, 0, DAY + dt.timedelta(days=1))
            self.tick(con)
            it = self.items()[0]
            self.assertEqual((it["status"], it["powtorki"], it["dzien"]), ("czeka", 1, (DAY + dt.timedelta(days=1)).isoformat()))
            self.clock.set(18, 0)
            self.P._CAL_CACHE.clear()
            self.tick(con)
            self.assertIn("(czeka od wczoraj)", self.last(con)[0])

    def test_answers_rules_tasks_and_partial(self):
        self.model.detect = {"przypomnienie": True, "sprawy": [{"tresc": "Zadzwonić do Kowalskiego", "slowa": []},
                                                              {"tresc": "Faktura dla Nowaka", "slowa": []},
                                                              {"tresc": "Kupić tonery", "slowa": []}]}
        with self.con() as con:
            self.voice(con, "przypomnij mi o trzech rzeczach")
            self.clock.set(17, 50)
            self.tick(con, 4)
            self.write(con, "1 zrobione, 2 jutro")
            reply = self.last(con)[0]
            self.assertIn("✓ 1. Zadzwonić do Kowalskiego — zrobione", reply)
            self.assertIn("→ 2. Faktura dla Nowaka — przypomnę jutro wieczorem", reply)
            self.assertIn("Czekam jeszcze na: *3.* Kupić tonery", reply)
            self.clock.add(90)
            self.tick(con)
            self.assertEqual(len(self.voices), 1)                       # odpowiedział — bez drugiego telefonu
            self.write(con, "3 do zadań")
            self.assertIn("📋 3. Kupić tonery — na liście zadań", self.last(con)[0])
            self.assertIn("głowa wolna", self.last(con)[0])
        with contextlib.closing(s.db()) as c:
            self.assertTrue(c.execute("SELECT 1 FROM messages WHERE task_title='Kupić tonery' AND is_task=1").fetchone())
        st = {i["tresc"]: (i["status"], i["dzien"]) for i in self.items()}
        self.assertEqual(st["Faktura dla Nowaka"], ("czeka", (DAY + dt.timedelta(days=1)).isoformat()))
        self.assertEqual(st["Kupić tonery"][0], "zadanie")

    def test_ack_free_text_and_unrelated_question(self):
        self.model.detect = {"przypomnienie": True, "sprawy": [{"tresc": "Zadzwonić do Kowalskiego", "slowa": []},
                                                              {"tresc": "Kupić tonery", "slowa": []}]}
        with self.con() as con:
            self.voice(con, "przypomnij mi o dwóch rzeczach")
            self.clock.set(17, 50)
            self.tick(con, 4)
            self.write(con, "ile mam zadań na 2 dni")                   # nie odpowiedź → zwykła rozmowa
            self.assertEqual(self.last(con)[0], "Zwykła odpowiedź Sebastiana.")
            self.model.answer = {"odpowiedz": True, "akcje": [{"nr": 1, "co": "godzina", "godzina": "20:30"},
                                                               {"nr": 2, "co": "usun"}]}
            self.voice(con, "z Kowalskim pogadam po kolacji, a tonery już ktoś kupił")
            reply = self.last(con)[0]
            self.assertIn("→ 1. Zadzwonić do Kowalskiego — przypomnę dziś o 20:30", reply)
            self.assertIn("✗ 2. Kupić tonery — skreślone", reply)
            self.clock.set(20, 30)
            self.tick(con, 2)
            self.assertIn("Zadzwonić do Kowalskiego", self.last(con)[0])
            self.write(con, "ok")
            self.assertIn("sprawy poczekają", self.last(con)[0])
            self.clock.add(120)
            self.tick(con)
            self.assertEqual(len(self.voices), 2)                       # po „ok” bez kolejnego telefonu

    def test_parse_actions(self):
        now = dt.datetime.combine(DAY, dt.time(18), TZ)
        pa = lambda t: {k: (v[0], v[1] and v[1].isoformat(), v[2]) for k, v in self.P.parse_actions(t, [1, 2, 3], now).items()}
        tomorrow = (DAY + dt.timedelta(days=1)).isoformat()
        self.assertEqual(pa("1 zrobione, 2 jutro"), {1: ("zrobione", None, None), 2: ("termin", tomorrow, None)})
        self.assertEqual(pa("zrobione 1 i 3"), {1: ("zrobione", None, None), 3: ("zrobione", None, None)})
        self.assertEqual(pa("1 i 2 do zadań"), {1: ("zadanie", None, None), 2: ("zadanie", None, None)})
        self.assertEqual(pa("wszystko jutro"), {n: ("termin", tomorrow, None) for n in (1, 2, 3)})
        self.assertEqual(pa("2 o 21"), {2: ("termin", DAY.isoformat(), "21:00")})
        self.assertEqual(pa("3 za godzinę"), {3: ("termin", DAY.isoformat(), "19:00")})
        self.assertEqual(pa("1 usuń"), {1: ("usun", None, None)})
        self.assertEqual(pa("2 w piątek"), {2: ("termin", (DAY + dt.timedelta(days=4)).isoformat(), None)})
        self.assertEqual(pa("ile mam zadań na 2 dni w tym tygodniu"), {})
        self.assertEqual(pa("ok"), {})

    def test_list_now_and_quiet_hours(self):
        with self.con() as con:
            self.write(con, "przypomnienia")
            self.assertIn("Nic nie czeka", self.last(con)[0])
            self.write(con, "przypomnij mi: wysłać ofertę do Malarzy")
            self.write(con, "przypomnienia")
            self.assertIn("• Wysłać ofertę do Malarzy — dziś o 17:45", self.last(con)[0])
            self.clock.set(21, 20)
            self.write(con, "przypomnij teraz")
            self.tick(con, 3)
            self.assertIn("O tym miałeś pamiętać", self.last(con)[0])
            self.clock.set(21, 50)
            self.tick(con)
            self.clock.set(22, 25)
            self.tick(con, 2)
            self.assertEqual(len(self.voices), 1)                       # drugi telefon wypadłby w ciszy nocnej
            self.assertNotIn("Olewasz", " ".join(self.last(con, 3)))

    def test_twilio_call_answered_and_fallback(self):
        import importlib
        tw = importlib.import_module("sebastian_dodatek_przypominacz.telefon")
        self.ctx.set_setting("dzwonek", "telefon")
        self.ctx.set_setting("twilio_sid", "AC123")
        self.ctx.set_setting("twilio_numer", "+48100200300")
        posts, state = [], {"status": "no-answer", "duration": "0"}

        class R:
            def __init__(self, data, code=201):
                self.status_code, self._d, self.text = code, data, json.dumps(data)

            def json(self):
                return self._d

            def raise_for_status(self):
                pass
        with patch.object(self.ctx, "secret", lambda name: "tok"), \
                patch.object(tw.requests, "post", lambda url, **kw: posts.append(kw["data"]) or R({"sid": f"CA{len(posts)}"})), \
                patch.object(tw.requests, "get", lambda url, **kw: R(state, 200)), self.con() as con:
            self.write(con, "przypomnij mi: oddzwonić do banku")
            self.clock.set(17, 50)
            self.tick(con, 3)
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["To"], "+" + OWNER)
            self.assertIn('voice="Polly.Jacek"', posts[0]["Twiml"])
            self.assertIn("Oddzwonić do banku", posts[0]["Twiml"])
            self.assertEqual(self.voices, [])                           # zamiast głosówki — połączenie
            self.clock.add(61)
            self.tick(con)
            self.assertEqual(len(posts), 2)
            self.tick(con)                                              # nieodebrane → od razu minka
            self.assertIn("Olewasz mnie", self.last(con)[0])
        with patch.object(self.ctx, "secret", lambda name: None), self.con() as con:      # brak tokenu → głosówka
            self.write(con, "przypomnij mi o 19: kupić chleb")
            self.clock.set(19, 0)
            self.tick(con, 3)
            self.assertTrue(self.voices)
            self.assertIn("*1.* Oddzwonić do banku", self.last(con)[0])         # niezałatwione dołączają
            self.assertIn("*2.* Kupić chleb", self.last(con)[0])

    def test_cli_commands(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            DH.cmd_run("przypominacz", "dzis")
            DH.cmd_run("przypominacz", "sprawdz", ["przypomnij", "mi", "o", "fakturze", "dla", "Nowaka"])
            DH.cmd_run("przypominacz", "dodaj", ["oddzwonić do Kowalskiej"])
            DH.cmd_run("przypominacz", "lista")
            DH.cmd_run("przypominacz", "ustaw", ["bez_spotkan", "18:30"])
            DH.cmd_run("przypominacz", "historia")
        text = out.getvalue()
        self.assertIn("16:00–17:30  Klient Nowak", text)
        self.assertIn("Wieczorne przypomnienie: 17:45", text)
        self.assertIn("To prośba o przypomnienie", text)
        self.assertIn("Oddzwonić do Kowalskiej", text)
        self.assertIn("bez_spotkan = 18:30", text)
        self.assertEqual(self.ctx.settings()["bez_spotkan"], "18:30")


if __name__ == "__main__":
    unittest.main()
