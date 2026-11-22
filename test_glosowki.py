"""Testy dodatku Głosówki (2.29): podsumowania długich głosówek od innych osób."""
import contextlib, datetime as dt, json, time, unittest
from unittest.mock import patch

import sebastian as s
import whatsapp as W
import whatsapp_watch as WW
import dodatki_host as DH
from test_dodatki import AddonBase, Clock

TZ = s.TZ
TODAY = dt.date(2026, 11, 23)
SUMMARY = {"podsumowanie": "Jan pyta o termin podpisania umowy na działkę i prosi o przesłanie projektu.",
           "pyta_o": ["Kiedy możemy podpisać umowę?", "Czy projekt jest gotowy?"],
           "do_zrobienia": ["Wyślij Janowi projekt umowy do środy", "Oddzwoń i ustal termin podpisania"], "pilne": True}


class VoiceNotes(AddonBase):
    def setUp(self):
        super().setUp()
        self.clock = Clock(dt.datetime.combine(TODAY, dt.time(10, 0), TZ))
        self.model_ok = True
        self.prompts = []

        def ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
            self.prompts.append(prompt)
            if "GŁOSÓWKI:" in prompt:
                return json.dumps(SUMMARY) if self.model_ok else None
            return "Zwykła odpowiedź Sebastiana."
        for p in (patch.object(W, "now", self.clock), patch.object(W, "ask", ask),
                  patch.object(W, "in_quiet", lambda at=None: (at or self.clock()).time() >= dt.time(22) or (at or self.clock()).time() < dt.time(7))):
            p.start()
            self.patches.append(p)
        self.G = DH.load(DH.discover()["glosowki"])[0]
        self.ctx = DH._LOADED["glosowki"][1]
        self.t = W.FileTransport()
        self.t.start()
        self.n = 0

    # ---------------------------------------------------------------- pomocnicze
    def at(self, hh, mm, day=TODAY):
        return dt.datetime.combine(day, dt.time(hh, mm), TZ).timestamp()

    def voice(self, ts, seconds, text, who="Jan Nowak", chat="48600111222"):
        self.n += 1
        with contextlib.closing(WW.db()) as wc:
            with patch.object(W, "transcribe", lambda b: text):
                WW.store(wc, {"id": f"v{self.n}", "chat": chat, "chat_name": who, "sender": chat, "sender_name": who,
                              "from_me": False, "is_group": False, "ts": int(ts), "kind": "voice", "text": "",
                              "audio_bytes": b"x", "audio_seconds": seconds})

    def old_voice(self, ts, text, who="Ola Kowal", chat="48600333444"):
        """Głosówka zapisana przed 2.29 — bez długości."""
        self.n += 1
        with contextlib.closing(WW.db()) as wc:
            wc.execute("INSERT INTO wmsg(id, chat, chat_name, sender, sender_name, from_me, is_group, ts, kind, text) "
                       "VALUES(?,?,?,?,?,0,0,?,'voice',?)", (f"o{self.n}", chat, who, chat, who, int(ts), text))
            wc.commit()

    def tick(self, con):
        DH._STATE.get("glosowki", {}).update(last_tick=0)
        DH.tick(con)

    def write(self, con, text):
        W.handle_incoming(con, self.t, {"id": f"T{time.time_ns()}", "kind": "text", "text": text, "ts": time.time()})

    def sent(self, con, purpose=None):
        q = "SELECT body FROM outbox WHERE kind='text'" + (" AND purpose=?" if purpose else "") + " ORDER BY id"
        return [r[0] for r in con.execute(q, (purpose,) if purpose else ())]

    def packs(self):
        with contextlib.closing(self.G.db(self.ctx)) as c:
            return [dict(r) for r in c.execute("SELECT * FROM paczki ORDER BY id")]

    def start_fresh(self, con):
        """Pierwszy tik (ustawia początek) — bez działania wstecz."""
        self.ctx.set_setting("wstecz_dzien", "")
        self.tick(con)

    # ---------------------------------------------------------------- przebieg
    def test_long_burst_summary_question_and_full_text(self):
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 50, "Cześć Andrzej, dzwonię w sprawie działki.")
            self.voice(self.at(10, 2), 45, "Chciałbym wiedzieć, kiedy podpisujemy umowę.")
            self.voice(self.at(10, 3), 40, "I czy możesz mi przesłać projekt. Dzięki!")
            self.clock.set(10, 5)
            self.tick(con)
            self.assertEqual(self.sent(con), [])                       # może jeszcze nagrywać
            self.clock.set(10, 9)
            self.tick(con)
            summary, question = self.sent(con)
            self.assertIn("Cześć Andrzej! 🎤 *Jan Nowak* nagrał(a) do Ciebie 3 głosówki (o 10:01, razem 2:15 min) — *pilne*", summary)
            self.assertIn("*Pyta o:*\n• Kiedy możemy podpisać umowę?", summary)
            self.assertIn("*Do zrobienia:*\n✅ Wyślij Janowi projekt umowy do środy", summary)
            self.assertIn("Chcesz przeczytać całą treść głosówek od Jan Nowak? Odpisz *tak*", question)
            self.write(con, "Tak")
            full = self.sent(con, "glosowki:tresc")
            self.assertEqual(len(full), 1)
            self.assertIn("📝 *Cała treść — Jan Nowak* (3 głosówki", full[0])
            self.assertIn("🎤 2/3 · 10:02 · 0:45\nChciałbym wiedzieć, kiedy podpisujemy umowę.", full[0])
            self.assertEqual(self.packs()[0]["status"], "przeczytana")
            self.assertFalse(any("Zwykła odpowiedź" in b for b in self.sent(con)))
            self.tick(con)
            self.assertEqual(len(self.packs()), 1)                     # te same głosówki nie wracają

    def test_short_burst_and_separate_moments_are_ignored(self):
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 50, "krótko")
            self.voice(self.at(10, 2), 40, "jeszcze krótko")
            self.voice(self.at(10, 20), 70, "później, osobno")             # 18 minut przerwy — osobna paczka
            self.clock.set(10, 40)
            self.tick(con)
            self.assertEqual(self.packs(), [])
            self.assertEqual(self.sent(con), [])

    def test_two_people_are_separate_and_yes_asks_which(self):
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 130, "Sprawa A", who="Jan Nowak", chat="481")
            self.voice(self.at(10, 2), 125, "Sprawa B", who="Ola Kowal", chat="482")
            self.clock.set(10, 10)
            self.tick(con)
            self.assertEqual([p["osoba"] for p in self.packs()], ["Jan Nowak", "Ola Kowal"])
            self.write(con, "tak")
            self.assertIn("Od kogo? *treść 2* — Ola Kowal · *treść 1* — Jan Nowak", self.sent(con)[-1])
            self.write(con, "treść 1")
            self.assertIn("Cała treść — Jan Nowak", self.sent(con)[-1])

    def test_no_then_later_by_number(self):
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 150, "Długa sprawa")
            self.clock.set(10, 10)
            self.tick(con)
            self.write(con, "nie trzeba")
            self.assertIn("Jasne, nie wysyłam 👍 Gdybyś chciał później: *treść 1*", self.sent(con)[-1])
            self.assertEqual(self.packs()[0]["status"], "pominieta")
            self.write(con, "tak")                                      # już nic nie czeka — zwykła odpowiedź
            self.assertNotIn("Cała treść", self.sent(con)[-1])
            self.write(con, "głosówki")
            self.assertIn("1. 23.11 10:01 · *Jan Nowak* · 2:30 min — Jan pyta o termin", self.sent(con)[-1])
            self.write(con, "tresc 1")
            self.assertIn("Cała treść — Jan Nowak", self.sent(con)[-1])

    def test_yes_not_caught_when_our_question_is_old_and_not_last(self):
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 150, "Długa sprawa")
            self.clock.set(10, 10)
            self.tick(con)
            W.enqueue(con, "text", "Przegląd dnia", purpose="brief")      # Sebastian napisał coś innego
            self.clock.set(13, 0)
            self.write(con, "tak")
            self.assertEqual(self.packs()[0]["status"], "wyslana")
            self.clock.set(10, 30)
            self.write(con, "tak")                                      # w ciągu 2 godzin — łapie
            self.assertEqual(self.packs()[0]["status"], "przeczytana")

    def test_quiet_hours_wait_until_morning(self):
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(23, 0), 200, "Późna sprawa")
            self.clock.set(23, 30)
            self.tick(con)
            self.assertEqual(self.sent(con), [])
            self.assertEqual(self.packs()[0]["status"], "czeka")
            self.clock.set(7, 5, TODAY + dt.timedelta(days=1))
            self.tick(con)
            self.assertIn("(23.11 o 23:00, razem 3:20 min)", self.sent(con)[0])

    def test_model_down_then_fallback(self):
        self.model_ok = False
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 150, "Długa sprawa")
            self.clock.set(10, 10)
            for _ in range(3):
                self.tick(con)
            self.assertEqual(self.sent(con), [])
            self.tick(con)
            self.assertIn("Nie udało się zrobić podsumowania", self.sent(con)[0])
            self.write(con, "pokaż")
            self.assertIn("Długa sprawa", self.sent(con)[-1])

    def test_retro_only_witek_from_chosen_day_then_only_new(self):
        words = " ".join(["słowo"] * 300)                                # ok. 136 s mowy
        self.clock.t = dt.datetime.combine(dt.date(2026, 11, 22), dt.time(16, 30), TZ)
        self.old_voice(self.at(9, 0, dt.date(2026, 11, 21)), words, who="Witek Michno", chat="483")         # wczoraj
        self.old_voice(self.at(11, 0, dt.date(2026, 11, 22)), "Andrzej, mam pytanie o klienta Skorupskiego.", who="Witek Michno", chat="483")
        self.old_voice(self.at(15, 40, dt.date(2026, 11, 22)), "I jeszcze jedno — kiedy jedziemy na spotkanie?", who="Witek Michno", chat="483")
        self.old_voice(self.at(12, 0, dt.date(2026, 11, 22)), words, who="Ola Kowal", chat="484")           # ktoś inny — nie wstecz
        with self.con() as con:
            self.tick(con)
            p = self.packs()
            self.assertEqual([(x["osoba"], x["ile"], x["wstecz"]) for x in p], [("Witek Michno", 2, 1)])   # krótkie, z przerwą — i tak razem
            msg = self.sent(con)[0]
            self.assertIn("*Witek Michno* nagrał(a) do Ciebie 2 głosówki (22.11 o 11:00, razem ok. ", msg)
            self.assertIn("Skorupskiego", self.prompts[-1])
            self.assertIn("kiedy jedziemy", self.prompts[-1])
            self.voice(self.at(16, 31, dt.date(2026, 11, 22)), 140, "Nowa po instalacji", who="Nowy", chat="485")
            self.clock.set(16, 40)
            self.tick(con)
            self.assertEqual([x["osoba"] for x in self.packs()], ["Witek Michno", "Nowy"])
            self.assertEqual([x["wstecz"] for x in self.packs()], [1, 0])

    def test_retro_nothing_found_tells_owner(self):
        self.clock.t = dt.datetime.combine(dt.date(2026, 11, 22), dt.time(16, 30), TZ)
        with self.con() as con:
            self.tick(con)
            self.assertIn("Szukałem głosówek od Witold Michno z 22.11", self.sent(con)[0])
            self.tick(con)
            self.assertEqual(len(self.sent(con)), 1)                    # tylko raz

    def test_manual_retro_command(self):
        self.ctx.set_setting("wstecz_dzien", "")
        self.old_voice(self.at(11, 0), "Pytanie o umowę", who="Witold Michno", chat="483")
        with self.con() as con:
            self.assertEqual(self.G.COMMANDS["wstecz"](self.ctx, ["Witold", TODAY.isoformat()]), 0)
            self.assertIn("*Witold Michno* nagrał(a)", self.sent(con)[0])

    def test_very_long_text_is_split_into_parts(self):
        long = ("To jest dość długie zdanie z głosówki o sprawach klienta. " * 160).strip()
        with self.con() as con:
            self.start_fresh(con)
            self.voice(self.at(10, 1), 600, long)
            with contextlib.closing(WW.db()) as wc:
                self.assertEqual(len(wc.execute("SELECT text FROM wmsg WHERE id='v1'").fetchone()[0]), len(long))   # nie ucięte do 4000
                self.assertEqual(wc.execute("SELECT sekundy FROM wmsg WHERE id='v1'").fetchone()[0], 600)
            self.clock.set(10, 20)
            self.tick(con)
            self.write(con, "tak")
            parts = self.sent(con, "glosowki:tresc")
            self.assertGreater(len(parts), 2)
            self.assertTrue(all(len(p) <= 3500 for p in parts))
            self.assertIn(f"(część 1/{len(parts)})", parts[0])

    def test_groups_and_own_voices_ignored(self):
        with self.con() as con:
            self.start_fresh(con)
            with contextlib.closing(WW.db()) as wc:
                WW.store(wc, {"id": "g1", "chat": "grp", "chat_name": "Grupa", "sender": "481", "sender_name": "Jan",
                              "from_me": False, "is_group": True, "ts": int(self.at(10, 1)), "kind": "voice", "text": "x" * 900,
                              "audio_seconds": 300})
                WW.store(wc, {"id": "m1", "chat": "481", "chat_name": "Jan", "sender": "me", "sender_name": "",
                              "from_me": True, "is_group": False, "ts": int(self.at(10, 1)), "kind": "voice", "text": "",
                              "audio_seconds": 300})
            self.clock.set(10, 20)
            self.tick(con)
            self.assertEqual(self.packs(), [])

    def test_watcher_reads_voice_length(self):
        try:
            from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message
        except ImportError:
            self.skipTest("neonize niezainstalowany")
        m = Message()
        m.audioMessage.seconds = 95
        w = WW.Watcher.__new__(WW.Watcher)
        kind, text, file = WW.Watcher.content(w, m, True, live=False)
        self.assertEqual((kind, file["audio_seconds"]), ("voice", 95))


if __name__ == "__main__":
    unittest.main()
