"""Rekrutacja — wspólny rdzeń dodatku: baza, baza faktów, sekrety, drobne narzędzia.

Wszystko, co dotyczy Agi (fakty, zdjęcie, dokumenty, baza), leży w data/dodatki/rekrutacja/ — nigdy w repozytorium.
"""
import contextlib, datetime as dt, json, os, re, sqlite3, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMAIL_OK = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")

STATUS = {
    "nowa": "czeka na przygotowanie",
    "przygotowywanie": "Sebastian przygotowuje dokumenty",
    "do_zatwierdzenia": "do zatwierdzenia",
    "do_sprawdzenia": "do sprawdzenia",
    "do_uzupelnienia": "brakuje danych",
    "zatwierdzona": "w kolejce do wysyłki",
    "wysylanie": "wysyłam",
    "wyslana": "wysłana",
    "wyslana_recznie": "wysłana przez formularz",
    "zaproszenie": "zaproszenie na rozmowę",
    "rozmowa": "po rozmowie",
    "oferta": "oferta pracy",
    "odmowa": "odmowa",
    "odrzucona": "pominięta",
    "duplikat": "duplikat",
    "formularz": "do wysłania przez formularz",
    "pytanie": "pracodawca pyta",
    "blad": "błąd",
}
OPEN = ("nowa", "przygotowywanie", "do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "zatwierdzona")
SENT = ("wyslana", "wyslana_recznie", "pytanie", "zaproszenie", "rozmowa", "oferta", "odmowa")
TODO = ("do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "formularz", "blad")
KRAKOW_AREA = ["krakow", "wieliczka", "niepolomice", "skawina", "zabierzow", "zielonki", "krzeszowice", "myslenice", "bochnia",
               "olkusz", "proszowice", "slomniki", "miechow", "kalwaria", "dobczyce", "liszki", "mogilany", "swiatniki", "michalowice",
               "kocmyrzow", "igolomia", "klaj", "chrzanow", "trzebinia", "alwernia", "wadowice", "biskupice", "gdow", "sulkowice",
               "jerzmanowice", "wielka wies", "modlnica", "batowice", "rybna", "czernichow", "tyniec", "brzesko", "bukowno",
               "sulowice", "lanckorona", "pcim", "raciechowice", "kokotow", "prusy", "zelkow", "radziszow", "libertow"]
AREA_KM = {"krakow": 0, "wieliczka": 15, "zielonki": 10, "zabierzow": 15, "skawina": 15, "liszki": 15, "mogilany": 15, "swiatniki": 15,
           "michalowice": 12, "kocmyrzow": 15, "igolomia": 20, "niepolomice": 20, "modlnica": 10, "batowice": 8, "tyniec": 10,
           "czernichow": 20, "wielka wies": 12, "rybna": 20, "biskupice": 20, "radziszow": 20, "libertow": 10, "kokotow": 15, "prusy": 15,
           "zelkow": 12, "krzeszowice": 25, "sulkowice": 25, "dobczyce": 28, "kalwaria": 30, "myslenice": 30, "gdow": 30, "slomniki": 30,
           "proszowice": 30, "klaj": 25, "lanckorona": 35, "jerzmanowice": 25, "alwernia": 30, "raciechowice": 35, "pcim": 40,
           "bochnia": 40, "olkusz": 40, "miechow": 40, "trzebinia": 35, "chrzanow": 40, "bukowno": 40, "sulowice": 25, "wadowice": 45, "brzesko": 50}
REMOTE = ["zdaln", "remote", "home office", "z domu", "hybryd", "cala polska", "dowolna lokalizacja"]


def in_area(place, km=50):
    """Kraków i okolice (ok. 50 km) albo praca zdalna. Pusta lokalizacja = nie wiadomo (True)."""
    p = plain(place)
    if not p.strip():
        return True
    if any(w in p for w in REMOTE):
        return True
    return any(w in p for w, d in AREA_KM.items() if d <= km)

RODO = ("Wyrażam zgodę na przetwarzanie moich danych osobowych dla potrzeb niezbędnych do realizacji procesu rekrutacji "
        "zgodnie z Rozporządzeniem Parlamentu Europejskiego i Rady (UE) 2016/679 z dnia 27 kwietnia 2016 r. w sprawie "
        "ochrony osób fizycznych w związku z przetwarzaniem danych osobowych i w sprawie swobodnego przepływu takich "
        "danych oraz uchylenia dyrektywy 95/46/WE (RODO).")

TOOLS = ["Word", "Excel", "PowerPoint", "Outlook", "Microsoft Teams", "Dokumenty i Arkusze Google", "Canva",
         "ChatGPT i narzędzia AI", "Zoom / Google Meet", "Systemy CRM", "Systemy dokumentacji medycznej",
         "Trello / Asana", "Media społecznościowe (obsługa profili)", "WordPress"]
LEVELS = ["", "podstawowy", "dobry", "bardzo dobry"]
def is_consent(text):
    """Czy tekst to naprawdę klauzula zgody (a nie np. informacja o przetwarzaniu danych przez pracodawcę)."""
    p = plain(text)
    return bool(len(p) >= 60 and re.search(r"\b(wyrazam|udzielam) zgod", p) and "przetwarz" in p and re.search(r"danych osobowych|moich danych", p))


def consent_clause(firma="", custom=""):
    """Klauzula do CV: zgoda pracodawcy, jeśli to naprawdę zgoda; w przeciwnym razie szeroka klauzula domyślna."""
    if custom and is_consent(custom):
        return custom.strip()
    who = f" przez {firma.strip()}" if firma and firma.strip() else ""
    return (f"Wyrażam zgodę na przetwarzanie moich danych osobowych{who} dla potrzeb niezbędnych do realizacji obecnego procesu "
            "rekrutacji, a także przyszłych procesów rekrutacyjnych, zgodnie z Rozporządzeniem Parlamentu Europejskiego i Rady (UE) "
            "2016/679 z dnia 27 kwietnia 2016 r. w sprawie ochrony osób fizycznych w związku z przetwarzaniem danych osobowych i w sprawie "
            "swobodnego przepływu takich danych oraz uchylenia dyrektywy 95/46/WE (RODO).")


WANT = ["koordynacja projektów i zadań", "administracja i back office", "wsparcie zespołu lub zarządu (asysta)",
        "dokumentacja i obieg informacji", "research i analizy", "przygotowanie treści i materiałów",
        "koordynacja wydarzeń i współpracy", "usprawnianie procesów i procedury", "administracja marketingu",
        "sprzedaż i doradztwo", "obsługa klienta (biuro obsługi, recepcja, infolinia)"]
AVOID = ["sprzedaż produktów lub usług", "pozyskiwanie klientów", "cold calling i telemarketing",
         "infolinia i call center", "stała bezpośrednia obsługa klientów lub pacjentów", "obsługa reklamacji"]
SALES_AVOID = list(AVOID)


# ================================================================ baza

def migrate(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS aplikacje(
        id INTEGER PRIMARY KEY, utworzono TEXT, zmieniono TEXT, status TEXT, zrodlo TEXT DEFAULT 'oferta',
        url TEXT DEFAULT '', firma TEXT DEFAULT '', stanowisko TEXT DEFAULT '', miasto TEXT DEFAULT '',
        email TEXT DEFAULT '', tresc TEXT DEFAULT '', klucz TEXT DEFAULT '', ocena INTEGER, ocena_opis TEXT DEFAULT '',
        ostrzezenia TEXT DEFAULT '[]', uwagi TEXT DEFAULT '[]', rodo TEXT DEFAULT '', wybor TEXT DEFAULT '',
        temat TEXT DEFAULT '', mail TEXT DEFAULT '', list TEXT DEFAULT '', cv_plik TEXT DEFAULT '',
        list_plik TEXT DEFAULT '', wyslano TEXT DEFAULT '', message_id TEXT DEFAULT '', blad TEXT DEFAULT '',
        notatka TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS aplikacje_status ON aplikacje(status);
    CREATE INDEX IF NOT EXISTS aplikacje_klucz ON aplikacje(klucz);
    CREATE TABLE IF NOT EXISTS historia(id INTEGER PRIMARY KEY, aplikacja_id INTEGER, kiedy TEXT, co TEXT);
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS zrodla(id INTEGER PRIMARY KEY, typ TEXT, url TEXT UNIQUE, nazwa TEXT DEFAULT '', wlaczone INTEGER DEFAULT 1,
        sprawdzono TEXT DEFAULT '', wynik TEXT DEFAULT '', znalezione INTEGER DEFAULT 0, bledy INTEGER DEFAULT 0, dodano TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS widziane(url TEXT PRIMARY KEY, kiedy TEXT, zrodlo_id INTEGER, tytul TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS firmy(id INTEGER PRIMARY KEY, nazwa TEXT, email TEXT, www TEXT DEFAULT '', opis TEXT DEFAULT '',
        dodano TEXT, uzyta INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS wiadomosci(id INTEGER PRIMARY KEY, uid INTEGER, message_id TEXT, od TEXT, od_nazwa TEXT DEFAULT '',
        temat TEXT, data TEXT, tresc TEXT, aplikacja_id INTEGER, rodzaj TEXT DEFAULT '', wazne INTEGER DEFAULT 0,
        streszczenie TEXT DEFAULT '', termin TEXT DEFAULT '', szkic TEXT DEFAULT '', status TEXT DEFAULT 'nowa', utworzono TEXT,
        references_ TEXT DEFAULT '', wyslano TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS wiadomosci_app ON wiadomosci(aplikacja_id);
    CREATE TABLE IF NOT EXISTS pytania(id INTEGER PRIMARY KEY, aplikacja_id INTEGER, wiadomosc_id INTEGER, pytanie TEXT,
        odpowiedz TEXT DEFAULT '', status TEXT DEFAULT 'otwarte', utworzono TEXT, zamknieto TEXT DEFAULT '');
    """)
    cols = {r[1] for r in c.execute("PRAGMA table_info(aplikacje)")}
    for col in ("kanal", "przypomnienie", "odpowiedz_kiedy", "podziekowanie"):
        if col not in cols:
            c.execute(f"ALTER TABLE aplikacje ADD COLUMN {col} TEXT DEFAULT ''")
    c.commit()


def db(ctx):
    c = ctx.db()
    migrate(c)
    return contextlib.closing(c)


def stamp(ctx):
    return ctx.now().isoformat(timespec="seconds")


def meta_get(c, k, default=""):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return r[0] if r else default


def meta_set(c, k, v):
    c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    c.commit()


def note(c, ctx, aid, what):
    c.execute("INSERT INTO historia(aplikacja_id,kiedy,co) VALUES(?,?,?)", (aid, stamp(ctx), what[:500]))


def set_status(c, ctx, aid, status, **fields):
    fields.update(status=status, zmieniono=stamp(ctx))
    c.execute(f"UPDATE aplikacje SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), aid))
    note(c, ctx, aid, "status: " + STATUS.get(status, status))
    c.commit()


# ================================================================ tekst i klucz duplikatu

def plain(text):
    text = unicodedata.normalize("NFKD", str(text or "").replace("ł", "l").replace("Ł", "L"))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


_FORMS = r"\b(sp\.?\s*z\s*o\.?\s*o\.?|spolka z ograniczona odpowiedzialnoscia|s\.?\s*a\.?|sp\.?\s*k\.?|sp\.?\s*j\.?|p\.?s\.?a\.?|s\.?c\.?|spolka akcyjna)(?=\W|$)"
_NOISE = r"\b(k/m|m/k|k/m/x|praca|oferta pracy|pelny etat|rekrutacja)\b"


def norm(text):
    t = re.sub(_FORMS, " ", plain(text))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()


def dedupe_key(firma, stanowisko, miasto=""):
    f, s = norm(firma), norm(re.sub(_NOISE, " ", re.sub(r"\(?\b[kmx](\s*/\s*[kmx]){1,2}\b\)?", " ", plain(stanowisko))))
    return f"{f}|{s}" if f and s else (f"{f}|*" if f else "")


def norm_url(url):
    u = re.sub(r"[#?].*$", "", str(url or "").strip().lower())
    return re.sub(r"^https?://(www\.)?", "", u).rstrip("/")


def find_duplicate(c, firma, stanowisko, url="", skip_id=0, zrodlo="oferta"):
    """Ta sama oferta (adres albo firma + stanowisko); przy aplikacji spontanicznej — ta sama firma."""
    rows = c.execute("SELECT id,url,klucz,zrodlo,status FROM aplikacje WHERE id<>? AND status NOT IN ('duplikat','odrzucona')", (skip_id,)).fetchall()
    key, nu = dedupe_key(firma, stanowisko), norm_url(url)
    for r in rows:
        if nu and norm_url(r["url"]) == nu:
            return r["id"]
        if key and r["klucz"] == key:
            return r["id"]
        if zrodlo == "spontaniczna" and r["zrodlo"] == "spontaniczna" and norm(firma) and r["klucz"].split("|")[0] == norm(firma):
            return r["id"]
    return 0


def http_url(url):
    """Tylko zwykłe adresy http(s) — linki z obcych stron nie mogą stać się np. javascript: w panelu."""
    u = str(url or "").strip()
    return u if re.match(r"^https?://[^\s<>\"']+$", u, re.I) else ""


def slug(text, fallback="firma"):
    s = re.sub(r"[^A-Za-z0-9]+", "_", re.sub(_FORMS, " ", norm_keep(text), flags=re.I)).strip("_")
    return s[:40] or fallback


def norm_keep(text):
    text = unicodedata.normalize("NFKD", str(text or "").replace("ł", "l").replace("Ł", "L"))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def hm(text, default=(8, 0)):
    m = re.match(r"^\s*(\d{1,2})[:.](\d{2})\s*$", str(text))
    return dt.time(int(m.group(1)) % 24, int(m.group(2)) % 60) if m else dt.time(*default)


# ================================================================ baza faktów

def facts_path(ctx):
    return ctx.folder() / "fakty.json"


def empty_facts():
    return {"osoba": {"imie": "", "nazwisko": "", "email": "", "telefon": "", "adres": "", "miasto": "", "linkedin": "", "zdjecie": "zdjecie.jpg"},
            "profil": [], "doswiadczenie": [], "wyksztalcenie": [], "kursy": [], "jezyki": [], "umiejetnosci": [],
            "narzedzia": [], "prawo_jazdy": False,
            "warunki": {"umowa": "umowa o pracę", "etat": "pełny etat", "min_netto": "", "dostepnosc": "", "dojazd_km": 50,
                        "zdalna": True, "poza_krakowem": True, "uwagi": ""},
            "kryteria": {"chce": list(WANT), "nie_chce": []}, "rodo": RODO, "odpowiedzi": {}}


def load_facts(ctx):
    base = empty_facts()
    with contextlib.suppress(Exception):
        got = json.loads(facts_path(ctx).read_text(encoding="utf-8"))
        for k, v in got.items():
            if isinstance(base.get(k), dict) and isinstance(v, dict):
                base[k].update(v)
            else:
                base[k] = v
    return with_ids(base)


def save_facts(ctx, facts):
    path = facts_path(ctx)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(with_ids(facts), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def with_ids(f):
    """Każdy fakt dostaje numer — CV składa się wyłącznie z numerowanych faktów."""
    f["profil"] = [{"id": f"p{i}", "tekst": _t(x)} for i, x in enumerate(f.get("profil", []), 1) if _t(x)]
    jobs = []
    for i, j in enumerate(f.get("doswiadczenie", []), 1):
        if not (j.get("stanowisko") or "").strip():
            continue
        j = dict(j, id=f"d{i}")
        j["punkty"] = [{"id": f"d{i}.{n}", "tekst": _t(x)} for n, x in enumerate(j.get("punkty", []), 1) if _t(x)]
        jobs.append(j)
    f["doswiadczenie"] = jobs
    f["wyksztalcenie"] = [dict(e, id=f"w{i}") for i, e in enumerate(f.get("wyksztalcenie", []), 1) if (e.get("uczelnia") or "").strip()]
    for key, pre in (("kursy", "k"), ("jezyki", "j"), ("umiejetnosci", "u")):
        f[key] = [{"id": f"{pre}{i}", "tekst": _t(x)} for i, x in enumerate(f.get(key, []), 1) if _t(x)]
    f["narzedzia"] = [{"id": f"n{i}", "nazwa": t["nazwa"].strip(), "poziom": (t.get("poziom") or "").strip()}
                      for i, t in enumerate(f.get("narzedzia", []), 1) if (t.get("nazwa") or "").strip()]
    return f


def _t(x):
    return (x.get("tekst") if isinstance(x, dict) else str(x or "")).strip()


def full_name(f):
    return f"{f['osoba'].get('imie', '')} {f['osoba'].get('nazwisko', '')}".strip()


def facts_brief(f, ids=True):
    """Fakty jako tekst dla modelu (z numerami) i dla kontrolera prawdy (bez)."""
    tag = (lambda x: f"[{x['id']}] ") if ids else (lambda x: "")
    o, w = f["osoba"], f["warunki"]
    out = [f"Kandydatka: {full_name(f)}, {o.get('miasto', '')}."]
    out.append("PROFIL (zatwierdzone zdania):")
    out += [f"  {tag(p)}{p['tekst']}" for p in f["profil"]]
    out.append("DOŚWIADCZENIE:")
    for j in f["doswiadczenie"]:
        out.append(f"  {tag(j)}{j['stanowisko']} — {j.get('firma', '')}, {j.get('miejsce', '')} ({j.get('od', '')} – {j.get('do', '')})"
                   + (" (opcjonalne)" if j.get("opcjonalne") and ids else ""))
        out += [f"      {tag(p)}{p['tekst']}" for p in j["punkty"]]
    out.append("WYKSZTAŁCENIE:")
    out += [f"  {e.get('uczelnia', '')}: {e.get('kierunek', '')}, {e.get('tytul', '')} ({e.get('okres', '')})" for e in f["wyksztalcenie"]]
    out.append("KURSY: " + "; ".join(f"{tag(k)}{k['tekst']}" for k in f["kursy"]))
    out.append("JĘZYKI: " + "; ".join(k["tekst"] for k in f["jezyki"]))
    out.append("UMIEJĘTNOŚCI: " + "; ".join(f"{tag(k)}{k['tekst']}" for k in f["umiejetnosci"]))
    out.append("NARZĘDZIA: " + "; ".join(f"{tag(t)}{t['nazwa']}" + (f" ({t['poziom']})" if t["poziom"] else "") for t in f["narzedzia"]))
    if f.get("prawo_jazdy"):
        out.append("Prawo jazdy kat. B: tak.")
    out.append(f"Dostępność: {w.get('dostepnosc', '')}. Forma: {w.get('umowa', '')}, {w.get('etat', '')}.")
    for q, a in (f.get("odpowiedzi") or {}).items():
        out.append(f"Dodatkowo — {q}: {a}")
    return "\n".join(out)


# ================================================================ sekrety (pęk kluczy macOS; poza Makiem plik — tylko do prób)

def secret(ctx, name):
    with contextlib.suppress(Exception):
        v = ctx.secret(name)
        if v:
            return v
    with contextlib.suppress(Exception):
        return json.loads((ctx.folder() / "sekrety-proba.json").read_text(encoding="utf-8")).get(name)
    return None


def set_secret(ctx, name, value):
    try:
        ctx.set_secret(name, value)
    except Exception:
        path, cur = ctx.folder() / "sekrety-proba.json", {}
        with contextlib.suppress(Exception):
            cur = json.loads(path.read_text(encoding="utf-8"))
        cur[name] = value
        path.write_text(json.dumps(cur), encoding="utf-8")
        with contextlib.suppress(Exception):
            os.chmod(path, 0o600)


def mailboxes(c):
    """(adres Agi, adres Sebastiana) — hasła są w pęku kluczy pod nazwami 'aga' i 'sebastian'."""
    return meta_get(c, "poczta_aga"), meta_get(c, "poczta_sebastian")
