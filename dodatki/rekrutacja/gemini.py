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
_MODEL = {"at": 0.0, "name": None, "key": ""}
_LAST = {"at": 0.0, "ok": 0.0}
PACE = 6.0                                                             # najwyżej ok. 10 zapytań na minutę


def key(ctx):
    return R.secret(ctx, "gemini") or ""


def _version(name):
    nums = re.findall(r"\d+(?:\.\d+)?", name.split("/")[-1])
    return float(nums[0]) if nums else 0.0


def pick_model(names, want=""):
    """Najlepszy model do pisania: wskazany w ustawieniach albo najnowszy „flash” (bez lite/image/tts/embedding/audio)."""
    names = [n.split("/")[-1] for n in names]
    if want:
        return want if want in names else None
    good = [n for n in names if "gemini" in n and "flash" in n and not re.search(r"lite|image|tts|embed|audio|live|thinking-exp|learnlm", n)]
    stable = [n for n in good if "preview" not in n and "exp" not in n]
    pool = stable or good
    return sorted(pool, key=lambda n: (_version(n), "latest" not in n, n), reverse=True)[0] if pool else None


def model(ctx, http=None):
    k = key(ctx)
    if not k:
        return None
    if _MODEL["name"] and _MODEL["key"] == k and time.time() - _MODEL["at"] < 6 * 3600:
        return _MODEL["name"]
    http = http or _http
    code, data = http("GET", f"{API}/models?pageSize=200", k, None)
    if code != 200:
        return None
    names = [m["name"] for m in data.get("models", []) if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    name = pick_model(names, str(ctx.settings().get("gemini_model") or "").strip())
    _MODEL.update(at=time.time(), name=name, key=k)
    return name


def _http(method, url, k, body):
    import requests
    r = requests.request(method, url, headers={"x-goog-api-key": k, "Content-Type": "application/json"},
                         data=json.dumps(body) if body is not None else None, timeout=120)
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
        _count(ctx, ok=False, pause=600)
        return None
    if code == 429:                                                    # limit: przerwa rośnie 1 → 2 → 4 … min (najwyżej godzina)
        with R.db(ctx) as c:
            streak = int(R.meta_get(c, "gemini_429", "0") or 0) + 1
            R.meta_set(c, "gemini_429", streak)
            c.commit()
        _count(ctx, ok=False, pause=min(3600, 60 * 2 ** (streak - 1)))
        return None
    if code in (400, 401, 403, 404):
        _MODEL.update(at=0.0, name=None)                               # zły klucz albo model wycofany — wybierz od nowa
        _count(ctx, ok=False, pause=900)
        return None
    if code != 200:
        _count(ctx, ok=False, pause=600)
        return None
    _count(ctx)
    _LAST["ok"] = time.time()
    with R.db(ctx) as c:
        if R.meta_get(c, "gemini_429"):
            R.meta_set(c, "gemini_429", 0)
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
    name = _MODEL["name"] or "wybiorę przy pierwszym liście"
    extra = " · przerwa (limit albo błąd), w tym czasie pisze model lokalny" if pause > time.time() else ""
    return f"Model: {name} · dziś zapytań: {used}{extra}"
