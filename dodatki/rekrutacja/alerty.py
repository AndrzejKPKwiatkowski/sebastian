"""Rekrutacja — oferty z alertów e-mail portali (Pracuj.pl, OLX, Indeed, LinkedIn, justjoin.it, RocketJobs, Aplikuj.pl, GoWork, Praca.pl…).

Aga zapisuje się na alerty sama; portale przysyłają jej maile z nowymi ofertami, a Sebastian czyta je w jej skrzynce
(tak jak każdą inną pocztę) i wyciąga stanowiska z linkami. Stron portali nie otwiera automatycznie — oferta trafia do panelu
z opisem z maila, a jeśli firma ma adres e-mail na swojej stronie, aplikacja może pójść mailem.
"""
import re

from . import rdzen as R, zrodla as Z

PORTALS = {"pracuj.pl": "Pracuj.pl", "olx.pl": "OLX", "indeed.": "Indeed", "linkedin.com": "LinkedIn", "justjoin.it": "justjoin.it",
           "rocketjobs.pl": "RocketJobs", "aplikuj.pl": "Aplikuj.pl", "gowork.pl": "GoWork", "praca.pl": "Praca.pl",
           "infopraca.pl": "InfoPraca", "nofluffjobs.com": "No Fluff Jobs", "theprotocol.it": "theprotocol", "jooble": "Jooble",
           "careerjet": "Careerjet", "praca.gov.pl": "praca.gov.pl", "bulldogjob": "Bulldogjob", "olx.": "OLX"}
NAV = re.compile(r"(?i)^(zobacz|sprawdź|sprawdz|aplikuj|więcej|wiecej|wszystkie|pokaż|pokaz|kliknij|tutaj|here|view|apply|see|"
                 r"wypisz|zrezygnuj|ustawienia|zarządzaj|zarzadzaj|edytuj|usuń|pobierz|zaloguj|regulamin|polityka|pomoc|kontakt|"
                 r"facebook|instagram|youtube|twitter|tiktok|app store|google play|otwórz|otworz|przejdź|przejdz)\b")
OFFER_URL = re.compile(r"(?i)(oferta|oferty|/praca/|job|viewjob|/rc/clk|/jobs/view|job-offer|/o/|/offer|clk|click|redirect|track|/l/)")


def portal_of(m):
    who = R.plain(f"{m.get('od', '')} {m.get('od_nazwa', '')}")
    return next((name for dom, name in PORTALS.items() if dom.rstrip(".") in who), "")


def is_alert(m):
    """Mail z portalu z kilkoma ofertami (nie potwierdzenie aplikacji i nie odpowiedź pracodawcy)."""
    if not portal_of(m):
        return False
    low = R.plain(f"{m.get('temat', '')} {m.get('tresc', '')[:3000]}")
    if re.search(r"(twoja aplikacja|aplikacja zostala|dziekujemy za aplikacj|zaprasza|rozmow)", low) and len(offers(m)) < 2:
        return False
    return len(offers(m)) >= 1 and bool(re.search(r"(ofert|ogloszen|stanowisk|alert|nowe|pasujac|dla ciebie|jobs?\b|praca)", low))


def _looks_like_title(t):
    t = t.strip()
    words = t.split()
    return 1 <= len(words) <= 14 and 4 <= len(t) <= 120 and not NAV.match(t) and not re.fullmatch(r"[\d\s.,zł-]+", t)


def offers(m):
    """[{tytul, url, tresc, miasto, firma}] z linków maila; opis = tekst maila tuż po tytule."""
    text = m.get("tresc") or ""
    out, seen = [], set()
    for l in m.get("linki_wszystkie") or m.get("linki") or []:
        title, url = (l.get("tekst") or "").strip(), l.get("url") or ""
        if not url.startswith(("http://", "https://")) or not _looks_like_title(title) or not OFFER_URL.search(url):
            continue
        k = R.norm(title)
        if k in seen:
            continue
        seen.add(k)
        pos = text.find(title)
        after = text[pos + len(title): pos + len(title) + 260] if pos >= 0 else ""
        after = re.split(r"\n\s*\n", after.strip())[0][:220]
        lines = [x.strip(" •·|-–") for x in re.split(r"[\n|·•]", after) if x.strip(" •·|-–")]
        city = next((x for x in lines if R.km_from_krakow(x) is not None and len(x) < 60), "")
        firm = next((x for x in lines if x != city and 2 <= len(x) <= 70 and not re.search(r"\d{3,}|zł|pln|dni temu|godz", x, re.I)), "")
        out.append({"tytul": title, "url": url, "miasto": city, "firma": firm,
                    "tresc": f"{title}\n{after}\n\n(Oferta z alertu e-mail; pełna treść na stronie portalu.)"})
    return out[:60]


def import_alert(ctx, m):
    """Dodaje oferty z alertu do kolejki. Zwraca (portal, ile dodanych, ile w mailu)."""
    portal = portal_of(m)
    items = offers(m)
    f = R.load_facts(ctx)
    added = 0
    with R.db(ctx) as c:
        for it in items:
            if Z.add_found(c, ctx, f, it, f"alert {portal}"):
                added += 1
        c.commit()
    return portal, added, len(items)
