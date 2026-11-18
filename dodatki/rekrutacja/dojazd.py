"""Rekrutacja — czas dojazdu z domu Agi do miejsca pracy (2.19).

Samochód, rower, pieszo: OSRM na danych OpenStreetMap (routing.openstreetmap.de, serwery FOSSGIS).
Komunikacja miejska: Transitous (api.transitous.org, rozkłady GTFS), przyjazd w najbliższy dzień roboczy na 8:00.
Adresy na współrzędne: Nominatim (OpenStreetMap). Wszystko z pamięcią podręczną, maks. 1 zapytanie na sekundę do każdej usługi.
Do usług trafiają tylko adres miejsca pracy z ogłoszenia i współrzędne — bez imienia i danych Agi.
"""
import contextlib, datetime as dt, json, math, re, time

from . import rdzen as R

UA = "Sebastian-rekrutacja/2.19 (prywatny asystent szukania pracy; https://github.com/AndrzejKPKwiatkowski/sebastian)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = {"samochod": "https://routing.openstreetmap.de/routed-car/route/v1/driving/",
        "rower": "https://routing.openstreetmap.de/routed-bike/route/v1/driving/",
        "pieszo": "https://routing.openstreetmap.de/routed-foot/route/v1/driving/"}
TRANSIT = "https://api.transitous.org/api/v1/plan"
MODES = ("samochod", "komunikacja", "rower", "pieszo")
WERSJA = 1
_last = {}
APPROX = {"city", "town", "village", "municipality", "county", "state", "region", "country", "administrative", "hamlet", "postcode"}


def _wait(service, gap=1.1):
    t = _last.get(service, 0) + gap - time.time()
    if t > 0:
        time.sleep(t)
    _last[service] = time.time()


def _get(service, url, params=None, timeout=20):
    import requests
    _wait(service)
    r = requests.get(url, params=params, headers={"User-Agent": UA, "Accept-Language": "pl"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _table(c):
    c.execute("CREATE TABLE IF NOT EXISTS dojazd_miejsca(klucz TEXT PRIMARY KEY, lat REAL, lon REAL, dokladny INTEGER, kiedy TEXT)")


def clean_address(text):
    t = re.sub(r"\s+", " ", text or "").strip(" ,.;")
    t = re.sub(r"(?i)\b(ul\.|ulica|al\.|aleja|os\.|osiedle)\s+", lambda m: {"ul.": "", "ulica": ""}.get(m.group(1).lower(), m.group(0)), t)
    return t[:160]


def geocode(ctx, text):
    """(lat, lon, dokładny) albo None. Wynik zapamiętany na stałe."""
    q = clean_address(text)
    if not q:
        return None
    key = R.plain(q)
    with R.db(ctx) as c:
        _table(c)
        row = c.execute("SELECT * FROM dojazd_miejsca WHERE klucz=?", (key,)).fetchone()
    if row:
        return (row["lat"], row["lon"], bool(row["dokladny"])) if row["lat"] is not None else None
    query = q if re.search(r"(?i)polska|poland", q) else q + ", Polska"
    found = _get("nominatim", NOMINATIM, {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "pl"})
    hit = found[0] if found else None
    res = None
    if hit:
        kind = str(hit.get("addresstype") or hit.get("type") or "")
        res = (float(hit["lat"]), float(hit["lon"]), kind not in APPROX)
    with R.db(ctx) as c:
        _table(c)
        c.execute("INSERT OR REPLACE INTO dojazd_miejsca VALUES(?,?,?,?,?)",
                  (key, res[0] if res else None, res[1] if res else None, int(res[2]) if res else 0, R.stamp(ctx)))
        c.commit()
    return res


def km_line(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def next_workday_8(now):
    d = now.date() + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    from zoneinfo import ZoneInfo
    return dt.datetime(d.year, d.month, d.day, 8, 0, tzinfo=ZoneInfo("Europe/Warsaw")).isoformat()


def street(ctx, mode, a, b):
    data = _get("osrm", OSRM[mode] + f"{a[1]:.6f},{a[0]:.6f};{b[1]:.6f},{b[0]:.6f}", {"overview": "false"})
    routes = data.get("routes") or []
    return round(routes[0]["duration"] / 60) if routes else None


def transit(ctx, a, b):
    data = _get("transitous", TRANSIT, {"fromPlace": f"{a[0]:.6f},{a[1]:.6f}", "toPlace": f"{b[0]:.6f},{b[1]:.6f}",
                                        "time": next_workday_8(ctx.now()), "arriveBy": "true"}, timeout=30)
    its = [i.get("duration") for i in (data.get("itineraries") or []) if isinstance(i.get("duration"), (int, float))]
    return round(min(its) / 60) if its else None


def destination(info, a):
    """Adres do liczenia: adres z ogłoszenia albo miasto. Pusty, gdy praca zdalna albo nic nie wiadomo."""
    where = (info.get("adres") or "").strip()
    city = (a.get("miasto") or "").strip()
    if R.km_from_krakow(" ".join((where, city))) == -1 and not re.search(r"\d", where):
        return ""
    if where and city and R.plain(city.split(",")[0]) not in R.plain(where):
        where = f"{where}, {city}"
    return where or city


def compute(ctx, info, a):
    """Słownik z czasami w minutach albo z powodem, dlaczego się nie dało."""
    st = ctx.settings()
    home_txt = (st.get("dojazd_skad") or "").strip()
    dest_txt = destination(info, a)
    out = {"v": WERSJA, "skad": home_txt, "cel": dest_txt}
    if not dest_txt:
        out["brak"] = "praca zdalna" if R.km_from_krakow(" ".join((info.get("adres") or "", a.get("miasto") or ""))) == -1 else "ogłoszenie nie podaje miejsca"
        return out
    if not home_txt or R.plain(home_txt) in ("krakow", ""):
        out["brak"] = "wpisz swój adres w Ustawieniach (Skąd dojeżdżasz)"
        return out
    try:
        home, dest = geocode(ctx, home_txt), geocode(ctx, dest_txt)
    except Exception as e:
        out["blad"] = f"mapa nie odpowiada ({type(e).__name__})"
        return out
    if not home:
        out["brak"] = "nie znalazłem Twojego adresu na mapie — popraw go w Ustawieniach"
        return out
    if not dest:
        out["brak"] = "nie znalazłem tego adresu na mapie"
        return out
    out["dokladny"] = dest[2]
    out["km"] = round(km_line(home, dest), 1)
    if out["km"] > 150:
        out["brak"] = f"ok. {round(out['km'])} km w linii prostej"
        return out
    for mode in ("samochod", "rower", "pieszo"):
        with contextlib.suppress(Exception):
            out[mode] = street(ctx, mode, home, dest)
    with contextlib.suppress(Exception):
        out["komunikacja"] = transit(ctx, home, dest)
    if not any(out.get(m) is not None for m in MODES):
        out["blad"] = "usługi map nie odpowiedziały — spróbuję później"
    return out


def too_far(ctx, d, pay_netto):
    """Powód odrzucenia albo pusty tekst (2.19.1): komunikacją 70 min i więcej LUB samochodem ponad 40 min, chyba że netto > 6500 zł.
    Ustawienie dojazd_tryb = „i” — odrzucam dopiero, gdy za długo jest oboma sposobami."""
    if not d or d.get("brak") or d.get("blad") or (not d.get("dokladny", True) and d.get("km", 0) < 15):
        return ""                                                     # samo „Kraków” — za mało, żeby odrzucać
    st = ctx.settings()
    max_t, max_c = int(st.get("dojazd_max_komunikacja", 70)), int(st.get("dojazd_max_samochod", 40))
    limit_pay = float(st.get("dojazd_wyjatek_netto", 6500))
    t, c = d.get("komunikacja"), d.get("samochod")
    if t is None and c is None:
        return ""
    if st.get("dojazd_tryb", "lub") == "i":
        if not ((t is None or t >= max_t) and (c is None or c > max_c)):
            return ""
    elif not ((t is not None and t >= max_t) or (c is not None and c > max_c)):
        return ""
    if pay_netto and pay_netto > limit_pay:
        return ""
    parts = ([f"komunikacją {t} min"] if t is not None else ["bez połączenia komunikacją"]) + ([f"samochodem {c} min"] if c is not None else [])
    return "za długi dojazd (" + ", ".join(parts) + ")"


def label(m):
    if m is None:
        return "—"
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d} min"
