"""Rekrutacja — oferta: pobranie strony ogłoszenia, wyciągnięcie danych, ocena dopasowania."""
import html, html.parser, ipaddress, re, socket
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


def fetch(url, deny=None):
    """(tekst, tytuł, [maile], [linki]) albo wyjątek RuntimeError z komunikatem po polsku."""
    import requests
    if not safe_url(url):
        raise RuntimeError("Ten adres nie wygląda na publiczną stronę z ogłoszeniem.")
    if deny and deny(url):
        raise RuntimeError("Ten portal nie zgadza się na automaty.")
    try:
        with requests.get(url, timeout=25, stream=True, allow_redirects=False,
                          headers={"User-Agent": "Mozilla/5.0 (Macintosh) Sebastian-Rekrutacja", "Accept-Language": "pl,en;q=0.7"}) as r:
            hops = 0
            while r.is_redirect and hops < 5:
                nxt = requests.compat.urljoin(r.url, r.headers.get("Location", ""))
                if not safe_url(nxt) or (deny and deny(nxt)):
                    raise RuntimeError("Strona przekierowuje pod adres, którego nie otwieram.")
                r = requests.get(nxt, timeout=25, stream=True, allow_redirects=False, headers=r.request.headers)
                hops += 1
            if r.status_code >= 400:
                raise RuntimeError(f"Strona odpowiedziała błędem {r.status_code}. Wklej treść ogłoszenia ręcznie.")
            raw = r.raw.read(2_500_000, decode_content=True)
            enc = r.encoding or "utf-8"
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Nie udało się otworzyć strony ({type(e).__name__}). Wklej treść ogłoszenia ręcznie.")
    page = raw.decode(enc, "replace")
    text, title = to_text(page)
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


SALARY_RE = re.compile(r"(\d{1,2}[ .\u00a0]?\d{3}(?:[,.]\d{2})?\s*(?:-|–|—|do)\s*\d{1,2}[ .\u00a0]?\d{3}(?:[,.]\d{2})?|\b(?:od|do)\s+\d{1,2}[ .\u00a0]?\d{3})"
                       r"\s*(?:zł|zl|pln)(?:\s*(?:brutto|netto|/\s*(?:mies\w*|mc|msc|h|godz\w*)))*", re.I)


def salary(text):
    """Widełki z treści ogłoszenia (bez modelu)."""
    m = SALARY_RE.search(text or "")
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


def analyze(ctx, f, text, title="", url=""):
    """Dane oferty i ocena dopasowania. Bez modelu zwraca to, co da się ustalić regułami."""
    out = {"firma": "", "stanowisko": "", "miasto": "", "email": "", "ocena": None, "uzasadnienie": "", "rodo": "", "ostrzezenia": [],
           "social_media": False, "niedziele_wieczory": False, "tylko_prowizja": False,
           "adres": "", "wynagrodzenie": salary(text), "wymagania": [], "obowiazki": [], "oferujemy": []}
    no_sales = any(x in R.SALES_AVOID for x in f["kryteria"].get("nie_chce", []))
    if no_sales and sales_hits(text) >= 3:
        out["ostrzezenia"].append("W ogłoszeniu często pojawia się sprzedaż albo obsługa klienta — sprawdź zakres obowiązków.")
    crit = f["kryteria"]
    w = f["warunki"]
    prompt = f"""Przeczytaj ogłoszenie o pracę i wypełnij JSON. Niczego nie zgaduj — gdy czegoś nie ma, zostaw pusty tekst.

Kandydatka SZUKA pracy w obszarach: {'; '.join(crit.get('chce', []))}.
NIE CHCE pracy, w której znaczną część stanowi: {'; '.join(crit.get('nie_chce', []))}.
Warunki: {w.get('umowa', '')}, {w.get('etat', '')}, Kraków i do {w.get('dojazd_km', 50)} km albo zdalnie.
Krótko o niej: {' '.join(p['tekst'] for p in f['profil'][:3])}

TYTUŁ STRONY: {title}
OGŁOSZENIE:
{text[:6000]}

JSON:
{{"firma": "nazwa pracodawcy", "stanowisko": "nazwa stanowiska bez dopisków typu (K/M)", "miasto": "miejsce pracy albo zdalnie",
  "email": "adres do wysłania aplikacji, jeśli jest w treści",
  "rodo": "dokładna treść klauzuli ZGODY do wpisania w CV (zaczyna się zwykle od „Wyrażam zgodę na przetwarzanie…”), jeśli pracodawca ją podał; NIE informacja o przetwarzaniu danych ani o administratorze",
  "sprzedaz": true/false (czy znaczną część pracy stanowi sprzedaż, pozyskiwanie klientów albo stała obsługa klienta),
  "social_media": true/false (czy główną częścią pracy jest prowadzenie mediów społecznościowych lub tworzenie treści na nie),
  "niedziele_wieczory": true/false (czy ogłoszenie wymaga regularnej pracy w niedziele albo wieczorami/nocą),
  "tylko_prowizja": true/false (czy wynagrodzenie jest wyłącznie prowizyjne, bez stałej podstawy),
  "adres": "adres miejsca pracy (ulica, miasto), jeśli podany",
  "wynagrodzenie": "widełki lub kwota wynagrodzenia dokładnie jak w ogłoszeniu (np. „6500–7500 zł brutto”), pusty tekst, gdy nie podano",
  "wymagania": ["krótkie punkty: czego pracodawca wymaga, tak jak w ogłoszeniu"],
  "obowiazki": ["krótkie punkty: co będzie się robić na tym stanowisku"],
  "oferujemy": ["krótkie punkty: co oferuje pracodawca (umowa, etat, benefity)"],
  "ocena": liczba 0-100 (jak dobrze oferta pasuje do tego, czego kandydatka szuka i co umie),
  "uzasadnienie": "jedno zdanie po polsku"}}"""
    got = None
    try:
        got = ctx.ask(prompt, as_json=True, max_tokens=1100, temperature=0.1)
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: analiza oferty bez modelu ({type(e).__name__})")
    if isinstance(got, dict):
        for k in ("firma", "stanowisko", "miasto", "uzasadnienie", "rodo"):
            out[k] = re.sub(r"\s+", " ", str(got.get(k) or "")).strip()[:1200 if k == "rodo" else 200]
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
        if no_sales and got.get("sprzedaz") is True and not out["ostrzezenia"]:
            out["ostrzezenia"].append("Model ocenia, że znaczną część tej pracy stanowi sprzedaż albo obsługa klienta.")
        if out["rodo"] and (not R.is_consent(out["rodo"]) or R.plain(out["rodo"])[:40] not in R.plain(text)):
            out["rodo"] = ""                                         # tylko prawdziwa klauzula zgody, zacytowana z ogłoszenia
    if not out["stanowisko"] and title:
        out["stanowisko"] = re.split(r"\s[|\-–—]\s", title)[0][:120]
    return out
