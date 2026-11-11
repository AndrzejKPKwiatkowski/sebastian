"""Rekrutacja — import wiedzy o Adze (np. z ChatGPT) do bazy faktów (2.8.1).

Dwie drogi: (1) wklejone podsumowanie z ChatGPT, (2) eksport danych ChatGPT (conversations.json albo cały ZIP).
Z eksportu biorę WYŁĄCZNIE wiadomości napisane przez Agę (nie odpowiedzi ChatGPT, które mogą zawierać zmyślenia)
i tylko z rozmów o pracy i rekrutacji. Model proponuje fakty, ale do bazy trafiają tylko te, które Aga zaznaczy.
Praca odbywa się w tle, po kawałku, żeby nie blokować panelu.
"""
import contextlib, io, json, re, zipfile

from . import rdzen as R

TOPIC = ("cv", "rekrutac", "list motywac", "list przewod", "rozmow", "kwalifikac", "stanowisk", "prac", "kariera", "doswiadcz",
         "umiejetnos", "ogloszen", "aplikac", "pracodaw", "linkedin", "zarobk", "wynagrodz", "etat", "umow")
CHUNK = 7000
MAX_CHUNKS = 25


def folder(ctx):
    p = ctx.folder() / "import"
    p.mkdir(exist_ok=True)
    return p


def _user_texts_from_export(data):
    """Wiadomości Agi z rozmów o pracy (eksport ChatGPT: lista rozmów z polem mapping)."""
    out = []
    for conv in data if isinstance(data, list) else []:
        title = str(conv.get("title") or "")
        msgs = []
        for node in (conv.get("mapping") or {}).values():
            m = (node or {}).get("message") or {}
            if ((m.get("author") or {}).get("role")) != "user":
                continue
            parts = (m.get("content") or {}).get("parts") or []
            text = "\n".join(p for p in parts if isinstance(p, str)).strip()
            if text:
                msgs.append((m.get("create_time") or 0, text))
        if not msgs:
            continue
        joined = "\n".join(t for _, t in sorted(msgs, key=lambda x: x[0] or 0))
        low = R.plain(title + " " + joined[:4000])
        if sum(w in low for w in TOPIC) >= 2:
            out.append(f"### Rozmowa: {title}\n{joined}")
    return out


def start(ctx, text="", upload=None, filename=""):
    """Zakłada zadanie importu. Zwraca (liczba_kawałków, komunikat)."""
    pieces, kind = [], "wklejone"
    if upload:
        raw = upload
        if filename.lower().endswith(".zip") or raw[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                name = next((n for n in z.namelist() if n.endswith("conversations.json")), "")
                if not name:
                    return 0, "W pliku ZIP nie ma conversations.json. Wgraj plik z eksportu danych ChatGPT."
                raw = z.read(name)
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            return 0, "To nie wygląda na plik conversations.json z eksportu ChatGPT."
        pieces, kind = _user_texts_from_export(data), "eksport"
        if not pieces:
            return 0, "Nie znalazłem w eksporcie rozmów o pracy i rekrutacji."
    elif text.strip():
        pieces = [text.strip()]
    else:
        return 0, "Wklej tekst albo wybierz plik."
    chunks, buf = [], ""
    for p in pieces:
        while p:
            room = CHUNK - len(buf)
            buf += p[:room] + "\n\n"
            p = p[room:]
            if len(buf) >= CHUNK:
                chunks.append(buf)
                buf = ""
    if buf.strip():
        chunks.append(buf)
    chunks = chunks[:MAX_CHUNKS]
    job = {"rodzaj": kind, "kawalki": chunks, "gotowe": 0, "kandydaci": [], "status": "w toku", "utworzono": R.stamp(ctx)}
    (folder(ctx) / "zadanie.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    return len(chunks), ""


def load(ctx):
    with contextlib.suppress(Exception):
        return json.loads((folder(ctx) / "zadanie.json").read_text(encoding="utf-8"))
    return None


def save(ctx, job):
    (folder(ctx) / "zadanie.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")


def clear(ctx):
    (folder(ctx) / "zadanie.json").unlink(missing_ok=True)


def extract(ctx, f, chunk, kind):
    source = ("To wiadomości napisane przez kandydatkę w rozmowach z asystentem AI." if kind == "eksport"
              else "To podsumowanie przygotowane przez asystenta AI na podstawie rozmów z kandydatką.")
    prompt = f"""{source}
Wypisz z tekstu WYŁĄCZNIE fakty o jej pracy i kwalifikacjach, które są w nim powiedziane wprost. Niczego nie dopowiadaj.
Pomiń fakty, które już są w BAZIE. Fakty oznaczone w tekście jako niepewne albo przypuszczenia daj do "niepewne".
Pisz po polsku, krótko, w stylu punktów do CV (bez „ja”, bez ozdobników).

BAZA (już zapisane):
{R.facts_brief(f, ids=False)[:5000]}

TEKST:
{chunk}

Zwróć JSON:
{{"profil": ["zdanie do profilu zawodowego w 1. osobie, np. „Mam doświadczenie w …”"],
  "punkty": [{{"stanowisko": "nazwa stanowiska z BAZY albo nowe", "firma": "firma", "tekst": "obowiązek lub osiągnięcie"}}],
  "stanowiska": [{{"stanowisko": "", "firma": "", "miejsce": "", "od": "MM.RRRR", "do": "MM.RRRR albo obecnie"}}],
  "umiejetnosci": [""], "narzedzia": [{{"nazwa": "", "poziom": "podstawowy|dobry|bardzo dobry|"}}],
  "kursy": [""], "jezyki": [""], "odpowiedzi": [{{"pytanie": "np. Oczekiwania finansowe", "odpowiedz": ""}}],
  "niepewne": [""]}}"""
    out = ctx.ask(prompt, as_json=True, max_tokens=1500, temperature=0.1)
    return out if isinstance(out, dict) else None


def _items(out):
    """Kandydaci jako płaska lista: {"id", "rodzaj", "tekst", "dane", "niepewne"}."""
    res = []
    add = lambda kind, text, data=None, unsure=False: res.append({"rodzaj": kind, "tekst": str(text).strip()[:400], "dane": data or {}, "niepewne": unsure}) if str(text).strip() else None
    money = re.compile(r"(\d[\d\s]*(zl|pln)|zarob|wynagrodz|na godzin|netto|brutto)")
    for key in ("profil", "umiejetnosci", "kursy", "jezyki", "niepewne"):
        out[key] = [x for x in out.get(key) or [] if not money.search(R.plain(str(x)))]       # zarobki Agi nigdy nie trafiają do CV
    out["punkty"] = [x for x in out.get("punkty") or [] if isinstance(x, dict) and not money.search(R.plain(str(x.get("tekst", ""))))]
    for x in out.get("profil") or []:
        add("profil", x)
    for x in out.get("punkty") or []:
        if isinstance(x, dict):
            add("punkt", f"{x.get('tekst', '')}  — {x.get('stanowisko', '')}, {x.get('firma', '')}".strip(" —,"), x)
    for x in out.get("stanowiska") or []:
        if isinstance(x, dict) and x.get("stanowisko") and x.get("od"):
            add("stanowisko", f"{x.get('stanowisko')} — {x.get('firma', '')} ({x.get('od', '')} – {x.get('do', '')})", x)
    for key, kind in (("umiejetnosci", "umiejetnosc"), ("kursy", "kurs"), ("jezyki", "jezyk")):
        for x in out.get(key) or []:
            add(kind, x)
    for x in out.get("narzedzia") or []:
        if isinstance(x, dict) and x.get("nazwa"):
            add("narzedzie", x["nazwa"] + (f" – {x['poziom']}" if x.get("poziom") else ""), x)
    pay = re.compile(r"(zarob|wynagrodz|pensj|stawk|zl\b|pln|netto|brutto|na godzin|/h\b)")
    for x in out.get("odpowiedzi") or []:
        if isinstance(x, dict) and x.get("pytanie") and x.get("odpowiedz") and not pay.search(R.plain(f"{x['pytanie']} {x['odpowiedz']}")):
            add("odpowiedz", f"{x['pytanie']}: {x['odpowiedz']}", x)
    for x in out.get("niepewne") or []:
        add("niepewne", x, unsure=True)
    return res


def work(ctx):
    """Jeden kawałek importu na obrót pracy w tle. True, gdy coś zrobiono."""
    job = load(ctx)
    if not job or job.get("status") != "w toku":
        return False
    if job["gotowe"] >= len(job["kawalki"]):
        seen, uniq = set(), []
        for c in job["kandydaci"]:
            k = (c["rodzaj"], R.norm(c["tekst"]))
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        for i, c in enumerate(uniq):
            c["id"] = i
        job.update(kandydaci=uniq, status="do przejrzenia", kawalki=[])
        save(ctx, job)
        return True
    f = R.load_facts(ctx)
    out = None
    with contextlib.suppress(Exception):
        out = extract(ctx, f, job["kawalki"][job["gotowe"]], job["rodzaj"])
    if out:
        job["kandydaci"] += _items(out)
    job["gotowe"] += 1
    save(ctx, job)
    return True


def apply(ctx, chosen_ids):
    """Dopisuje zaznaczone fakty do bazy. Zwraca liczbę dodanych."""
    job = load(ctx)
    if not job:
        return 0
    f = R.load_facts(ctx)
    have = lambda lst, t: R.norm(t) in {R.norm(x["tekst"] if isinstance(x, dict) else x) for x in lst}
    n = 0
    raw = {k: [x["tekst"] for x in f[k]] for k in ("profil", "umiejetnosci", "kursy", "jezyki")}
    jobs = [dict(j, punkty=[p["tekst"] for p in j["punkty"]]) for j in f["doswiadczenie"]]
    tools = [{"nazwa": t["nazwa"], "poziom": t["poziom"]} for t in f["narzedzia"]]
    for c in job["kandydaci"]:
        if c.get("id") not in chosen_ids or c["rodzaj"] == "niepewne":
            continue
        kind, t, d = c["rodzaj"], c["tekst"], c.get("dane") or {}
        target = {"profil": "profil", "umiejetnosc": "umiejetnosci", "kurs": "kursy", "jezyk": "jezyki"}.get(kind)
        if target:
            if not have(raw[target], t):
                raw[target].append(t)
                n += 1
        elif kind == "narzedzie":
            if not any(R.norm(x["nazwa"]) == R.norm(d.get("nazwa", "")) for x in tools):
                tools.append({"nazwa": d.get("nazwa", "").strip(), "poziom": d.get("poziom", "") if d.get("poziom") in R.LEVELS else ""})
                n += 1
        elif kind == "stanowisko":
            if not any(R.norm(j["stanowisko"]) == R.norm(d.get("stanowisko", "")) and R.norm(j.get("firma", "")) == R.norm(d.get("firma", "")) for j in jobs):
                jobs.append({k: str(d.get(k, "")).strip() for k in ("stanowisko", "firma", "miejsce", "od", "do")} | {"punkty": []})
                n += 1
        elif kind == "punkt":
            text = str(d.get("tekst", "")).strip()
            job_ = next((j for j in jobs if R.norm(j["stanowisko"]) == R.norm(d.get("stanowisko", ""))), None) or \
                next((j for j in jobs if d.get("firma") and R.norm(j.get("firma", "")) == R.norm(d.get("firma", ""))), None)
            if job_ and text and not have(job_["punkty"], text):
                job_["punkty"].append(text)
                n += 1
        elif kind == "odpowiedz":
            f.setdefault("odpowiedzi", {})[str(d.get("pytanie"))[:200]] = str(d.get("odpowiedz"))[:400]
            n += 1
    f.update(raw)
    f["doswiadczenie"], f["narzedzia"] = jobs, tools
    R.save_facts(ctx, f)
    clear(ctx)
    return n
