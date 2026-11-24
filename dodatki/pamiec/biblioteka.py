"""Pamięć — Biblioteka wiedzy (2.35): kursy, książki, materiały → wyszukiwarka pełnotekstowa (SQLite FTS5).

Inaczej niż „o mnie”: z biblioteki nie powstają fakty o osobie. Fragmenty są indeksowane od razu (bez modelu),
a przy rozmowie Sebastian dobiera najlepiej pasujące. Na prośbę pisze poradnik (PDF) albo wyjaśnienie
wyłącznie na podstawie tych materiałów. Gdy źródła się różnią — wygrywa nowsze (rok wydania albo data wgrania).
"""
import contextlib, datetime as dt, html, re
from pathlib import Path

from . import rdzen as R

PIECE = 1600


def schema(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(zrodla)")}
    if "cel" not in cols:
        con.execute("ALTER TABLE zrodla ADD COLUMN cel TEXT DEFAULT 'osoba'")
    if "rok" not in cols:
        con.execute("ALTER TABLE zrodla ADD COLUMN rok INTEGER DEFAULT 0")
    con.executescript("""
    CREATE VIRTUAL TABLE IF NOT EXISTS wiedza USING fts5(tekst, tytul, osoba UNINDEXED, zrodlo UNINDEXED,
        tokenize='unicode61 remove_diacritics 2');
    CREATE TABLE IF NOT EXISTS zlecenia(
        id INTEGER PRIMARY KEY AUTOINCREMENT, osoba TEXT, rodzaj TEXT, temat TEXT, status TEXT DEFAULT 'czeka',
        wynik TEXT DEFAULT '', plik TEXT DEFAULT '', kanal TEXT DEFAULT 'panel', utworzono TEXT, gotowe TEXT DEFAULT '');
    """)
    con.commit()


def guess_year(name):
    years = [int(y) for y in re.findall(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)", name or "")]
    return max(years) if years else 0


def add(con, pid, name, path="", year=0, text=None):
    """Nowe źródło biblioteki. Tekst indeksowany od razu; plik — przez pracownika w tle (index_source)."""
    year = int(year or 0) or guess_year(name)
    cur = con.execute("INSERT INTO zrodla(osoba, rodzaj, nazwa, sciezka, dodano, cel, rok) VALUES(?,?,?,?,?,?,?)",
                      (pid, "biblioteka", name[:200], str(path or ""), R.now_iso(), "biblioteka", year))
    sid = cur.lastrowid
    if text is not None:
        store(con, sid, pid, name, [text])
    con.commit()
    return sid


def pieces(texts, size=PIECE):
    out = []
    for t in texts:
        t = re.sub(r"[ \t]+", " ", R.SECRET.sub("[ukryte]", t or "")).strip()
        paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9•\-#])", t) if p.strip()]
        cur = ""
        for p in paras:
            while len(p) > size:
                cut = p.rfind(". ", 0, size)
                cut = cut + 1 if cut > size // 2 else size
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(p[:cut].strip())
                p = p[cut:].strip()
            if len(cur) + len(p) + 1 > size and cur:
                out.append(cur)
                cur = p
            else:
                cur = (cur + "\n" + p) if cur else p
        if cur:
            out.append(cur)
    return [p for p in out if len(p) >= 40]


def store(con, sid, pid, title, texts):
    parts = pieces(texts)
    con.executemany("INSERT INTO wiedza(tekst, tytul, osoba, zrodlo) VALUES(?,?,?,?)", [(p, title, pid, sid) for p in parts])
    con.execute("UPDATE zrodla SET kawalkow=?, zrobione=?, status=?, notatka=?, zakonczono=? WHERE id=?",
                (len(parts), len(parts), "gotowe" if parts else "pusty",
                 f"{len(parts)} fragmentów w bibliotece" if parts else "nie znalazłem tekstu (skan bez tekstu?)", R.now_iso(), sid))
    return len(parts)


def index_source(con, src, extract=None):
    try:
        _, docs = R.file_docs(src["sciezka"], extract)
        store(con, src["id"], src["osoba"], src["nazwa"], [t for _, texts in docs for t in texts])
    except Exception as e:
        con.execute("UPDATE zrodla SET status='blad', notatka=? WHERE id=?", (f"{type(e).__name__}: {str(e)[:200]}", src["id"]))
    con.commit()


def sources(con, pid):
    return [dict(r) for r in con.execute("SELECT * FROM zrodla WHERE osoba=? AND cel='biblioteka' ORDER BY id DESC", (pid,))]


def _match(query):
    words = [w for w in re.findall(r"\w+", R.norm(query)) if len(w) >= 3][:12]
    stop = {"jak", "czy", "jest", "sie", "dla", "albo", "oraz", "ktore", "ktory", "jaki", "jakie", "mnie", "mam", "moje", "moj",
            "poradnik", "wyjasnij", "wytlumacz", "prosze", "temat", "tego", "tym", "ten", "ta", "to", "co", "na", "od", "do", "przez"}
    terms = []
    for w in words:
        if w in stop:
            continue
        terms.append(f'"{w[:max(4, len(w) - 2)]}"*' if len(w) >= 5 else f'"{w}"*')
    return " OR ".join(dict.fromkeys(terms))


def search(con, pid, query, k=8):
    """Najlepiej pasujące fragmenty biblioteki osoby; nowsze źródła lekko wyżej."""
    q = _match(query)
    if not q:
        return []
    try:
        rows = con.execute("SELECT w.tekst, w.tytul, w.zrodlo, bm25(wiedza) AS s, z.rok, z.dodano FROM wiedza w "
                           "JOIN zrodla z ON z.id=w.zrodlo WHERE wiedza MATCH ? AND w.osoba=? AND z.status<>'nieaktualne' "
                           "ORDER BY s LIMIT 60", (q, pid)).fetchall()
    except Exception:
        return []
    now = dt.date.today().year
    out = []
    for r in rows:
        year = r["rok"] or int((r["dodano"] or "2000")[:4])
        fresh = max(0.0, 1 - (now - year) / 20)
        out.append({"tekst": r["tekst"], "tytul": r["tytul"], "zrodlo": r["zrodlo"], "rok": r["rok"],
                    "score": r["s"] - 1.5 * fresh})
    out.sort(key=lambda x: x["score"])
    return out[:k]


def context(con, pid, question, limit=2600):
    hits = search(con, pid, question, 5)
    if not hits:
        return ""
    text, n = "Z biblioteki wiedzy tej osoby (jej kursy i książki):\n", 0
    for h in hits:
        part = f"[{h['tytul']}{', ' + str(h['rok']) if h['rok'] else ''}] {h['tekst']}\n"
        if n + len(part) > limit:
            break
        text += part
        n += len(part)
    return text


# ================================================================ poradniki i wyjaśnienia

GUIDE = """Jesteś asystentem {first}. Napisz po polsku {what} na temat: „{topic}”.
Korzystaj WYŁĄCZNIE z fragmentów jej materiałów (kursy, książki) poniżej. Nie dopisuj wiedzy spoza nich — jeśli czegoś
brakuje, napisz krótko, czego materiały nie obejmują. Gdy źródła się różnią, wybierz NOWSZE (rok przy źródle) i zaznacz to.
{form}
Na końcu sekcja „Źródła” — tytuły materiałów, z których korzystasz.

FRAGMENTY:
{chunks}"""

FORMS = {
    "poradnik": ("praktyczny poradnik", "Układ: tytuł (# …), krótki wstęp, sekcje (## …) z krokami i punktami (- …), na końcu „Najważniejsze w skrócie”. "
                                        "Pisz konkretnie, jak dla osoby, która ma to zastosować. Długość: 600–1200 słów.", 2600),
    "wyjasnienie": ("jasne wyjaśnienie", "Najpierw odpowiedź w 2–3 zdaniach, potem szczegóły w kilku punktach (- …). Długość: 150–350 słów.", 900),
}


def queue(con, pid, kind, topic, channel="panel"):
    cur = con.execute("INSERT INTO zlecenia(osoba, rodzaj, temat, kanal, utworzono) VALUES(?,?,?,?,?)",
                      (pid, kind, topic.strip()[:200], channel, R.now_iso()))
    con.commit()
    return cur.lastrowid


def run_job(con, job, ask, folder):
    """ask(prompt, max_tokens) → tekst. Poradnik dostaje też PDF."""
    p = R.person(con, job["osoba"])
    first = R.first_name(p)
    con.execute("UPDATE zlecenia SET status='w_toku' WHERE id=?", (job["id"],))
    con.commit()
    hits = search(con, job["osoba"], job["temat"], 14 if job["rodzaj"] == "poradnik" else 6)
    if not hits:
        con.execute("UPDATE zlecenia SET status='gotowe', wynik=?, gotowe=? WHERE id=?",
                    (f"W Twojej bibliotece nie znalazłem niczego o „{job['temat']}”. Wgraj materiały na ten temat albo spróbuj innych słów.",
                     R.now_iso(), job["id"]))
        con.commit()
        return False
    what, form, tokens = FORMS.get(job["rodzaj"], FORMS["wyjasnienie"])
    chunks = "\n\n".join(f"[{h['tytul']}{', ' + str(h['rok']) if h['rok'] else ''}]\n{h['tekst']}" for h in hits)[:22000]
    text = ask(GUIDE.format(first=first, what=what, topic=job["temat"], form=form, chunks=chunks), tokens)
    if not text or not str(text).strip():
        con.execute("UPDATE zlecenia SET status='blad', wynik='Lokalny model nie odpowiedział — spróbuj za chwilę.', gotowe=? WHERE id=?",
                    (R.now_iso(), job["id"]))
        con.commit()
        return False
    text = str(text).strip()
    pdf = ""
    if job["rodzaj"] == "poradnik":
        with contextlib.suppress(Exception):
            out = Path(folder) / "poradniki" / f"{dt.datetime.now():%Y%m%d-%H%M}-{R.slug(job['temat'])[:40]}.pdf"
            render_pdf(text, out, f"Poradnik: {job['temat']}", f"Przygotował Sebastian dla: {p['imie'] if p else ''} · {dt.date.today():%d.%m.%Y}")
            pdf = str(out)
    con.execute("UPDATE zlecenia SET status='gotowe', wynik=?, plik=?, gotowe=? WHERE id=?", (text, pdf, R.now_iso(), job["id"]))
    con.commit()
    return True


def jobs(con, pid, limit=15):
    return [dict(r) for r in con.execute("SELECT * FROM zlecenia WHERE osoba=? ORDER BY id DESC LIMIT ?", (pid, limit))]


# ================================================================ PDF poradnika

def _fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    sets = [[Path("/System/Library/Fonts/Supplemental") / n for n in ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf")],
            [Path("/usr/share/fonts/truetype/dejavu") / n for n in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf")]]
    for paths in sets:
        if all(p.exists() for p in paths):
            with contextlib.suppress(Exception):
                for name, p in zip(("PorR", "PorB", "PorI"), paths):
                    pdfmetrics.registerFont(TTFont(name, str(p)))
                from reportlab.pdfbase.pdfmetrics import registerFontFamily
                registerFontFamily("PorR", normal="PorR", bold="PorB", italic="PorI", boldItalic="PorB")
                return "PorR", "PorB"
    return "Helvetica", "Helvetica-Bold"


def _inline(t):
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", t)


def render_pdf(md, out, title, sub):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    reg, bold = _fonts()
    ink, acc, gold, mut = HexColor("#262220"), HexColor("#6b2337"), HexColor("#b8924a"), HexColor("#7a7368")
    st = {"t": ParagraphStyle("t", fontName=bold, fontSize=20, leading=25, textColor=acc, spaceAfter=4),
          "s": ParagraphStyle("s", fontName=reg, fontSize=9, leading=12, textColor=mut, spaceAfter=14),
          "h1": ParagraphStyle("h1", fontName=bold, fontSize=15, leading=20, textColor=acc, spaceBefore=10, spaceAfter=6),
          "h2": ParagraphStyle("h2", fontName=bold, fontSize=12.5, leading=17, textColor=acc, spaceBefore=10, spaceAfter=4),
          "h3": ParagraphStyle("h3", fontName=bold, fontSize=11, leading=15, textColor=gold, spaceBefore=6, spaceAfter=3),
          "p": ParagraphStyle("p", fontName=reg, fontSize=10.5, leading=15.5, textColor=ink, spaceAfter=6),
          "li": ParagraphStyle("li", fontName=reg, fontSize=10.5, leading=15, textColor=ink, leftIndent=14, bulletIndent=3, spaceAfter=2)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    story = [Paragraph(html.escape(title), st["t"]), Paragraph(html.escape(sub), st["s"])]
    first_h1 = True
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            if level == 1 and first_h1:
                first_h1 = False
                continue                                   # tytuł już jest na górze
            story.append(Paragraph(_inline(m.group(2)), st["h1" if level == 1 else "h2" if level == 2 else "h3"]))
        elif re.match(r"^([-*•]|\d+[.)])\s+", s):
            num = re.match(r"^(\d+)[.)]\s+", s)
            story.append(Paragraph(_inline(re.sub(r"^([-*•]|\d+[.)])\s+", "", s)), st["li"], bulletText=(num.group(1) + "." if num else "•")))
        else:
            story.append(Paragraph(_inline(s), st["p"]))
    story.append(Spacer(1, 6))
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                      title=title, author="Sebastian").build(story)
    return out
