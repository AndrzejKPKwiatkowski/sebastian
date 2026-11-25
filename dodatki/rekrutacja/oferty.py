"""Rekrutacja — oferta: pobranie strony ogłoszenia, wyciągnięcie danych, ocena dopasowania."""
import contextlib, html, html.parser, ipaddress, json, os, re, socket, threading, time
from urllib.parse import urlparse

from . import rdzen as R

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
JUNK = ("sentry", "wixpress", "example.", "noreply", "no-reply", "donotreply", "@2x", ".png", ".jpg", ".webp", ".svg", "u003e")
NOT_FOR_CV = ("iod", "rodo", "dpo", "abi", "gdpr", "privacy", "prywatnosc", "ochronadanych", "ochrona.danych", "daneosobowe",
              "dane.osobowe", "inspektor", "iodo", "reklamacje", "faktury", "ksiegowosc", "sklep", "zamowienia", "marketing", "media", "prasa")
GOOD = ("rekrut", "kariera", "praca", "hr", "cv", "jobs", "kadry", "biuro", "kontakt", "office", "sekretariat", "info")
SALES = ["sprzedaz", "sprzedawc", "handlow", "telemarket", "call center", "cold call", "pozyskiwanie klient", "pozyskiwania klient",
         "przedstawiciel", "akwizyc", "prowizj", "infolini", "doradca klienta", "target sprzeda", "plan sprzeda"]


class _Text(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form", "iframe"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.depth, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth:
            self.out.append(data)


def to_text(raw_html):
    p = _Text()
    try:
        p.feed(raw_html)
    except Exception:
        pass
    text = re.sub(r"[ \t\xa0]+", " ", "".join(p.out))
    return re.sub(r"\n\s*\n+", "\n", text).strip(), re.sub(r"\s+", " ", p.title).strip()


def safe_url(url):
    """Tylko publiczne adresy http(s) — panel nie może służyć do zaglądania w usługi na Macu ani w sieci domowej."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        for info in socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                return False
    except Exception:
        return False
    return True


BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.6"}


# 2.36.2: portale (pracuj.pl przez Cloudflare) blokują adres Maca, gdy linki otwierane są jeden za drugim.
# Otwieram je w odstępach jak człowiek, a po blokadzie robię przerwę — nie obchodzę blokad.
GAP = {"pracuj.pl": 30}
DEFAULT_GAP = 3
COOLDOWN = 45 * 60
_LAST, _COOL, _LOCK = {}, {}, threading.Lock()
PACE = not os.environ.get("SEBASTIAN_TESTY")
BLOCK_MARKS = ("you are being rate limited", "used cloudflare to restrict access", "attention required! | cloudflare", "just a moment...",
               "cf-chl-", "enable javascript and cookies to continue", "checking your browser before accessing")


def host(url):
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _gap(h):
    return next((v for k, v in GAP.items() if h == k or h.endswith("." + k)), DEFAULT_GAP)


def blocked_msg(h):
    return (f"{h} chwilowo nie pokazuje Sebastianowi ogłoszeń (za dużo otwarć z tego komputera). Spróbuję później sam — "
            f"albo otwórz ogłoszenie u siebie i kliknij zakładkę „Wyślij do Sebastiana”, albo wklej treść.")


def cooling(url):
    """Sekundy do końca przerwy po blokadzie (0 = można otwierać)."""
    return max(0, int(_COOL.get(host(url), 0) - time.time()))


def pace(url):
    h = host(url)
    if cooling(url):
        raise RuntimeError(blocked_msg(h))
    if not PACE:
        return
    with _LOCK:
        wait = _LAST.get(h, 0) + _gap(h) - time.time()
        if wait > 0:
            time.sleep(min(wait, _gap(h)))
        _LAST[h] = time.time()


def block_page(page, url, st=None):
    """Strona blokady albo pusta „skorupa” portalu zamiast ogłoszenia."""
    low = page[:30000].lower()
    if any(k in low for k in BLOCK_MARKS):
        return "blokada"
    if host(url).endswith("pracuj.pl") and ",oferta," in url and "jobposting" not in low and not (st or {}).get("firma"):
        return "pusta"
    return ""


def junk_text(a):
    """Treść zapisana wcześniej ze strony blokady (pracuj.pl bez danych ogłoszenia) — do pobrania jeszcze raz."""
    t, u = str(a.get("tresc") or ""), str(a.get("url") or "")
    if not t.strip():
        return False
    if any(k in t[:3000].lower() for k in BLOCK_MARKS):
        return True
    return host(u).endswith("pracuj.pl") and ",oferta," in u and not (a.get("firma") or "").strip() and not t.startswith("Stanowisko:") and len(t) < 6000


def _strip(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(t or "")))).strip()


def structured(page):
    """2.36: dane ogłoszenia zapisane w stronie dla wyszukiwarek (JSON-LD JobPosting, meta og:) — działa też na stronach,
    które treść pokazują dopiero skryptem. Zwraca {stanowisko, firma, miasto, wynagrodzenie, opis}."""
    out = {"stanowisko": "", "firma": "", "miasto": "", "wynagrodzenie": "", "opis": ""}
    for blob in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page)[:20]:
        with contextlib.suppress(Exception):
            data = json.loads(html.unescape(blob.strip()))
            items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
            for it in items:
                if not isinstance(it, dict) or "JobPosting" not in str(it.get("@type")):
                    continue
                out["stanowisko"] = out["stanowisko"] or _strip(it.get("title"))
                org = it.get("hiringOrganization") or {}
                out["firma"] = out["firma"] or _strip(org.get("name") if isinstance(org, dict) else org)
                locs = it.get("jobLocation") or []
                locs = locs if isinstance(locs, list) else [locs]
                for loc in locs:
                    addr = (loc or {}).get("address") or {} if isinstance(loc, dict) else {}
                    if isinstance(addr, dict) and addr.get("addressLocality"):
                        out["miasto"] = out["miasto"] or _strip(addr.get("addressLocality"))
                pay = it.get("baseSalary") or {}
                if isinstance(pay, dict):
                    v = pay.get("value") or {}
                    if isinstance(v, dict) and (v.get("minValue") or v.get("value")):
                        lo, hi = v.get("minValue") or v.get("value"), v.get("maxValue")
                        out["wynagrodzenie"] = f"{lo}{'–' + str(hi) if hi and hi != lo else ''} {pay.get('currency') or 'PLN'}" + \
                                               (f" / {str(v.get('unitText')).lower()}" if v.get("unitText") else "")
                desc = _strip(it.get("description"))
                for k in ("qualifications", "responsibilities", "jobBenefits"):
                    if it.get(k):
                        desc += "\n" + _strip(it.get(k) if isinstance(it.get(k), str) else " ".join(map(str, it.get(k))))
                out["opis"] = out["opis"] or desc
    def meta(name):
        m = re.search(r'(?is)<meta[^>]+(?:property|name)=["\']' + re.escape(name) + r'["\'][^>]*content=["\']([^"\']*)', page)
        return _strip(m.group(1)) if m else ""
    out["stanowisko"] = out["stanowisko"] or meta("og:title")
    if not out["opis"]:
        out["opis"] = meta("og:description") or meta("description")
    return out


def structured_text(st):
    lines = [f"{k}: {st[v]}" for k, v in (("Stanowisko", "stanowisko"), ("Pracodawca", "firma"), ("Miejsce pracy", "miasto"),
                                          ("Wynagrodzenie", "wynagrodzenie")) if st.get(v)]
    return ("\n".join(lines) + ("\n\n" + st["opis"] if st.get("opis") else "")).strip()


def fetch(url, deny=None):
    """(tekst, tytuł, [maile], [linki]) albo wyjątek RuntimeError z komunikatem po polsku."""
    import requests
    url = R.clean_url(url)
    if not safe_url(url):
        raise RuntimeError("Ten adres nie wygląda na publiczną stronę z ogłoszeniem.")
    if deny and deny(url):
        raise RuntimeError("Ten portal nie zgadza się na automaty.")
    pace(url)
    try:
        with requests.get(url, timeout=25, stream=True, allow_redirects=False, headers=BROWSER) as r:   # 2.36: jak zwykła przeglądarka
            hops = 0
            while r.is_redirect and hops < 5:
                nxt = requests.compat.urljoin(r.url, r.headers.get("Location", ""))
                if not safe_url(nxt) or (deny and deny(nxt)):
                    raise RuntimeError("Strona przekierowuje pod adres, którego nie otwieram.")
                r = requests.get(nxt, timeout=25, stream=True, allow_redirects=False, headers=r.request.headers)
                hops += 1
            if r.status_code == 429 or (r.status_code == 403 and "cloudflare" in str(r.headers.get("Server", "")).lower()):
                _COOL[host(url)] = time.time() + COOLDOWN
                raise RuntimeError(blocked_msg(host(url)))
            if r.status_code >= 400:
                hint = {403: " (portal blokuje otwieranie spoza przeglądarki)", 404: " (ogłoszenie zniknęło albo link jest niepełny)",
                        410: " (ogłoszenie wygasło)", 429: " (za dużo zapytań — spróbuję później)"}.get(r.status_code, "")
                raise RuntimeError(f"Strona odpowiedziała błędem {r.status_code}{hint}. Wklej treść ogłoszenia ręcznie.")
            raw = r.raw.read(2_500_000, decode_content=True)
            enc = r.encoding or "utf-8"
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Nie udało się otworzyć strony ({type(e).__name__}). Wklej treść ogłoszenia ręcznie.")
    page = raw.decode(enc, "replace")
    text, title = to_text(page)
    st = structured(page)                                                # 2.36: dane dla wyszukiwarek — firma, stanowisko, opis
    kind = block_page(page, url, st)
    if kind == "blokada":
        _COOL[host(url)] = time.time() + COOLDOWN
        raise RuntimeError(blocked_msg(host(url)))
    if kind == "pusta":
        raise RuntimeError(f"{host(url)} pokazał Sebastianowi pustą stronę zamiast ogłoszenia. Otwórz je u siebie i kliknij „Wyślij do Sebastiana” "
                           f"albo wklej treść — spróbuję też jeszcze raz później.")
    head = structured_text(st)
    if head and (st["firma"] or st["opis"]):
        text = head + ("\n\n" + text if len(text) >= 200 and st["opis"][:80] not in text else "")
    if len(text) < 200:
        raise RuntimeError("Strona nie pokazała treści ogłoszenia (pewnie wymaga przeglądarki). Wklej treść ręcznie.")
    links = [html.unescape(h) for h in re.findall(r'href=["\'](https?://[^"\'#]+)["\']', page, re.I)][:300]
    return text[:20000], title[:200], emails(html.unescape(page)), links


def emails(text):
    found = []
    for m in EMAIL_RE.findall(text or ""):
        m = m.strip(".").lower()
        local = m.split("@")[0]
        if m not in found and not any(j in m for j in JUNK) and not any(local == b or local.startswith(b + ".") or local.startswith(b + "-")
                                                                       or local.startswith(b + "_") for b in NOT_FOR_CV):
            found.append(m)
    return sorted(found, key=lambda m: (not any(g in m.split("@")[0] for g in GOOD), found.index(m)))[:8]


def sales_hits(text):
    low = R.plain(text)
    return sum(low.count(w) for w in SALES)


SALARY_RE = re.compile(r"(\d{1,2}[ .\u00a0]?\d{3}(?:[,.]\d{2})?\s*(?:-|–|—|do)\s*\d{1,2}[ .\u00a0]?\d{3}(?:[,.]\d{2})?|\b(?:od|do)\s+\d{1,2}[ .\u00a0]?\d{3}"
                       r"|\b\d{2,3}(?:[,.]\d{1,2})?\s*(?:-|–|—)\s*\d{2,3}(?:[,.]\d{1,2})?(?=\s*(?:zł|zl|pln)\s*/\s*(?:h|godz))"
                       r"|\b\d{2,3}(?:[,.]\d{1,2})?(?=\s*(?:zł|zl|pln)\s*/\s*(?:h|godz))|\b\d{1,2}[ .\u00a0]?\d{3}(?:[,.]\d{2})?(?=\s*(?:zł|zl|pln)\s*(?:brutto|netto)))"
                       r"\s*(?:zł|zl|pln)(?:\s*(?:brutto|netto|/\s*(?:mies\w*|mc|msc|h|godz\w*)))*", re.I)


def salary(text):
    """Widełki z treści ogłoszenia (bez modelu)."""
    m = SALARY_RE.search(text or "")
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


def uop_net(brutto):
    """Na rękę z umowy o pracę, 2026: ZUS 13,71%, zdrowotna 9%, KUP 250 zł, PIT 12% (32% powyżej 120 000 zł rocznie),
    PIT-2 (300 zł), bez ulgi dla młodych, bez statusu studenta, bez PPK. Np. 7000 zł brutto → 5101,67 zł."""
    b = float(brutto)
    social = round(b * 0.0976, 2) + round(b * 0.015, 2) + round(b * 0.0245, 2)
    health = round((b - social) * 0.09, 2)
    base = round(b - social - 250)
    over = max(0, base - 10000)                                       # ok. 120 000 zł rocznie
    tax = max(0, round((base - over) * 0.12 + over * 0.32 - 300))
    return round(b - social - health - tax, 2)


def contract(text):
    """Rodzaj umowy z ogłoszenia: uop | zlecenie | b2b | pusty (nie wiadomo)."""
    t = R.plain(text or "")
    if re.search(r"umow\w* o prace|\buop\b|etat\b|zatrudnienie na podstawie umowy o prace", t):
        return "uop"
    if re.search(r"\bb2b\b|kontrakt|faktur|dzialalnosc gospodarcz", t):
        return "b2b"
    if re.search(r"zleceni", t):
        return "zlecenie"
    return ""


def _amounts(t):
    nums = []
    for m in re.findall(r"\d[\d .]*(?:,\d{1,2})?", t):
        raw = m.strip().rstrip(".")
        whole = raw.split(",")[0].replace(" ", "")
        whole = whole.replace(".", "") if re.fullmatch(r"\d{1,3}(\.\d{3})+", whole) else whole.split(".")[0]
        with contextlib.suppress(ValueError):
            nums.append(float(whole))
    return nums


def pay_info(pay, text=""):
    """Wynagrodzenie miesięcznie: {od, do (kwoty z ogłoszenia, miesięcznie), netto_od, netto_do (na rękę), umowa, podane_netto}
    albo None. Brutto liczone jak umowa o pracę (zlecenie — tak samo, w przybliżeniu); przy B2B kwota „na fakturę” bez przeliczania."""
    t = R.plain(pay or "").replace("\xa0", " ")
    nums = _amounts(t)
    if not nums:
        return None
    hourly = bool(re.search(r"/\s*h\b|godz|hour|za godzine", t))
    nums = [x * 168 for x in nums] if hourly else [x for x in nums if x >= 1000]
    if not nums:
        return None
    lo, hi = min(nums), max(nums)
    kind = contract(pay) or contract(text)
    given_net = "netto" in t or "na reke" in t
    if kind == "b2b" or given_net:
        n_lo, n_hi = lo, hi
    else:
        n_lo, n_hi = uop_net(lo), uop_net(hi)
    return {"od": round(lo), "do": round(hi), "netto_od": round(n_lo), "netto_do": round(n_hi), "umowa": kind,
            "podane_netto": given_net, "godzinowo": hourly}


def netto_max(pay, text=""):
    """Górna kwota na rękę miesięcznie (zł) albo None."""
    p = pay_info(pay, text)
    return p["netto_do"] if p else None


def netto_text(pay, text=""):
    """Dopisek do wynagrodzenia w panelu, np. „na rękę ok. 4 401–5 102 zł (umowa o pracę: bez ulg, z PIT-2)”."""
    p = pay_info(pay, text)
    if not p:
        return ""
    fmt = lambda x: f"{x:,.0f}".replace(",", " ")
    rng = fmt(p["netto_do"]) if p["netto_od"] == p["netto_do"] else f"{fmt(p['netto_od'])}–{fmt(p['netto_do'])}"
    if p["umowa"] == "b2b":
        return f"B2B: {rng} zł na fakturę — na rękę zależy od Twojej działalności (ZUS, podatek)"
    if p["podane_netto"]:
        return f"to już kwota na rękę{' (z ' + fmt(p['od']) + ' zł/mies. przy stawce godzinowej)' if p['godzinowo'] else ''}"
    how = {"uop": "umowa o pracę", "zlecenie": "umowa zlecenie — w przybliżeniu"}.get(p["umowa"], "liczone jak umowa o pracę")
    return f"na rękę ok. {rng} zł miesięcznie ({how}; bez ulg, z PIT-2, bez PPK)"


SECTION_HEADS = {
    "wymagania": r"wymagania|wymagamy|oczekujemy|czego oczekujemy|nasze oczekiwania|kogo szukamy|twoje kwalifikacje|twój profil|"
                 r"tw[oó]j profil|mile widziane|requirements|our requirements|kwalifikacje",
    "obowiazki": r"obowiązki|obowiazki|zakres obowiązków|zakres zadań|twoje zadania|zadania|czym będziesz się zajmować|"
                 r"co będziesz robić|twój zakres|responsibilities|your responsibilities",
    "oferujemy": r"oferujemy|co oferujemy|co zyskujesz|benefity|to oferujemy|we offer|what we offer|zapewniamy",
}
OTHER_HEADS = r"o firmie|o nas|informacje|klauzula|aplikuj|jak aplikować|kontakt|o pracodawcy|lokalizacja|wynagrodzenie|rodo|about us"


def sections(text):
    """Wymagania / obowiązki / oferujemy wycięte z ogłoszenia po nagłówkach — gdy model nie odpowie albo utnie odpowiedź."""
    out = {k: [] for k in SECTION_HEADS}
    cur = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if END.match(line):
            break
        head = re.sub(r"[:\s]+$", "", line)
        if len(head) <= 60 and not re.search(r"[.;]\s*\w", head):
            hit = next((k for k, rx in SECTION_HEADS.items() if re.fullmatch(rf"(?i)\W*({rx})\W*", head)), None)
            if hit:
                cur = hit
                continue
            if re.fullmatch(rf"(?i)\W*({OTHER_HEADS})\W*", head):
                cur = None
                continue
        if cur and len(out[cur]) < 14:
            item = re.sub(r"^[\s•·\-–—*▪●◦✓✔>]+", "", line).strip()
            if 3 <= len(item):
                out[cur].append(item[:220])
    return out


NOISE = re.compile(r"(?i)^(aplikuj( teraz)?|zapisz|zapisz ofertę|udostępnij|drukuj|zgłoś|zgłoś ofertę|zaloguj( się)?|zarejestruj( się)?|"
                   r"menu|szukaj|wróć|pokaż (więcej|mniej)|rozwiń|zwiń|cookies?|akceptuj.*|ustawienia cookies|polityka prywatności|"
                   r"regulamin|pracodawcy|dla firm|moje konto|powiadomienia|ok|tak|nie|x|×|[\W_]{1,3}|\d{1,2})$")
END = re.compile(r"(?i)^(podobne oferty|inne oferty( tego pracodawcy)?|zobacz (też|również|podobne)|polecane oferty|"
                 r"oferty dla ciebie|najnowsze oferty|©|copyright|pracuj\.pl\s*\d{4}|newsletter)")
ICONS = {"obowiazki": "📋", "wymagania": "✔️", "oferujemy": "🎁", "inne": "▪️"}


def pretty(text, title=""):
    """Ogłoszenie jak na portalu: [{"typ": "naglowek"|"lista"|"akapit", ...}] — nagłówki sekcji, punkty i akapity, bez menu strony."""
    lines = [re.sub(r"\s+", " ", x).strip() for x in (text or "").splitlines()]
    lines = [x for x in lines if x and not NOISE.match(x)]
    heads = [i for i, x in enumerate(lines) if len(x) <= 70 and re.fullmatch(
        rf"(?i)\W*(?:(?:twój|twoje|twoja|nasze|nasz|nasza|co|czego)\s+)?({'|'.join(SECTION_HEADS.values())}|{OTHER_HEADS})(?:\s+\w+){{0,2}}\W*:?", x)]
    start = 0
    if title:                                                          # od tytułu stanowiska, gdy jest przed pierwszą sekcją
        t = R.plain(title)[:40]
        hit = next((i for i, x in enumerate(lines) if t and R.plain(x).startswith(t)), None)
        if hit is not None and (not heads or hit < heads[0]):
            start = hit
    if not start and heads and heads[0] > 25:
        start = max(0, heads[0] - 12)
    out, cur, listy = [], None, False
    for x in lines[start:]:
        if END.match(x):
            break
        head = re.sub(r"[:\s]+$", "", x)
        pre = r"\W*(?:(?:twój|twoje|twoja|nasze|nasz|nasza|co|czego|your|our)\s+)?"
        kind = next((k for k, rx in SECTION_HEADS.items() if re.fullmatch(rf"(?i){pre}({rx})(?:\s+\w+){{0,2}}\W*", head)), None)
        is_head = len(head) <= 70 and (kind or re.fullmatch(rf"(?i){pre}({OTHER_HEADS})\W*", head) or
                                       (x.endswith(":") and len(head) <= 50 and not re.search(r"[.!?]", head)))
        if is_head:
            out.append({"typ": "naglowek", "tekst": head.strip(" •-–"), "ikona": ICONS.get(kind or "inne")})
            cur, listy = None, bool(kind)
            continue
        bullet = bool(re.match(r"^[•·\-–—*▪●◦✓✔>]\s*", x))
        item = re.sub(r"^[•·\-–—*▪●◦✓✔>]+\s*", "", x)
        if bullet or (listy and len(item) <= 220):
            if cur is None:
                cur = {"typ": "lista", "punkty": []}
                out.append(cur)
            cur["punkty"].append(item)
        else:
            cur = None
            if out and out[-1]["typ"] == "akapit" and len(out[-1]["tekst"]) < 600 and not re.search(r"[.!?]$", out[-1]["tekst"]):
                out[-1]["tekst"] += " " + item
            else:
                out.append({"typ": "akapit", "tekst": item})
    return out[:120]


def analyze(ctx, f, text, title="", url=""):
    """Dane oferty i ocena dopasowania. Bez modelu zwraca to, co da się ustalić regułami."""
    out = {"firma": "", "stanowisko": "", "miasto": "", "email": "", "ocena": None, "uzasadnienie": "", "rodo": "", "ostrzezenia": [],
           "social_media": False, "niedziele_wieczory": False, "tylko_prowizja": False,
           "adres": "", "wynagrodzenie": salary(text), "wymagania": [], "obowiazki": [], "oferujemy": [], "po_angielsku": False}
    no_sales = any(x in R.SALES_AVOID for x in f["kryteria"].get("nie_chce", []))
    if no_sales and sales_hits(text) >= 3:
        out["ostrzezenia"].append("W ogłoszeniu często pojawia się sprzedaż albo obsługa klienta — sprawdź zakres obowiązków.")
    crit = f["kryteria"]
    w = f["warunki"]
    learned = ""
    with contextlib.suppress(Exception):
        from . import preferencje as PF
        with R.db(ctx) as c:
            learned = PF.prompt_part(c)
    prompt = f"""Przeczytaj ogłoszenie o pracę i wypełnij JSON. Niczego nie zgaduj — gdy czegoś nie ma, zostaw pusty tekst.

Kandydatka SZUKA pracy w obszarach: {'; '.join(crit.get('chce', []))}.
NIE CHCE pracy, w której znaczną część stanowi: {'; '.join(crit.get('nie_chce', []))}.
Jej warunki (tylko do oceny, NIE przepisuj ich do pól oferty): {w.get('umowa', '')}, {w.get('etat', '')}, praca w promieniu {w.get('dojazd_km', 50)} km od Krakowa lub zdalna.
Krótko o niej: {' '.join(p['tekst'] for p in f['profil'][:3])}
{learned}

TYTUŁ STRONY: {title}
OGŁOSZENIE:
{text[:6000]}

JSON:
{{"firma": "nazwa pracodawcy", "stanowisko": "nazwa stanowiska bez dopisków typu (K/M)", "miasto": "miejsce pracy z OGŁOSZENIA (miasto albo „zdalnie”), pusty tekst, gdy ogłoszenie go nie podaje",
  "email": "adres do wysłania aplikacji, jeśli jest w treści",
  "rodo": "dokładna treść klauzuli ZGODY do wpisania w CV (zaczyna się zwykle od „Wyrażam zgodę na przetwarzanie…”), jeśli pracodawca ją podał; NIE informacja o przetwarzaniu danych ani o administratorze",
  "sprzedaz": true/false (czy znaczną część pracy stanowi sprzedaż, pozyskiwanie klientów albo stała obsługa klienta),
  "social_media": true/false (czy główną częścią pracy jest prowadzenie mediów społecznościowych lub tworzenie treści na nie),
  "niedziele_wieczory": true/false (czy ogłoszenie wymaga regularnej pracy w niedziele albo wieczorami/nocą),
  "tylko_prowizja": true/false (czy wynagrodzenie jest wyłącznie prowizyjne, bez stałej podstawy),
  "po_angielsku": true/false (czy ogłoszenie jest napisane po angielsku albo wymaga biegłego angielskiego w pracy lub rekrutacji),
  "adres": "adres miejsca pracy (ulica, miasto), jeśli podany",
  "wynagrodzenie": "widełki lub kwota wynagrodzenia dokładnie jak w ogłoszeniu (np. „6500–7500 zł brutto”), pusty tekst, gdy nie podano",
  "wymagania": ["punkty: czego pracodawca wymaga — PRZEPISANE DOSŁOWNIE z ogłoszenia, bez zmieniania słów"],
  "obowiazki": ["punkty: co będzie się robić na tym stanowisku — PRZEPISANE DOSŁOWNIE z ogłoszenia"],
  "oferujemy": ["krótkie punkty: co oferuje pracodawca (umowa, etat, benefity)"],
  "ocena": liczba 0-100 (jak dobrze RODZAJ pracy, zadania i warunki pasują do tego, czego kandydatka SZUKA i czego NIE CHCE;
     nie oceniaj tu wymagań — spełnienie wymagań liczę osobno),
  "uzasadnienie": "1–2 krótkie zdania po polsku do Agi, w drugiej osobie (np. „Pasuje do Ciebie, bo… Uważaj na…”)"}}"""
    got = None
    try:
        got = ctx.ask(prompt, as_json=True, max_tokens=2400, temperature=0.1)
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: analiza oferty bez modelu ({type(e).__name__})")
    lists_empty = not isinstance(got, dict) or not (got.get("wymagania") or got.get("obowiazki"))
    if lists_empty and len(text) > 600:                                  # ucięta albo pusta odpowiedź — jeszcze raz przez Gemini
        with contextlib.suppress(Exception):
            from . import gemini as GM
            if GM.available(ctx):
                g2 = GM.ask_json(ctx, prompt, max_tokens=2400, temperature=0.1)
                if isinstance(g2, dict) and (g2.get("wymagania") or g2.get("obowiazki")):
                    got = g2 if not isinstance(got, dict) else dict(got, **{k: g2.get(k) for k in ("wymagania", "obowiazki", "oferujemy")})
    if isinstance(got, dict):
        for k in ("firma", "stanowisko", "miasto", "uzasadnienie", "rodo"):
            out[k] = re.sub(r"\s+", " ", str(got.get(k) or "")).strip()[:{"rodo": 1200, "uzasadnienie": 700}.get(k, 200)]
        if len(out["uzasadnienie"]) >= 700:                            # bez ucinania w pół słowa
            out["uzasadnienie"] = out["uzasadnienie"][:out["uzasadnienie"].rfind(".") + 1] or out["uzasadnienie"]
        for k in ("miasto", "stanowisko", "firma"):                     # model nie przepisuje warunków kandydatki jako danych oferty
            if re.search(r"(?i)\bdo \d+ ?km\b|albo zdalnie|kandydat", out[k]):
                out[k] = ""
        m = EMAIL_RE.search(str(got.get("email") or ""))
        if m and m.group(0).lower() in text.lower() and emails(m.group(0)):    # w ogłoszeniu i nie adres IOD/RODO itp.
            out["email"] = m.group(0).lower()
        try:
            out["ocena"] = max(0, min(100, int(float(got.get("ocena")))))
        except (TypeError, ValueError):
            pass
        out["adres"] = re.sub(r"\s+", " ", str(got.get("adres") or "")).strip()[:200]
        pay = re.sub(r"\s+", " ", str(got.get("wynagrodzenie") or "")).strip()[:160]
        if pay and re.search(r"\d", pay) and re.sub(r"\D", "", pay)[:3] in re.sub(r"\D", "", text):
            out["wynagrodzenie"] = pay                                 # kwota musi być w ogłoszeniu
        for k in ("wymagania", "obowiazki", "oferujemy"):
            items = got.get(k) if isinstance(got.get(k), list) else []
            out[k] = [re.sub(r"\s+", " ", str(x)).strip(" •-–")[:220] for x in items if str(x).strip()][:14]
        out["social_media"] = got.get("social_media") is True
        out["niedziele_wieczory"] = got.get("niedziele_wieczory") is True
        out["tylko_prowizja"] = got.get("tylko_prowizja") is True
        out["po_angielsku"] = got.get("po_angielsku") is True
        if no_sales and got.get("sprzedaz") is True and not out["ostrzezenia"]:
            out["ostrzezenia"].append("Model ocenia, że znaczną część tej pracy stanowi sprzedaż albo obsługa klienta.")
        if out["rodo"] and (not R.is_consent(out["rodo"]) or R.plain(out["rodo"])[:40] not in R.plain(text)):
            out["rodo"] = ""                                         # tylko prawdziwa klauzula zgody, zacytowana z ogłoszenia
    cut = sections(text)                                               # zawsze coś pokazać: punkty wprost z ogłoszenia
    for k in ("wymagania", "obowiazki", "oferujemy"):
        if not out[k] and cut[k]:
            out[k] = cut[k]
    for k, label in (("firma", "Pracodawca"), ("stanowisko", "Stanowisko"), ("miasto", "Miejsce pracy")):   # 2.36: z danych strony
        m = re.search(rf"(?m)^{label}: (.+)$", text[:3000])
        if m and not out[k]:
            out[k] = m.group(1).strip()[:200]
    if not out["stanowisko"] and title:
        out["stanowisko"] = re.split(r"\s[|\-–—]\s", title)[0][:120]
    if not out["firma"] and title:                                       # „Stanowisko – Firma – Miasto – Portal”
        parts = [x.strip() for x in re.split(r"\s[|\-–—]\s", title) if x.strip()]
        portal = ("pracuj", "olx", "indeed", "linkedin", "praca", "gowork", "nofluff", "justjoin", "theprotocol", "aplikuj", "infopraca", "jooble")
        cities = set(R.AREA_KM) | {"warszawa", "wroclaw", "poznan", "gdansk", "lodz", "katowice", "lublin", "szczecin", "zdalnie", "hybryd", "oferta pracy", "praca"}
        rest = [x for x in parts[1:] if not any(p_ in R.plain(x) for p_ in portal) and not any(c in R.plain(x) for c in cities) and len(x) > 2]
        if rest:
            out["firma"] = rest[0][:200]
    return out
