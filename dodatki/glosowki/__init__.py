"""Głosówki — podsumowania długich nagrań (Sebastian 2.29).

Przebieg:
  1. Obserwacja WhatsAppa zapisuje głosówki od innych osób już przepisane na tekst (mlx-whisper, lokalnie)
     razem z długością nagrania (od 2.29).
  2. Co 30 s dodatek zbiera głosówki jednej osoby wysłane „naraz” (odstępy do `przerwa_minut`). Paczka jest
     zamknięta, gdy od ostatniej głosówki minęło `przerwa_minut` — wtedy wiadomo, że ktoś skończył nagrywać.
  3. Gdy łączna długość ≥ `prog_sekund` (2 minuty): lokalny model robi podsumowanie — o czym, o co pyta,
     co jest do zrobienia — i Sebastian wysyła je właścicielowi, a zaraz potem pyta, czy przysłać całą treść.
  4. „tak” → cała treść (w częściach, jeśli długa); „nie” → nic; „treść 3” → dowolna wcześniejsza paczka.
  Jedyne działanie wstecz: przy pierwszym uruchomieniu — wszystkie głosówki od `wstecz_osoba` (Witold Michno)
  z dnia `wstecz_dzien` (22.11.2026), złożone w jedno podsumowanie (bez progu 2 minut).
  W godzinach ciszy podsumowania czekają do rana (chyba że `w_ciszy` = true).
  Nagrania nie są zapisywane — tylko tekst w lokalnej bazie na Macu.
"""
import contextlib, datetime as dt, json, re, sqlite3, time, unicodedata

YES = re.compile(r"^(tak|tak tak|chce|tak chce|pokaz|pokaz cala tresc|dawaj|poprosze|tak poprosze|jasne|pewnie|"
                 r"wyslij|tak wyslij|prosze|tak prosze|cala tresc|tresc|chetnie)\W*$")
NO = re.compile(r"^(nie|nie trzeba|nie dzieki|nie dziekuje|niepotrzebne|nie teraz|wystarczy|wystarczy podsumowanie)\W*$")
FULL = re.compile(r"^(tresc|cala tresc|transkrypcja|glosowk[ia]|nagrania)\s*(?:nr\.?\s*)?(\d+)\W*$")
LIST = re.compile(r"^(glosowki|podsumowania glosowek|lista glosowek)\W*$")
PART = 3300


def norm(text):
    t = unicodedata.normalize("NFKD", (text or "").lower().replace("ł", "l"))
    return re.sub(r"\s+", " ", "".join(ch for ch in t if not unicodedata.combining(ch))).strip(" .!,?")


def plural(n, one, few, many):
    return one if n == 1 else few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def mmss(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


# ================================================================ baza dodatku

def db(ctx):
    con = ctx.db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS uzyte(id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS paczki(
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat TEXT, osoba TEXT, od_ts INTEGER, do_ts INTEGER, ile INTEGER,
        sekundy REAL, szacunek INTEGER DEFAULT 0, wstecz INTEGER DEFAULT 0, ids TEXT, tresc TEXT,
        podsumowanie TEXT DEFAULT '', status TEXT DEFAULT 'czeka', proby INTEGER DEFAULT 0,
        utworzono TEXT, wyslano TEXT DEFAULT '', odpowiedz TEXT DEFAULT '');
    """)
    return con


def meta(con, k, v=None):
    if v is None:
        r = con.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None
    con.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (k, str(v)))


def watch_rows(ctx, since, until=None):
    """Głosówki od innych z obserwowanego WhatsAppa (tylko odczyt)."""
    ctx.need("whatsapp.obserwacja")
    path = ctx.W.home() / "obserwacja.sqlite3"
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(wmsg)")}
        sec = "sekundy" if "sekundy" in cols else "0 AS sekundy"
        groups = "" if ctx.settings().get("grupy") else "AND is_group=0 "
        return [dict(r) for r in con.execute(
            f"SELECT id, chat, chat_name, sender, sender_name, ts, text, {sec} FROM wmsg WHERE kind='voice' AND from_me=0 "
            f"{groups}AND ts>=? AND ts<? ORDER BY chat, sender, ts", (int(since), int(until or 4102444800)))]
    finally:
        con.close()


def seconds_of(ctx, r):
    """(sekundy, czy_szacunek). Bez zapisanej długości (głosówki sprzed 2.29) — szacunek z liczby słów."""
    if r.get("sekundy"):
        return float(r["sekundy"]), False
    words = len(re.findall(r"\w+", r.get("text") or ""))
    return words / float(ctx.settings().get("slow_na_sekunde") or 2.2), True


def name_match(r, names):
    who = norm(" ".join([r.get("sender_name") or "", r.get("chat_name") or ""]))
    return any(n and n in who for n in names)


def wanted(spec):
    return [norm(x) for x in re.split(r"[;|]", spec or "") if norm(x)]


def bursts(ctx, rows, gap=None):
    """Głosówki jednej osoby wysłane naraz (odstępy ≤ przerwa_minut) → paczki."""
    gap = gap if gap is not None else float(ctx.settings().get("przerwa_minut") or 5) * 60
    out, cur = [], []
    for r in rows:
        if r["text"].strip() == "[głosówka]":        # z historii telefonu — bez nagrania, nie da się przepisać
            continue
        if cur and (r["chat"], r["sender"]) == (cur[-1]["chat"], cur[-1]["sender"]) and r["ts"] - cur[-1]["ts"] <= gap:
            cur.append(r)
        else:
            if cur:
                out.append(cur)
            cur = [r]
    if cur:
        out.append(cur)
    return out


def collect(ctx, con, since, until=None, retro=False, now_ts=None, names=None):
    """Zamknięte paczki ≥ progu → tabela paczki (status czeka). Zwraca liczbę nowych.
    retro + names: wszystkie głosówki tych osób z okresu → jedna paczka na rozmowę, bez progu."""
    now_ts = now_ts or time.time()
    st = ctx.settings()
    gap = float(st.get("przerwa_minut") or 5) * 60
    used = {r["id"] for r in con.execute("SELECT id FROM uzyte")}
    rows = [r for r in watch_rows(ctx, since, until) if r["id"] not in used]
    if names is not None:
        rows = [r for r in rows if name_match(r, names)]
    new = 0
    for b in bursts(ctx, rows, gap=10 ** 9 if names is not None else None):
        if not retro and now_ts - b[-1]["ts"] < gap:
            continue                                     # ta osoba może jeszcze nagrywać
        con.executemany("INSERT OR IGNORE INTO uzyte(id) VALUES(?)", [(r["id"],) for r in b])
        secs = [seconds_of(ctx, r) for r in b]
        total = sum(s for s, _ in secs)
        if names is None and total < float(st.get("prog_sekund") or 120):
            continue
        who = b[0]["sender_name"] or b[0]["chat_name"] or ("+" + b[0]["sender"] if (b[0]["sender"] or "").isdigit() else b[0]["sender"]) or "?"
        tresc = json.dumps([{"ts": r["ts"], "s": s, "text": (r["text"] or "").strip()} for r, (s, _) in zip(b, secs)], ensure_ascii=False)
        con.execute("INSERT INTO paczki(chat, osoba, od_ts, do_ts, ile, sekundy, szacunek, wstecz, ids, tresc, utworzono) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (b[0]["chat"], who, b[0]["ts"], b[-1]["ts"], len(b), total, int(any(e for _, e in secs)), int(retro),
                     json.dumps([r["id"] for r in b]), tresc, ctx.now().isoformat(timespec="seconds")))
        new += 1
    con.commit()
    return new


# ================================================================ podsumowanie i wysyłka

def transcript(ctx, p, numbered=True):
    items = json.loads(p["tresc"] or "[]")
    tz = ctx.now().tzinfo
    out = []
    for i, it in enumerate(items, 1):
        head = f"🎤 {i}/{len(items)} · {dt.datetime.fromtimestamp(it['ts'], tz):%H:%M} · {mmss(it['s'])}" if numbered else ""
        body = it["text"] or "(nie udało się przepisać tej głosówki)"
        out.append(f"{head}\n{body}" if head else body)
    return "\n\n".join(out)


def summarize(ctx, p):
    owner = (ctx.owner_name() or "właściciel").split()[0]
    text = transcript(ctx, p, numbered=False)[:24000]
    prompt = f"""Jesteś asystentem {owner}a. Poniżej są głosówki, które {p['osoba']} nagrał(a) do {owner}a na WhatsAppie,
przepisane automatycznie (mogą być błędy rozpoznawania mowy — popraw je w myślach, nie cytuj ich).

Zwróć wyłącznie JSON:
{{"podsumowanie": "2–4 zdania po polsku: o czym mówi i w jakiej sprawie",
  "pyta_o": ["każde pytanie lub prośba skierowana do {owner}a — krótko, konkretnie"],
  "do_zrobienia": ["konkretne działania dla {owner}a wynikające z głosówek, zaczynające się od czasownika (np. „Oddzwoń do …”, „Wyślij …”, „Potwierdź …”), z terminem, jeśli padł"],
  "pilne": true albo false}}
Jeśli o nic nie pyta — "pyta_o": []. Jeśli nic nie trzeba robić — "do_zrobienia": ["Nic pilnego — wystarczy przeczytać"].
Nie dopisuj niczego, czego nie ma w nagraniach.

GŁOSÓWKI:
{text}"""
    out = ctx.ask(prompt, as_json=True, max_tokens=900, temperature=0.2)
    if not isinstance(out, dict) or not str(out.get("podsumowanie") or "").strip():
        return None
    lst = lambda v: [str(x).strip() for x in (v if isinstance(v, list) else [v] if v else []) if str(x).strip()][:8]
    return {"podsumowanie": str(out["podsumowanie"]).strip()[:900], "pyta_o": lst(out.get("pyta_o")),
            "do_zrobienia": lst(out.get("do_zrobienia")) or ["Nic pilnego — wystarczy przeczytać"], "pilne": bool(out.get("pilne"))}


def summary_text(ctx, p, s):
    owner = (ctx.owner_name() or "").split()[0]
    tz = ctx.now().tzinfo
    start = dt.datetime.fromtimestamp(p["od_ts"], tz)
    n = p["ile"]
    when = f"{start:%d.%m} o {start:%H:%M}" if p["wstecz"] or start.date() != ctx.now().date() else f"o {start:%H:%M}"
    length = ("ok. " if p["szacunek"] else "") + mmss(p["sekundy"]) + " min"
    lines = [f"Cześć{' ' + owner if owner else ''}! 🎤 *{p['osoba']}* nagrał(a) do Ciebie {n} {plural(n, 'głosówkę', 'głosówki', 'głosówek')} "
             f"({when}, razem {length})" + (" — *pilne*" if s and s.get("pilne") else "") + "."]
    if s:
        lines += ["", f"*O czym:* {s['podsumowanie']}"]
        if s["pyta_o"]:
            lines += ["", "*Pyta o:*"] + [f"• {x}" for x in s["pyta_o"]]
        lines += ["", "*Do zrobienia:*"] + [f"✅ {x}" for x in s["do_zrobienia"]]
    else:
        lines += ["", "Nie udało się zrobić podsumowania (lokalny model nie odpowiada) — całą treść możesz przeczytać niżej."]
    return "\n".join(lines) + f"\n\n_(nr {p['id']})_"


def deliver(ctx, con, now_ts=None):
    """Wysyła podsumowania paczek, które czekają (poza ciszą). Zwraca liczbę wysłanych."""
    if ctx.in_quiet() and not ctx.settings().get("w_ciszy"):
        return 0
    sent = 0
    for p in con.execute("SELECT * FROM paczki WHERE status='czeka' ORDER BY id").fetchall():
        s = None
        with contextlib.suppress(Exception):
            s = summarize(ctx, p)
        if s is None and p["proby"] < 3:                 # model chwilowo niedostępny — spróbuję przy kolejnych tikach
            con.execute("UPDATE paczki SET proby=proby+1 WHERE id=?", (p["id"],))
            con.commit()
            continue
        ctx.send_text(summary_text(ctx, p, s), "podsumowanie")
        ctx.send_text(f"Chcesz przeczytać całą treść głosówek od {p['osoba']}? Odpisz *tak* — albo w dowolnym momencie *treść {p['id']}*.",
                      "pytanie")
        con.execute("UPDATE paczki SET status='wyslana', podsumowanie=?, wyslano=? WHERE id=?",
                    (json.dumps(s, ensure_ascii=False) if s else "", ctx.now().isoformat(timespec="seconds"), p["id"]))
        con.commit()
        sent += 1
    return sent


def retro_window(ctx):
    day = str(ctx.settings().get("wstecz_dzien") or "").strip()
    if not day:
        return None
    with contextlib.suppress(ValueError):
        start = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(0), ctx.now().tzinfo)
        return start.timestamp(), (start + dt.timedelta(days=1)).timestamp()
    return None


def tick(ctx):
    now_ts = ctx.now().timestamp()
    with contextlib.closing(db(ctx)) as con:
        start = meta(con, "start")
        if start is None:                                # pierwsze uruchomienie: jedyne działanie wstecz
            start = str(int(now_ts))
            meta(con, "start", start)
            con.commit()
            win, names = retro_window(ctx), wanted(ctx.settings().get("wstecz_osoba"))
            if win and names and win[0] < now_ts:
                n = collect(ctx, con, win[0], min(win[1], now_ts), retro=True, now_ts=now_ts, names=names)
                ctx.log.info(f"Głosówki: wstecz ({ctx.settings().get('wstecz_dzien')}) — paczek do podsumowania: {n}")
                if not n:
                    who = re.split(r"[;|]", ctx.settings().get("wstecz_osoba") or "")[0].strip()
                    ctx.send_text(f"🎤 Szukałem głosówek od {who} z {dt.date.fromisoformat(ctx.settings()['wstecz_dzien']):%d.%m}, "
                                  "ale obserwacja WhatsAppa ich nie zapisała (albo kontakt nazywa się inaczej). "
                                  "Na Macu: python sebastian.py dodatek glosowki sprawdz — pokaże, czyje głosówki są zapisane.", "wstecz")
        collect(ctx, con, int(start), now_ts=now_ts)
        deliver(ctx, con, now_ts)


# ================================================================ odpowiedzi właściciela

def full_parts(ctx, p):
    tz = ctx.now().tzinfo
    start = dt.datetime.fromtimestamp(p["od_ts"], tz)
    head = f"📝 *Cała treść — {p['osoba']}* ({p['ile']} {plural(p['ile'], 'głosówka', 'głosówki', 'głosówek')}, {start:%d.%m %H:%M}, nr {p['id']})\n\n"
    text = head + transcript(ctx, p)
    parts, cur = [], ""
    for para in text.split("\n\n"):
        while len(para) > PART:                          # bardzo długa pojedyncza głosówka — tnę po zdaniach
            cut = para.rfind(". ", 0, PART)
            cut = cut + 1 if cut > PART // 2 else PART
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(para[:cut].strip())
            para = para[cut:].strip()
        if len(cur) + len(para) + 2 > PART and cur:
            parts.append(cur)
            cur = para
        else:
            cur = (cur + "\n\n" + para) if cur else para
    if cur:
        parts.append(cur)
    if len(parts) > 1:
        parts = [f"{x}\n\n_(część {i}/{len(parts)})_" for i, x in enumerate(parts, 1)]
    return parts


def send_full(ctx, con, p):
    for part in full_parts(ctx, p):
        ctx.send_text(part, "tresc")
    con.execute("UPDATE paczki SET status='przeczytana', odpowiedz='tak' WHERE id=?", (p["id"],))
    con.commit()
    return True


def list_text(ctx, con, limit=10):
    rows = con.execute("SELECT * FROM paczki ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        return "Nie było jeszcze długich głosówek do podsumowania 🙂"
    tz = ctx.now().tzinfo
    out = ["*Ostatnie długie głosówki:*"]
    for p in rows:
        s = json.loads(p["podsumowanie"]) if p["podsumowanie"] else {}
        about = (s.get("podsumowanie") or "").split(". ")[0][:110]
        out.append(f"{p['id']}. {dt.datetime.fromtimestamp(p['od_ts'], tz):%d.%m %H:%M} · *{p['osoba']}* · "
                   f"{('ok. ' if p['szacunek'] else '') + mmss(p['sekundy'])} min" + (f" — {about}" if about else ""))
    return "\n".join(out) + "\n\nCała treść: *treść 3*"


def asked_last(ctx):
    """Czy ostatnia wiadomość Sebastiana do właściciela to nasze pytanie „chcesz przeczytać całą treść?”."""
    con = getattr(ctx, "_con", None)
    if con is None:
        return False
    with contextlib.suppress(Exception):
        r = con.execute("SELECT purpose FROM outbox WHERE COALESCE(to_phone,'')='' ORDER BY id DESC LIMIT 1").fetchone()
        return bool(r) and str(r[0]).startswith("glosowki:")
    return False


def on_message(ctx, msg):
    t = norm(msg["text"])
    if not t or len(t.split()) > 5:
        return None
    with contextlib.closing(db(ctx)) as con:
        m = FULL.match(t)
        if m:
            p = con.execute("SELECT * FROM paczki WHERE id=?", (int(m.group(2)),)).fetchone()
            if not p:
                return f"Nie mam paczki głosówek nr {m.group(2)}. Lista: *głosówki*"
            return send_full(ctx, con, p)
        if LIST.match(t):
            return list_text(ctx, con)
        # „tak”/„nie” łapię tylko, gdy to odpowiedź na nasze pytanie: było ostatnie albo padło w ciągu 2 godzin
        hours = 24 if asked_last(ctx) else 2
        since = (ctx.now() - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
        open_ = con.execute("SELECT * FROM paczki WHERE status='wyslana' AND wyslano>=? ORDER BY id DESC", (since,)).fetchall()
        if not open_:
            return None
        if YES.match(t):
            if len(open_) > 1:
                return "Od kogo? " + " · ".join(f"*treść {p['id']}* — {p['osoba']}" for p in open_[:5])
            return send_full(ctx, con, open_[0])
        if NO.match(t):
            con.executemany("UPDATE paczki SET status='pominieta', odpowiedz='nie' WHERE id=?", [(p["id"],) for p in open_])
            con.commit()
            return f"Jasne, nie wysyłam 👍 Gdybyś chciał później: *treść {open_[0]['id']}*."
    return None


# ================================================================ polecenia w Terminalu

def _cmd_list(ctx, args):
    with contextlib.closing(db(ctx)) as con:
        print(list_text(ctx, con, 30).replace("*", ""))
    return 0


def _cmd_full(ctx, args):
    if not args or not args[0].isdigit():
        print("Użycie: python sebastian.py dodatek glosowki tresc 3")
        return 1
    with contextlib.closing(db(ctx)) as con:
        p = con.execute("SELECT * FROM paczki WHERE id=?", (int(args[0]),)).fetchone()
        if not p:
            print("Nie ma takiej paczki.")
            return 1
        print("\n\n".join(full_parts(ctx, p)).replace("*", ""))
    return 0


def _cmd_retro(ctx, args):
    """wstecz "Imię" [RRRR-MM-DD] — podsumuj (i wyślij na WhatsAppie) wszystkie głosówki tej osoby z danego dnia."""
    if not args:
        print('Użycie: python sebastian.py dodatek glosowki wstecz "Witek" 2026-11-22')
        return 1
    day = dt.date.fromisoformat(args[1]) if len(args) > 1 else ctx.now().date()
    start = dt.datetime.combine(day, dt.time(0), ctx.now().tzinfo).timestamp()
    with contextlib.closing(db(ctx)) as con:
        if meta(con, "start") is None:
            meta(con, "start", str(int(ctx.now().timestamp())))
        n = collect(ctx, con, start, start + 86400, retro=True, names=wanted(args[0]))
        sent = deliver(ctx, con)
    print(f"Paczek: {n}, wysłanych podsumowań: {sent}." + ("" if n else " Nie znalazłem głosówek tej osoby z tego dnia — sprawdź: sprawdz " + day.isoformat()))
    return 0 if n else 1


def _cmd_check(ctx, args):
    day = ctx.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if args:
        day = dt.datetime.combine(dt.date.fromisoformat(args[0]), dt.time(0), ctx.now().tzinfo)
    prog = float(ctx.settings().get("prog_sekund") or 120)
    found = 0
    for b in bursts(ctx, watch_rows(ctx, day.timestamp(), day.timestamp() + 86400)):
        secs = [seconds_of(ctx, r) for r in b]
        total = sum(s for s, _ in secs)
        who = b[0]["sender_name"] or b[0]["chat_name"] or b[0]["sender"]
        mark = ("PODSUMOWAŁBYM" if total >= prog else "za krótko") + ("" if all((r["text"] or "").strip() for r in b) else " · część nieprzepisana")
        print(f"{dt.datetime.fromtimestamp(b[0]['ts'], ctx.now().tzinfo):%H:%M}  {who}: {len(b)} głosówek, "
              f"{('ok. ' if any(e for _, e in secs) else '') + mmss(total)} min — {mark}")
        found += 1
    if not found:
        print("Dziś nie ma jeszcze głosówek od innych (albo obserwacja WhatsAppa nie jest połączona).")
    return 0


def _cmd_settings(ctx, args):
    for k, v in ctx.settings().items():
        print(f"{k} = {v}")
    return 0


def _cmd_set(ctx, args):
    if len(args) < 2:
        print("Użycie: python sebastian.py dodatek glosowki ustaw prog_sekund 180")
        return 1
    print(f"{args[0]} = {ctx.set_setting(args[0], ' '.join(args[1:]))}")
    return 0


COMMANDS = {"lista": _cmd_list, "tresc": _cmd_full, "sprawdz": _cmd_check, "wstecz": _cmd_retro, "ustawienia": _cmd_settings, "ustaw": _cmd_set}
