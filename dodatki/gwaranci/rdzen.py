"""Gwaranci — rdzeń: osoby i struktura, zasady, zajętość z kalendarzy, przydział, rezerwacje, poczta z zaproszeniami.

Wszystkie dane (linki do kalendarzy, maile, rezerwacje) leżą w data/dodatki/gwaranci/ — nigdy w repozytorium.
Z kalendarzy gwarantów zapamiętuję wyłącznie godziny zajętości (od–do), bez tytułów i opisów wydarzeń.
"""
import contextlib, datetime as dt, email.policy, imaplib, json, re, secrets, smtplib, sqlite3, ssl, subprocess, sys, unicodedata, urllib.request
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
EMAIL_OK = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")

TYPES = {"usluga": ("Usługa", 30), "serwis": ("Serwis", 60), "analiza": ("Analiza", 75), "doradztwo": ("Doradztwo", 75)}
# każdy awans = jedno spotkanie gwaranckie w tygodniu więcej; Trainee i asystenci nie są gwarantami
LADDER = {"trainee": 0, "asystent": 0, "consultant": 1, "consultant ii": 2, "planner": 3, "senior planner": 4,
          "vip planner": 5, "vip planner ii": 6}
MGR_FULL, MGR_PART = 8, 5
STATUS = {"czeka": "czeka na akceptację gwaranta", "potwierdzone": "potwierdzone", "odrzucone": "gwarant nie może",
          "anulowane": "anulowane", "wygaslo": "bez odpowiedzi — wygasło"}
ACTIVE = ("czeka", "potwierdzone")
DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
DAYS_SHORT = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]
MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października",
          "listopada", "grudnia"]

# Struktura zespołu NIE leży w repozytorium (dane osobowe współpracowników): czytam ją z data/dodatki/gwaranci/struktura.json
# {"osoby": [{"imie_nazwisko": "...", "stanowisko": "Planner", "przelozony": "Imię Nazwisko", "pelny_etat": false, "admin": false}, ...]}
STRUCTURE_FILE = "struktura.json"


# ================================================================ drobiazgi

def plain(s):
    s = unicodedata.normalize("NFD", str(s or "").lower()).replace("ł", "l")
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", plain(name)).strip("-")


def is_manager(position):
    return bool(re.match(r"^\s*(m[1-9]|d[1-9]|director|dyrektor)", plain(position)))


def ladder(position):
    p = plain(position).strip()
    p = re.sub(r"\s+", " ", p)
    return LADDER.get(p, 0)


def max_limit(person):
    """Najwięcej spotkań gwaranckich w tygodniu: menedżer 8 (pełny etat) / 5, reszta wg awansów."""
    if is_manager(person["stanowisko"]):
        return MGR_FULL if person["pelny_etat"] else MGR_PART
    return ladder(person["stanowisko"])


def can_guarantee(person):
    return max_limit(person) > 0


def hm(m):
    return f"{m // 60}:{m % 60:02d}"


def dur(m):
    h, r = divmod(int(m), 60)
    return f"{h} h {r} min" if h and r else (f"{h} h" if h else f"{r} min")


def fdate(d):
    return f"{DAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]}"


def now(ctx=None):
    with contextlib.suppress(Exception):
        if ctx is not None:
            v = ctx.now()
            if isinstance(v, dt.datetime):
                return v.astimezone(TZ)
    return dt.datetime.now(TZ)


def iso(t):
    return t.astimezone(TZ).isoformat(timespec="minutes")


def parse(s):
    return dt.datetime.fromisoformat(s).astimezone(TZ)


def week_start(d):
    d = d.date() if isinstance(d, dt.datetime) else d
    return d - dt.timedelta(days=d.weekday())


# ================================================================ baza

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS osoby (
    id TEXT PRIMARY KEY, imie_nazwisko TEXT NOT NULL, stanowisko TEXT NOT NULL DEFAULT 'Trainee',
    przelozony TEXT NOT NULL DEFAULT '', pelny_etat INTEGER NOT NULL DEFAULT 0, email TEXT NOT NULL DEFAULT '',
    telefon TEXT NOT NULL DEFAULT '', token TEXT NOT NULL, aktywna INTEGER NOT NULL DEFAULT 1, dodano TEXT NOT NULL,
    admin INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS gwaranci (
    osoba TEXT PRIMARY KEY, kalendarze TEXT NOT NULL DEFAULT '[]', dostepnosc TEXT NOT NULL DEFAULT '[]',
    limit_tyg INTEGER NOT NULL DEFAULT 0, gotowe INTEGER NOT NULL DEFAULT 0, wstrzymany INTEGER NOT NULL DEFAULT 0,
    odczyt TEXT NOT NULL DEFAULT '', blad TEXT NOT NULL DEFAULT '', zmieniono TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS zajetosc (osoba TEXT NOT NULL, od TEXT NOT NULL, do TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS zajetosc_osoba ON zajetosc(osoba);
CREATE TABLE IF NOT EXISTS rezerwacje (
    id INTEGER PRIMARY KEY AUTOINCREMENT, adept TEXT NOT NULL, gwarant TEXT NOT NULL, typ TEXT NOT NULL,
    start TEXT NOT NULL, minuty INTEGER NOT NULL, miejsce TEXT NOT NULL DEFAULT 'online', miejsce_opis TEXT NOT NULL DEFAULT '',
    notatka TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'czeka', poziom INTEGER NOT NULL DEFAULT 3,
    kategoria TEXT NOT NULL DEFAULT '', token TEXT NOT NULL, uid TEXT NOT NULL, sekwencja INTEGER NOT NULL DEFAULT 0,
    utworzono TEXT NOT NULL, decyzja TEXT NOT NULL DEFAULT '', przypomniano INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS prosby (
    id INTEGER PRIMARY KEY AUTOINCREMENT, imie_nazwisko TEXT NOT NULL, email TEXT NOT NULL, telefon TEXT NOT NULL DEFAULT '',
    przelozony TEXT NOT NULL DEFAULT '', utworzono TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'nowa');
"""


def db(ctx):
    con = sqlite3.connect(ctx.folder() / "gwaranci.sqlite3", timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM osoby LIMIT 1").fetchone():
        seed(con, ctx.folder() / STRUCTURE_FILE)
    return con


def meta_get(c, k, default=""):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return r["v"] if r else default


def meta_set(c, k, v):
    c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    c.commit()


def seed(c, path):
    """Pierwsze uruchomienie: osoby ze struktura.json (po kolei — przełożony zawsze przed podwładnym)."""
    with contextlib.suppress(FileNotFoundError):
        rows = json.loads(path.read_text(encoding="utf-8")).get("osoby", [])
        import_people(c, rows)


def import_people(c, rows, update=False):
    """Dopisuje nowe osoby; z update=True poprawia też stanowisko, przełożonego, etat i uprawnienia już istniejących."""
    stamp = dt.datetime.now(TZ).isoformat(timespec="seconds")
    n = 0
    for r in rows:
        name = " ".join(str(r.get("imie_nazwisko", "")).split())
        if not name:
            continue
        boss = slug(r.get("przelozony", "")) if r.get("przelozony") else ""
        if update and person(c, slug(name)):
            c.execute("UPDATE osoby SET stanowisko=?, przelozony=?, pelny_etat=?, admin=?, aktywna=1 WHERE id=?",
                      (r.get("stanowisko", "Trainee"), boss, int(bool(r.get("pelny_etat"))), int(bool(r.get("admin"))), slug(name)))
            n += 1
            continue
        cur = c.execute("INSERT OR IGNORE INTO osoby(id,imie_nazwisko,stanowisko,przelozony,pelny_etat,admin,email,token,dodano) VALUES(?,?,?,?,?,?,?,?,?)",
                        (slug(name), name, r.get("stanowisko", "Trainee"), boss, int(bool(r.get("pelny_etat"))), int(bool(r.get("admin"))),
                         r.get("email", ""), secrets.token_urlsafe(18), stamp))
        n += cur.rowcount
    c.commit()
    return n


def person(c, pid):
    r = c.execute("SELECT * FROM osoby WHERE id=?", (pid,)).fetchone()
    return dict(r) if r else None


def people(c):
    return {r["id"]: dict(r) for r in c.execute("SELECT * FROM osoby WHERE aktywna=1")}


def find_person(c, text):
    """Osoba po imieniu i nazwisku (w dowolnej kolejności, bez polskich znaków), albo po samym nazwisku, gdy jednoznaczne."""
    words = plain(text).split()
    if not words:
        return None
    all_ = list(people(c).values())
    for p in all_:
        n = plain(p["imie_nazwisko"]).split()
        if sorted(n) == sorted(words):
            return p
    hits = [p for p in all_ if all(w in plain(p["imie_nazwisko"]).split() for w in words)]
    return hits[0] if len(hits) == 1 else None


def by_token(c, token):
    r = c.execute("SELECT * FROM osoby WHERE token=? AND aktywna=1", (token,)).fetchone()
    return dict(r) if r else None


def add_person(c, name, position="Trainee", boss="", email="", full=False):
    pid = slug(name)
    if person(c, pid):
        raise ValueError(f"{name} już jest w strukturze.")
    bossp = find_person(c, boss) if boss else None
    if boss and not bossp:
        raise ValueError(f"Nie znam przełożonego „{boss}”.")
    c.execute("INSERT INTO osoby(id,imie_nazwisko,stanowisko,przelozony,pelny_etat,email,token,dodano) VALUES(?,?,?,?,?,?,?,?)",
              (pid, name.strip(), position.strip(), bossp["id"] if bossp else "", int(full), email.strip(),
               secrets.token_urlsafe(18), dt.datetime.now(TZ).isoformat(timespec="seconds")))
    c.commit()
    return person(c, pid)


def set_position(c, pid, position):
    c.execute("UPDATE osoby SET stanowisko=? WHERE id=?", (position.strip(), pid))
    g = c.execute("SELECT limit_tyg FROM gwaranci WHERE osoba=?", (pid,)).fetchone()
    p = person(c, pid)
    if g and g["limit_tyg"] > max_limit(p):
        c.execute("UPDATE gwaranci SET limit_tyg=? WHERE osoba=?", (max_limit(p), pid))
    c.commit()
    return p


# ================================================================ struktura

def uplines(ppl, pid):
    out, seen = [], set()
    cur = ppl.get(pid, {}).get("przelozony", "")
    while cur and cur in ppl and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = ppl[cur]["przelozony"]
    return out


def nearest_manager(ppl, pid):
    return next((u for u in uplines(ppl, pid) if is_manager(ppl[u]["stanowisko"])), "")


def structure_of(ppl, pid):
    """Struktura = najbliższy menedżer (M1 i wyżej) — ten, kto ma międzyprowizję. Menedżer to sam sobie struktura."""
    if pid in ppl and is_manager(ppl[pid]["stanowisko"]):
        return pid
    return nearest_manager(ppl, pid)


def tier(ppl, g, a):
    """0 bezpośredni menedżer, 1 pośredni menedżer, 2 gwarant z tej samej struktury, 3 gwarant z innej struktury."""
    if g == nearest_manager(ppl, a):
        return 0
    if is_manager(ppl[g]["stanowisko"]) and g in uplines(ppl, a):
        return 1
    if structure_of(ppl, g) == structure_of(ppl, a):
        return 2
    return 3


def category(ppl, g, a):
    if is_manager(ppl[g]["stanowisko"]) and g in uplines(ppl, a):
        return "wlasna_linia"
    return "w_strukturze" if structure_of(ppl, g) == structure_of(ppl, a) else "przysluga"


# ================================================================ gwaranci i zajętość

def guarantor(c, pid):
    r = c.execute("SELECT * FROM gwaranci WHERE osoba=?", (pid,)).fetchone()
    if not r:
        return None
    g = dict(r)
    g["kalendarze"] = json.loads(g["kalendarze"] or "[]")
    g["dostepnosc"] = json.loads(g["dostepnosc"] or "[]")
    return g


def save_guarantor(c, pid, **fields):
    if not c.execute("SELECT 1 FROM gwaranci WHERE osoba=?", (pid,)).fetchone():
        c.execute("INSERT INTO gwaranci(osoba) VALUES(?)", (pid,))
    for k, v in fields.items():
        if k in ("kalendarze", "dostepnosc"):
            v = json.dumps(v, ensure_ascii=False)
        c.execute(f"UPDATE gwaranci SET {k}=? WHERE osoba=?", (v, pid))
    c.execute("UPDATE gwaranci SET zmieniono=? WHERE osoba=?", (dt.datetime.now(TZ).isoformat(timespec="seconds"), pid))
    c.commit()


def ready_guarantors(c):
    ppl = people(c)
    out = {}
    for r in c.execute("SELECT osoba FROM gwaranci WHERE gotowe=1 AND wstrzymany=0"):
        if r["osoba"] in ppl and can_guarantee(ppl[r["osoba"]]):
            out[r["osoba"]] = guarantor(c, r["osoba"])
    return out


def clean_calendar_url(url):
    """Akceptuję tajny adres iCal z Google (i każdy inny link .ics / webcal); webcal:// zamieniam na https://."""
    u = (url or "").strip().strip("<>\"' ")
    u = re.sub(r"^webcal://", "https://", u, flags=re.I)
    if not re.match(r"^https://", u, flags=re.I):
        return ""
    return u


def fetch_ics(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Sebastian-Gwaranci/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(15 * 1024 * 1024)
    text = data.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text[:2000]:
        raise ValueError("To nie jest link do kalendarza (brak danych iCal). Skopiuj „Tajny adres w formacie iCal”.")
    return text


def busy_blocks(ics_text, start, end):
    """Zajęte godziny [(od, do)] między start i end. Pomijam wydarzenia „Dostępny” (TRANSP:TRANSPARENT) i odwołane."""
    import icalendar
    import recurring_ical_events
    cal = icalendar.Calendar.from_ical(ics_text)
    out = []
    for ev in recurring_ical_events.of(cal).between(start, end):
        if str(ev.get("STATUS", "")).upper() == "CANCELLED" or str(ev.get("TRANSP", "OPAQUE")).upper() == "TRANSPARENT":
            continue
        a = ev.decoded("DTSTART")
        if isinstance(a, dt.datetime):
            a = a.replace(tzinfo=a.tzinfo or TZ).astimezone(TZ)
            b = None
            with contextlib.suppress(Exception):
                if ev.get("DTEND") is not None:
                    b = ev.decoded("DTEND")
                    b = b.replace(tzinfo=b.tzinfo or TZ).astimezone(TZ)
                elif ev.get("DURATION") is not None:
                    b = a + ev.decoded("DURATION")
            b = b or a + dt.timedelta(hours=1)
        else:                                                  # wydarzenie całodniowe oznaczone jako „Zajęty”
            a = dt.datetime.combine(a, dt.time(), TZ)
            b = dt.datetime.combine(ev.decoded("DTEND") if ev.get("DTEND") is not None else a.date() + dt.timedelta(days=1), dt.time(), TZ)
        if b > a:
            out.append((a, b))
    return out


def refresh_busy(c, pid, days=40, fetch=None, when=None):
    """Czyta wszystkie kalendarze gwaranta i zapisuje same godziny zajętości. Zwraca (liczba bloków, błąd)."""
    fetch = fetch or fetch_ics
    g = guarantor(c, pid)
    if not g or not g["kalendarze"]:
        return 0, "brak podłączonego kalendarza"
    t0 = (when or dt.datetime.now(TZ)) - dt.timedelta(days=1)
    t1 = t0 + dt.timedelta(days=days)
    blocks, errors = [], []
    for url in g["kalendarze"]:
        try:
            blocks += busy_blocks(fetch(url), t0, t1)
        except Exception as e:
            errors.append(str(e)[:160] or type(e).__name__)
    if errors and not blocks:
        c.execute("UPDATE gwaranci SET blad=? WHERE osoba=?", ("; ".join(errors), pid))
        c.commit()
        return 0, "; ".join(errors)
    c.execute("DELETE FROM zajetosc WHERE osoba=?", (pid,))
    c.executemany("INSERT INTO zajetosc(osoba,od,do) VALUES(?,?,?)", [(pid, iso(a), iso(b)) for a, b in blocks])
    c.execute("UPDATE gwaranci SET odczyt=?, blad=? WHERE osoba=?",
              (dt.datetime.now(TZ).isoformat(timespec="seconds"), "; ".join(errors), pid))
    c.commit()
    return len(blocks), "; ".join(errors)


def busy_of(c, pid):
    return [(parse(r["od"]), parse(r["do"])) for r in c.execute("SELECT od, do FROM zajetosc WHERE osoba=?", (pid,))]


# ================================================================ terminy i przydział

def bookings_of(c, pid, statuses=ACTIVE):
    q = "SELECT * FROM rezerwacje WHERE gwarant=? AND status IN (%s)" % ",".join("?" * len(statuses))
    return [dict(r) for r in c.execute(q, (pid, *statuses))]


def week_load(c, pid, day):
    """(liczba spotkań, minuty) gwaranta w tygodniu dnia `day` — liczę czekające i potwierdzone."""
    ws = week_start(day)
    n = mins = 0
    for b in bookings_of(c, pid):
        if week_start(parse(b["start"])) == ws:
            n += 1
            mins += b["minuty"]
    return n, mins


class Snapshot:
    """Jedno spojrzenie na bazę na potrzeby liczenia wolnych terminów (żeby nie pytać bazy setki razy)."""

    def __init__(self, c, settings):
        self.ppl = people(c)
        self.g = ready_guarantors(c)
        self.busy = {p: busy_of(c, p) for p in self.g}
        self.book = {p: bookings_of(c, p) for p in self.g}
        self.total = {p: sum(b["minuty"] for b in c.execute("SELECT minuty FROM rezerwacje WHERE gwarant=? AND status='potwierdzone'", (p,)))
                      for p in self.g}
        self.buffer = int(settings.get("bufor_min", 15))

    def load(self, p, day):
        ws = week_start(day)
        bs = [b for b in self.book[p] if week_start(parse(b["start"])) == ws]
        return len(bs), sum(b["minuty"] for b in bs)

    def free(self, p, a, start, minutes):
        if p == a or p not in self.g:
            return False
        g = self.g[p]
        end = start + dt.timedelta(minutes=minutes)
        wd, m0 = start.weekday(), start.hour * 60 + start.minute
        if not any(int(d) == wd and int(x) <= m0 and m0 + minutes <= int(y) for d, x, y in g["dostepnosc"]):
            return False
        pad = dt.timedelta(minutes=self.buffer)
        if any(start < b + pad and end + pad > a_ for a_, b in self.busy[p]):
            return False
        for b in self.book[p]:
            bs = parse(b["start"])
            if start < bs + dt.timedelta(minutes=b["minuty"]) + pad and end + pad > bs:
                return False
        n, _ = self.load(p, start)
        return n < int(g["limit_tyg"] or 0)

    def candidates(self, a, start, minutes):
        out = []
        for p in self.g:
            if self.free(p, a, start, minutes):
                n, mins = self.load(p, start)
                out.append({"gwarant": p, "poziom": tier(self.ppl, p, a), "minuty_tyg": mins, "minuty_razem": self.total.get(p, 0)})
        out.sort(key=lambda x: (x["poziom"], x["minuty_tyg"], x["minuty_razem"], self.ppl[x["gwarant"]]["imie_nazwisko"]))
        return out


def slots(c, settings, a, typ, day, when=None, snap=None):
    """Wolne godziny dnia: [(start, kandydaci)] — co 30 min, od wyprzedzenia do końca okna."""
    when = when or dt.datetime.now(TZ)
    snap = snap or Snapshot(c, settings)
    minutes = TYPES[typ][1]
    first = when + dt.timedelta(hours=int(settings.get("wyprzedzenie_h", 24)))
    last_day = when.date() + dt.timedelta(days=int(settings.get("okno_dni", 35)))
    if day > last_day:
        return []
    out = []
    for m in range(int(settings.get("od_godz", 7)) * 60, int(settings.get("do_godz", 21)) * 60 - minutes + 1, 30):
        start = dt.datetime.combine(day, dt.time(m // 60, m % 60), TZ)
        if start < first:
            continue
        cand = snap.candidates(a, start, minutes)
        if cand:
            out.append((start, cand))
    return out


def days_with_slots(c, settings, a, typ, when=None):
    when = when or dt.datetime.now(TZ)
    snap = Snapshot(c, settings)
    out = {}
    for i in range(int(settings.get("okno_dni", 35)) + 1):
        d = when.date() + dt.timedelta(days=i)
        s = slots(c, settings, a, typ, d, when, snap)
        if s:
            out[d] = {"n": len(s), "menedzer": any(x[1][0]["poziom"] == 0 for x in s)}
    return out


def book(c, settings, a, typ, start, place="online", place_text="", note="", when=None):
    """Rezerwuje: jeszcze raz sprawdza wolny termin (świeża zajętość) i przydziela gwaranta. Zwraca rezerwację."""
    minutes = TYPES[typ][1]
    cand = Snapshot(c, settings).candidates(a, start, minutes)
    if start < (when or dt.datetime.now(TZ)) + dt.timedelta(hours=int(settings.get("wyprzedzenie_h", 24))) or not cand:
        raise ValueError("Ten termin właśnie przestał być wolny. Wybierz proszę inny.")
    ppl = people(c)
    g = cand[0]["gwarant"]
    tok = secrets.token_urlsafe(18)
    uid = f"gwaranci-{secrets.token_hex(8)}@sebastian"
    cur = c.execute("INSERT INTO rezerwacje(adept,gwarant,typ,start,minuty,miejsce,miejsce_opis,notatka,status,poziom,kategoria,token,uid,utworzono)"
                    " VALUES(?,?,?,?,?,?,?,?,'czeka',?,?,?,?,?)",
                    (a, g, typ, iso(start), minutes, place, place_text.strip()[:200], note.strip()[:500], cand[0]["poziom"],
                     category(ppl, g, a), tok, uid, (when or dt.datetime.now(TZ)).isoformat(timespec="seconds")))
    c.commit()
    return booking(c, cur.lastrowid)


def booking(c, bid):
    r = c.execute("SELECT * FROM rezerwacje WHERE id=?", (bid,)).fetchone()
    return dict(r) if r else None


def booking_by_token(c, tok):
    r = c.execute("SELECT * FROM rezerwacje WHERE token=?", (tok,)).fetchone()
    return dict(r) if r else None


def set_status(c, bid, status):
    c.execute("UPDATE rezerwacje SET status=?, decyzja=?, sekwencja=sekwencja+1 WHERE id=?",
              (status, dt.datetime.now(TZ).isoformat(timespec="seconds"), bid))
    c.commit()
    return booking(c, bid)


# ================================================================ poczta (skrzynka Sebastiana, Gmail z hasłem aplikacji)

def mailbox(ctx, c):
    """(adres, hasło aplikacji) skrzynki Sebastiana: własne ustawienie dodatku albo to z dodatku Rekrutacja."""
    addr = meta_get(c, "poczta") or ""
    pwd = None
    with contextlib.suppress(Exception):
        pwd = ctx.secret("poczta")
    if not (addr and pwd):
        with contextlib.suppress(Exception):
            rc = sqlite3.connect(ctx.folder().parent / "rekrutacja" / "rekrutacja.sqlite3", timeout=10)
            rc.row_factory = sqlite3.Row
            r = rc.execute("SELECT v FROM meta WHERE k='poczta_sebastian'").fetchone()
            rc.close()
            addr = addr or (r["v"] if r else "")
        if sys.platform == "darwin":
            with contextlib.suppress(Exception):
                r = subprocess.run(["security", "find-generic-password", "-s", "sebastian-rekrutacja", "-a", "sebastian", "-w"],
                                   capture_output=True, text=True, timeout=10)
                pwd = pwd or (r.stdout.strip() if r.returncode == 0 else None)
    return (addr or ""), (pwd or "")


def _event_ics(ctx, c, b, method="REQUEST", with_adept=False, accepted=False):
    ppl = people(c)
    g, a = ppl[b["gwarant"]], ppl[b["adept"]]
    addr, _ = mailbox(ctx, c)
    sender = ctx.settings().get("nadawca", "Sebastian · Asystent Krakowa inPartners")
    start = parse(b["start"])
    end = start + dt.timedelta(minutes=b["minuty"])
    z = lambda t: t.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    esc = lambda s: str(s).replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")
    title = f"Spotkanie gwaranckie · {TYPES[b['typ']][0]} · {a['imie_nazwisko']} + {g['imie_nazwisko']}"
    lines = ["BEGIN:VCALENDAR", "PRODID:-//Sebastian//Gwaranci//PL", "VERSION:2.0", "CALSCALE:GREGORIAN", f"METHOD:{method}",
             "BEGIN:VEVENT", f"UID:{b['uid']}", f"SEQUENCE:{b['sekwencja']}", f"DTSTAMP:{z(dt.datetime.now(TZ))}",
             f"DTSTART:{z(start)}", f"DTEND:{z(end)}", f"SUMMARY:{esc(title)}",
             f"DESCRIPTION:{esc(description(ctx, c, b))}", f"LOCATION:{esc(place_label(b))}",
             f"STATUS:{'CANCELLED' if method == 'CANCEL' else 'CONFIRMED'}", "TRANSP:OPAQUE",
             f"ORGANIZER;CN={esc(sender)}:mailto:{addr}",
             f"ATTENDEE;CN={esc(g['imie_nazwisko'])};ROLE=REQ-PARTICIPANT;PARTSTAT={'ACCEPTED' if accepted else 'NEEDS-ACTION'};RSVP=TRUE:mailto:{g['email']}"]
    if with_adept and a.get("email"):
        lines.append(f"ATTENDEE;CN={esc(a['imie_nazwisko'])};ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;RSVP=FALSE:mailto:{a['email']}")
    lines += ["BEGIN:VALARM", "TRIGGER:-PT60M", "ACTION:DISPLAY", "DESCRIPTION:Spotkanie gwaranckie za godzinę", "END:VALARM",
              "END:VEVENT", "END:VCALENDAR"]
    out = []
    for ln in lines:                                           # zawijanie linii co 73 bajty (RFC 5545)
        raw = ln.encode("utf-8")
        while len(raw) > 73:
            cut = 73
            while (raw[cut] & 0xC0) == 0x80:
                cut -= 1
            out.append(raw[:cut].decode("utf-8"))
            raw = b" " + raw[cut:]
        out.append(raw.decode("utf-8"))
    return "\r\n".join(out) + "\r\n"


def place_label(b):
    return f"Na miejscu: {b['miejsce_opis'] or 'do ustalenia'}" if b["miejsce"] == "miejsce" else "Online (link prześle gwarant)"


def description(ctx, c, b):
    ppl = people(c)
    g, a = ppl[b["gwarant"]], ppl[b["adept"]]
    start = parse(b["start"])
    lines = [f"Typ spotkania: {TYPES[b['typ']][0]} ({dur(b['minuty'])})",
             f"Kiedy: {fdate(start)}, {hm(start.hour * 60 + start.minute)}–{hm(start.hour * 60 + start.minute + b['minuty'])}",
             f"Gdzie: {place_label(b)}", "",
             f"Adept: {a['imie_nazwisko']}, {a['stanowisko']}" + (f", tel. {a['telefon']}" if a.get("telefon") else "") + (f", {a['email']}" if a.get("email") else ""),
             f"Gwarant: {g['imie_nazwisko']}, {g['stanowisko']}"]
    if b.get("notatka"):
        lines += ["", f"Od adepta: {b['notatka']}"]
    lines += ["", "Dla gwaranta: zaakceptuj lub odrzuć w ciągu 24 h. Przy spotkaniu na miejscu akceptacja oznacza, że możesz tam być.",
              "Dla adepta: przygotuj dane klienta i materiały. Po spotkaniu wypełnij feedback po usłudze i wyślij gwarantowi kilka zdań: "
              "czego się nauczyłeś/nauczyłaś i za co jesteś wdzięczny/wdzięczna.", "",
              "Zarezerwowano przez Sebastiana — asystenta Krakowa inPartners."]
    return "\n".join(lines)


def html_mail(title, intro, rows=(), buttons=(), outro=""):
    """Prosty, elegancki mail w stylu Apple: jasne tło, karta, duże przyciski."""
    e = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    rows_html = "".join(f'<tr><td style="padding:6px 0;color:#6e6e73;width:110px;vertical-align:top">{e(k)}</td>'
                        f'<td style="padding:6px 0;color:#1d1d1f">{e(v)}</td></tr>' for k, v in rows)
    btn_html = "".join(f'<a href="{u}" style="display:inline-block;margin:6px 8px 0 0;padding:12px 20px;border-radius:12px;'
                       f'text-decoration:none;font-weight:600;background:{"#1d1d1f" if i == 0 else "#f2f2f7"};'
                       f'color:{"#ffffff" if i == 0 else "#1d1d1f"}">{e(t)}</a>' for i, (t, u) in enumerate(buttons))
    return (f'<div style="background:#f5f5f7;padding:28px 12px;font-family:-apple-system,BlinkMacSystemFont,\'SF Pro Text\',Inter,Segoe UI,Arial,sans-serif">'
            f'<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:18px;padding:28px">'
            f'<div style="font-size:13px;color:#6e6e73;margin-bottom:6px">Sebastian · Asystent Krakowa inPartners</div>'
            f'<div style="font-size:22px;font-weight:700;color:#1d1d1f;margin-bottom:12px">{e(title)}</div>'
            f'<div style="font-size:15px;line-height:1.5;color:#1d1d1f">{intro}</div>'
            f'<table style="width:100%;margin:16px 0;font-size:14px;border-top:1px solid #e5e5ea;border-bottom:1px solid #e5e5ea">{rows_html}</table>'
            f'<div>{btn_html}</div>'
            f'<div style="font-size:13px;line-height:1.5;color:#6e6e73;margin-top:18px">{outro}</div></div></div>')


def send_mail(ctx, c, to, subject, text, html="", ics="", method="REQUEST"):
    addr, pwd = mailbox(ctx, c)
    if not addr or not pwd:
        raise RuntimeError("Brak skrzynki Sebastiana — podłącz: python sebastian.py dodatek gwaranci poczta")
    if not EMAIL_OK.match(to or ""):
        raise RuntimeError(f"Brak poprawnego maila odbiorcy ({to or 'pusty'}).")
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = formataddr((ctx.settings().get("nadawca", "Sebastian · Asystent Krakowa inPartners"), addr))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="sebastian.local")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    if ics:
        msg.add_alternative(ics.encode("utf-8"), maintype="text", subtype="calendar", params={"method": method, "charset": "utf-8"})
        msg.add_attachment(ics.encode("utf-8"), maintype="application", subtype="ics", filename="zaproszenie.ics")
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
    try:
        s.starttls(context=ssl.create_default_context())
        s.login(addr, "".join(pwd.split()))
        s.send_message(msg)
    finally:
        with contextlib.suppress(Exception):
            s.quit()


def check_replies(ctx, c, since_days=14):
    """Czyta odpowiedzi na zaproszenia (Tak / Nie z Gmaila) w skrzynce Sebastiana — tylko podgląd, niczego nie oznacza
    jako przeczytane. Zwraca [(rezerwacja, 'tak'|'nie')]."""
    import icalendar
    addr, pwd = mailbox(ctx, c)
    if not addr or not pwd:
        return []
    last = int(meta_get(c, "imap_uid", "0") or 0)
    out = []
    box = imaplib.IMAP4_SSL("imap.gmail.com", timeout=40)
    try:
        box.login(addr, "".join(pwd.split()))
        box.select("INBOX", readonly=True)
        since = (dt.date.today() - dt.timedelta(days=since_days)).strftime("%d-%b-%Y")
        typ, data = box.uid("SEARCH", None, f'(SINCE {since})')
        uids = [int(x) for x in (data[0] or b"").split() if int(x) > last]
        for uid in uids[-200:]:
            typ, msgdata = box.uid("FETCH", str(uid), "(BODY.PEEK[])")
            last = max(last, uid)
            raw = next((p[1] for p in msgdata if isinstance(p, tuple)), b"")
            if b"text/calendar" not in raw and b".ics" not in raw:
                continue
            import email as _email
            msg = _email.message_from_bytes(raw)
            for part in msg.walk():
                if part.get_content_type() not in ("text/calendar", "application/ics"):
                    continue
                with contextlib.suppress(Exception):
                    cal = icalendar.Calendar.from_ical(part.get_payload(decode=True))
                    if str(cal.get("METHOD", "")).upper() != "REPLY":
                        continue
                    for ev in cal.walk("VEVENT"):
                        b = c.execute("SELECT * FROM rezerwacje WHERE uid=?", (str(ev.get("UID", "")),)).fetchone()
                        if not b:
                            continue
                        att = ev.get("ATTENDEE")
                        att = att[0] if isinstance(att, list) else att
                        stat = str(att.params.get("PARTSTAT", "")).upper() if att is not None else ""
                        if stat == "ACCEPTED":
                            out.append((dict(b), "tak"))
                        elif stat == "DECLINED":
                            out.append((dict(b), "nie"))
    finally:
        with contextlib.suppress(Exception):
            box.logout()
        meta_set(c, "imap_uid", last)
    return out
