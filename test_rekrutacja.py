"""Testy dodatku Rekrutacja (część A). Bez Gmaila, bez Ollamy, bez Tailscale — wszystko udawane."""
import contextlib, datetime as dt, importlib, json, re, time, unittest
import os
os.environ["SEBASTIAN_TESTY"] = "1"          # testy nie dotykają prawdziwego pęku kluczy macOS (hasła Gmaila, klucze API)
from pathlib import Path
from unittest.mock import patch

import sebastian as s
import whatsapp as W
import dodatki_host as DH
from test_whatsapp import Base

TUE_10 = dt.datetime(2026, 11, 10, 10, 0, tzinfo=s.TZ)
FACTS = {
    "osoba": {"imie": "Anna", "nazwisko": "Testowa", "email": "anna.testowa@gmail.com", "telefon": "+48 600 000 000",
              "adres": "ul. Próbna 1", "miasto": "30-001 Kraków", "linkedin": ""},
    "profil": ["Specjalistka z doświadczeniem w administracji i prowadzeniu dokumentacji.",
               "Przygotowywałam raporty i koordynowałam terminy.", "Pracuję dokładnie i samodzielnie."],
    "doswiadczenie": [
        {"stanowisko": "Sekretarka medyczna", "firma": "ZZOZ", "miejsce": "Czarnków", "od": "02.2022", "do": "10.2024",
         "punkty": ["prowadzenie i archiwizacja dokumentacji medycznej", "obsługa administracyjna pacjentów"]},
        {"stanowisko": "Koordynatorka", "firma": "Mevlana Sp. z o.o.", "miejsce": "", "od": "12.2025", "do": "08.2026",
         "punkty": ["koordynowanie działań i terminów", "przygotowywanie raportów i ankiet"]}],
    "wyksztalcenie": [{"uczelnia": "Uniwersytet Testowy", "kierunek": "Pedagogika", "tytul": "magister", "okres": "2020 – 2022"}],
    "kursy": ["Zamówienia Publiczne - Akademia PARP (2026)"], "jezyki": ["polski – ojczysty", "angielski – zaawansowany"],
    "umiejetnosci": ["organizacja pracy", "samodzielność", "praca z dokumentacją", "analityczne myślenie"],
    "narzedzia": [{"nazwa": "Excel", "poziom": "dobry"}, {"nazwa": "Canva", "poziom": ""}], "prawo_jazdy": True,
    "warunki": {"umowa": "umowa o pracę", "etat": "pełny etat", "min_netto": "7000", "dostepnosc": "po miesięcznym okresie wypowiedzenia"}}
OFFER = ("Biuro Rachunkowe Testowe Sp. z o.o. zatrudni osobę na stanowisko Specjalistka ds. administracji biurowej w Krakowie. "
         "Obowiązki: prowadzenie dokumentacji, obieg korespondencji, koordynacja terminów. Wymagania: znajomość Excel, "
         "dokładność. CV prosimy przesyłać na adres rekrutacja@testowe.pl. ") * 2


class FakeModel:
    def __init__(self):
        self.letter = ("Szanowni Państwo,\n\nz zainteresowaniem przeczytałam ogłoszenie i chciałabym zgłosić swoją kandydaturę. "
                       "W poprzedniej pracy prowadziłam i archiwizowałam dokumentację medyczną oraz koordynowałam terminy. "
                       "Pracuję w Excelu i dbam o porządek w dokumentach.\n\nPrzygotowywałam raporty i ankiety, dlatego obieg "
                       "korespondencji i dokumentów nie jest dla mnie nowością. Cenię dokładność i samodzielność, a w pracy biurowej "
                       "najlepiej odnajduję się tam, gdzie liczy się porządek, terminowość i dobra komunikacja z zespołem.\n\n"
                       "Chętnie opowiem więcej podczas rozmowy.\n\nZ poważaniem\nAnna")
        self.truth = []
        self.profile = None

    def __call__(self, prompt, as_json=False, max_tokens=1200, temperature=0.4):
        if "Dobierasz" in prompt:
            return json.dumps({"kolejnosc": ["d2", "d1", "d99"], "punkty": {"d1": ["d1.2", "x"]}, "profil": ["p2", "p1", "p77"],
                               "umiejetnosci": ["u3", "u1", "u2"], "narzedzia": ["n1"]})
        if "Przeczytaj ogłoszenie" in prompt:
            return json.dumps({"firma": "Biuro Rachunkowe Testowe Sp. z o.o.", "stanowisko": "Specjalistka ds. administracji biurowej",
                               "miasto": "Kraków", "email": "rekrutacja@testowe.pl", "rodo": "", "sprzedaz": False, "ocena": 84,
                               "uzasadnienie": "Administracja i dokumentacja, bez sprzedaży."})
        if "Piszesz w imieniu" in prompt or "piszesz SWÓJ list" in prompt:
            return json.dumps({"list": self.letter, "mail": "Dzień dobry,\n\nw odpowiedzi na ogłoszenie przesyłam w załączniku CV i list "
                               "przewodni. Praca z dokumentacją i koordynacja terminów to obszar, w którym czuję się pewnie. "
                               "Będę wdzięczna za informację zwrotną."})
        if "sekcji „Profil zawodowy”" in prompt:
            return json.dumps({"profil": self.profile}) if self.profile else None
        if "kontrolerem prawdy" in prompt:
            return json.dumps({"niepotwierdzone": self.truth})
        return None


class RekrutacjaBase(Base):
    def setUp(self):
        super().setUp()
        DH._LOADED.clear()
        DH._STATE.clear()
        DH.bind(W)
        self.model = FakeModel()
        self.extra = [patch.object(W, "ask", self.model), patch.object(W, "now", lambda: TUE_10)]
        for p in self.extra:
            p.start()
        self.mod, self.ctx = DH.load(DH.discover()["rekrutacja"])
        pkg = self.mod.__name__
        self.extra.append(patch.object(importlib.import_module(pkg + ".poczta"), "send", self.fake_send))
        self.extra[-1].start()
        self.extra.append(patch.object(importlib.import_module(pkg + ".dokumenty"), "writer_model", lambda ctx: None))  # bez prawdziwego Ollamy
        self.extra[-1].start()
        self.extra.append(patch.object(importlib.import_module(pkg + ".kontakty"), "find_email", lambda *a, **k: {}))   # bez internetu
        self.extra[-1].start()
        self.R = importlib.import_module(pkg + ".rdzen")
        self.D = importlib.import_module(pkg + ".dokumenty")
        self.P = importlib.import_module(pkg + ".panel")
        self.O = importlib.import_module(pkg + ".oferty")
        f = self.R.empty_facts()
        for k, v in FACTS.items():
            f[k].update(v) if isinstance(f.get(k), dict) else f.__setitem__(k, v)
        self.R.save_facts(self.ctx, f)
        self.facts = self.R.load_facts(self.ctx)
        self.sent = []

    def tearDown(self):
        for p in self.extra:
            p.stop()
        DH._LOADED.clear()
        DH._STATE.clear()
        super().tearDown()

    def fake_send(self, sender, pwd, to, subject, body, attachments=(), name="", reply_to="", in_reply_to="", references="", html="", images=None):
        self.sent.append({"from": sender, "to": to, "subject": subject, "body": body, "files": [Path(p).name for p in attachments], "pwd": pwd,
                          "in_reply_to": in_reply_to, "html": html, "images": sorted(images or {})})
        return f"<id{len(self.sent)}@test>"

    def ready(self):
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "onboarding", "gotowe")
            self.R.meta_set(c, "poczta_aga", "anna.testowa@gmail.com")
            self.R.meta_set(c, "poczta_sebastian", "sebastian.test@gmail.com")
        self.R.set_secret(self.ctx, "aga", "a" * 16)
        self.R.set_secret(self.ctx, "sebastian", "s" * 16)

    def add(self, **kw):
        row = dict(utworzono=self.R.stamp(self.ctx), zmieniono=self.R.stamp(self.ctx), status="nowa", zrodlo="oferta", url="", firma="",
                   stanowisko="", email="", tresc=OFFER, klucz="")
        row.update(kw)
        with self.R.db(self.ctx) as c:
            cur = c.execute(f"INSERT INTO aplikacje({','.join(row)}) VALUES({','.join('?' * len(row))})", tuple(row.values()))
            c.commit()
            return cur.lastrowid

    def row(self, aid):
        with self.R.db(self.ctx) as c:
            return dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone())


class FactsAndDocuments(RekrutacjaBase):
    def test_selection_keeps_only_real_facts(self):
        sel = self.D.clean_selection(self.facts, json.loads(self.model("Dobierasz")))
        self.assertEqual(sel["kolejnosc"], ["d2", "d1"])                 # nieistniejące d99 odrzucone, nic nie znika
        self.assertEqual(sel["punkty"]["d1"], ["d1.2", "d1.1"])
        self.assertEqual(sel["profil"], ["p2", "p1"])
        self.assertEqual(self.D.clean_selection(self.facts, "śmieci"), self.D.default_selection(self.facts))

    def test_cv_is_one_page_and_built_only_from_facts(self):
        import fitz
        out = self.ctx.folder() / "cv.pdf"
        self.D.render_cv(self.facts, self.D.default_selection(self.facts), out)
        doc = fitz.open(out)
        self.assertEqual(len(doc), 1)
        text = re.sub(r"\s+", " ", doc[0].get_text())
        for needle in ("Anna", "Testowa", "Sekretarka medyczna", "02.2022 - 10.2024", "prowadzenie i archiwizacja", "Excel – dobry",
                       "prawo jazdy kat. B", "KLAUZULA RODO", "2016/679"):
            self.assertIn(needle, text)

    def test_custom_rodo_clause_lands_in_cv(self):
        import fitz
        out = self.ctx.folder() / "cv2.pdf"
        self.D.render_cv(self.facts, None, out, rodo="Wyrażam zgodę na przetwarzanie danych przez Testowe Sp. z o.o. także w przyszłych rekrutacjach.")
        self.assertIn("przyszłych rekrutacjach", re.sub(r"\s+", " ", fitz.open(out)[0].get_text()))

    def test_truth_rules_flag_inventions(self):
        app = {"zrodlo": "oferta", "firma": "X", "stanowisko": "Asystentka", "tresc": "Wymagamy Excel."}
        bad = "Mam 5 lat doświadczenia, znam SAP i język niemiecki oraz mam certyfikat PRINCE2."
        notes = " ".join(self.D.rule_check(self.facts, app, bad))
        for word in ("5", "sap", "niemiecki", "certyfikat"):
            self.assertIn(word, notes.lower())
        self.assertEqual(self.D.rule_check(self.facts, app, "Pracuję w Excelu i prowadziłam dokumentację medyczną."), [])

    def test_duplicate_keys(self):
        k = self.R.dedupe_key
        self.assertEqual(k("ABC Sp. z o.o.", "Specjalista ds. administracji (K/M)"), k("abc", "specjalista ds administracji"))
        self.assertNotEqual(k("ABC", "Asystentka"), k("ABC", "Księgowa"))
        self.assertEqual(self.R.slug("Biuro Rachunkowe Żółć S.A."), "Biuro_Rachunkowe_Zolc")

    def test_offer_fetch_refuses_local_addresses(self):
        for url in ("http://127.0.0.1:8765/", "http://localhost:11434/api/tags", "file:///etc/passwd", "http://192.168.1.1/"):
            with self.assertRaises(RuntimeError):
                self.O.fetch(url)
        self.assertEqual(self.O.emails("pisz: Rekrutacja@Firma.pl, logo@2x.png, noreply@firma.pl"), ["rekrutacja@firma.pl"])


class Flow(RekrutacjaBase):
    def test_prepare_approve_send_and_report(self):
        self.ready()
        aid = self.add()
        self.assertEqual(self.P.prepare(self.ctx, aid), "do_zatwierdzenia")
        a = self.row(aid)
        self.assertEqual(a["firma"], "Biuro Rachunkowe Testowe Sp. z o.o.")
        self.assertEqual(a["email"], "rekrutacja@testowe.pl")
        self.assertEqual(a["ocena"], 84)
        self.assertEqual(a["cv_plik"], "Anna_Testowa_CV_Biuro_Rachunkowe_Testowe.pdf")
        self.assertTrue(a["list"].endswith("Z poważaniem\nAnna Testowa\ntel. +48 600 000 000"))
        self.assertNotIn("—", a["list"])
        self.assertNotIn("Model nie odpowiedział", a["uwagi"])
        # nic nie wychodzi bez zatwierdzenia
        self.assertIsNone(self.P.send_one(self.ctx, send=self.fake_send))
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zatwierdzona")
        self.assertEqual(self.P.send_one(self.ctx, send=self.fake_send), aid)
        m = self.sent[0]
        self.assertEqual((m["from"], m["to"]), ("anna.testowa@gmail.com", "rekrutacja@testowe.pl"))
        self.assertEqual(m["subject"], "Aplikacja na stanowisko Specjalistka ds. administracji biurowej – Anna Testowa")
        self.assertEqual(len(m["files"]), 2)
        self.assertEqual(self.row(aid)["status"], "wyslana")
        # ta sama oferta drugi raz = duplikat
        dup = self.add(url="", firma="Biuro Rachunkowe Testowe", stanowisko="Specjalistka ds. administracji biurowej (K/M)")
        self.assertEqual(self.P.prepare(self.ctx, dup), "duplikat")
        # raport: ze skrzynki Sebastiana do Agi, po 20:00
        with patch.object(W, "now", lambda: TUE_10.replace(hour=20, minute=5)):
            self.assertTrue(self.P.evening_report(self.ctx, send=self.fake_send))
            self.assertFalse(self.P.evening_report(self.ctx, send=self.fake_send))       # raz dziennie
        r = self.sent[-1]
        self.assertEqual((r["from"], r["to"], r["pwd"]), ("sebastian.test@gmail.com", "anna.testowa@gmail.com", "s" * 16))
        self.assertIn("dzisiaj wysłałem 1 aplikację", r["body"])
        self.assertIn("Biuro Rachunkowe Testowe", r["body"])

    def test_sending_respects_window_limit_and_pause(self):
        self.ready()
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zatwierdzona")
        with patch.object(W, "now", lambda: TUE_10.replace(hour=17)):
            self.assertIsNone(self.P.send_one(self.ctx, send=self.fake_send))
        with patch.object(W, "now", lambda: dt.datetime(2026, 11, 14, 10, 0, tzinfo=s.TZ)):          # sobota
            self.assertIsNone(self.P.send_one(self.ctx, send=self.fake_send))
        self.ctx.set_setting("wstrzymane", "tak")
        self.assertIsNone(self.P.send_one(self.ctx, send=self.fake_send))
        self.ctx.set_setting("wstrzymane", "nie")
        self.ctx.set_setting("limit_dzienny", 0)
        self.assertIsNone(self.P.send_one(self.ctx, send=self.fake_send))
        self.ctx.set_setting("limit_dzienny", 70)
        self.assertEqual(self.P.send_one(self.ctx, send=self.fake_send), aid)
        self.assertEqual(len(self.sent), 1)

    def test_suspect_text_goes_to_review_and_missing_email_to_completion(self):
        self.ready()
        self.model.truth = ["„znam SAP” — brak w faktach"]
        aid = self.add()
        self.assertEqual(self.P.prepare(self.ctx, aid), "do_sprawdzenia")
        self.assertIn("SAP", self.row(aid)["uwagi"])
        self.model.truth = []
        aid2 = self.add(tresc=OFFER.replace("rekrutacja@testowe.pl", "formularz na stronie"), firma="Inna Firma", stanowisko="Asystentka")
        self.assertIn(self.P.prepare(self.ctx, aid2), ("do_uzupelnienia",))

    def test_failed_send_is_reported_not_lost(self):
        self.ready()
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zatwierdzona")

        def boom(*a, **k):
            raise OSError("brak sieci")
        self.assertIsNone(self.P.send_one(self.ctx, send=boom))
        a = self.row(aid)
        self.assertEqual(a["status"], "blad")
        self.assertIn("brak sieci", a["blad"])


class Panel(RekrutacjaBase):
    def client(self, hosts=None):
        app = self.P.make_app(self.ctx, hosts=hosts)
        app.config.update(TESTING=True, SEND=self.fake_send, TEST_LOGIN=lambda a, p: (True, "") if len(p.replace(" ", "")) == 16 else (False, "złe hasło"))
        return app.test_client()

    def csrf(self, cl):
        with cl.session_transaction() as sess:
            sess.setdefault("csrf", "tok")
            return sess["csrf"]

    def test_first_run_password_and_onboarding(self):
        cl = self.client()
        self.assertEqual(cl.get("/").status_code, 302)
        with contextlib.redirect_stdout(open("/dev/null", "w")):
            self.mod.cmd_adres(self.ctx, [])
        with self.R.db(self.ctx) as c:
            tok = self.R.meta_get(c, "token_startowy")
        self.assertEqual(cl.get("/start/zly").status_code, 403)
        r = cl.post(f"/start/{tok}", data={"haslo": "dobrehaslo1", "haslo2": "dobrehaslo1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(cl.get(f"/start/{tok}").status_code, 403)                         # link jednorazowy
        self.assertIn("/witaj/1", cl.get("/").headers["Location"])
        t = self.csrf(cl)
        self.assertEqual(cl.post("/witaj/1", data={}).status_code, 400)                    # bez CSRF
        self.assertIn("/witaj/2", cl.post("/witaj/1", data={"csrf": t}).headers["Location"])
        self.assertIn("Google odrzucił".encode() if False else "złe hasło".encode(), cl.post("/witaj/2", data={"csrf": t, "adres": "anna.testowa@gmail.com", "haslo": "x"}).data)
        self.assertIn("/witaj/3", cl.post("/witaj/2", data={"csrf": t, "adres": "anna.testowa@gmail.com", "haslo": "abcd efgh ijkl mnop"}).headers["Location"])
        self.assertIn("/witaj/4", cl.post("/witaj/3", data={"csrf": t, "pomin": "1"}).headers["Location"])
        self.assertIn("Kontakt".encode(), cl.get("/witaj/4").data)
        form = {"csrf": t, "o_imie": "Anna", "o_nazwisko": "Testowa", "o_email": "anna.testowa@gmail.com", "o_telefon": "1", "o_adres": "",
                "o_miasto": "Kraków", "o_linkedin": "", "profil": "Zdanie pierwsze.\nZdanie drugie.", "ile_stanowisk": "1",
                "d0_stanowisko": "Sekretarka", "d0_firma": "ZZOZ", "d0_od": "02.2022", "d0_do": "10.2024", "d0_punkty": "dokumentacja\narchiwum",
                "ile_szkol": "0", "kursy": "", "jezyki": "polski"}
        self.assertIn("/witaj/5", cl.post("/witaj/4", data=form).headers["Location"])
        self.assertIn("/witaj/6", cl.post("/witaj/5", data={"csrf": t, "t0": "1", "t0_poziom": "dobry", "t6": "1",
                                                            "inne_narzedzia": "Optima – podstawowy", "umiejetnosci": "a\nb\nc", "prawo_jazdy": "1"}).headers["Location"])
        f = self.R.load_facts(self.ctx)
        self.assertEqual([(t_["nazwa"], t_["poziom"]) for t_ in f["narzedzia"]], [("Word", "dobry"), ("Canva", ""), ("Optima", "podstawowy")])
        self.assertEqual(f["doswiadczenie"][0]["punkty"][1]["tekst"], "archiwum")
        self.assertIn("/witaj/7", cl.post("/witaj/6", data={"csrf": t, "c0": "1", "n0": "1", "w_umowa": "umowa o pracę", "w_dojazd_km": "50"}).headers["Location"])
        self.assertIn("/witaj/8", cl.post("/witaj/7", data={"csrf": t, "szukanie": "1", "podziekowania": "1", "limit_dzienny": "40"}).headers["Location"])
        st = self.ctx.settings()
        self.assertEqual((st["szukanie"], st["autopilot"], st["przypomnienia"], st["limit_dzienny"]), (True, False, False, 40))
        self.assertEqual(cl.get("/podglad-cv.pdf").data[:4], b"%PDF")
        self.assertEqual(cl.post("/witaj/8", data={"csrf": t}).headers["Location"], "/")
        self.assertIn("Dodaj ofertę".encode(), cl.get("/").data)

    def test_login_throttle_and_host_check(self):
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        self.assertEqual(self.client(hosts={"100.64.0.5"}).get("/login", headers={"Host": "evil.example"}).status_code, 403)
        cl = self.client()
        for _ in range(5):
            cl.post("/login", data={"haslo": "zle"})
        self.assertIn("Za dużo prób".encode(), cl.post("/login", data={"haslo": "poprawne123"}).data)

    def test_add_offer_from_panel_and_duplicate(self):
        self.ready()
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        cl = self.client()
        cl.post("/login", data={"haslo": "poprawne123"})
        t = self.csrf(cl)
        r = cl.post("/dodaj", data={"csrf": t, "rodzaj": "oferta", "url": "", "tresc": OFFER})
        aid = int(r.headers["Location"].rsplit("/", 1)[1])
        self.assertIn("Przygotowuję dokumenty".encode(), cl.get(f"/aplikacja/{aid}").data)
        self.P.work_once(self.ctx)
        page = cl.get(f"/aplikacja/{aid}").data.decode()
        self.assertIn("Zatwierdź i wyślij", page)
        self.assertEqual(cl.get(f"/plik/{aid}/cv").data[:4], b"%PDF")
        self.assertEqual(cl.get(f"/plik/{aid}/../../sesja.key").status_code, 404)
        a = self.row(aid)
        r = cl.post(f"/aplikacja/{aid}", data={"csrf": t, "co": "zatwierdz", "firma": a["firma"], "stanowisko": a["stanowisko"], "email": a["email"],
                                               "miasto": a["miasto"], "list": a["list"], "temat": a["temat"], "mail": a["mail"]})
        self.assertEqual(self.row(aid)["status"], "zatwierdzona")
        self.P.work_once(self.ctx)
        self.assertEqual(self.row(aid)["status"], "wyslana")
        # spontaniczna do tej samej firmy dwa razy
        r1 = cl.post("/dodaj", data={"csrf": t, "rodzaj": "spontaniczna", "firma": "Kancelaria Nowak", "email": "biuro@nowak.pl"})
        r2 = cl.post("/dodaj", data={"csrf": t, "rodzaj": "spontaniczna", "firma": "Kancelaria Nowak sp. z o.o.", "email": "biuro@nowak.pl"})
        self.assertEqual(r1.headers["Location"], r2.headers["Location"])
        self.assertIn("Kancelaria".encode(), cl.get("/aplikacje?q=Nowak").data)


class Replies(RekrutacjaBase):
    def sent_app(self, **kw):
        self.ready()
        aid = self.add(**kw)
        self.P.prepare(self.ctx, aid)
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zatwierdzona")
        self.P.send_one(self.ctx, send=self.fake_send)
        self.A = importlib.import_module(self.mod.__name__ + ".odpowiedzi")
        return aid

    def mail(self, uid, body, subject="Re: Aplikacja", od="hr@testowe.pl", reply_to="<id1@test>", auto=False):
        return {"uid": uid, "message_id": f"<m{uid}@x>", "od": od, "od_nazwa": "Kadry", "temat": subject, "data": "2026-11-10T11:00:00",
                "in_reply_to": reply_to, "references": reply_to, "auto": auto, "tresc": body}

    def test_invitation_notifies_and_drafts(self):
        aid = self.sent_app()
        W.save_settings({"WA_USERS": [{"phone": "48600000000", "name": "Anna", "access": "pelny"}]})
        W.bind(s)
        box = [self.mail(5, "Dzień dobry, zapraszamy Panią na rozmowę kwalifikacyjną w czwartek 13.11 o 10:00. Proszę o potwierdzenie.")]
        answer = {"rodzaj": "zaproszenie", "streszczenie": "Zaproszenie na rozmowę w czwartek 13.11 o 10:00.", "termin": "13.11 10:00", "pytania": [],
                  "odpowiedz": "Dzień dobry, dziękuję za zaproszenie i chętnie przyjdę na rozmowę w czwartek o dziesiątej.",
                  "brakuje": ["Czy proponowany termin Ci pasuje?"]}
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps(answer)):
            self.assertEqual(self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box), 1)
        self.assertEqual(self.row(aid)["status"], "zaproszenie")
        with contextlib.closing(W.db()) as con:
            out = con.execute("SELECT body, to_phone FROM outbox WHERE purpose='rekrutacja'").fetchall()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["to_phone"], "48600000000")
        self.assertIn("Zaproszenie na rozmowę", out[0]["body"])
        self.assertTrue(any("Zaproszenie na rozmowę" in m["subject"] and m["to"] == "anna.testowa@gmail.com" and "cid:brawo" in m["html"] for m in self.sent))
        with self.R.db(self.ctx) as c:
            q = c.execute("SELECT * FROM pytania").fetchone()
            w = c.execute("SELECT * FROM wiadomosci").fetchone()
        self.assertEqual(q["pytanie"], "Czy proponowany termin Ci pasuje?")
        reply = {"odpowiedz": "Dzień dobry, dziękuję za zaproszenie. Potwierdzam rozmowę w czwartek 13.11 o 10:00.", "brakuje": []}
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps(reply)):
            self.A.answer_question(self.ctx, q["id"], "tak, pasuje")
        self.assertEqual(self.R.load_facts(self.ctx)["odpowiedzi"]["Czy proponowany termin Ci pasuje?"], "tak, pasuje")
        self.A.send_draft(self.ctx, w["id"], "Dzień dobry, potwierdzam rozmowę. Anna", send=self.fake_send)
        last = self.sent[-1]
        self.assertEqual((last["to"], last["subject"]), ("hr@testowe.pl", "Re: Aplikacja"))
        self.assertEqual(self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box), 0)

    def test_rejection_gets_thanks_and_private_mail_is_ignored(self):
        aid = self.sent_app()
        box = [self.mail(7, "Dzień dobry, dziękujemy za udział. Niestety zdecydowaliśmy się na innego kandydata."),
               self.mail(8, "Promocja w sklepie, kup teraz!", subject="Rabat 20%", od="sklep@sklep.pl", reply_to="")]
        verdict = {"rodzaj": "odmowa", "streszczenie": "Odmowa.", "termin": "", "pytania": []}
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps(verdict)):
            self.assertEqual(self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box), 1)
        self.assertEqual(self.row(aid)["status"], "odmowa")
        self.assertEqual(self.row(aid)["podziekowanie"], "czeka")             # wychodzi dopiero w oknie wysyłki
        n = len(self.sent)
        self.assertEqual(self.A.pending_thanks(self.ctx, send=self.fake_send), 1)
        self.assertEqual(len(self.sent), n + 1)
        self.assertIn("dziękuję za informację", self.sent[-1]["body"])
        self.assertEqual(self.A.pending_thanks(self.ctx, send=self.fake_send), 0)
        with self.R.db(self.ctx) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM wiadomosci").fetchone()[0], 1)

    def test_autoresponder_and_follow_up(self):
        aid = self.sent_app()
        box = [self.mail(9, "To jest wiadomość automatyczna. Potwierdzamy otrzymanie zgłoszenia.", auto=True)]
        with patch.object(W, "ask", lambda prompt, **kw: None):
            self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box)
        self.assertEqual(self.row(aid)["status"], "wyslana")
        with self.R.db(self.ctx) as c:
            c.execute("UPDATE aplikacje SET odpowiedz_kiedy='', wyslano='2026-10-20T10:00:00+01:00' WHERE id=?", (aid,))
            c.commit()
        self.assertEqual(self.A.follow_ups(self.ctx, send=self.fake_send), 1)
        self.assertIn("czy jest ona jeszcze rozpatrywana", self.sent[-1]["body"])
        self.assertEqual(self.A.follow_ups(self.ctx, send=self.fake_send), 0)


class SourcesAndForms(RekrutacjaBase):
    def setUp(self):
        super().setUp()
        self.Z = importlib.import_module(self.mod.__name__ + ".zrodla")
        self.F = importlib.import_module(self.mod.__name__ + ".formularze")

    def analysis(self, **kw):
        base = {"firma": "Firma", "stanowisko": "Asystentka", "miasto": "Kraków", "ocena": 80}
        base.update(kw)
        return lambda prompt, **k: json.dumps(base) if "Przeczytaj" in prompt else self.model(prompt)

    def test_listing_page_finds_offers_and_skips_seen(self):
        page = ('<html><body><a href="/oferty/123-asystentka-biura">Asystentka biura zarządu</a>'
                '<a href="/oferty/124-spawacz">Spawacz MIG/MAG</a><a href="/polityka-prywatnosci">Polityka prywatności</a>'
                '<a href="https://inna.pl/praca/1">Specjalistka ds. administracji</a></body></html>')
        with self.R.db(self.ctx) as c:
            self.Z.seed(c, self.ctx)
            c.execute("DELETE FROM zrodla")
            c.execute("INSERT INTO zrodla(typ,url,nazwa) VALUES('strona','https://firma.pl/kariera','Firma')")
            c.execute("INSERT INTO zrodla(typ,url,nazwa) VALUES('strona','https://www.pracuj.pl/praca','Pracuj')")
            c.commit()
        with patch.object(self.Z, "_get", lambda url, **k: (page, url)):
            self.assertEqual(self.Z.discover(self.ctx), 1)
            with self.R.db(self.ctx) as c:
                c.execute("UPDATE zrodla SET sprawdzono=''")
                c.commit()
            self.assertEqual(self.Z.discover(self.ctx), 0)
        with self.R.db(self.ctx) as c:
            a = c.execute("SELECT * FROM aplikacje").fetchone()
            pr = c.execute("SELECT * FROM zrodla WHERE nazwa='Pracuj'").fetchone()
        self.assertEqual((a["url"], a["zrodlo"]), ("https://firma.pl/oferty/123-asystentka-biura", "auto"))
        self.assertEqual(pr["wlaczone"], 0)

    def test_jsonld_and_auto_filter(self):
        page = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"Koordynatorka biura",'
                '"hiringOrganization":{"name":"Testowe SA"},"jobLocation":{"address":{"addressLocality":"Katowice"}},"description":"<p>Obsługa biura</p>"}</script>')
        got = [self.Z.posting_text(p) for p in self.Z.jsonld_postings(page)]
        self.assertEqual((got[0]["tytul"], got[0]["firma"], got[0]["miasto"]), ("Koordynatorka biura", "Testowe SA", "Katowice"))
        self.ready()
        aid = self.add(zrodlo="auto")
        with patch.object(W, "ask", self.analysis(firma="Daleko", miasto="Gdańsk", ocena=90)):
            self.assertEqual(self.P.prepare(self.ctx, aid), "odrzucona")
        self.assertIn("za daleko", self.row(aid)["notatka"])
        aid2 = self.add(zrodlo="auto")
        with patch.object(W, "ask", self.analysis(firma="Słabe", ocena=30)):
            self.assertEqual(self.P.prepare(self.ctx, aid2), "odrzucona")
        self.assertTrue(self.R.in_area("Wieliczka") and self.R.in_area("praca zdalna") and not self.R.in_area("Warszawa"))

    def test_autopilot_and_spontaneous(self):
        self.ready()
        self.ctx.set_setting("autopilot", "tak")
        aid = self.add(zrodlo="auto")
        self.assertEqual(self.P.prepare(self.ctx, aid), "zatwierdzona")
        with self.R.db(self.ctx) as c:
            added, skipped = self.Z.import_firms(c, self.ctx, "Kancelaria Nowak; biuro@nowak.pl; www.nowak.pl; prawo pracy\nBez maila\nKancelaria Nowak; biuro@nowak.pl")
        self.assertEqual((added, skipped), (1, 2))
        self.assertEqual(self.Z.spontaneous_fill(self.ctx, 5), 1)
        with self.R.db(self.ctx) as c:
            sp = c.execute("SELECT id FROM aplikacje WHERE zrodlo='spontaniczna'").fetchone()["id"]
        self.assertEqual(self.P.prepare(self.ctx, sp), "zatwierdzona")
        self.assertTrue(self.row(sp)["temat"].startswith("Zapytanie o możliwość współpracy"))

    def test_form_channel_kit_and_recruitee(self):
        self.ready()
        aid = self.add(url="https://kariera.firma.pl/oferta/1", tresc=OFFER.replace("rekrutacja@testowe.pl", "formularz"))
        with patch.object(W, "ask", self.analysis()):
            self.assertEqual(self.P.prepare(self.ctx, aid), "formularz")
        kit = dict(self.F.kit(self.facts, self.row(aid)))
        self.assertEqual(kit["Oczekiwania finansowe"], "od 7000 zł netto miesięcznie")
        self.assertEqual(kit["Miasto"], "Kraków")
        app = {"email": "", "url": "https://firma.recruitee.com/o/asystentka-biura", "kanal": "", "list": "List"}
        self.assertEqual(self.F.channel(app), {"typ": "recruitee", "host": "firma.recruitee.com", "slug": "asystentka-biura"})

        class Resp:
            def __init__(self, code, data=None):
                self.status_code, self._d = code, data or {}

            def json(self):
                return self._d

            def raise_for_status(self):
                pass
        calls = []
        cv = self.ctx.folder() / "cv.pdf"
        cv.write_bytes(b"%PDF-1.4")
        q_legal = {"offer": {"open_questions": [{"id": 1, "kind": "legal", "body": "Zgoda na przetwarzanie danych (RODO)", "required": True}]}}
        q_text = {"offer": {"open_questions": [{"id": 2, "kind": "string", "body": "Ile lat doświadczenia?", "required": True}]}}
        post = lambda url, data=None, files=None, **k: calls.append((url, data, files)) or Resp(201)
        self.assertEqual(self.F.recruitee_apply(self.facts, app, cv, cv, "List", post=post, get=lambda url, **k: Resp(200, q_legal)), (True, ""))
        url, data, files = calls[0]
        self.assertEqual(url, "https://firma.recruitee.com/api/offers/asystentka-biura/candidates?async=true")
        self.assertEqual(data["candidate[name]"], "Anna Testowa")
        self.assertEqual(data["candidate[open_question_answers_attributes][0][flag]"], "true")
        ok, why = self.F.recruitee_apply(self.facts, app, cv, cv, "List", post=post, get=lambda url, **k: Resp(200, q_text))
        self.assertFalse(ok)
        self.assertIn("wymagane pytanie", why)


class ReviewFindings(Replies):
    """Przypadki z niezależnego przeglądu kodu (11.11.2026)."""

    def test_own_alerts_are_not_read_as_replies(self):
        aid = self.sent_app()
        echo = self.mail(20, "Zaproszenie na rozmowę: Biuro Rachunkowe Testowe. Zapraszamy na rozmowę kwalifikacyjną.", od="sebastian.test@gmail.com", reply_to="")
        marked = dict(self.mail(21, "Zaproszenie na rozmowę kwalifikacyjną, rekrutacja", od="ktos@testowe.pl", reply_to=""), nasza=True)
        self.assertEqual(self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: [echo, marked]), 0)
        self.assertEqual(self.row(aid)["status"], "wyslana")

    def test_protected_addresses_are_not_used_for_applications(self):
        self.ready()
        text = OFFER.replace("rekrutacja@testowe.pl", "formularz na stronie") + " Administrator danych: iod@testowe.pl, rodo@testowe.pl."
        aid = self.add(url="https://kariera.testowe.pl/1", tresc=text)
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "Testowe", "stanowisko": "Asystentka", "miasto": "Kraków",
                                                                      "email": "iod@testowe.pl", "ocena": 80}) if "Przeczytaj" in prompt else self.model(prompt)):
            self.assertEqual(self.P.prepare(self.ctx, aid), "formularz")
        self.assertEqual(self.row(aid)["email"], "")

    def test_invitation_with_niestety_is_not_a_rejection(self):
        aid = self.sent_app()
        box = [self.mail(30, "Dzień dobry, niestety wtorkowy termin odpadł. Zapraszamy na rozmowę kwalifikacyjną w czwartek o 10.")]
        with patch.object(W, "ask", lambda prompt, **kw: None):
            self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box)
        self.assertEqual(self.row(aid)["status"], "zaproszenie")
        self.assertEqual(self.row(aid)["podziekowanie"], "")
        self.assertFalse(any("Szkoda" in m["body"] for m in self.sent))

    def test_unsure_rejection_waits_for_aga(self):
        aid = self.sent_app()
        box = [self.mail(31, "Dzień dobry, dziękujemy, ale zdecydowaliśmy się na innego kandydata.")]
        with patch.object(W, "ask", lambda prompt, **kw: None):
            self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box)
        self.assertEqual(self.row(aid)["status"], "odmowa")
        self.assertEqual(self.row(aid)["podziekowanie"], "")
        with self.R.db(self.ctx) as c:
            w = c.execute("SELECT * FROM wiadomosci").fetchone()
        self.assertEqual((w["wazne"], w["status"]), (1, "nowa"))
        self.assertIn("dziękuję za informację", w["szkic"])

    def test_old_mail_from_employer_domain_is_ignored(self):
        aid = self.sent_app()
        old = self.mail(32, "Rekrutacja: dziękujemy za zgłoszenie, niestety stanowisko nieaktualne, nie będziemy kontynuować.",
                        od="administracja@testowe.pl", reply_to="")
        old["data"] = "2026-11-01T09:00:00+01:00"
        self.assertEqual(self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: [old]), 0)
        self.assertEqual(self.row(aid)["status"], "wyslana")

    def test_draft_reply_is_sent_once(self):
        self.sent_app()
        box = [self.mail(33, "Prosimy o informację, kiedy może Pani rozpocząć pracę? Rekrutacja na stanowisko.")]
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"rodzaj": "pytanie", "streszczenie": "Pytają o termin.", "pytania": [],
                                                                      "odpowiedz": "Dzień dobry, mogę zacząć po miesięcznym okresie wypowiedzenia.", "brakuje": []})):
            self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box)
        with self.R.db(self.ctx) as c:
            wid = c.execute("SELECT id FROM wiadomosci").fetchone()["id"]
        self.A.send_draft(self.ctx, wid, "Dzień dobry, mogę zacząć po miesięcznym okresie wypowiedzenia.", send=self.fake_send)
        with self.assertRaises(RuntimeError):
            self.A.send_draft(self.ctx, wid, "Dzień dobry, drugi raz.", send=self.fake_send)

    def approved(self):
        self.ready()
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zatwierdzona")
        return aid

    def test_send_errors_are_classified(self):
        P = importlib.import_module(self.mod.__name__ + ".poczta")
        aid = self.approved()

        def not_sent(*a, **k):
            raise P.NotSent("sieć")
        self.assertIsNone(self.P.send_one(self.ctx, send=not_sent))
        self.assertEqual(self.row(aid)["status"], "zatwierdzona")             # wraca do kolejki
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "nastepna_wysylka", 0)

        def unsure(*a, **k):
            raise P.Uncertain("przerwane")
        self.assertIsNone(self.P.send_one(self.ctx, send=unsure))
        self.assertEqual(self.row(aid)["status"], "blad")
        self.assertIn("Wysłane", self.row(aid)["blad"])

    def test_claimed_application_is_not_sent_twice_after_restart(self):
        aid = self.approved()
        with self.R.db(self.ctx) as c:
            c.execute("UPDATE aplikacje SET status='wysylanie' WHERE id=?", (aid,))
            c.commit()
        self.assertIsNone(self.P.send_one(self.ctx, send=self.fake_send))
        import threading
        stop = threading.Event()
        stop.set()
        self.P.worker(self.ctx, stop)
        self.assertEqual(self.row(aid)["status"], "blad")
        self.assertEqual(self.sent, [])

    def test_model_silence_in_truth_check_blocks_autopilot(self):
        self.ready()
        self.ctx.set_setting("autopilot", "tak")
        aid = self.add(zrodlo="auto")
        real = self.model

        def no_checker(prompt, **kw):
            return None if "kontrolerem prawdy" in prompt else real(prompt, **kw)
        with patch.object(W, "ask", no_checker):
            self.assertEqual(self.P.prepare(self.ctx, aid), "do_sprawdzenia")

    def test_skipped_offer_can_be_retried_and_recruitee_approved(self):
        self.ready()
        aid = self.add(zrodlo="auto", url="https://firma.recruitee.com/o/asystentka", tresc=OFFER.replace("rekrutacja@testowe.pl", "formularz"))
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "Firma", "stanowisko": "Asystentka", "miasto": "Kraków", "ocena": 30})
                          if "Przeczytaj" in prompt else self.model(prompt)):
            self.assertEqual(self.P.prepare(self.ctx, aid), "odrzucona")
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.R.find_duplicate(c, "Firma", "Asystentka", "https://firma.recruitee.com/o/asystentka"), 0)
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        cl.post("/login", data={"haslo": "poprawne123"})
        with cl.session_transaction() as sess:
            sess["csrf"] = "t"
        cl.post(f"/aplikacja/{aid}", data={"csrf": "t", "co": "ponow"})
        self.assertEqual((self.row(aid)["status"], self.row(aid)["zrodlo"]), ("nowa", "oferta"))
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "Firma", "stanowisko": "Asystentka", "miasto": "Kraków", "ocena": 30})
                          if "Przeczytaj" in prompt else self.model(prompt)):
            self.assertEqual(self.P.prepare(self.ctx, aid), "do_zatwierdzenia")      # kanał Recruitee, bez maila
        a = self.row(aid)
        cl.post(f"/aplikacja/{aid}", data={"csrf": "t", "co": "zatwierdz", "firma": a["firma"], "stanowisko": a["stanowisko"], "email": "",
                                           "miasto": a["miasto"], "list": a["list"], "temat": a["temat"], "mail": a["mail"]})
        self.assertEqual(self.row(aid)["status"], "zatwierdzona")

    def test_source_cap_keeps_unseen_offers_and_drops_bad_links(self):
        Z = importlib.import_module(self.mod.__name__ + ".zrodla")
        page = "".join(f'<a href="/oferty/{i}-asystentka">Asystentka biura {i}</a>' for i in range(1, 8))
        with self.R.db(self.ctx) as c:
            Z.seed(c, self.ctx)
            c.execute("DELETE FROM zrodla")
            c.execute("INSERT INTO zrodla(typ,url,nazwa) VALUES('strona','https://firma.pl/kariera','Firma')")
            c.commit()
        with patch.object(Z, "_get", lambda url, **k: (page, url)):
            self.assertEqual(Z.discover(self.ctx, max_new=3), 3)
            self.assertEqual(Z.discover(self.ctx, max_new=10), 4)
        self.assertEqual(self.R.http_url("javascript:alert(1)"), "")

    def test_forced_report_keeps_evening_report(self):
        self.ready()
        self.assertTrue(self.P.evening_report(self.ctx, send=self.fake_send, force=True))
        with patch.object(W, "now", lambda: TUE_10.replace(hour=20, minute=5)):
            self.assertTrue(self.P.evening_report(self.ctx, send=self.fake_send))


class Update281(RekrutacjaBase):
    """2.8.1: klauzula RODO, sprzedaż i obsługa klienta, szukanie maila w sieci, agregatory, import wiedzy."""

    def mod_(self, name):
        return importlib.import_module(self.mod.__name__ + "." + name)

    def test_consent_clause_is_validated(self):
        info = "Jeśli masz pytania dotyczące przetwarzania Twoich danych, skontaktuj się z inspektorem: iod@firma.pl. Administratorem danych jest Firma."
        self.assertFalse(self.R.is_consent(info))
        good = "Wyrażam zgodę na przetwarzanie moich danych osobowych przez Firma Sp. z o.o. w celu prowadzenia rekrutacji na stanowisko Asystentka."
        self.assertTrue(self.R.is_consent(good))
        self.assertEqual(self.R.consent_clause("Firma", good), good)
        default = self.R.consent_clause("Biuro Testowe", info)
        self.assertIn("przez Biuro Testowe", default)
        self.assertIn("przyszłych procesów rekrutacyjnych", default)
        import fitz
        self.ready()
        aid = self.add()
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "Testowe", "stanowisko": "Asystentka", "miasto": "Kraków",
                                                                      "email": "rekrutacja@testowe.pl", "rodo": info, "ocena": 80})
                          if "Przeczytaj" in prompt else self.model(prompt)):
            self.P.prepare(self.ctx, aid)
        a = self.row(aid)
        text = re.sub(r"\s+", " ", fitz.open(self.P.app_dir(self.ctx, aid) / a["cv_plik"])[0].get_text())
        self.assertNotIn("skontaktuj się z inspektorem", text)
        self.assertIn("przyszłych procesów rekrutacyjnych", text)

    def test_sales_and_customer_service_are_welcome(self):
        Z = self.mod_("zrodla")
        self.assertTrue(Z.looks_relevant(self.facts, "Doradca klienta w salonie"))
        self.assertTrue(Z.looks_relevant(self.facts, "Specjalistka ds. sprzedaży"))
        O = self.mod_("oferty")
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "X", "stanowisko": "Sprzedawca", "sprzedaz": True, "ocena": 70})):
            out = O.analyze(self.ctx, self.facts, "sprzedaż sprzedaż sprzedaż obsługa klienta, cele sprzedażowe, prowizja")
        self.assertEqual(out["ostrzezenia"], [])
        f = self.R.load_facts(self.ctx)
        f["kryteria"]["nie_chce"] = list(self.R.AVOID)
        self.assertFalse(Z.looks_relevant(f, "Sprzedawca w sklepie"))

    def test_migration_unblocks_sales_and_fixes_old_clauses(self):
        self.ready()
        f = self.R.load_facts(self.ctx)
        f["kryteria"]["nie_chce"] = list(self.R.AVOID) + ["praca w nocy"]
        self.R.save_facts(self.ctx, f)
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        with self.R.db(self.ctx) as c:
            c.execute("UPDATE aplikacje SET rodo='Informacja o administratorze danych osobowych — kontakt iod@x.pl, dane przetwarzamy w celu…' WHERE id=?", (aid,))
            c.commit()
        self.P.migrate_281(self.ctx)
        crit = self.R.load_facts(self.ctx)["kryteria"]
        self.assertEqual(crit["nie_chce"], ["praca w nocy"])
        self.assertIn("sprzedaż i doradztwo", crit["chce"])
        self.assertEqual(self.row(aid)["rodo"], "")

    def site(self, pages):
        """Udawany internet: adres → html."""
        def get(url, **k):
            for key, page in pages.items():
                if url.rstrip("/") == key.rstrip("/"):
                    return page, url
            raise RuntimeError("404")
        return get

    def test_company_email_found_on_its_website(self):
        K = self.mod_("kontakty")
        Z = self.mod_("zrodla")
        importlib.reload(K) if False else None
        real_find = K.__dict__.get("find_email")
        pages = {"https://testowe.pl": '<html><title>Biuro Testowe</title><body>Biuro Testowe — usługi. <a href="/kontakt">Kontakt</a></body></html>',
                 "https://testowe.pl/kontakt": "Biuro Testowe, Kraków. Napisz: iod@testowe.pl, biuro@testowe.pl, rekrutacja@testowe.pl, jan@gmail.com"}
        self.extra[-1].stop()                                             # w tym teście prawdziwa funkcja, udawane strony
        try:
            find = importlib.import_module(self.mod.__name__ + ".kontakty").find_email
            with patch.object(Z, "_get", lambda url, **k: self.site(pages)(url)):
                got = find(self.ctx, {"firma": "Biuro Testowe Sp. z o.o.", "url": "https://www.pracuj.pl/praca/1"})
                self.assertEqual((got["email"], got["sposob"]), ("rekrutacja@testowe.pl", "domysl"))
                self.assertEqual(find(self.ctx, {"firma": "Zupełnie Inna Firma", "url": ""}), {})
            other = {"https://kowalski.pl": "<html>Sklep z rowerami Kowalski</html>"}
            with patch.object(Z, "_get", lambda url, **k: self.site(other)(url)):
                self.assertEqual(find(self.ctx, {"firma": "Kancelaria Adwokacka Jan Kowalski", "url": ""}), {})
        finally:
            self.extra[-1].start()

    def test_prepare_uses_web_email_and_mentions_the_offer(self):
        self.ready()
        self.ctx.set_setting("autopilot", "tak")
        aid = self.add(zrodlo="auto", url="https://kariera.firma.pl/oferta/1", tresc=OFFER.replace("rekrutacja@testowe.pl", "formularz na stronie"))
        K = self.mod_("kontakty")
        with patch.object(K, "find_email", lambda *a, **k: {"email": "biuro@testowe.pl", "strona": "https://testowe.pl/kontakt", "sposob": "domysl"}), \
             patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "Biuro Testowe", "stanowisko": "Asystentka", "miasto": "Kraków", "ocena": 90})
                          if "Przeczytaj" in prompt else (None if "Piszesz w imieniu" in prompt else self.model(prompt))):
            status = self.P.prepare(self.ctx, aid)
        a = self.row(aid)
        self.assertEqual(status, "do_zatwierdzenia")                      # adres zgadnięty → bez autopilota
        self.assertEqual(a["email"], "biuro@testowe.pl")
        self.assertIn("w nawiązaniu do ogłoszenia Państwa firmy na stanowisko Asystentka (https://kariera.firma.pl/oferta/1)", a["mail"])
        self.assertIn("sprawdź, czy to ta firma", a["uwagi"])

    def test_aggregators(self):
        Z = self.mod_("zrodla")

        class Resp:
            status_code = 200

            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data

            def raise_for_status(self):
                pass
        calls = []
        adz = {"results": [{"title": "Asystentka biura", "company": {"display_name": "ABC"}, "location": {"display_name": "Kraków, małopolskie"},
                            "description": "Obsługa biura i dokumentacji", "redirect_url": "https://www.adzuna.pl/land/ad/1"}]}
        got = Z.adzuna(self.ctx, "id", "key", get=lambda url, params=None, **k: calls.append(params) or Resp(adz))
        self.assertEqual((got[0]["firma"], got[0]["url"]), ("ABC", "https://www.adzuna.pl/land/ad/1"))
        self.assertEqual((calls[0]["where"], calls[0]["distance"]), ("Kraków", 50))
        job = {"jobs": [{"title": "Recepcjonistka", "company": "Hotel X", "location": "Kraków", "snippet": "recepcja", "link": "https://jooble.org/desc/1"}]}
        got = Z.jooble(self.ctx, "k", post=lambda url, json=None, **k: Resp(job))
        self.assertEqual(got[0]["tytul"], "Recepcjonistka")
        with self.R.db(self.ctx) as c:
            Z.seed(c, self.ctx)
            c.execute("DELETE FROM zrodla WHERE typ NOT IN ('adzuna','jooble')")
            c.commit()
        Z.discover(self.ctx)
        with self.R.db(self.ctx) as c:
            self.assertIn("czeka na klucz", c.execute("SELECT wynik FROM zrodla WHERE typ='adzuna'").fetchone()["wynik"])

    def test_knowledge_import_from_chatgpt_export(self):
        Wd = self.mod_("wiedza")
        export = [{"title": "Pomoc z CV", "mapping": {
            "a": {"message": {"author": {"role": "user"}, "create_time": 1, "content": {"parts": ["Pomóż mi z CV. Pracowałam w ZZOZ, robiłam grafiki zmian dla 20 osób."]}}},
            "b": {"message": {"author": {"role": "assistant"}, "create_time": 2, "content": {"parts": ["Napiszę, że znasz SAP i masz certyfikat PMP."]}}}}},
            {"title": "Przepis na sernik", "mapping": {"c": {"message": {"author": {"role": "user"}, "content": {"parts": ["Jak zrobić sernik?"]}}}}}]
        n, msg = Wd.start(self.ctx, upload=json.dumps(export).encode(), filename="conversations.json")
        self.assertEqual((n, msg), (1, ""))
        job = Wd.load(self.ctx)
        self.assertIn("grafiki zmian", job["kawalki"][0])
        self.assertNotIn("SAP", job["kawalki"][0])                        # odpowiedzi ChatGPT pomijane
        self.assertNotIn("sernik", job["kawalki"][0])
        found = {"profil": ["Układałam grafiki pracy dla zespołu 20 osób."], "punkty": [{"stanowisko": "Sekretarka medyczna", "firma": "ZZOZ", "tekst": "układanie grafików zmian dla 20 osób"}],
                 "narzedzia": [{"nazwa": "Word", "poziom": "dobry"}], "niepewne": ["zna SAP"]}
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps(found)):
            Wd.work(self.ctx)
            Wd.work(self.ctx)
        job = Wd.load(self.ctx)
        self.assertEqual(job["status"], "do przejrzenia")
        ids = {c["id"] for c in job["kandydaci"] if c["rodzaj"] != "profil"}
        self.assertEqual(Wd.apply(self.ctx, ids | {999}), 2)
        f = self.R.load_facts(self.ctx)
        pts = [p["tekst"] for p in f["doswiadczenie"][0]["punkty"]]
        self.assertIn("układanie grafików zmian dla 20 osób", pts)
        self.assertIn("Word", [t["nazwa"] for t in f["narzedzia"]])
        self.assertNotIn("Układałam grafiki pracy dla zespołu 20 osób.", [p["tekst"] for p in f["profil"]])
        self.assertIsNone(Wd.load(self.ctx))


class Corrections281(RekrutacjaBase):
    def test_optional_positions_only_when_picked(self):
        f = self.R.load_facts(self.ctx)
        jobs = [dict(j, punkty=[p["tekst"] for p in j["punkty"]]) for j in f["doswiadczenie"]]
        jobs.append({"stanowisko": "Asystent nauczyciela", "firma": "Przedszkole", "od": "02.2021", "do": "04.2021", "opcjonalne": True, "punkty": ["praca z dziećmi"]})
        f["doswiadczenie"] = jobs
        self.R.save_facts(self.ctx, f)
        f = self.R.load_facts(self.ctx)
        self.assertNotIn("d3", self.D.default_selection(f)["kolejnosc"])
        self.assertNotIn("d3", self.D.clean_selection(f, {"kolejnosc": ["d1"]})["kolejnosc"])
        sel = self.D.clean_selection(f, {"kolejnosc": ["d3", "d1"]})
        self.assertEqual(sel["kolejnosc"], ["d2", "d1", "d3"])            # w CV zawsze od najnowszego
        self.assertEqual(sel["ranking"][:2], ["d3", "d1"])                # a ważność według oferty

    def test_less_relevant_positions_are_shorter_and_cv_has_only_city(self):
        f = self.R.load_facts(self.ctx)
        jobs = [dict(j, punkty=[p["tekst"] for p in j["punkty"]]) for j in f["doswiadczenie"]]
        for extra in range(3):
            jobs.append({"stanowisko": f"Stanowisko {extra}", "firma": "X", "od": f"0{extra + 1}.2019", "do": f"0{extra + 2}.2019",
                         "punkty": ["a", "b", "c", "d"]})
        f["doswiadczenie"] = jobs
        self.R.save_facts(self.ctx, f)
        f = self.R.load_facts(self.ctx)
        sel = self.D.clean_selection(f, {"kolejnosc": ["d1", "d2", "d3"]})
        self.assertEqual(len(sel["punkty"]["d5"]), 3)                     # zawsze 3 punkty przy stanowisku
        self.assertEqual(len(self.D.default_selection(f)["punkty"]["d5"]), 3)
        self.mod.apply_patch(self.ctx, {"osoba": {"adres": "", "miasto": "Kraków"}, "warunki": {"dojazd_km": 20}, "ustawienia": {"bez_prowizji": "tak"}})
        import fitz
        out = self.ctx.folder() / "cv3.pdf"
        self.D.render_cv(self.R.load_facts(self.ctx), None, out)
        text = fitz.open(out)[0].get_text()
        self.assertNotIn("Próbna", text)
        self.assertIn("Kraków", text)
        self.assertTrue(self.ctx.settings()["bez_prowizji"])
        self.assertTrue(self.R.in_area("Wieliczka", 20) and not self.R.in_area("Bochnia", 20) and self.R.in_area("Bochnia", 50))

    def test_patch_from_chatgpt_summary(self):
        patch_ = {"punkty": [{"firma": "ZZOZ", "tekst": "umawianie badań i organizowanie transportu medycznego"}],
                  "kursy": ["Interwencja kryzysowa - CRP (2022)", "Szkolenie z LinkedIna"], "kursy_zmien": [{"zawiera": "Interwencja kryzysowa", "na": "Interwencja kryzysowa - CRP (2026)"}],
                  "kursy_usun": ["LinkedIn"], "narzedzia": [{"nazwa": "Excel", "poziom": "bardzo dobry"}], "narzedzia_usun": ["Canva"],
                  "nie_chce": ["praca w social mediach"], "historia": [{"firma": "homfi", "stanowisko": "Asystent Oddziału"}]}
        self.mod.apply_patch(self.ctx, patch_)
        self.mod.apply_patch(self.ctx, patch_)                          # drugi raz niczego nie dubluje
        f = self.R.load_facts(self.ctx)
        kursy = [k["tekst"] for k in f["kursy"]]
        self.assertIn("Interwencja kryzysowa - CRP (2026)", kursy)
        self.assertFalse(any("LinkedIn" in k or "(2022)" in k and "Interwencja" in k for k in kursy))
        self.assertEqual([(t["nazwa"], t["poziom"]) for t in f["narzedzia"]], [("Excel", "bardzo dobry")])
        self.assertEqual([p["tekst"] for p in f["doswiadczenie"][0]["punkty"]].count("umawianie badań i organizowanie transportu medycznego"), 1)
        Z = importlib.import_module(self.mod.__name__ + ".zrodla")
        self.assertFalse(Z.looks_relevant(f, "Social Media Manager"))
        self.assertTrue(Z.looks_relevant(f, "Asystentka biura"))
        with self.R.db(self.ctx) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM aplikacje WHERE firma='homfi'").fetchone()[0], 1)
            self.assertTrue(self.R.find_duplicate(c, "homfi", "Asystent Oddziału"))

    def test_pay_never_imported(self):
        Wd = importlib.import_module(self.mod.__name__ + ".wiedza")
        items = Wd._items({"profil": ["Zarabiałam 5000 zł netto.", "Mam doświadczenie w administracji."],
                           "punkty": [{"firma": "X", "tekst": "stawka 31 zł/h"}], "odpowiedzi": [{"pytanie": "Oczekiwania finansowe", "odpowiedz": "7000 netto"},
                                                                                              {"pytanie": "Dostępność", "odpowiedz": "od zaraz"}]})
        texts = " ".join(i["tekst"] for i in items)
        self.assertNotIn("5000", texts)
        self.assertNotIn("31 zł", texts)
        self.assertNotIn("7000", texts)
        self.assertIn("Dostępność: od zaraz", texts)




class Improvements282(RekrutacjaBase):
    def jobs_with(self, n=5):
        f = self.R.load_facts(self.ctx)
        jobs = [dict(j, punkty=[p["tekst"] for p in j["punkty"]] + [f"dodatkowy punkt {i}" for i in range(n)]) for j in f["doswiadczenie"]]
        f["doswiadczenie"] = jobs
        f["kursy"] = ["Kurs A (2022)", "Kurs B (2026)", "Kurs bez roku", "Kurs C (2024)"]
        self.R.save_facts(self.ctx, f)
        return self.R.load_facts(self.ctx)

    def pdf_text(self, f, sel):
        import fitz
        out = self.ctx.folder() / "cv_test.pdf"
        self.D.render_cv(f, sel, out)
        doc = fitz.open(out)
        self.assertEqual(len(doc), 1)
        return doc[0].get_text()

    def test_three_points_in_model_order_and_courses_newest_first(self):
        f = self.jobs_with()
        d1 = [p["id"] for p in f["doswiadczenie"][0]["punkty"]]
        sel = self.D.clean_selection(f, {"kolejnosc": ["d1"], "punkty": {"d1": [d1[4], d1[0]]}})
        self.assertEqual(sel["punkty"]["d1"], [d1[4], d1[0], d1[1]])
        self.assertTrue(all(len(v) <= 3 for v in sel["punkty"].values()))
        text = self.pdf_text(f, sel)
        pos = [text.find(x) for x in ("Kurs B", "Kurs C", "Kurs A", "Kurs bez roku")]
        self.assertTrue(all(p >= 0 for p in pos) and pos == sorted(pos), pos)

    def test_tailored_profile_only_from_facts(self):
        a = {"stanowisko": "Asystentka biura", "firma": "X", "tresc": OFFER, "zrodlo": "oferta"}
        self.model.profile = ("Specjalistka ds. administracji z doświadczeniem w prowadzeniu i archiwizacji dokumentacji. "
                              "Koordynuje terminy, przygotowuje raporty i dba o porządek w obiegu dokumentów.")
        self.assertTrue(self.D.tailored_profile(self.ctx, self.facts, a).startswith("Specjalistka"))
        self.model.profile = "Specjalistka z 12-letnim doświadczeniem w SAP, która zarządzała zespołem 40 osób w dziale administracji firmy."
        self.assertEqual(self.D.tailored_profile(self.ctx, self.facts, a), "")      # liczby i narzędzie spoza faktów — odrzucone
        self.ready()
        self.model.profile = ("Specjalistka ds. administracji z doświadczeniem w prowadzeniu i archiwizacji dokumentacji. "
                              "Koordynuje terminy i przygotowuje raporty.")
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        sel = json.loads(self.row(aid)["wybor"])
        self.assertEqual((sel["profil_zrodlo"], sel["profil_model"][:12]), ("model", "Specjalistka"))
        self.assertIn("Koordynuje terminy", self.pdf_text(self.R.load_facts(self.ctx), sel))

    def test_cv_edit_own_points_hide_and_restore(self):
        f = self.jobs_with(2)
        sel = self.D.clean_selection(f, {"kolejnosc": ["d1", "d2"], "profil_tekst": "Opis od Sebastiana o dokumentacji.", "profil_zrodlo": "model"})
        new = self.D.apply_cv_edit(f, sel, "Mój własny opis do tej oferty.", {"d1": ["Mój punkt jeden", "", "Mój punkt dwa"]}, ["d1"])
        prof, pts = self.D.cv_content(f, new)
        self.assertEqual(prof, "Mój własny opis do tej oferty.")
        self.assertEqual(pts["d1"], ["Mój punkt jeden", "Mój punkt dwa"])
        self.assertEqual(new["kolejnosc"], ["d1"])
        text = self.pdf_text(f, new)
        self.assertIn("Mój punkt jeden", text)
        self.assertNotIn(f["doswiadczenie"][1]["stanowisko"], text)
        back = self.D.reset_cv_edit(f, new)
        prof, pts = self.D.cv_content(f, back)
        self.assertEqual(prof, "Opis od Sebastiana o dokumentacji.")
        self.assertNotIn("Mój punkt jeden", pts["d1"])
        self.assertIn("d2", back["kolejnosc"])
        unchanged = self.D.apply_cv_edit(f, sel, prof, pts, back["kolejnosc"])         # bez zmian = bez „własnej wersji”
        self.assertNotIn("wlasne_punkty", unchanged)
        with self.assertRaises(ValueError):
            self.D.apply_cv_edit(f, sel, "", {}, [])

    def test_patch_replaces_point_with_concrete_one(self):
        f = self.R.load_facts(self.ctx)
        job = f["doswiadczenie"][0]
        first = job["punkty"][0]["tekst"]
        rule = {"firma": job["firma"], "zawiera": first[:12], "na": "ok. 80 dokumentów miesięcznie"}
        self.mod.apply_patch(self.ctx, {"punkty_zmien": [rule]})
        self.mod.apply_patch(self.ctx, {"punkty_zmien": [rule]})
        texts = [p["tekst"] for p in self.R.load_facts(self.ctx)["doswiadczenie"][0]["punkty"]]
        self.assertEqual(texts.count("ok. 80 dokumentów miesięcznie"), 1)
        self.assertNotIn(first, texts)

    def test_edit_cv_page(self):
        self.ready()
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zatwierdzona")
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        cl.post("/login", data={"haslo": "poprawne123"})
        with cl.session_transaction() as sess:
            sess["csrf"] = "t"
        self.assertIn("Edytuj CV".encode(), cl.get(f"/aplikacja/{aid}").data)
        page = cl.get(f"/aplikacja/{aid}/cv").data.decode()
        self.assertIn("Profil zawodowy", page)
        f = self.R.load_facts(self.ctx)
        form = {"csrf": "t", "co": "zapisz", "profil": "Opis poprawiony przez Agę.", "pokaz": ["d1", "d2"], "p_d1": ["Punkt Agi", "", ""]}
        self.assertEqual(cl.post(f"/aplikacja/{aid}/cv", data=form).status_code, 302)
        a = self.row(aid)
        self.assertEqual(a["status"], "do_zatwierdzenia")                       # zatwierdzona wraca do sprawdzenia
        sel = json.loads(a["wybor"])
        self.assertEqual((sel["profil_tekst"], sel["wlasne_punkty"]["d1"]), ("Opis poprawiony przez Agę.", ["Punkt Agi"]))
        self.assertTrue((self.P.app_dir(self.ctx, aid) / a["cv_plik"]).exists())
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "wyslana")
        cl.post(f"/aplikacja/{aid}/cv", data=dict(form, profil="Po wysłaniu."))
        self.assertEqual(json.loads(self.row(aid)["wybor"])["profil_tekst"], "Opis poprawiony przez Agę.")   # wysłane się nie zmienia



class LettersAndOffers282(RekrutacjaBase):
    CLAUSE = ("Wyrażam zgodę na przetwarzanie moich danych osobowych przez 5 Wojskowy Szpital Kliniczny z siedzibą ul. Wrocławska 1-3, "
              "30-901 Kraków, w zakresie objętym przekazanym przeze mnie CV dla celów przeprowadzenia procesu rekrutacyjnego na "
              "stanowisko______________________. Wyrażam zgodę na przetwarzanie moich danych osobowych przez 5 Wojskowy Szpital "
              "Kliniczny z siedzibą ul. Wrocławska 1-3, 30-901 Kraków, w zakresie objętym przekazanym przeze mnie CV dla celów "
              "przeprowadzenia przyszłych procesów rekrutacyjnych.")

    def test_clause_gets_job_title_and_one_sentence(self):
        out = self.R.consent_clause("Szpital", self.CLAUSE, "Referent")
        self.assertIn("na stanowisko Referent, a także dla celów przyszłych procesów rekrutacyjnych.", out)
        self.assertEqual(out.count("Wyrażam zgodę"), 1)
        self.assertNotIn("___", out)
        bare = self.R.consent_clause("Szpital", self.CLAUSE, "")
        self.assertNotIn("stanowisko", bare)
        self.assertNotIn("na,", bare)
        self.assertEqual(self.R.format_phone("669579733"), "+48 669 579 733")

    def test_language_rules(self):
        bad = ("Szanowni Państwo,\n\ndostaję się aplikacja na stanowisko. Potrafiłbym szybko przejść przez procesy bez zbędnej nauki podstaw. "
               "Jestem gotowy do pracy.")
        issues = " ".join(self.D.language_issues(bad))
        for word in ("potrafiłbym", "jestem gotowy", "bez zbędnej nauki", "dostaję się"):
            self.assertIn(word, issues.lower())
        self.assertEqual(self.D.language_issues("Kierowałam działem obsługi i pracowałam z zespołem. Jestem gotowa do rozmowy."), [])

    def test_masculine_letter_is_retried_then_replaced(self):
        a = {"stanowisko": "Asystentka biura", "firma": "Firma", "tresc": OFFER, "zrodlo": "oferta", "url": ""}
        self.model.letter = ("Z zainteresowaniem przeczytałem ogłoszenie. " * 3 + "Pracowałem z dokumentacją i byłem odpowiedzialny za terminy. " * 6)
        letter, mail, by_model = self.D.compose(self.ctx, self.facts, a)
        self.assertFalse(by_model)
        self.assertEqual(self.D.language_issues(letter), [])
        self.assertTrue(letter.startswith("Szanowni Państwo,"))
        self.assertIn("na stanowisko Asystentka biura", mail)
        self.assertIn("list motywacyjny", mail)
        self.assertNotIn("przewodni", letter + mail)

    def test_good_letter_kept_and_mail_from_facts(self):
        self.ready()
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        a = self.row(aid)
        self.assertTrue(a["list"].startswith("Szanowni Państwo,"))
        self.assertIn("Z poważaniem", a["list"])
        self.assertIn("Do moich zadań należały tam m.in. ", a["mail"])
        self.assertIn("List_motywacyjny", a["list_plik"])
        import fitz
        text = fitz.open(self.P.app_dir(self.ctx, aid) / a["list_plik"])[0].get_text()
        for part in ("Klauzula RODO", "Z poważaniem", "Dotyczy:", a["firma"]):
            self.assertIn(part, text)
        self.assertLess(text.find(self.facts["osoba"]["email"]), text.find("Szanowni"))      # dane nadawczyni na górze

    def test_offer_details_and_match(self):
        O = self.O
        self.assertEqual(O.salary("Wynagrodzenie 6 500 - 7 500 zł brutto miesięcznie"), "6 500 - 7 500 zł brutto")
        orig = self.model

        def model(prompt, **kw):
            if "Przeczytaj ogłoszenie" in prompt:
                return json.dumps({"firma": "Biuro Testowe", "stanowisko": "Asystentka", "miasto": "Wieliczka", "email": "rekrutacja@testowe.pl",
                                   "ocena": 80, "uzasadnienie": "ok", "adres": "ul. Długa 1, Wieliczka", "wynagrodzenie": "9999 zł",
                                   "wymagania": ["obsługa Excela", "prawo jazdy kat. C"], "obowiazki": ["obieg dokumentów"], "oferujemy": ["umowa o pracę"]})
            if "Porównaj WYMAGANIA" in prompt:
                return json.dumps({"dopasowanie": [{"nr": 1, "ocena": "mam", "dlaczego": "Excel w narzędziach"},
                                                   {"nr": 2, "ocena": "brak", "dlaczego": "tylko kat. B"}, {"nr": 9, "ocena": "mam"}]})
            return orig(prompt, **kw)
        with patch.object(W, "ask", model):
            self.ready()
            aid = self.add(tresc=OFFER + " Wymagane prawo jazdy kat. C. Oferujemy 6000-7000 zł brutto.")
            self.P.prepare(self.ctx, aid)
        info = json.loads(self.row(aid)["analiza"])
        self.assertEqual(info["wynagrodzenie"], "6000-7000 zł brutto")          # kwoty spoza ogłoszenia model nie wstawi
        self.assertEqual([x["ocena"] for x in info["dopasowanie"]], ["mam", "brak"])
        self.assertEqual(info["obowiazki"], ["obieg dokumentów"])
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        cl.post("/login", data={"haslo": "poprawne123"})
        page = cl.get(f"/aplikacja/{aid}").data.decode()
        for part in ("Pobierz CV", "Pobierz list motywacyjny", "6000-7000 zł brutto", "ok. 15 km od Krakowa", "prawo jazdy kat. C", "brakuje: 1", "Sprawdź dojazd"):
            self.assertIn(part, page)

    def test_migration_prepares_waiting_again(self):
        self.ready()
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        self.assertEqual(self.row(aid)["status"], "do_zatwierdzenia")
        self.P.migrate_282(self.ctx)
        self.assertEqual(self.row(aid)["status"], "nowa")
        self.P.migrate_282(self.ctx)                                             # tylko raz
        self.P.prepare(self.ctx, aid)
        self.assertEqual(self.row(aid)["status"], "do_zatwierdzenia")



class KeychainIsolation283(RekrutacjaBase):
    def test_tests_never_touch_the_real_keychain(self):
        with patch.object(DH.subprocess, "run", side_effect=AssertionError("security wywołane w teście")) as run, \
                patch.object(DH.sys, "platform", "darwin"):
            self.R.set_secret(self.ctx, "aga", "x" * 16)
            self.assertEqual(self.R.secret(self.ctx, "aga"), "x" * 16)          # zapis do pliku próbnego w folderze testu
            self.assertIsNone(self.ctx.secret("jooble"))
            run.assert_not_called()



class RealMail283(RekrutacjaBase):
    """Przypadki z prawdziwej skrzynki Agi (12.11.2026)."""
    BAD_LETTER = ("Szanowni Państwo,\n\nDroga Agnieszko Kwiatkowska,\n\nSzukamy osoby, która wesprze codzienne funkcjonowanie biura oraz działu. "
                  "Twoje doświadczenie w administracji i prowadzeniu dokumentacji będzie nieocenionym atutem.\n\nW trakcie swojej kariery zawodowej "
                  "przygotowywałaś analizy i raporty, pracowałaś z danymi poufnymi oraz koordynowałaś zadania. Twoja skrupulatność pomoże Ci "
                  "sprawnie wykonywać obowiązki biurowe.\n\nWspierałaś również pracowników w rozliczeniach czasu pracy i prowadziłaś ewidencje.")

    def kind(self, model_kind, **m):
        msg = dict({"od": "", "od_nazwa": "", "temat": "", "tresc": "", "auto": False}, **m)
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"rodzaj": model_kind, "streszczenie": "x", "termin": "", "pytania": []})):
            return self.A.classify(self.ctx, msg, {"firma": "Empik", "stanowisko": "Doradca"})

    def setUp(self):
        super().setUp()
        self.A = importlib.import_module(self.mod.__name__ + ".odpowiedzi")

    def test_letter_written_to_aga_is_never_used(self):
        names = ("Agnieszka", "Kwiatkowska")
        self.assertTrue(any("zwraca się do kandydatki" in x for x in self.D.language_issues(self.BAD_LETTER, names)))
        self.model.letter = self.BAD_LETTER
        a = {"stanowisko": "Pracownik ds. Administracji", "firma": "Solid MCG", "tresc": OFFER, "zrodlo": "oferta", "url": ""}
        letter, mail, by_model = self.D.compose(self.ctx, self.facts, a)
        self.assertFalse(by_model)
        for bad in ("Droga", "Szukamy", "Twoje", "przygotowywałaś"):
            self.assertNotIn(bad, letter)
        f = self.facts
        self.assertEqual(self.D.language_issues(letter, (f["osoba"]["imie"], f["osoba"]["nazwisko"])), [])

    def test_erecruiter_and_portal_mails(self):
        own = self.kind("zaproszenie", od="system@konto.erecruiter.pl", od_nazwa="Konto Kandydata", temat="Czy to Twoja aplikacja?",
                        tresc="Czy to Twoja aplikacja? Zauważyliśmy nową aplikację powiązaną z Twoim adresem e-mail. Zdecyduj co mamy z nią zrobić. Teams")
        self.assertEqual(own["rodzaj"], "do_potwierdzenia")
        got = self.kind("zaproszenie", od="mail@stage.erecruiter.pl", od_nazwa="eRecruiter", temat="Dziękujemy",
                        tresc="Cześć! Cieszymy się, że chcesz rozwijać swoją karierę właśnie z nami. Twoje zgłoszenie właśnie trafiło do naszego Zespołu "
                              "Rekrutacji. Jeśli Twoje doświadczenie będzie tym, czego szukamy, odezwiemy się do Ciebie telefonicznie. "
                              "*Wiadomość wygenerowana automatycznie, prosimy na nią nie odpowiadać.")
        self.assertEqual(got["rodzaj"], "potwierdzenie")
        sel = self.kind("odmowa", od="mail@stage.erecruiter.pl", od_nazwa="eRecruiter", temat="Dziękujemy za aplikację",
                        tresc="Dziękujemy za złożenie aplikacji i wypełnienie kwestionariusza. Skontaktujemy się wyłącznie z wybranymi kandydatami.")
        self.assertEqual(sel["rodzaj"], "potwierdzenie")
        promo = self.kind("inne", od="noreply@pracuj.pl", od_nazwa="Pracuj.pl", temat="Jak wypadasz na tle innych?",
                          tresc="Sprawdź kompetencje innych kandydatów na to samo stanowisko w firmie INSMIND i oceń swoje szanse rekrutacyjne.")
        self.assertEqual(promo["rodzaj"], "reklama")
        real = self.kind("inne", od="noreply@erecruiter.pl", temat="Rozmowa", tresc="Zapraszamy Panią na rozmowę kwalifikacyjną 20.11 o godz. 10:00 w naszym biurze.")
        self.assertEqual(real["rodzaj"], "zaproszenie")
        no = self.kind("odmowa", od="hr@firma.pl", tresc="Dziękujemy za udział. Niestety zdecydowaliśmy się na innego kandydata.")
        self.assertEqual((no["rodzaj"], no["pewne"]), ("odmowa", True))

    def test_mail_text_and_buttons(self):
        P = importlib.import_module(self.mod.__name__ + ".poczta")
        import email, email.policy
        raw = ("From: Konto Kandydata <system@konto.erecruiter.pl>\nSubject: Czy to Twoja aplikacja?\nMIME-Version: 1.0\n"
               "Content-Type: text/html; charset=utf-8\n\n<p>Czy to Twoja aplikacja?</p><p>&nbsp;</p><p>&nbsp;</p>"
               '<a href="https://konto.erecruiter.pl/potwierdz/abc">Tak, to moja aplikacja</a> <a href="https://erecruiter.pl/polityka">Polityka prywatności</a>')
        msg = email.message_from_string(raw, policy=email.policy.default)
        self.assertNotIn("&nbsp;", P._text(msg))
        self.assertEqual(P.links(msg), [{"tekst": "Tak, to moja aplikacja", "url": "https://konto.erecruiter.pl/potwierdz/abc"}])
        self.assertEqual(P.clean_text("a&amp;nbsp;\n\n\n\n b"), "a\n\nb")

    def test_offer_fields_are_not_aga_conditions(self):
        long = "Pasuje do Ciebie, bo to administracja i dokumentacja. " * 8
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"firma": "X", "stanowisko": "Asystentka", "miasto": "Kraków i do 20 km albo zdalnie",
                                                                     "uzasadnienie": long, "ocena": 95})):
            out = self.O.analyze(self.ctx, self.facts, OFFER)
        self.assertEqual(out["miasto"], "")
        self.assertGreater(len(out["uzasadnienie"]), 300)
        self.assertTrue(out["uzasadnienie"].endswith("."))

    def test_migration_fixes_stored_messages(self):
        self.ready()
        aid = self.add(firma="Empik", stanowisko="Doradca", email="hr@empik.com")
        with self.R.db(self.ctx) as c:
            self.R.set_status(c, self.ctx, aid, "zaproszenie", wyslano=self.R.stamp(self.ctx))
            c.execute("UPDATE aplikacje SET podziekowanie='czeka' WHERE id=?", (aid,))
            c.execute("INSERT INTO wiadomosci(uid,od,od_nazwa,temat,tresc,aplikacja_id,rodzaj,wazne,status,streszczenie) VALUES(1,'system@konto.erecruiter.pl',"
                      "'Konto Kandydata','Czy to Twoja aplikacja?','Czy to Twoja aplikacja? Zdecyduj co mamy z nią zrobić.',?,'zaproszenie',1,'nowa','Pracownik firmy Empik informuje')", (aid,))
            c.execute("INSERT INTO wiadomosci(uid,od,od_nazwa,temat,tresc,aplikacja_id,rodzaj,wazne,status) VALUES(2,'mail@stage.erecruiter.pl','eRecruiter','x',"
                      "'Dziękujemy za złożenie aplikacji. Skontaktujemy się wyłącznie z wybranymi kandydatami.',?,'odmowa',0,'zalatwiona')", (aid,))
            c.commit()
        self.P.migrate_283(self.ctx)
        with self.R.db(self.ctx) as c:
            kinds = [r["rodzaj"] for r in c.execute("SELECT rodzaj FROM wiadomosci ORDER BY uid")]
        self.assertEqual(kinds, ["do_potwierdzenia", "potwierdzenie"])
        a = self.row(aid)
        self.assertEqual((a["status"], a["podziekowanie"]), ("wyslana", ""))



class MatchWording285(RekrutacjaBase):
    def test_reasons_are_short_and_addressed_to_aga(self):
        self.assertEqual(self.D.clean_reason("Wymagany pakiet MS Office; w sekcji NARZĘDZIA kandydatka wskazuje 'Word (bardzo dobry)'", "Znajomość MS Office"),
                         "Masz Word (bardzo dobry).")
        self.assertNotIn("FAKTY", self.D.clean_reason("Doświadczenie jest kluczowe; FAKTY potwierdzają: 'Sekretarka medyczna'", "Doświadczenie w administracji"))
        self.assertEqual(self.D.clean_reason("Angielski masz na poziomie zaawansowanym."), "Angielski masz na poziomie zaawansowanym.")

    def test_garbled_requirements_dropped_and_old_analyses_refreshed(self):
        a = {"tresc": "Wymagania: dobra znajomość pakietu MS Office, prawo jazdy kat. B."}
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"dopasowanie": [{"nr": 1, "ocena": "mam", "dlaczego": "Word i Excel znasz bardzo dobrze."}]})):
            got = self.D.match_report(self.ctx, self.facts, a, ["Dobra znajomość pakietu MS Office", "Znajomość języka chińskiego i SAP"])
            self.assertEqual([x["wymaganie"] for x in got], ["Dobra znajomość pakietu MS Office"])
            self.ready()
            aid = self.add()
            with self.R.db(self.ctx) as c:
                c.execute("UPDATE aplikacje SET status='do_zatwierdzenia', analiza=? WHERE id=?",
                          (json.dumps({"wymagania": ["prowadzenie dokumentacji"], "dopasowanie": [{"wymaganie": "x", "ocena": "mam", "dlaczego": "FAKTY: x"}]}), aid))
                c.commit()
            self.assertEqual(self.P.refresh_match(self.ctx), aid)
            self.assertIsNone(self.P.refresh_match(self.ctx))
        info = json.loads(self.row(aid)["analiza"])
        self.assertEqual((info["v"], info["dopasowanie"][0]["dlaczego"]), (2, "Word i Excel znasz bardzo dobrze."))



class Sheep290(RekrutacjaBase):
    def setUp(self):
        super().setUp()
        self.OW = importlib.import_module(self.mod.__name__ + ".owca")
        self.ready()
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "adres_panelu", "http://mac:8790")
        self.ctx.set_setting("tylko_dni_robocze", "tak")

    def at(self, h, m=0, day=12):
        return dt.datetime(2026, 11, day, h, m, tzinfo=s.TZ)

    def waiting(self, n=3, status="do_zatwierdzenia"):
        for i in range(n):
            self.add(firma=f"Firma {i}", stanowisko="Asystentka", status=status)

    def test_day_flow_morning_nudge_bravo(self):
        self.waiting(3)
        with self.R.db(self.ctx) as c:
            self.assertIsNone(self.OW.due(self.ctx, c, self.at(7, 30)))
            self.assertEqual(self.OW.due(self.ctx, c, self.at(7, 50)), "rano")
        self.assertEqual(self.OW.tick(self.ctx, self.fake_send, self.at(7, 50)), "rano")
        mail = self.sent[-1]
        self.assertIn("Jaki cel na dziś", mail["subject"])
        self.assertIn("cid:rano", mail["html"])
        self.assertIn("http://mac:8790/owca/cel/", mail["html"])
        self.assertEqual(mail["images"], ["rano"])
        self.assertIsNone(self.OW.tick(self.ctx, self.fake_send, self.at(8, 30)))            # rano tylko raz
        with self.R.db(self.ctx) as c:
            self.OW.set_goal(c, self.ctx, self.at(9).date(), 2)
        self.assertEqual(self.OW.tick(self.ctx, self.fake_send, self.at(11, 5)), "p1")        # pierwszy tydzień: przypomina
        self.assertIn("0/2", self.sent[-1]["subject"])
        self.assertIn("Przejrzyj 2 aplikacje", self.sent[-1]["html"])
        with self.R.db(self.ctx) as c:
            c.execute("UPDATE aplikacje SET status='wyslana', wyslano=? WHERE id IN (SELECT id FROM aplikacje LIMIT 2)", (self.at(12).isoformat(),))
            c.commit()
        self.assertEqual(self.OW.tick(self.ctx, self.fake_send, self.at(12, 10)), "brawo")
        self.assertIn("2/2", self.sent[-1]["subject"])
        self.assertIsNone(self.OW.tick(self.ctx, self.fake_send, self.at(15, 40)))           # po celu cisza
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.OW.streak(c, self.ctx, self.at(12).date()), 1)
            self.assertIn("2/2 — osiągnięty", self.OW.report_line(self.ctx, c, self.at(12).date()))

    def test_after_first_week_only_when_behind_and_never_on_weekends(self):
        self.waiting(5)
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "owca_start", "2026-10-01")
            self.OW.set_goal(c, self.ctx, self.at(9).date(), 4)
            self.R.meta_set(c, "owca_2026-11-12", json.dumps(["rano"]))
            c.execute("UPDATE aplikacje SET status='wyslana', wyslano=? WHERE id IN (SELECT id FROM aplikacje LIMIT 2)", (self.at(9).isoformat(),))
            c.commit()
            self.assertIsNone(self.OW.due(self.ctx, c, self.at(11, 5)))                   # 2/4 o 11:00 — w tempie
            self.assertEqual(self.OW.due(self.ctx, c, self.at(15, 35)), "p3")              # 2/4 pod koniec okna — w tyle
            self.assertIsNone(self.OW.due(self.ctx, c, self.at(8, 0, day=14)))             # sobota

    def test_goal_link_from_mail(self):
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        with self.R.db(self.ctx) as c:
            tok = self.OW.token(c)
        day = self.ctx.now().date().isoformat()
        r = cl.get(f"/owca/cel/{tok}/{day}/40")
        self.assertIn("Cel na dziś: 40", r.data.decode())
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.OW.goal(c, self.ctx, self.ctx.now().date()), (40, True))
        self.assertEqual(cl.get(f"/owca/cel/zly/{day}/10").status_code, 410)
        self.assertEqual(cl.get("/owca/rano.png").status_code, 200)

    def test_dates_in_invitations(self):
        ref = dt.date(2026, 11, 12)
        P = self.OW.parse_date
        self.assertEqual(P("20.11 o 10:00", ref), dt.date(2026, 11, 20))
        self.assertEqual(P("wtorek, 17 listopada, godz. 9", ref), dt.date(2026, 11, 17))
        self.assertEqual(P("jutro o 12", ref), dt.date(2026, 11, 13))
        self.assertEqual(P("5.01.2027", ref), dt.date(2027, 1, 5))
        self.assertIsNone(P("o 10.00 h", ref))
        self.assertIsNone(P("", ref))

    def test_interview_to_signed_contract(self):
        aid = self.add(firma="Biuro Testowe", stanowisko="Asystentka", status="zaproszenie", wyslano="2026-11-10T09:00:00+01:00",
                       analiza=json.dumps({"dopasowanie": [{"wymaganie": "Excel", "ocena": "mam", "dlaczego": "Excel znasz bardzo dobrze."},
                                                           {"wymaganie": "SAP", "ocena": "brak", "dlaczego": "Nie pracowałaś w SAP."}],
                                           "obowiazki": ["obieg dokumentów"]}))
        with self.R.db(self.ctx) as c:
            c.execute("INSERT INTO wiadomosci(uid,od,temat,tresc,aplikacja_id,rodzaj,wazne,status,termin,data) VALUES(1,'hr@testowe.pl','Rozmowa','Zapraszamy',?,"
                      "'zaproszenie',1,'nowa','20.11 o 10:00','2026-11-12T10:00:00+01:00')", (aid,))
            c.commit()
        self.assertEqual(self.OW.stage_tick(self.ctx, self.fake_send, self.at(10, 30)), f"zaproszenie:1")
        prep = self.sent[-1]["html"]
        for part in ("Zaproszenie na rozmowę", "Excel znasz bardzo dobrze", "SAP", "obieg dokumentów", "Dlaczego chce Pani zmienić pracę"):
            self.assertIn(part, self.sent[-1]["subject"] + prep)
        self.assertIsNone(self.OW.stage_tick(self.ctx, self.fake_send, self.at(11)))
        self.assertEqual(self.OW.stage_tick(self.ctx, self.fake_send, self.at(8, 0, day=20)), "dzien:1")
        self.assertEqual(self.OW.stage_tick(self.ctx, self.fake_send, self.at(10, 0, day=21)), "jak:1")
        self.assertIn("/owca/etap/", self.sent[-1]["html"])
        self.assertIn("dziękuję za rozmowę dotyczącą stanowiska Asystentka", self.sent[-1]["html"])
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        with self.R.db(self.ctx) as c:
            tok = self.OW.token(c)
        cl.get(f"/owca/etap/{tok}/{aid}/oferta")
        self.assertEqual(self.row(aid)["status"], "oferta")
        self.assertEqual(self.OW.stage_tick(self.ctx, self.fake_send, self.at(12, 0, day=21)), f"oferta:{aid}")
        self.assertIn("Dokumenty, które zwykle są potrzebne", self.sent[-1]["html"])
        self.assertIn("Przyjmujesz ofertę", cl.get(f"/owca/etap/{tok}/{aid}/przyjmuje").data.decode())
        self.assertEqual(self.row(aid)["status"], "oferta")                                  # najpierw pytanie, potem decyzja
        cl.get(f"/owca/etap/{tok}/{aid}/przyjmuje?tak=1")
        self.assertEqual(self.row(aid)["status"], "przyjeta")
        st = self.ctx.settings()
        self.assertTrue(st["wstrzymane"] and not st["szukanie"] and not st["spontaniczne"])
        self.assertEqual(self.OW.stage_tick(self.ctx, self.fake_send, self.at(13, 0, day=21)), "koniec")
        self.assertIn("Gratulacje! Nowa praca", self.sent[-1]["subject"])
        self.assertIsNone(self.OW.stage_tick(self.ctx, self.fake_send, self.at(14, 0, day=21)))
        self.assertEqual(cl.get(f"/owca/etap/zly/{aid}/oferta").status_code, 403)



class MoreOffers2100(RekrutacjaBase):
    ALERT_TEXT = ("Nowe oferty pracy dla Ciebie\n\nAsystentka biura\nBiuro Rachunkowe Lex\nKraków\n6000–7000 zł\n\n"
                  "Kierowca kat. C\nTrans-Pol\nKraków\n\nRecepcjonistka w klinice\nMedica Plus\nBochnia\n\n"
                  "Sekretarka medyczna\nCentrum Zdrowia\nWieliczka\n\nZobacz wszystkie oferty\nWypisz się z alertów")
    LINKS = [{"tekst": "Asystentka biura", "url": "https://www.pracuj.pl/praca/asystentka-biura-krakow,oferta,1001"},
             {"tekst": "Kierowca kat. C", "url": "https://www.pracuj.pl/praca/kierowca,oferta,1002"},
             {"tekst": "Recepcjonistka w klinice", "url": "https://www.pracuj.pl/praca/recepcjonistka,oferta,1003"},
             {"tekst": "Sekretarka medyczna", "url": "https://www.pracuj.pl/praca/sekretarka,oferta,1004"},
             {"tekst": "Zobacz wszystkie oferty", "url": "https://www.pracuj.pl/praca"},
             {"tekst": "Wypisz się z alertów", "url": "https://www.pracuj.pl/alerty/wypisz"}]

    def setUp(self):
        super().setUp()
        self.A = importlib.import_module(self.mod.__name__ + ".odpowiedzi")
        self.AL = importlib.import_module(self.mod.__name__ + ".alerty")
        self.CB = importlib.import_module(self.mod.__name__ + ".cbop")
        self.OW = importlib.import_module(self.mod.__name__ + ".owca")
        self.ready()
        f = self.R.load_facts(self.ctx)
        f["warunki"]["dojazd_km"] = 20
        self.R.save_facts(self.ctx, f)

    def alert(self, uid=50, **kw):
        m = {"uid": uid, "message_id": f"<a{uid}@pracuj>", "od": "powiadomienia@pracuj.pl", "od_nazwa": "Pracuj.pl", "temat": "4 nowe oferty: asystentka",
             "data": "2026-11-12T08:00:00", "in_reply_to": "", "references": "", "auto": False, "tresc": self.ALERT_TEXT, "linki": self.LINKS[:3],
             "linki_wszystkie": self.LINKS}
        m.update(kw)
        return m

    def test_alert_email_becomes_offers(self):
        m = self.alert()
        self.assertTrue(self.AL.is_alert(m))
        titles = [x["tytul"] for x in self.AL.offers(m)]
        self.assertEqual(titles, ["Asystentka biura", "Kierowca kat. C", "Recepcjonistka w klinice", "Sekretarka medyczna"])
        self.assertEqual(self.AL.offers(m)[0]["firma"], "Biuro Rachunkowe Lex")
        self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: [m])
        with self.R.db(self.ctx) as c:
            rows = [dict(r) for r in c.execute("SELECT stanowisko, firma, miasto, zrodlo, status FROM aplikacje ORDER BY id")]
            alert = c.execute("SELECT rodzaj, status, streszczenie FROM wiadomosci").fetchone()
        self.assertEqual([r["stanowisko"] for r in rows], ["Asystentka biura", "Sekretarka medyczna"])   # bez kierowcy i bez Bochni (20 km)
        self.assertEqual({r["zrodlo"] for r in rows} | {r["status"] for r in rows}, {"auto", "nowa"})
        self.assertEqual((alert["rodzaj"], alert["status"]), ("alert", "zalatwiona"))
        self.assertIn("nowych pasujących: 2", alert["streszczenie"])
        self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: [self.alert(uid=51, message_id="<a51@pracuj>")])
        with self.R.db(self.ctx) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM aplikacje").fetchone()[0], 2)                # te same oferty drugi raz nie wchodzą
        self.assertEqual(self.sent, [])                                                                  # alert nie budzi Agi

    def test_portal_confirmation_is_not_an_alert(self):
        m = self.alert(temat="Twoja aplikacja została wysłana", tresc="Dziękujemy za aplikację na stanowisko Asystentka biura.",
                       linki=[], linki_wszystkie=[{"tekst": "Moje aplikacje", "url": "https://www.pracuj.pl/konto/aplikacje"}])
        self.assertFalse(self.AL.is_alert(m))
        self.assertFalse(self.AL.is_alert(dict(self.alert(), od="hr@firma.pl", od_nazwa="Kadry")))

    def cbop_response(self, status="Poprawny"):
        import base64, io, zipfile
        offers = [{"stanowisko": "Pracownik biurowy", "pracodawca": "Urząd Gminy Zielonki", "miejscowosc": "Zielonki", "email": "kadry@zielonki.pl",
                   "zakresObowiazkow": "obsługa sekretariatu, obieg dokumentów", "wynagrodzenieBrutto": "5200", "typOferty": "OFERTA_PRACY",
                   "statusOferty": "P", "link": "https://oferty.praca.gov.pl/portal/lista-ofert/szczegoly-oferty/abc"},
                  {"stanowisko": "Magazynier", "pracodawca": "X", "miejscowosc": "Kraków", "typOferty": "OFERTA_PRACY", "statusOferty": "P"},
                  {"stanowisko": "Asystentka", "pracodawca": "Y", "miejscowosc": "Tarnów", "typOferty": "OFERTA_PRACY", "statusOferty": "P"}]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("12_2026_11_12_20_00.json", json.dumps({"oferty": offers}, ensure_ascii=False))
        blob = base64.b64encode(buf.getvalue()).decode()
        return f"<soap:Envelope><soap:Body><odpowiedz><status>{status}</status><plik>{blob}</plik></odpowiedz></soap:Body></soap:Envelope>"

    def test_cbop_needs_partner_runs_in_evening(self):
        calls = []

        def post(url, data, headers):
            calls.append(data)
            return 200, self.cbop_response()
        evening = dt.datetime(2026, 11, 12, 20, 0, tzinfo=s.TZ)
        self.assertEqual(self.CB.run(self.ctx, post=post, now=evening), "")                          # bez nazwy partnera — nic
        self.ctx.set_setting("cbop_partner", "Sebastian-Kwiatkowska")
        self.assertEqual(self.CB.run(self.ctx, post=post, now=evening.replace(hour=12)), "")          # poza godzinami udostępniania
        self.assertIn("nowych pasujących 1", self.CB.run(self.ctx, post=post, now=evening))
        self.assertIn("<Wojewodztwo>12</Wojewodztwo>", calls[0])
        self.assertIn("<Partner>Sebastian-Kwiatkowska</Partner>", calls[0])
        with self.R.db(self.ctx) as c:
            a = dict(c.execute("SELECT * FROM aplikacje").fetchone())
        self.assertEqual((a["firma"], a["email"], a["miasto"]), ("Urząd Gminy Zielonki", "kadry@zielonki.pl", "Zielonki"))
        self.assertIn("obieg dokumentów", a["tresc"])
        self.assertEqual(self.CB.run(self.ctx, post=post, now=evening), "")                          # raz na dobę
        self.assertEqual(self.CB.fetch("zly", post=lambda *a: (200, "<x>Niepoprawna autoryzacja</x>")), ("Niepoprawna autoryzacja", []))

    def test_quick_add_and_more_offers_pages(self):
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        cl.post("/login", data={"haslo": "poprawne123"})
        with cl.session_transaction() as sess:
            sess["csrf"] = "t"
        page = cl.get("/szybko?u=https://www.pracuj.pl/praca/x,oferta,1&t=Asystentka+biura+w+Krakowie").data.decode()
        self.assertIn("https://www.pracuj.pl/praca/x,oferta,1", page)
        self.assertIn("Asystentka biura w Krakowie", page)
        more = cl.get("/wiecej-ofert").data.decode()
        for part in ("Pracuj.pl — alerty", "Wyślij do Sebastiana", "javascript:(function()", "/szybko?u="):
            self.assertIn(part, more)
        cl.post("/wiecej-ofert", data={"csrf": "t", "krok": "pracuj"})
        with self.R.db(self.ctx) as c:
            self.assertEqual(json.loads(self.R.meta_get(c, "wiecej_ofert_zrobione")), ["pracuj"])
        self.assertIn("Więcej ofert", cl.get("/").data.decode())

    def test_sheep_sends_the_idea_tomorrow_morning(self):
        self.P.migrate_290(self.ctx)                                           # dziś (wtorek 10.11 w testach)
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "adres_panelu", "http://mac:8790")
            when = self.R.meta_get(c, "owca_pomysl")
        self.assertEqual(when, "czeka:2026-11-11")
        self.assertNotEqual(self.OW.tick(self.ctx, self.fake_send, dt.datetime(2026, 11, 10, 8, 0, tzinfo=s.TZ)), "pomysl")
        self.assertEqual(self.OW.tick(self.ctx, self.fake_send, dt.datetime(2026, 11, 11, 7, 50, tzinfo=s.TZ)), "pomysl")
        mail = self.sent[-1]
        self.assertIn("Mam pomysł, jak zrobić, żeby było więcej ofert", mail["subject"])
        for part in ("Pracuj.pl", "OLX", "Indeed", "LinkedIn", "anna.testowa@gmail.com", "/wiecej-ofert", "asystentka biura"):
            self.assertIn(part, mail["html"])
        self.assertEqual(self.OW.tick(self.ctx, self.fake_send, dt.datetime(2026, 11, 11, 7, 55, tzinfo=s.TZ)), "rano")   # potem zwykły poranek
        self.assertNotEqual(self.OW.tick(self.ctx, self.fake_send, dt.datetime(2026, 11, 12, 7, 50, tzinfo=s.TZ)), "pomysl")



class SheepMails2110(RekrutacjaBase):
    def setUp(self):
        super().setUp()
        self.A = importlib.import_module(self.mod.__name__ + ".odpowiedzi")
        self.ready()
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "adres_panelu", "http://mac:8790")

    def test_evening_report_in_sheep_style(self):
        aid = self.add(firma="Biuro Lex", stanowisko="Asystentka", status="wyslana", wyslano=self.ctx.now().isoformat())
        self.add(firma="Firma B", status="do_zatwierdzenia")
        with self.R.db(self.ctx) as c:
            c.execute("INSERT INTO wiadomosci(uid,od,temat,tresc,aplikacja_id,rodzaj,wazne,status,utworzono) VALUES(9,'hr@lex.pl','x','x',?,'zaproszenie',1,'nowa',?)",
                      (aid, self.R.stamp(self.ctx)))
            c.commit()
        self.assertTrue(self.P.evening_report(self.ctx, send=self.fake_send, force=True))
        m = self.sent[-1]
        self.assertTrue(m["subject"].startswith("🌙 Dziś 1 wysłanych"))
        self.assertIn("cid:wieczor", m["html"])
        self.assertEqual(m["images"], ["wieczor"])
        for part in ("Dobry wieczór", "Biuro Lex", "zaproszenie na rozmowę", "Wysłane dziś", "http://mac:8790/do-zrobienia", "Cel dnia: 1 z"):
            self.assertIn(part, m["html"])
        self.assertIn("🐑 Cel dnia: 1/", m["body"])                                     # linia owcy w wersji tekstowej (wcześniej znikała)

    def test_invitation_notification_in_sheep_style(self):
        aid = self.add(firma="Biuro Lex", stanowisko="Asystentka", status="wyslana", wyslano="2026-11-09T10:00:00+01:00", email="hr@lex.pl")
        box = [{"uid": 70, "message_id": "<z70@lex>", "od": "hr@lex.pl", "od_nazwa": "Kadry", "temat": "Rozmowa", "data": "2026-11-10T11:00:00",
                "in_reply_to": "", "references": "", "auto": False, "tresc": "Dziękujemy za aplikację na stanowisko Asystentka. Zapraszamy Panią na rozmowę kwalifikacyjną 20.11 o godz. 10:00."}]
        with patch.object(W, "ask", lambda prompt, **kw: json.dumps({"rodzaj": "zaproszenie", "streszczenie": "Biuro Lex zaprasza Cię na rozmowę 20.11 o 10:00.",
                                                                       "termin": "20.11, 10:00", "pytania": []})):
            self.A.check_inbox(self.ctx, send=self.fake_send, fetch=lambda *a, **k: box)
        mail = next(m for m in self.sent if m["to"] == self.facts["osoba"]["email"] or "Zaproszenie" in m["subject"])
        self.assertEqual(mail["subject"], "📅 Zaproszenie na rozmowę: Biuro Lex")
        for part in ("cid:brawo", "zaprasza Cię na rozmowę", "20.11, 10:00", "http://mac:8790/wiadomosc/"):
            self.assertIn(part, mail["html"])



class Gemini2120(RekrutacjaBase):
    GOOD = ("Ogłoszenie na stanowisko asystentki biura od razu zwróciło moją uwagę, bo opisuje pracę, w której czuję się najpewniej: "
            "porządek w dokumentach i pilnowanie terminów.\n\nW szpitalu prowadziłam dokumentację i archiwizowałam ją tak, żeby wszystko "
            "dało się szybko odnaleźć. Koordynowałam terminy i przygotowywałam raporty dla kierownika, co nauczyło mnie dokładności.\n\n"
            "Pracuję w Excelu i Wordzie na co dzień i lubię, gdy w biurze wszystko jest na swoim miejscu. Dobrze odnajduję się w zespole "
            "i potrafię zadbać o sprawy bez przypominania.\n\nChętnie opowiem więcej podczas rozmowy. Będę wdzięczna za kontakt.")

    def setUp(self):
        super().setUp()
        self.GM = importlib.import_module(self.mod.__name__ + ".gemini")
        self.GM._MODEL.update(at=0.0, name=None, key="")
        self.calls = []
        self.code = 200
        self.extra.append(patch.object(self.GM, "_http", self.http))
        self.extra[-1].start()
        self.extra.append(patch.object(self.GM, "PACE", 0.0))
        self.extra[-1].start()
        self.ready()

    def http(self, method, url, key, body):
        self.calls.append((method, url, body))
        if method == "GET":
            return 200, {"models": [{"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]} for n in
                                    ("gemini-2.0-flash", "gemini-3.1-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-preview", "gemini-3.1-pro",
                                     "gemini-3.1-flash-image", "text-embedding-004")]}
        if self.code != 200:
            return self.code, {}
        prompt = body["contents"][0]["parts"][0]["text"]
        if "LIST MOTYWACYJNY" in prompt or "piszesz SWÓJ list" in prompt:
            return 200, {"candidates": [{"content": {"parts": [{"text": json.dumps({"list": self.GOOD})}]}}]}
        return 200, {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def test_model_choice(self):
        self.assertEqual(self.GM.pick_model(["models/gemini-2.0-flash", "models/gemini-3.1-flash", "models/gemini-3.1-flash-lite",
                                            "models/gemini-3.5-flash-preview", "models/gemini-3.1-pro"]), "gemini-3.1-flash")
        self.assertEqual(self.GM.pick_model(["models/gemini-3.5-flash-preview", "models/gemini-3.1-flash-lite"]), "gemini-3.5-flash-preview")
        self.assertEqual(self.GM.pick_model(["models/gemini-3.1-pro"], "gemini-3.1-pro"), "gemini-3.1-pro")
        self.assertIsNone(self.GM.pick_model([]))

    def test_no_key_means_local(self):
        a = {"stanowisko": "Asystentka biura", "firma": "Firma", "tresc": OFFER, "zrodlo": "oferta", "url": ""}
        letter, mail, by_model = self.D.compose(self.ctx, self.facts, a)
        self.assertEqual(self.calls, [])                                          # bez klucza żadnego zapytania do Google
        self.assertTrue(by_model)

    def test_letter_from_gemini_without_personal_data(self):
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        a = {"stanowisko": "Asystentka biura", "firma": "Firma", "tresc": OFFER, "zrodlo": "oferta", "url": ""}
        letter, mail, by_model = self.D.compose(self.ctx, self.facts, a)
        self.assertTrue(by_model)
        self.assertIn("od razu zwróciło moją uwagę", letter)
        self.assertTrue(letter.rstrip().endswith(self.R.full_name(self.facts)) or self.R.full_name(self.facts) in letter)   # podpis lokalnie
        sent = json.dumps([c[2] for c in self.calls if c[0] == "POST"], ensure_ascii=False)
        o = self.facts["osoba"]
        for private in (self.R.full_name(self.facts), o["email"], o.get("telefon") or "zzz-brak"):
            self.assertNotIn(private, sent)
        self.assertIn("WZORY TONU", sent)
        self.assertTrue(any("gemini-3.1-flash:generateContent" in c[1] for c in self.calls))

    def test_rate_limit_pauses_and_falls_back(self):
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        self.code = 429
        a = {"stanowisko": "Asystentka biura", "firma": "Firma", "tresc": OFFER, "zrodlo": "oferta", "url": ""}
        letter, mail, by_model = self.D.compose(self.ctx, self.facts, a)
        self.assertTrue(by_model)                                                  # napisał model lokalny
        self.assertFalse(self.GM.available(self.ctx))                             # godzina przerwy
        posts = len([c for c in self.calls if c[0] == "POST"])
        self.D.compose(self.ctx, self.facts, a)
        self.assertEqual(len([c for c in self.calls if c[0] == "POST"]), posts)   # w przerwie nie pyta
        self.assertIn("przerwa", self.GM.status(self.ctx))

    def test_daily_limit_and_switch_off(self):
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        self.ctx.set_setting("gemini_limit_dzienny", "10")
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, f"gemini_{self.ctx.now().date().isoformat()}", 10)
            c.commit()
        self.assertFalse(self.GM.available(self.ctx))
        self.ctx.set_setting("gemini_limit_dzienny", "300")
        self.assertTrue(self.GM.available(self.ctx))
        self.ctx.set_setting("pisanie", "lokalnie")
        self.assertFalse(self.GM.available(self.ctx))

    def test_waiting_letters_rewritten_once(self):
        aid = self.add()
        self.P.prepare(self.ctx, aid)                                             # bez klucza: list lokalny
        old = self.row(aid)["list"]
        self.assertIsNone(self.P.refresh_letter(self.ctx))                        # bez Gemini nic nie ruszam
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        self.assertEqual(self.P.refresh_letter(self.ctx), aid)
        new = self.row(aid)
        self.assertNotEqual(new["list"], old)
        self.assertIn("od razu zwróciło moją uwagę", new["list"])
        self.assertEqual(json.loads(new["analiza"])["list_v"], 3)
        self.assertTrue((self.P.app_dir(self.ctx, aid) / new["list_plik"]).exists())
        self.assertIsNone(self.P.refresh_letter(self.ctx))                        # drugi raz już nie


class Rewrite2121(Gemini2120):
    def test_backoff_grows_and_resets(self):
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        self.code = 429
        pauses = []
        for _ in range(3):
            with self.R.db(self.ctx) as c:
                self.R.meta_set(c, "gemini_przerwa", 0); c.commit()
            self.assertIsNone(self.GM.ask_json(self.ctx, "test LIST MOTYWACYJNY"))
            with self.R.db(self.ctx) as c:
                pauses.append(float(self.R.meta_get(c, "gemini_przerwa", "0")) - time.time())
        self.assertLess(pauses[0], 70)                                            # pierwsza przerwa ok. minuty, nie godzina
        self.assertGreater(pauses[2], pauses[0] * 3)                              # kolejne coraz dłuższe
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "gemini_przerwa", 0); c.commit()
        self.code = 200
        self.assertIsNotNone(self.GM.ask_json(self.ctx, "test LIST MOTYWACYJNY"))
        with self.R.db(self.ctx) as c:
            self.assertEqual(int(self.R.meta_get(c, "gemini_429", "0") or 0), 0)

    def test_local_text_not_marked_as_gemini(self):
        aid = self.add()
        self.P.prepare(self.ctx, aid)
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        self.code = 500                                                           # Google nie odpowiada
        self.assertIsNone(self.P.refresh_letter(self.ctx))
        self.assertEqual(self.P.letters_to_rewrite(self.ctx), [aid])              # zostaje do przepisania później

    def test_command_rewrites_all_and_keeps_approved(self):
        a1, a2 = self.add(), self.add(firma="Inna firma", stanowisko="Recepcjonistka")
        self.P.prepare(self.ctx, a1); self.P.prepare(self.ctx, a2)
        self.assertTrue(self.row(a2)["list"], self.row(a2)["status"])
        with self.R.db(self.ctx) as c:
            c.execute("UPDATE aplikacje SET status='zatwierdzona' WHERE id=?", (a2,)); c.commit()
        self.R.set_secret(self.ctx, "gemini", "klucz-testowy")
        init = importlib.import_module(self.mod.__name__)
        with patch("builtins.print"):
            self.assertEqual(init.COMMANDS["przepisz"](self.ctx, []), 0)
        self.assertIn("od razu zwróciło moją uwagę", self.row(a1)["list"])
        self.assertNotIn("od razu zwróciło moją uwagę", self.row(a2)["list"])   # zatwierdzonej nie ruszam
        with patch("builtins.print"):
            init.COMMANDS["przepisz"](self.ctx, ["--takze-zatwierdzone"])
        self.assertIn("od razu zwróciło moją uwagę", self.row(a2)["list"])


class Conversation213(RekrutacjaBase):
    """2.13: Sebastian odpisuje Adze, pamięta rozmowę, wstrzymuje owcę i przypomina w umówionym terminie."""
    def setUp(self):
        super().setUp()
        pkg = self.mod.__name__
        self.RZ = importlib.import_module(pkg + ".rozmowa")
        self.OW = importlib.import_module(pkg + ".owca")
        self.A = importlib.import_module(pkg + ".odpowiedzi")
        self.ready()
        self.answers, self.prompts = [], []
        orig = self.model.__call__
        def talk(prompt, as_json=False, max_tokens=1200, temperature=0.4):
            if "NOWA WIADOMOŚĆ OD AGI" in prompt or "prosiła, żeby przypomnieć" in prompt:
                self.prompts.append(prompt)
                return json.dumps(self.answers.pop(0)) if self.answers else None
            return orig(prompt, as_json, max_tokens, temperature)
        self.extra.append(patch.object(W, "ask", talk))
        self.extra[-1].start()

    def test_busy_without_model_asks_when_and_pauses_sheep(self):
        text, effects = self.RZ.reply_to(self.ctx, "panel", "Nie mam dziś czasu, sorry")
        self.assertIn("Kiedy będziesz mogła", text)
        with self.R.db(self.ctx) as c:
            self.assertTrue(self.RZ.paused(c, TUE_10.date()))
            self.assertIsNone(self.OW.due(self.ctx, c, TUE_10.replace(hour=11, minute=5)))   # dziś owca milczy
            self.assertFalse(self.RZ.paused(c, TUE_10.date() + dt.timedelta(days=1)))
        text, _ = self.RZ.reply_to(self.ctx, "panel", "W czwartek o 10")                        # odpowiedź na pytanie „kiedy”
        self.assertIn("Zapisane", text)
        with self.R.db(self.ctx) as c:
            rem = self.RZ.pending_reminders(c)
        self.assertEqual(rem[0]["kiedy"], "2026-11-12T10:00")

    def test_model_reply_reminder_memory_and_context(self):
        self.answers = [{"odpowiedz": "Udanego wyjazdu, Anno! Odpuszczam przypomnienia, a w poniedziałek rano wrócę z ofertami.",
                         "przerwa_do": "2026-11-15", "wznow": False, "przypomnij": {"kiedy": "2026-11-16 09:00", "co": "powrót z wyjazdu"},
                         "cel": None, "zapamietaj": ["Wyjazd 11–15.11.2026", "Woli oferty w centrum Krakowa"]},
                        {"odpowiedz": "Jasne, dziś 15 to świetny cel.", "przerwa_do": "", "wznow": True, "przypomnij": None, "cel": 15,
                         "zapamietaj": ["Woli oferty w centrum Krakowa"]}]
        text, effects = self.RZ.reply_to(self.ctx, "mail", "Od jutra wyjeżdżam do niedzieli")
        self.assertIn("Udanego wyjazdu", text)
        self.assertIn("przypomnienie 16.11 09:00", effects)
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.RZ.pause_until(c, self.ctx), "2026-11-15")
            self.assertEqual([m["fakt"] for m in self.RZ.memory(c)], ["Wyjazd 11–15.11.2026", "Woli oferty w centrum Krakowa"])
        text, effects = self.RZ.reply_to(self.ctx, "whatsapp", "Jednak zostaję, dziś zrobię 15")
        second = self.prompts[-1]
        self.assertIn("Od jutra wyjeżdżam do niedzieli", second)                              # historia rozmowy
        self.assertIn("Udanego wyjazdu", second)
        self.assertIn("Woli oferty w centrum Krakowa", second)                               # pamięć
        self.assertIn("1–3 zdania", second)                                                  # WhatsApp: krócej
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.RZ.pause_until(c, self.ctx), "")
            self.assertEqual(self.OW.goal(c, self.ctx, TUE_10.date())[0], 15)
            self.assertEqual(len(self.RZ.memory(c)), 2)                                      # bez powtórek
            self.assertEqual(len(self.RZ.history(c, 50)), 4)

    def test_bad_grammar_retried_then_rules(self):
        self.answers = [{"odpowiedz": "Rozumiem, byłeś zajęty.", "przerwa_do": ""}, {"odpowiedz": "Zrobiłeś dużo.", "przerwa_do": ""}]
        text, _ = self.RZ.reply_to(self.ctx, "panel", "jestem zajęta")
        self.assertEqual(len(self.prompts), 2)
        self.assertIn("rodzaju żeńskim", self.prompts[1])
        self.assertIn("Kiedy będziesz mogła", text)

    def test_mail_reply_in_thread_without_quote(self):
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "imap_uid_seb", 5)
        msgs = [{"uid": 6, "message_id": "<a1@gmail>", "od": "anna.testowa@gmail.com", "od_nazwa": "Anna", "temat": "Re: 🐑 3/30 — zostało 27",
                 "data": TUE_10.isoformat(), "in_reply_to": "", "references": "<x@seb>", "nasza": False,
                 "tresc": "Dziś nie dam rady, mam dużo na głowie.\n\nW dniu 10.11.2026 Owca Sebastian napisał(a):\n> Hej, jeszcze trochę!"},
                {"uid": 7, "message_id": "<b1@x>", "od": "obcy@firma.pl", "od_nazwa": "", "temat": "Oferta", "data": TUE_10.isoformat(),
                 "in_reply_to": "", "references": "", "nasza": False, "tresc": "Kup teraz"}]
        n = self.RZ.check_mail(self.ctx, send=self.fake_send, fetch=lambda *a, **k: msgs)
        self.assertEqual(n, 1)
        out = self.sent[-1]
        self.assertEqual((out["to"], out["from"], out["in_reply_to"]), ("anna.testowa@gmail.com", "sebastian.test@gmail.com", "<a1@gmail>"))
        self.assertEqual(out["subject"], "Re: 🐑 3/30 — zostało 27")
        self.assertIn("Owca Sebastian", out["body"])
        with self.R.db(self.ctx) as c:
            hist = self.RZ.history(c)
            self.assertEqual(R_uid := int(self.R.meta_get(c, "imap_uid_seb")), 7)
        self.assertEqual(hist[0]["tresc"], "Dziś nie dam rady, mam dużo na głowie.")             # bez cytatu
        self.assertEqual(self.RZ.check_mail(self.ctx, send=self.fake_send, fetch=lambda *a, **k: msgs), 0)   # drugi raz nie
        self.ctx.set_setting("rozmowa", "nie")
        self.assertEqual(self.RZ.check_mail(self.ctx, send=self.fake_send, fetch=lambda *a, **k: 1 / 0), 0)

    def test_whatsapp_from_aga_goes_to_conversation(self):
        queued = []
        aga = {"phone": "48600000000", "name": "Anna", "role": "rodzina"}
        with patch.object(self.A, "aga_phone", lambda ctx, f: "48600000000"), \
             patch.object(W, "enqueue", lambda con, kind, body="", **k: queued.append((body, k.get("to")))):
            self.assertTrue(DH.on_message(None, "text", "Nie mam dziś czasu", aga))
            self.assertFalse(DH.on_message(None, "text", "/pomoc", aga))                        # „/” = zwykły Sebastian
            self.assertFalse(DH.on_message(None, "text", "Cześć", {"phone": "48111222333", "name": "Ktoś", "role": "rodzina"}))
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0][1], "48600000000")                                         # odpowiedź do Agi, nie do właściciela
        self.assertIn("Kiedy będziesz mogła", queued[0][0])

    def test_reminder_fires_once_and_ends_pause(self):
        with self.R.db(self.ctx) as c:
            self.RZ.set_pause(c, self.ctx, TUE_10.date() + dt.timedelta(days=3))
            self.RZ.add_reminder(c, self.ctx, TUE_10 - dt.timedelta(minutes=5), "aplikacje", "mail")
        self.answers = [{"odpowiedz": "Hej Anno, jak się umawialiśmy: czeka na Ciebie kilka ofert. Zerkniesz na 10 minut?"}]
        self.assertTrue(self.RZ.tick(self.ctx, self.fake_send))
        self.assertIn("Zerkniesz na 10 minut", self.sent[-1]["body"])
        self.assertFalse(self.RZ.tick(self.ctx, self.fake_send))
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.RZ.pause_until(c, self.ctx), "")

    def test_paused_days_keep_streak(self):
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "owca_przerwy", json.dumps([["2026-11-09", "2026-11-09"]]))
            self.OW.set_goal(c, self.ctx, dt.date(2026, 11, 6), 1)
        self.add(status="wyslana", wyslano="2026-11-06T10:00:00", firma="F1", stanowisko="S")
        with self.R.db(self.ctx) as c:
            self.assertEqual(self.OW.streak(c, self.ctx, TUE_10.date()), 1)                   # pon. (przerwa) nie przerywa serii

    def test_crisis_gets_care_not_push(self):
        text, effects = self.RZ.reply_to(self.ctx, "panel", "Nie chcę już żyć, nic mi nie wychodzi")
        self.assertIn("116 123", text)
        self.assertEqual(self.prompts, [])
        with self.R.db(self.ctx) as c:
            self.assertTrue(self.RZ.paused(c, TUE_10.date() + dt.timedelta(days=2)))

    def test_when_parsing(self):
        now = TUE_10
        self.assertEqual(self.RZ.parse_when("w czwartek o 10", now).strftime("%Y-%m-%d %H:%M"), "2026-11-12 10:00")
        self.assertEqual(self.RZ.parse_when("jutro wieczorem", now).strftime("%Y-%m-%d %H:%M"), "2026-11-11 19:00")
        self.assertEqual(self.RZ.parse_when("za tydzień", now).date().isoformat(), "2026-11-16")
        self.assertEqual(self.RZ.parse_when("20.11", now).strftime("%d.%m %H:%M"), "20.11 09:00")
        self.assertIsNone(self.RZ.parse_when("nie wiem", now))

    def test_panel_page(self):
        self.RZ.reply_to(self.ctx, "panel", "Nie mam dziś czasu")
        from werkzeug.security import generate_password_hash
        with self.R.db(self.ctx) as c:
            self.R.meta_set(c, "haslo", generate_password_hash("poprawne123"))
        app = self.P.make_app(self.ctx)
        app.config.update(TESTING=True)
        cl = app.test_client()
        cl.post("/login", data={"haslo": "poprawne123"})
        with cl.session_transaction() as sess:
            sess["csrf"] = "t"
        html = cl.get("/rozmowa").get_data(as_text=True)
        self.assertIn("Nie mam dziś czasu", html)
        self.assertIn("wstrzymane do", html)
        cl.post("/rozmowa", data={"csrf": "t", "co": "koniec_przerwy"})
        self.assertNotIn("wstrzymane do", cl.get("/rozmowa").get_data(as_text=True))
        cl.post("/rozmowa", data={"csrf": "t", "co": "napisz", "tresc": "Hej Sebastian"})
        self.assertIn("Hej Sebastian", cl.get("/rozmowa").get_data(as_text=True))

if __name__ == "__main__":
    unittest.main()
