"""Rekrutacja — pisanie przez API Google Gemini (list motywacyjny, opis w CV, wyjaśnienia dopasowania).

Zasady:
- do Google idą tylko fakty zawodowe i treść ogłoszenia — imię, nazwisko, e-mail, telefon, LinkedIn i adres są
  usuwane z zapytania przed wysłaniem (podpis i dane kontaktowe Sebastian dopisuje lokalnie),
- kontrola prawdy i języka zostaje na Macu (to samo sito co dla modelu lokalnego),
- dzienny limit zapytań; po błędzie limitu (429) albo braku odpowiedzi — przerwa i powrót do modelu lokalnego (Bielik),
- model wybierany automatycznie z listy dostępnych dla klucza (najnowszy „flash”), można go wskazać w ustawieniach.
"""
import contextlib, json, re, time

from . import rdzen as R

API = "https://generativelanguage.googleapis.com/v1beta"
_MODEL = {"at": 0.0, "name": None, "names": [], "key": ""}
_LAST = {"at": 0.0, "ok": 0.0}
ONLY = {"on": False}                                                   # przepisywanie: tylko Gemini, bez modelu lokalnego (nie marnuję czasu Bielika)
PACE = 13.0                                                            # najwyżej ok. 4–5 zapytań na minutę (darmowy poziom: 5/min)


def key(ctx):
    return R.secret(ctx, "gemini") or ""


def _version(name):
    nums = re.findall(r"\d+(?:\.\d+)?", name.split("/")[-1])
    return float(nums[0]) if nums else 0.0


def ranked(names, want=""):
    """Kolejność modeli do pisania: wskazany w ustawieniach albo najnowsze stabilne „flash”, potem „flash-lite”
    (osobne limity — gdy jeden wyczerpie dzienny przydział albo jest przeciążony, piszę następnym)."""
    names = [n.split("/")[-1] for n in names]
    if want:
        return [want] if want in names else []
    ok = [n for n in names if "gemini" in n and "flash" in n and not re.search(r"image|tts|embed|audio|live|thinking-exp|learnlm", n)]
    def order(pool):
        stable = [n for n in pool if "preview" not in n and "exp" not in n]
        return sorted(stable, key=lambda n: (_version(n), "latest" not in n, n), reverse=True) or \
               sorted(pool, key=lambda n: (_version(n), n), reverse=True)[:1]
    return order([n for n in ok if "lite" not in n]) + order([n for n in ok if "lite" in n])


def pick_model(names, want=""):
    """Pierwszy model z kolejności (zgodność z 2.12)."""
    r = [n for n in ranked(names, want) if "lite" not in n] or ranked(names, want)
    return r[0] if r else None


def blocks(c):
    now = time.time()
    return {m: t for m, t in json.loads(R.meta_get(c, "gemini_blokady") or "{}").items() if t > now}


def block(ctx, name, seconds, why):
    with R.db(ctx) as c:
        b = blocks(c)
        b[name] = time.time() + seconds
        R.meta_set(c, "gemini_blokady", json.dumps(b))
        R.meta_set(c, "gemini_powod", why)
        c.commit()


def _until_pacific_midnight():
    """Dzienne limity Google zerują się o północy czasu pacyficznego (u nas ok. 9:00)."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    now = dt.datetime.now(ZoneInfo("America/Los_Angeles"))
    nxt = (now + dt.timedelta(days=1)).replace(hour=0, minute=2, second=0, microsecond=0)
    return (nxt - now).total_seconds()


def candidates(ctx, http=None):
    k = key(ctx)
    if not k:
        return []
    if not (_MODEL["names"] and _MODEL["key"] == k and time.time() - _MODEL["at"] < 6 * 3600):
        code, data = (http or _http)("GET", f"{API}/models?pageSize=200", k, None)
        if code != 200:
            return []
        names = [m["name"] for m in data.get("models", []) if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        _MODEL.update(at=time.time(), names=ranked(names, str(ctx.settings().get("gemini_model") or "").strip()), key=k)
    return list(_MODEL["names"])


def model(ctx, http=None):
    """Pierwszy model, który nie ma teraz blokady (limitu dziennego, przeciążenia)."""
    names = candidates(ctx, http)
    with R.db(ctx) as c:
        b = blocks(c)
    free = [n for n in names if n not in b]
    _MODEL["name"] = free[0] if free else (names[0] if names else None)
    if names and not free:
        with R.db(ctx) as c:                                           # wszystkie zablokowane — czekam do najbliższego odblokowania
            R.meta_set(c, "gemini_przerwa", min(b[n] for n in names))
            c.commit()
        return None
    return _MODEL["name"]


def _http(method, url, k, body):
    import requests
    r = requests.request(method, url, headers={"x-goog-api-key": k, "Content-Type": "application/json"},
                         data=json.dumps(body) if body is not None else None, timeout=180)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def redact(text, f):
    """Bez danych osobowych: imię i nazwisko, e-mail, telefon, LinkedIn, adres."""
    o = f.get("osoba", {})
    full = R.full_name(f)
    out = text.replace(f"Kandydatka: {full}", "Kandydatka (dane osobowe pominięte)")
    for v in (full, o.get("email"), o.get("telefon"), o.get("linkedin"), o.get("adres"), o.get("nazwisko")):
        if v and len(str(v)) > 3:
            out = out.replace(str(v), "[pominięte]")
    out = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[e-mail]", out)
    out = re.sub(r"(?<!\d)(?:\+?48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)", "[telefon]", out)
    return re.sub(r"https?://(www\.)?linkedin\.com/\S+", "[linkedin]", out)


def available(ctx):
    """Czy wolno teraz pytać Gemini (klucz, włączone, nie ma przerwy, nie przekroczono dziennego limitu)."""
    st = ctx.settings()
    if not key(ctx) or str(st.get("pisanie", "gemini")) != "gemini":
        return False
    with R.db(ctx) as c:
        if float(R.meta_get(c, "gemini_przerwa", "0") or 0) > time.time():
            return False
        used = int(R.meta_get(c, f"gemini_{ctx.now().date().isoformat()}", "0") or 0)
    return used < int(st.get("gemini_limit_dzienny", 300) or 300)


def _count(ctx, ok=True, pause=0):
    with R.db(ctx) as c:
        k = f"gemini_{ctx.now().date().isoformat()}"
        R.meta_set(c, k, int(R.meta_get(c, k, "0") or 0) + 1)
        if pause:
            R.meta_set(c, "gemini_przerwa", time.time() + pause)
        if not ok:
            R.meta_set(c, "gemini_ostatni_blad", R.stamp(ctx))
        c.commit()


def ask_json(ctx, prompt, max_tokens=1200, temperature=0.5, http=None):
    """JSON od Gemini albo None (wtedy piszący wraca do modelu lokalnego)."""
    if not available(ctx):
        return None
    http = http or _http
    name = model(ctx, http)
    if not name:
        if not candidates(ctx, http):
            _count(ctx, ok=False, pause=1800)
        return None
    f = R.load_facts(ctx)
    body = {"contents": [{"role": "user", "parts": [{"text": redact(prompt, f)}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max(4096, max_tokens * 3),
                                 "responseMimeType": "application/json"}}
    wait = PACE - (time.time() - _LAST["at"])                           # równe tempo: darmowy poziom liczy zapytania na minutę
    if wait > 0:
        time.sleep(wait)
    _LAST["at"] = time.time()
    try:
        code, data = http("POST", f"{API}/models/{name}:generateContent", key(ctx), body)
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: Gemini nie odpowiada ({type(e).__name__})")
        block(ctx, name, 300, f"{name}: brak odpowiedzi ({type(e).__name__}) — próbuję innym modelem")
        _count(ctx, ok=False, pause=15)
        return None
    if code == 429:
        err = (data or {}).get("error") or {}
        details = err.get("details") or []
        quota = " ".join(v.get("quotaId", "") for d in details for v in (d.get("violations") or []))
        if "PerDay" in quota or "per day" in str(err.get("message", "")).lower():
            block(ctx, name, _until_pacific_midnight(), f"{name}: wyczerpany dzienny limit darmowego poziomu — piszę innym modelem, ten wraca ok. 9:00")
            _count(ctx, ok=False, pause=5)
            return None
        delay = 0.0
        for d in details:
            m = re.match(r"([\d.]+)s", str(d.get("retryDelay", "")))
            if m:
                delay = float(m.group(1))
        with R.db(ctx) as c:
            streak = int(R.meta_get(c, "gemini_429", "0") or 0) + 1
            R.meta_set(c, "gemini_429", streak)
            R.meta_set(c, "gemini_powod", f"{name}: limit na minutę — chwila przerwy")
            c.commit()
        if streak >= 3:
            block(ctx, name, 900, f"{name}: ciągle limit — przez kwadrans piszę innym modelem")
        _count(ctx, ok=False, pause=min(300, max(delay + 2, 30 * streak)))
        return None
    if code in (400, 401, 403):
        _MODEL.update(at=0.0, names=[])                                # zły klucz albo zmiana modeli — lista od nowa
        with R.db(ctx) as c:
            R.meta_set(c, "gemini_powod", f"Google odrzuca zapytania (błąd {code}) — sprawdź klucz w Ustawieniach")
            c.commit()
        _count(ctx, ok=False, pause=900)
        return None
    if code == 404:
        block(ctx, name, 86400, f"{name}: model niedostępny — piszę innym")
        _count(ctx, ok=False)
        return None
    if code != 200:                                                     # 500/503: Google przeciążony — inny model, krótka przerwa
        block(ctx, name, 600, f"{name}: Google przeciążony (błąd {code}) — piszę innym modelem")
        _count(ctx, ok=False, pause=20)
        return None
    _count(ctx)
    _LAST["ok"] = time.time()
    with R.db(ctx) as c:
        if R.meta_get(c, "gemini_429") not in ("", "0"):
            R.meta_set(c, "gemini_429", 0)
        R.meta_set(c, "gemini_powod", "")
        c.commit()
    with contextlib.suppress(Exception):
        parts = data["candidates"][0]["content"]["parts"]
        raw = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        with contextlib.suppress(ValueError):
            return json.loads(raw)
        hit = re.search(r"\{.*\}", raw, re.S)
        if hit:
            return json.loads(hit.group(0))
    return None


def used_since(t0):
    """Czy od chwili t0 Gemini choć raz odpowiedziało (czyli tekst jest od Gemini, a nie z modelu lokalnego)."""
    return _LAST["ok"] >= t0


def status(ctx):
    """Krótki opis dla Ustawień."""
    if not key(ctx):
        return "Brak klucza — listy pisze model lokalny."
    with R.db(ctx) as c:
        used = int(R.meta_get(c, f"gemini_{ctx.now().date().isoformat()}", "0") or 0)
        pause = float(R.meta_get(c, "gemini_przerwa", "0") or 0)
        why = R.meta_get(c, "gemini_powod")
        blocked = blocks(c)
    name = _MODEL["name"] or "wybiorę przy pierwszym liście"
    extra = " · przerwa, w tym czasie pisze model lokalny" if pause > time.time() else ""
    extra += f" · {why}" if why else ""
    extra += f" · odpoczywają (limit dzienny albo przeciążenie): {', '.join(blocked)}" if blocked else ""
    return f"Model: {name} · dziś zapytań: {used}{extra}"
