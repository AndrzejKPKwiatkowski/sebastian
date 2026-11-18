"""Rekrutacja — uwagi Agi do ofert i to, czego Sebastian się z nich uczy (2.16).

Przy każdej ofercie Aga może zaznaczyć, co jej nie pasuje (albo że oferta jest świetna) i dopisać zdanie od siebie.
Sebastian zamienia to na proste, jawne zasady, które Aga widzi i może usuwać w Ustawieniach:
  * angielski — pomijaj ogłoszenia po angielsku i takie, które wymagają biegłego angielskiego,
  * unikaj    — hasła (np. „AutoCAD”, „uprawnienia geodezyjne”), których obecność w ogłoszeniu oznacza „nie dla mnie”,
  * lubi      — hasła, które oznaczają „więcej takich” (podnoszą ocenę dopasowania),
  * zasady    — krótkie zdania jej słowami; trafiają do oceny każdej nowej oferty.
Zasada prawdy: hasło trafia do „unikaj”/„lubi” tylko wtedy, gdy występuje w tej ofercie albo w słowach Agi.
"""
import contextlib, json, re

from . import rdzen as R

TAGS = [
    ("angielski", "Po angielsku — wolę rekrutację po polsku"),
    ("programy", "Wymaga programów lub uprawnień, których nie mam"),
    ("branza", "Nie moja branża"),
    ("dojazd", "Za daleko albo zły dojazd"),
    ("pensja", "Za niska pensja"),
    ("sprzedaz", "Za dużo sprzedaży lub obsługi klienta"),
    ("lubie", "Świetna — szukaj więcej takich"),
]
TAG_NAMES = dict(TAGS)
BASIC_TOOLS = {"excel", "word", "office", "ms office", "pakietu ms office", "powerpoint", "outlook", "google", "internet", "windows",
               "teams", "zoom", "pakiet office", "ms excel", "ms word", "komputer", "komputera"}
PLACES = {"krakow", "krakowie", "krakowa", "tyniec", "tyncu", "polska", "polsce", "malopolska", "malopolskie", "warszawa", "warszawie",
          "zdalnie", "zdalna", "hybrydowo", "hybrydowa", "stacjonarnie", "biuro", "biurze", "praca", "pracy", "umowa", "etat", "ai"}
NEG_TAGS = {"angielski", "programy", "branza", "sprzedaz"}            # tylko z nich mogą powstać hasła „pomijam”
WARN_TAIL = "prosiłaś, żeby takie"
EN_WORDS = {"the", "and", "you", "with", "will", "our", "for", "are", "we", "of", "to", "in", "your", "is", "be", "this", "on", "as", "an"}
PL_WORDS = {"i", "w", "z", "na", "do", "się", "jest", "oraz", "dla", "nie", "że", "od", "po", "jako", "w", "lub", "przez", "będzie", "nas"}
ENGLISH_REQ = re.compile(r"(angielsk\w*|english).{0,40}?(biegł|\bc1\b|\bc2\b|\bb2\b|fluent|advanced|bardzo dobr|komunikatywn|swobodn|zaawansowan)|"
                         r"(biegł\w*|zaawansowan\w*|bardzo dobr\w*|swobodn\w*)\s+(znajomo\w+\s+)?(język\w*\s+)?angielsk|"
                         r"(fluent|advanced|very good|excellent|proficient)\W{0,20}english", re.I)


# ---------------------------------------------------------------- baza

def ensure(c):
    c.execute("CREATE TABLE IF NOT EXISTS uwagi_ofert(id INTEGER PRIMARY KEY, aplikacja_id INTEGER, tagi TEXT, tekst TEXT, "
              "nauka TEXT DEFAULT '', kiedy TEXT)")


def load(c):
    try:
        p = json.loads(R.meta_get(c, "preferencje") or "{}")
    except ValueError:
        p = {}
    p.setdefault("angielski", False)
    for k in ("unikaj", "lubi", "zasady"):
        p.setdefault(k, [])
    return p


def save(c, p):
    R.meta_set(c, "preferencje", json.dumps(p, ensure_ascii=False))
    c.commit()


def feedback_for(c, aid):
    ensure(c)
    return [dict(r) for r in c.execute("SELECT * FROM uwagi_ofert WHERE aplikacja_id=? ORDER BY id DESC", (aid,)).fetchall()]


# ---------------------------------------------------------------- rozpoznawanie w ogłoszeniu

def has(text, phrase):
    ph = R.plain(phrase).strip()
    return bool(ph) and re.search(r"(?<![a-z0-9])" + re.escape(ph) + r"(?![a-z0-9])", R.plain(text or "")) is not None


def mostly_english(text):
    words = re.findall(r"[a-ząćęłńóśźż]+", (text or "").lower())
    en = sum(1 for w in words if w in EN_WORDS)
    pl = sum(1 for w in words if w in PL_WORDS)
    return en >= 15 and en > 2 * pl


def english_required(text):
    return bool(ENGLISH_REQ.search(text or ""))


def check(c, text, model_says_english=False):
    """(ostrzeżenia, polubione hasła) dla treści ogłoszenia według nauczonych zasad."""
    p = load(c)
    warn = []
    if p["angielski"] and (model_says_english or mostly_english(text) or english_required(text)):
        warn.append("Ogłoszenie po angielsku albo wymaga biegłego angielskiego — prosiłaś, żeby takie pomijać.")
    hits = [u["haslo"] for u in p["unikaj"] if has(text, u["haslo"])]
    if hits:
        warn.append(f"Wymaga: {', '.join(hits[:4])} — prosiłaś, żeby takie oferty pomijać.")
    likes = [u["haslo"] for u in p["lubi"] if has(text, u["haslo"])]
    return warn, likes


def prompt_part(c):
    """Fragment do oceny oferty przez model: to, czego Aga nauczyła Sebastiana."""
    p = load(c)
    lines = []
    if p["zasady"]:
        lines.append("Z jej uwag do wcześniejszych ofert: " + " ".join(z["tekst"].rstrip(".") + "." for z in p["zasady"][-12:]))
    if p["unikaj"]:
        lines.append("Oferty wymagające tego jej nie pasują: " + ", ".join(u["haslo"] for u in p["unikaj"][-25:]) + ".")
    if p["lubi"]:
        lines.append("Chętnie widzi oferty z: " + ", ".join(u["haslo"] for u in p["lubi"][-15:]) + ".")
    if p["angielski"]:
        lines.append("Nie chce ofert po angielsku ani wymagających biegłego angielskiego.")
    return "\n".join(lines)


# ---------------------------------------------------------------- nauka z uwagi

def _candidates(lines):
    """Nazwy programów/uprawnień z punktów wymagań (bez modelu)."""
    out = []
    for line in lines:
        if not re.search(r"program|oprogramowan|znajomo|obsług|uprawnie|certyfik|licencj|system", line, re.I):
            continue
        for m in re.finditer(r"\b([A-Z][A-Za-z0-9+#.\-]{1,}(?:[ -][A-Z0-9][A-Za-z0-9+#.\-]*)?)", line):
            w = m.group(1).strip(".-")
            if len(w) >= 2 and R.plain(w) not in BASIC_TOOLS and not w.lower().startswith(("znajomo", "obsług", "do", "min")):
                out.append(w)
        m = re.search(r"uprawnie\w*\s+([a-ząćęłńóśźż]+(?:\s+[a-ząćęłńóśźż]+)?)", line, re.I)
        if m:
            out.append("uprawnienia " + m.group(1).split()[0])
    seen, res = set(), []
    for w in out:
        if R.plain(w) not in seen:
            seen.add(R.plain(w))
            res.append(w)
    return res[:6]


def ok_avoid(f, h):
    """Czy hasło nadaje się na „pomijam”: nie miejsce pracy, nie to, czego Aga szuka, nie skrót z 1–2 liter."""
    p = R.plain(h).strip()
    if len(p) < 3 or p in PLACES or p in BASIC_TOOLS:
        return False
    city = R.plain((f.get("osoba") or {}).get("miasto") or "")
    if city and p.startswith(city[:5]):
        return False
    wanted = R.plain(" ".join((f.get("kryteria") or {}).get("chce", [])))
    return not (len(p) >= 5 and p in wanted)


def save_feedback(ctx, aid, tags, text):
    """Zapis od razu (bez czekania na model). Zwraca id uwagi albo None."""
    tags = [t for t in tags if t in TAG_NAMES]
    text = (text or "").strip()[:1500]
    if not tags and not text:
        return None
    with R.db(ctx) as c:
        ensure(c)
        cur = c.execute("INSERT INTO uwagi_ofert(aplikacja_id,tagi,tekst,nauka,kiedy) VALUES(?,?,?,?,?)",
                        (aid, json.dumps(tags), text, "", R.stamp(ctx)))
        R.note(c, ctx, aid, "uwaga Agi: " + ", ".join([TAG_NAMES[t] for t in tags] + ([text[:80]] if text else [])))
        c.commit()
        return cur.lastrowid


def learn(ctx, aid, tags, text):
    """Zapis + nauka od razu (polecenia i testy)."""
    fid = save_feedback(ctx, aid, tags, text)
    return learn_from(ctx, fid) if fid else []


def learn_from(ctx, fid):
    """Nauka z zapisanej uwagi (w tle). Zwraca listę tego, czego Sebastian się nauczył."""
    from . import dokumenty as D
    with R.db(ctx) as c:
        ensure(c)
        u = c.execute("SELECT * FROM uwagi_ofert WHERE id=?", (fid,)).fetchone()
        if not u:
            return []
        aid, tags, text = u["aplikacja_id"], json.loads(u["tagi"] or "[]"), u["tekst"] or ""
        a = dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone())
    f = R.load_facts(ctx)
    try:
        info = json.loads(a.get("analiza") or "{}")
    except ValueError:
        info = {}
    reqs = [str(x) for x in (info.get("wymagania") or [])]
    offer = a.get("tresc") or ""
    got = None
    prompt = f"""Aga szuka pracy. Oceniła ofertę i chce, żeby Sebastian (jej asystent) wyciągnął z tego zasady na przyszłość.

OFERTA: {a.get('stanowisko') or ''} — {a.get('firma') or ''}
WYMAGANIA: {'; '.join(reqs)[:2500] or '(brak listy)'}
FRAGMENT OGŁOSZENIA: {offer[:2500]}

ZAZNACZYŁA: {', '.join(TAG_NAMES[t] for t in tags) or '—'}
NAPISAŁA: {text or '—'}

Zwróć wyłącznie JSON:
{{"unikaj": ["0–4 krótkich haseł (1–3 słowa), których obecność w ogłoszeniu oznacza dla niej ofertę do pominięcia — nazwy programów,
  uprawnień, branż; TYLKO gdy wynika to z jej uwagi (coś jej NIE pasuje) i hasło występuje w tej ofercie albo w jej słowach;
  NIGDY miejsca pracy (miasta, dzielnice), formy pracy ani ogólniki typu „Excel”"],
 "lubi": ["0–4 haseł oznaczających oferty, które chce widzieć częściej — tylko gdy oferta jej się podobała"],
 "angielski": true/false (czy chce pomijać oferty po angielsku albo wymagające biegłego angielskiego),
 "zasada": "jedno krótkie zdanie po polsku, w 3. osobie, co brać pod uwagę przy kolejnych ofertach; pusty tekst, gdy uwaga jest zbyt ogólna (np. „spoko”)"}}"""
    if tags or len(text) >= 25:
        with contextlib.suppress(Exception):
            got = D.write(ctx, prompt, max_tokens=500, temperature=0.1)
    learned = {"unikaj": [], "lubi": [], "angielski": "angielski" in tags, "zasada": ""}
    source = offer + "\n" + text
    negative = bool(set(tags) & NEG_TAGS) or (text and not tags and "lubie" not in tags)
    if isinstance(got, dict):
        for k in ("unikaj", "lubi"):
            for h in (got.get(k) or [])[:4]:
                h = re.sub(r"\s+", " ", str(h)).strip(" .,;:\"'„”")[:40]
                if not has(source, h) or R.plain(h) in BASIC_TOOLS:
                    continue
                if k == "unikaj" and (not negative or not ok_avoid(f, h)):
                    continue
                if k == "lubi" and (len(R.plain(h)) < 3 or R.plain(h) in PLACES):
                    continue
                learned[k].append(h)
        learned["angielski"] = learned["angielski"] or got.get("angielski") is True
        z = re.sub(r"\s+", " ", str(got.get("zasada") or "")).strip()[:200]
        if z and not re.search(r"\[(pominięte|e-mail|telefon)\]", z):
            learned["zasada"] = z
    if not got:                                                   # bez modelu: proste reguły
        if "programy" in tags:
            learned["unikaj"] = [h for h in _candidates(reqs or offer.splitlines()) if has(source, h) and ok_avoid(f, h)][:4]
        if "lubie" in tags and a.get("stanowisko"):
            learned["lubi"] = [re.split(r"[/(,–-]", a["stanowisko"])[0].strip()[:40]]
        if len(text) >= 25:
            learned["zasada"] = f"Uwaga do oferty „{(a.get('stanowisko') or 'oferta')[:60]}”: {text[:160]}"
        elif tags and not set(tags) <= {"lubie", "angielski"}:
            parts = [TAG_NAMES[t].split(" — ")[0].lower() for t in tags if t not in ("angielski", "lubie")]
            learned["zasada"] = f"Oferta „{(a.get('stanowisko') or 'oferta')[:60]}”: {', '.join(parts)}."
    now = R.stamp(ctx)
    out = []
    with R.db(ctx) as c:
        p = load(c)
        if learned["angielski"] and not p["angielski"]:
            p["angielski"] = True
            out.append("pomijam oferty po angielsku i wymagające biegłego angielskiego")
        for k, label in (("unikaj", "pomijam oferty wymagające"), ("lubi", "szukam więcej ofert z")):
            have = {R.plain(u["haslo"]) for u in p[k]}
            new = [h for h in learned[k] if R.plain(h) not in have]
            p[k] += [{"haslo": h, "skad": aid, "kiedy": now} for h in new]
            if new:
                out.append(f"{label}: {', '.join(new)}")
        if learned["zasada"] and R.plain(learned["zasada"]) not in {R.plain(z["tekst"]) for z in p["zasady"]}:
            p["zasady"].append({"tekst": learned["zasada"], "skad": aid, "kiedy": now})
            p["zasady"] = p["zasady"][-40:]
            out.append("zapamiętałem Twoją uwagę")
        save(c, p)
        c.execute("UPDATE uwagi_ofert SET nauka=? WHERE id=?", ("; ".join(out) or "zapisane — bez nowych zasad", fid))
        c.commit()
    return out


def cleanup(ctx):
    """Usuwa hasła „pomijam”, które nie powinny tam trafić (miejsca pracy, to, czego Aga szuka, 1–2 litery) i odświeża ostrzeżenia."""
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        p = load(c)
        good = [u for u in p["unikaj"] if ok_avoid(f, u["haslo"])]
        removed = [u["haslo"] for u in p["unikaj"] if u not in good]
        if removed:
            p["unikaj"] = good
            save(c, p)
    flag_waiting(ctx)
    return removed


def flag_waiting(ctx, skip=0):
    """Po nowej zasadzie: oznacza czekające oferty, które jej nie spełniają (nie odrzuca — decyzja należy do Agi)."""
    n = 0
    with R.db(ctx) as c:
        rows = c.execute("SELECT id, tresc, ostrzezenia FROM aplikacje WHERE status IN ('do_zatwierdzenia','do_sprawdzenia','formularz','do_uzupelnienia') "
                         "AND id<>?", (skip,)).fetchall()
        for r in rows:
            warn, _ = check(c, r["tresc"] or "")
            try:
                cur = json.loads(r["ostrzezenia"] or "[]")
            except ValueError:
                cur = []
            keep = [w for w in cur if WARN_TAIL not in w]                # stare ostrzeżenia z zasad liczę od nowa
            if keep + warn != cur:
                c.execute("UPDATE aplikacje SET ostrzezenia=? WHERE id=?", (json.dumps(keep + warn, ensure_ascii=False), r["id"]))
                n += bool(warn)
        c.commit()
    return n
