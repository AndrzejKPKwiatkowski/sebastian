"""Rekrutacja — źródła ofert (część B): strony z ogłoszeniami, kanały RSS, tablice Recruitee, lista firm.

Sebastian sam przegląda tylko źródła, które to dopuszczają: strony z listą ogłoszeń (urzędy, uczelnie, strony karier firm),
kanały RSS/Atom i publiczne tablice Recruitee. Duże portale, których regulamin zabrania automatów (Pracuj.pl, OLX, LinkedIn,
Indeed), nie są przeglądane automatycznie — oferty z nich Aga wkleja linkiem, a Sebastian otwiera wtedy jedną stronę,
tak jak przeglądarka.
"""
import contextlib, html, json, re, time
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

from . import oferty as O, rdzen as R

NO_AUTOMATION = ("pracuj.pl", "olx.pl", "linkedin.com", "indeed.com", "indeed.pl", "glassdoor", "gowork.pl", "jooble", "praca.pl",
                 "nofluffjobs.com", "justjoin.it", "facebook.com")
OFFER_HINTS = ("oferta", "oferty", "ogloszen", "praca", "job", "kariera", "career", "nabor", "rekrutac", "stanowisk", "konkurs", "vacanc", "/o/")
ROLE_WORDS = ("asystent", "sekretar", "administrac", "administrat", "biur", "office", "koordynat", "referent", "inspektor", "specjalist",
              "dokumentac", "kancelar", "recepc", "back office", "kadr", "rejestr", "archiw", "projekt", "operacyj", "pracownik", "obslug",
              "sprzeda", "handlow", "doradc", "konsultant", "customer", "klient", "account", "opiekun", "infolini", "call center")
SALES_ROLES = ("sprzedawca", "przedstawiciel handlowy", "telemarket", "doradca klienta", "call center", "kasjer")
JUNK_LINKS = ("logowanie", "login", "rejestracja", "polityka", "cookies", "regulamin", "kontakt", "rodo", "mapa", "facebook", "instagram",
              "twitter", "youtube", "mailto:", "tel:", "javascript:", "#")
AGGREGATORS = [("adzuna", "api://adzuna", "Adzuna — oferty z wielu polskich portali (API)"),
               ("jooble", "api://jooble", "Jooble — oferty z wielu polskich portali (API)")]
DEFAULT_SOURCES = [
    ("strona", "https://nabory.kprm.gov.pl/", "Służba cywilna — nabory (KPRM)"),
    ("strona", "https://praca.uj.edu.pl/", "Uniwersytet Jagielloński — praca"),
    ("strona", "https://www.bip.krakow.pl/?bip_id=1&mmi=1397", "BIP Kraków — nabory"),
]


def blocked(url):
    host = (urlparse(url).hostname or "").lower()
    return next((d for d in NO_AUTOMATION if host == d or host.endswith("." + d)), "")


def seed(c, ctx):
    if not R.meta_get(c, "zrodla_zasiane"):
        for typ, url, name in DEFAULT_SOURCES:
            c.execute("INSERT OR IGNORE INTO zrodla(typ,url,nazwa,dodano) VALUES(?,?,?,?)", (typ, url, name, R.stamp(ctx)))
        R.meta_set(c, "zrodla_zasiane", "1")
    if not R.meta_get(c, "agregatory_zasiane"):
        for typ, url, name in AGGREGATORS:
            c.execute("INSERT OR IGNORE INTO zrodla(typ,url,nazwa,dodano) VALUES(?,?,?,?)", (typ, url, name, R.stamp(ctx)))
        R.meta_set(c, "agregatory_zasiane", "1")


def kind_of(url):
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".recruitee.com"):
        return "recruitee"
    if re.search(r"(rss|atom|feed)(\.xml)?(\?|$|/)", url.lower()) or url.lower().endswith(".xml"):
        return "rss"
    return "strona"


# ================================================================ pobieranie

def _get(url, timeout=25, limit=3_000_000):
    """Strona źródła; każde przekierowanie sprawdzane osobno, zanim zostanie otwarte."""
    import requests
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh) Sebastian-Rekrutacja", "Accept-Language": "pl,en;q=0.7"}
    for _ in range(6):
        if not O.safe_url(url):
            raise RuntimeError("adres niepubliczny")
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=False, stream=True)
        if r.is_redirect:
            url = requests.compat.urljoin(url, r.headers.get("Location", ""))
            r.close()
            continue
        r.raise_for_status()
        raw = r.raw.read(limit, decode_content=True)
        return raw.decode(r.encoding or "utf-8", "replace"), url
    raise RuntimeError("za dużo przekierowań")


def jsonld_postings(page):
    """JobPosting z danych strukturalnych (Google for Jobs) — najpewniejsze dane, jeśli strona je ma."""
    out = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        with contextlib.suppress(Exception):
            data = json.loads(html.unescape(block.strip()))
            stack = data if isinstance(data, list) else [data]
            while stack:
                d = stack.pop()
                if isinstance(d, dict):
                    if "@graph" in d:
                        stack += d["@graph"] if isinstance(d["@graph"], list) else [d["@graph"]]
                    if d.get("@type") == "ItemList":
                        stack += [x.get("item", x) if isinstance(x, dict) else x for x in d.get("itemListElement", [])]
                    if d.get("@type") in ("JobPosting", ["JobPosting"]):
                        out.append(d)
                elif isinstance(d, list):
                    stack += d
    return out


def posting_text(p):
    org = p.get("hiringOrganization") or {}
    loc = p.get("jobLocation") or {}
    loc = loc[0] if isinstance(loc, list) and loc else loc
    addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
    city = addr.get("addressLocality", "") if isinstance(addr, dict) else ""
    remote = "praca zdalna" if str(p.get("jobLocationType", "")).upper() == "TELECOMMUTE" else ""
    desc, _ = O.to_text(str(p.get("description", "")))
    return {"tytul": str(p.get("title", ""))[:200], "firma": str(org.get("name", "") if isinstance(org, dict) else org)[:200],
            "miasto": ", ".join(x for x in (city, remote) if x), "url": str(p.get("url", "")),
            "tresc": f"{p.get('title', '')}\n{org.get('name', '') if isinstance(org, dict) else ''}\n{city} {remote}\n\n{desc}"[:20000]}


def links_from_page(page, base):
    """Linki, które wyglądają na pojedyncze ogłoszenia: (url, tekst)."""
    found, host = [], urlparse(base).hostname or ""
    for href, label in re.findall(r'<a\b[^>]*?href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        text = re.sub(r"\s+", " ", O.to_text(label)[0]).strip()
        url = urljoin(base, html.unescape(href))
        low_u, low_t = R.plain(url), R.plain(text)
        if not url.startswith("http") or len(text) < 6 or len(text) > 160 or any(j in low_u for j in JUNK_LINKS):
            continue
        same = (urlparse(url).hostname or "").endswith(host.replace("www.", "")) or any(a in url for a in ("recruitee.com", "teamtailor", "erecruiter", "elevato", "traffit", "hr-link"))
        if not same:
            continue
        if any(h in low_u for h in OFFER_HINTS) and (any(w in low_t for w in ROLE_WORDS) or re.search(r"/\d{3,}|[?&]id=\d+|/o/", low_u)):
            found.append((url, text))
    seen, unique = set(), []
    for u, t in found:
        k = R.norm_url(u)
        if k not in seen and k != R.norm_url(base):
            seen.add(k)
            unique.append((u, t))
    return unique[:80]


def rss_items(xml_text):
    out = []
    with contextlib.suppress(ET.ParseError):
        root = ET.fromstring(xml_text.encode("utf-8", "replace"))
        for it in root.iter():
            tag = it.tag.split("}")[-1]
            if tag not in ("item", "entry"):
                continue
            title = link = desc = ""
            for ch in it:
                t = ch.tag.split("}")[-1]
                if t == "title":
                    title = (ch.text or "").strip()
                elif t == "link":
                    link = (ch.get("href") or ch.text or "").strip()
                elif t in ("description", "summary", "content"):
                    desc = O.to_text(ch.text or "")[0]
            if link:
                out.append({"url": link, "tytul": title[:200], "tresc": f"{title}\n\n{desc}"[:20000] if desc else ""})
    return out[:100]


def recruitee_offers(url):
    host = urlparse(url).hostname
    page, _ = _get(f"https://{host}/api/offers/")
    data = json.loads(page)
    out = []
    for o in data.get("offers", []):
        desc = O.to_text((o.get("description") or "") + "\n" + (o.get("requirements") or ""))[0]
        city = ", ".join(x for x in (o.get("city") or "", "praca zdalna" if o.get("remote") else "") if x)
        out.append({"url": o.get("careers_url") or f"https://{host}/o/{o.get('slug')}", "tytul": o.get("title", ""),
                    "firma": o.get("company_name", ""), "miasto": city, "tresc": f"{o.get('title', '')}\n{city}\n\n{desc}"[:20000],
                    "kanal": {"typ": "recruitee", "host": host, "slug": o.get("slug", ""), "open_questions": len(o.get("open_questions") or [])}})
    return out


# ================================================================ agregatory z oficjalnym API (Adzuna, Jooble)

def phrases(ctx):
    return [p.strip() for p in str(ctx.settings().get("frazy", "")).split(",") if p.strip()][:12]


def adzuna(ctx, app_id, app_key, get=None):
    import requests
    get = get or requests.get
    out = []
    km = int(R.load_facts(ctx)["warunki"].get("dojazd_km") or 20)
    queries = [(p, "Kraków", km) for p in phrases(ctx)] + [("praca zdalna " + p, "", 0) for p in phrases(ctx)[:2]]
    for what, where, km in queries:
        params = {"app_id": app_id, "app_key": app_key, "what": what, "results_per_page": 50, "max_days_old": 10, "content-type": "application/json"}
        if where:
            params.update(where=where, distance=km)
        r = get("https://api.adzuna.com/v1/api/jobs/pl/search/1", params=params, timeout=30)
        if r.status_code in (401, 403):
            raise RuntimeError("Adzuna odrzuciła klucz")
        r.raise_for_status()
        for j in r.json().get("results", []):
            desc = O.to_text(j.get("description") or "")[0]
            city = (j.get("location") or {}).get("display_name", "")
            firm = (j.get("company") or {}).get("display_name", "")
            out.append({"url": j.get("redirect_url", ""), "tytul": j.get("title", ""), "firma": firm, "miasto": city,
                        "tresc": f"{j.get('title', '')}\n{firm}\n{city}\n\n{desc}"[:20000]})
    return out


def jooble(ctx, key, post=None):
    import requests
    post = post or requests.post
    host = str(ctx.settings().get("jooble_host", "") or "jooble.org")
    out = []
    for kw in phrases(ctx)[:4]:                                   # klucz Jooble ma mały limit — oszczędnie
        km = str(int(R.load_facts(ctx)["warunki"].get("dojazd_km") or 20))
        r = post(f"https://{host}/api/{key}", json={"keywords": kw, "location": "Kraków", "radius": km, "page": "1"}, timeout=30)
        if r.status_code in (401, 403):
            raise RuntimeError("Jooble odrzuciło klucz")
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            snip = O.to_text(j.get("snippet") or "")[0]
            out.append({"url": j.get("link", ""), "tytul": j.get("title", ""), "firma": j.get("company", ""), "miasto": j.get("location", ""),
                        "tresc": f"{j.get('title', '')}\n{j.get('company', '')}\n{j.get('location', '')}\n\n{snip}"[:20000]})
    return out


def scan_source(src, ctx=None):
    """[{url, tytul, tresc?, firma?, miasto?, kanal?}] z jednego źródła."""
    if src["typ"] == "recruitee":
        return recruitee_offers(src["url"])
    if src["typ"] == "adzuna":
        a, b = R.secret(ctx, "adzuna_id"), R.secret(ctx, "adzuna_key")
        if not a or not b:
            raise RuntimeError("brak klucza Adzuna (Ustawienia → Klucze)")
        return adzuna(ctx, a, b)
    if src["typ"] == "jooble":
        k = R.secret(ctx, "jooble")
        if not k:
            raise RuntimeError("brak klucza Jooble (Ustawienia → Klucze)")
        return jooble(ctx, k)
    page, final = _get(src["url"])
    if src["typ"] == "rss" or page.lstrip()[:200].lower().startswith(("<?xml", "<rss", "<feed")):
        return rss_items(page)
    posts = [posting_text(p) for p in jsonld_postings(page)]
    if posts:
        return [dict(p, url=p["url"] or final) for p in posts]
    return [{"url": u, "tytul": t} for u, t in links_from_page(page, final)]


# ================================================================ wstępny filtr (tani, przed pobraniem całej oferty)

def _ok_social(f):
    return not any("social" in R.plain(x) or "spolecznosciow" in R.plain(x) for x in f["kryteria"].get("nie_chce", []))


def looks_relevant(f, title, text=""):
    low = R.plain(title + " " + text[:600])
    if any(w in low for w in ("kierowca", "magazynier", "spawacz", "operator wozka", "kucharz", "sprzataczk", "budowlan", "monter",
                              "elektryk", "mechanik", "pielegniar", "lekarz", "programist", "developer", "kelner", "barista",
                              "ochron", "social media", "community manager", "content creator", "tiktok", "influencer", "copywriter",
                              "specjalista ds. mediow spolecznosciowych", "social media manager", "smm")) and not _ok_social(f):
        return False
    if any(w in low for w in SALES_ROLES) and any(x in R.SALES_AVOID for x in f["kryteria"].get("nie_chce", [])):
        return False
    wants = " ".join(R.plain(x) for x in f["kryteria"].get("chce", []))
    return any(w in low for w in ROLE_WORDS) or any(w in low for w in wants.split() if len(w) > 6)


def discover(ctx, max_new=40):
    """Przegląda źródła, których czas minął; nowe, pasujące na pierwszy rzut oka oferty trafiają do kolejki (status „nowa”)."""
    st = ctx.settings()
    f = R.load_facts(ctx)
    every = float(st.get("zrodla_co_godzin", 6)) * 3600
    added = 0
    with R.db(ctx) as c:
        seed(c, ctx)
        rows = [dict(r) for r in c.execute("SELECT * FROM zrodla WHERE wlaczone=1 ORDER BY sprawdzono")]
    for src in rows:
        if added >= max_new:
            break
        last = 0
        with contextlib.suppress(Exception):
            import datetime as dt
            last = dt.datetime.fromisoformat(src["sprawdzono"]).timestamp() if src["sprawdzono"] else 0
        period = every
        if src["typ"] == "adzuna":
            period = float(st.get("agregatory_co_godzin", 12)) * 3600
        elif src["typ"] == "jooble":
            period = float(st.get("jooble_co_godzin", 24)) * 3600
        if time.time() - last < period:
            continue
        if src["typ"] in ("adzuna", "jooble") and not (R.secret(ctx, "jooble") if src["typ"] == "jooble" else R.secret(ctx, "adzuna_key")):
            with R.db(ctx) as c:
                c.execute("UPDATE zrodla SET wynik=? WHERE id=?", ("czeka na klucz (Ustawienia → Klucze)", src["id"]))
                c.commit()
            continue
        if blocked(src["url"]):
            with R.db(ctx) as c:
                c.execute("UPDATE zrodla SET wlaczone=0, wynik=? WHERE id=?", ("Ten portal nie zgadza się na automaty — wklejaj oferty z niego linkiem.", src["id"]))
                c.commit()
            continue
        try:
            items = scan_source(src, ctx)
            msg, err = f"znaleziono {len(items)} ogłoszeń", 0
        except Exception as e:
            items, msg, err = [], f"nie działa: {type(e).__name__} {str(e)[:80]}", 1
        new = 0
        full = False
        with R.db(ctx) as c:
            for it in items:
                it["url"] = R.http_url(it.get("url"))
                key = R.norm_url(it["url"])
                if not key or c.execute("SELECT 1 FROM widziane WHERE url=?", (key,)).fetchone():
                    continue
                if added >= max_new:
                    full = True                                  # niewidziane zostają na następny przegląd
                    break
                c.execute("INSERT OR IGNORE INTO widziane(url,kiedy,zrodlo_id,tytul) VALUES(?,?,?,?)", (key, R.stamp(ctx), src["id"], it.get("tytul", "")[:200]))
                if not looks_relevant(f, it.get("tytul", ""), it.get("tresc", "")):
                    continue
                if R.find_duplicate(c, it.get("firma", ""), it.get("tytul", ""), it["url"]):
                    continue
                now = R.stamp(ctx)
                cur = c.execute("INSERT INTO aplikacje(utworzono,zmieniono,status,zrodlo,url,firma,stanowisko,miasto,tresc,kanal) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (now, now, "nowa", "auto", it["url"], it.get("firma", ""), "", it.get("miasto", ""), it.get("tresc", ""),
                                 json.dumps(it.get("kanal") or {})))
                R.note(c, ctx, cur.lastrowid, f"znaleziona automatycznie: {src['nazwa'] or src['url']}")
                new += 1
                added += 1
            c.execute("UPDATE zrodla SET sprawdzono=?, wynik=?, znalezione=znalezione+?, bledy=CASE WHEN ?=1 THEN bledy+1 ELSE 0 END WHERE id=?",
                      ("" if full else R.stamp(ctx), msg + (f", nowych pasujących: {new}" if items else "") + (" (reszta przy następnym przeglądzie)" if full else ""),
                       new, err, src["id"]))
            c.commit()
    return added


# ================================================================ aplikacje bez ogłoszenia (lista firm)

def import_firms(c, ctx, text):
    """Linie „Nazwa firmy; e-mail; strona; opis” albo „Nazwa, e-mail”. Zwraca (dodane, pominięte)."""
    added = skipped = 0
    for line in text.splitlines():
        parts = [p.strip() for p in re.split(r"[;\t]|,(?=\s*\S+@)", line) if p.strip()]
        mail = next((p.lower() for p in parts if R.EMAIL_OK.match(p)), "")
        name = next((p for p in parts if p.lower() != mail), "")
        if not name or not mail:
            skipped += 1 if line.strip() else 0
            continue
        www = next((p for p in parts if re.match(r"^(https?://|www\.)", p)), "")
        www = R.http_url(www if www.startswith("http") else ("https://" + www if www else ""))
        rest = [p for p in parts if p not in (name, mail, www)]
        if c.execute("SELECT 1 FROM firmy WHERE lower(email)=?", (mail,)).fetchone() or R.find_duplicate(c, name, "", zrodlo="spontaniczna"):
            skipped += 1
            continue
        c.execute("INSERT INTO firmy(nazwa,email,www,opis,dodano) VALUES(?,?,?,?,?)", (name[:200], mail, www[:300], " ".join(rest)[:1500], R.stamp(ctx)))
        added += 1
    c.commit()
    return added, skipped


def spontaneous_fill(ctx, need):
    """Uzupełnia kolejkę aplikacjami bez ogłoszenia z listy firm (najwyżej `need`)."""
    made = 0
    with R.db(ctx) as c:
        for firm in c.execute("SELECT * FROM firmy WHERE uzyta=0 ORDER BY id LIMIT ?", (max(0, need),)).fetchall():
            c.execute("UPDATE firmy SET uzyta=1 WHERE id=?", (firm["id"],))
            if R.find_duplicate(c, firm["nazwa"], "", zrodlo="spontaniczna"):
                continue
            now = R.stamp(ctx)
            tresc = f"{firm['nazwa']}\n{firm['www']}\n{firm['opis']}".strip()
            cur = c.execute("INSERT INTO aplikacje(utworzono,zmieniono,status,zrodlo,firma,email,tresc,klucz,url) VALUES(?,?,?,?,?,?,?,?,?)",
                            (now, now, "nowa", "spontaniczna", firm["nazwa"], firm["email"], tresc, R.dedupe_key(firm["nazwa"], ""), firm["www"]))
            R.note(c, ctx, cur.lastrowid, "z listy firm (bez ogłoszenia)")
            made += 1
        c.commit()
    return made
