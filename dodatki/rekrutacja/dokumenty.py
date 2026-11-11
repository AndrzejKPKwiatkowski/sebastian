"""Rekrutacja — dokumenty: CV, list przewodni, mail i kontroler prawdy.

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

def default_selection(f):
    return {"kolejnosc": [j["id"] for j in f["doswiadczenie"]],
            "punkty": {j["id"]: [p["id"] for p in j["punkty"]] for j in f["doswiadczenie"]},
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
    order = [x for x in dict.fromkeys(sel.get("kolejnosc") or []) if x in jobs]
    order += [x for x in jobs if x not in order]
    points = {}
    for j in f["doswiadczenie"]:
        ids = [p["id"] for p in j["punkty"]]
        got = [x for x in dict.fromkeys((sel.get("punkty") or {}).get(j["id"]) or []) if x in ids]
        points[j["id"]] = got + [x for x in ids if x not in got]          # kolejność od modelu, komplet z bazy
    return {"kolejnosc": order, "punkty": points,
            "profil": pick("profil", [p["id"] for p in f["profil"]], 4, 2),
            "umiejetnosci": pick("umiejetnosci", [u["id"] for u in f["umiejetnosci"]], 6, 3),
            "narzedzia": pick("narzedzia", [t["id"] for t in f["narzedzia"]], 7, 1)}


def select_for_offer(ctx, f, app):
    prompt = f"""Dobierasz, co wyeksponować w CV pod konkretną ofertę pracy. NIE piszesz żadnego tekstu.
Zwracasz wyłącznie numery faktów z listy poniżej (w nawiasach kwadratowych). Nie wymyślaj numerów.

OFERTA: {app['stanowisko']} — {app['firma']} ({app['miasto']})
{(app['tresc'] or '')[:3500]}

FAKTY:
{R.facts_brief(f)}

Zwróć JSON:
{{"kolejnosc": [numery stanowisk d… od najlepiej pasującego do oferty],
  "punkty": {{"d1": [numery punktów tego stanowiska, najważniejsze dla oferty pierwsze]}},
  "profil": [3 albo 4 numery zdań p…, w kolejności czytania],
  "umiejetnosci": [do 6 numerów u…],
  "narzedzia": [do 7 numerów n…]}}"""
    try:
        return clean_selection(f, ctx.ask(prompt, as_json=True, max_tokens=700, temperature=0.1))
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: wybór faktów bez modelu ({type(e).__name__})")
        return default_selection(f)


# ================================================================ CV (ReportLab) — układ jak w dotychczasowym CV Agi

def render_cv(f, sel, out_path, photo=None, rodo=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    sel = clean_selection(f, sel)
    data = None
    for scale in (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setTitle(f"CV — {R.full_name(f)}")
        c.setAuthor(R.full_name(f))
        fits = _draw_cv(c, f, sel, photo, rodo or f.get("rodo") or R.RODO, scale)
        c.save()
        data = buf.getvalue()
        if fits:
            break
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


def _draw_cv(c, f, sel, photo, rodo, k):
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
    profil = " ".join(p["tekst"] for p in f["profil"] if p["id"] in sel["profil"])
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
        pts = {p["id"]: p["tekst"] for p in j["punkty"]}
        place = ", ".join(x for x in (j.get("firma", ""), j.get("miejsce", "")) if x)
        items = [(_para(f"<b>{escape(j['stanowisko'])}</b>", FB, body), 0)]
        if place:
            items.append((_para(f"<b>{escape(place)}</b>", FB, body), 1))
        items.append((_para(escape(f"{j.get('od', '')} - {j.get('do', '')}"), FR, body * 0.94), 2.5))
        items += [(_para(escape(pts[pid]), FR, body, bullet=True), 0.6) for pid in sel["punkty"].get(jid, []) if pid in pts]
        blocks.append((items, top - _flow(c, items, 0, top, col_w, draw=False) + 9 * k))
    heights = [h for _, h in blocks]
    split = min(range(len(blocks) + 1), key=lambda i: max(sum(heights[:i]), sum(heights[i:]))) if blocks else 0
    for col, part in enumerate((blocks[:split], blocks[split:])):
        yy = top
        for items, h in part:
            _flow(c, items, x0 + col * (col_w + 14), yy, col_w)
            yy -= h
        fits = fits and yy >= floor - 9 * k

    # ---- lewa kolumna: kursy, umiejętności, narzędzia, języki, wykształcenie, kontakt
    lx, lw = 24.0, LW - 46
    contact_h = 132.0
    y = H - PH - 34

    def section(title, paragraphs, yy):
        yy = _heading(c, title, lx, yy, lw * 0.92, head)
        return _flow(c, paragraphs, lx - 2, yy - 2, lw + 2) - 21 * k

    y = section("Kursy i kwalifikacje", [(_para(escape(x["tekst"]), FL, body, bullet=True), 1.5) for x in f["kursy"]], y)
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
    return fits


# ================================================================ list przewodni (PDF)

def polish_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def render_letter(f, text, out_path, firma="", stanowisko="", today=None, rodo=None):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer
    FR, FB, FI, FL = fonts()
    o = f["osoba"]
    today = today or dt.date.today()
    ink, soft = HexColor(INK), HexColor("#6b6b6b")
    st = lambda **kw: ParagraphStyle("s", **kw)
    story = [Paragraph(escape(R.full_name(f)), st(fontName=FL, fontSize=24, leading=30, textColor=ink)),
             Paragraph(escape("  ·  ".join(x for x in (o.get("telefon", ""), o.get("email", ""), o.get("miasto", "")) if x)),
                       st(fontName=FR, fontSize=8.8, leading=13, textColor=soft)),
             Spacer(1, 7), HRFlowable(width="100%", thickness=0.7, color=ink), Spacer(1, 20),
             Paragraph(escape(f"{(o.get('miasto') or 'Kraków').split(',')[0].split()[-1]}, {polish_date(today)}"),
                       st(fontName=FR, fontSize=9.5, leading=13, textColor=soft, alignment=TA_RIGHT)), Spacer(1, 16)]
    if firma:
        story += [Paragraph(f"<b>{escape(firma)}</b>", st(fontName=FB, fontSize=10.5, leading=14, textColor=ink)), Spacer(1, 3)]
    if stanowisko:
        story += [Paragraph(escape(f"Dotyczy: rekrutacji na stanowisko {stanowisko}"), st(fontName=FR, fontSize=9.5, leading=13, textColor=soft))]
    story.append(Spacer(1, 22))
    body = st(fontName=FR, fontSize=10.3, leading=15.6, textColor=ink, spaceAfter=10)
    for para in re.split(r"\n\s*\n", text.strip()):
        story.append(Paragraph(escape(para.strip()).replace("\n", "<br/>"), body))
    note = rodo or f.get("rodo") or R.RODO

    def footer(canvas_, doc):
        p = Paragraph(escape(note), st(fontName=FI, fontSize=6.4, leading=8.2, textColor=soft))
        _, h = p.wrap(A4[0] - 124, 200)
        p.drawOn(canvas_, 62, 26)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=62, rightMargin=62, topMargin=56, bottomMargin=78,
                            title=f"List przewodni — {R.full_name(f)}", author=R.full_name(f))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out_path


# ================================================================ list i mail (model) + wersja awaryjna bez modelu

def subject(f, app):
    if app["zrodlo"] == "spontaniczna" or not app["stanowisko"]:
        return f"Zapytanie o możliwość współpracy – {R.full_name(f)}"
    return f"Aplikacja na stanowisko {app['stanowisko']} – {R.full_name(f)}"


def signature(f):
    o = f["osoba"]
    return "Z poważaniem\n" + R.full_name(f) + (f"\ntel. {o['telefon']}" if o.get("telefon") else "")


def fallback_texts(f, app):
    prof = " ".join(p["tekst"] for p in f["profil"][:3])
    where = f" w firmie {app['firma']}" if app["firma"] else ""
    if app["zrodlo"] == "spontaniczna" or not app["stanowisko"]:
        opening = (f"piszę z pytaniem, czy{where} znalazłoby się miejsce dla osoby do wsparcia administracyjnego "
                   "i organizacyjnego. Nie odpowiadam na konkretne ogłoszenie, dlatego krótko się przedstawię.")
        mail_open = "przesyłam swoje CV i list przewodni z pytaniem o możliwość współpracy."
    else:
        opening = f"z zainteresowaniem przeczytałam ogłoszenie na stanowisko {app['stanowisko']}{where} i chciałabym zgłosić swoją kandydaturę."
        mail_open = f"w odpowiedzi na ogłoszenie na stanowisko {app['stanowisko']} przesyłam swoje CV i list przewodni."
    avail = f["warunki"].get("dostepnosc", "")
    letter = (f"Szanowni Państwo,\n\n{opening}\n\n{prof}\n\n"
              + (f"Pracę mogę rozpocząć w terminie: {avail}. " if avail else "")
              + "Chętnie opowiem więcej podczas rozmowy.\n\n" + signature(f))
    mail = (f"Dzień dobry,\n\n{mail_open} Będę wdzięczna za informację zwrotną i chętnie odpowiem na dodatkowe pytania.\n\n"
            + signature(f))
    return letter, mail


def tidy(text, f):
    text = re.sub(r"[ \t]*[—–][ \t]*", ", ", str(text or "")).replace(" ,", ",")
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r", "")).strip()
    text = re.sub(r"(?is)\n*(z poważaniem|z wyrazami szacunku|pozdrawiam serdecznie|pozdrawiam)[\s,]*.*$", "", text).strip()
    return text + "\n\n" + signature(f)


def compose(ctx, f, app):
    """(list, mail) — pisane przez model wyłącznie z faktów; gdy model nie odpowie, wersja z szablonu."""
    spont = app["zrodlo"] == "spontaniczna" or not app["stanowisko"]
    prompt = f"""Piszesz w imieniu kandydatki list przewodni i krótki mail do pracodawcy. Po polsku, w formach żeńskich.

ŻELAZNA ZASADA: o kandydatce wolno napisać WYŁĄCZNIE to, co jest w FAKTACH. Żadnych nowych umiejętności, narzędzi,
lat doświadczenia, liczb, certyfikatów ani stanowisk. Jeśli oferta wymaga czegoś, czego nie ma w FAKTACH, pomiń to.
Nie podawaj oczekiwań finansowych.

STYL: naturalnie, ciepło i profesjonalnie; pewnie, ale bez zadęcia; po partnersku, nie służalczo. Bez rekrutacyjnych
frazesów („dynamiczny zespół”, „z pasją”, „wychodząc naprzeciw”), bez myślników i wypunktowań, zdania różnej długości.
Doświadczenie sprzedażowe i obsługowe przedstawiaj tylko jako źródło umiejętności organizacyjnych i komunikacyjnych.

{'To aplikacja SPONTANICZNA: firma nie ogłosiła naboru. Zapytaj uprzejmie o możliwość współpracy przy administracji, dokumentacji lub koordynacji.' if spont else 'To odpowiedź na ogłoszenie.'}
FIRMA: {app['firma'] or '(nieznana — pisz bez nazwy)'}
STANOWISKO: {app['stanowisko'] or '(brak)'}
OGŁOSZENIE / OPIS FIRMY:
{(app['tresc'] or '(brak treści)')[:4000]}

FAKTY O KANDYDATCE:
{R.facts_brief(f, ids=False)}

Zwróć JSON {{"list": "...", "mail": "..."}}:
- "list": 170–240 słów, zaczyna się od „Szanowni Państwo,”; 3–4 akapity oddzielone pustą linią; nawiązuje do 2–3 konkretnych
  wymagań z ogłoszenia, na które FAKTY dają pokrycie; kończy się zdaniem o gotowości do rozmowy. BEZ podpisu.
- "mail": 50–90 słów, zaczyna się od „Dzień dobry,”; mówi, że w załączniku jest CV i list przewodni; jedno zdanie, dlaczego
  ta rola; prośba o informację zwrotną. BEZ podpisu."""
    fb_letter, fb_mail = fallback_texts(f, app)
    try:
        out = ctx.ask(prompt, as_json=True, max_tokens=1100, temperature=0.5)
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: list bez modelu ({type(e).__name__})")
        out = None
    if not isinstance(out, dict) or len(str(out.get("list", "")).split()) < 60 or len(str(out.get("mail", "")).split()) < 15:
        return fb_letter, fb_mail, False
    return tidy(out["list"], f), tidy(out["mail"], f), True


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
