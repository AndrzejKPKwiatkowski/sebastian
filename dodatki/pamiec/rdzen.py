"""Pamięć — rdzeń: osoby, źródła wiedzy, fakty, pytania sprawdzające, profile.

Wszystko lokalnie w data/dodatki/pamiec/ (baza stan.sqlite3 + pliki). Nic nie jest kasowane:
fakt odrzucony albo poprawiony zostaje w bazie ze statusem, a poprawki trafiają do „księgi poprawek”,
która przy składaniu profilu ma pierwszeństwo przed wszystkim innym.
"""
import contextlib, datetime as dt, difflib, html, io, json, re, shutil, sqlite3, tempfile, time, unicodedata, zipfile
from pathlib import Path

CHUNK = 6000
CATEGORIES = [
    ("kim_jest", "Kim jest"),
    ("praca", "Praca i firma"),
    ("ludzie", "Ludzie wokół"),
    ("sprawy", "Bieżące sprawy i projekty"),
    ("preferencje", "Preferencje i styl"),
    ("cele", "Cele i wartości"),
    ("codziennosc", "Codzienność i nawyki"),
]
CAT = dict(CATEGORIES)
CAT_ORDER = {k: i for i, (k, _) in enumerate(CATEGORIES)}
KIND_PL = {"whatsapp": "rozmowy z Sebastianem", "chatgpt": "eksport ChatGPT", "claude": "eksport Claude",
           "gemini": "eksport Gemini", "plik": "plik", "tekst": "wklejony tekst", "nauka": "dotychczasowa nauka Sebastiana",
           "folder": "folder", "biblioteka": "biblioteka wiedzy"}
STATUS_PL = {"nowe": "czeka", "w_toku": "przetwarzam", "gotowe": "gotowe", "blad": "błąd", "pusty": "brak treści"}
TEXT_EXT = (".txt", ".md", ".csv", ".log", ".json", ".html", ".htm")
DOC_EXT = (".pdf", ".docx", ".pptx", ".xlsx", ".rtf", ".doc", ".odt", ".jpg", ".jpeg", ".png")
SECRET = re.compile(r"\b(\d{11}|\d{26}|(?:\d{4}[ -]?){3}\d{4})\b|has[łl]o\s*[:=]\s*\S+", re.I)


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def norm(text):
    t = unicodedata.normalize("NFKD", (text or "").lower().replace("ł", "l"))
    return re.sub(r"\s+", " ", "".join(ch for ch in t if not unicodedata.combining(ch))).strip(" .!,?;:")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")[:40] or "osoba"


# ================================================================ baza

def db(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(folder / "stan.sqlite3", timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS osoby(id TEXT PRIMARY KEY, imie TEXT, rola TEXT, telefon TEXT, folder TEXT, dodano TEXT);
    CREATE TABLE IF NOT EXISTS zrodla(
        id INTEGER PRIMARY KEY AUTOINCREMENT, osoba TEXT, rodzaj TEXT, nazwa TEXT, sciezka TEXT DEFAULT '',
        status TEXT DEFAULT 'nowe', kawalkow INTEGER DEFAULT 0, zrobione INTEGER DEFAULT 0, faktow INTEGER DEFAULT 0,
        notatka TEXT DEFAULT '', dodano TEXT, zakonczono TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS kawalki(
        id INTEGER PRIMARY KEY AUTOINCREMENT, zrodlo INTEGER, nr INTEGER, tekst TEXT, status TEXT DEFAULT 'nowy',
        faktow INTEGER DEFAULT 0, proby INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS ix_kaw ON kawalki(status, id);
    CREATE TABLE IF NOT EXISTS fakty(
        id INTEGER PRIMARY KEY AUTOINCREMENT, osoba TEXT, kategoria TEXT, tresc TEXT, klucz TEXT, pewnosc REAL,
        potwierdzen INTEGER DEFAULT 1, status TEXT DEFAULT 'nowy', zrodlo INTEGER, poprawia INTEGER,
        utworzono TEXT, zmieniono TEXT, uzyto TEXT DEFAULT '', ile_uzyc INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS ix_fakty ON fakty(osoba, status, kategoria);
    CREATE TABLE IF NOT EXISTS pytania(
        id INTEGER PRIMARY KEY AUTOINCREMENT, osoba TEXT, fakt INTEGER, pytanie TEXT, status TEXT DEFAULT 'czeka',
        nr INTEGER DEFAULT 0, partia TEXT DEFAULT '', kanal TEXT DEFAULT '', utworzono TEXT, zadano TEXT DEFAULT '',
        odpowiedz TEXT DEFAULT '', odpowiedziano TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS poprawki(
        id INTEGER PRIMARY KEY AUTOINCREMENT, osoba TEXT, fakt INTEGER, bylo TEXT, jest TEXT, kiedy TEXT);
    CREATE TABLE IF NOT EXISTS profil(osoba TEXT, kategoria TEXT, tekst TEXT, zaktualizowano TEXT, PRIMARY KEY(osoba, kategoria));
    CREATE TABLE IF NOT EXISTS rozmowy(id INTEGER PRIMARY KEY AUTOINCREMENT, osoba TEXT, ts REAL, tekst TEXT, zrodlo INTEGER DEFAULT 0);
    """)
    con.commit()
    from . import biblioteka as B                      # 2.35: biblioteka wiedzy (kursy, książki)
    B.schema(con)
    return con


def meta(con, k, v=None):
    if v is None:
        r = con.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None
    con.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (k, str(v)))


# ================================================================ osoby (każdy użytkownik Sebastiana ma własną pamięć)

def sync_people(con, users):
    """users: lista {phone, name, role} z WhatsAppa. Id osoby = numer telefonu (albo slug imienia)."""
    for u in users:
        pid = re.sub(r"\D", "", u.get("phone") or "") or slug(u.get("name") or "")
        if not pid:
            continue
        name = (u.get("name") or "").strip() or ("+" + pid if pid.isdigit() else pid)
        r = con.execute("SELECT * FROM osoby WHERE id=?", (pid,)).fetchone()
        if r:
            con.execute("UPDATE osoby SET imie=?, rola=?, telefon=? WHERE id=?", (name, u.get("role") or r["rola"], u.get("phone") or "", pid))
        else:
            con.execute("INSERT INTO osoby(id, imie, rola, telefon, folder, dodano) VALUES(?,?,?,?,?,?)",
                        (pid, name, u.get("role") or "", u.get("phone") or "", slug(name.split()[0] if name else pid), now_iso()))
    con.commit()


def with_extra(users, settings):
    """Użytkownicy WhatsAppa + osoba panelu Agi, jeśli nie ma jej na liście WhatsAppa (pamięć i tak ma być jej)."""
    users = list(users or [])
    want = norm((settings or {}).get("osoba_panelu_agi") or "")
    if want and not any(any(norm(x).startswith(want) for x in (u.get("name") or "").split()) for u in users if u.get("role") != "wlasciciel"):
        users.append({"phone": "", "name": (settings or {}).get("osoba_panelu_agi"), "role": "rodzina"})
    return users


def people(con):
    return [dict(r) for r in con.execute("SELECT * FROM osoby ORDER BY CASE rola WHEN 'wlasciciel' THEN 0 ELSE 1 END, imie")]


def person(con, pid):
    r = con.execute("SELECT * FROM osoby WHERE id=?", (pid,)).fetchone()
    return dict(r) if r else None


def find_person(con, text):
    t = norm(text)
    for p in people(con):
        if t and (t == p["id"] or t == norm(p["imie"]) or t == p["folder"] or norm(p["imie"]).startswith(t)):
            return p
    return None


def first_name(p):
    return (p["imie"] or "").split()[0] if p and p.get("imie") else "Ty"


# ================================================================ źródła: eksporty czatów, pliki, tekst

def _ts(v):
    with contextlib.suppress(Exception):
        if isinstance(v, (int, float)) and v > 0:
            return dt.datetime.fromtimestamp(v).strftime("%Y-%m-%d")
        if isinstance(v, str) and v[:4].isdigit():
            return v[:10]
    return ""


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if isinstance(content.get("parts"), list):
            return "\n".join(_text_of(p) for p in content["parts"] if isinstance(p, (str, dict)))
        return str(content.get("text") or content.get("result") or "")
    if isinstance(content, list):
        return "\n".join(_text_of(c) for c in content)
    return ""


def chatgpt_docs(data):
    """conversations.json z ChatGPT: tylko to, co pisała osoba (bez odpowiedzi modelu)."""
    for conv in data:
        nodes = [n.get("message") for n in (conv.get("mapping") or {}).values() if isinstance(n, dict) and n.get("message")]
        nodes = [m for m in nodes if (m.get("author") or {}).get("role") == "user"]
        nodes.sort(key=lambda m: m.get("create_time") or 0)
        msgs = [t.strip() for t in (_text_of(m.get("content") or {}) for m in nodes) if t and t.strip()]
        if msgs:
            yield f"[{_ts(conv.get('create_time'))}] Rozmowa z ChatGPT „{conv.get('title') or 'bez tytułu'}”", msgs


def claude_docs(data):
    for conv in data:
        msgs = []
        for m in conv.get("chat_messages") or []:
            if m.get("sender") != "human":
                continue
            t = m.get("text") or _text_of([c for c in (m.get("content") or []) if isinstance(c, dict) and c.get("type") == "text"])
            if t and t.strip():
                msgs.append(t.strip())
        if msgs:
            yield f"[{_ts(conv.get('created_at'))}] Rozmowa z Claude „{conv.get('name') or 'bez tytułu'}”", msgs


def gemini_docs(data):
    by_day = {}
    for it in data:
        if not isinstance(it, dict) or "gemini" not in json.dumps(it.get("header", "") + str(it.get("products", "")), ensure_ascii=False).lower():
            continue
        t = re.sub(r"^(Prompted|Wysłano prompta|Zapytanie|Prompt)\s*:?\s*", "", str(it.get("title") or "")).strip()
        if len(t) > 3:
            by_day.setdefault(_ts(it.get("time")), []).append(t)
    for day in sorted(by_day):
        yield f"[{day}] Zapytania do Gemini", by_day[day]


def memory_docs(data, label):
    """Zapisane „wspomnienia” modeli (np. memories.json) i inne listy tekstów."""
    texts = []

    def walk(v, depth=0):
        if depth > 6:
            return
        if isinstance(v, str) and len(v.strip()) >= 25:
            texts.append(v.strip())
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ("uuid", "id", "account", "created_at", "updated_at", "email_address"):
                    walk(x, depth + 1)
        elif isinstance(v, list):
            for x in v:
                walk(x, depth + 1)
    walk(data)
    if texts:
        yield label, texts


def json_docs(data, name=""):
    """Rozpoznaje rodzaj eksportu po budowie JSON-a. Zwraca (rodzaj, dokumenty)."""
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if "mapping" in data[0]:
            return "chatgpt", list(chatgpt_docs(data))
        if "chat_messages" in data[0]:
            return "claude", list(claude_docs(data))
        if "header" in data[0] and any("gemini" in str(d.get("header", "")).lower() for d in data[:50]):
            return "gemini", list(gemini_docs(data))
    return "plik", list(memory_docs(data, f"Plik {name}"))


def html_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def file_docs(path, extract=None):
    """Dowolny plik → (rodzaj, [(tytuł, [teksty])]). Zip: eksporty ChatGPT/Claude/Gemini albo paczka plików."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".zip":
        kind, docs = "plik", []
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n]
            for n in names:
                low = n.lower()
                if low.endswith(".json") and (low.endswith("conversations.json") or "gemini" in low or "memor" in low
                                              or "myactivity" in low.replace(" ", "")):
                    with contextlib.suppress(Exception):
                        k, d = json_docs(json.loads(z.read(n).decode("utf-8", "ignore")), Path(n).name)
                        if k != "plik":
                            kind = k
                        docs += d
            if not docs:                                           # zwykła paczka plików
                with tempfile.TemporaryDirectory() as tmp:
                    for n in names[:2000]:
                        if Path(n).suffix.lower() in TEXT_EXT + DOC_EXT:
                            target = Path(tmp) / f"{len(docs)}{Path(n).suffix.lower()}"
                            target.write_bytes(z.read(n))
                            for _, d in [file_docs(target, extract)]:
                                docs += [(f"Plik {Path(n).name}", texts) for _, texts in d]
        return kind, docs
    if ext == ".json":
        with contextlib.suppress(Exception):
            return json_docs(json.loads(path.read_text(encoding="utf-8", errors="ignore")), path.name)
    if ext in (".html", ".htm"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        kind = "gemini" if "Gemini" in raw[:20000] and "MyActivity" in path.name.replace(" ", "") else "plik"
        return kind, [(f"Plik {path.name}", [html_text(raw)])]
    if ext in (".txt", ".md", ".csv", ".log"):
        return "plik", [(f"Plik {path.name}", [path.read_text(encoding="utf-8", errors="ignore")])]
    if extract is not None:
        with contextlib.suppress(Exception):
            text = extract(path) or ""
            if text.strip():
                return "plik", [(f"Plik {path.name}", [text])]
    return "plik", []


def chunks(docs, size=CHUNK):
    """[(tytuł, [teksty])] → kawałki ≤ size znaków; jedna rozmowa nie jest dzielona, jeśli się mieści."""
    out, cur = [], ""
    for title, texts in docs:
        block = title + ":\n" + "\n".join("— " + re.sub(r"\s+", " ", SECRET.sub("[ukryte]", t)).strip() for t in texts if t.strip())
        while len(block) > size:
            cut = block.rfind("\n", 0, size)
            cut = cut if cut > size // 2 else size
            if cur:
                out.append(cur)
                cur = ""
            out.append(block[:cut])
            block = title + " (cd.):\n" + block[cut:].lstrip()
        if len(cur) + len(block) + 2 > size and cur:
            out.append(cur)
            cur = block
        else:
            cur = (cur + "\n\n" + block) if cur else block
    if cur.strip():
        out.append(cur)
    return out


def add_source(con, pid, kind, name, path="", text=None):
    """Nowe źródło wiedzy. Tekst od razu dzielony na kawałki; plik — przez pracownika w tle (parse_source)."""
    cur = con.execute("INSERT INTO zrodla(osoba, rodzaj, nazwa, sciezka, dodano) VALUES(?,?,?,?,?)",
                      (pid, kind, name[:200], str(path or ""), now_iso()))
    sid = cur.lastrowid
    if text is not None:
        store_chunks(con, sid, chunks([(name, [text])]))
    con.commit()
    return sid


def store_chunks(con, sid, parts):
    con.executemany("INSERT INTO kawalki(zrodlo, nr, tekst) VALUES(?,?,?)", [(sid, i, t) for i, t in enumerate(parts, 1)])
    con.execute("UPDATE zrodla SET kawalkow=?, status=? WHERE id=?", (len(parts), "w_toku" if parts else "pusty", sid))


def parse_source(con, src, extract=None):
    """Plik źródła → kawałki. Rodzaj poprawiany po rozpoznaniu (ChatGPT / Claude / Gemini)."""
    try:
        kind, docs = file_docs(src["sciezka"], extract)
        parts = chunks(docs)
        store_chunks(con, src["id"], parts)
        if src["rodzaj"] in ("plik", "folder") and kind != "plik":
            con.execute("UPDATE zrodla SET rodzaj=? WHERE id=?", (kind, src["id"]))
        con.execute("UPDATE zrodla SET notatka=? WHERE id=?",
                    (f"{len(docs)} {'rozmów' if kind in ('chatgpt', 'claude') else 'części'}, {len(parts)} kawałków do przemyślenia", src["id"]))
    except Exception as e:
        con.execute("UPDATE zrodla SET status='blad', notatka=? WHERE id=?", (f"{type(e).__name__}: {str(e)[:200]}", src["id"]))
    con.commit()


# ================================================================ fakty

DIGEST_PROMPT = """Budujesz pamięć o człowieku: {name}{role}. Na podstawie tekstu niżej wypisz NOWE, trwałe i konkretne fakty
o {name}: kim jest, czym się zajmuje, z kim pracuje i żyje (kto jest kim dla {name_d}), jakie ma sprawy, plany, cele,
preferencje, styl pracy i nawyki. Źródło: {kind}. {source_hint}

Zasady:
• Pisz po polsku, w trzeciej osobie, zdaniem samodzielnym: „{first} …”. Jedna informacja = jeden fakt.
• „pewnosc”: 0.9–1.0 gdy {first} mówi to wprost o sobie; 0.5–0.7 gdy to Twój wniosek albo domysł.
• Pomijaj wiedzę ogólną, treść odpowiedzi modeli, jednorazowe drobiazgi i to, co już jest w pamięci poniżej.
• Nie zapisuj haseł, numerów kart, kont, PESEL-i.
• Najwyżej 15 faktów. Gdy nic nowego — pusta lista.
Kategorie: kim_jest, praca, ludzie, sprawy, preferencje, cele, codziennosc.

Co już wiem o {name_l} (nie powtarzaj):
{known}

TEKST:
<<<
{text}
>>>

Zwróć wyłącznie JSON: {{"fakty": [{{"kategoria": "…", "tresc": "…", "pewnosc": 0.8}}]}}"""


def known_brief(con, pid, limit=1800):
    rows = con.execute("SELECT kategoria, tekst FROM profil WHERE osoba=? ORDER BY kategoria", (pid,)).fetchall()
    text = "\n".join(f"[{CAT.get(r['kategoria'], r['kategoria'])}] {r['tekst']}" for r in rows if r["tekst"])
    if not text:
        text = "\n".join("• " + r["tresc"] for r in con.execute(
            "SELECT tresc FROM fakty WHERE osoba=? AND status IN ('nowy','potwierdzony') ORDER BY pewnosc DESC, potwierdzen DESC LIMIT 40", (pid,)))
    return text[:limit] or "(jeszcze nic)"


def add_fact(con, pid, cat, text, conf, sid=None, status="nowy", fixes=None):
    """Zapis faktu z łączeniem powtórek: podobny fakt dostaje +1 potwierdzenie (i pewność w górę)."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) < 6 or SECRET.search(text):
        return None, False
    cat = cat if cat in CAT else "sprawy"
    key = norm(text)
    conf = max(0.0, min(1.0, float(conf if conf is not None else 0.7)))
    for r in con.execute("SELECT id, klucz, pewnosc, status FROM fakty WHERE osoba=? AND kategoria=? AND status IN ('nowy','potwierdzony')",
                         (pid, cat)).fetchall():
        if r["klucz"] == key or (len(key) > 20 and difflib.SequenceMatcher(None, r["klucz"], key).ratio() >= 0.85):
            con.execute("UPDATE fakty SET potwierdzen=potwierdzen+1, pewnosc=?, zmieniono=? WHERE id=?",
                        (min(1.0, max(r["pewnosc"], conf) + 0.05), now_iso(), r["id"]))
            return r["id"], False
    cur = con.execute("INSERT INTO fakty(osoba, kategoria, tresc, klucz, pewnosc, status, zrodlo, poprawia, utworzono, zmieniono) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)", (pid, cat, text[:500], key, conf, status, sid, fixes, now_iso(), now_iso()))
    return cur.lastrowid, True


def digest_chunk(con, chunk, ask):
    """Jeden kawałek → fakty (przez lokalny model). True = przerobiony; False = model nie odpowiedział."""
    src = con.execute("SELECT * FROM zrodla WHERE id=?", (chunk["zrodlo"],)).fetchone()
    p = person(con, src["osoba"]) if src else None
    if not src or not p:
        con.execute("UPDATE kawalki SET status='pominiety' WHERE id=?", (chunk["id"],))
        con.commit()
        return True
    first = first_name(p)
    hints = {"whatsapp": f"To wiadomości, które {first} napisał(a) do swojego asystenta Sebastiana.",
             "chatgpt": f"To pytania i wiadomości, które {first} pisał(a) do ChatGPT — mówią, czym się zajmuje i co go/ją zajmuje.",
             "claude": f"To wiadomości, które {first} pisał(a) do Claude.", "gemini": f"To zapytania, które {first} wpisywał(a) w Gemini.",
             "nauka": "To dotychczasowy profil wiedzy zebrany przez Sebastiana z poczty i dokumentów.",
             "tekst": f"To tekst, który {first} sam(a) wkleił(a), żeby Sebastian się z niego uczył."}
    prompt = DIGEST_PROMPT.format(name=p["imie"], role=f" ({p['rola']})" if p.get("rola") else "", name_d=p["imie"], name_l=p["imie"],
                                  first=first, kind=KIND_PL.get(src["rodzaj"], src["rodzaj"]),
                                  source_hint=hints.get(src["rodzaj"], "To plik/dokument przekazany Sebastianowi do nauki."),
                                  known=known_brief(con, p["id"]), text=chunk["tekst"][:CHUNK + 500])
    out = ask(prompt)
    if not isinstance(out, dict):
        con.execute("UPDATE kawalki SET proby=proby+1, status=CASE WHEN proby>=2 THEN 'blad' ELSE 'nowy' END WHERE id=?", (chunk["id"],))
        con.commit()
        return False
    n = 0
    for f in (out.get("fakty") or [])[:15]:
        if isinstance(f, dict):
            fid, new = add_fact(con, p["id"], str(f.get("kategoria") or ""), str(f.get("tresc") or ""), f.get("pewnosc"), src["id"])
            n += int(bool(new))
    con.execute("UPDATE kawalki SET status='gotowy', faktow=? WHERE id=?", (n, chunk["id"]))
    con.execute("UPDATE zrodla SET zrobione=zrobione+1, faktow=faktow+? WHERE id=?", (n, src["id"]))
    finish_sources(con)
    con.commit()
    return True


def finish_sources(con):
    for s in con.execute("SELECT id FROM zrodla WHERE status='w_toku'").fetchall():
        left = con.execute("SELECT COUNT(*) FROM kawalki WHERE zrodlo=? AND status='nowy'", (s["id"],)).fetchone()[0]
        if not left:
            con.execute("UPDATE zrodla SET status='gotowe', zakonczono=? WHERE id=?", (now_iso(), s["id"]))


def next_chunk(con):
    return con.execute("SELECT k.* FROM kawalki k JOIN zrodla z ON z.id=k.zrodlo WHERE k.status='nowy' "
                       "ORDER BY CASE z.rodzaj WHEN 'whatsapp' THEN 0 WHEN 'tekst' THEN 1 ELSE 2 END, k.id LIMIT 1").fetchone()


# ================================================================ pytania sprawdzające („czy dobrze zrozumiałem?”)

def question_text(fact):
    return f"Zrozumiałem, że: „{fact['tresc']}” — dobrze rozumiem?"


def make_questions(con, pid, limit=10):
    """Fakty niepewne i jeszcze niesprawdzone → pytania (najważniejsze kategorie najpierw)."""
    have = con.execute("SELECT COUNT(*) FROM pytania WHERE osoba=? AND status IN ('czeka','zadane')", (pid,)).fetchone()[0]
    if have >= limit:
        return 0
    rows = con.execute("SELECT * FROM fakty WHERE osoba=? AND status='nowy' AND pewnosc<0.8 AND id NOT IN (SELECT fakt FROM pytania) "
                       "ORDER BY pewnosc, id LIMIT 200", (pid,)).fetchall()
    rows = sorted(rows, key=lambda r: (CAT_ORDER.get(r["kategoria"], 9), -r["potwierdzen"], r["pewnosc"]))[:limit - have]
    for r in rows:
        con.execute("INSERT INTO pytania(osoba, fakt, pytanie, utworzono) VALUES(?,?,?,?)", (pid, r["id"], question_text(r), now_iso()))
    con.commit()
    return len(rows)


def open_questions(con, pid, status=("czeka", "zadane")):
    q = f"SELECT q.*, f.tresc, f.kategoria FROM pytania q JOIN fakty f ON f.id=q.fakt WHERE q.osoba=? AND q.status IN ({','.join('?' * len(status))}) ORDER BY q.id"
    return [dict(r) for r in con.execute(q, (pid, *status))]


def fact_verdict(con, fid, verdict, correction=""):
    """Ocena faktu prosto z listy (panel): tak → potwierdzony; nie (+ poprawka) → księga poprawek."""
    q = con.execute("SELECT id FROM pytania WHERE fakt=? AND status IN ('czeka','zadane')", (fid,)).fetchone()
    if not q:
        f = con.execute("SELECT * FROM fakty WHERE id=?", (fid,)).fetchone()
        if not f or f["status"] not in ("nowy", "potwierdzony"):
            return False
        cur = con.execute("INSERT INTO pytania(osoba, fakt, pytanie, utworzono) VALUES(?,?,?,?)", (f["osoba"], fid, question_text(f), now_iso()))
        q = {"id": cur.lastrowid}
    return answer(con, q["id"], verdict, correction, "panel")


def answer(con, qid, verdict, correction="", channel="panel"):
    """verdict: tak | nie | pomin. Nie + poprawka → nowy fakt (pewność 1.0) i wpis w księdze poprawek."""
    q = con.execute("SELECT * FROM pytania WHERE id=?", (qid,)).fetchone()
    if not q or q["status"] not in ("czeka", "zadane"):
        return False
    f = con.execute("SELECT * FROM fakty WHERE id=?", (q["fakt"],)).fetchone()
    correction = re.sub(r"\s+", " ", correction or "").strip(" -–—:,.")
    if verdict == "tak":
        con.execute("UPDATE fakty SET status='potwierdzony', pewnosc=1.0, zmieniono=? WHERE id=?", (now_iso(), f["id"]))
        note = "tak"
    elif verdict == "nie":
        con.execute("UPDATE fakty SET status=?, zmieniono=? WHERE id=?", ("poprawiony" if correction else "odrzucony", now_iso(), f["id"]))
        if correction:
            add_fact(con, f["osoba"], f["kategoria"], correction, 1.0, f["zrodlo"], status="potwierdzony", fixes=f["id"])
        con.execute("INSERT INTO poprawki(osoba, fakt, bylo, jest, kiedy) VALUES(?,?,?,?,?)",
                    (f["osoba"], f["id"], f["tresc"], correction or "(to nieprawda)", now_iso()))
        note = "nie" + (": " + correction if correction else "")
    else:
        note = "pominięte"
    con.execute("UPDATE pytania SET status=?, odpowiedz=?, odpowiedziano=?, kanal=? WHERE id=?",
                ("pominiete" if verdict == "pomin" else "odpowiedziane", note, now_iso(), channel, qid))
    meta(con, f"zmiana:{f['osoba']}", now_iso())
    con.commit()
    return True


YES_W = r"(tak|dobrze|zgadza\w*|zgoda|prawda|racja|potwierdzam|jasne|✓|✅|👍)"
NO_W = r"(nie|zle|bzdura|falsz|nieprawda|❌|✗|👎)"
NO_STRIP = re.compile(r"(?i)^\s*(nie|źle|zle|bzdura|fałsz|falsz|nieprawda|❌|✗|👎)(?=\W|$)[\s,.:;!\-–—]*")


def parse_answers(text, numbers):
    """„1 tak, 2 nie — pracuje w X, 3 tak” → [(nr, 'tak'|'nie', poprawka)]. Numery spoza listy są pomijane.
    „tak wszystko”/„wszystko się zgadza” → tak dla wszystkich. Zwraca [] gdy to nie są odpowiedzi."""
    raw = (text or "").strip()
    t = norm(raw)
    if re.fullmatch(r"(tak\s*)?(wszystko|wszystkie)\s*(tak|dobrze|sie zgadza|ok|zgadza sie|prawda)?|(wszystko\s*)?(sie\s*)?zgadza(\s*sie)?", t) and numbers:
        return [(n, "tak", "") for n in numbers]
    clean = re.sub(r"\s+", " ", re.sub(r"[^\w\s✓✅👍]", " ", t)).strip()
    if len(numbers) == 1 and re.fullmatch(YES_W + r"(\s+\w+){0,3}", clean):
        return [(numbers[0], "tak", "")]
    if len(numbers) == 1:
        if re.match(NO_W + r"\b", t):
            return [(numbers[0], "nie", NO_STRIP.sub("", raw).strip())]
    parts = re.split(r"(?:^|[\s,;.\n])(\d{1,2})\s*[\.\):\-–—]?\s*", raw)
    out = []
    for i in range(1, len(parts) - 1, 2):
        n, body = int(parts[i]), parts[i + 1].strip(" ,;.\n")
        if n not in numbers:
            continue
        b = norm(body)
        if re.match(YES_W + r"\b", b) or not b:
            out.append((n, "tak", ""))
        elif re.match(NO_W + r"\b", b):
            out.append((n, "nie", NO_STRIP.sub("", body).strip()))
        else:
            out.append((n, "nie", body))                       # sama treść = poprawka
    return out


# ================================================================ profil (konsolidacja)

PROFILE_PROMPT = """Złóż krótki, rzeczowy opis: „{cat}” — {name}. Na podstawie faktów niżej napisz 3–10 punktów (po polsku, „• …”),
od najważniejszych. POPRAWKI mają pierwszeństwo przed wszystkim (to, co {first} sam(a) poprawił(a)). Fakty potwierdzone
są pewne; niepotwierdzone (pewność < 0.8) opisz ostrożnie („prawdopodobnie”). Nie dopisuj niczego spoza faktów.

POPRAWKI:
{fixes}

FAKTY (pewność, ile razy się powtórzyło):
{facts}

Zwróć wyłącznie JSON: {{"tekst": "• …\\n• …"}}"""


def facts_for(con, pid, cat, limit=120):
    rows = con.execute("SELECT * FROM fakty WHERE osoba=? AND kategoria=? AND status IN ('nowy','potwierdzony')", (pid, cat)).fetchall()
    rows = sorted(rows, key=lambda r: (r["status"] != "potwierdzony", -(r["pewnosc"] * (1 + min(r["potwierdzen"], 10) / 5)), -r["id"]))
    return rows[:limit]


def consolidate(con, pid, ask=None):
    """Profil osoby: kategoria po kategorii. Bez modelu — punkty z najmocniejszych faktów."""
    p = person(con, pid)
    if not p:
        return 0
    fixes = [r for r in con.execute("SELECT bylo, jest FROM poprawki WHERE osoba=? ORDER BY id DESC LIMIT 30", (pid,))]
    n = 0
    for cat, label in CATEGORIES:
        rows = facts_for(con, pid, cat)
        if not rows:
            continue
        text = ""
        if ask is not None:
            out = ask(PROFILE_PROMPT.format(cat=label, name=p["imie"], first=first_name(p),
                                            fixes="\n".join(f"• było: {f['bylo']} → jest: {f['jest']}" for f in fixes) or "(brak)",
                                            facts="\n".join(f"• ({r['pewnosc']:.1f}, {r['potwierdzen']}×{', potwierdzone' if r['status'] == 'potwierdzony' else ''}) {r['tresc']}"
                                                            for r in rows)))
            if isinstance(out, dict):
                text = str(out.get("tekst") or "").strip()
        if not text:
            text = "\n".join(("• " if r["status"] == "potwierdzony" or r["pewnosc"] >= 0.8 else "• (prawdopodobnie) ") + r["tresc"] for r in rows[:10])
        con.execute("INSERT OR REPLACE INTO profil(osoba, kategoria, tekst, zaktualizowano) VALUES(?,?,?,?)", (pid, cat, text[:4000], now_iso()))
        con.commit()                                   # 2.32: nie trzymam bazy zablokowanej, gdy model myśli nad kolejną kategorią
        n += 1
    meta(con, f"profil:{pid}", now_iso())
    meta(con, f"zmiana:{pid}", "")
    con.commit()
    return n


def profile_text(con, pid, query="", limit=3000):
    """Co Sebastian wie o osobie — dla odpowiedzi na WhatsAppie i dla innych dodatków."""
    rows = con.execute("SELECT kategoria, tekst FROM profil WHERE osoba=?", (pid,)).fetchall()
    parts = [f"[{CAT[r['kategoria']]}]\n{r['tekst']}" for r in sorted(rows, key=lambda r: CAT_ORDER.get(r["kategoria"], 9)) if r["tekst"]]
    text = "\n".join(parts)
    words = [w for w in re.findall(r"\w{4,}", norm(query))][:8]
    if words:
        like = " OR ".join("klucz LIKE ?" for _ in words)
        hits = con.execute(f"SELECT id, tresc FROM fakty WHERE osoba=? AND status IN ('nowy','potwierdzony') AND ({like}) "
                           f"ORDER BY pewnosc DESC LIMIT 12", (pid, *[f"%{w[:max(4, len(w) - 2)]}%" for w in words])).fetchall()
        if hits:
            text += "\n[Pasujące fakty]\n" + "\n".join("• " + h["tresc"] for h in hits)
            con.executemany("UPDATE fakty SET uzyto=?, ile_uzyc=ile_uzyc+1 WHERE id=?", [(now_iso(), h["id"]) for h in hits])
            con.commit()
    return text[:limit]


def stats(con, pid=None):
    w, a = ("WHERE osoba=?", (pid,)) if pid else ("", ())
    one = lambda q: con.execute(q, a).fetchone()[0]
    return {"fakty": one(f"SELECT COUNT(*) FROM fakty {w}"),
            "potwierdzone": one(f"SELECT COUNT(*) FROM fakty {w} {'AND' if w else 'WHERE'} status='potwierdzony'"),
            "pytania": one(f"SELECT COUNT(*) FROM pytania {w} {'AND' if w else 'WHERE'} status IN ('czeka','zadane')"),
            "zrodla": one(f"SELECT COUNT(*) FROM zrodla {w}"),
            "w_kolejce": con.execute("SELECT COUNT(*) FROM kawalki k JOIN zrodla z ON z.id=k.zrodlo WHERE k.status='nowy'"
                                     + (" AND z.osoba=?" if pid else ""), a).fetchone()[0]}
