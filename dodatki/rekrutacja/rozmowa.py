"""Rekrutacja — rozmowa z Agą (2.13).

Aga może po prostu odpisać Sebastianowi: na maila owcy, osobnym mailem na skrzynkę Sebastiana, na WhatsAppie
albo w panelu (zakładka Rozmowa). Sebastian:
  * odpisuje życzliwie, krótko i konkretnie — przyjmuje to, co napisała, i delikatnie, ale konsekwentnie proponuje
    mały krok do przodu albo pyta o termin („nie mam dziś czasu” → „jasne, kiedy będziesz mogła?”);
  * wstrzymuje codzienne maile owcy na czas, gdy Aga jest zajęta albo wyjeżdża (seria się wtedy nie przerywa);
  * przypomina w terminie, który Aga poda;
  * prowadzi dziennik rozmowy (także własnych maili i WhatsAppów do Agi) i pamięć trwałych faktów, więc rozumie
    kontekst z poprzednich dni.
Pisze ten sam łańcuch co listy: Gemini (bez danych osobowych) → Bielik → model Sebastiana; gdy żaden nie odpowie —
proste reguły. Pamięć leży lokalnie w bazie dodatku; Aga widzi ją w panelu i może usuwać wpisy.
"""
import contextlib, datetime as dt, json, re

from . import rdzen as R
try:
    import mail_szablon as MS                                   # wspólny wygląd maili Sebastiana (folder główny)
except ImportError:                                             # pragma: no cover
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
    import mail_szablon as MS

DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
WEEKDAYS = {"poniedzial": 0, "wtor": 1, "srod": 2, "czwart": 3, "piat": 4, "sobot": 5, "niedziel": 6}
MEMORY_CAP = 80
HISTORY = 16

CRISIS = re.compile(r"nie chce (juz )?zyc|samoboj|skonczyc ze soba|zrobic sobie krzywde|odebrac sobie zycie|nie mam po co zyc")
BUSY = re.compile(r"nie mam (dzis |dzisiaj |teraz |w ogole )?czasu|zajet|nie dam (dzis |dzisiaj )?rady|nie zdaze|dzis nie|dzisiaj nie|"
                  r"nie dzis|nie dzisiaj|mam urwanie|mam dzis duzo|padam")
AWAY = re.compile(r"wyjazd|wyjezdzam|wyjechal|urlop|nie ma mnie|nie bedzie mnie|w podrozy|na wakacjach|poza domem|w szpitalu")
BACK = re.compile(r"wrocilam|jestem z powrotem|juz jestem|mozemy dzialac|dzialamy|wracam do (pracy|szukania)")
ASKED_WHEN = re.compile(r"kiedy\b.*\?")


# ================================================================ baza

def ensure(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS rozmowa(id INTEGER PRIMARY KEY, kanal TEXT, kto TEXT, tresc TEXT, temat TEXT DEFAULT '',
        message_id TEXT DEFAULT '', kiedy TEXT);
    CREATE TABLE IF NOT EXISTS rozmowa_pamiec(id INTEGER PRIMARY KEY, fakt TEXT, utworzono TEXT);
    CREATE TABLE IF NOT EXISTS rozmowa_przypomnienia(id INTEGER PRIMARY KEY, kiedy TEXT, co TEXT DEFAULT '', kanal TEXT DEFAULT 'mail',
        utworzono TEXT, wyslano TEXT DEFAULT '');
    """)


def log(ctx, kanal, kto, tresc, temat="", message_id=""):
    """Wpis do dziennika rozmowy. kto: 'aga' albo 'sebastian'."""
    tresc = (tresc or "").strip()
    if not tresc:
        return
    with contextlib.suppress(Exception), R.db(ctx) as c:
        ensure(c)
        c.execute("INSERT INTO rozmowa(kanal,kto,tresc,temat,message_id,kiedy) VALUES(?,?,?,?,?,?)",
                  (kanal, kto, tresc[:2000], (temat or "")[:200], message_id or "", R.stamp(ctx)))
        c.commit()


def history(c, n=HISTORY):
    ensure(c)
    rows = c.execute("SELECT * FROM rozmowa ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def memory(c):
    ensure(c)
    return [dict(r) for r in c.execute("SELECT * FROM rozmowa_pamiec ORDER BY id").fetchall()]


def remember(ctx, c, facts):
    have = {R.plain(m["fakt"]) for m in memory(c)}
    for fact in facts or []:
        fact = re.sub(r"\s+", " ", str(fact or "")).strip(" -•.")[:200]
        if len(fact) < 6 or R.plain(fact) in have or re.search(r"\[(pominięte|e-mail|telefon)\]", fact):
            continue
        c.execute("INSERT INTO rozmowa_pamiec(fakt,utworzono) VALUES(?,?)", (fact, R.stamp(ctx)))
        have.add(R.plain(fact))
    extra = c.execute("SELECT COUNT(*) FROM rozmowa_pamiec").fetchone()[0] - MEMORY_CAP
    if extra > 0:
        c.execute("DELETE FROM rozmowa_pamiec WHERE id IN (SELECT id FROM rozmowa_pamiec ORDER BY id LIMIT ?)", (extra,))
    c.commit()


# ================================================================ przerwy owcy (Aga zajęta / na wyjeździe)

def pauses(c):
    return json.loads(R.meta_get(c, "owca_przerwy") or "[]")


def paused(c, day):
    """Czy w ten dzień owca ma odpuścić codzienne maile (i nie liczyć go do serii)."""
    d = day.isoformat()
    return any(a <= d <= b for a, b in pauses(c))


def pause_until(c, ctx):
    today = ctx.now().date().isoformat()
    ends = [b for a, b in pauses(c) if a <= today <= b]
    return max(ends) if ends else ""


def set_pause(c, ctx, until):
    today = ctx.now().date()
    until = max(today, min(until, today + dt.timedelta(days=60)))
    items = [p for p in pauses(c) if p[1] >= (today - dt.timedelta(days=90)).isoformat()]
    items = [p for p in items if not (p[0] <= today.isoformat() <= p[1])]
    items.append([today.isoformat(), until.isoformat()])
    R.meta_set(c, "owca_przerwy", json.dumps(items))
    c.commit()
    return until


def end_pause(c, ctx):
    today = ctx.now().date()
    y = (today - dt.timedelta(days=1)).isoformat()
    items = [[a, min(b, y)] if a <= today.isoformat() <= b else [a, b] for a, b in pauses(c)]
    R.meta_set(c, "owca_przerwy", json.dumps([p for p in items if p[0] <= p[1]]))
    c.commit()


# ================================================================ przypomnienia

def add_reminder(c, ctx, when, what, kanal):
    ensure(c)
    c.execute("DELETE FROM rozmowa_przypomnienia WHERE wyslano='' AND substr(kiedy,1,10)=?", (when.date().isoformat(),))
    c.execute("INSERT INTO rozmowa_przypomnienia(kiedy,co,kanal,utworzono) VALUES(?,?,?,?)",
              (when.strftime("%Y-%m-%dT%H:%M"), (what or "")[:200], kanal, R.stamp(ctx)))
    c.commit()


def pending_reminders(c):
    ensure(c)
    return [dict(r) for r in c.execute("SELECT * FROM rozmowa_przypomnienia WHERE wyslano='' ORDER BY kiedy").fetchall()]


def parse_when(text, now, default_hour=(9, 0)):
    """Kiedy z odpowiedzi Agi: data (20.11, 20 listopada, jutro), dzień tygodnia, „za tydzień”, „za 3 dni”, godzina."""
    from . import owca as OW
    t = R.plain(text)
    day = OW.parse_date(text, now.date())
    if not day:
        m = re.search(r"za (\d{1,2}|dwa|trzy|kilka) (dni|tygodn)", t)
        if m:
            n = {"dwa": 2, "trzy": 3, "kilka": 3}.get(m.group(1)) or int(m.group(1))
            day = now.date() + dt.timedelta(days=n * (7 if m.group(2).startswith("tygodn") else 1))
        elif re.search(r"za tydzien|w przyszlym tygodniu|od przyszlego tygodnia", t):
            day = now.date() + dt.timedelta(days=7 - now.weekday())       # najbliższy poniedziałek
        else:
            for stem, wd in WEEKDAYS.items():
                if re.search(r"\b" + stem, t):
                    ahead = (wd - now.weekday()) % 7 or 7
                    day = now.date() + dt.timedelta(days=ahead)
                    break
    if not day and re.search(r"\b(wieczorem|po poludniu|pozniej|za godzine|za dwie godziny)\b", t):
        day = now.date()
    if not day:
        return None
    hour = default_hour
    m = re.search(r"\b(?:o|na|od|po)\s*(\d{1,2})(?::(\d{2}))?(?!\d)", t)
    if m and 6 <= int(m.group(1)) <= 21:
        hour = (int(m.group(1)), int(m.group(2) or 0))
    elif "wieczorem" in t:
        hour = (19, 0)
    elif "po poludniu" in t:
        hour = (15, 0)
    elif "za godzine" in t:
        return now + dt.timedelta(hours=1)
    elif "za dwie godziny" in t:
        return now + dt.timedelta(hours=2)
    when = dt.datetime.combine(day, dt.time(*hour)).replace(tzinfo=now.tzinfo)
    return when if when > now else None


# ================================================================ sytuacja (to, co Sebastian wie „na teraz”)

def situation(ctx, c):
    from . import owca as OW
    now = ctx.now()
    day = now.date()
    g, own = OW.goal(c, ctx, day)
    p = OW.progress(c, day)
    s = OW.streak(c, ctx, day)
    lines = [f"Dziś: {DAYS[day.weekday()]}, {day.strftime('%d.%m.%Y')}, godz. {now.strftime('%H:%M')}.",
             f"Cel na dziś: {g} aplikacji ({'ustawiony przez Agę' if own else 'domyślny'}); zrobione: {p['zrobione']}; "
             f"czeka na jej przejrzenie: {p['czeka']}; w przygotowaniu: {p['w_przygotowaniu']}; seria dni z celem: {s}."]
    week = (day - dt.timedelta(days=6)).isoformat()
    sent7 = c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))}) AND substr(wyslano,1,10)>=?",
                      (*R.SENT, week)).fetchone()[0]
    lines.append(f"Wysłane w ostatnich 7 dniach: {sent7}.")
    stages = c.execute("SELECT firma, stanowisko, status FROM aplikacje WHERE status IN ('zaproszenie','rozmowa','oferta','pytanie') "
                       "ORDER BY zmieniono DESC LIMIT 5").fetchall()
    if stages:
        names = {"zaproszenie": "zaproszenie na rozmowę", "rozmowa": "po rozmowie", "oferta": "propozycja pracy", "pytanie": "pytanie od pracodawcy"}
        lines.append("Sprawy w toku: " + "; ".join(f"{r['firma'] or 'firma'} ({r['stanowisko'] or 'stanowisko'}) — {names[r['status']]}" for r in stages) + ".")
    pu = pause_until(c, ctx)
    if pu:
        lines.append(f"Przerwa w codziennych mailach owcy do {dt.date.fromisoformat(pu).strftime('%d.%m')} (włącznie).")
    rem = pending_reminders(c)
    if rem:
        lines.append("Zaplanowane przypomnienia: " + "; ".join(f"{r['kiedy'].replace('T', ' ')}" + (f" ({r['co']})" if r["co"] else "") for r in rem[:3]) + ".")
    if ctx.settings().get("wstrzymane"):
        lines.append("Wysyłka aplikacji jest wstrzymana w ustawieniach.")
    base = R.meta_get(c, "adres_panelu")
    if base:
        lines.append(f"Adres panelu: {base}")
    return "\n".join(lines)


def _hi(f):
    name = (f.get("osoba") or {}).get("imie") or "Aga"
    return "Ago" if R.plain(name).startswith("agn") or R.plain(name) == "aga" else name


# ================================================================ odpowiedź

GUIDE = """Jesteś Sebastianem — asystentem, który pomaga Adze znaleźć pracę (w mailach podpisujesz się jako Owca Sebastian).
Aga właśnie do Ciebie napisała. Odpisz jej jak życzliwy, mądry przyjaciel, który wierzy w nią i trzyma rękę na pulsie.

JAK PISZESZ
- Po polsku, naturalnie, ciepło i serdecznie, bez sztuczności, bez frazesów coachingowych, bez myślników jako ozdobników.
- O sobie w rodzaju męskim („zapisałem”, „przypomnę”), do Agi w rodzaju żeńskim („mogłabyś”, „dałaś radę”). Zwracaj się „{hi}” albo bez imienia.
- Krótko: {length}. Bez nagłówków, list, „Droga Agnieszko” i podpisu (podpis dodam sam).
- Najwyżej jedno emoji, i tylko gdy pasuje.
- Najpierw przyjmij to, co napisała — bez oceniania, bez wyrzutów, bez wywoływania poczucia winy.
- Potem delikatnie, ale stanowczo pchnij sprawę do przodu: jeden mały, konkretny krok albo jedno pytanie o termin.
  * „Nie mam dziś czasu” → zaakceptuj i zapytaj, kiedy będzie mogła (albo zaproponuj, kiedy przypomnisz).
  * Wyjazd, urlop, zajęty tydzień → życz dobrze, zapytaj, kiedy przypomnieć (jeśli podała datę — potwierdź ją).
  * Kolejne przekładanie → zaproponuj mniejszy krok (np. 10 minut i 5 aplikacji), ale nie odpuszczaj celu.
  * Podała termin → potwierdź krótko, że przypomnisz, i nie dokładaj nowych próśb.
  * Dobre wieści → ciesz się razem z nią.
  * Zmęczenie, stres, smutek → najpierw empatia, bez pchania; zaproponuj odpoczynek i najmniejszy krok na później.
- Pamiętaj o tym, co było w rozmowie wcześniej (HISTORIA, PAMIĘĆ) i nawiązuj do tego naturalnie; nie powtarzaj swoich wcześniejszych zdań.
- O jej zdrowie ani sprawy prywatne nie dopytuj; jeśli sama o nich wspomina, przyjmij to ciepło i dostosuj tempo.

PRAWDA
- Liczby, firmy i stan spraw bierz wyłącznie z SYTUACJI. Niczego nie wymyślaj; gdy czegoś nie wiesz, odeślij do panelu.
- Umiesz: przypomnieć w podanym terminie, wstrzymać codzienne maile owcy na czas zajętości lub wyjazdu, ustawić cel dnia,
  przygotowywać aplikacje w tle, pilnować odpowiedzi pracodawców. Aplikacje wysyłam dopiero po jej zatwierdzeniu w panelu.
  Nie obiecuj niczego innego.

SYTUACJA
{situation}

PAMIĘĆ (trwałe fakty z wcześniejszych rozmów)
{memory}

HISTORIA (ostatnie wiadomości; „Aga” i „Sebastian”)
{history}

NOWA WIADOMOŚĆ OD AGI ({channel})
{message}

Zwróć wyłącznie JSON:
{{"odpowiedz": "treść odpowiedzi",
  "przerwa_do": "RRRR-MM-DD — ostatni dzień, w którym owca ma nie wysyłać codziennych maili (dziś, gdy dziś nie da rady; ostatni dzień wyjazdu); pusty tekst, gdy bez zmian",
  "wznow": false,
  "przypomnij": {{"kiedy": "RRRR-MM-DD GG:MM", "co": "krótko o czym"}} albo null — tylko gdy Aga podała termin (teraz albo w odpowiedzi na Twoje pytanie); bez godziny przyjmij {hour},
  "cel": null albo liczba — gdy Aga podaje, ile aplikacji chce dziś zrobić,
  "zapamietaj": ["0–3 krótkich, trwałych faktów przydatnych w kolejnych rozmowach: dostępność, plany, preferencje co do pracy i ofert, co ją motywuje; bez spraw zdrowotnych i intymnych; bez powtórzeń z PAMIĘCI"]}}
„wznow”: true tylko wtedy, gdy Aga wraca wcześniej i chce działać.{feedback}"""


def _fmt_history(rows):
    out = []
    for r in rows:
        who = "Aga" if r["kto"] == "aga" else "Sebastian"
        text = re.sub(r"\s+", " ", r["tresc"])[:500]
        out.append(f"[{r['kiedy'][:16].replace('T', ' ')} · {r['kanal']}] {who}: {text}")
    return "\n".join(out) or "(to pierwsza rozmowa)"


def problems(text):
    t = text or ""
    out = []
    if not t.strip():
        out.append("odpowiedź jest pusta")
    if len(t) > 1100:
        out.append("odpowiedź jest za długa")
    if re.search(r"\b\w{2,}łeś\b|\bbyłeś\b|\bmógłbyś\b|\bchciałbyś\b|\bmusiałbyś\b", t):
        out.append("do Agi zwracaj się w rodzaju żeńskim (np. „mogłabyś”, „zrobiłaś”)")
    if re.search(r"\b(zapisałam|przypomniałam|przygotowałam|sprawdziłam|wysłałam|zrobiłam to dla ciebie)\b", t, re.I):
        out.append("o sobie (Sebastian) piszesz w rodzaju męskim („zapisałem”)")
    if re.search(r"\[(pominięte|e-mail|telefon|linkedin)\]", t):
        out.append("nie wstawiaj znaczników [pominięte]")
    if re.search(r"^\s*(droga|drogi|szanowna)\b", t, re.I):
        out.append("bez „Droga/Szanowna” na początku")
    return out


def _date(s):
    with contextlib.suppress(Exception):
        return dt.date.fromisoformat(str(s)[:10])
    return None


def _when(s, now):
    with contextlib.suppress(Exception):
        w = dt.datetime.strptime(str(s).strip()[:16].replace("T", " "), "%Y-%m-%d %H:%M").replace(tzinfo=now.tzinfo)
        if now < w <= now + dt.timedelta(days=60):
            return w
    return None


def fallback(ctx, c, text, kanal):
    """Gdy żaden model nie odpowie: proste, życzliwe odpowiedzi z regułami."""
    f = R.load_facts(ctx)
    hi = _hi(f)
    now = ctx.now()
    t = R.plain(text)
    hist = history(c, 4)
    asked = any(r["kto"] == "sebastian" and ASKED_WHEN.search(R.plain(r["tresc"])) for r in hist[-2:])
    when = parse_when(text, now)
    out = {"odpowiedz": "", "przerwa_do": "", "wznow": False, "przypomnij": None, "cel": None, "zapamietaj": []}
    if BACK.search(t):
        out["wznow"] = True
        out["odpowiedz"] = f"Super, że jesteś, {hi}! Wracamy do gry. Zajrzyj do panelu, czekają na Ciebie przygotowane aplikacje."
    elif AWAY.search(t):
        back = when.date() if when else None
        out["przerwa_do"] = ((back - dt.timedelta(days=1)) if back else now.date() + dt.timedelta(days=6)).isoformat()
        if when:
            out["przypomnij"] = {"kiedy": when.strftime("%Y-%m-%d %H:%M"), "co": "powrót do szukania pracy"}
            out["odpowiedz"] = (f"Udanego wyjazdu, {hi}! Do tego czasu nie zawracam Ci głowy, a {DAYS[when.weekday()]} "
                                f"{when.strftime('%d.%m')} przypomnę się z przygotowanymi ofertami.")
        else:
            out["odpowiedz"] = (f"Udanego wyjazdu, {hi}! Odpuszczam na ten czas poranne przypomnienia. Kiedy mam się do Ciebie odezwać? "
                                f"Napisz dzień, a przypomnę.")
    elif BUSY.search(t):
        out["przerwa_do"] = now.date().isoformat()
        if when:
            out["przypomnij"] = {"kiedy": when.strftime("%Y-%m-%d %H:%M"), "co": "aplikacje"}
            out["odpowiedz"] = f"Jasne, rozumiem. Dziś odpuszczam, a {DAYS[when.weekday()]} o {when.strftime('%H:%M')} przypomnę się z ofertami."
        else:
            out["odpowiedz"] = (f"Jasne, {hi}, rozumiem. Dziś już nie przypominam. Kiedy będziesz mogła usiąść do ofert na chwilę? "
                                f"Napisz dzień, a przypomnę.")
    elif when and asked:
        out["przypomnij"] = {"kiedy": when.strftime("%Y-%m-%d %H:%M"), "co": "aplikacje"}
        out["odpowiedz"] = f"Zapisane! Przypomnę się {DAYS[when.weekday()]} {when.strftime('%d.%m')} o {when.strftime('%H:%M')}."
    else:
        from . import owca as OW
        p = OW.progress(c, now.date())
        out["odpowiedz"] = (f"Dzięki, {hi}, przeczytałem. " +
                            (f"Na Twoje spojrzenie czeka {p['czeka']} {OW._plural(p['czeka'], 'aplikacja', 'aplikacje', 'aplikacji')} — "
                             "zerkniesz dziś choć na kilka?" if p["czeka"] else "Przygotowuję kolejne oferty i dam znać, gdy będą gotowe."))
    return out


def think(ctx, c, text, kanal):
    """Decyzja i odpowiedź (słownik jak w GUIDE) — model, a gdy zawiedzie, reguły."""
    from . import dokumenty as D
    f = R.load_facts(ctx)
    hour = R.hm(ctx.settings().get("owca_rano", "07:45"), (7, 45))
    hour = "09:00" if hour < dt.time(9, 0) else hour.strftime("%H:%M")
    hist = history(c)[:-1]                                         # bez właśnie zapisanej wiadomości Agi
    mem = "\n".join(f"- {m['fakt']}" for m in memory(c)[-40:]) or "(jeszcze nic)"
    length = "1–3 zdania" if kanal == "whatsapp" else "2–5 zdań"
    feedback = ""
    for attempt in range(2):
        prompt = GUIDE.format(hi=_hi(f), length=length, situation=situation(ctx, c), memory=mem, history=_fmt_history(hist),
                              channel={"whatsapp": "WhatsApp", "mail": "mail", "panel": "panel"}.get(kanal, kanal),
                              message=text[:3000], hour=hour, feedback=feedback)
        got = None
        with contextlib.suppress(Exception):
            got = D.write(ctx, prompt, max_tokens=700, temperature=0.6)
        if not isinstance(got, dict) or not str(got.get("odpowiedz") or "").strip():
            break
        bad = problems(str(got["odpowiedz"]))
        if not bad:
            return got, True
        feedback = "\n\nPOPRAW poprzednią wersję: " + "; ".join(bad) + "."
    return fallback(ctx, c, text, kanal), False


def apply(ctx, c, out, kanal):
    """Skutki odpowiedzi: przerwa, wznowienie, przypomnienie, cel dnia, pamięć."""
    from . import owca as OW
    now = ctx.now()
    done = []
    if out.get("wznow"):
        end_pause(c, ctx)
        done.append("przerwa zakończona")
    until = _date(out.get("przerwa_do"))
    if until and until >= now.date() and not out.get("wznow"):
        done.append(f"przerwa do {set_pause(c, ctx, until).isoformat()}")
    rem = out.get("przypomnij")
    if isinstance(rem, dict):
        when = _when(rem.get("kiedy"), now)
        if when:
            add_reminder(c, ctx, when, str(rem.get("co") or ""), "whatsapp" if kanal == "whatsapp" else "mail")
            done.append(f"przypomnienie {when.strftime('%d.%m %H:%M')}")
    with contextlib.suppress(TypeError, ValueError):
        if out.get("cel") not in (None, "", 0):
            done.append(f"cel {OW.set_goal(c, ctx, now.date(), int(out['cel']))}")
    if isinstance(out.get("zapamietaj"), list):
        remember(ctx, c, out["zapamietaj"][:3])
    return done


def crisis_reply(f):
    return (f"{_hi(f)}, bardzo dobrze, że to napisałaś. Teraz ważniejsza jesteś Ty niż jakiekolwiek oferty — odkładam wszystkie przypomnienia. "
            "Proszę, odezwij się dziś do kogoś bliskiego. Jeśli jest Ci bardzo ciężko, zadzwoń pod 116 123 (telefon zaufania dla dorosłych), "
            "a gdy grozi Ci niebezpieczeństwo — pod 112. Jestem tu, kiedy zechcesz pogadać.")


def reply_to(ctx, kanal, text, temat="", message_id=""):
    """Odpowiedź Sebastiana na wiadomość Agi (zapisuje obie strony w dzienniku). Zwraca (tekst, skutki)."""
    text = (text or "").strip()
    if not text:
        return "", []
    log(ctx, kanal, "aga", text, temat, message_id)
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        ensure(c)
        if CRISIS.search(R.plain(text)):
            set_pause(c, ctx, ctx.now().date() + dt.timedelta(days=3))
            answer, effects = crisis_reply(f), ["przerwa 3 dni"]
        else:
            out, by_model = think(ctx, c, text, kanal)
            effects = apply(ctx, c, out, kanal)
            answer = re.sub(r"\n{3,}", "\n\n", str(out["odpowiedz"]).strip())
    log(ctx, kanal, "sebastian", answer)
    return answer, effects


# ================================================================ kanały

AGA_QUOTE = re.compile(r"^(>|\s*(W dniu|Dnia|On .{0,80}wrote|.{0,80}napisał\(a\):|-{2,}\s*(Original|Oryginalna|Wiadomość)|"
                       r"Od:|From:|Wysłane z|Sent from|Owca Sebastian\s*$|🐑 Owca Sebastian))", re.I)


def strip_quote(text):
    out = []
    for line in (text or "").splitlines():
        if AGA_QUOTE.match(line):
            break
        out.append(line)
    return "\n".join(out).strip()


def aga_addresses(ctx, c):
    me, _ = R.mailboxes(c)
    f = R.load_facts(ctx)
    return {a.lower() for a in (me, (f.get("osoba") or {}).get("email")) if a}


def check_mail(ctx, send=None, fetch=None):
    """Czyta skrzynkę Sebastiana; na maile od Agi odpisuje w tym samym wątku. Zwraca liczbę odpowiedzi."""
    from . import poczta as P, odpowiedzi as A
    if not ctx.settings().get("rozmowa", True):
        return 0
    send, fetch = send or P.send, fetch or P.fetch_new
    with R.db(ctx) as c:
        me, seb = R.mailboxes(c)
        first = R.meta_get(c, "imap_uid_seb") == ""
        after = int(R.meta_get(c, "imap_uid_seb", "0") or 0)
        aga = aga_addresses(ctx, c)
    pwd = R.secret(ctx, "sebastian")
    if not seb or not pwd or not me:
        return 0
    msgs = fetch(seb, pwd, after_uid=after, since_days=2 if first else 7, limit=30)
    n = 0
    for m in msgs:
        with R.db(ctx) as c:
            ensure(c)
            R.meta_set(c, "imap_uid_seb", max(int(R.meta_get(c, "imap_uid_seb", "0") or 0), int(m["uid"])))
            c.commit()
            seen = m["message_id"] and c.execute("SELECT 1 FROM rozmowa WHERE message_id=?", (m["message_id"],)).fetchone()
        if seen or m.get("nasza") or (m["od"] or "").lower() not in aga:
            continue
        if first:
            with contextlib.suppress(Exception):                      # przy pierwszym czytaniu tylko świeże (ostatnia doba)
                if (ctx.now() - dt.datetime.fromisoformat(m["data"]).astimezone(ctx.now().tzinfo)).total_seconds() > 86400:
                    continue
        body = strip_quote(m["tresc"]) or m["temat"]
        answer, _ = reply_to(ctx, "mail", body, m["temat"], m["message_id"])
        if not answer:
            continue
        try:
            send(seb, pwd, m["od"], A.re_subject(m["temat"] or "Rozmowa"), answer + "\n\n— Owca Sebastian", name="Owca Sebastian",
                 in_reply_to=m["message_id"], references=m.get("references", ""),
                 html=MS.letter(answer, "Owca Sebastian", tagline="asystent rekrutacji"))
            n += 1
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: odpowiedź do Agi nie wyszła ({type(e).__name__})")
    return n


def on_whatsapp(ctx, msg):
    """Wiadomość od Agi na WhatsAppie (gdy jej numer jest na liście Sebastiana). Zwraca odpowiedź albo None."""
    from . import odpowiedzi as A
    text = (msg.get("text") or "").strip()
    user = msg.get("user") or {}
    if not text or text.startswith("/") or not ctx.settings().get("rozmowa", True):
        return None                                                    # „/…” = zwykły Sebastian
    with R.db(ctx) as c:
        if R.meta_get(c, "onboarding") != "gotowe":
            return None
    phone = re.sub(r"\D", "", str(user.get("phone", "")))
    if not phone or phone != A.aga_phone(ctx, R.load_facts(ctx)):
        return None
    answer, _ = reply_to(ctx, "whatsapp", text)
    return answer or None


def nudge_text(ctx, c, rem):
    """Treść przypomnienia, o które prosiła Aga."""
    from . import dokumenty as D, owca as OW
    f = R.load_facts(ctx)
    prompt = (f"Jesteś Sebastianem, życzliwym asystentem Agi w szukaniu pracy. Aga prosiła, żeby przypomnieć się jej teraz"
              f"{' (' + rem['co'] + ')' if rem['co'] else ''}. Napisz krótkie (2–3 zdania), ciepłe przypomnienie: nawiąż do rozmowy, "
              f"zaproponuj jeden konkretny, mały krok na teraz. O sobie w rodzaju męskim, do Agi w żeńskim, bez podpisu, bez nagłówka.\n\n"
              f"SYTUACJA\n{situation(ctx, c)}\n\nHISTORIA\n{_fmt_history(history(c, 8))}\n\nZwróć JSON: {{\"odpowiedz\": \"...\"}}")
    got = None
    with contextlib.suppress(Exception):
        got = D.write(ctx, prompt, max_tokens=400, temperature=0.6)
    text = str((got or {}).get("odpowiedz") or "").strip() if isinstance(got, dict) else ""
    if text and not problems(text):
        return text
    p = OW.progress(c, ctx.now().date())
    return f"Hej {_hi(f)}, przypominam się, tak jak prosiłaś. " + (f"Czeka na Ciebie {p['czeka']} {OW._plural(p['czeka'], 'przygotowana aplikacja', 'przygotowane aplikacje', 'przygotowanych aplikacji')} — "
                 "wystarczy 10 minut, żeby przejrzeć kilka." if p["czeka"] else "Mam dla Ciebie świeże oferty w przygotowaniu — zajrzysz dziś do panelu?")


def tick(ctx, send=None):
    """Wysyła przypomnienia, których termin minął (najwyżej jedno na obrót). Zwraca True, gdy coś wyszło."""
    from . import poczta as P, odpowiedzi as A
    send = send or P.send
    now = ctx.now()
    with R.db(ctx) as c:
        ensure(c)
        row = c.execute("SELECT * FROM rozmowa_przypomnienia WHERE wyslano='' AND kiedy<=? ORDER BY kiedy LIMIT 1",
                        (now.strftime("%Y-%m-%dT%H:%M"),)).fetchone()
        if not row:
            return False
        rem = dict(row)
        c.execute("UPDATE rozmowa_przypomnienia SET wyslano=? WHERE id=?", (R.stamp(ctx), rem["id"]))
        if pause_until(c, ctx):
            end_pause(c, ctx)                                          # umówiony powrót — owca wraca do codziennych maili
        c.commit()
        text = nudge_text(ctx, c, rem)
        me, seb = R.mailboxes(c)
    f = R.load_facts(ctx)
    ok = rem["kanal"] == "whatsapp" and A.whatsapp(ctx, f, text, dedupe=f"rozmowa:{rem['id']}", log_it=False)
    if not ok:
        sender, key = (seb, "sebastian") if seb and R.secret(ctx, "sebastian") else (me, "aga")
        if me and R.secret(ctx, key):
            with contextlib.suppress(Exception):
                send(sender, R.secret(ctx, key), me, "Przypominam się, tak jak prosiłaś", text + "\n\n— Owca Sebastian", name="Owca Sebastian",
                     html=MS.letter(text, "Owca Sebastian", tagline="asystent rekrutacji"))
                ok = True
    log(ctx, rem["kanal"] if ok else "mail", "sebastian", text)
    return bool(ok)
