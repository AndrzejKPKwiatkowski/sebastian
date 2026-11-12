"""Rekrutacja — oferty z Centralnej Bazy Ofert Pracy (urzędy pracy) przez oficjalną usługę ePraca/CBOP.

Usługa wymaga nazwy partnera nadanej przez MRPiPS (pole Partner), działa w godzinach udostępniania ustalonych przez
ministerstwo (wieczorem i w nocy) i ma limit 20 wywołań w jednym cyklu. Odpowiedź to spakowane pliki JSON
(najwyżej 1000 ofert w pliku). Pobieramy województwo małopolskie (kod 12) i zostawiamy oferty z dojazdu Agi.
"""
import base64, contextlib, io, json, re, time, zipfile

from . import rdzen as R, zrodla as Z

URLS = ("https://oferty.praca.gov.pl/integration/services/v2/oferta", "https://oferty.praca.gov.pl/integration/services/oferta")
NS = ("https://oferty.praca.gov.pl/v2/oferta", "https://oferty.praca.gov.pl/oferta")
MALOPOLSKIE = "12"


def request_xml(partner, ns, v2=True, region=MALOPOLSKIE):
    lang = "<Jezyk>pl</Jezyk>" if v2 else ""
    from xml.sax.saxutils import escape
    return (f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ofer="{ns}">'
            f"<soapenv:Header/><soapenv:Body><ofer:Dane><pytanie><Partner>{escape(partner)}</Partner>{lang}"
            f"<Kryterium><Wojewodztwo>{region}</Wojewodztwo></Kryterium></pytanie></ofer:Dane></soapenv:Body></soapenv:Envelope>")


def status_of(xml_text):
    for s in ("Niepoprawna autoryzacja", "Usługa niedostępna", "Przekroczono limit wywołań usługi", "Brak danych", "Poprawny"):
        if s in xml_text:
            return s
    return ""


def _walk(obj):
    if isinstance(obj, dict):
        if "stanowisko" in obj:
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def parse_response(xml_text):
    """Lista ofert (słowniki z pól CBOP) z odpowiedzi: szuka zakodowanego archiwum ZIP i czyta z niego pliki JSON."""
    out = []
    for blob in re.findall(r">\s*([A-Za-z0-9+/=\s]{400,})\s*<", xml_text):
        with contextlib.suppress(Exception):
            raw = base64.b64decode(re.sub(r"\s+", "", blob))
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for name in z.namelist():
                    if name.lower().endswith(".json"):
                        with contextlib.suppress(Exception):
                            out += list(_walk(json.loads(z.read(name).decode("utf-8-sig"))))
    return out


def _txt(v):
    if isinstance(v, list):
        return "; ".join(_txt(x) for x in v if _txt(x))
    if isinstance(v, dict):
        return ", ".join(_txt(x) for x in v.values() if _txt(x))
    return re.sub(r"\s+", " ", str(v or "")).strip()


def to_item(o):
    """Oferta CBOP → wpis do kolejki (pełna treść, bez otwierania strony)."""
    req = []
    for k in ("wymaganiaKonieczne", "wymaganiaPozadane", "wymaganiaDodatkowe"):
        if o.get(k):
            req.append(_txt(o[k]))
    if o.get("inneWymagania"):
        req.append(_txt(o["inneWymagania"]))
    city = _txt(o.get("miejscowosc")) or _txt(o.get("miejscePracy"))
    email = ""
    for k in ("email", "adresAplikowania", "emailOsobyZglPracodawca"):
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", _txt(o.get(k)))
        if m:
            email = m.group(0)
            break
    pay = _txt(o.get("wynagrodzenieBruttoZTypemStawki")) or _txt(o.get("wynagrodzenieBrutto"))
    body = "\n".join(x for x in (
        f"{_txt(o.get('stanowisko'))} — {_txt(o.get('pracodawca'))}",
        f"Miejsce pracy: {_txt(o.get('miejscePracy')) or city}",
        f"Wynagrodzenie: {pay} zł brutto" if pay else "",
        f"Rodzaj umowy: {_txt(o.get('rodzajUmowy'))}" if o.get("rodzajUmowy") else "",
        f"Wymiar: {_txt(o.get('wymiarEtatu'))}" if o.get("wymiarEtatu") else "",
        f"Obowiązki: {_txt(o.get('zakresObowiazkow')) or _txt(o.get('rodzajObowiazkow'))}",
        f"Wymagania: {'; '.join(req)}" if req else "",
        f"Sposób aplikowania: {_txt(o.get('sposobAplikowania'))} {_txt(o.get('adresAplikowania'))}".strip(),
        f"Kontakt: {_txt(o.get('osobaDoKontaktu'))} {_txt(o.get('nrTelefonu'))} {email}".strip(),
        "Źródło: Centralna Baza Ofert Pracy (urząd pracy).") if x and not re.search(r":\s*$", x))
    return {"tytul": _txt(o.get("stanowisko")), "firma": _txt(o.get("pracodawca")), "miasto": city, "email": email,
            "url": _txt(o.get("link")), "tresc": body}


def active(o):
    typ = _txt(o.get("typOferty")).upper()
    st = _txt(o.get("statusOferty")).upper()
    return (not typ or "OFERTA" in typ) and st in ("", "P", "A")


def fetch(partner, post=None):
    """(status, oferty). post(url, data, headers) → (kod, tekst); domyślnie requests."""
    if post is None:
        import requests

        def post(url, data, headers):
            r = requests.post(url, data=data.encode("utf-8"), headers=headers, timeout=120)
            return r.status_code, r.text
    last = ""
    for i, (url, ns) in enumerate(zip(URLS, NS)):
        code, text = post(url, request_xml(partner, ns, v2=(i == 0)), {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""})
        last = status_of(text) or f"HTTP {code}"
        if last in ("Niepoprawna autoryzacja", "Usługa niedostępna", "Przekroczono limit wywołań usługi"):
            return last, []
        items = parse_response(text)
        if items or last in ("Poprawny", "Brak danych"):
            return last or "Poprawny", items
    return last, []


def due(ctx, c, now):
    st = ctx.settings()
    partner = str(st.get("cbop_partner") or "").strip()
    if not partner:
        return ""
    if not (now.hour >= 19 or now.hour < 6):                                  # godziny udostępniania: wieczór i noc
        return ""
    last = float(R.meta_get(c, "cbop_ostatnio", "0") or 0)
    return partner if time.time() - last > 20 * 3600 else ""


def run(ctx, post=None, now=None):
    """Raz na dobę (wieczorem): pobiera małopolskie oferty i dodaje pasujące. Zwraca opis wyniku albo ''."""
    now = now or ctx.now()
    with R.db(ctx) as c:
        partner = due(ctx, c, now)
        if not partner:
            return ""
        R.meta_set(c, "cbop_ostatnio", time.time())
        c.commit()
    try:
        status, offers = fetch(partner, post)
    except Exception as e:
        status, offers = f"błąd połączenia ({type(e).__name__})", []
    f = R.load_facts(ctx)
    added = 0
    with R.db(ctx) as c:
        for o in offers:
            if active(o) and Z.add_found(c, ctx, f, to_item(o), "CBOP (urzędy pracy)"):
                added += 1
        msg = f"{status}: ofert {len(offers)}, nowych pasujących {added}"
        R.meta_set(c, "cbop_wynik", f"{R.stamp(ctx)[:16].replace('T', ' ')} — {msg}")
        c.commit()
    return msg
