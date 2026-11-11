"""Rekrutacja — szukanie adresu e-mail firmy, gdy ogłoszenie go nie podaje (2.8.1).

Kolejność: (1) strona firmy z ogłoszenia (link do domeny firmy), (2) wyszukiwarka Brave Search, jeśli jest klucz,
(3) próba typowych domen z nazwy firmy (firma.pl, firma.com.pl, firma.com). Strona musi wyglądać na stronę tej firmy
(nazwa firmy na stronie), a adres musi być w domenie tej strony. Adresy IOD/RODO i podobne są pomijane.
"""
import contextlib, html, json, re
from urllib.parse import quote, urljoin, urlparse

from . import oferty as O, rdzen as R, zrodla as Z

PORTALS = Z.NO_AUTOMATION + ("adzuna", "jooble", "careerjet", "rocketjobs.pl", "theprotocol.it", "infopraca.pl", "aplikuj.pl", "talent.com",
                             "recruitee.com", "teamtailor.com", "erecruiter.pl", "traffit.com", "elevato.net", "workable.com", "greenhouse.io",
                             "lever.co", "smartrecruiters.com", "bip.", "gov.pl", "google.", "facebook.", "youtube.", "wikipedia.", "panoramafirm",
                             "aleo.com", "rejestr.io", "krs-online", "owg.pl", "biznes.gov", "pkt.pl", "cylex", "yelp", "gowork", "oferteo")
PAGES = ("kontakt", "kariera", "praca", "rekrutacja", "o-nas", "o_nas", "about", "contact", "careers", "dolacz", "jobs", "zespol")
GOOD = ("rekrutacja", "rekrutacje", "kariera", "praca", "hr", "cv", "kadry", "jobs", "career", "careers", "recruitment")
OK = ("biuro", "sekretariat", "office", "kontakt", "info", "hello", "firma", "recepcja", "administracja")


def _host(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _portal(url):
    h = _host(url)
    return not h or any(p in h for p in PORTALS)


GENERIC = {"biuro", "firma", "grupa", "polska", "poland", "group", "spolka", "centrum", "studio", "uslugi", "uslug", "the", "and", "rachunkowe",
           "rachunkowa", "kancelaria", "adwokacka", "prawna", "radcy", "prawnego", "handlowe", "handlowa", "consulting", "serwis",
           "przedsiebiorstwo", "zaklad", "sklep", "hurtownia", "agencja", "fundacja", "stowarzyszenie", "krakow", "krakowska", "krakowskie",
           "medyczne", "medyczny", "gabinet", "centrum", "system", "systems", "solutions", "services", "international", "spzoo", "oddzial"}


def _name_tokens(firma):
    """Wyróżniające słowa nazwy firmy (bez form prawnych i słów ogólnych)."""
    return [w for w in R.norm(firma).split() if len(w) >= 3 and w not in GENERIC][:3]


def _page_is_company(text, firma):
    """Strona jest stroną tej firmy, jeśli są na niej wszystkie wyróżniające słowa nazwy (przy 3 słowach — co najmniej 2)."""
    low = R.norm(text)
    toks = _name_tokens(firma)
    if not toks:
        return R.norm(firma) in low and len(R.norm(firma)) >= 6
    return sum(t in low for t in toks) >= (2 if len(toks) == 3 else len(toks))


def _fetch(url):
    page, final = Z._get(url, timeout=15, limit=1_500_000)
    return page, final


def site_emails(start_url, firma):
    """[(adres, strona)] ze strony firmy i jej podstron kontakt/kariera; tylko w domenie strony."""
    try:
        page, final = _fetch(start_url)
    except Exception:
        return []
    text, _ = O.to_text(page)
    if not _page_is_company(text + " " + final, firma):
        return []
    root = f"{urlparse(final).scheme}://{urlparse(final).netloc}/"
    dom = _host(final)
    pages, found = [(final, page)], []
    links = []
    for href in re.findall(r'href=["\']([^"\'#]+)["\']', page, re.I):
        u = urljoin(final, html.unescape(href))
        if _host(u) == dom and any(p in R.plain(u) for p in PAGES):
            links.append(u)
    for guess in ("kontakt", "kariera", "praca"):
        links.append(urljoin(root, guess))
    for u in list(dict.fromkeys(links))[:6]:
        with contextlib.suppress(Exception):
            p2, f2 = _fetch(u)
            if _host(f2) == dom:
                pages.append((f2, p2))
    for url, p in pages:
        for m in O.emails(html.unescape(p.replace("[at]", "@").replace("(at)", "@").replace(" [małpa] ", "@"))):
            d = m.rsplit("@", 1)[-1]
            if d == dom or d.endswith("." + dom) or dom.endswith("." + d):
                found.append((m, url))
    seen, out = set(), []
    for m, u in found:
        if m not in seen:
            seen.add(m)
            out.append((m, u))
    rank = lambda m: (0 if any(m.split("@")[0].startswith(g) for g in GOOD) else 1 if any(m.split("@")[0].startswith(o) for o in OK) else 2)
    return sorted(out, key=lambda x: rank(x[0]))


def brave(query, key, get=None):
    import requests
    get = get or requests.get
    r = get(f"https://api.search.brave.com/res/v1/web/search?q={quote(query)}&count=8&country=PL&search_lang=pl",
            headers={"Accept": "application/json", "X-Subscription-Token": key}, timeout=20)
    r.raise_for_status()
    return [x.get("url", "") for x in (r.json().get("web") or {}).get("results", [])]


def guesses(firma):
    toks = _name_tokens(firma)
    base = re.sub(r"[^a-z0-9]", "", "".join(toks))
    first = re.sub(r"[^a-z0-9]", "", toks[0]) if toks else ""
    out = []
    for b in dict.fromkeys(x for x in (base, first) if len(x) >= 5):
        out += [f"https://{b}.pl", f"https://www.{b}.pl", f"https://{b}.com.pl", f"https://{b}.com", f"https://{b}.eu"]
    return out


def find_email(ctx, app, offer_page_links=(), get=None):
    """{"email", "strona", "sposob"} albo {} — adres firmy znaleziony w sieci."""
    firma = (app.get("firma") or "").strip()
    if len(R.norm(firma)) < 3:
        return {}
    candidates = [(u, "ogloszenie") for u in offer_page_links if not _portal(u)]
    if app.get("url") and not _portal(app["url"]):
        candidates.insert(0, (f"{urlparse(app['url']).scheme}://{urlparse(app['url']).netloc}/", "ogloszenie"))
    key = R.secret(ctx, "brave")
    if key:
        with contextlib.suppress(Exception):
            city = "Kraków" if not app.get("miasto") else app["miasto"].split(",")[0]
            candidates += [(u, "wyszukiwarka") for u in brave(f"{firma} {city} kontakt", key, get=get) if not _portal(u)][:4]
    candidates += [(u, "domysl") for u in guesses(firma)]
    tried = set()
    for u, how in candidates:
        root = f"{urlparse(u).scheme}://{urlparse(u).netloc}/"
        if root in tried:
            continue
        tried.add(root)
        for start in dict.fromkeys((u, root)):
            got = site_emails(start, firma)
            if got:
                return {"email": got[0][0], "strona": got[0][1], "sposob": how}
        if len(tried) >= 8:
            break
    return {}


def offer_links(page_html, base):
    """Linki z ogłoszenia, które mogą prowadzić na stronę firmy (nie na portal)."""
    out = []
    for href in re.findall(r'href=["\'](https?://[^"\'#]+)["\']', page_html or "", re.I):
        u = html.unescape(href)
        if not _portal(u) and _host(u) != _host(base):
            out.append(u)
    return list(dict.fromkeys(out))[:5]
