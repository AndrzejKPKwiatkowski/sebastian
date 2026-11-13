"""Rekrutacja — dokumenty: CV, list motywacyjny, mail i kontroler prawdy.

Zasada: CV NIE jest pisane przez model. Model wybiera tylko numery faktów (co wyeksponować i w jakiej kolejności),
a tekst zawsze pochodzi z bazy faktów zatwierdzonej przez Agę. List i mail pisze model, ale zanim trafią do Agi,
czyta je kontroler prawdy (reguły + drugi przebieg modelu) i zgłasza wszystko, czego baza faktów nie potwierdza.
"""
import contextlib, datetime as dt, io, json, re
from pathlib import Path
from xml.sax.saxutils import escape

from . import rdzen as R

HERE = Path(__file__).resolve().parent
MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
          "października", "listopada", "grudnia"]
DARK, GREY, INK = "#3e3a39", "#d9d9d9", "#2b2b2b"

# ================================================================ czcionki

_FONTS = None


def fonts():
    """(zwykła, pogrubiona, kursywa, lekka) — Montserrat z dodatku; awaryjnie Arial/DejaVu; ostatecznie Helvetica."""
    global _FONTS
    if _FONTS:
        return _FONTS
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    sets = [[HERE / "fonty" / f"Montserrat-{w}.ttf" for w in ("Regular", "Bold", "Italic", "Light")],
            [Path("/System/Library/Fonts/Supplemental") / n for n in ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial.ttf")],
            [Path("/usr/share/fonts/truetype/dejavu") / n for n in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans.ttf")]]
    for paths in sets:
        if all(p.exists() for p in paths):
            try:
                names = ("RekR", "RekB", "RekI", "RekL")
                for name, p in zip(names, paths):
                    pdfmetrics.registerFont(TTFont(name, str(p)))
                _FONTS = names
                return _FONTS
            except Exception:
                continue
    _FONTS = ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica")
    return _FONTS


# ================================================================ wybór faktów do CV (model zwraca tylko numery)

def _ym(text):
    t = R.plain(text or "")
    if any(w in t for w in ("obecnie", "nadal", "teraz", "present")):
        return (9999, 12)
    m = re.search(r"(\d{1,2})[./-](\d{4})", t) or re.search(r"()(\d{4})", t)
    return (int(m.group(2)), int(m.group(1) or 0)) if m else (0, 0)


def chronological(f, ids):
    """Od najnowszego: najpierw data zakończenia, potem rozpoczęcia."""
    by = {j["id"]: j for j in f["doswiadczenie"]}
    return sorted(ids, key=lambda i: (_ym(by[i].get("do")), _ym(by[i].get("od"))), reverse=True)


POINTS_PER_JOB = 3


def courses_newest_first(kursy):
    """Kursy od najnowszego (rok w nawiasie); bez roku na końcu, w kolejności z bazy."""
    return sorted(kursy, key=lambda k: _ym(k["tekst"]), reverse=True)


def default_selection(f):
    return {"kolejnosc": chronological(f, [j["id"] for j in f["doswiadczenie"] if not j.get("opcjonalne")]),
            "z_modelu": False,
            "punkty": {j["id"]: [p["id"] for p in j["punkty"]][:POINTS_PER_JOB] for j in f["doswiadczenie"]},
            "profil": [p["id"] for p in f["profil"]][:4],
            "umiejetnosci": [u["id"] for u in f["umiejetnosci"]][:6],
            "narzedzia": [t["id"] for t in f["narzedzia"]][:7]}


def clean_selection(f, sel):
    """Z odpowiedzi modelu zostają wyłącznie istniejące numery; nic nie znika z doświadczenia."""
    base = default_selection(f)
    if not isinstance(sel, dict):
        return base

    def pick(key, pool, limit, minimum=1):
        got = [x for x in dict.fromkeys(sel.get(key) or []) if x in pool][:limit]
        return got if len(got) >= minimum else base[key]

    jobs = [j["id"] for j in f["doswiadczenie"]]
    optional = {j["id"] for j in f["doswiadczenie"] if j.get("opcjonalne")}
    ranking = [x for x in dict.fromkeys(sel.get("ranking") or sel.get("kolejnosc") or []) if x in jobs]
    picked = sel["z_modelu"] if isinstance(sel.get("z_modelu"), bool) else bool(ranking)
    ranking += [x for x in jobs if x not in ranking and x not in optional]  # stanowiska opcjonalne tylko, gdy pasują do oferty
    order = chronological(f, ranking)                                      # w CV zawsze od najnowszego
    points = {}
    for j in f["doswiadczenie"]:
        ids = [p["id"] for p in j["punkty"]]
        got = [x for x in dict.fromkeys((sel.get("punkty") or {}).get(j["id"]) or []) if x in ids]
        points[j["id"]] = (got + [x for x in ids if x not in got])[:POINTS_PER_JOB]   # 3 najważniejsze dla oferty
    hidden = [x for x in dict.fromkeys(sel.get("ukryte") or []) if x in jobs]
    if hidden and len(hidden) < len(order):
        order = [x for x in order if x not in hidden]
    extra = [x for x in dict.fromkeys(sel.get("pokazane") or []) if x in jobs and x not in order]
    if extra:
        order = chronological(f, order + extra)
    out = {"kolejnosc": order, "ranking": ranking, "z_modelu": picked, "punkty": points,
           "profil": pick("profil", [p["id"] for p in f["profil"]], 4, 2),
           "umiejetnosci": pick("umiejetnosci", [u["id"] for u in f["umiejetnosci"]], 6, 3),
           "narzedzia": pick("narzedzia", [t["id"] for t in f["narzedzia"]], 7, 1)}
    if hidden:
        out["ukryte"] = hidden
    if extra:
        out["pokazane"] = extra
    prof = re.sub(r"\s+", " ", str(sel.get("profil_tekst") or "")).strip()
    if prof:
        out["profil_tekst"] = prof[:900]                                   # opis pod ofertę (sprawdzony) albo poprawiony przez Agę
        out["profil_zrodlo"] = sel.get("profil_zrodlo") if sel.get("profil_zrodlo") in ("model", "aga") else "aga"
    model_prof = re.sub(r"\s+", " ", str(sel.get("profil_model") or (prof if sel.get("profil_zrodlo") == "model" else ""))).strip()
    if model_prof:
        out["profil_model"] = model_prof[:900]                             # wersja Sebastiana — do przywrócenia po edycji
    own = sel.get("wlasne_punkty") if isinstance(sel.get("wlasne_punkty"), dict) else {}
    own = {k: [re.sub(r"\s+", " ", str(t)).strip()[:300] for t in v if str(t).strip()][:5]
           for k, v in own.items() if k in jobs and isinstance(v, list)}
    own = {k: v for k, v in own.items() if v}
    if own:
        out["wlasne_punkty"] = own                                         # punkty poprawione ręcznie przez Agę
    return out


def cv_content(f, sel):
    """Co faktycznie stoi w CV: (opis, {stanowisko: [punkty]}) — z uwzględnieniem poprawek Agi."""
    sel = clean_selection(f, sel)
    profile = sel.get("profil_tekst") or " ".join(p["tekst"] for p in f["profil"] if p["id"] in sel["profil"])
    by_id = {j["id"]: j for j in f["doswiadczenie"]}
    points = {}
    for jid in sel["kolejnosc"]:
        if jid in sel.get("wlasne_punkty", {}):
            points[jid] = sel["wlasne_punkty"][jid]
        else:
            texts = {p["id"]: p["tekst"] for p in by_id[jid]["punkty"]}
            points[jid] = [texts[x] for x in sel["punkty"].get(jid, []) if x in texts]
    return profile, points


def apply_cv_edit(f, sel, form_profile, form_points, shown):
    """Poprawki Agi z ekranu „Edytuj CV”. form_points: {stanowisko: [teksty]}, shown: stanowiska zaznaczone do CV."""
    sel = clean_selection(f, sel)
    base = {k: v for k, v in sel.items() if k not in ("wlasne_punkty", "ukryte", "pokazane")}
    base_prof, base_points = cv_content(f, dict(base, profil_tekst=sel.get("profil_model") or "", profil_zrodlo="model"))
    jobs = [j["id"] for j in f["doswiadczenie"]]
    shown = [x for x in shown if x in jobs]
    if not shown:
        raise ValueError("W CV musi zostać przynajmniej jedno stanowisko.")
    new = dict(base)
    new["ukryte"] = [x for x in base["kolejnosc"] if x not in shown]
    new["pokazane"] = [x for x in shown if x not in base["kolejnosc"]]
    by_id = {j["id"]: j for j in f["doswiadczenie"]}
    own = {}
    for jid in shown:
        texts = [re.sub(r"\s+", " ", t).strip() for t in form_points.get(jid, []) if t and t.strip()]
        default = base_points.get(jid) or [p["tekst"] for p in by_id[jid]["punkty"]][:POINTS_PER_JOB]
        if texts and texts != default:
            own[jid] = texts
    new["wlasne_punkty"] = own
    prof = re.sub(r"\s+", " ", form_profile or "").strip()
    if prof and prof != base_prof:
        new.update(profil_tekst=prof, profil_zrodlo="aga")
    elif sel.get("profil_model"):
        new.update(profil_tekst=sel["profil_model"], profil_zrodlo="model")
    else:
        new.pop("profil_tekst", None)
    return clean_selection(f, new)


def reset_cv_edit(f, sel):
    sel = clean_selection(f, sel)
    new = {k: v for k, v in sel.items() if k not in ("wlasne_punkty", "ukryte", "pokazane", "profil_tekst", "profil_zrodlo")}
    if sel.get("profil_model"):
        new.update(profil_tekst=sel["profil_model"], profil_zrodlo="model")
    return clean_selection(f, new)


def select_for_offer(ctx, f, app):
    prompt = f"""Dobierasz, co wyeksponować w CV pod konkretną ofertę pracy. NIE piszesz żadnego tekstu.
Zwracasz wyłącznie numery faktów z listy poniżej (w nawiasach kwadratowych). Nie wymyślaj numerów.

OFERTA: {app['stanowisko']} — {app['firma']} ({app['miasto']})
{(app['tresc'] or '')[:3500]}

FAKTY:
{R.facts_brief(f)}

Zwróć JSON:
{{"kolejnosc": [numery stanowisk d… od NAJLEPIEJ PASUJĄCEGO do oferty (np. przy ofercie pedagogicznej najpierw praca z dziećmi i praktyki,
     przy gastronomii najpierw gastronomia, przy biurze najpierw administracja); stanowiska oznaczone (opcjonalne) dodaj tylko, gdy pasują],
  "punkty": {{"d1": [DOKŁADNIE 3 numery punktów tego stanowiska, które najbardziej zwiększą szansę na tę pracę; najważniejszy pierwszy;
     punkty z liczbami i konkretnymi efektami mają pierwszeństwo, gdy pasują do oferty]}},
  "profil": [3 albo 4 numery zdań p…, w kolejności czytania],
  "umiejetnosci": [do 6 numerów u…],
  "narzedzia": [do 7 numerów n…]}}"""
    try:
        return clean_selection(f, ctx.ask(prompt, as_json=True, max_tokens=700, temperature=0.1))
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: wybór faktów bez modelu ({type(e).__name__})")
        return default_selection(f)


def tailored_profile(ctx, f, app):
    """Opis na górę CV pisany pod ofertę, wyłącznie z faktów. Pusty tekst, gdy model nie odpowie albo dopisze coś spoza faktów."""
    if not (app.get("tresc") or "").strip() and not app.get("stanowisko"):
        return ""
    prompt = f"""Napisz opis do sekcji „Profil zawodowy” w CV kandydatki, dopasowany do tej oferty. Po polsku, w formach żeńskich.

ŻELAZNA ZASADA: wyłącznie to, co jest w FAKTACH. Żadnych nowych umiejętności, narzędzi, lat doświadczenia, liczb ani certyfikatów.
Wybierz z FAKTÓW to, co najbardziej odpowiada wymaganiom oferty, i nazwij to słowami bliskimi ogłoszeniu.
Jeśli w FAKTACH jest liczba, która pasuje do oferty (np. ile dokumentów miesięcznie), możesz ją podać dokładnie tak jak w faktach.

FORMA: 2 albo 3 zdania, razem 35–65 słów. Styl CV, bez „ja”, bez nazwy firmy, bez frazesów („z pasją”, „dynamiczny”),
bez myślników. Pierwsze zdanie mówi, kim jest kandydatka w kontekście tej roli (np. „Specjalistka ds. …”, „Pedagożka …”).

OFERTA: {app.get('stanowisko') or '(zapytanie o współpracę)'} — {app.get('firma') or ''}
{(app.get('tresc') or '')[:3000]}

FAKTY:
{R.facts_brief(f, ids=False)}

Zwróć JSON {{"profil": "..."}}"""
    with contextlib.suppress(Exception):
        out = write(ctx, prompt, max_tokens=300, temperature=0.3)
        text = re.sub(r"\s+", " ", re.sub(r"[ \t]*[—–][ \t]*", ", ", str((out or {}).get("profil") or ""))).strip()
        words = len(text.split())
        if 15 <= words <= 90 and not rule_check(f, app, text):
            return text
    return ""


# ================================================================ CV (ReportLab) — układ jak w dotychczasowym CV Agi

def render_cv(f, sel, out_path, photo=None, rodo=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    sel = clean_selection(f, sel)
    rodo = rodo or f.get("rodo") or R.RODO
    scales = (1.3, 1.25, 1.2, 1.15, 1.1, 1.05, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7)   # największy rozmiar, który się mieści

    def trial(kl, kr):
        c = canvas.Canvas(io.BytesIO(), pagesize=A4)
        return _draw_cv(c, f, sel, None, rodo, kl, kr)
    kl = next((k for k in scales if trial(k, 0.7)[0]), 0.7)               # lewa i prawa kolumna dobierane osobno
    kr = next((k for k in scales if trial(kl, k)[1]), 0.7)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"CV — {R.full_name(f)}")
    c.setAuthor(R.full_name(f))
    _draw_cv(c, f, sel, photo, rodo, kl, kr)
    c.save()
    data = buf.getvalue()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(data)
    return out_path


def _para(text, font, size, color=INK, leading=None, bullet=False):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    st = ParagraphStyle("x", fontName=font, fontSize=size, leading=leading or size * 1.38, textColor=HexColor(color),
                        leftIndent=size * 1.3 if bullet else 0, bulletIndent=size * 0.2 if bullet else 0,
                        bulletFontName=font, bulletFontSize=size)
    return Paragraph(text, st, bulletText="•" if bullet else None)


def _flow(c, items, x, y, width, draw=True):
    """Rysuje akapity jeden pod drugim od y w dół; zwraca y po ostatnim. items: (Paragraph, odstęp_po)."""
    for p, gap in items:
        _, h = p.wrap(width, 2000)
        if draw:
            p.drawOn(c, x, y - h)
        y -= h + gap
    return y


def _heading(c, text, x, y, width, size):
    from reportlab.lib.colors import HexColor
    FB = fonts()[1]
    c.saveState()                                   # odstęp między literami nie może „wyciec” do dalszego tekstu
    c.setFillColor(HexColor(INK))
    t = c.beginText(x, y)
    t.setFont(FB, size)
    t.setCharSpace(size * 0.26)
    t.textOut(text.upper())
    c.drawText(t)
    c.restoreState()
    c.setStrokeColor(HexColor(INK))
    c.setLineWidth(0.7)
    c.line(x, y - size * 0.55, x + width, y - size * 0.55)
    return y - size * 1.55


def _draw_cv(c, f, sel, photo, rodo, kl, kr=None):
    """Rysuje CV; kl/kr — skala tekstu lewej i prawej kolumny. Zwraca (lewa_się_mieści, prawa_się_mieści)."""
    kr = kl if kr is None else kr
    k = kr
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    FR, FB, FI, FL = fonts()
    W, H = A4
    LW, PH, HH = 258.0, 240.0, 157.0
    o = f["osoba"]
    fits = True
    body, head = 8.7 * k, 13.2 * k

    # ---- tło lewej kolumny, zdjęcie, nagłówek z nazwiskiem
    c.setFillColor(HexColor(GREY)); c.rect(0, 0, LW, H - PH, stroke=0, fill=1)
    c.setFillColor(HexColor(DARK)); c.rect(0, H - PH, LW, PH, stroke=0, fill=1)
    if photo and Path(photo).exists():
        try:
            img = ImageReader(str(photo))
            iw, ih = img.getSize()
            s = max(LW / iw, PH / ih)
            c.saveState()
            path = c.beginPath(); path.rect(0, H - PH, LW, PH); c.clipPath(path, stroke=0, fill=0)
            c.drawImage(img, (LW - iw * s) / 2, H - ih * s, iw * s, ih * s)       # dosunięte do góry (twarz)
            c.restoreState()
        except Exception:
            pass
    c.setFillColor(HexColor(DARK)); c.rect(LW, H - HH, W - LW, HH, stroke=0, fill=1)
    c.setFillColor(white)
    name_size = 40.0
    from reportlab.pdfbase.pdfmetrics import stringWidth
    longest = max(o.get("imie", ""), o.get("nazwisko", ""), key=len)
    while name_size > 22 and stringWidth(longest, FL, name_size) > W - LW - 44:
        name_size -= 1
    c.setFont(FL, name_size)
    c.drawString(LW + 24, H - 72, o.get("imie", ""))
    c.drawString(LW + 24, H - 72 - name_size * 1.08, o.get("nazwisko", ""))

    # ---- prawa strona: profil, doświadczenie, RODO
    x0 = LW + 20
    RW = W - x0 - 24
    y = _heading(c, "Profil zawodowy", x0, H - HH - 30, RW * 0.94, head)
    profil, chosen = cv_content(f, sel)
    y = _flow(c, [(_para(escape(profil), FR, body), 0)], x0, y - 4, RW)

    rodo_items = [(_para("<b>KLAUZULA RODO</b>", FB, 5.9, leading=7.6), 0), (_para(escape(rodo), FI, 5.9, leading=7.6), 0)]
    rodo_h = 18 - _flow(c, rodo_items, x0, 18, RW, draw=False)
    _flow(c, rodo_items, x0, 18 + rodo_h, RW)
    floor = 18 + rodo_h + 12

    y = _heading(c, "Doświadczenie", x0, y - 22 * k, RW * 0.94, head)
    top = y - 4
    col_w = (RW - 14) / 2
    by_id = {j["id"]: j for j in f["doswiadczenie"]}
    blocks = []
    for jid in sel["kolejnosc"]:
        j = by_id[jid]
        place = ", ".join(x for x in (j.get("firma", ""), j.get("miejsce", "")) if x)
        items = [(_para(f"<b>{escape(j['stanowisko'])}</b>", FB, body), 0)]
        if place:
            items.append((_para(f"<b>{escape(place)}</b>", FB, body), 1))
        items.append((_para(escape(f"{j.get('od', '')} - {j.get('do', '')}"), FR, body * 0.94), 2.5))
        items += [(_para(escape(t), FR, body, bullet=True), 0.6) for t in chosen.get(jid, [])]
        blocks.append((items, top - _flow(c, items, 0, top, col_w, draw=False) + 9 * k))
    heights = [h for _, h in blocks]
    split = min(range(len(blocks) + 1), key=lambda i: max(sum(heights[:i]), sum(heights[i:]))) if blocks else 0
    for col, part in enumerate((blocks[:split], blocks[split:])):
        used = sum(h for _, h in part)
        spare = (top - floor) - used
        gap = min(22.0, spare / max(1, len(part))) if spare > 0 else 0        # równo rozłożony zapas, żeby kolumna nie była pusta
        yy = top
        for items, h in part:
            _flow(c, items, x0 + col * (col_w + 14), yy, col_w)
            yy -= h + gap
        fits = fits and top - used >= floor - 9 * k

    right_fits, fits = fits, True
    k = kl
    body, head = 8.7 * k, 13.2 * k
    # ---- lewa kolumna: kursy, umiejętności, narzędzia, języki, wykształcenie, kontakt
    lx, lw = 24.0, LW - 46
    contact_h = 132.0
    y = H - PH - 34

    def section(title, paragraphs, yy):
        yy = _heading(c, title, lx, yy, lw * 0.92, head)
        return _flow(c, paragraphs, lx - 2, yy - 2, lw + 2) - 21 * k

    y = section("Kursy i kwalifikacje", [(_para(escape(x["tekst"]), FL, body, bullet=True), 1.5) for x in courses_newest_first(f["kursy"])], y)
    skills = [u for u in f["umiejetnosci"] if u["id"] in sel["umiejetnosci"]]
    y = section("Umiejętności", [(_para(escape(x["tekst"]), FL, body, bullet=True), 0.5) for x in skills], y)
    tools = [t for t in f["narzedzia"] if t["id"] in sel["narzedzia"]]
    if tools:
        y = section("Narzędzia", [(_para(escape(t["nazwa"] + (f" – {t['poziom']}" if t["poziom"] else "")), FL, body, bullet=True), 0.5) for t in tools], y)
    langs = [(_para(escape(x["tekst"]), FL, body, bullet=True), 0.5) for x in f["jezyki"]]
    if f.get("prawo_jazdy"):
        langs.append((_para("prawo jazdy kat. B", FL, body, bullet=True), 0.5))
    y = section("Języki" + (" i uprawnienia" if f.get("prawo_jazdy") else ""), langs, y)
    edu = []
    for e in f["wyksztalcenie"]:
        edu += [(_para(f"<b>{escape(e.get('uczelnia', ''))}</b>", FB, body * 0.93), 0.5),
                (_para(escape(e.get("kierunek", "")), FL, body * 0.93), 0.5),
                (_para(escape(" | ".join(x for x in (e.get("tytul", ""), e.get("okres", "")) if x)), FI, body * 0.93), 9 * k)]
    y = section("Wykształcenie", edu, y)
    fits = fits and y >= contact_h - 4

    c.setFillColor(HexColor(DARK)); c.rect(13, 0, LW - 13, contact_h, stroke=0, fill=1)
    lines = [x for x in (o.get("adres", ""), o.get("miasto", ""), o.get("telefon", ""), o.get("email", "")) if x]
    if o.get("linkedin"):
        lines.append(re.sub(r"^https?://(www\.)?", "", o["linkedin"]).rstrip("/"))
    c.setFillColor(white)
    size = 9.6
    widest = max((stringWidth(s_, FR, size) for s_ in lines), default=0)
    if widest > LW - 13 - 40:
        size = max(6.5, size * (LW - 13 - 40) / widest)
    c.setFont(FR, size)
    step = min(19.0, (contact_h - 34) / max(1, len(lines) - 1)) if len(lines) > 1 else 0
    yy = contact_h - 24 - (contact_h - 48 - step * (len(lines) - 1)) / 2
    for line in lines:
        c.drawString(13 + 22, yy, line)
        yy -= step
    return fits, right_fits


# ================================================================ list motywacyjny (PDF)

def polish_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def render_letter(f, text, out_path, firma="", stanowisko="", today=None, rodo=None, adres_firmy="", podpis=None):
    """List motywacyjny jak oficjalne pismo: nadawczyni po lewej, data po prawej, adresat po prawej, treść,
    „Z poważaniem” z podpisem, klauzula RODO na dole strony."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    FR, FB, FI, FL = fonts()
    o = f["osoba"]
    today = today or dt.date.today()
    ink, soft = HexColor(INK), HexColor("#555555")
    st = lambda **kw: ParagraphStyle("s", **kw)
    W_ = A4[0] - 124 - 12                                                # szerokość ramki (bez wewnętrznych marginesów)
    city = (o.get("miasto") or "Kraków").split(",")[0].strip() or "Kraków"
    me = [f'<font name="{FB}">{escape(R.full_name(f))}</font>', escape(city)]
    me += [escape(x) for x in (o.get("email", ""), R.format_phone(o.get("telefon", ""))) if x]
    left = Paragraph("<br/>".join(me), st(fontName=FR, fontSize=10, leading=14.5, textColor=ink))
    right = Paragraph(escape(f"{city}, {polish_date(today)}"), st(fontName=FR, fontSize=10, leading=14.5, textColor=ink, alignment=TA_RIGHT))
    head = Table([[left, right]], colWidths=[W_ * 0.6, W_ * 0.4])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story = [head, Spacer(1, 30)]
    to = [f'<font name="{FB}">{escape(firma)}</font>'] if firma else []
    to += [escape(x.strip()) for x in re.split(r",\s*(?=\d{2}-\d{3}|\D)", adres_firmy or "") if x.strip()][:3]
    if to:
        box = Paragraph("<br/>".join(to), st(fontName=FR, fontSize=10, leading=14.5, textColor=ink))
        t = Table([["", box]], colWidths=[W_ * 0.55, W_ * 0.45])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story += [t, Spacer(1, 28)]
    if stanowisko:
        story += [Paragraph(f'<font name="{FB}">Dotyczy:</font> {escape("aplikacji na stanowisko " + stanowisko)}',
                            st(fontName=FR, fontSize=10, leading=14, textColor=ink)), Spacer(1, 16)]
    body_text = text.strip()
    closing = ""
    m = re.search(r"(?is)\n\s*(z poważaniem|z wyrazami szacunku)\s*,?\s*\n.*$", body_text)
    if m:
        closing, body_text = m.group(1).strip().capitalize(), body_text[:m.start()].strip()
    body = st(fontName=FR, fontSize=10.5, leading=16, textColor=ink, spaceAfter=10, alignment=TA_LEFT)
    paras = [x.strip() for x in re.split(r"\n\s*\n", body_text) if x.strip()]
    for i, para in enumerate(paras):
        style = st(fontName=FR, fontSize=10.5, leading=16, textColor=ink, spaceAfter=12, alignment=TA_LEFT) if i == 0 and len(para) < 40 else body
        story.append(Paragraph(escape(para).replace("\n", "<br/>"), style))
    sign = [Spacer(1, 14), Paragraph(escape(closing or "Z poważaniem"), st(fontName=FR, fontSize=10.5, leading=15, textColor=ink, alignment=TA_RIGHT))]
    if podpis and Path(podpis).exists():
        with contextlib.suppress(Exception):
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(str(podpis)).getSize()
            h = 38.0
            img = Image(str(podpis), width=h * iw / ih, height=h)
            img.hAlign = "RIGHT"
            sign += [Spacer(1, 4), img]
    sign += [Spacer(1, 2 if podpis and Path(podpis).exists() else 22),
             Paragraph(escape(R.full_name(f)), st(fontName=FR, fontSize=10.5, leading=15, textColor=ink, alignment=TA_RIGHT))]
    story.append(KeepTogether(sign))
    note = rodo or f.get("rodo") or R.RODO

    def footer(canvas_, doc):
        p = Paragraph(f'<font name="{FB}">Klauzula RODO</font><br/>' + escape(note), st(fontName=FI, fontSize=6.6, leading=8.4, textColor=soft))
        _, h = p.wrap(W_, 200)
        p.drawOn(canvas_, 68, 30)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=62, rightMargin=62, topMargin=56, bottomMargin=100,
                            title=f"List motywacyjny — {R.full_name(f)}", author=R.full_name(f))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out_path


def clean_reason(text, requirement=""):
    """Wyjaśnienie dopasowania po ludzku: bez powtórzonego wymagania, bez „FAKTY potwierdzają”, cudzysłowów i „kandydatki”."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    head, sep, rest = t.partition(";")
    rw = {w[:5] for w in re.findall(r"[a-z]{4,}", R.plain(requirement))}
    hw = [w[:5] for w in re.findall(r"[a-z]{4,}", R.plain(head))]
    if sep and rest.strip() and (re.search(r"(?i)wymagan|kluczow", head) or (hw and sum(w in rw for w in hw) >= len(hw) / 2)):
        t = rest.strip()                                     # „Wymagany pakiet MS Office; …” → bez powtórzenia wymagania
    t = re.sub(r"(?i)\b(fakty|w faktach|baza faktów)\b\s*(potwierdzaj\w*|zawieraj\w*|wskazuj\w*|podaj\w*|mówi\w*)?\s*(to)?\s*(stanowisk\w*)?\s*:?\s*", "", t)
    t = re.sub(r"(?i)\bw sekcji [A-ZŁŚŻŹĆĄĘÓŃ]+\b", "", t)
    t = re.sub(r"(?i)\bkandydatka\s+(wskazuje|ma|posiada|podaje)\b", "masz", t)
    t = re.sub(r"(?i)\bkandydatk\w*\b", "Ty", t)
    t = re.sub(r"['\"„”‘’]", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ;:,.")
    return (t[:1].upper() + t[1:] + ".") if t else ""


def match_report(ctx, f, app, wymagania):
    """Co z wymagań oferty kandydatka ma, a czego nie — na podstawie faktów. [{wymaganie, ocena: mam|czesciowo|brak, dlaczego}]"""
    offer = R.plain(app.get("tresc") or "")
    reqs = []
    for x in (wymagania or []):
        x = re.sub(r"\s+", " ", str(x)).strip(" •-–")
        words = [w for w in re.findall(r"[a-z]{4,}", R.plain(x))]
        if x and (not offer or not words or sum(w[:5] in offer for w in words) >= max(1, len(words) // 2)):
            reqs.append(x)                                   # wymaganie musi być z ogłoszenia, nie przekręcone przez model
    reqs = reqs[:14]
    if not reqs:
        return []
    listing = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(reqs))
    prompt = f"""Pomagasz Adze ocenić, na ile spełnia wymagania z ogłoszenia o pracę. Porównaj WYMAGANIA z FAKTAMI o niej.
„mam” — tylko gdy FAKTY wprost to potwierdzają; „czesciowo” — gdy jest coś pokrewnego; „brak” — gdy FAKTY nic o tym nie mówią.

Pole „dlaczego”: jedno krótkie, naturalne zdanie do Agi, w drugiej osobie, najwyżej 14 słów.
Nie powtarzaj wymagania, nie pisz „FAKTY”, „kandydatka”, „w sekcji”, bez cudzysłowów.
Dobre przykłady: „Angielski masz na poziomie zaawansowanym.” · „Prowadziłaś dokumentację medyczną w ZZOZ.” ·
„Word i Excel znasz bardzo dobrze.” · „Znasz podstawy z kursu PARP, ale bez praktyki.” · „Nie pracowałaś przy przetargach.”

WYMAGANIA:
{listing}

FAKTY:
{R.facts_brief(f, ids=False)}

Zwróć JSON {{"dopasowanie": [{{"nr": 1, "ocena": "mam|czesciowo|brak", "dlaczego": "..."}}]}}"""
    out = None
    with contextlib.suppress(Exception):
        out = write(ctx, prompt, max_tokens=900, temperature=0.1)
    rows = (out or {}).get("dopasowanie") if isinstance(out, dict) else None
    res = []
    for r in rows if isinstance(rows, list) else []:
        with contextlib.suppress(Exception):
            n = int(r.get("nr")) - 1
            grade = R.plain(str(r.get("ocena") or ""))
            grade = "mam" if grade.startswith("mam") else "czesciowo" if grade.startswith("czesc") else "brak" if grade.startswith("brak") else ""
            if 0 <= n < len(reqs) and grade and all(x["wymaganie"] != reqs[n] for x in res):
                res.append({"wymaganie": reqs[n], "ocena": grade, "dlaczego": clean_reason(r.get("dlaczego"), reqs[n])[:200]})
    return res


# ================================================================ list i mail (model) + wersja awaryjna bez modelu

def subject(f, app):
    if app["zrodlo"] == "spontaniczna" or not app["stanowisko"]:
        return f"Zapytanie o możliwość współpracy – {R.full_name(f)}"
    return f"Aplikacja na stanowisko {app['stanowisko']} – {R.full_name(f)}"


def signature(f):
    o = f["osoba"]
    return "Z poważaniem\n" + R.full_name(f) + (f"\ntel. {R.format_phone(o['telefon'])}" if o.get("telefon") else "")


# ---------------------------------------------------------------- model do pisania (polski) i kontrola języka

_WRITER = {"at": 0.0, "name": None}


def writer_model(ctx):
    """Model do listów: ustawienie „model_pisania” albo (auto) zainstalowany Bielik — polski model, pisze dużo lepiej po polsku."""
    import time
    want = str(ctx.settings().get("model_pisania") or "auto").strip()
    if want.lower() in ("", "glowny", "główny", "sebastian"):
        return None
    if time.time() - _WRITER["at"] < 600:
        return _WRITER["name"]
    name = None
    with contextlib.suppress(Exception):
        import requests
        tags = [m["name"] for m in requests.get("http://127.0.0.1:11434/api/tags", timeout=3).json().get("models", [])]
        if want.lower() == "auto":
            name = next((t for t in tags if "bielik" in t.lower()), None)
        else:
            name = want if want in tags or any(t.startswith(want + ":") for t in tags) else None
    _WRITER.update(at=time.time(), name=name)
    return name


def write(ctx, prompt, max_tokens=1100, temperature=0.4):
    """Zapytanie o tekst (JSON): najpierw Gemini (gdy włączone i dostępne), potem Bielik, na końcu główny model Sebastiana."""
    from . import gemini as GM
    got = GM.ask_json(ctx, prompt, max_tokens=max_tokens, temperature=temperature)
    if isinstance(got, dict):
        return got
    m = writer_model(ctx)
    if m:
        with contextlib.suppress(Exception):
            import requests
            r = requests.post("http://127.0.0.1:11434/api/chat", timeout=600, json={
                "model": m, "stream": False, "keep_alive": "20m", "format": "json", "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": temperature, "num_ctx": 12288, "num_predict": max_tokens, "repeat_penalty": 1.1}})
            if r.ok:
                raw = r.json()["message"]["content"]
                with contextlib.suppress(ValueError):
                    return json.loads(raw)
                hit = re.search(r"\{.*\}", raw, re.S)
                if hit:
                    with contextlib.suppress(ValueError):
                        return json.loads(hit.group(0))
    return ctx.ask(prompt, as_json=True, max_tokens=max_tokens, temperature=temperature)


NOT_VERBS = {"działem", "udziałem", "oddziałem", "wydziałem", "podziałem", "przydziałem", "materiałem", "kanałem", "zapałem",
             "ciałem", "personelem", "aniołem", "kościołem", "stołem", "popiołem", "dołem", "orłem", "węgłem", "szczegółem",
             "zespołem", "przemysłem", "pomysłem", "zmysłem", "upadłem", "sensem", "celem", "modelem", "hotelem", "szpitalem",
             "portalem", "kapitałem", "potencjałem", "rozdziałem", "sygnałem", "arsenałem", "tunelem", "panelem", "kanałem",
             "przedziałem", "ideałem", "finałem", "lokalem", "regałem", "posiłkiem", "plenerem", "kołem", "mułem", "postulatem"}
MASC_ADJ = r"(?:gotowy|zainteresowany|zmotywowany|przekonany|pewny|zadowolony|zdeterminowany|otwarty|przygotowany|chętny|świadomy|" \
           r"doświadczony|zaangażowany|wdzięczny|skłonny|zdolny|dyspozycyjny|samodzielny|odpowiedzialny|komunikatywny|sumienny)"
OVERCLAIM = [r"bez (zbędnej |dodatkowej |długiej )?nauki", r"bez (żadnego )?wdrożeni", r"od pierwszego dnia", r"eksper(t|tka) w", r"perfekcyjn",
             r"bezbłędn", r"potrafi(łabym|łbym) szybko przejść", r"list polecaj"]


SECOND_PERSON = r"\b[a-ząćęłńóśźż]{3,}łaś\b|\b(twoj\w*|twoim|twoich|tobie|ciebie|ciebi\w*)\b|\b(będziesz|możesz|jesteś|pomożesz|wykażesz|dołączysz)\b"
EMPLOYER_VOICE = r"\b(szukamy|poszukujemy|oferujemy|zapewniamy|zapraszamy|dołącz do nas|nasz(ego|ym|a|ej)? (zesp|firm|dział))\w*"
FIRST_PERSON = (r"\b[a-ząćęłńóśźż]{2,}(łam|łabym)\b|\b(jestem|mam|chciałabym|chcę|pracuję|potrafię|prowadzę|zajmuję się|znam|mogę|opowiem|"
                r"zgłaszam|przesyłam|cenię|umiem|wiem|moich|moje|mój|moja|mnie)\b")


def language_issues(text, names=()):
    """Błędy, których list Agi mieć nie może: list pisany DO niej albo głosem pracodawcy, formy męskie, przesadne obietnice,
    powtórzenia, niedokończone zdania."""
    out = []
    body = re.sub(r"(?is)\n\s*(z poważaniem|z wyrazami szacunku).*$", "", text)       # podpis z imieniem nie jest błędem
    low = body.lower()
    hits = sorted({m.group(0) for m in re.finditer(SECOND_PERSON, low)})
    if hits:
        out.append(f"List zwraca się do kandydatki zamiast być napisany przez nią („{'”, „'.join(hits[:3])}”).")
    hits = sorted({m.group(0) for m in re.finditer(EMPLOYER_VOICE, low)})
    if hits:
        out.append(f"List brzmi jak ogłoszenie pracodawcy („{'”, „'.join(hits[:3])}”).")
    for n in [x for x in names if x and len(x) > 2]:
        if re.search(rf"\b{re.escape(n.lower()[:5])}\w*", low):
            out.append(f"W treści listu pada imię lub nazwisko kandydatki („{n}”) — list pisze ona sama.")
            break
    if len(re.findall(FIRST_PERSON, low)) < 3:
        out.append("List nie jest napisany w pierwszej osobie (jak „pracowałam”, „przygotowywałam”).")
    for w in dict.fromkeys(re.findall(r"\b[a-ząćęłńóśźż]{2,}(?:łbym|łem)\b", low)):
        if w not in NOT_VERBS:
            out.append(f"Forma męska „{w}” — list pisze kobieta.")
    for m in re.finditer(rf"\b(jestem|będę|byłbym|czuję się|pozostaję|zostałem)\s+(bardzo\s+)?{MASC_ADJ}\b", low):
        out.append(f"Forma męska „{m.group(0)}”.")
    for pat in OVERCLAIM:
        m = re.search(pat, low)
        if m:
            out.append(f"Przesadne albo niezgodne sformułowanie „{m.group(0)}”.")
    sentences = [x.strip().lower() for x in re.split(r"(?<=[.!?])\s+", body) if len(x.strip()) > 25]
    if len(sentences) != len(set(sentences)):
        out.append("To samo zdanie powtarza się dwa razy.")
    if re.search(r"\b(dostaję się|dostaje się|aplikacja na stanowisko\s*\.)", low):
        out.append("Zdanie bez sensu („dostaję się…”).")
    if re.search(r"[a-ząćęłńóśźż]{3,}\s*$", body.strip()) and not body.strip().endswith((".", "!", "?")):
        out.append("Tekst kończy się w pół zdania.")
    return list(dict.fromkeys(out))


def proofread(ctx, f, app, text):
    """Korekta językowa przez model: tylko poprawki, bez nowych treści. Zwraca tekst poprawiony albo oryginał."""
    prompt = f"""Jesteś korektorką tekstów po polsku. Autorką tekstu jest kobieta (pisze o sobie w formach żeńskich).
Popraw WYŁĄCZNIE: błędy gramatyczne i odmianę, interpunkcję, literówki, niezręczne powtórzenia i formy męskie (na żeńskie).
Nie dodawaj żadnych nowych informacji, liczb ani obietnic. Nie usuwaj faktów. Zachowaj akapity (pusta linia między nimi).

TEKST:
{text}

Zwróć JSON {{"tekst": "poprawiony tekst"}}"""
    with contextlib.suppress(Exception):
        out = write(ctx, prompt, max_tokens=1200, temperature=0.0)
        fixed = str((out or {}).get("tekst") or "").strip()
        if fixed and 0.8 <= len(fixed) / max(1, len(text)) <= 1.25 and len(rule_check(f, app, fixed)) <= len(rule_check(f, app, text)):
            return fixed
    return text


def ranked_jobs(f, sel, app=None):
    """Stanowiska od najważniejszego dla oferty: kolejność od modelu, a bez niej — wspólne słowa z ogłoszeniem."""
    sel = clean_selection(f, sel)
    order = sel.get("ranking") or sel["kolejnosc"]
    if sel.get("z_modelu") or not app:
        return order
    words = {w for w in re.findall(r"[a-z]{5,}", R.plain(f"{app.get('stanowisko', '')} {app.get('tresc', '')}"))}
    by_id = {j["id"]: j for j in f["doswiadczenie"]}

    def score(jid):
        j = by_id[jid]
        text = R.plain(" ".join([j["stanowisko"]] + [p["tekst"] for p in j["punkty"]]))
        return sum(1 for w in set(re.findall(r"[a-z]{5,}", text)) if any(w[:6] == x[:6] for x in words))
    return sorted(order, key=lambda x: -score(x))


def best_job_points(f, sel, n=2, app=None):
    """Najlepiej pasujące stanowisko i jego najważniejsze punkty (do maila)."""
    sel = clean_selection(f, sel)
    by_id = {j["id"]: j for j in f["doswiadczenie"]}
    for jid in ranked_jobs(f, sel, app):
        j = by_id[jid]
        _, pts = cv_content(f, dict(sel, kolejnosc=[jid] + [x for x in sel["kolejnosc"] if x != jid]))
        if pts.get(jid):
            return j, pts[jid][:n]
    return None, []


def enumerate_pl(items):
    """„A oraz B” albo „A; B; C” (gdy punkty same mają przecinki, średnik czyta się czytelniej)."""
    items = [x for x in items if x]
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} oraz {items[1]}"
    return "; ".join(items[:-1]) + "; " + items[-1]


def mail_text(f, app, sel=None):
    """Mail z aplikacją: krótki, zawsze poprawny — składany z faktów, bez modelu."""
    spont = app.get("zrodlo") == "spontaniczna" or not app.get("stanowisko")
    job = app.get("stanowisko") or ""
    if spont:
        first = "zwracam się z pytaniem o możliwość współpracy. W załączniku przesyłam CV oraz list motywacyjny."
    elif app.get("z_sieci"):
        first = (f"w nawiązaniu do ogłoszenia Państwa firmy na stanowisko {job}" + (f" ({app['url']})" if app.get("url") else "")
                 + " przesyłam w załączniku CV oraz list motywacyjny.")
    else:
        first = f"w odpowiedzi na ogłoszenie na stanowisko {job} przesyłam w załączniku CV oraz list motywacyjny."
    j, pts = best_job_points(f, sel, app=app)
    why = ""
    if j and pts:
        place = f" ({j['firma']})" if j.get("firma") else ""
        prose = [re.sub(r"\s*;\s*", ", ", p).rstrip(". ") for p in pts]
        why = (f"Najbliższe tej roli jest moje doświadczenie na stanowisku {j['stanowisko']}{place}. "
               f"Do moich zadań należały tam m.in. {enumerate_pl(prose)}.")
    avail = (f["warunki"].get("dostepnosc") or "").strip().rstrip(".")
    start = "" if not avail else (f"Pracę mogę rozpocząć {avail}." if avail.lower().startswith(("od ", "po ", "w ", "z ", "za ", "natychmiast", "od razu"))
                                  else f"Dostępność: {avail}.")
    body = "\n\n".join(x for x in (first, why, start, "Będę wdzięczna za informację zwrotną i chętnie odpowiem na pytania podczas rozmowy.") if x)
    return "Dzień dobry,\n\n" + body + "\n\n" + signature(f)


STYLE_EXAMPLES = """--- wzór 1 (oferta biurowa) ---
Ogłoszenie na stanowisko specjalistki ds. administracji od razu zwróciło moją uwagę, bo opisuje dokładnie tę pracę, w której
czuję się najpewniej: porządek w dokumentach, pilnowanie terminów i wsparcie zespołu w codziennej organizacji.

W szpitalu prowadziłam dokumentację medyczną, średnio około 80 historii choroby miesięcznie, równolegle w systemie i w wersji
papierowej. Zanim teczka trafiła dalej, sprawdzałam, czy niczego w niej nie brakuje, bo od tego zależały rozliczenia świadczeń.
Później przygotowałam ponad 100 spersonalizowanych planów finansowych. Ta praca nauczyła mnie dyskrecji przy danych poufnych
i prowadzenia wielu spraw jednocześnie bez gubienia szczegółów.

Dobrze odnajduję się też w koordynacji. W ciągu trzech miesięcy współorganizowałam 10 transmisji na żywo i 8 wywiadów:
ustalałam terminy, byłam w kontakcie z gośćmi, przygotowywałam materiały i pilnowałam, żeby nic nie zostało bez odpowiedzi.

Chętnie opowiem, jak mogłabym odciążyć Państwa zespół. Będę wdzięczna za możliwość rozmowy.
--- wzór 2 (bez ogłoszenia) ---
piszę z pytaniem, czy w Państwa biurze przydałaby się osoba, która weźmie na siebie dokumentację i codzienną organizację pracy.
Nie znalazłam aktualnego ogłoszenia, ale profil Państwa działalności bardzo dobrze pasuje do tego, czym zajmuję się na co dzień.

Mam za sobą pracę z dokumentacją medyczną, przygotowywanie planów i zestawień oraz koordynowanie spotkań i wydarzeń.
Lubię, gdy wszystko jest na swoim miejscu, a terminy są dotrzymane, i potrafię o to zadbać bez przypominania.

Jeśli taka pomoc byłaby dla Państwa wartościowa, chętnie się spotkam i opowiem więcej."""


def fallback_texts(f, app, sel=None):
    """List bez modelu: z punktów najlepiej pasujących stanowisk (konkrety z bazy faktów)."""
    spont = app["zrodlo"] == "spontaniczna" or not app["stanowisko"]
    where = f" w firmie {app['firma']}" if app["firma"] else ""
    if spont:
        opening = (f"zwracam się z pytaniem, czy{where} znalazłoby się miejsce dla osoby do wsparcia administracyjnego "
                   "i organizacyjnego. Nie odpowiadam na konkretne ogłoszenie, dlatego krótko się przedstawię.")
    else:
        opening = f"z zainteresowaniem przeczytałam Państwa ogłoszenie na stanowisko {app['stanowisko']} i chciałabym zgłosić swoją kandydaturę."
    sel = clean_selection(f, sel)
    by_id = {j["id"]: j for j in f["doswiadczenie"]}
    _, pts = cv_content(f, sel)
    paras = []
    for jid in ranked_jobs(f, sel, app)[:2]:
        if jid in pts and pts[jid]:
            j = by_id[jid]
            paras.append(f"Na stanowisku {j['stanowisko']}" + (f" ({j['firma']})" if j.get("firma") else "")
                         + " do moich zadań należały m.in. " + enumerate_pl([re.sub(r"\s*;\s*", ", ", p).rstrip(". ") for p in pts[jid]]) + ".")
    avail = f["warunki"].get("dostepnosc", "")
    letter = (f"Szanowni Państwo,\n\n{opening}\n\n" + "\n\n".join(paras or [" ".join(p["tekst"] for p in f["profil"][:3])])
              + "\n\n" + (f"Pracę mogę rozpocząć {avail}. " if avail.lower().startswith(("od ", "po ", "w ", "z ", "za ")) else (f"Dostępność: {avail}. " if avail else ""))
              + "Chętnie opowiem więcej podczas rozmowy.\n\n" + signature(f))
    return letter, mail_text(f, app, sel)


def tidy(text, f):
    text = re.sub(r"[ \t]*[—–][ \t]*", ", ", str(text or "")).replace(" ,", ",")
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r", "")).strip()
    text = re.sub(r"(?is)\n*(z poważaniem|z wyrazami szacunku|pozdrawiam serdecznie|pozdrawiam)[\s,]*.*$", "", text).strip()
    text = re.sub(r"(?i)list(u|em|owi)?\s+(polecając|przewodni)\w*", lambda m: "list" + (m.group(1) or "") + " motywacyjn" +
                  {"": "y", "u": "ego", "em": "ym", "owi": "emu"}[(m.group(1) or "").lower()], text)
    if not re.match(r"(?i)szanown", text):
        text = "Szanowni Państwo,\n\n" + text
    return text + "\n\n" + signature(f)


def compose(ctx, f, app, sel=None):
    """(list, mail, czy_model) — list pisany przez model wyłącznie z faktów, sprawdzony i poprawiony językowo; mail z szablonu.
    Gdy list nie przejdzie kontroli po dwóch próbach — wersja z faktów bez modelu."""
    spont = app["zrodlo"] == "spontaniczna" or not app["stanowisko"]
    base = f"""Jesteś kandydatką do pracy i piszesz SWÓJ list motywacyjny do pracodawcy. Piszesz o sobie w pierwszej osobie,
w formach żeńskich: „pracowałam”, „przygotowywałam”, „jestem gotowa”, „chciałabym”. Adresatem jest pracodawca (zwracasz się
do niego „Państwo”). NIE piszesz do kandydatki i nie piszesz jak pracodawca: żadnego „Ty”, „Twoje”, „przygotowywałaś”,
„szukamy”, „oferujemy”, żadnego zwracania się do kandydatki po imieniu. Poprawna polszczyzna.

ŻELAZNA ZASADA: o kandydatce wolno napisać WYŁĄCZNIE to, co jest w FAKTACH. Żadnych nowych umiejętności, narzędzi,
lat doświadczenia, liczb, certyfikatów ani stanowisk. Nie obiecuj, że nie potrzebuje wdrożenia ani nauki. Jeśli oferta
wymaga czegoś, czego nie ma w FAKTACH, pomiń to. Nie podawaj oczekiwań finansowych.

STYL: naturalnie, ciepło i profesjonalnie; pewnie, ale bez zadęcia; po partnersku, nie służalczo. Bez rekrutacyjnych
frazesów („dynamiczny zespół”, „z pasją”, „wychodząc naprzeciw”), bez myślników i wypunktowań, zdania różnej długości.
Doświadczenie sprzedażowe i w obsłudze klienta pokazuj jako atut, gdy oferta dotyczy sprzedaży lub obsługi klienta; w ofertach biurowych
jako źródło umiejętności organizacyjnych i komunikacyjnych.

{'To aplikacja SPONTANICZNA: firma nie ogłosiła naboru. Zapytaj uprzejmie o możliwość współpracy przy administracji, dokumentacji lub koordynacji.' if spont else 'To odpowiedź na ogłoszenie.'}
FIRMA: {app['firma'] or '(nieznana — pisz bez nazwy)'}
STANOWISKO: {app['stanowisko'] or '(brak)'}
OGŁOSZENIE / OPIS FIRMY:
{(app['tresc'] or '(brak treści)')[:4000]}

FAKTY O KANDYDATCE:
{R.facts_brief(f, ids=False)}

Zwróć JSON {{"list": "..."}}:
- "list": 170–240 słów, BEZ nagłówka „Szanowni Państwo”, BEZ podpisu i BEZ „Z poważaniem” (dodam je sama); 3–4 akapity
  oddzielone pustą linią. Pierwszy akapit: o jakie stanowisko chodzi i dlaczego ta rola. Środkowe: 2–3 konkretne wymagania
  z ogłoszenia, na które FAKTY dają pokrycie — każde poparte tym, co kandydatka faktycznie robiła (czynność, miejsce, efekt).
  Jeśli FAKTY podają liczby (np. „ok. 80 historii choroby miesięcznie”, liczba wydarzeń, osób, dokumentów), użyj 2–3 najlepiej
  pasujących do oferty, dokładnie w tym brzmieniu. Liczb spoza FAKTÓW nie wolno podawać ani szacować.
  Ostatni akapit: gotowość do rozmowy.

JAK MA BRZMIEĆ (wskazówki samej kandydatki): naturalnie, ciepło, ale profesjonalnie; pewnie, ale bez arogancji; z zaangażowaniem,
ale bez desperacji; po partnersku, nie służalczo. Bez rekrutacyjnych frazesów, korporacyjnych wypełniaczy, myślników
i wygładzonego, mechanicznego stylu. Zdania różnej długości. Zmianę pracy przedstawiaj jako świadomą decyzję, nie ucieczkę.

WZORY TONU (to inne oferty — NIE kopiuj zdań, tylko sposób pisania; fakty bierz wyłącznie z FAKTÓW i dopasuj do TEJ oferty):
{STYLE_EXAMPLES}"""
    fb_letter, fb_mail = fallback_texts(f, app, sel)
    mail = mail_text(f, app, sel)
    feedback = ""
    for attempt in range(2):
        try:
            out = write(ctx, base + feedback, max_tokens=1100, temperature=0.5 if attempt == 0 else 0.3)
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: list bez modelu ({type(e).__name__})")
            out = None
        body = str((out or {}).get("list") or "").strip() if isinstance(out, dict) else ""
        if len(body.split()) < 60:
            feedback = "\n\nPOPRZEDNIA WERSJA BYŁA ZA KRÓTKA. Napisz pełny list (170–240 słów)."
            continue
        letter = tidy(body, f)
        names = (f["osoba"].get("imie", ""), f["osoba"].get("nazwisko", ""))
        if any(x.startswith("List zwraca się") or x.startswith("List brzmi") or "imię lub nazwisko" in x or "pierwszej osobie" in x
               for x in language_issues(letter, names)):
            feedback = ("\n\nPOPRZEDNIA WERSJA BYŁA NAPISANA DO KANDYDATKI albo głosem pracodawcy. To ma być list OD niej: "
                        "pisz „ja” w pierwszej osobie (np. „Przez dwa lata prowadziłam dokumentację…”), nie używaj „Ty”, „Twoje”, "
                        "„przygotowywałaś”, nie pisz „szukamy”, nie zwracaj się do niej po imieniu.")
            continue                                                   # takiego tekstu się nie poprawia — piszę od nowa
        if language_issues(letter, names):
            letter = tidy(proofread(ctx, f, app, letter.rsplit("\n\nZ poważaniem", 1)[0]), f)
        problems = language_issues(letter, names) + rule_check(f, app, letter)
        if not problems:
            return letter, mail, True
        feedback = "\n\nPOPRAW TE BŁĘDY Z POPRZEDNIEJ WERSJI (nie powtarzaj ich):\n- " + "\n- ".join(problems[:6])
    return fb_letter, mail, False


# ================================================================ kontroler prawdy

KNOWN_TOOLS = ["excel", "word", "powerpoint", "outlook", "teams", "sap", "jira", "confluence", "photoshop", "illustrator",
               "indesign", "canva", "wordpress", "salesforce", "hubspot", "trello", "asana", "notion", "slack", "sql", "python",
               "power bi", "tableau", "autocad", "symfonia", "optima", "enova", "subiekt", "płatnik", "platnik", "google analytics",
               "google ads", "meta ads", "figma", "ms project", "sharepoint", "visio", "access", "crm", "erp", "livespace", "pipedrive"]
KNOWN_LANGS = ["niemiecki", "francuski", "hiszpański", "włoski", "rosyjski", "ukraiński", "czeski", "japoński", "chiński",
               "angielski", "norweski", "szwedzki", "niderlandzki", "portugalski"]
RISKY = [(r"\bcertyfikat\w*", "certyfikat"), (r"\bstudi\w+ podyplomow\w+", "studia podyplomowe"), (r"\bdoktor\w*", "doktorat"),
         (r"\bprawo jazdy", "prawo jazdy"), (r"\bksięgowo\w*", "księgowość"), (r"\bkadr\w* i płac\w*", "kadry i płace"),
         (r"\bbiegł\w+ znajomoś\w+", "„biegła znajomość”"), (r"\bwieloletni\w+", "„wieloletnie”")]


def rule_check(f, app, text):
    """Twarde reguły: liczby, narzędzia, języki i ryzykowne określenia muszą mieć pokrycie w bazie faktów."""
    facts = R.plain(R.facts_brief(f, ids=False))
    offer = R.plain(app["tresc"] or "") + " " + R.plain(app["firma"] or "") + " " + R.plain(app["stanowisko"] or "")
    low = R.plain(text)
    out = []
    body = re.sub(r"(?s)z powazaniem.*$", "", low)
    body = re.sub(r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+", " ", body)          # linki i adresy to nie twierdzenia o kandydatce
    for num in dict.fromkeys(re.findall(r"\b\d[\d.,]*\d|\b\d\b", body)):
        seen = lambda hay: re.search(rf"(?<!\d){re.escape(num)}(?!\d)", hay)
        if not seen(facts) and not seen(offer):
            out.append(f"Liczba „{num}” nie występuje w bazie faktów ani w ogłoszeniu.")
    for m in dict.fromkeys(re.findall(r"\b(dwu|trzy|cztero|piecio|szescio|kilku|kilkunasto|wielo)letni\w*|\b(dwa|trzy|cztery|piec|szesc|kilka|kilkanascie) lata?\b|\blat doswiadczenia", body)):
        out.append("W tekście pada określenie długości doświadczenia — sprawdź, czy zgadza się z CV.")
        break
    for tool in KNOWN_TOOLS:
        if re.search(rf"(?<![a-z]){re.escape(R.plain(tool))}(?![a-z])", body) and R.plain(tool) not in facts:
            out.append(f"Narzędzie „{tool}” nie jest wpisane w bazie faktów.")
    for lang in KNOWN_LANGS:
        stem = R.plain(lang)[:-1]
        if re.search(rf"\b{stem}\w*", body) and stem not in facts:
            out.append(f"Język „{lang}” nie jest wpisany w bazie faktów.")
    for pattern, label in RISKY:
        if re.search(R.plain(pattern), body) and not re.search(R.plain(pattern), facts):
            out.append(f"Określenie {label} nie ma pokrycia w bazie faktów.")
    if re.search(r"\[[^\]]{0,40}\]|\{[^}]{0,40}\}|xxx|lorem", low):
        out.append("W tekście został niewypełniony fragment (nawias albo znacznik).")
    firma = R.norm(app["firma"] or "")
    if firma and len(firma) > 3 and firma.split()[0] not in R.norm(text) and app["zrodlo"] != "spontaniczna":
        pass                                                           # brak nazwy firmy to nie nieprawda — nie zgłaszamy
    return list(dict.fromkeys(out))


def model_check(ctx, f, app, letter, mail):
    prompt = f"""Jesteś kontrolerem prawdy. Porównaj TEKST z FAKTAMI o kandydatce.
Wypisz tylko te twierdzenia o kandydatce (doświadczenie, umiejętności, narzędzia, liczby, wykształcenie, uprawnienia),
których FAKTY NIE potwierdzają. Ogólne deklaracje (chęć rozmowy, zainteresowanie firmą, uprzejmości) pomijaj.
Informacje o firmie wzięte z OGŁOSZENIA nie są błędem.

FAKTY:
{R.facts_brief(f, ids=False)}

OGŁOSZENIE (skrót): {(app['tresc'] or '')[:1500]}

TEKST:
{letter}

{mail}

Zwróć JSON {{"niepotwierdzone": ["krótki cytat i czego brakuje w faktach", ...]}} — pusta lista, gdy wszystko ma pokrycie."""
    out = None
    with contextlib.suppress(Exception):
        out = ctx.ask(prompt, as_json=True, max_tokens=500, temperature=0.0)
    if not isinstance(out, dict) or not isinstance(out.get("niepotwierdzone"), list):
        return ["Do sprawdzenia: kontrola prawdy przez model nie odpowiedziała — przeczytaj list i mail przed wysłaniem."]
    return [f"Do sprawdzenia: {str(x)[:220]}" for x in out["niepotwierdzone"] if str(x).strip()][:6]


def check(ctx, f, app, letter, mail, by_model=True):
    notes = rule_check(f, app, letter) + rule_check(f, app, mail)
    if by_model:
        notes += model_check(ctx, f, app, letter, mail)
    return list(dict.fromkeys(notes))
