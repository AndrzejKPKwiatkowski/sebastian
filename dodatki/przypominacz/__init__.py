"""Przypominacz — odkładanie spraw na wieczór.

Przebieg:
  1. Głosówka (albo tekst „przypomnij mi …”) od właściciela → czy to sprawa „na później”? (słowa-klucze,
     a gdy ich nie ma — lokalny model). Potwierdzenie od razu, z godziną przypomnienia.
  2. W tle: kontekst z poczty, notatek, nauki i obserwowanego WhatsAppa (krótko, ze źródłem).
  3. Wieczorem — po ostatnim spotkaniu z kalendarza — wiadomość z listą + „telefon”: głosówka
     (albo prawdziwe połączenie przez Twilio, jeśli je ustawisz).
  4. Czeka na odpowiedź („1 zrobione, 2 jutro”, albo swobodnie — wtedy rozumie model).
     Bez odpowiedzi: po godzinie drugi „telefon”; dalej nic → smutna minka. Sprawy bez decyzji wracają
     następnego wieczoru. Nic nie znika: każda zmiana trafia do historii.
"""
import contextlib, datetime as dt, json, re, time, unicodedata
from xml.sax.saxutils import escape

ORDINALS = ["Pierwsza", "Druga", "Trzecia", "Czwarta", "Piąta", "Szósta"]
WEEKDAYS = {"poniedzialek": 0, "poniedzialku": 0, "wtorek": 1, "wtorku": 1, "sroda": 2, "srode": 2, "srody": 2,
            "czwartek": 3, "czwartku": 3, "piatek": 4, "piatku": 4, "sobota": 5, "sobote": 5, "soboty": 5,
            "niedziela": 6, "niedziele": 6, "niedzieli": 6}
TRIGGER = re.compile(r"\b(przypomnij|przypomnisz|przypomniec|przypominaj|przypomnienie|pamietaj|nie zapomnij|"
                     r"nie daj mi zapomniec|zebym nie zapomnial\w*|musze pamietac|odloz|odkladam|na pozniej|na wieczor|"
                     r"zanotuj mi|zanotuj na|zapisz mi na|wroc do tego|wrocmy do tego)\b")
LEAD = re.compile(r"^\s*(sebastian\w*[\s,]*)?(hej[\s,]*)?(prosze[\s,]*)?(przypomnij\s+mi[\s,]*(prosze[\s,]*)?(o\s+tym[\s,]*)?"
                  r"(?:(ze|zeby)\b)?|przypomnienie|pamietaj\s*(?:(ze|zeby)\b)?|nie\s+zapomnij\s*(?:(ze|zeby)\b)?|"
                  r"zanotuj\s+mi|na\s+pozniej)\s*[:,\-]?\s*", re.I)
ACK = re.compile(r"^(ok|okej|okay|dobra|dobrze|widze|przyjalem|przyjete|dzieki|dziekuje|jasne|zaraz|za chwile|spoko|"
                 r"jestem|juz|juz patrze|patrze)\W*$")
ACTIONS = [
    ("zadanie", re.compile(r"\b(do zadan|zadani\w*|na liste|do listy)\b")),
    ("usun", re.compile(r"\b(usun\w*|skresl\w*|niewazn\w*|odpusc\w*|nie trzeba|wyrzuc\w*|anuluj\w*|nieaktualn\w*)\b")),
    ("pojutrze", re.compile(r"\bpojutrz\w*\b")),
    ("jutro", re.compile(r"\bjutr\w*\b")),
    ("tydzien", re.compile(r"\bza tydzien\b")),
    ("dzien", re.compile(r"\b(w |na )?(poniedzialek|wtorek|srod[ae]|czwartek|piatek|sobot[ae]|niedziel[ae])\b")),
    ("godzina", re.compile(r"\bo (\d{1,2})(?:[:.](\d{2}))?\b")),
    ("za", re.compile(r"\bza (\d+|pol|godzin\w*)\s*(min\w*|godz\w*|h)?\b")),
    ("pozniej", re.compile(r"\bpozniej\b")),
    ("zrobione", re.compile(r"(\b(zrobion\w*|zrobil\w*|zrobie\w*|gotowe|zalatwion\w*|zalatwil\w*|done|ok|odhacz\w*)\b|✓|✅)")),
]
ACTION = dict(ACTIONS)
FILLER = {"i", "to", "juz", "na", "do", "mi", "sie", "ta", "ten", "te", "ze", "a", "nr", "numer", "sprawa", "sprawe", "punkt",
          "wieczorem", "rano", "jest", "bedzie", "prosze", "dzieki", "przypomnij", "przenies", "przesun", "daj", "wrzuc",
          "dodaj", "w", "we", "o", "za", "godz", "godzine", "rowniez", "tez", "obie", "oba", "wszystko", "wszystkie", "listy",
          "liste", "zadan", "zadania", "z", "tym", "tak", "no", "dobra", "ok"}
_CAL_CACHE = {}


def norm(text):
    t = unicodedata.normalize("NFKD", (text or "").lower().replace("ł", "l"))
    return "".join(ch for ch in t if not unicodedata.combining(ch)).strip()


def hm(value):
    h, m = str(value).split(":")
    return dt.time(int(h), int(m))


def plural(n, one, few, many):
    if n == 1:
        return one
    return few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def count_pl(n, accusative=True):
    """1 → „jedną sprawę” / „jedna sprawa”, 2 → „dwie sprawy”, 5 → „pięć spraw”."""
    words = {1: "jedną" if accusative else "jedna", 2: "dwie", 3: "trzy", 4: "cztery", 5: "pięć", 6: "sześć", 7: "siedem",
             8: "osiem", 9: "dziewięć", 10: "dziesięć"}
    noun = plural(n, "sprawę" if accusative else "sprawa", "sprawy", "spraw")
    return f"{words.get(n, n)} {noun}"


def when_pl(moment, today):
    if moment.date() == today:
        return f"dziś o {moment:%H:%M}"
    if moment.date() == today + dt.timedelta(days=1):
        return f"jutro o {moment:%H:%M}"
    days = ["w poniedziałek", "we wtorek", "w środę", "w czwartek", "w piątek", "w sobotę", "w niedzielę"]
    return f"{days[moment.weekday()]} {moment:%d.%m} o {moment:%H:%M}"


# ================================================================ baza dodatku

def db(ctx):
    con = ctx.db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS sprawy(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tresc TEXT, nagranie TEXT, slowa TEXT DEFAULT '[]', zrodlo TEXT,
        utworzono TEXT, dzien TEXT, godzina TEXT, status TEXT DEFAULT 'czeka',
        kontekst TEXT DEFAULT '', kontekst_stan TEXT DEFAULT 'czeka',
        sesja INTEGER, nr INTEGER, wynik TEXT DEFAULT '', zmieniono TEXT, powtorki INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sesje(
        id INTEGER PRIMARY KEY AUTOINCREMENT, dzien TEXT, wyslano TEXT, etap INTEGER DEFAULT 1, krok TEXT,
        odpowiedz TEXT, zamknieta TEXT, polaczenie TEXT DEFAULT '', polaczenie_stan TEXT DEFAULT '', wynik TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS historia(
        id INTEGER PRIMARY KEY AUTOINCREMENT, czas TEXT, sprawa INTEGER, sesja INTEGER, co TEXT, opis TEXT);
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
    """)
    return con


def note(con, ctx, what, desc, item=None, session=None):
    con.execute("INSERT INTO historia(czas, sprawa, sesja, co, opis) VALUES(?,?,?,?,?)",
                (ctx.now().isoformat(timespec="seconds"), item, session, what, desc[:500]))


def meta(con, key, value=None):
    if value is None:
        r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)", (key, value))


def stamp(ctx):
    return ctx.now().isoformat(timespec="seconds")


def parse_ts(ctx, value):
    t = dt.datetime.fromisoformat(value)
    return t if t.tzinfo else t.replace(tzinfo=ctx.now().tzinfo)


# ================================================================ kiedy przypomnieć

def calendar(ctx, day):
    key = day.isoformat()
    hit = _CAL_CACHE.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    events = ctx.calendar(day)
    _CAL_CACHE[key] = (time.time(), events)
    return events


def latest_time(ctx, s):
    latest = hm(s["najpozniej"])
    with contextlib.suppress(Exception):
        q = dt.datetime.combine(dt.date.today(), ctx.quiet_start()) - dt.timedelta(minutes=15)
        if q.time() < latest and q.time() > dt.time(12):
            latest = q.time()
    return latest


def evening_slot(ctx, day, s=None):
    """(godzina przypomnienia, ostatnie spotkanie albo None) — po ostatnim spotkaniu dnia, w granicach ustawień."""
    s = s or ctx.settings()
    tz = ctx.now().tzinfo
    latest = dt.datetime.combine(day, latest_time(ctx, s), tz)
    timed = [e for e in calendar(ctx, day) if e.get("start") and e.get("end") and e["start"] < latest]
    if timed:
        last = max(timed, key=lambda e: e["end"])
        slot = last["end"] + dt.timedelta(minutes=int(s["po_spotkaniu_minut"]))
        slot = max(slot, dt.datetime.combine(day, hm(s["najwczesniej"]), tz))
    else:
        last, slot = None, dt.datetime.combine(day, hm(s["bez_spotkan"]), tz)
    slot = min(slot, latest)
    return slot.replace(second=0, microsecond=0), last


def fire_time(ctx, item, s=None):
    s = s or ctx.settings()
    tz = ctx.now().tzinfo
    day = dt.date.fromisoformat(item["dzien"])
    if item["godzina"]:
        return dt.datetime.combine(day, hm(item["godzina"]), tz)
    slot, _ = evening_slot(ctx, day, s)
    created = parse_ts(ctx, item["utworzono"])
    if created.date() == day:
        slot = max(slot, created + dt.timedelta(minutes=int(s["odstep_minut"])))
    return slot


def plan_day(ctx, created, s):
    """Dla nowej sprawy „na wieczór”: dziś, a gdy dzisiejszy wieczór już minął (albo zostało za mało czasu) — jutro."""
    today = created.date()
    slot, _ = evening_slot(ctx, today, s)
    slot = max(slot, created + dt.timedelta(minutes=int(s["odstep_minut"])))
    if slot.time() > latest_time(ctx, s) or slot.date() != today:
        return today + dt.timedelta(days=1)
    return today


def explicit_when(text, now):
    """Termin powiedziany wprost: „jutro”, „w piątek”, „o 16”, „za godzinę”. → (dzień|None, „HH:MM”|None)."""
    t = norm(text)
    day, hour = None, None
    if re.search(r"\bpojutrz\w*\b", t):
        day = now.date() + dt.timedelta(days=2)
    elif re.search(r"\bjutr\w*\b", t):
        day = now.date() + dt.timedelta(days=1)
    else:
        m = re.search(r"\b(?:w|we|na)\s+(poniedzialek|wtorek|srod[ae]|czwartek|piatek|sobot[ae]|niedziel[ae])\b", t)
        if m:
            wd = WEEKDAYS.get(m.group(1), WEEKDAYS.get(m.group(1)[:-1] + "a"))
            if wd is not None:
                day = now.date() + dt.timedelta(days=(wd - now.weekday()) % 7 or 7)
    m = re.search(r"\bza\s+(\d+|pol|godzin\w*)\s*(min\w*|godz\w*|h)?\b", t)
    if m and not day:
        amount = m.group(1)
        unit = m.group(2) or ""
        if amount == "pol":
            delta = dt.timedelta(minutes=30)
        elif amount.startswith("godzin"):
            delta = dt.timedelta(hours=1)
        elif unit.startswith("min"):
            delta = dt.timedelta(minutes=int(amount))
        else:
            delta = dt.timedelta(hours=int(amount))
        when = now + delta
        return when.date(), f"{when:%H:%M}"
    m = re.search(r"\bo\s+(?:godz\w*\s+)?(\d{1,2})(?:[:.](\d{2}))?\b", t)
    if m and 6 <= int(m.group(1)) <= 23 and int(m.group(2) or 0) < 60:
        hour = f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"
        if not day and dt.datetime.combine(now.date(), hm(hour), now.tzinfo) <= now:
            day = now.date() + dt.timedelta(days=1)
    return day, hour


# ================================================================ rozpoznawanie głosówki

PROMPT_DETECT = """Andrzej nagrał głosówkę albo napisał do swojego asystenta Sebastiana. Rozstrzygnij, czy prosi o PRZYPOMNIENIE
później — coś przyszło mu do głowy w trakcie innej pracy (telefon do wykonania, sprawa do sprawdzenia, rzecz do kupienia,
mail do wysłania) i chce do tego wrócić później. Zwykłe pytanie albo polecenie do wykonania od razu to NIE przypomnienie.
{pewne}
Jeśli to przypomnienie: wypisz OSOBNO każdą sprawę — krótko (do 12 słów), jako coś do zrobienia, bezokolicznikiem,
np. „Zadzwonić do Kowalskiego w sprawie umowy”. Do każdej 1–4 słowa do szukania w poczcie i rozmowach (nazwiska,
firmy, przedmioty) w formie podstawowej. Nie dopisuj niczego, czego nie powiedział.

Odpowiedz JSON-em: {{"przypomnienie": true/false, "sprawy": [{{"tresc": "...", "slowa": ["..."]}}]}}

Dziś: {today}
Wiadomość: \"\"\"{text}\"\"\""""


def clean_item(text):
    t = text.strip()
    stripped = LEAD.sub("", norm(t))
    if stripped != norm(t):              # utnij taką samą długość z oryginału (z polskimi znakami)
        cut = len(norm(t)) - len(stripped)
        t = t[cut:].strip()
    when = (r"(?:o|około)\s+(?:godz\w*\s+)?\d{1,2}(?:[:.]\d{2})?|jutro|pojutrze|dziś|dzisiaj|wieczorem|później|"
            r"na wieczór|na później|za\s+(?:\d+|pół)\s+\w+|za\s+godzinę|(?:w|we)\s+(?:poniedziałek|wtorek|środę|czwartek|"
            r"piątek|sobotę|niedzielę)")
    for _ in range(4):                    # termin i „że/żeby” na początku albo na końcu nie są treścią sprawy
        before = t
        t = re.sub(rf"^(?:{when})\b\s*[:,\-]?\s*", "", t, flags=re.I)
        t = re.sub(r"^(?:że|żeby|o tym,?\s*że|o tym,?\s*żeby)\s+", "", t, flags=re.I)
        t = re.sub(rf"[,\s]+(?:{when})\s*[.!]?$", "", t, flags=re.I)
        if t == before:
            break
    t = re.sub(r"\s+", " ", t).strip(" ,.;:-")
    return (t[:1].upper() + t[1:])[:240] if t else ""


def keywords(text):
    stop = {"zadzwonic", "napisac", "sprawdzic", "wyslac", "przypomnij", "pamietaj", "trzeba", "musze", "jutro", "wieczorem",
            "sprawie", "temat", "tego", "tym", "ktory", "ktora", "ktore", "pozniej", "zeby", "jeszcze", "bardzo"}
    out = []
    for w in re.findall(r"[\wąćęłńóśźż]{4,}", text or ""):
        if norm(w) not in stop and w not in out:
            out.append(w)
    return out[:5]


def detect(ctx, text, voice):
    """→ None (to nie przypomnienie) albo lista spraw [{"tresc", "slowa"}]."""
    s = ctx.settings()
    t = norm(text)
    if not t or re.match(r"^(przypomnienia|przypomnij teraz)\b", t) or t.startswith("zapamietaj"):
        return None
    triggered = bool(TRIGGER.search(t))
    if not triggered and not (voice and s.get("rozpoznawanie_modelem", True)):
        return None
    out = None
    with contextlib.suppress(Exception):
        out = ctx.ask(PROMPT_DETECT.format(
            pewne="(Ta wiadomość zawiera prośbę o przypomnienie — wypisz sprawy.)" if triggered else "",
            today=ctx.now().strftime("%Y-%m-%d %H:%M"), text=text.strip()[:3000]), as_json=True, max_tokens=700)
    items = []
    if isinstance(out, dict) and isinstance(out.get("sprawy"), list):
        for x in out["sprawy"][:10]:
            if isinstance(x, dict) and str(x.get("tresc", "")).strip():
                words = [str(w)[:40] for w in (x.get("slowa") or []) if str(w).strip()][:5]
                items.append({"tresc": str(x["tresc"]).strip()[:240], "slowa": words or keywords(x["tresc"])})
    if triggered:
        if not items:
            item = clean_item(text)
            if len(item) < 3:
                return None
            items = [{"tresc": item, "slowa": keywords(item)}]
        return items
    if isinstance(out, dict) and out.get("przypomnienie") is True and items:
        return items
    return None


def add_items(ctx, con, items, original, source, now=None):
    s = ctx.settings()
    now = now or ctx.now()
    day, hour = explicit_when(original, now)
    if not day:
        day = now.date() if hour else plan_day(ctx, now, s)
    ids = []
    for it in items:
        cur = con.execute("INSERT INTO sprawy(tresc, nagranie, slowa, zrodlo, utworzono, dzien, godzina, zmieniono) "
                          "VALUES(?,?,?,?,?,?,?,?)",
                          (it["tresc"], original[:4000], json.dumps(it.get("slowa") or [], ensure_ascii=False), source,
                           now.isoformat(timespec="seconds"), day.isoformat(), hour, now.isoformat(timespec="seconds")))
        ids.append(cur.lastrowid)
        note(con, ctx, "przyjeta", f"{source}: {it['tresc']}", cur.lastrowid)
    con.commit()
    first = con.execute("SELECT * FROM sprawy WHERE id=?", (ids[0],)).fetchone()
    return ids, fire_time(ctx, first, s)


def confirmation(ctx, items, when):
    today = ctx.now().date()
    s = ctx.settings()
    head = f"✓ Przyjąłem — przypomnę {when_pl(when, today)}"
    if when.date() >= today:
        slot, last = evening_slot(ctx, when.date(), s)
        if slot == when and last:
            head += f" (po spotkaniu „{last['title'][:50]}”, do {last['end']:%H:%M})"
        elif slot == when:
            head += " (wieczorem)"
    lines = [head + ":"] + [f"• {it['tresc']}" for it in items]
    lines.append("W międzyczasie poszukam kontekstu w poczcie i na WhatsAppie. Możesz wracać do swoich spraw 🙂")
    return "\n".join(lines)


# ================================================================ kontekst

PROMPT_CONTEXT = """Sprawa do przypomnienia Andrzejowi: „{item}”.
Poniżej fragmenty z jego poczty, notatek, wiedzy i rozmów na WhatsAppie znalezione po słowach kluczowych.
Napisz 1–2 krótkie zdania z tym, co jest ISTOTNE dla tej sprawy (kto, co ustalono, kiedy, ostatni stan) i w nawiasie
źródło, np. „(mail od Kowalskiego 03.11)” albo „(WhatsApp z Janem 05.11)”. Nie zgaduj. Jeśli nic nie dotyczy tej
sprawy, napisz dokładnie: brak.
Odpowiedz JSON-em: {{"kontekst": "..."}}

Fragmenty:
{found}"""


def gather_context(ctx, item):
    s = ctx.settings()
    words = json.loads(item["slowa"] or "[]") or keywords(item["tresc"])
    query = item["tresc"] + " " + " ".join(words)
    found = []
    with contextlib.suppress(Exception):
        k = ctx.search_knowledge(query, limit=2500)
        if k:
            found.append(k)
    with contextlib.suppress(Exception):
        for m in ctx.search_whatsapp(words, days=int(s["kontekst_dni"]), limit=10):
            found.append(f"- (WhatsApp, {m['chat']}, {m['when']:%d.%m %H:%M}, {m['who']}) {m['text']}")
    with contextlib.suppress(Exception):
        p = ctx.people_context(item["tresc"])
        if p:
            found.append(p)
    with contextlib.suppress(Exception):
        today = ctx.now().date()
        lw = [norm(w) for w in words if len(w) >= 4]
        for d in range(0, 8):
            for e in calendar(ctx, today + dt.timedelta(days=d)):
                if any(w[:5] in norm(e["title"] + " " + e.get("where", "")) for w in lw):
                    when = e["start"].strftime("%d.%m %H:%M") if e.get("start") else (today + dt.timedelta(days=d)).strftime("%d.%m")
                    found.append(f"- (kalendarz {when}) {e['title']}")
    text = "\n".join(found).strip()
    if not text:
        return "", "brak"
    out = None
    with contextlib.suppress(Exception):
        out = ctx.ask(PROMPT_CONTEXT.format(item=item["tresc"], found=text[:6000]), as_json=True, max_tokens=300)
    if isinstance(out, dict) and str(out.get("kontekst", "")).strip():
        c = str(out["kontekst"]).strip()
        return ("", "brak") if norm(c).strip(". ") == "brak" else (c[:400], "ok")
    first = [l.strip("- ").strip() for l in text.splitlines() if l.strip()][:2]
    return " · ".join(first)[:300], "surowy"


def context_step(ctx, con, limit_one=True):
    r = con.execute("SELECT * FROM sprawy WHERE kontekst_stan='czeka' AND status IN ('czeka','przypomniana') "
                    "ORDER BY id LIMIT 1").fetchone()
    if not r:
        return False
    try:
        c, state = gather_context(ctx, r)
    except Exception as e:
        c, state = "", "blad"
        ctx.log.warning(f"Kontekst sprawy {r['id']}: {type(e).__name__}: {str(e)[:150]}")
    con.execute("UPDATE sprawy SET kontekst=?, kontekst_stan=? WHERE id=?", (c, state, r["id"]))
    note(con, ctx, "kontekst", c or state, r["id"])
    con.commit()
    return True


# ================================================================ wieczorne przypomnienie

def call_name(ctx):
    s = ctx.settings()
    if s.get("wolacz"):
        return s["wolacz"]
    name = ctx.owner_name()
    return name + "u" if name.endswith("j") else name


def reminder_text(ctx, rows):
    name = ctx.owner_name()
    lines = [f"Hej {name} 👋 O tym miałeś pamiętać:" if name else "Hej 👋 O tym miałeś pamiętać:", ""]
    for r in rows:
        made = parse_ts(ctx, r["utworzono"])
        extra = " (czeka od wczoraj)" if r["powtorki"] == 1 else (f" (czeka już {r['powtorki'] + 1}. wieczór)" if r["powtorki"] > 1 else "")
        lines.append(f"*{r['nr']}.* {r['tresc']}{extra}")
        if r["kontekst"]:
            lines.append(f"   ↳ {r['kontekst']}")
        lines.append(f"   {'🎙' if r['zrodlo'] == 'głosówka' else '✍'} {made:%d.%m %H:%M}")
    lines += ["", "Co z nimi robisz? Odpisz np.: *1 zrobione* · *2 jutro* · *3 do zadań* · *4 usuń* · *1 o 21* · "
                  "*wszystko jutro* — albo po prostu napisz lub nagraj, co postanowiłeś."]
    return "\n".join(lines)


def voice_text(ctx, rows, second=False):
    n = len(rows)
    who = call_name(ctx)
    if second:
        return (f"{ctx.owner_name() or who}, przypominam. {plural(n, 'Czeka', 'Czekają', 'Czeka')} na Ciebie {count_pl(n, False)}, "
                f"{plural(n, 'którą', 'które', 'które')} odłożyłeś na później. Zajrzyj na WhatsAppa i odpisz, co z nimi zrobisz.")
    parts = [f"Hej {who}! Tu Sebastian. Masz {count_pl(n)}, "
             f"{plural(n, 'którą', 'które', 'które')} odłożyłeś na później."]
    for i, r in enumerate(rows[:len(ORDINALS)]):
        t = r["tresc"].rstrip(".")
        parts.append(f"{ORDINALS[i]}: {t}." if n > 1 else f"{t}.")
    if n > len(ORDINALS):
        parts.append(f"I jeszcze {n - len(ORDINALS)} — są w wiadomości.")
    parts.append("Teraz spójrz na WhatsAppa i odpowiedz, co z nimi zrobisz.")
    return " ".join(parts)


def ring(ctx, con, session_id, text, label):
    """„Telefon”: prawdziwe połączenie (Twilio), a gdy nie jest ustawione albo się nie uda — głosówka."""
    s = ctx.settings()
    if s.get("dzwonek") == "telefon":
        try:
            import importlib
            tw = importlib.import_module(__name__ + ".telefon")
            sid = tw.call(ctx, text)
            con.execute("UPDATE sesje SET polaczenie=?, polaczenie_stan='dzwoni' WHERE id=?", (sid, session_id))
            note(con, ctx, "telefon", f"{label}: połączenie {sid}", session=session_id)
            return "telefon"
        except Exception as e:
            note(con, ctx, "telefon", f"{label}: nieudane ({type(e).__name__}: {str(e)[:120]}) — głosówka", session=session_id)
            ctx.log.warning(f"Twilio: {type(e).__name__}: {str(e)[:150]} — wysyłam głosówkę")
    ok = ctx.send_voice(text, name=label)
    note(con, ctx, "glosowka", f"{label}: {'wysłana' if ok else 'brak głosu — tylko tekst'}", session=session_id)
    return "glosowka" if ok else "tekst"


def open_session(ctx, con, rows):
    now = ctx.now()
    cur = con.execute("INSERT INTO sesje(dzien, wyslano, etap, krok) VALUES(?,?,1,?)",
                      (now.date().isoformat(), now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")))
    sid = cur.lastrowid
    for i, r in enumerate(rows, 1):
        con.execute("UPDATE sprawy SET status='przypomniana', sesja=?, nr=?, zmieniono=? WHERE id=?",
                    (sid, i, now.isoformat(timespec="seconds"), r["id"]))
    con.commit()
    rows = con.execute("SELECT * FROM sprawy WHERE sesja=? ORDER BY nr", (sid,)).fetchall()
    ctx.send_text(reminder_text(ctx, rows), purpose="wieczor")
    how = ring(ctx, con, sid, voice_text(ctx, rows), "przypomnienie")
    note(con, ctx, "wyslane", f"{len(rows)} spraw · {how}", session=sid)
    con.commit()
    return sid


def roll_over(ctx, con):
    """Nowy dzień: otwarte wczorajsze przypomnienia zamknięte; sprawy bez decyzji wracają dziś wieczorem."""
    today = ctx.now().date().isoformat()
    for ses in con.execute("SELECT * FROM sesje WHERE zamknieta IS NULL AND dzien<?", (today,)).fetchall():
        left = con.execute("SELECT * FROM sprawy WHERE sesja=? AND status='przypomniana'", (ses["id"],)).fetchall()
        for r in left:
            con.execute("UPDATE sprawy SET status='czeka', dzien=?, godzina=NULL, sesja=NULL, nr=NULL, powtorki=powtorki+1, "
                        "zmieniono=? WHERE id=?", (today, stamp(ctx), r["id"]))
            note(con, ctx, "wraca", "bez decyzji — wraca dziś wieczorem", r["id"], ses["id"])
        con.execute("UPDATE sesje SET zamknieta=?, wynik=? WHERE id=?",
                    (stamp(ctx), "bez odpowiedzi" if not ses["odpowiedz"] else ("częściowo" if left else "załatwione"), ses["id"]))
    for r in con.execute("SELECT * FROM sprawy WHERE status='czeka' AND dzien<?", (today,)).fetchall():
        con.execute("UPDATE sprawy SET dzien=?, godzina=NULL, zmieniono=? WHERE id=?", (today, stamp(ctx), r["id"]))
        note(con, ctx, "przesunieta", "termin minął (Mac spał?) — dziś wieczorem", r["id"])
    con.commit()


def escalate(ctx, con, ses):
    s = ctx.settings()
    now = ctx.now()
    if ses["odpowiedz"]:
        return
    rows = con.execute("SELECT * FROM sprawy WHERE sesja=? AND status='przypomniana' ORDER BY nr", (ses["id"],)).fetchall()
    if not rows:
        con.execute("UPDATE sesje SET zamknieta=?, wynik='załatwione' WHERE id=?", (stamp(ctx), ses["id"]))
        con.commit()
        return
    step = parse_ts(ctx, ses["krok"])
    if ses["etap"] == 1 and now >= step + dt.timedelta(minutes=int(s["drugi_raz_po_minutach"])):
        if ctx.in_quiet(now):
            con.execute("UPDATE sesje SET etap=9 WHERE id=?", (ses["id"],))
            note(con, ctx, "cisza", "cisza nocna — bez drugiego telefonu", session=ses["id"])
        else:
            con.execute("UPDATE sesje SET etap=2, krok=?, polaczenie='', polaczenie_stan='' WHERE id=?",
                        (now.isoformat(timespec="seconds"), ses["id"]))
            ring(ctx, con, ses["id"], voice_text(ctx, rows, second=True), "przypominam")
        con.commit()
        return
    if ses["etap"] == 2:
        sad = False
        if ses["polaczenie"]:
            state, answered = "nieznany", False
            with contextlib.suppress(Exception):
                import importlib
                state, answered = importlib.import_module(__name__ + ".telefon").status(ctx, ses["polaczenie"])
            con.execute("UPDATE sesje SET polaczenie_stan=? WHERE id=?", (state, ses["id"]))
            if answered:
                con.execute("UPDATE sesje SET etap=4 WHERE id=?", (ses["id"],))
                note(con, ctx, "odebrane", "odebrałeś drugi telefon — bez minki", session=ses["id"])
            elif state in ("no-answer", "busy", "failed", "canceled") or state == "completed":   # completed bez odbioru = poczta głosowa
                sad = True
            elif now >= step + dt.timedelta(minutes=10 + int(s["minka_po_minutach"])):
                sad = True
        elif now >= step + dt.timedelta(minutes=int(s["minka_po_minutach"])):
            sad = True
        if sad:
            if not ctx.in_quiet(now):
                ctx.send_text(s.get("minka") or "I co? Olewasz mnie :'(", purpose="minka")
                note(con, ctx, "minka", "bez odpowiedzi — smutna minka", session=ses["id"])
            con.execute("UPDATE sesje SET etap=3, krok=? WHERE id=?", (now.isoformat(timespec="seconds"), ses["id"]))
        con.commit()


def tick(ctx):
    with contextlib.closing(db(ctx)) as con:
        roll_over(ctx, con)
        now = ctx.now()
        s = ctx.settings()
        ses = con.execute("SELECT * FROM sesje WHERE zamknieta IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if ses:
            escalate(ctx, con, ses)
            if not con.execute("SELECT 1 FROM sesje WHERE zamknieta IS NULL").fetchone():
                ses = None
        force = meta(con, "teraz") == "1"
        quiet_session = ses is not None and (ses["odpowiedz"] or ses["etap"] >= 3)
        if not ses or quiet_session:
            due = []
            for r in con.execute("SELECT * FROM sprawy WHERE status='czeka' ORDER BY id").fetchall():
                with contextlib.suppress(Exception):
                    if force or fire_time(ctx, r, s) <= now:
                        due.append(r)
            if due and (force or not ctx.in_quiet(now)):
                waiting = [r for r in due if r["kontekst_stan"] == "czeka"]
                if waiting and not force and all(now - fire_time(ctx, r, s) < dt.timedelta(minutes=10) for r in waiting):
                    context_step(ctx, con)              # jeszcze chwila na kontekst (najwyżej 10 minut)
                    return
                meta(con, "teraz", "0")
                if quiet_session:            # poprzednie przypomnienie już „wybrzmiało” — niezałatwione dołączają do nowego
                    left = con.execute("SELECT * FROM sprawy WHERE sesja=? AND status='przypomniana' ORDER BY nr",
                                       (ses["id"],)).fetchall()
                    con.execute("UPDATE sesje SET zamknieta=?, wynik='dołączone do kolejnego' WHERE id=?", (stamp(ctx), ses["id"]))
                    due = list(left) + due
                open_session(ctx, con, due[:15])
                return
            if force and not due:
                meta(con, "teraz", "0")
                con.commit()
        context_step(ctx, con)


# ================================================================ odpowiedź na przypomnienie

PROMPT_ANSWER = """Sebastian przypomniał Andrzejowi o sprawach:
{items}

Andrzej odpisał: \"\"\"{text}\"\"\"

Czy to odpowiedź na te przypomnienia (mówi, co z którąś sprawą robi)? Jeśli tak, dla każdej sprawy, o której mówi, podaj:
co = zrobione | jutro | zadanie (dopisać do listy zadań) | usun (nieaktualne) | termin (inny dzień: data RRRR-MM-DD) |
godzina (dziś później: HH:MM). Nie wymyślaj spraw, o których nie mówi.
Odpowiedz JSON-em: {{"odpowiedz": true/false, "akcje": [{{"nr": 1, "co": "zrobione", "data": "", "godzina": ""}}]}}
Dziś: {today}"""


def parse_actions(text, numbers, now):
    """Regułami: „1 zrobione, 2 jutro”, „zrobione 1 i 3”, „wszystko jutro”, „2 o 21”. → {nr: (co, dzień, godzina)}."""
    t = norm(text).replace("✓", " zrobione ").replace("✅", " zrobione ")
    result = {}

    def action_of(seg):
        for name, rx in ACTIONS:
            m = rx.search(seg)
            if not m:
                continue
            if name == "zrobione" and re.fullmatch(r"\W*(ok)\W*", seg):
                continue
            if name in ("jutro", "pojutrze", "tydzien", "dzien"):
                day = now.date() + dt.timedelta(days={"jutro": 1, "pojutrze": 2, "tydzien": 7}.get(name, 0))
                if name == "dzien":
                    wd = WEEKDAYS.get(m.group(2), WEEKDAYS.get(m.group(2)[:-1] + "a"))
                    day = now.date() + dt.timedelta(days=(wd - now.weekday()) % 7 or 7)
                hour = None
                hm_ = ACTION["godzina"].search(seg)
                if hm_ and 6 <= int(hm_.group(1)) <= 23:
                    hour = f"{int(hm_.group(1)):02d}:{int(hm_.group(2) or 0):02d}"
                return ("termin", day, hour)
            if name == "godzina":
                h, mi = int(m.group(1)), int(m.group(2) or 0)
                if not (6 <= h <= 23 and mi < 60):
                    continue
                day = now.date()
                if dt.datetime.combine(day, dt.time(h, mi), now.tzinfo) <= now:
                    day += dt.timedelta(days=1)
                return ("termin", day, f"{h:02d}:{mi:02d}")
            if name in ("za", "pozniej"):
                when = now + dt.timedelta(hours=1)
                if name == "za":
                    a, u = m.group(1), m.group(2) or ""
                    when = now + (dt.timedelta(minutes=30) if a == "pol" else dt.timedelta(hours=1) if a.startswith("godzin")
                                  else dt.timedelta(minutes=int(a)) if u.startswith("min") else dt.timedelta(hours=int(a)))
                return ("termin", when.date(), f"{when:%H:%M}")
            return (name, None, None)
        return None

    if re.search(r"\b(wszystk\w*|calosc|kazd\w*|obie|oba|wszystko)\b", t):
        act = action_of(re.sub(r"\b(wszystk\w*|calosc|kazd\w*|obie|oba)\b", " ", t))
        if act:
            return {n: act for n in numbers}
    segments = [x for x in re.split(r"[,;\n]+|\s+i\s+|\s+oraz\s+|\.\s+", t) if x.strip()]
    for seg in segments:                      # reguły tylko dla krótkich odpowiedzi; resztę rozumie model
        rest = seg
        for _, rx in ACTIONS:
            rest = rx.sub(" ", rest)
        rest = [w for w in re.findall(r"[a-z]+", rest) if w not in FILLER]
        if len(rest) > 2:
            return {}
    carry, last = [], None
    for seg in segments:
        seg_wo_time = re.sub(r"\bo\s+\d{1,2}(?:[:.]\d{2})?\b|\bza\s+\d+\s*\w*", " ", seg)
        nums = [int(x) for x in re.findall(r"(?<![\d:.])(\d{1,2})(?![\d:.])", seg_wo_time) if int(x) in numbers]
        act = action_of(seg_wo_time if not re.search(r"\bo\s+\d|\bza\s+\d", seg) else seg)
        if act:
            for n in carry + nums:
                result[n] = act
            carry, last = [], act
        elif nums:
            if last:
                for n in nums:
                    result[n] = last
            else:
                carry += nums
    if not result and len(numbers) == 1 and not re.search(r"\d", t):
        act = action_of(t)
        if act and not re.fullmatch(r"\W*ok\W*", t):
            result[numbers[0]] = act
    return result


def apply_actions(ctx, con, ses, rows, actions):
    by_nr = {r["nr"]: r for r in rows}
    out = []
    for nr in sorted(actions):
        r = by_nr.get(nr)
        if not r:
            continue
        what, day, hour = actions[nr]
        if what == "zrobione":
            con.execute("UPDATE sprawy SET status='zrobione', wynik='zrobione', zmieniono=? WHERE id=?", (stamp(ctx), r["id"]))
            out.append(f"✓ {nr}. {r['tresc']} — zrobione")
        elif what == "usun":
            con.execute("UPDATE sprawy SET status='odrzucona', wynik='skreślone', zmieniono=? WHERE id=?", (stamp(ctx), r["id"]))
            out.append(f"✗ {nr}. {r['tresc']} — skreślone")
        elif what == "zadanie":
            msg = ctx.add_task(r["tresc"])
            con.execute("UPDATE sprawy SET status='zadanie', wynik=?, zmieniono=? WHERE id=?", (msg[:200], stamp(ctx), r["id"]))
            out.append(f"📋 {nr}. {r['tresc']} — na liście zadań")
        elif what == "termin":
            con.execute("UPDATE sprawy SET status='czeka', dzien=?, godzina=?, sesja=NULL, nr=NULL, kontekst_stan="
                        "CASE WHEN kontekst_stan='brak' THEN 'czeka' ELSE kontekst_stan END, zmieniono=? WHERE id=?",
                        (day.isoformat(), hour, stamp(ctx), r["id"]))
            later = dict(r)
            later.update(dzien=day.isoformat(), godzina=hour)
            when = when_pl(fire_time(ctx, later), ctx.now().date()) if hour else (
                "jutro wieczorem" if day == ctx.now().date() + dt.timedelta(days=1) else f"{day:%d.%m} wieczorem")
            out.append(f"→ {nr}. {r['tresc']} — przypomnę {when}")
        note(con, ctx, what, out[-1] if out else what, r["id"], ses["id"])
    return out


def answer(ctx, con, ses, text):
    rows = con.execute("SELECT * FROM sprawy WHERE sesja=? AND status='przypomniana' ORDER BY nr", (ses["id"],)).fetchall()
    if not rows:
        return None
    now = ctx.now()
    t = norm(text)
    numbers = [r["nr"] for r in rows]
    if ACK.match(t):
        if not ses["odpowiedz"]:
            con.execute("UPDATE sesje SET odpowiedz=? WHERE id=?", (stamp(ctx), ses["id"]))
            note(con, ctx, "odpowiedz", "potwierdzenie bez decyzji", session=ses["id"])
            con.commit()
        return ("👍 Dobrze — sprawy poczekają. Odpisz, gdy zdecydujesz (np. *1 zrobione*, *2 jutro*). "
                "Jeśli nie, wrócą jutro wieczorem.")
    actions = parse_actions(text, numbers, now)
    if not actions and len(t.split()) >= 2:
        out = None
        with contextlib.suppress(Exception):
            out = ctx.ask(PROMPT_ANSWER.format(items="\n".join(f"{r['nr']}. {r['tresc']}" for r in rows),
                                               text=text.strip()[:2000], today=now.strftime("%Y-%m-%d %H:%M (%A)")),
                          as_json=True, max_tokens=400)
        if isinstance(out, dict) and out.get("odpowiedz") is True:
            for a in out.get("akcje") or []:
                with contextlib.suppress(Exception):
                    nr, what = int(a.get("nr")), str(a.get("co", "")).strip().lower()
                    if nr not in numbers:
                        continue
                    if what in ("zrobione", "zadanie", "usun"):
                        actions[nr] = (what, None, None)
                    elif what == "jutro":
                        actions[nr] = ("termin", now.date() + dt.timedelta(days=1), None)
                    elif what == "termin" and a.get("data"):
                        day = dt.date.fromisoformat(str(a["data"])[:10])
                        if day >= now.date():
                            actions[nr] = ("termin", day, None)
                    elif what == "godzina" and a.get("godzina"):
                        h = hm(str(a["godzina"])[:5])
                        day = now.date() if dt.datetime.combine(now.date(), h, now.tzinfo) > now else now.date() + dt.timedelta(days=1)
                        actions[nr] = ("termin", day, f"{h:%H:%M}")
    if not actions:
        return None
    done = apply_actions(ctx, con, ses, rows, actions)
    con.execute("UPDATE sesje SET odpowiedz=COALESCE(odpowiedz, ?) WHERE id=?", (stamp(ctx), ses["id"]))
    left = con.execute("SELECT * FROM sprawy WHERE sesja=? AND status='przypomniana' ORDER BY nr", (ses["id"],)).fetchall()
    if not left:
        con.execute("UPDATE sesje SET zamknieta=?, wynik='załatwione' WHERE id=?", (stamp(ctx), ses["id"]))
    con.commit()
    msg = "\n".join(done)
    if left:
        msg += "\n\nCzekam jeszcze na: " + ", ".join(f"*{r['nr']}.* {r['tresc']}" for r in left) + \
               " — odpisz, gdy zdecydujesz; inaczej wróci jutro wieczorem."
    else:
        msg += "\n\nWszystko ogarnięte — głowa wolna 🙂"
    return msg


# ================================================================ wiadomości od właściciela

def list_text(ctx, con):
    s = ctx.settings()
    today = ctx.now().date()
    lines = []
    ses = con.execute("SELECT * FROM sesje WHERE zamknieta IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    if ses:
        rows = con.execute("SELECT * FROM sprawy WHERE sesja=? AND status='przypomniana' ORDER BY nr", (ses["id"],)).fetchall()
        if rows:
            lines.append("*Czekam na Twoją decyzję:*")
            lines += [f"*{r['nr']}.* {r['tresc']}" for r in rows]
    waiting = con.execute("SELECT * FROM sprawy WHERE status='czeka' ORDER BY dzien, id").fetchall()
    if waiting:
        lines.append(("\n" if lines else "") + "*Odłożone na później:*")
        for r in waiting:
            with contextlib.suppress(Exception):
                lines.append(f"• {r['tresc']} — {when_pl(fire_time(ctx, r, s), today)}")
    if not lines:
        slot, last = evening_slot(ctx, today, s)
        return (f"Nic nie czeka 🙂 Gdy coś Ci wpadnie do głowy, nagraj głosówkę („przypomnij mi…”) — "
                f"dziś przypomniałbym {slot:%H:%M}" + (f" (po „{last['title'][:40]}”)." if last else "."))
    return "\n".join(lines)


def on_message(ctx, msg):
    if not msg["text"].strip():
        return None
    t = norm(msg["text"])
    with contextlib.closing(db(ctx)) as con:
        if re.match(r"^przypomnienia\W*$|^(co mam|co czeka) (na wieczor|do przypomnienia)\W*$", t):
            return list_text(ctx, con)
        if re.match(r"^przypomnij (teraz|juz)\W*$", t):
            waiting = con.execute("SELECT COUNT(*) FROM sprawy WHERE status='czeka'").fetchone()[0]
            if not waiting:
                return "Nic nie czeka na przypomnienie 🙂"
            meta(con, "teraz", "1")
            con.commit()
            return f"Już przypominam ({waiting} {plural(waiting, 'sprawa', 'sprawy', 'spraw')})…"
        ses = con.execute("SELECT * FROM sesje WHERE zamknieta IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if ses and not TRIGGER.search(t):
            out = answer(ctx, con, ses, msg["text"])
            if out:
                return out
        items = detect(ctx, msg["text"], msg["voice"])
        if not items:
            return None
        _, when = add_items(ctx, con, items, msg["text"], "głosówka" if msg["voice"] else "wiadomość")
        return confirmation(ctx, items, when)


# ================================================================ polecenia w Terminalu

def _cmd_list(ctx, args):
    with contextlib.closing(db(ctx)) as con:
        print(list_text(ctx, con).replace("*", ""))
        print("\nOstatnie przypomnienia:")
        for ses in con.execute("SELECT * FROM sesje ORDER BY id DESC LIMIT 5"):
            n = con.execute("SELECT COUNT(*) FROM sprawy WHERE sesja=?", (ses["id"],)).fetchone()[0]
            state = ses["wynik"] or ("czeka na odpowiedź" if not ses["odpowiedz"] else "częściowo")
            print(f"  {ses['wyslano'][:16].replace('T', ' ')} · etap {ses['etap']} · {state}"
                  + (f" · telefon: {ses['polaczenie_stan']}" if ses["polaczenie"] else "") + f" · {n} spraw")
    return 0


def _cmd_today(ctx, args):
    s = ctx.settings()
    today = ctx.now().date()
    events = ctx.calendar(today)
    print(f"Kalendarz na dziś ({today:%d.%m.%Y}):")
    for e in events:
        print("  cały dzień  " + e["title"] if e["all_day"] else f"  {e['start']:%H:%M}–{e['end']:%H:%M}  {e['title']}")
    if not events:
        print("  (pusto — albo kalendarz nie jest zaimportowany w panelu)")
    slot, last = evening_slot(ctx, today, s)
    print(f"\nWieczorne przypomnienie: {slot:%H:%M}" + (f" (po „{last['title']}”, koniec {last['end']:%H:%M}, "
                                                        f"+{s['po_spotkaniu_minut']} min)" if last else " (dziś bez spotkań)"))
    print(f"Ustawienia: najwcześniej {s['najwczesniej']}, bez spotkań {s['bez_spotkan']}, najpóźniej {latest_time(ctx, s):%H:%M}")
    return 0


def _cmd_check(ctx, args):
    text = " ".join(args).strip()
    if not text:
        print('Podaj tekst, np.: python sebastian.py dodatek przypominacz sprawdz "przypomnij mi o fakturze dla Nowaka"')
        return 1
    items = detect(ctx, text, voice=True)
    if not items:
        print("To NIE jest prośba o przypomnienie — Sebastian odpowie normalnie.")
        return 0
    now = ctx.now()
    day, hour = explicit_when(text, now)
    print("To prośba o przypomnienie. Sprawy:")
    for it in items:
        print(f"  • {it['tresc']}   (szukam po: {', '.join(it['slowa'])})")
    if hour or day:
        print(f"Termin powiedziany wprost: {day or now.date()} {hour or 'wieczorem'}")
    else:
        print(f"Przypomnę: {plan_day(ctx, now, ctx.settings())} wieczorem")
    return 0


def _cmd_add(ctx, args):
    text = " ".join(args).strip()
    if not text:
        print('Podaj tekst, np.: python sebastian.py dodatek przypominacz dodaj "przypomnij mi zadzwonić do Kowalskiego"')
        return 1
    items = detect(ctx, text if TRIGGER.search(norm(text)) else "przypomnij mi: " + text, voice=True) or \
        [{"tresc": clean_item(text), "slowa": keywords(text)}]
    with contextlib.closing(db(ctx)) as con:
        _, when = add_items(ctx, con, items, text, "Terminal")
    msg = confirmation(ctx, items, when)
    ctx.send_text(msg, purpose="potwierdzenie")
    print(msg.replace("*", ""))
    print("\n(Potwierdzenie poszło też na WhatsAppa — wyśle je usługa w tle.)")
    return 0


def _cmd_now(ctx, args):
    with contextlib.closing(db(ctx)) as con:
        waiting = con.execute("SELECT COUNT(*) FROM sprawy WHERE status='czeka'").fetchone()[0]
        if not waiting:
            print("Nic nie czeka. Najpierw: python sebastian.py dodatek przypominacz dodaj \"…\"")
            return 0
        meta(con, "teraz", "1")
        con.commit()
    print(f"OK — usługa WhatsApp przypomni o {waiting} sprawach w ciągu ok. pół minuty (musi działać: wa-status).")
    return 0


def _cmd_settings(ctx, args):
    for k, v in ctx.settings().items():
        print(f"  {k} = {v}")
    print("\nZmiana: python sebastian.py dodatek przypominacz ustaw KLUCZ WARTOŚĆ")
    print("Token Twilio NIE jest tutaj — leży w pęku kluczy macOS (ustawia: … przypominacz telefon).")
    return 0


def _cmd_set(ctx, args):
    if len(args) < 2:
        print("Użycie: python sebastian.py dodatek przypominacz ustaw KLUCZ WARTOŚĆ")
        return 1
    key, value = args[0], " ".join(args[1:])
    if key in ("najwczesniej", "bez_spotkan", "najpozniej"):
        try:
            hm(value)
        except Exception:
            print("Godzinę podaj jako HH:MM, np. 18:30")
            return 1
    if key == "dzwonek" and value not in ("glosowka", "telefon"):
        print("dzwonek: glosowka albo telefon")
        return 1
    try:
        print(f"{key} = {ctx.set_setting(key, value)}")
    except Exception as e:
        print(e)
        return 1
    return 0


def _cmd_history(ctx, args):
    with contextlib.closing(db(ctx)) as con:
        for r in con.execute("SELECT h.*, s.tresc FROM historia h LEFT JOIN sprawy s ON s.id=h.sprawa ORDER BY h.id DESC LIMIT 40"):
            print(f"{r['czas'][:16].replace('T', ' ')}  {r['co']:<12} {(r['tresc'] or '')[:50]:<50}  {r['opis'][:80]}")
    return 0


def _cmd_phone(ctx, args):
    import importlib
    return importlib.import_module(__name__ + ".telefon").setup(ctx, args)


COMMANDS = {"lista": _cmd_list, "dzis": _cmd_today, "sprawdz": _cmd_check, "dodaj": _cmd_add, "teraz": _cmd_now,
            "ustawienia": _cmd_settings, "ustaw": _cmd_set, "historia": _cmd_history, "telefon": _cmd_phone}
