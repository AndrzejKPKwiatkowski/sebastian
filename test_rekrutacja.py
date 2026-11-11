"""Testy dodatku Rekrutacja (część A). Bez Gmaila, bez Ollamy, bez Tailscale — wszystko udawane."""
import contextlib, datetime as dt, importlib, json, re, unittest
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

    def __call__(self, prompt, as_json=False, max_tokens=1200, temperature=0.4):
        if "Dobierasz" in prompt:
            return json.dumps({"kolejnosc": ["d2", "d1", "d99"], "punkty": {"d1": ["d1.2", "x"]}, "profil": ["p2", "p1", "p77"],
                               "umiejetnosci": ["u3", "u1", "u2"], "narzedzia": ["n1"]})
        if "Przeczytaj ogłoszenie" in prompt:
            return json.dumps({"firma": "Biuro Rachunkowe Testowe Sp. z o.o.", "stanowisko": "Specjalistka ds. administracji biurowej",
                               "miasto": "Kraków", "email": "rekrutacja@testowe.pl", "rodo": "", "sprzedaz": False, "ocena": 84,
                               "uzasadnienie": "Administracja i dokumentacja, bez sprzedaży."})
        if "Piszesz w imieniu" in prompt:
            return json.dumps({"list": self.letter, "mail": "Dzień dobry,\n\nw odpowiedzi na ogłoszenie przesyłam w załączniku CV i list "
                               "przewodni. Praca z dokumentacją i koordynacja terminów to obszar, w którym czuję się pewnie. "
                               "Będę wdzięczna za informację zwrotną."})
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

    def fake_send(self, sender, pwd, to, subject, body, attachments=(), name="", reply_to="", in_reply_to="", references=""):
        self.sent.append({"from": sender, "to": to, "subject": subject, "body": body, "files": [Path(p).name for p in attachments], "pwd": pwd, "in_reply_to": in_reply_to})
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
        self.assertTrue(any(m["subject"].startswith("Zaproszenie") and m["to"] == "anna.testowa@gmail.com" for m in self.sent))
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
        self.assertEqual(len(sel["punkty"]["d5"]), 2)
        self.assertEqual(len(self.D.default_selection(f)["punkty"]["d5"]), 4)
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


if __name__ == "__main__":
    unittest.main()
