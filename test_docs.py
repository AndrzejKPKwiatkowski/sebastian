"""Testy modułu Dokumenty (Sebastian 2.2). Bez prawdziwej Ollamy — model jest udawany."""
import contextlib, io, json, os, pathlib, re, tempfile, time, unittest
from unittest.mock import patch

import sebastian as s
import learner as L
import learner_docs as D

PAGES = [
    ["KSIĘGA WIECZYSTA KR1P/00012345/6", "Sąd Rejonowy dla Krakowa-Podgórza", "DZIAŁ I-O — OZNACZENIE NIERUCHOMOŚCI",
     "Działka nr 123/4, obręb 0021 Podgórze", "Powierzchnia: 0,0812 ha"],
    ["DZIAŁ II — WŁASNOŚĆ", "Właściciel: Jan Nowak, udział 1/2", "Właściciel: Anna Nowak, udział 1/2"],
    ["DZIAŁ IV — HIPOTEKA", "Hipoteka umowna 350 000,00 zł", "Wierzyciel: PKO Bank Polski S.A.", "Hipoteka zwykła 20 000 zł"],
]
READ = {
    1: "KSIĘGA WIECZYSTA KR1P/00012345/6\nSąd Rejonowy dla Krakowa-Podgórza\nDZIAŁ I-O — OZNACZENIE NIERUCHOMOŚCI\n"
       "Działka nr 123/4, obręb 0021 Podgórze\nPowierzchnia: 0,0812 ha",
    2: "DZIAŁ II — WŁASNOŚĆ\nWłaściciel: Jan Nowak, udział 1/2\nWłaściciel: Anna Nowak[?], udział 1/2",
}
HAND_A = "Hipoteka umowna 350 000,00 zł\nWierzyciel: PKO Bank Polski S.A.\n~~Hipoteka zwykła 20 000 zł~~"
HAND_B = "Hipoteka umowna 350 000,00 zł\nWierzyciel: PKO Bank Pols S.A.\n~~Hipoteka zwykła 20 000 zł~~"
ENTRIES = {
    1: {"dzial_strony": "I-O", "wpisy": [{"dzial": "I-O", "rodzaj": "działka", "tytul": "Działka 123/4 — Podgórze",
                                          "tresc": "Działka nr 123/4.", "cytat": "Działka nr 123/4, obręb 0021 Podgórze"}]},
    2: {"dzial_strony": "II", "wpisy": [
        {"dzial": "II", "rodzaj": "właściciel", "tytul": "Jan Nowak — 1/2", "tresc": "Współwłaściciel.",
         "osoby": ["Jan Nowak"], "cytat": "Właściciel: Jan Nowak, udział 1/2"},
        {"dzial": "II", "rodzaj": "właściciel", "tytul": "Jan Wymyślony", "tresc": "Tego nie ma w tekście.",
         "cytat": "Jan Wymyślony jest jedynym właścicielem całości"}]},
    3: {"dzial_strony": "IV", "wpisy": [
        {"dzial": "IV", "rodzaj": "hipoteka", "tytul": "Hipoteka umowna 350 000 zł — PKO BP", "tresc": "Hipoteka.",
         "kwota": "350 000,00 zł", "cytat": "Hipoteka umowna 350 000,00 zł"},
        {"dzial": "IV", "rodzaj": "hipoteka", "tytul": "Hipoteka zwykła 20 000 zł", "tresc": "Wykreślona.",
         "cytat": "Hipoteka zwykła 20 000 zł"}]},
}


def make_scan(path, pages=PAGES):
    import fitz
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for cand in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if pathlib.Path(cand).exists():
            font = ImageFont.truetype(cand, 34)
            break
    doc = fitz.open()
    for lines in pages:
        im = Image.new("L", (1240, 1754), 245)
        d = ImageDraw.Draw(im)
        for i, t in enumerate(lines):
            d.text((120, 160 + i * 70), t, font=font, fill=20)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(path)


class FakeModel:
    """Udaje model wizyjny i tekstowy. Strona 3 jest „pisana ręcznie”, dwa odczyty różnią się jednym słowem."""
    def __init__(self):
        self.calls = []
        self.stop_after = None
        self.offset = 0

    def __call__(self, model, prompt, images=None, as_json=False, temperature=0.0, max_tokens=2500, num_ctx=None):
        if L.STOP:
            return None
        self.calls.append(prompt[:30])
        if self.stop_after and len(self.calls) >= self.stop_after:
            L.STOP = True
        page = len([c for c in self.calls if c.startswith("Patrzysz")]) - self.offset
        if prompt.startswith("Patrzysz"):
            return json.dumps({"typ": "mieszany" if page == 3 else "druk", "jezyk": "pl", "naglowek": "",
                               "wykreslenia": ["hipoteka zwykła przekreślona"] if page == 3 else [], "pieczecie": 1,
                               "podpisy": 0, "dopiski": [], "opis": "strona księgi"})
        if prompt.startswith("To strona"):
            return READ[page]
        if prompt.startswith("To fragment"):
            return HAND_A if "1 z" in prompt else ""
        if prompt.startswith("Przeczytaj uważnie"):
            return HAND_B if "1 z" in prompt else ""
        if prompt.startswith("Analizujesz"):
            n = int(re.search(r"stronę (\d+)", prompt).group(1))
            return json.dumps(ENTRIES[n], ensure_ascii=False)
        if prompt.startswith("Masz listę"):
            return json.dumps({"podsumowanie": "Działka w Krakowie, dwóch współwłaścicieli, hipoteka PKO BP.",
                               "do_wyjasnienia": [{"tekst": "Potwierdzić wykreślenie hipoteki zwykłej.", "wpisy": ["E5", "E77"]}]},
                              ensure_ascii=False)
        raise AssertionError("nieoczekiwane zapytanie: " + prompt[:60])


BASE = "http://127.0.0.1:8765"


def panel_client():
    app = s.make_app()
    app.testing = True
    c = app.test_client()
    c.post("/login", data={"token": (s.DATA / "panel.token").read_text()}, base_url=BASE)
    with c.session_transaction(base_url=BASE) as sess:
        csrf = sess["csrf"]
    return c, csrf


class DocsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = s.DATA
        s.DATA = pathlib.Path(self.temp.name)
        s.init()
        cfg = s.config()
        cfg["model"] = "test-model"
        s.write_json(s.DATA / "config.json", cfg)
        L.bind(s)
        L.STOP = False
        self.model = FakeModel()
        orig_find = D.find_bin
        self.patches = [patch.object(D, "chat", self.model), patch.object(D, "vision_ready", lambda: (True, "")),
                        patch.object(L, "check_model", lambda wait=True: None), patch.object(L, "sebastian_busy", lambda: False),
                        patch.object(L, "notify", lambda *a: None),
                        # bez ocrmypdf i Tesseracta — test ma działać wszędzie i szybko
                        patch.object(D, "find_bin", lambda name: None if name in ("ocrmypdf", "tesseract") else orig_find(name))]
        for p in self.patches:
            p.start()
        self.scan = s.DATA / "skan_testowy.pdf"
        make_scan(self.scan)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        L.STOP = False
        s.DATA = self.old
        self.temp.cleanup()

    def run_job(self, jid):
        with contextlib.closing(D.db()) as con:
            return D.process(con, jid)

    # ---------------------------------------------------------------- pojedyncze klocki

    def test_merge_reads_marks_differences(self):
        text, alts, agree = D.merge_reads("Wierzyciel: PKO Bank Polski S.A.\nkwota 350", "Wierzyciel: PKO Bank Pols S.A.\nkwota 350")
        self.assertIn("⟦Polski⟧", text)
        self.assertEqual(alts, [{"odczyt": "Polski", "inny": "Pols"}])
        self.assertIn("\nkwota 350", text)
        self.assertGreater(agree, 0.8)
        self.assertLess(agree, 1.0)

    def test_mark_uncertain_and_plain(self):
        self.assertEqual(D.mark_uncertain("Jan Kowalski[?] oraz Nowak [?]"), "Jan ⟦Kowalski⟧ oraz ⟦Nowak⟧")
        self.assertEqual(D.mark_uncertain("bez znaczników"), "bez znaczników")
        self.assertEqual(D.plain("⟦Jan⟧ ~~stare~~  nowe"), "Jan stare nowe")

    def test_split_rows_cuts_between_lines(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (800, 1800), 255)
        d = ImageDraw.Draw(im)
        for y in range(100, 1700, 90):
            d.rectangle((50, y, 750, y + 40), fill=0)       # „wiersze” pisma
        strips = D.split_rows(im, max_strips=4)
        self.assertGreater(len(strips), 1)
        y = 0
        for st in strips[:-1]:
            y += st.size[1]
            self.assertFalse(y >= 100 and (y - 100) % 90 <= 40, f"cięcie przechodzi przez wiersz pisma: y={y}")

    def test_wide_page_split_into_halves(self):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (3000, 2000), "white")
        d = ImageDraw.Draw(im)
        d.rectangle((100, 100, 1420, 1900), fill="black")       # lewa strona rozkładówki
        d.rectangle((1580, 100, 2900, 1900), fill="black")      # prawa strona
        strips = D.split_page(im)
        widths = sorted({st.size[0] for st in strips})
        self.assertEqual(len(widths), 2)
        self.assertTrue(1420 <= widths[0] <= 1580 and sum(widths) == 3000, widths)

    def test_quote_check_and_struck(self):
        self.assertTrue(D.quote_found("Hipoteka umowna 350 000,00 zł", "DZIAŁ IV hipoteka umowna 350 000,00 zł wierzyciel"))
        self.assertFalse(D.quote_found("Jan Wymyślony jest właścicielem", "Właściciel: Jan Nowak"))
        self.assertTrue(D.in_struck("Hipoteka zwykła 20 000 zł", "x ~~Hipoteka zwykła 20 000 zł~~ y"))
        self.assertEqual(D.norm_dzial("Dział IV"), "IV")
        self.assertEqual(D.norm_dzial("Dritte Abteilung"), "IV")
        self.assertEqual(D.norm_dzial("1-O"), "I-O")

    def test_kw_number_and_court(self):
        texts = ["KSIĘGA WIECZYSTA KR1P/00012345/6\nSąd Rejonowy dla Krakowa-Podgórza\nDZIAŁ I-O"]
        self.assertEqual(D.find_kw_number(texts), "KR1P/00012345/6")
        self.assertEqual(D.find_court(texts), "Sąd Rejonowy dla Krakowa-Podgórza")

    # ---------------------------------------------------------------- cały przebieg

    def test_full_pipeline_builds_linked_pdf(self):
        import fitz
        jid = D.add(self.scan, "KW próba")
        self.assertTrue(self.scan.exists(), "oryginał użytkownika nie może zniknąć przy doc-add")
        self.assertTrue(self.run_job(jid))
        with contextlib.closing(D.db()) as con:
            job = D.get_job(con, jid)
            self.assertEqual(job["status"], "done", job["error"])
            self.assertEqual(job["profile"], "kw")
            meta = D.job_meta(job)
            pages = {r["n"]: dict(r) for r in con.execute("SELECT * FROM pages WHERE job_id=?", (jid,))}
        self.assertEqual(meta["numer"], "KR1P/00012345/6")
        self.assertIn("Polski", pages[3]["text"])
        self.assertIn("⟦Polski⟧", pages[3]["text"])             # dwa odczyty pisma różniły się
        self.assertIn("⟦Nowak⟧", pages[2]["text"])         # model sam oznaczył niepewne słowo
        entries = json.loads((D.job_dir(job) / "wpisy.json").read_text())["wpisy"]
        by_title = {e["tytul"]: e for e in entries}
        self.assertFalse(by_title["Jan Wymyślony"]["potwierdzony"])  # cytatu nie ma w odczycie
        self.assertTrue(by_title["Hipoteka zwykła 20 000 zł"]["wykreslony"])
        self.assertTrue(any("Jan Wymyślony" in x["tekst"] for x in meta["do_wyjasnienia"]))
        self.assertEqual(meta["do_wyjasnienia"][0]["wpisy"], ["E5"])     # nieistniejący E77 odrzucony
        out = D.job_dir(job) / job["out_name"]
        with fitz.open(out) as doc:
            self.assertIn("Spis treści", doc[0].get_text())
            self.assertIn("KR1P/00012345/6", doc[0].get_text())
            offset = len(doc) - 3
            targets = [ln.get("page") for p in range(offset) for ln in doc[p].get_links()]
            self.assertTrue(all(t is not None and t >= 0 for t in targets))
            self.assertIn(offset + 2, targets)                   # „skan s. 3” prowadzi do 3. strony skanu
            self.assertFalse(any((ln.get("uri") or "").startswith("scan:") for p in range(offset) for ln in doc[p].get_links()))
            toc = [t[1] for t in doc.get_toc()]
            self.assertIn("6. Skany oryginału (3 stron)", toc)
            self.assertTrue(any(t.startswith("Strona 3") for t in toc))
            self.assertTrue(doc[offset + 2].search_for("PKO Bank"))     # niewidoczna warstwa z odczytu
            self.assertTrue(any(ln.get("page") == 0 for ln in doc[offset].get_links()))  # « spis treści
        # do nauki
        with contextlib.closing(L.db()) as lc:
            f = lc.execute("SELECT * FROM files WHERE id=?", (f"doc:{jid}",)).fetchone()
        self.assertEqual(f["status"], "new")
        self.assertIn("Hipoteka umowna", D.learning_text(f["id"]))
        with patch.object(L, "ask", lambda *a, **k: json.dumps({"fakty": [{"kategoria": "Historia i ważne wydarzenia", "fakt": "Nieruchomość w Krakowie ma hipotekę PKO BP."}]})):
            with contextlib.closing(L.db()) as lc:
                L.process_file(lc, None, lc.execute("SELECT * FROM files WHERE id=?", (f"doc:{jid}",)).fetchone())
                self.assertEqual(lc.execute("SELECT status FROM files WHERE id=?", (f"doc:{jid}",)).fetchone()[0], "done")
                self.assertEqual(L.stats(lc)["drive_all"], 0)

    def test_stop_and_resume_without_rereading(self):
        jid = D.add(self.scan, "KW przerwana")
        self.model.stop_after = 3            # przerwanie w trakcie 2. strony
        self.assertFalse(self.run_job(jid))
        with contextlib.closing(D.db()) as con:
            done = con.execute("SELECT COUNT(*) FROM pages WHERE job_id=? AND status='done'", (jid,)).fetchone()[0]
        self.assertEqual(done, 1)
        L.STOP = False
        self.model.stop_after = None
        self.model.offset = 2             # kolejne „Patrzysz…” dotyczą stron 2 i 3
        before = len(self.model.calls)
        self.assertTrue(self.run_job(jid))
        classified = [c for c in self.model.calls[before:] if c.startswith("Patrzysz")]
        self.assertEqual(len(classified), 2)          # strona 1 nie była czytana drugi raz

    def test_edit_page_and_apply_rebuilds_only_changed(self):
        jid = D.add(self.scan, "KW poprawki")
        self.run_job(jid)
        c, t = panel_client()
        r = c.get(f"/docs/{jid}", base_url=BASE)
        self.assertEqual(r.status_code, 200)
        self.assertIn("do sprawdzenia", r.get_data(as_text=True))
        self.assertEqual(c.get(f"/docs/{jid}/img/3?w=300", base_url=BASE).status_code, 200)
        r = c.get(f"/docs/{jid}/do-sprawdzenia.zip", base_url=BASE)
        self.assertEqual(r.status_code, 200)
        import zipfile
        names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
        self.assertIn("strona_0003.jpg", names)
        self.assertIn("odczyt.md", names)
        r = c.get(f"/docs/{jid}/strona/3", base_url=BASE)
        self.assertIn("Pols", r.get_data(as_text=True))
        self.assertEqual(c.post(f"/docs/{jid}/strona/3", data={"text": "x", "csrf": "zly"},
                                base_url=BASE).status_code, 403)
        r = c.post(f"/docs/{jid}/strona/3", data={"text": HAND_A, "verified": "1", "csrf": t}, base_url=BASE)
        self.assertEqual(r.status_code, 302)
        r = c.post(f"/docs/{jid}/akcja", data={"akcja": "apply", "csrf": t}, base_url=BASE)
        before = len(self.model.calls)
        self.assertTrue(self.run_job(jid))
        again = [c for c in self.model.calls[before:] if c.startswith("Analizujesz")]
        self.assertEqual(len(again), 1)               # tylko poprawiona strona
        with contextlib.closing(D.db()) as con:
            row = con.execute("SELECT * FROM pages WHERE job_id=? AND n=3", (jid,)).fetchone()
            self.assertFalse(D.needs_check(row))
            self.assertEqual(D.get_job(con, jid)["status"], "done")
        self.assertEqual(c.get(f"/docs/{jid}/pdf", base_url=BASE).status_code, 200)

    def test_panel_accepts_large_upload(self):
        import fitz
        from PIL import Image
        import numpy as np
        big = s.DATA / "duzy.pdf"
        rng = np.random.default_rng(0)
        with fitz.open() as doc:
            for _ in range(3):
                buf = io.BytesIO()
                Image.fromarray(rng.integers(0, 255, (2600, 2000, 3)).astype("uint8")).save(buf, "JPEG", quality=95)
                p = doc.new_page()
                p.insert_image(p.rect, stream=buf.getvalue())
            doc.save(big)
        self.assertGreater(big.stat().st_size, 7 * 1024 * 1024)      # więcej niż zwykły limit panelu (6 MB)
        c, t = panel_client()
        with open(big, "rb") as fh:
            r = c.post("/docs/upload", data={"csrf": t, "nazwa": "Duży skan", "typ": "kw", "plik": (fh, "KW duża.pdf")},
                       base_url=BASE, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:300])
        with contextlib.closing(D.db()) as con:
            job = con.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual((job["name"], job["src_name"], job["kind_hint"], job["status"], job["pages"]),
                         ("Duży skan", "KW duża.pdf", "kw", "queued", 3))
        self.assertFalse(list(D.root().glob(".wgrywanie-*")))
        # inne formularze nadal mają mały limit
        r = c.post("/docs/1/akcja", data={"csrf": t, "akcja": "x" * (7 * 1024 * 1024)}, base_url=BASE)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(c.get("/docs", base_url=BASE).status_code, 200)

    def test_inbox_and_lock(self):
        D.db().close()
        dropped = D.inbox() / "KW z Findera.pdf"
        dropped.write_bytes(self.scan.read_bytes())
        self.assertEqual(D.ingest_inbox(), [])                # świeży plik — może się jeszcze kopiować
        old = time.time() - 120
        os.utime(dropped, (old, old))
        self.assertEqual(len(D.ingest_inbox()), 1)
        self.assertFalse(dropped.exists())
        lock = D.JobLock()
        self.assertFalse(D.busy())
        self.assertTrue(lock.acquire())
        self.assertTrue(D.busy())
        self.assertFalse(D.JobLock().acquire())               # drugi proces nie wejdzie
        lock.release()
        self.assertFalse(D.busy())

    def test_learner_service_processes_documents(self):
        """Usługa nauki (learn-run) ma w środku wątek dokumentów; nauka czeka, gdy dokument jest analizowany."""
        import threading
        import learner_mail
        jid = D.add(self.scan, "KW w tle")

        class NoDrive:
            service = None
            def __init__(self, con): pass
            def due(self): return False
        seen_busy = []
        real_busy = D.busy
        def spy_busy():
            b = real_busy()
            seen_busy.append(b)
            return b
        with patch.object(L, "Drive", NoDrive), patch.object(learner_mail, "tick", lambda con: None), \
                patch.object(L, "install_signals", lambda: None), patch.object(D, "busy", spy_busy), \
                patch.object(L, "ask", lambda *a, **k: json.dumps({"fakty": []})):
            L.save_settings({"MAIL_HISTORY": False, "IDLE_SLEEP_MINUTES": 1})
            t = threading.Thread(target=L.run, daemon=True)
            t.start()
            deadline = time.time() + 60
            status = ""
            while time.time() < deadline:
                with contextlib.closing(D.db()) as con:
                    status = D.get_job(con, jid)["status"]
                if status == "done":
                    break
                time.sleep(0.5)
            L.STOP = True
            t.join(30)
        self.assertEqual(status, "done")
        self.assertFalse(t.is_alive())

    def test_cli_routing(self):
        with patch("sys.argv", ["sebastian.py", "doc-list"]), patch.object(D, "cmd_list") as cl:
            s.main()
            cl.assert_called_once()
        with patch("sys.argv", ["sebastian.py", "doc-rebuild", "3", "struktura"]), patch.object(D, "cmd_rebuild") as cr:
            s.main()
            cr.assert_called_once_with(3, "struktura")
        with patch("sys.argv", ["sebastian.py", "doctor"]), patch.object(s, "learn_command") as lc:
            try:
                s.main()
            except BaseException:
                pass
            lc.assert_not_called()                             # „doctor” to nie polecenie dokumentów


if __name__ == "__main__":
    unittest.main()
