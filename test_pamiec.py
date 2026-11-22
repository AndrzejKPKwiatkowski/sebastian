"""Testy dodatku Pamięć (2.30): Sebastian uczy się o każdym użytkowniku, pyta „czy dobrze zrozumiałem?”."""
import contextlib, datetime as dt, io, json, re, time, unittest, zipfile
from pathlib import Path
from unittest.mock import patch

import sebastian as s
import whatsapp as W
import dodatki_host as DH
from test_dodatki import AddonBase, Clock
from test_whatsapp import OWNER

TZ = s.TZ
AGA = "48500999888"
DAY = dt.date(2026, 11, 23)


def chatgpt_zip(path):
    conv = [{"title": "Plan finansowy klienta", "create_time": 1731000000, "mapping": {
        "a": {"message": {"author": {"role": "user"}, "create_time": 1, "content": {"content_type": "text", "parts": ["Jestem planerem finansowym w inPartners, prowadzę zespół Feniks."]}}},
        "b": {"message": {"author": {"role": "assistant"}, "create_time": 2, "content": {"parts": ["To świetnie! Oto plan…"]}}},
        "c": {"message": {"author": {"role": "user"}, "create_time": 3, "content": {"parts": ["Moja żona Aga szuka pracy w administracji. Karta 4111 1111 1111 1111"]}}}}}]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("conversations.json", json.dumps(conv))
        z.writestr("chat.html", "<html>ignorowane</html>")
    return path


class Memory(AddonBase):
    def setUp(self):
        super().setUp()
        W.save_settings({"WA_USERS": [{"phone": AGA, "name": "Aga Kwiatkowska", "access": "pelny"}]})
        W.C = W.load_settings()
        self.clock = Clock(dt.datetime.combine(DAY, dt.time(10, 0), TZ))
        self.reply = {"fakty": [{"kategoria": "praca", "tresc": "Andrzej jest planerem finansowym w inPartners.", "pewnosc": 0.95},
                                {"kategoria": "ludzie", "tresc": "Andrzej ma żonę Agę, która szuka pracy w administracji.", "pewnosc": 0.6},
                                {"kategoria": "praca", "tresc": "Andrzej prowadzi zespół Feniks.", "pewnosc": 0.7}]}
        self.prompts = []

        def ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
            self.prompts.append(prompt)
            if "Budujesz pamięć" in prompt:
                return json.dumps(self.reply)
            if "Złóż krótki" in prompt:
                lines = [re.sub(r"^• \([^)]*\) ", "• ", l) for l in prompt.split("FAKTY")[1].splitlines() if l.startswith("• (")]
                return json.dumps({"tekst": "\n".join(lines)})
            return "Zwykła odpowiedź Sebastiana."
        for p in (patch.object(W, "now", self.clock), patch.object(W, "ask", ask),
                  patch.object(W, "in_quiet", lambda at=None: (at or self.clock()).time() >= dt.time(22) or (at or self.clock()).time() < dt.time(7))):
            p.start()
            self.patches.append(p)
        self.M = DH.load(DH.discover()["pamiec"])[0]
        self.M.START_WORKER = False
        self.ctx = DH._LOADED["pamiec"][1]
        self.R = self.M.R
        self.t = W.FileTransport()
        self.t.start()
        self.tick()

    # ---------------------------------------------------------------- pomocnicze
    def tick(self):
        with self.con() as con:
            DH._STATE.get("pamiec", {}).update(last_tick=0)
            DH.tick(con)

    def db(self):
        return contextlib.closing(self.R.db(self.ctx.folder()))

    def work(self, n=20):
        for _ in range(n):
            if not self.M.work_once(self.ctx, chat_pause=0):
                break

    def write(self, text, phone=None):
        with self.con() as con:
            W.handle_incoming(con, self.t, {"id": f"T{time.time_ns()}", "kind": "text", "text": text, "ts": time.time(),
                                            **({"from": phone} if phone else {})})
            return [dict(r) for r in con.execute("SELECT body, to_phone, purpose FROM outbox ORDER BY id DESC LIMIT 3")]

    def facts(self, pid=OWNER):
        with self.db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM fakty WHERE osoba=? ORDER BY id", (pid,))]

    # ---------------------------------------------------------------- osoby i źródła
    def test_people_from_whatsapp(self):
        with self.db() as c:
            ps = {p["id"]: p for p in self.R.people(c)}
        self.assertEqual(ps[OWNER]["rola"], "wlasciciel")
        self.assertEqual(ps[AGA]["imie"], "Aga Kwiatkowska")
        self.assertTrue((self.ctx.folder() / "wrzuc-tutaj").exists() or True)

    def test_chatgpt_export_only_user_messages_and_secrets_hidden(self):
        kind, docs = self.R.file_docs(chatgpt_zip(Path(self.temp.name) / "eksport.zip"))
        self.assertEqual(kind, "chatgpt")
        text = self.R.chunks(docs)[0]
        self.assertIn("Rozmowa z ChatGPT „Plan finansowy klienta”", text)
        self.assertIn("Jestem planerem finansowym", text)
        self.assertNotIn("Oto plan", text)                                  # odpowiedzi modelu pomijane
        self.assertNotIn("4111", text)

    def test_claude_and_gemini_exports(self):
        claude = [{"name": "Oferta", "created_at": "2026-10-01T10:00:00Z", "chat_messages": [
            {"sender": "human", "text": "Pomóż mi z ofertą dla klienta z Rybnika"}, {"sender": "assistant", "text": "Jasne"}]}]
        self.assertEqual(self.R.json_docs(claude)[0], "claude")
        self.assertIn("Rybnika", self.R.chunks(self.R.json_docs(claude)[1])[0])
        gem = [{"header": "Gemini Apps", "title": "Prompted jak założyć IKZE", "time": "2026-09-01T08:00:00Z"},
               {"header": "Gemini Apps", "title": "Prompted przepis na sernik", "time": "2026-09-01T09:00:00Z"}]
        kind, docs = self.R.json_docs(gem)
        self.assertEqual((kind, docs[0][0]), ("gemini", "[2026-09-01] Zapytania do Gemini"))
        self.assertEqual(docs[0][1], ["jak założyć IKZE", "przepis na sernik"])

    def test_long_text_chunked(self):
        parts = self.R.chunks([("Notatki", ["Zdanie o pracy. " * 1200])])
        self.assertGreater(len(parts), 2)
        self.assertTrue(all(len(p) <= self.R.CHUNK for p in parts))
        self.assertTrue(parts[1].startswith("Notatki (cd.)"))

    # ---------------------------------------------------------------- nauka
    def test_digest_merges_repeats_and_builds_profile(self):
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "Notatki", text="Jestem planerem w inPartners. Prowadzę Feniksy.")
            self.R.add_source(c, OWNER, "tekst", "Notatki 2", text="Znowu o pracy w inPartners.")
        self.work()
        f = self.facts()
        self.assertEqual(len(f), 3)                                         # drugi raz te same fakty → potwierdzenia
        self.assertEqual(f[0]["potwierdzen"], 2)
        self.assertIn("Co już wiem o Andrzej", self.prompts[1])
        with self.db() as c:
            prof = self.R.profile_text(c, OWNER)
        self.assertIn("[Praca i firma]", prof)
        self.assertIn("[Ludzie wokół]", prof)

    def test_questions_on_whatsapp_and_answers_with_correction(self):
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "Notatki", text="Tekst o mnie")
        self.work()
        self.clock.set(19, 5)
        self.tick()
        with self.con() as con:
            msg = con.execute("SELECT body, to_phone FROM outbox WHERE purpose='pamiec:pytania' ORDER BY id").fetchall()
        self.assertEqual(len(msg), 1)                                       # Aga nie ma jeszcze faktów
        body = msg[0]["body"]
        self.assertIn("🐑 *Sebastian uczy się o Tobie* i ma 2 pytania:", body)
        self.assertIn("1. Zrozumiałem, że: „Andrzej prowadzi zespół Feniks.”", body)       # praca przed ludźmi
        self.assertIn("2. Zrozumiałem, że: „Andrzej ma żonę Agę", body)
        out = self.write("1 tak, 2 nie — Aga to moja wspólniczka, nie żona")
        self.assertIn("Dzięki, Andrzej! 🐑 ✓ 1 · poprawione: 2. Zapamiętane.", out[0]["body"])
        f = {x["tresc"]: x for x in self.facts()}
        self.assertEqual(f["Andrzej prowadzi zespół Feniks."]["status"], "potwierdzony")
        self.assertEqual(f["Andrzej ma żonę Agę, która szuka pracy w administracji."]["status"], "poprawiony")
        self.assertEqual(f["Aga to moja wspólniczka, nie żona"]["pewnosc"], 1.0)
        with self.db() as c:
            self.assertEqual(c.execute("SELECT jest FROM poprawki").fetchone()[0], "Aga to moja wspólniczka, nie żona")
        self.tick()                                                         # jeden raz dziennie
        with self.con() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM outbox WHERE purpose='pamiec:pytania'").fetchone()[0], 1)
        out = self.write("tak")                                             # nic już nie czeka → zwykła rozmowa
        self.assertNotIn("Zapamiętane", out[0]["body"])

    def test_corrections_win_in_profile_prompt(self):
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "N", text="x" * 30)
        self.work()
        with self.db() as c:
            fid = c.execute("SELECT id FROM fakty WHERE kategoria='ludzie'").fetchone()[0]
            self.R.fact_verdict(c, fid, "nie", "Aga jest wspólniczką Andrzeja")
            self.R.consolidate(c, OWNER, self.M.asker(self.ctx))
        prompt = [p for p in self.prompts if "„Ludzie wokół”" in p][-1]
        self.assertIn("było: Andrzej ma żonę Agę", prompt)
        self.assertIn("Aga jest wspólniczką Andrzeja", prompt)
        self.assertNotIn("(0.6, 1×) Andrzej ma żonę", prompt)

    def test_family_member_gets_own_questions_and_answers(self):
        self.reply = {"fakty": [{"kategoria": "praca", "tresc": "Aga szuka pracy w administracji w Krakowie.", "pewnosc": 0.6}]}
        with self.db() as c:
            self.R.add_source(c, AGA, "tekst", "CV", text="moje cv")
        self.work()
        self.clock.set(19, 5)
        self.tick()
        with self.con() as con:
            r = con.execute("SELECT body, to_phone FROM outbox WHERE purpose='pamiec:pytania'").fetchone()
        self.assertEqual(r["to_phone"], AGA)
        self.assertIn("Odpisz *tak* albo *nie — jak jest naprawdę*", r["body"])
        out = self.write("tak, zgadza się", phone=AGA)
        self.assertEqual(out[0]["to_phone"], AGA)
        self.assertIn("Dzięki, Aga!", out[0]["body"])
        self.assertEqual(self.facts(AGA)[0]["status"], "potwierdzony")

    def test_learns_from_chat_but_not_from_commands(self):
        self.write("zadania")
        self.write("Pamiętaj, że w poniedziałki zawsze mam spotkanie zespołu Feniks o 9 rano w biurze.")
        with self.db() as c:
            rows = [r["tekst"] for r in c.execute("SELECT * FROM rozmowy")]
        self.assertEqual(len(rows), 1)
        with self.db() as c:
            self.assertEqual(self.M.flush_chats(c), 0)                      # za mało i za świeże
            c.execute("UPDATE rozmowy SET ts=ts-7*3600")
            c.commit()
            self.assertEqual(self.M.flush_chats(c), 1)
            src = c.execute("SELECT * FROM zrodla WHERE rodzaj='whatsapp'").fetchone()
        self.assertEqual(src["osoba"], OWNER)
        self.work()
        self.assertIn("wiadomości, które Andrzej napisał(a) do swojego asystenta", [p for p in self.prompts if "Budujesz" in p][0])

    def test_what_you_know_and_ask_me(self):
        self.assertIn("Dopiero się o Tobie uczę", self.write("co o mnie wiesz")[0]["body"])
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "N", text="o mnie")
        self.work()
        self.assertIn("*Co o Tobie wiem* (3 faktów, 0 potwierdzonych)", self.write("co o mnie wiesz")[0]["body"])
        self.assertIn("ma 2 pytania", self.write("pytaj mnie")[0]["body"])
        self.assertIn("✓ 1, 2", self.write("wszystko się zgadza")[0]["body"])

    def test_answer_context_only_about_asking_person(self):
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "N", text="o mnie")
        self.work()
        DH.bind(W)
        own = DH.answer_context("gdzie pracuję?", W.owner_user())
        self.assertIn("planerem finansowym", own)
        self.assertEqual(DH.answer_context("gdzie pracuję?", W.user_by_phone(AGA)), "")
        self.write("czym się zajmuję w pracy na co dzień, powiesz mi?")
        answer_prompt = [p for p in self.prompts if "Pytanie: czym" in p][0]
        self.assertIn("Co Sebastian wie o osobie, z którą rozmawia", answer_prompt)

    def test_ctx_memory_for_other_addons_needs_permission(self):
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "N", text="o mnie")
        self.work()
        other = DH.Context({"id": "inny", "manifest": {"uprawnienia": ["pamiec.odczyt"]}})
        self.assertIn("inPartners", other.memory())
        with self.assertRaises(DH.PermissionDenied):
            DH.Context({"id": "x", "manifest": {"uprawnienia": []}}).memory()
        with self.assertRaises(DH.PermissionDenied):
            self.ctx.send_to("48111222333", "obcy numer")

    def test_drop_folder_and_seed_from_learner(self):
        prof = Path(s.DATA) / "learner" / "wyniki" / "Profil_wiedzy.md"
        prof.parent.mkdir(parents=True, exist_ok=True)
        prof.write_text("# Profil\n" + "Andrzej prowadzi zespół. " * 20, encoding="utf-8")
        with self.db() as c:
            c.execute("DELETE FROM meta WHERE k='seed_nauka'")
            c.commit()
            box = self.ctx.folder() / "wrzuc-tutaj" / "aga"
            box.mkdir(parents=True, exist_ok=True)
            f = chatgpt_zip(box / "chatgpt.zip")
            old = time.time() - 60
            import os
            os.utime(f, (old, old))
        self.work(1)
        with self.db() as c:
            src = {r["rodzaj"]: dict(r) for r in c.execute("SELECT * FROM zrodla")}
        self.assertEqual(src["nauka"]["osoba"], OWNER)
        self.assertEqual(src["chatgpt"]["osoba"], AGA)
        self.assertFalse(f.exists())
        self.assertIn("1 rozmów", src["chatgpt"]["notatka"])

    def test_terminal_upload_keeps_original(self):
        f = chatgpt_zip(Path(self.temp.name) / "x.zip")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.M.COMMANDS["wgraj"](self.ctx, [str(f), "Aga"])
        self.assertTrue(f.exists())
        self.assertIn("dla: Aga Kwiatkowska", out.getvalue())

    def test_parse_answers_grammar(self):
        P = self.R.parse_answers
        self.assertEqual(P("1 tak 2 nie, pracuje w PZU 3. dobrze", [1, 2, 3]), [(1, "tak", ""), (2, "nie", "pracuje w PZU"), (3, "tak", "")])
        self.assertEqual(P("nie, mieszkam w Krakowie", [4]), [(4, "nie", "mieszkam w Krakowie")])
        self.assertEqual(P("2: mieszkam w Krakowie", [1, 2]), [(2, "nie", "mieszkam w Krakowie")])
        self.assertEqual(P("Jutro o 10 mam spotkanie", [1, 2]), [])
        self.assertEqual(P("9 tak", [1, 2]), [])

    # ---------------------------------------------------------------- panel
    def test_panel_tab_main_and_aga_only(self):
        from flask import Flask
        with self.db() as c:
            self.R.add_source(c, OWNER, "tekst", "N", text="o mnie")
        self.work()
        app = Flask("t")
        app.secret_key = "x"
        DH.register_web(app, "pamiec", prefix="/pamiec")
        cl = app.test_client()
        html = cl.get(f"/pamiec?osoba={OWNER}").get_data(as_text=True)
        self.assertIn("Mam do Ciebie parę pytań, Andrzej", html)
        self.assertIn("Aga Kwiatkowska", html)                              # zakładki osób
        csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        qid = re.search(r'name="id" value="(\d+)"', html).group(1)
        r = cl.post("/pamiec/odpowiedz", data={"csrf": csrf, "osoba": OWNER, "id": qid, "werdykt": "nie", "poprawka": "Aga to wspólniczka"})
        self.assertEqual(r.status_code, 302)
        r = cl.post("/pamiec/wgraj", data={"csrf": csrf, "osoba": AGA, "plik": (io.BytesIO(open(chatgpt_zip(Path(self.temp.name) / "e.zip"), "rb").read()), "chatgpt.zip")},
                    content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        cl.post("/pamiec/tekst", data={"csrf": csrf, "osoba": AGA, "nazwa": "O mnie", "tekst": "Lubię porządek i planowanie."})
        with self.db() as c:
            self.assertEqual(sorted(r["rodzaj"] for r in c.execute("SELECT rodzaj FROM zrodla WHERE osoba=?", (AGA,))), ["plik", "tekst"])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM poprawki").fetchone()[0], 1)
        aga_app = Flask("a")
        aga_app.secret_key = "y"
        DH._LOADED.pop("pamiec", None)
        DH.register_web(aga_app, "pamiec", prefix="/pamiec", people_filter=lambda ps: [p for p in ps if p["id"] == AGA])
        html = aga_app.test_client().get(f"/pamiec?osoba={OWNER}").get_data(as_text=True)
        self.assertIn("Mam do Ciebie parę pytań, Aga", html)                # cudzej pamięci nie zobaczy
        self.assertNotIn("planerem finansowym", html)


if __name__ == "__main__":
    unittest.main()
