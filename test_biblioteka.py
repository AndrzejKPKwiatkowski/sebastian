"""2.35: Biblioteka wiedzy w dodatku Pamięć — kursy i książki, wyszukiwanie, poradniki (PDF) i wyjaśnienia."""
import contextlib, io, json, re, time, unittest, unittest.mock
from pathlib import Path

import whatsapp as W
import dodatki_host as DH
from test_pamiec import Memory, AGA, OWNER

COURSE = """Moduł 3. Pierwsza rozmowa z klientem
Zanim zaczniesz rozmowę z klientem, przygotuj listę pytań otwartych. Słuchaj więcej, niż mówisz.
Zasada 70/30: klient mówi 70% czasu. Notuj potrzeby i cele klienta, a na końcu podsumuj je jego słowami.

Moduł 4. Obiekcje
Obiekcję „nie mam czasu” traktuj jako prośbę o krótszą rozmowę. Zaproponuj 15 minut."""


class Library(Memory):
    def setUp(self):
        super().setUp()
        self.B = self.M.B
        base_ask = W.ask

        def ask(prompt, as_json=False, max_tokens=1200, temperature=0.4):
            if "FRAGMENTY:" in prompt:
                self.prompts.append(prompt)
                if "praktyczny poradnik" in prompt:
                    return "# Rozmowa z klientem\n\nKrótki wstęp.\n\n## Przygotowanie\n- Lista pytań otwartych\n- Zasada **70/30**\n\n## Źródła\n- Kurs sprzedaży"
                return "Słuchaj więcej, niż mówisz — klient mówi 70% czasu.\n- Notuj potrzeby"
            return base_ask(prompt, as_json, max_tokens, temperature)
        p = unittest.mock.patch.object(W, "ask", ask)
        p.start()
        self.patches.append(p)

    def lib(self, pid=OWNER, name="Kurs sprzedaży", text=COURSE, year=0):
        with self.db() as c:
            return self.B.add(c, pid, name, year=year, text=text)

    def test_search_ignores_polish_endings_and_diacritics(self):
        self.lib()
        with self.db() as c:
            hits = self.B.search(c, OWNER, "jak rozmawiać z klientami na pierwszym spotkaniu")
            self.assertTrue(hits)
            self.assertIn("70/30", hits[0]["tekst"])
            self.assertEqual(self.B.search(c, AGA, "klient"), [])              # cudzej biblioteki nie widać
            self.assertEqual(c.execute("SELECT COUNT(*) FROM kawalki").fetchone()[0], 0)   # z biblioteki nie robię faktów o osobie

    def test_newer_source_wins(self):
        self.lib(name="Stary kurs", text="Rozmowa z klientem: klient mówi połowę czasu rozmowy z doradcą.", year=2012)
        self.lib(name="Nowy kurs", text="Rozmowa z klientem: klient mówi 70% czasu rozmowy z doradcą.", year=2025)
        with self.db() as c:
            self.assertEqual(self.B.search(c, OWNER, "ile czasu mówi klient w rozmowie")[0]["tytul"], "Nowy kurs")
            sid = c.execute("SELECT id FROM zrodla WHERE nazwa='Nowy kurs'").fetchone()[0]
            c.execute("UPDATE zrodla SET status='nieaktualne' WHERE id=?", (sid,))
            c.commit()
            self.assertEqual(self.B.search(c, OWNER, "ile czasu mówi klient w rozmowie")[0]["tytul"], "Stary kurs")

    def test_guide_on_whatsapp_becomes_pdf(self):
        self.lib()
        out = self.write("Poradnik: pierwsza rozmowa z klientem")
        self.assertIn("📚 Piszę poradnik „pierwsza rozmowa z klientem”", out[0]["body"])
        self.work()
        self.assertIn("Korzystaj WYŁĄCZNIE z fragmentów", self.prompts[-1])
        self.assertIn("[Kurs sprzedaży]", self.prompts[-1])
        self.tick()
        with self.con() as con:
            rows = [dict(r) for r in con.execute("SELECT kind, body, audio, to_phone FROM outbox ORDER BY id")]
        doc = [r for r in rows if r["kind"] == "doc"]
        self.assertEqual(len(doc), 1)
        self.assertTrue(doc[0]["audio"].endswith(".pdf") and Path(doc[0]["audio"]).exists())
        self.assertIn("Poradnik „pierwsza rozmowa z klientem”", [r["body"] for r in rows if r["kind"] == "text"][-1])
        import fitz
        text = fitz.open(doc[0]["audio"])[0].get_text()
        self.assertIn("Poradnik: pierwsza rozmowa z klientem", text)
        self.assertIn("Przygotowanie", text)
        self.assertIn("70/30", text)

    def test_explain_for_aga_goes_to_her(self):
        self.lib(pid=AGA, name="Kurs obiekcji")
        out = self.write("wyjaśnij mi: obiekcja nie mam czasu", phone=AGA)
        self.assertEqual(out[0]["to_phone"], AGA)
        self.work()
        self.tick()
        with self.con() as con:
            r = con.execute("SELECT body, to_phone FROM outbox WHERE purpose='pamiec:biblioteka'").fetchone()
        self.assertEqual(r["to_phone"], AGA)
        self.assertIn("*Wyjaśnienie: obiekcja nie mam czasu*", r["body"])

    def test_empty_library_and_no_hits(self):
        self.assertIn("biblioteka wiedzy jest jeszcze pusta", self.write("poradnik: cokolwiek")[0]["body"])
        self.lib()
        self.assertIn("nie znalazłem nic o „astronomia gwiazd”", self.write("poradnik o astronomia gwiazd")[0]["body"])
        self.assertIn("Twoja biblioteka wiedzy:*\n• Kurs sprzedaży", self.write("biblioteka")[0]["body"])

    def test_library_used_in_normal_answers(self):
        self.lib()
        self.write("ile czasu powinien mówić klient na pierwszej rozmowie?")
        prompt = [p for p in self.prompts if "Pytanie: ile czasu" in p][0]
        self.assertIn("Z biblioteki wiedzy tej osoby", prompt)
        self.assertIn("Zasada 70/30", prompt)

    def test_panel_upload_order_and_download(self):
        from flask import Flask
        app = Flask("t")
        app.secret_key = "x"
        DH.register_web(app, "pamiec", prefix="/pamiec")
        cl = app.test_client()
        html = cl.get(f"/pamiec?osoba={OWNER}").get_data(as_text=True)
        self.assertIn("📚 Biblioteka wiedzy", html)
        csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        r = cl.post("/pamiec/wgraj", data={"csrf": csrf, "osoba": OWNER, "cel": "biblioteka", "rok": "2024",
                                           "plik": (io.BytesIO(COURSE.encode()), "Kurs_sprzedazy.txt")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        self.work()
        with self.db() as c:
            src = c.execute("SELECT * FROM zrodla WHERE cel='biblioteka'").fetchone()
        self.assertEqual((src["status"], src["rok"]), ("gotowe", 2024))
        cl.post("/pamiec/zlecenie", data={"csrf": csrf, "osoba": OWNER, "rodzaj": "poradnik", "temat": "rozmowa z klientem"})
        self.work()
        html = cl.get(f"/pamiec?osoba={OWNER}").get_data(as_text=True)
        jid = re.search(r'/pamiec/plik/(\d+)', html).group(1)
        pdf = cl.get(f"/pamiec/plik/{jid}")
        self.assertEqual((pdf.status_code, pdf.data[:4]), (200, b"%PDF"))
        aga_app = Flask("a")
        aga_app.secret_key = "y"
        DH._LOADED.pop("pamiec", None)
        DH.register_web(aga_app, "pamiec", prefix="/pamiec", people_filter=lambda ps: [p for p in ps if p["id"] == AGA])
        self.assertEqual(aga_app.test_client().get(f"/pamiec/plik/{jid}").status_code, 404)   # cudzego poradnika nie pobierze

    def test_drop_folder_library_and_terminal_guide(self):
        import os
        box = self.ctx.folder() / "wrzuc-tutaj" / "aga" / "biblioteka"
        box.mkdir(parents=True, exist_ok=True)
        f = box / "Ksiazka_2023.txt"
        f.write_text(COURSE, encoding="utf-8")
        os.utime(f, (time.time() - 60, time.time() - 60))
        self.work()
        with self.db() as c:
            src = c.execute("SELECT * FROM zrodla WHERE cel='biblioteka'").fetchone()
        self.assertEqual((src["osoba"], src["rok"], src["status"]), (AGA, 2023, "gotowe"))
        self.assertTrue(box.exists())                                            # podfolder zostaje na kolejne pliki
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.M.COMMANDS["poradnik"](self.ctx, ["rozmowa z klientem", "Aga"])
        self.assertIn("PDF:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
