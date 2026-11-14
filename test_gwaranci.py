"""Testy 2.14 / 2.14.1: dodatek Gwaranci (także gwaranci z cal.com). Bez sieci, bez Gmaila, bez WhatsAppa — wszystko udawane."""
import datetime as dt, json, os, re, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SEBASTIAN_TESTY"] = "1"

import importlib.util, sys
ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gw", ROOT / "dodatki" / "gwaranci" / "__init__.py",
                                              submodule_search_locations=[str(ROOT / "dodatki" / "gwaranci")])
GW = importlib.util.module_from_spec(spec)
sys.modules["gw"] = GW
spec.loader.exec_module(GW)
from gw import rdzen as R, przebieg as PB, panel as PN

TZ = R.TZ
MON = dt.date(2026, 11, 16)                       # poniedziałek
NOW = dt.datetime(2026, 11, 14, 10, 0, tzinfo=TZ)  # sobota


FAKE = [("Marek Dyrektor", "D1 - Director", "", True, True), ("Celina Kloc", "Planner", "Marek Dyrektor", False, False),
        ("Jola Nowa", "Trainee", "Celina Kloc", False, False), ("Przemek Vip", "VIP Planner II", "Marek Dyrektor", False, False),
        ("Bartek Świeży", "Trainee", "Marek Dyrektor", False, False), ("Adam Wierzba", "M2 - Executive Manager", "Marek Dyrektor", True, True),
        ("Olga Ruda", "Consultant", "Adam Wierzba", False, False), ("Witek Lipa", "Planner", "Adam Wierzba", False, False),
        ("Tomasz Solny", "Trainee", "Witek Lipa", False, False), ("Janek Pomocny", "Asystent", "Adam Wierzba", False, False),
        ("Kuba Dąb", "M1 - Team Manager", "Adam Wierzba", True, False), ("Wiktor Buk", "Planner", "Kuba Dąb", False, False),
        ("Tomasz Dekiel", "Trainee", "Kuba Dąb", False, False), ("Piotr Jawor", "Trainee", "Kuba Dąb", False, False),
        ("Mateusz Żar", "Trainee", "Piotr Jawor", False, False), ("Maciej Grab", "Senior Planner", "Kuba Dąb", False, False),
        ("Beata Klon", "Consultant", "Maciej Grab", False, False), ("Magda Brzoza", "Trainee", "Maciej Grab", False, False),
        ("Małgorzata Żółć", "Trainee", "Maciej Grab", False, False), ("Grzegorz Sosna", "M1 - Team Manager", "Marek Dyrektor", False, False),
        ("Łukasz Cis", "Senior Planner", "Grzegorz Sosna", False, False)]


class Ctx:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.manifest = json.loads((ROOT / "dodatki" / "gwaranci" / "dodatek.json").read_text(encoding="utf-8"))
        self.id = "gwaranci"
        self.sent = []
        self.secrets = {}
        self.t = NOW
        import logging
        self.log = logging.getLogger("test.gwaranci")

    def folder(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        f = self.dir / "struktura.json"
        if not f.exists():
            f.write_text(json.dumps({"osoby": [{"imie_nazwisko": n, "stanowisko": s, "przelozony": b, "pelny_etat": e, "admin": a}
                                               for n, s, b, e, a in FAKE]}, ensure_ascii=False), encoding="utf-8")
        return self.dir

    def settings(self):
        return dict(self.manifest["ustawienia"])

    def set_setting(self, k, v):
        return v

    def now(self):
        return self.t

    def send_text(self, text, purpose="info"):
        self.sent.append(text)

    def secret(self, name):
        return self.secrets.get(name)

    def set_secret(self, name, value):
        self.secrets[name] = value


def ics(*events, day=MON):
    body = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//t//PL\r\n"
    for i, ev in enumerate(events):
        a, b, title = ev[:3]
        transp = ev[3] if len(ev) > 3 else "OPAQUE"
        body += (f"BEGIN:VEVENT\r\nUID:e{i}@t\r\nDTSTAMP:20260101T000000Z\r\nDTSTART;TZID=Europe/Warsaw:{day:%Y%m%d}T{a.replace(':', '')}00\r\n"
                 f"DTEND;TZID=Europe/Warsaw:{day:%Y%m%d}T{b.replace(':', '')}00\r\nSUMMARY:{title}\r\nTRANSP:{transp}\r\nEND:VEVENT\r\n")
    return body + "END:VCALENDAR\r\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ctx = Ctx(self.tmp.name)
        self.c = R.db(self.ctx)
        self.mails = []
        p = patch.object(R, "send_mail", side_effect=lambda ctx, c, to, subject, text, html="", ics="", method="REQUEST":
                         self.mails.append({"to": to, "subject": subject, "text": text, "ics": ics, "method": method}))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.c.close)
        self.st = self.ctx.settings()

    def ready(self, name, avail, limit=3, cal=""):
        p = R.find_person(self.c, name)
        self.c.execute("UPDATE osoby SET email=? WHERE id=?", (R.slug(name) + "@example.com", p["id"]))
        self.c.commit()
        R.save_guarantor(self.c, p["id"], kalendarze=["https://example.com/x.ics"], dostepnosc=avail, limit_tyg=limit, gotowe=1)
        R.refresh_busy(self.c, p["id"], fetch=lambda url: cal or ics(), when=NOW)
        return p["id"]


class Struktura(Base):
    def test_kolejnosc_przydzialu(self):
        ppl = R.people(self.c)
        self.assertEqual(R.tier(ppl, "kuba-dab", "beata-klon"), 0)        # bezpośredni menedżer
        self.assertEqual(R.tier(ppl, "adam-wierzba", "beata-klon"), 1)     # pośredni
        self.assertEqual(R.tier(ppl, "marek-dyrektor", "beata-klon"), 1)
        self.assertEqual(R.tier(ppl, "wiktor-buk", "beata-klon"), 2)             # ta sama struktura (Kuby)
        self.assertEqual(R.tier(ppl, "lukasz-cis", "beata-klon"), 3)           # inna struktura
        self.assertEqual(R.structure_of(ppl, "tomasz-solny"), "adam-wierzba")  # Witek nie ma jeszcze M1
        self.assertEqual(R.structure_of(ppl, "jola-nowa"), "marek-dyrektor")
        self.assertEqual(R.category(ppl, "olga-ruda", "tomasz-solny"), "w_strukturze")

    def test_limity(self):
        lim = lambda n: R.max_limit(R.find_person(self.c, n))
        self.assertEqual(lim("Adam Wierzba"), 8)
        self.assertEqual(lim("Grzegorz Sosna"), 5)
        self.assertEqual(lim("Wiktor Buk"), 3)
        self.assertEqual(lim("Maciej Grab"), 4)
        self.assertEqual(lim("Olga Ruda"), 1)
        self.assertEqual(lim("Przemek Vip"), 6)
        self.assertEqual(lim("Bartek Świeży"), 0)
        self.assertEqual(lim("Janek Pomocny"), 0)

    def test_awans_przez_whatsapp(self):
        out = GW.on_message(self.ctx, {"text": "gwaranci awans Olga Ruda na Consultant II"})
        self.assertIn("Consultant II", out)
        self.assertEqual(R.max_limit(R.find_person(self.c, "Olga Ruda")), 2)
        self.assertIsNone(GW.on_message(self.ctx, {"text": "co mam jutro w kalendarzu?"}))
        out = GW.on_message(self.ctx, {"text": "gwaranci dodaj Jan Nowak od Kuba Dąb"})
        self.assertIn("Dodano Jan Nowak", out)
        self.assertEqual(R.find_person(self.c, "Jan Nowak")["przelozony"], "kuba-dab")
        self.assertIn("/l/", GW.on_message(self.ctx, {"text": "gwaranci link Jan Nowak"}))


class Kalendarz(Base):
    def test_zajetosc_bez_wolnych_i_odwolanych(self):
        blocks = R.busy_blocks(ics(("10:00", "11:00", "Klient"), ("12:00", "13:00", "Lunch", "TRANSPARENT")),
                               dt.datetime(2026, 11, 15, tzinfo=TZ), dt.datetime(2026, 11, 18, tzinfo=TZ))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0].hour, 10)

    def test_przydzial_i_kolizje(self):
        kuba = self.ready("Kuba Dąb", [[0, 600, 1080]], 2, ics(("13:00", "14:00", "Klient")))
        wiktor = self.ready("Wiktor Buk", [[0, 960, 1140]], 3)
        snap = R.Snapshot(self.c, self.st)
        at = lambda h, m=0: dt.datetime.combine(MON, dt.time(h, m), TZ)
        self.assertEqual(snap.candidates("beata-klon", at(11), 75)[0]["gwarant"], kuba)
        self.assertEqual(snap.candidates("beata-klon", at(13), 30), [])                       # Kuba ma klienta, Wiktor jeszcze nie
        self.assertEqual(snap.candidates("beata-klon", at(17), 60)[0]["gwarant"], kuba)        # Kuba do 18:00 — mieści się
        self.assertEqual(snap.candidates("beata-klon", at(17, 30), 60)[0]["gwarant"], wiktor)  # po 18:00 już tylko Wiktor
        days = R.days_with_slots(self.c, self.st, "beata-klon", "analiza", NOW)
        self.assertIn(MON, days)
        self.assertTrue(days[MON]["menedzer"])
        # limit: Kuba ma 2 w tygodniu
        R.book(self.c, self.st, "beata-klon", "usluga", at(10), when=NOW)
        R.book(self.c, self.st, "tomasz-dekiel", "usluga", at(11), when=NOW)
        snap = R.Snapshot(self.c, self.st)
        self.assertNotIn(kuba, [x["gwarant"] for x in snap.candidates("beata-klon", at(15), 30)])

    def test_rezerwacja_i_decyzja(self):
        self.ready("Kuba Dąb", [[0, 600, 1080]], 3)
        self.c.execute("UPDATE osoby SET email='beata@example.com' WHERE id='beata-klon'")
        self.c.commit()
        b = R.book(self.c, self.st, "beata-klon", "analiza", dt.datetime.combine(MON, dt.time(11), TZ), "miejsce", "u klienta, Długa 5", when=NOW)
        self.assertEqual(b["kategoria"], "wlasna_linia")
        PB.after_booking(self.ctx, self.c, b)
        self.assertEqual(self.mails[0]["to"], "kuba-dab@example.com")
        self.assertIn("METHOD:REQUEST", self.mails[0]["ics"])
        self.assertIn("/decyzja/", self.mails[0]["text"])
        self.assertTrue(any("czeka na akceptację" in s for s in self.ctx.sent))
        with self.assertRaises(ValueError):                                       # ten sam termin drugi raz — Kuba zajęty
            R.book(self.c, self.st, "magda-brzoza", "analiza", dt.datetime.combine(MON, dt.time(11), TZ), when=NOW)
        b = PB.decide(self.ctx, self.c, b, True)
        self.assertEqual(b["status"], "potwierdzone")
        self.assertTrue(any(m["to"] == "beata@example.com" and "beata@example.com" in m["ics"] for m in self.mails))

    def test_przypomnienie_i_wygasniecie(self):
        self.ready("Kuba Dąb", [[0, 600, 1080]], 3)
        b = R.book(self.c, self.st, "beata-klon", "usluga", dt.datetime.combine(MON, dt.time(11), TZ), when=NOW)
        PB.periodic(self.ctx, self.c, when=NOW + dt.timedelta(hours=21), refresh=False, mail=False)
        self.assertEqual(R.booking(self.c, b["id"])["przypomniano"], 1)
        PB.periodic(self.ctx, self.c, when=dt.datetime.combine(MON, dt.time(10), TZ), refresh=False, mail=False)
        self.assertEqual(R.booking(self.c, b["id"])["status"], "wygaslo")

    def test_ics_zawijanie_i_polskie_znaki(self):
        self.ready("Kuba Dąb", [[0, 600, 1080]], 3)
        b = R.book(self.c, self.st, "malgorzata-zolc", "analiza",
                   dt.datetime.combine(MON, dt.time(11), TZ), when=NOW)
        text = R._event_ics(self.ctx, self.c, b)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n")))
        import icalendar
        cal = icalendar.Calendar.from_ical(text)
        self.assertIn("Małgorzata Żółć", str(next(iter(cal.walk("VEVENT")))["SUMMARY"]))


class Panel(Base):
    def setUp(self):
        super().setUp()
        self.app = PN.make_app(self.ctx).test_client()

    def login(self, name):
        p = R.find_person(self.c, name)
        r = self.app.get(f"/l/{p['token']}")
        self.assertEqual(r.status_code, 302)
        return p

    def csrf(self, path):
        html = self.app.get(path).get_data(as_text=True)
        m = re.search(r'name="csrf" value="([^"]+)"', html)
        return m.group(1) if m else ""

    def test_onboarding_gwaranta(self):
        self.login("Wiktor Buk")
        self.assertIn("/dane", self.app.get("/").headers["Location"])
        tok = self.csrf("/dane")
        r = self.app.post("/dane", data={"csrf": tok, "email": "wiktor@example.com"})
        self.assertIn("/gwarant/start", self.app.get("/").headers["Location"])
        with patch.object(R, "fetch_ics", return_value=ics(("10:00", "11:00", "Klient"))):
            tok = self.csrf("/gwarant/start")
            r = self.app.post("/gwarant/start?k=1", data={"csrf": tok, "kalendarze": "webcal://calendar.google.com/x/basic.ics"})
        self.assertIn("k=2", r.headers["Location"])
        html = self.app.get(r.headers["Location"]).get_data(as_text=True)
        self.assertIn("Kalendarz podłączony", html)
        tok = self.csrf("/gwarant/start?k=2")
        r = self.app.post("/gwarant/start?k=2", data={"csrf": tok, "dostepnosc": json.dumps([[0, 960, 1140]]), "limit": "9"})
        g = R.guarantor(self.c, "wiktor-buk")
        self.assertEqual(g["limit_tyg"], 3)                 # nie więcej niż pozwala stanowisko
        self.assertEqual(g["kalendarze"], ["https://calendar.google.com/x/basic.ics"])
        self.assertTrue(g["gotowe"])
        self.assertTrue(any("gotowy" in s for s in self.ctx.sent))
        self.assertIn("Panel gwaranta", self.app.get("/gwarant").get_data(as_text=True))

    def test_rezerwacja_przez_panel(self):
        self.ready("Kuba Dąb", [[0, 600, 1080]], 3)
        self.login("Beata Klon")
        self.c.execute("UPDATE osoby SET email='beata@example.com' WHERE id='beata-klon'")
        self.c.commit()
        with patch.object(R, "now", return_value=NOW), patch.object(R, "fetch_ics", return_value=ics()):
            html = self.app.get(f"/rezerwuj?typ=analiza&d={MON.isoformat()}").get_data(as_text=True)
            self.assertIn("Spotkanie gwaranckie", html)
            m = re.search(r'href="(/rezerwuj/potwierdz[^"]+)"', html)
            self.assertTrue(m)
            url = m.group(1).replace("&amp;", "&")
            html = self.app.get(url).get_data(as_text=True)
            self.assertIn("Kuba Dąb", html)
            tok = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
            start = re.search(r'name="start" value="([^"]+)"', html).group(1)
            r = self.app.post("/rezerwuj/potwierdz", data={"csrf": tok, "typ": "analiza", "start": start, "loc": "online", "notatka": "rodzina 2+1"})
            self.assertIn("Prośba wysłana", r.get_data(as_text=True))
        b = dict(self.c.execute("SELECT * FROM rezerwacje").fetchone())
        self.assertEqual(b["gwarant"], "kuba-dab")
        # decyzja z linku w mailu — bez logowania, dopiero po kliknięciu przycisku
        other = PN.make_app(self.ctx).test_client()
        html = other.get(f"/decyzja/{b['token']}/tak").get_data(as_text=True)
        self.assertEqual(R.booking(self.c, b["id"])["status"], "czeka")
        tok = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        other.post(f"/decyzja/{b['token']}/tak", data={"csrf": tok})
        self.assertEqual(R.booking(self.c, b["id"])["status"], "potwierdzone")
        self.assertIn("potwierdzone", self.app.get("/moje").get_data(as_text=True))

    def test_admin_i_dostep(self):
        r = self.app.get("/rezerwuj")
        self.assertIn("/witaj", r.headers["Location"])
        r = self.app.post("/dostep", data={"imie_nazwisko": "Jan Nowak", "email": "jan@example.com", "przelozony": "Kuba Dąb"})
        self.assertIn("Dziękujemy", r.get_data(as_text=True))
        self.assertTrue(any("prośba o dostęp" in s for s in self.ctx.sent))
        self.login("Beata Klon")
        self.c.execute("UPDATE osoby SET email='beata@example.com' WHERE id='beata-klon'")
        self.c.commit()
        self.assertEqual(self.app.get("/admin").status_code, 403)
        self.login("Adam Wierzba")
        self.c.execute("UPDATE osoby SET email='andrzej@example.com' WHERE id='adam-wierzba'")
        self.c.commit()
        r = self.app.get("/admin")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Jan Nowak", r.get_data(as_text=True))


class FakeCal:
    """Udawane API cal.com: wolne terminy co 75 min (analiza) i co 30 min (krótsze), rezerwacje, statusy, odwołania."""
    def __init__(self):
        self.calls, self.status, self.refuse, self.invalid = [], "pending", False, False

    def __call__(self, method, path, params=None, body=None, version="2024-08-13", key=""):
        self.calls.append((method, path, params, body, key))
        if path == "/slots":
            if params["username"] == "nie-ma":
                return 404, {"error": {"message": "not found"}}
            step = 75 if int(params.get("duration", 30)) == 75 else 30
            day = MON.isoformat()
            starts = [dt.datetime.combine(MON, dt.time(9), TZ) + dt.timedelta(minutes=step * i) for i in range(4)]
            return 200, {"status": "success", "data": {day: [{"start": x.isoformat()} for x in starts]}}
        if method == "POST" and path == "/bookings":
            if self.refuse:
                return 400, {"error": {"message": "User either already has booking at this time or is not available"}}
            if self.invalid:
                return 400, {"error": {"message": "responses - {location}error_required_field"}}
            return 201, {"status": "success", "data": {"uid": "cal-uid-1", "status": "pending"}}
        if method == "GET" and path.startswith("/bookings/"):
            return 200, {"status": "success", "data": {"uid": path.split("/")[-1], "status": self.status}}
        if path.endswith("/cancel"):
            return 200, {"status": "success", "data": {}}
        return 404, {}


class CalCom(Base):
    def setUp(self):
        super().setUp()
        self.cal = FakeCal()
        p = patch.object(R, "calcom_http", self.cal)
        p.start()
        self.addCleanup(p.stop)

    def podepnij(self, name="Adam Wierzba", ref="adam-w/spotkanie-gwaranckie"):
        f = self.ctx.folder() / "struktura.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        for o in data["osoby"]:
            if o["imie_nazwisko"] == name:
                o["calcom"] = "https://cal.com/" + ref
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.c.close()
        self.c = R.db(self.ctx)
        pid = R.slug(name)
        self.c.execute("UPDATE osoby SET email=? WHERE id IN (?, 'tomasz-solny')", (pid + "@example.com", pid))
        self.c.execute("UPDATE osoby SET email='tomasz@example.com' WHERE id='tomasz-solny'")
        self.c.commit()
        R.refresh_busy(self.c, pid, when=NOW)
        return pid

    def test_link_calcom(self):
        self.assertEqual(R.parse_calcom("https://cal.com/andrzej-kwiatkowski/spotkanie-gwaranckie"), "andrzej-kwiatkowski/spotkanie-gwaranckie")
        self.assertEqual(R.parse_calcom("cal.com/andrzej-kwiatkowski/spotkanie-gwaranckie?month=2026-11"), "andrzej-kwiatkowski/spotkanie-gwaranckie")
        self.assertEqual(R.parse_calcom("https://cal.com/andrzej-kwiatkowski"), "")
        self.assertEqual(R.parse_calcom("https://calendar.google.com/x/basic.ics"), "")

    def test_domyslnie_podpiety_z_struktury(self):
        adam = self.podepnij()
        g = R.guarantor(self.c, adam)
        self.assertEqual(g["calcom"], "adam-w/spotkanie-gwaranckie")
        self.assertTrue(g["gotowe"])
        self.assertEqual(g["limit_tyg"], 8)
        R.save_guarantor(self.c, adam, calcom="")                 # sam przełączył się na iCal — nie nadpisuję przy kolejnym starcie
        self.c.close()
        self.c = R.db(self.ctx)
        self.assertEqual(R.guarantor(self.c, adam)["calcom"], "")

    def test_rezerwacja_w_calcom(self):
        adam = self.podepnij()
        day = R.slots(self.c, self.st, "tomasz-solny", "analiza", MON, NOW)
        times = [s.strftime("%H:%M") for s, _ in day]
        self.assertIn("10:15", times)                             # godzina z cal.com spoza siatki co 30 min
        self.assertNotIn("10:00", times)
        start = dt.datetime.combine(MON, dt.time(10, 15), TZ)
        b = R.book(self.c, self.st, "tomasz-solny", "analiza", start, "miejsce", "biuro Zakopiańska", "rodzina 2+1", when=NOW)
        self.assertEqual((b["gwarant"], b["calcom_uid"]), (adam, "cal-uid-1"))
        post = next(x for x in self.cal.calls if x[0] == "POST")
        self.assertEqual(post[3]["start"], "2026-11-16T09:15:00Z")
        self.assertEqual(post[3]["attendee"]["email"], "tomasz@example.com")
        self.assertIn("Na miejscu: biuro Zakopiańska", post[3]["bookingFieldsResponses"]["notes"])
        self.assertNotIn("10:15", [s.strftime("%H:%M") for s, _ in R.slots(self.c, self.st, "tomasz-solny", "analiza", MON, NOW)])
        PB.after_booking(self.ctx, self.c, b)
        self.assertEqual([m["to"] for m in self.mails], ["tomasz@example.com"])  # prośbę do gwaranta wysyła cal.com
        self.assertTrue(any("cal.com" in s for s in self.ctx.sent))
        PB.periodic(self.ctx, self.c, when=NOW + dt.timedelta(hours=30), refresh=False, mail=False)
        self.assertEqual(R.booking(self.c, b["id"])["status"], "czeka")  # bez przypomnień i wygasania — to robi cal.com
        self.cal.status = "accepted"
        PB.sync_calcom(self.ctx, self.c, NOW)
        self.assertEqual(R.booking(self.c, b["id"])["status"], "potwierdzone")
        PB.cancel_by_adept(self.ctx, self.c, R.booking(self.c, b["id"]))
        self.assertTrue(any(x[1] == "/bookings/cal-uid-1/cancel" for x in self.cal.calls))
        self.assertEqual(R.booking(self.c, b["id"])["status"], "anulowane")

    def test_odmowa_calcom_bierze_nastepnego(self):
        self.podepnij()
        wiktor = self.ready("Wiktor Buk", [[0, 540, 1080]], 3)
        self.cal.refuse = True
        start = dt.datetime.combine(MON, dt.time(10, 30), TZ)
        b = R.book(self.c, self.st, "tomasz-solny", "usluga", start, when=NOW)
        self.assertEqual((b["gwarant"], b["calcom_uid"]), (wiktor, ""))

    def test_onboarding_z_calcom_i_whatsapp(self):
        app = PN.make_app(self.ctx).test_client()
        p = R.find_person(self.c, "Wiktor Buk")
        self.c.execute("UPDATE osoby SET email='wiktor@example.com' WHERE id=?", (p["id"],))
        self.c.commit()
        app.get(f"/l/{p['token']}")
        tok = re.search(r'name="csrf" value="([^"]+)"', app.get("/gwarant/start").get_data(as_text=True)).group(1)
        r = app.post("/gwarant/start?k=1", data={"csrf": tok, "zrodlo": "calcom", "calcom": "https://cal.com/nie-ma/x"})
        self.assertIn("Nie udało się odczytać", r.get_data(as_text=True))
        r = app.post("/gwarant/start?k=1", data={"csrf": tok, "zrodlo": "calcom", "calcom": "https://cal.com/wiktor-b/gwarant"})
        self.assertIn("k=2", r.headers["Location"])
        self.assertIn("cal.com podłączony", app.get(r.headers["Location"]).get_data(as_text=True))
        app.post("/gwarant/start?k=2", data={"csrf": tok, "dostepnosc": "[]", "limit": "2"})
        g = R.guarantor(self.c, p["id"])
        self.assertEqual((g["calcom"], g["limit_tyg"], g["gotowe"]), ("wiktor-b/gwarant", 2, 1))
        out = GW.on_message(self.ctx, {"text": "gwaranci calcom Olga Ruda https://cal.com/olga/gw"})
        self.assertIn("cal.com podpięty", out)


class Naprawy2143(CalCom):
    """2.14.3: cal.com odrzuca formularz → prośba idzie mailem; Gmail zrywa połączenie → ponowienie i kolejka."""
    def test_calcom_formularz_odrzucony_idzie_mailem(self):
        adam = self.podepnij()
        self.cal.invalid = True
        start = dt.datetime.combine(MON, dt.time(10, 15), TZ)
        b = R.book(self.c, self.st, "tomasz-solny", "analiza", start, when=NOW)
        self.assertEqual((b["gwarant"], b["calcom_uid"]), (adam, ""))               # ten sam gwarant, bez „Termin zajęty”
        self.assertIn("error_required_field", b["calcom_blad"])
        posts = [x[3] for x in self.cal.calls if x[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertNotIn("bookingFieldsResponses", posts[1])                      # druga, najprostsza próba
        PB.after_booking(self.ctx, self.c, b)
        self.assertEqual([m["to"] for m in self.mails], [adam + "@example.com", "tomasz@example.com"])
        self.assertTrue(self.mails[0]["ics"])
        self.assertTrue(any("prośba poszła mailem" in t for t in self.ctx.sent))
        self.assertIn("error_required_field", R.meta_get(self.c, "calcom_ostatni_blad"))

    def test_adept_bez_maila_idzie_mailem_do_gwaranta(self):
        adam = self.podepnij()
        self.c.execute("UPDATE osoby SET email='' WHERE id='tomasz-solny'")
        self.c.commit()
        b = R.book(self.c, self.st, "tomasz-solny", "analiza", dt.datetime.combine(MON, dt.time(10, 15), TZ), when=NOW)
        self.assertEqual((b["gwarant"], b["calcom_uid"]), (adam, ""))
        self.assertFalse([x for x in self.cal.calls if x[0] == "POST"])

    def test_kolejka_maili(self):
        p = patch.object(R, "send_mail", side_effect=R.MailError("Gmail zerwał połączenie (SMTPServerDisconnected)"))
        p.start()
        err = R.send_or_queue(self.ctx, self.c, "gw@example.com", "Prośba", "treść", ics="X", booking_id=7)
        p.stop()
        self.assertIn("w kolejce", err)
        self.assertEqual(R.flush_queue(self.ctx, self.c, NOW), [])                 # jeszcze nie pora
        PB.periodic(self.ctx, self.c, when=dt.datetime.now(TZ) + dt.timedelta(minutes=5), refresh=False, mail=False)
        self.assertEqual([(m["to"], m["ics"]) for m in self.mails], [("gw@example.com", "X")])
        self.assertTrue(any("wyszedł za 2. razem" in t for t in self.ctx.sent))
        with patch.object(R, "send_mail", side_effect=R.MailError("Gmail odrzucił hasło aplikacji")):
            self.assertNotIn("kolejce", R.send_or_queue(self.ctx, self.c, "gw@example.com", "x", "y"))   # zły login — bez kolejki

    def test_smtp_ponawia_i_przechodzi_na_465(self):
        import smtplib
        tried = []

        class Box:
            def __init__(self, host, port, timeout=60, context=None):
                tried.append(port)
                if len(tried) < 3:
                    raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
            def ehlo(self): pass
            def starttls(self, context=None): pass
            def login(self, a, b): pass
            def send_message(self, m): return {}
            def quit(self): pass
        from email.message import EmailMessage
        with patch.object(R.smtplib, "SMTP", Box), patch.object(R.smtplib, "SMTP_SSL", Box):
            R.smtp_send("seb@gmail.com", "abcd efgh", EmailMessage(), pause=0)
        self.assertEqual(tried, [587, 587, 465])

        class Bad(Box):
            def __init__(self, *a, **k): pass
            def login(self, a, b): raise smtplib.SMTPAuthenticationError(535, b"bad")
        with patch.object(R.smtplib, "SMTP", Bad), self.assertRaises(R.MailError) as e:
            R.smtp_send("seb@gmail.com", "x", EmailMessage(), pause=0)
        self.assertIn("hasło aplikacji", str(e.exception))

    def test_domyslna_skrzynka(self):
        self.assertEqual(R.mailbox(self.ctx, self.c)[0], "sebastian.k.kwiatkowski@gmail.com")


if __name__ == "__main__":
    unittest.main()
