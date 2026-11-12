"""Rekrutacja — owca Sebastian: cel dnia, postęp i motywacja mailem (jak w aplikacjach do nauki, tylko spokojniej).

Rano owca pyta o cel (przyciski 10/20/30/40/50 w mailu), w ciągu dnia przypomina, jeśli Aga zostaje w tyle,
a po osiągnięciu celu gratuluje. Przez pierwszy tydzień przypomina w każdym zaplanowanym okienku, potem tylko wtedy,
gdy postęp jest wyraźnie poniżej tempa. „Zrobione” to aplikacje wysłane dziś plus zatwierdzone dziś (czekające na wysyłkę) —
to jest ta część pracy, która zależy od Agi.
"""
import contextlib, datetime as dt, hashlib, html as H, json, secrets
from pathlib import Path

from . import rdzen as R

ART = Path(__file__).with_name("szablony") / "owca"
GOALS = (10, 20, 30, 40, 50)
FIRST_WEEK = 7
INK, SOFT, BLUE, BG = "#1d1d1f", "#6e6e73", "#0071e3", "#f5f5f7"


# ================================================================ dane dnia

def today(ctx):
    return ctx.now().date()


def working_day(ctx, day):
    return day.weekday() < 5 or not ctx.settings().get("tylko_dni_robocze", True)


def goal(c, ctx, day):
    """Cel na dzień: ustawiony przez Agę, inaczej ostatni ustawiony, inaczej z ustawień (domyślnie 30), najwyżej limit dzienny."""
    st = ctx.settings()
    cap = int(st.get("limit_dzienny", 70) or 70)
    own = R.meta_get(c, f"cel_{day.isoformat()}")
    if own:
        return min(cap, int(own)), True
    last = R.meta_get(c, "cel_ostatni")
    return min(cap, int(last or st.get("owca_cel", 30) or 30)), False


def set_goal(c, ctx, day, n):
    n = max(1, min(int(ctx.settings().get("limit_dzienny", 70) or 70), int(n)))
    R.meta_set(c, f"cel_{day.isoformat()}", n)
    R.meta_set(c, "cel_ostatni", n)
    c.commit()
    return n


def progress(c, day):
    d = day.isoformat()
    sent = c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))}) AND substr(wyslano,1,10)=?",
                     (*R.SENT, d)).fetchone()[0]
    queued = c.execute("SELECT COUNT(*) FROM aplikacje WHERE status IN ('zatwierdzona','wysylanie') AND substr(zmieniono,1,10)=?", (d,)).fetchone()[0]
    waiting = c.execute("SELECT COUNT(*) FROM aplikacje WHERE status IN ('do_zatwierdzenia','do_sprawdzenia','formularz')").fetchone()[0]
    preparing = c.execute("SELECT COUNT(*) FROM aplikacje WHERE status IN ('nowa','przygotowywanie')").fetchone()[0]
    return {"wyslane": sent, "w_kolejce": queued, "zrobione": sent + queued, "czeka": waiting, "w_przygotowaniu": preparing}


def streak(c, ctx, day):
    """Ile kolejnych dni roboczych przed dziś (i dziś, jeśli już się udało) cel był osiągnięty."""
    n, d = 0, day
    for i in range(60):
        if not working_day(ctx, d):
            d -= dt.timedelta(days=1)
            continue
        g, _ = goal(c, ctx, d)
        done = progress(c, d)["zrobione"] if d == day else c.execute(
            f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))}) AND substr(wyslano,1,10)=?", (*R.SENT, d.isoformat())).fetchone()[0]
        if done >= g:
            n += 1
        elif d != day:
            break
        d -= dt.timedelta(days=1)
    return n


def first_week(c, ctx, day):
    start = R.meta_get(c, "owca_start")
    if not start:
        R.meta_set(c, "owca_start", day.isoformat())
        c.commit()
        return True
    with contextlib.suppress(ValueError):
        return (day - dt.date.fromisoformat(start)).days < FIRST_WEEK
    return False


def token(c):
    t = R.meta_get(c, "owca_token")
    if not t:
        t = secrets.token_urlsafe(18)
        R.meta_set(c, "owca_token", t)
        c.commit()
    return t


def goal_link(base, tok, day, n):
    return f"{base}/owca/cel/{tok}/{day.isoformat()}/{n}"


# ================================================================ co i kiedy wysłać

def _slots(st):
    out = []
    for x in str(st.get("owca_przypomnienia", "11:00,13:30,15:30")).split(","):
        with contextlib.suppress(Exception):
            out.append(R.hm(x.strip(), None))
    return [x for x in out if x]


def _window(st):
    try:
        a, b = str(st.get("godziny", "08:00-16:00")).split("-")
        return R.hm(a, (8, 0)), R.hm(b, (16, 0))
    except Exception:
        return dt.time(8, 0), dt.time(16, 0)


def expected(st, now, g):
    """Ile powinno być zrobione o tej porze przy równym tempie w oknie wysyłki."""
    a, b = _window(st)
    span = (b.hour * 60 + b.minute) - (a.hour * 60 + a.minute)
    gone = (now.hour * 60 + now.minute) - (a.hour * 60 + a.minute)
    return 0 if span <= 0 else max(0.0, min(1.0, gone / span)) * g


def due(ctx, c, now=None):
    """Który mail owcy wysłać teraz: 'rano' / 'przypomnienie' / 'brawo' / None (z powodem w meta dla testów)."""
    st = ctx.settings()
    now = now or ctx.now()
    day = now.date()
    if not st.get("owca", True) or st.get("wstrzymane") or not working_day(ctx, day) or R.meta_get(c, "onboarding") != "gotowe":
        return None
    sent = json.loads(R.meta_get(c, f"owca_{day.isoformat()}") or "[]")
    g, _ = goal(c, ctx, day)
    p = progress(c, day)
    if "brawo" not in sent and p["zrobione"] >= g:
        return "brawo"
    if "brawo" in sent:
        return None
    morning = R.hm(st.get("owca_rano", "07:45"), (7, 45))
    if "rano" not in sent and now.time() >= morning and now.time() < dt.time(12, 0):
        return "rano"
    slots = [s for s in _slots(st) if now.time() >= s]
    if not slots or len([x for x in sent if x.startswith("p")]) >= 3:
        return None
    slot = f"p{len(slots)}"
    if slot in sent:
        return None
    if p["czeka"] == 0 and p["w_przygotowaniu"] == 0:
        return None                                                    # nie ma czego zatwierdzać — przypomnienie nic by nie dało
    behind = p["zrobione"] < 0.8 * expected(st, now, g)
    if first_week(c, ctx, day) or behind:
        return slot
    return None


def mark(c, day, kind):
    key = f"owca_{day.isoformat()}"
    sent = json.loads(R.meta_get(c, key) or "[]")
    R.meta_set(c, key, json.dumps(sent + [kind]))
    c.commit()


# ================================================================ treść

MORNING = ["Nowy dzień, nowe szanse. Ile aplikacji wysyłamy dziś?",
           "Kawa jest, owca jest. Jaki cel na dziś?",
           "Dzień dobry! Ustalmy jedną liczbę na dziś, resztę zrobimy razem.",
           "Kolejny krok bliżej nowej pracy. Ile aplikacji dziś?",
           "Dobrze Cię widzieć. Jaki plan na dziś?"]
NUDGE_LOW = ["Hej, jeszcze trochę do roboty! Kilka minut i lecimy dalej.",
             "Mamy jeszcze kawałek drogi. Wystarczy kilka zatwierdzeń.",
             "Nie odpuszczamy — każda wysłana aplikacja to jedna szansa więcej."]
NUDGE_HALF = ["Jesteś w połowie! Jeszcze jedna runda i cel jest Twój.",
              "Dobre tempo. Jeszcze trochę i odhaczamy cały cel.",
              "Połowa za nami — jedziesz dalej!"]
NUDGE_CLOSE = ["Już prawie! Kilka aplikacji i cel dnia zrobiony.",
               "Finisz blisko — dokończmy to razem.",
               "Ostatnia prosta. Jeszcze chwila i gotowe!"]
BRAVO = ["Cel na dziś osiągnięty. Świetna robota!",
         "Zrobione! Owca jest z Ciebie dumna.",
         "Brawo! Dzisiejszy cel odhaczony."]


def _pick(options, day, salt=""):
    h = int(hashlib.sha256(f"{day.isoformat()}{salt}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def _plural(n, one, few, many):
    if n == 1:
        return one
    return few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def _bar(done, g):
    pct = max(0, min(100, round(100 * done / g))) if g else 0
    left, right = max(pct, 1), max(100 - pct, 0)
    cells = f'<td style="background:{BLUE};height:10px;width:{left}%;border-radius:5px 0 0 5px;font-size:0">&nbsp;</td>'
    if right:
        cells += f'<td style="background:#e5e5ea;height:10px;width:{right}%;border-radius:0 5px 5px 0;font-size:0">&nbsp;</td>'
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate"><tr>{cells}</tr></table>'


def _button(href, label, primary=True):
    bg, fg = (BLUE, "#ffffff") if primary else ("#e8f1fc", BLUE)
    return (f'<a href="{H.escape(href)}" style="display:inline-block;background:{bg};color:{fg};text-decoration:none;font-weight:600;'
            f'font-size:15px;padding:11px 20px;border-radius:999px;margin:4px 4px 4px 0">{H.escape(label)}</a>')


def _page(title, lead, body_html, art, footer=""):
    font = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif"
    return f'''<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{H.escape(title)}</title></head>
<body style="margin:0;padding:0;background:{BG};font-family:{font};color:{INK}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:28px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:22px">
<tr><td align="center" style="padding:30px 28px 0"><img src="cid:{art}" width="140" height="140" alt="Owca Sebastian" style="display:block;border:0"></td></tr>
<tr><td style="padding:14px 32px 0;text-align:center"><div style="font-size:26px;line-height:32px;font-weight:700;letter-spacing:-0.3px">{H.escape(title)}</div>
<div style="font-size:16px;line-height:23px;color:{SOFT};margin-top:8px">{H.escape(lead)}</div></td></tr>
<tr><td style="padding:22px 32px 30px;font-size:15px;line-height:22px">{body_html}</td></tr>
</table>
<div style="font-size:12px;line-height:18px;color:#86868b;margin-top:14px;max-width:520px">{footer or "Owca Sebastian · Twój asystent rekrutacji. Przypomnienia wyłączysz w panelu: Ustawienia → Jak pracuję."}</div>
</td></tr></table></body></html>'''


def _stats(done, g, s, p):
    rows = [(f"{done} / {g}", "zrobione dziś"), (f"{s} {_plural(s, 'dzień', 'dni', 'dni')}", "seria"), (str(p["czeka"]), "czeka na Ciebie")]
    cells = "".join(f'<td align="center" style="padding:6px 4px;width:33%"><div style="font-size:22px;font-weight:700">{H.escape(a)}</div>'
                    f'<div style="font-size:12px;color:{SOFT}">{H.escape(b)}</div></td>' for a, b in rows)
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};border-radius:16px;margin:0 0 16px"><tr>{cells}</tr></table>'


def compose(ctx, c, kind, now=None):
    """(temat, tekst, html, nazwa obrazka) dla maila owcy."""
    now = now or ctx.now()
    day = now.date()
    f = R.load_facts(ctx)
    name = f["osoba"].get("imie") or "Aga"
    hi = "Ago" if name.lower().startswith("agn") or name.lower() == "aga" else name
    g, own = goal(c, ctx, day)
    p = progress(c, day)
    done = p["zrobione"]
    s = streak(c, ctx, day)
    base = R.meta_get(c, "adres_panelu") or ""
    tok = token(c)
    left = max(0, g - done)
    if kind == "rano":
        y = day - dt.timedelta(days=1)
        while not working_day(ctx, y) and (day - y).days < 5:
            y -= dt.timedelta(days=1)
        yg, _ = goal(c, ctx, y)
        ydone = c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))}) AND substr(wyslano,1,10)=?",
                          (*R.SENT, y.isoformat())).fetchone()[0]
        title = f"Dzień dobry, {hi}!"
        lead = _pick(MORNING, day)
        buttons = "".join(_button(goal_link(base, tok, day, n), str(n), primary=(n == g)) for n in GOALS) if base else ""
        body = (f'<p style="margin:0 0 14px">Wybierz cel na dziś — jedno kliknięcie wystarczy:</p><p style="margin:0 0 16px">{buttons}</p>'
                f'<p style="margin:0 0 16px;color:{SOFT};font-size:14px">Jeśli nie wybierzesz, zostaje {g} — tak jak ostatnio.</p>'
                + _stats(ydone, yg, s, p).replace("zrobione dziś", "wczoraj")
                + (f'<p style="margin:0 0 6px">Gotowych do przejrzenia: <b>{p["czeka"]}</b>. Wystarczy je przeczytać i zatwierdzić — wysyłkę biorę na siebie.</p>'
                   if p["czeka"] else '<p style="margin:0 0 6px">Szukam i przygotowuję nowe oferty — dam znać, gdy będą gotowe do przejrzenia.</p>')
                + (f'<p style="margin:18px 0 0">{_button(base + "/do-zrobienia", "Otwórz panel")}</p>' if base else ""))
        subject = f"🐑 Dzień dobry, {hi}! Jaki cel na dziś?"
        text = (f"Dzień dobry, {hi}!\n\n{lead}\n\n" + ("\n".join(f"Cel {n}: {goal_link(base, tok, day, n)}" for n in GOALS) if base else "")
                + f"\n\nJeśli nie wybierzesz, zostaje {g}. Wczoraj: {ydone}/{yg}. Seria: {s}. Czeka na Ciebie: {p['czeka']}.\n\nOwca Sebastian")
        art = "rano"
    elif kind == "brawo":
        title = f"{g} / {g} — cel osiągnięty!"
        lead = _pick(BRAVO, day)
        s_txt = f"To już <b>{s}. {_plural(s, 'dzień', 'dzień', 'dzień')}</b> z rzędu." if s > 1 else "Pierwszy dzień serii — jutro budujemy dalej."
        body = (_bar(1, 1) + f'<p style="margin:16px 0 14px;text-align:center">{s_txt}</p>'
                + _stats(done, g, s, p)
                + '<p style="margin:0">Na dziś możesz odpocząć z czystym sumieniem. Odpowiedzi od pracodawców pilnuję dalej i dam znać, gdy przyjdzie coś ważnego.</p>')
        subject = f"🎉 Cel osiągnięty: {done}/{g}!"
        text = f"{lead}\n\nDziś: {done}/{g}. Seria: {s}.\n\nOwca Sebastian"
        art = "brawo"
    else:
        ratio = done / g if g else 0
        lead = _pick(NUDGE_LOW if ratio < 0.4 else NUDGE_HALF if ratio < 0.75 else NUDGE_CLOSE, day, kind)
        title = f"{done} / {g} — zostało {left}"
        todo = min(left, p["czeka"])
        cta = (f'<p style="margin:16px 0 0">{_button(base + "/do-zrobienia", f"Przejrzyj {todo} {_plural(todo, chr(97) + "plikację", "aplikacje", "aplikacji")}")}</p>'
               if base and todo else "")
        hint = (f"Gotowych do przejrzenia jest {p['czeka']}. Kilka minut i będziesz bliżej celu." if p["czeka"] else
                f"Przygotowuję {p['w_przygotowaniu']} {_plural(p['w_przygotowaniu'], 'aplikację', 'aplikacje', 'aplikacji')} — zajrzyj za chwilę.")
        body = _bar(done, g) + f'<p style="margin:16px 0 14px">{H.escape(hint)}</p>' + _stats(done, g, s, p) + cta
        subject = f"🐑 {done}/{g} — {lead.split('!')[0].split('.')[0]}!"
        text = f"{lead}\n\nDziś: {done}/{g}, zostało {left}. Czeka na Ciebie: {p['czeka']}.\n" + (f"{base}/do-zrobienia\n" if base else "") + "\nOwca Sebastian"
        art = "motywacja"
    return subject, text, _page(title, lead, body, art), art


def image(name):
    return (ART / f"{name}.png").read_bytes()


def tick(ctx, send, now=None):
    """Wywoływane w każdym obrocie pracy w tle. Wysyła najwyżej jeden mail owcy. Zwraca rodzaj albo None."""
    now = now or ctx.now()
    with R.db(ctx) as c:
        kind = due(ctx, c, now)
        if not kind:
            return None
        me, seb = R.mailboxes(c)
        subject, text, html, art = compose(ctx, c, kind, now)
    sender, key = (seb, "sebastian") if seb and R.secret(ctx, "sebastian") else (me, "aga")
    pwd = R.secret(ctx, key)
    if not me or not pwd:
        return None
    try:
        send(sender, pwd, me, subject, text, name="Owca Sebastian", html=html, images={art: image(art)})
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: mail owcy nie wyszedł ({type(e).__name__})")
        return None
    with R.db(ctx) as c:
        mark(c, now.date(), kind)
    return kind


def report_line(ctx, c, day):
    g, _ = goal(c, ctx, day)
    p = progress(c, day)
    s = streak(c, ctx, day)
    return f"🐑 Cel dnia: {p['zrobione']}/{g}" + (" — osiągnięty!" if p["zrobione"] >= g else "") + (f" Seria: {s} {_plural(s, 'dzień', 'dni', 'dni')}." if s else "")


# ================================================================ etapy po wysłaniu: rozmowa, zadanie, oferta, umowa

MONTHS = {"stycz": 1, "lut": 2, "marc": 3, "kwie": 4, "maj": 5, "czerw": 6, "lip": 7, "sierp": 8, "wrze": 9, "pazdz": 10, "listop": 11, "grud": 12}


def parse_date(text, ref):
    """Data z „termin” w wiadomości: 20.11, 20.11.2026, 20 listopada, jutro. None, gdy nie da się ustalić."""
    t = R.plain(text or "")
    if "pojutrze" in t:
        return ref + dt.timedelta(days=2)
    if "jutro" in t:
        return ref + dt.timedelta(days=1)
    import re
    for m in re.finditer(r"(?<![\d:])(\d{1,2})[./-](\d{1,2})(?:[./-](\d{4}|\d{2}))?(?![\d:])", t):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        after = t[m.end():m.end() + 6]
        if not y and re.match(r"\s*(h|godz|-\s*\d)", after):
            continue                                                   # 10.00 h — godzina, nie data
        year = (int(y) + (2000 if len(y) == 2 else 0)) if y else ref.year
        with contextlib.suppress(ValueError):
            out = dt.date(year, mo, d)
            if not y and out < ref - dt.timedelta(days=1):
                out = out.replace(year=ref.year + 1)
            return out
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\w*", t)
    if m:
        with contextlib.suppress(ValueError):
            out = dt.date(ref.year, MONTHS[m.group(2)], int(m.group(1)))
            return out if out >= ref - dt.timedelta(days=1) else out.replace(year=ref.year + 1)
    return None


def thanks_note(f, a):
    from . import dokumenty as D
    job = f" dotyczącą stanowiska {a['stanowisko']}" if a.get("stanowisko") else ""
    return ("Dzień dobry,\n\ndziękuję za rozmowę" + job + " i za czas, który Państwo mi poświęcili. Po naszym spotkaniu tym bardziej "
            "chciałabym dołączyć do zespołu — zakres zadań bardzo dobrze pasuje do mojego doświadczenia.\n\nJeśli potrzebują Państwo "
            "dodatkowych informacji, chętnie je prześlę.\n\n" + D.signature(f))


def stage_link(base, tok, aid, action):
    return f"{base}/owca/etap/{tok}/{aid}/{action}"


def _list(items):
    return "".join(f'<tr><td valign="top" style="padding:3px 10px 3px 0;color:{BLUE};font-weight:700">•</td><td style="padding:3px 0">{x}</td></tr>' for x in items)


def _section(title, items):
    if not items:
        return ""
    return (f'<div style="font-size:17px;font-weight:700;margin:20px 0 6px">{H.escape(title)}</div>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="font-size:15px;line-height:22px">{_list(items)}</table>')


QUESTIONS = ["Proszę opowiedzieć o sobie.", "Dlaczego interesuje Panią to stanowisko i nasza firma?",
             "Dlaczego chce Pani zmienić pracę? (pokaż to jako świadomą decyzję, nie ucieczkę)",
             "Jak organizuje Pani pracę, gdy jest dużo zadań naraz? (podaj przykład z liczbami)",
             "Jakie są Pani oczekiwania finansowe i od kiedy może Pani zacząć?"]
ASK_THEM = ["Jak wygląda typowy dzień na tym stanowisku?", "Z kim będę najczęściej współpracować?",
            "Jak wygląda wdrożenie i po czym poznam, że dobrze mi idzie?", "Jakie są kolejne etapy rekrutacji?"]


def stage_events(ctx, c, now):
    """Zdarzenia do wysłania teraz: [(klucz, rodzaj, aplikacja, wiadomość|None, termin)]."""
    day = now.date()
    done = set(json.loads(R.meta_get(c, "owca_etapy") or "[]"))
    out = []
    rows = c.execute("SELECT w.id wid, w.rodzaj, w.termin, w.data, a.* FROM wiadomosci w JOIN aplikacje a ON a.id=w.aplikacja_id "
                     "WHERE w.rodzaj IN ('zaproszenie','zadanie') ORDER BY w.id").fetchall()
    for r in rows:
        r = dict(r)
        when = parse_date(r["termin"], dt.date.fromisoformat((r["data"] or day.isoformat())[:10]) if r["data"] else day)
        if r["status"] in ("odmowa", "przyjeta", "oferta"):
            continue
        k = f"{r['rodzaj']}:{r['wid']}"
        if k not in done:
            out.append((k, r["rodzaj"], r, when))
        if r["rodzaj"] == "zaproszenie" and when:
            if when == day and f"dzien:{r['wid']}" not in done:
                out.append((f"dzien:{r['wid']}", "dzien", r, when))
            if day > when and (day - when).days <= 3 and f"jak:{r['wid']}" not in done and r["status"] in ("zaproszenie", "rozmowa"):
                out.append((f"jak:{r['wid']}", "jak", r, when))
    for a in c.execute("SELECT * FROM aplikacje WHERE status='oferta' ORDER BY id").fetchall():   # z maila albo zaznaczona przez Agę
        if f"oferta:{a['id']}" not in done:
            out.append((f"oferta:{a['id']}", "oferta", dict(a), None))
    with contextlib.suppress(Exception):
        if c.execute("SELECT 1 FROM aplikacje WHERE status='przyjeta'").fetchone() and "koniec" not in done:
            row = dict(c.execute("SELECT * FROM aplikacje WHERE status='przyjeta' ORDER BY zmieniono DESC LIMIT 1").fetchone())
            out.append(("koniec", "koniec", row, None))
    return out


def stage_compose(ctx, c, kind, a, when):
    f = R.load_facts(ctx)
    base = R.meta_get(c, "adres_panelu") or ""
    tok = token(c)
    firm, job = a.get("firma") or "pracodawca", a.get("stanowisko") or "stanowisko"
    when_txt = f"{when.day}.{when.month:02d}" if when else ""
    info = {}
    with contextlib.suppress(Exception):
        info = json.loads(a.get("analiza") or "{}")
    fit = info.get("dopasowanie") or []
    app_link = f'{base}/aplikacja/{a["id"]}' if base else ""
    if kind == "zaproszenie":
        strong = [f"<b>{H.escape(x['wymaganie'])}</b> — {H.escape(x.get('dlaczego') or '')}" for x in fit if x["ocena"] == "mam"][:4]
        gaps = [f"<b>{H.escape(x['wymaganie'])}</b> — powiedz uczciwie, co już znasz i jak szybko się wdrażasz" for x in fit if x["ocena"] != "mam"][:3]
        tasks = [H.escape(x) for x in (info.get("obowiazki") or [])][:4]
        body = (f'<p style="margin:0">Termin: <b>{H.escape(a.get("termin") or when_txt or "sprawdź w wiadomości od pracodawcy")}</b>.</p>'
                + _section("Twoje mocne strony na tę rozmowę", strong)
                + _section("Przygotuj odpowiedź, gdy zapytają o", gaps)
                + _section("Co będziesz tam robić (z ogłoszenia)", tasks)
                + _section("Pytania, które prawie zawsze padają", [H.escape(q) for q in QUESTIONS])
                + _section("Twoje pytania do nich", [H.escape(q) for q in ASK_THEM])
                + _section("Przed wyjściem", ["Przeczytaj jeszcze raz ogłoszenie i stronę firmy.", "Sprawdź dojazd i wyjdź z zapasem 15 minut.",
                                              "Weź wydrukowane CV i dowód osobisty.", "Dzień po rozmowie podeślę Ci gotowe podziękowanie do wysłania."])
                + (f'<p style="margin:22px 0 0">{_button(app_link, "Otwórz ofertę i odpowiedź")}</p>' if app_link else ""))
        return (f"🐑 Zaproszenie na rozmowę — {firm}! Przygotujmy się", "Zaproszenie na rozmowę!",
                f"{firm} · {job}. To duży krok — przygotujmy się razem.", body, "brawo")
    if kind == "dzien":
        body = ('<p style="margin:0 0 12px">Trzy rzeczy na dziś: spokojny oddech, przykłady z liczbami (np. ok. 80 historii choroby miesięcznie, '
                'ponad 100 planów finansowych) i jedno pytanie do nich na koniec.</p>'
                + (f'<p style="margin:16px 0 0">{_button(app_link, "Przypomnij mi ofertę")}</p>' if app_link else ""))
        return (f"🐑 Dziś rozmowa — {firm}. Powodzenia!", "Dziś Twój dzień!", f"{firm} · {job}. Trzymam kciuki (kopytka też).", body, "motywacja")
    if kind == "jak":
        buttons = "".join(_button(stage_link(base, tok, a["id"], x), lab, primary=(i == 0)) for i, (x, lab) in enumerate(
            (("rozmowa", "Było OK, czekam na decyzję"), ("oferta", "Dostałam ofertę!"), ("odmowa", "To nie to"), ("jeszcze", "Rozmowa jeszcze przed mną")))) if base else ""
        body = (f'<p style="margin:0 0 14px">Daj znać jednym kliknięciem — dopasuję kolejne kroki:</p><p style="margin:0">{buttons}</p>'
                f'<div style="font-size:17px;font-weight:700;margin:22px 0 6px">Podziękowanie po rozmowie (do skopiowania)</div>'
                f'<div style="background:{BG};border-radius:14px;padding:14px 16px;font-size:14px;line-height:21px;white-space:pre-wrap">{H.escape(thanks_note(f, a))}</div>'
                '<p style="margin:10px 0 0;color:#6e6e73;font-size:14px">Wyślij je w odpowiedzi na wiadomość z zaproszeniem — najlepiej w ciągu doby od rozmowy.</p>')
        return (f"🐑 Jak poszła rozmowa? ({firm})", "Jak poszło?", f"{firm} · {job}", body, "rano")
    if kind == "zadanie":
        body = (_section("Jak podejść do zadania", ["Przeczytaj polecenie dwa razy i wypisz, co dokładnie ma powstać.",
                                                    "Zapytaj, jeśli coś jest niejasne — to dobrze świadczy, nie źle.",
                                                    "Zaplanuj czas: zostaw sobie zapas przed terminem na sprawdzenie.",
                                                    "Pokaż sposób myślenia: krótko opisz, co i dlaczego zrobiłaś."])
                + (f'<p style="margin:22px 0 0">{_button(app_link, "Otwórz wiadomość")}</p>' if app_link else ""))
        return (f"🐑 Zadanie rekrutacyjne — {firm}. Dasz radę!", "Zadanie rekrutacyjne", f"{firm} · {job}. Kolejny etap, czyli jesteś w grze.", body, "motywacja")
    if kind == "oferta":
        w = f.get("warunki", {})
        mine = f"od {w.get('min_netto')} zł netto" if w.get("min_netto") else "Twoje oczekiwania"
        buttons = (_button(stage_link(base, tok, a["id"], "przyjmuje"), "Przyjmuję ofertę 🎉") +
                   _button(app_link or base, "Jeszcze się zastanawiam", primary=False)) if base else ""
        body = (_section("Sprawdź w propozycji", [f"Rodzaj umowy: {H.escape(w.get('umowa') or 'umowa o pracę')}, {H.escape(w.get('etat') or 'pełny etat')}.",
                                                  f"Wynagrodzenie netto na rękę — porównaj z: {H.escape(mine)}.",
                                                  "Okres próbny i na jak długo jest pierwsza umowa.",
                                                  f"Data startu — Twoja dostępność: {H.escape(w.get('dostepnosc') or 'do ustalenia')}.",
                                                  "Godziny pracy (bez niedziel i wieczorów?) i dojazd.", "Benefity: opieka medyczna, karta sportowa, PPK."])
                + _section("Dokumenty, które zwykle są potrzebne", ["Dowód osobisty, PESEL, numer konta, adres urzędu skarbowego.",
                                                                    "Świadectwa pracy, dyplom, zaświadczenia z kursów.",
                                                                    "Badania medycyny pracy (skierowanie daje pracodawca) i szkolenie BHP.",
                                                                    "Wypowiedzenie w obecnej pracy — dopiero po podpisaniu nowej umowy."])
                + (f'<p style="margin:22px 0 0">{buttons}</p>' if buttons else ""))
        return (f"🎉 Oferta pracy — {firm}!", "Masz ofertę!", f"{firm} · {job}. Zanim powiesz „tak”, sprawdźmy szczegóły.", body, "brawo")
    if kind == "koniec":
        body = ('<p style="margin:0 0 12px;text-align:center">Wstrzymałem szukanie i wysyłkę nowych aplikacji. Odpowiedzi od pracodawców '
                'nadal przeczytam i dam znać, jeśli przyjdzie coś ważnego.</p>'
                '<p style="margin:0;text-align:center">Gdybyś kiedyś chciała wrócić do szukania — jeden przełącznik w Ustawieniach.</p>')
        return (f"🎉 Gratulacje! Nowa praca — {firm}", "Udało się!", f"{firm} · {job}. Owca Sebastian jest z Ciebie ogromnie dumna.", body, "brawo")
    return None


def stage_tick(ctx, send, now=None):
    """Najwyżej jeden mail o etapie rekrutacji na obrót (7:00–21:00). Zwraca klucz zdarzenia albo None."""
    now = now or ctx.now()
    if not ctx.settings().get("owca", True) or not (dt.time(7, 0) <= now.time() <= dt.time(21, 0)):
        return None
    with R.db(ctx) as c:
        if R.meta_get(c, "onboarding") != "gotowe":
            return None
        events = stage_events(ctx, c, now)
        if not events:
            return None
        key, kind, a, when = events[0]
        made = stage_compose(ctx, c, kind, a, when)
        me, seb = R.mailboxes(c)
        base = R.meta_get(c, "adres_panelu") or ""
    sender, k = (seb, "sebastian") if seb and R.secret(ctx, "sebastian") else (me, "aga")
    pwd = R.secret(ctx, k)
    if not made or not me or not pwd:
        return None
    subject, title, lead, body, art = made
    text = f"{title}\n\n{lead}\n\nSzczegóły w panelu: {base}\n\nOwca Sebastian"
    try:
        send(sender, pwd, me, subject, text, name="Owca Sebastian", html=_page(title, lead, body, art), images={art: image(art)})
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: mail owcy o etapie nie wyszedł ({type(e).__name__})")
        return None
    with R.db(ctx) as c:
        done = json.loads(R.meta_get(c, "owca_etapy") or "[]")
        R.meta_set(c, "owca_etapy", json.dumps(done + [key]))
        c.commit()
    return key


def stage_action(ctx, c, aid, action):
    """Klik z maila: rozmowa / oferta / odmowa / jeszcze / przyjmuje. Zwraca tekst dla Agi."""
    a = c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone()
    if not a:
        return None
    if action == "jeszcze":
        return "Dobrze — przypomnę się po rozmowie."
    if action not in ("rozmowa", "oferta", "odmowa", "przyjmuje"):
        return None
    if action == "przyjmuje":
        R.set_status(c, ctx, aid, "przyjeta")
        for k, v in (("szukanie", "nie"), ("spontaniczne", "nie"), ("wstrzymane", "tak")):
            ctx.set_setting(k, v)
        R.note(c, ctx, aid, "Aga przyjęła ofertę — szukanie i wysyłka wstrzymane")
        c.commit()
        return f"Gratulacje! Zapisałam: przyjęta oferta w {a['firma']}. Szukanie i wysyłka są wstrzymane."
    R.set_status(c, ctx, aid, action)
    R.note(c, ctx, aid, f"Aga z maila owcy: {R.STATUS[action]}")
    c.commit()
    return {"rozmowa": "Zapisane: po rozmowie, czekasz na decyzję. Trzymam kciuki!",
            "oferta": "Wspaniale! Zaraz dostaniesz mail z tym, co sprawdzić w ofercie.",
            "odmowa": "Szkoda, ale to też doświadczenie. Jedziemy dalej — kolejne oferty czekają."}[action]
