"""Pamięć — „Sebastian uczy się o Tobie” (Sebastian 2.30).

Każdy użytkownik Sebastiana (Andrzej, Aga, asystent…) ma własną pamięć. Sebastian uczy się:
  • z rozmów na WhatsAppie — z tego, co mu piszecie i nagrywacie (dłuższe wiadomości, nie komendy),
  • z eksportów ChatGPT, Claude i Gemini (zip albo conversations.json / MyActivity.json) — tylko Wasze wiadomości,
  • z dowolnych plików (PDF, Word, Excel, PowerPoint, tekst, zdjęcia z tekstem, zip z plikami) i wklejonego tekstu,
  • z dotychczasowego Profilu wiedzy (nauka z poczty i Dysku) — raz, na start.
Pliki wrzuca się w panelu (zakładka „Uczy się o Tobie”), do folderu data/dodatki/pamiec/wrzuc-tutaj/<imię>/
albo poleceniem: python sebastian.py dodatek pamiec wgraj <plik albo folder> <imię>.

W tle (osobny wątek w usłudze WhatsApp) lokalny model przerabia kawałek po kawałku na fakty, łączy powtórki,
składa profil osoby w 7 kategoriach i układa pytania „Zrozumiałem, że … — dobrze?”. Codziennie o wybranej
godzinie wysyła kilka pytań na WhatsAppie; odpowiedzi („1 tak, 2 nie — …”) i poprawki z panelu trafiają do
księgi poprawek, która ma pierwszeństwo przy składaniu profilu. Nic nie jest kasowane.

Z pamięci korzysta Sebastian przy odpowiedziach na WhatsAppie (każdy widzi tylko swoją) oraz inne dodatki
(ctx.memory — uprawnienie „pamiec.odczyt”).
"""
import contextlib, datetime as dt, mimetypes, os, re, shutil, threading, time
from pathlib import Path

from . import biblioteka as B
from . import rdzen as R

START_WORKER = os.environ.get("SEBASTIAN_TESTY") != "1"      # testy: bez wątku, work_once wołane ręcznie
_W = {"thread": None, "last_chat": 0.0, "state": "", "ctx": None}
COMMANDISH = re.compile(r"^(pomoc|menu|zadania|lista|przeglad|pilne|poczta|kalendarz|jutro|dokumenty|status|cisza|wznow|"
                        r"zrobione|szczegoly|odpowiedz|pytania|pomysly|tresc|glosowki|przypomnij|przypomnienia|gwaranci|tak|nie|ok)\b")
WHAT_YOU_KNOW = re.compile(r"^(co o mnie wiesz|czego sie o mnie nauczyles|czego sie o mnie dowiedziales|moj profil|co wiesz o mnie)\W*$")
GUIDE_RE = re.compile(r"(?i)^\s*(?:zrób |zrob |stwórz |stworz |napisz |przygotuj )?(?:mi )?poradnik\s*(?:o|na temat|dla mnie o)?\s*[:\-–]?\s*(?P<temat>.+)$", re.S)
EXPLAIN_RE = re.compile(r"(?i)^\s*(?:wyjaśnij|wyjasnij|wytłumacz|wytlumacz|z biblioteki|z moich materiałów|z moich materialow)\s*(?:mi)?\s*[:\-–]?\s*(?P<temat>.+)$", re.S)
LIBRARY_RE = re.compile(r"^(biblioteka|moja biblioteka|biblioteka wiedzy)\W*$")
ASK_ME = re.compile(r"^(pytaj mnie|zadaj (mi )?pytania|masz (do mnie )?pytania|pytania o mnie)\W*$")


def con_of(ctx):
    return R.db(ctx.folder())


def users(ctx):
    base = []
    with contextlib.suppress(Exception):
        base = ctx.W.all_users()
    return R.with_extra(base, ctx.settings())


def owner_id(ctx):
    with contextlib.suppress(Exception):
        return re.sub(r"\D", "", ctx.W.C.WA_OWNER_PHONE or "")
    return ""


def pid_of(ctx, user):
    phone = (user or {}).get("phone") or ""
    return re.sub(r"\D", "", phone) or owner_id(ctx)


# ================================================================ praca w tle

def extractor(ctx):
    def extract(path):
        import learner as L
        L.bind(ctx.W.S)
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or ""
        return L.extract_text(path, {"name": path.name, "mime": mime})
    return extract


def asker(ctx, max_tokens=1500):
    return lambda prompt: ctx.ask(prompt, as_json=True, max_tokens=max_tokens, temperature=0.2)


def drop_folders(ctx, con):
    """Pliki wrzucone do wrzuc-tutaj/<imię>/ → źródła (plik przenoszony do wgrane/)."""
    n = 0
    base = ctx.folder() / "wrzuc-tutaj"
    for p in R.people(con):
        box = base / p["folder"]
        (box / "biblioteka").mkdir(parents=True, exist_ok=True)      # 2.35: kursy i książki → biblioteka wiedzy
        for f in sorted(box.rglob("*")):
            if not f.is_file() or f.name.startswith(".") or time.time() - f.stat().st_mtime < 15:
                continue                                       # jeszcze się kopiuje
            lib = "biblioteka" in f.relative_to(box).parts[:-1]
            target = ctx.folder() / "wgrane" / p["id"] / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{f.name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), target)
            if lib:
                B.add(con, p["id"], f.name, target)
            else:
                R.add_source(con, p["id"], "plik", f.name, target)
            n += 1
        for d in sorted((x for x in box.rglob("*") if x.is_dir() and x.name != "biblioteka"), reverse=True):
            with contextlib.suppress(OSError):
                d.rmdir()
    return n


def flush_chats(con, force=False):
    """Wiadomości z WhatsAppa → źródło „rozmowy z Sebastianem” (gdy zbierze się dość albo minie 6 h)."""
    n = 0
    for r in con.execute("SELECT osoba, SUM(LENGTH(tekst)) AS dl, MIN(ts) AS od FROM rozmowy WHERE zrodlo=0 GROUP BY osoba").fetchall():
        if not force and r["dl"] < 2500 and time.time() - r["od"] < 6 * 3600:
            continue
        rows = con.execute("SELECT * FROM rozmowy WHERE osoba=? AND zrodlo=0 ORDER BY ts", (r["osoba"],)).fetchall()
        text = "\n".join(f"[{dt.datetime.fromtimestamp(x['ts']):%d.%m %H:%M}] {x['tekst']}" for x in rows)
        sid = R.add_source(con, r["osoba"], "whatsapp", f"Rozmowy z Sebastianem {dt.datetime.fromtimestamp(r['od']):%d.%m}", text=text)
        con.executemany("UPDATE rozmowy SET zrodlo=? WHERE id=?", [(sid, x["id"]) for x in rows])
        con.commit()
        n += 1
    return n


def seed_from_learner(ctx, con):
    """Raz: dotychczasowy Profil wiedzy (nauka z poczty i Dysku) jako pierwsze źródło wiedzy o właścicielu."""
    if R.meta(con, "seed_nauka"):
        return 0
    R.meta(con, "seed_nauka", R.now_iso())
    con.commit()
    oid = owner_id(ctx)
    path = Path(ctx.W.S.DATA) / "learner" / "wyniki" / "Profil_wiedzy.md"
    if not oid or not R.person(con, oid) or not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if len(text) < 200:
        return 0
    R.add_source(con, oid, "nauka", "Profil wiedzy (nauka z poczty i Dysku)", text=text)
    return 1


def due_profile(ctx, con, pid):
    last = R.meta(con, f"profil:{pid}") or ""
    new = con.execute("SELECT COUNT(*) FROM fakty WHERE osoba=? AND utworzono>?", (pid, last)).fetchone()[0]
    changed = R.meta(con, f"zmiana:{pid}")
    return new >= int(ctx.settings().get("profil_co_faktow") or 25) or (bool(changed) or new > 0) and (
        not last or dt.datetime.fromisoformat(last) < dt.datetime.now().astimezone() - dt.timedelta(hours=6))


def work_once(ctx, extract=None, chat_pause=None):
    """Jeden krok pracy w tle. True = coś zrobiono (pracuj dalej od razu)."""
    with contextlib.closing(con_of(ctx)) as con:
        did = drop_folders(ctx, con) + flush_chats(con) + seed_from_learner(ctx, con)
        for job in con.execute("SELECT * FROM zlecenia WHERE status='czeka' ORDER BY id LIMIT 1").fetchall():
            _W["state"] = f"piszę: {job['rodzaj']} „{job['temat']}”"
            B.run_job(con, job, lambda prompt, tokens: ctx.ask(prompt, max_tokens=tokens, temperature=0.3), ctx.folder())
            return True
        for src in con.execute("SELECT * FROM zrodla WHERE status='nowe' AND sciezka<>'' ORDER BY id LIMIT 1").fetchall():
            _W["state"] = f"czytam: {src['nazwa']}"
            if (src["cel"] if "cel" in src.keys() else "osoba") == "biblioteka":
                B.index_source(con, src, extract)
            else:
                R.parse_source(con, src, extract)
            return True
        pause = float(ctx.settings().get("przerwa_po_rozmowie_s") if chat_pause is None else chat_pause)
        if time.time() - _W["last_chat"] < pause:              # ktoś właśnie rozmawia z Sebastianem — model dla niego
            return bool(did)
        chunk = R.next_chunk(con)
        if chunk:
            _W["state"] = f"uczę się: kawałek {chunk['nr']} źródła {chunk['zrodlo']}"
            R.digest_chunk(con, chunk, asker(ctx))
            return True
        for p in R.people(con):
            if due_profile(ctx, con, p["id"]):
                _W["state"] = f"składam profil: {p['imie']}"
                R.consolidate(con, p["id"], asker(ctx, 1200))
                R.make_questions(con, p["id"])
                return True
        _W["state"] = "czekam na nową wiedzę"
        return bool(did)


def worker(ctx):
    extract = extractor(ctx)
    while True:
        try:
            did = work_once(ctx, extract)
        except Exception as e:
            ctx.log.warning(f"Pamięć: {type(e).__name__}: {str(e)[:200]}")
            did = False
        time.sleep(1 if did else 20)


def ensure_worker(ctx):
    if not START_WORKER or not ctx.settings().get("nauka_w_tle", True):
        return
    t = _W["thread"]
    if t is None or not t.is_alive():
        _W["thread"] = threading.Thread(target=worker, args=(ctx,), name="pamiec", daemon=True)
        _W["thread"].start()


# ================================================================ pytania na WhatsAppie

def batch_text(p, qs):
    n = len(qs)
    head = f"🐑 *Sebastian uczy się o Tobie* i ma {n} {'pytanie' if n == 1 else 'pytania' if n < 5 else 'pytań'}:"
    body = "\n\n".join(f"{q['nr']}. {q['pytanie']}" for q in qs)
    how = ("Odpisz *tak* albo *nie — jak jest naprawdę*." if n == 1 else
           "Odpisz np. *1 tak, 2 nie — jak jest naprawdę, 3 tak* (albo *wszystko się zgadza*).")
    return f"{head}\n\n{body}\n\n{how}\nWszystkie pytania i to, co o Tobie wiem — w panelu: „Uczy się o Tobie”."


def send_batch(ctx, con, p, when=None):
    """Kilka pytań do osoby na WhatsAppie. Zwraca tekst albo ''."""
    when = when or ctx.now()
    stale = (when - dt.timedelta(hours=48)).isoformat(timespec="seconds")
    con.execute("UPDATE pytania SET status='czeka' WHERE osoba=? AND status='zadane' AND kanal='whatsapp' AND zadano<?", (p["id"], stale))
    if con.execute("SELECT 1 FROM pytania WHERE osoba=? AND status='zadane' AND kanal='whatsapp'", (p["id"],)).fetchone():
        return ""                                              # poprzednie jeszcze bez odpowiedzi — nie zasypuję
    R.make_questions(con, p["id"])
    qs = R.open_questions(con, p["id"], ("czeka",))[: int(ctx.settings().get("pytan_naraz") or 3)]
    if not qs:
        return ""
    for i, q in enumerate(qs, 1):
        q["nr"] = i
        con.execute("UPDATE pytania SET status='zadane', nr=?, partia=?, kanal='whatsapp', zadano=? WHERE id=?",
                    (i, when.date().isoformat(), when.isoformat(timespec="seconds"), q["id"]))
    con.commit()
    return batch_text(p, qs)


def deliver(ctx, con, p, text):
    if not text:
        return
    if p["id"] == owner_id(ctx) or p.get("rola") == "wlasciciel":
        ctx.send_text(text, "pytania")
    else:
        ctx.send_to(p["telefon"], text, "pytania")


def daily_questions(ctx, con):
    st = ctx.settings()
    if not st.get("pytania_przez_whatsapp", True) or ctx.in_quiet():
        return 0
    at = ctx.now()
    hh, mm = (int(x) for x in str(st.get("pytania_godzina") or "19:00").split(":")[:2])
    if (at.hour, at.minute) < (hh, mm):
        return 0
    sent = 0
    for p in R.people(con):
        key = f"wyslano:{p['id']}"
        if R.meta(con, key) == at.date().isoformat() or not p.get("telefon"):
            continue
        R.meta(con, key, at.date().isoformat())
        con.commit()
        text = send_batch(ctx, con, p, at)
        if text:
            deliver(ctx, con, p, text)
            sent += 1
    return sent


def deliver_jobs(ctx, con):
    """2.35: gotowe poradniki i wyjaśnienia zamówione na WhatsAppie → do osoby, która prosiła."""
    for j in con.execute("SELECT * FROM zlecenia WHERE kanal='whatsapp' AND status IN ('gotowe','blad') ORDER BY id").fetchall():
        p = R.person(con, j["osoba"])
        con.execute("UPDATE zlecenia SET status=? WHERE id=?", ("wyslane" if j["status"] == "gotowe" else "blad_wyslany", j["id"]))
        con.commit()
        if not p:
            continue
        owner = p["id"] == owner_id(ctx) or p.get("rola") == "wlasciciel"
        phone = None if owner else p["telefon"]
        if j["plik"] and Path(j["plik"]).exists():
            with contextlib.suppress(Exception):
                ctx.send_file(j["plik"], f"📚 Gotowe! Poradnik „{j['temat']}” z Twojej biblioteki wiedzy — w PDF poniżej.", phone)
                continue
        text = (f"📚 *{'Poradnik' if j['rodzaj'] == 'poradnik' else 'Wyjaśnienie'}: {j['temat']}*\n\n" if j["status"] == "gotowe" else "") + (j["wynik"] or "")
        for i in range(0, len(text), 3300):
            part = text[i:i + 3300]
            if owner:
                ctx.send_text(part, "biblioteka")
            else:
                ctx.send_to(p["telefon"], part, "biblioteka")


def tick(ctx):
    with contextlib.closing(con_of(ctx)) as con:
        if time.time() - float(R.meta(con, "osoby_sync") or 0) > 3600:
            R.sync_people(con, users(ctx))
            R.meta(con, "osoby_sync", str(time.time()))
            con.commit()
        daily_questions(ctx, con)
        deliver_jobs(ctx, con)
    ensure_worker(ctx)


# ================================================================ wiadomości

def handle(ctx, msg):
    text = (msg.get("text") or "").strip()
    if not text:
        return None
    _W["last_chat"] = time.time()
    pid = pid_of(ctx, msg.get("user"))
    t = R.norm(text)
    with contextlib.closing(con_of(ctx)) as con:
        if not R.person(con, pid):
            R.sync_people(con, users(ctx))
        p = R.person(con, pid)
        if not p:
            return None
        since = (ctx.now() - dt.timedelta(hours=72)).isoformat(timespec="seconds")
        asked = [q for q in R.open_questions(con, pid, ("zadane",)) if q["kanal"] == "whatsapp" and q["zadano"] >= since]
        if asked:
            res = R.parse_answers(text, [q["nr"] for q in asked])
            if res:
                by_nr = {q["nr"]: q for q in asked}
                ok, fixed, wrong = [], [], []
                for nr, verdict, corr in res:
                    R.answer(con, by_nr[nr]["id"], verdict, corr, "whatsapp")
                    (ok if verdict == "tak" else fixed if corr else wrong).append(str(nr))
                bits = ([f"✓ {', '.join(ok)}"] if ok else []) + ([f"poprawione: {', '.join(fixed)}"] if fixed else []) + \
                       ([f"skreślone: {', '.join(wrong)}"] if wrong else [])
                left = [q for q in R.open_questions(con, pid, ("zadane",)) if q["kanal"] == "whatsapp"]
                return (f"Dzięki, {R.first_name(p)}! 🐑 {' · '.join(bits)}. Zapamiętane." +
                        (f" Zostało jeszcze {len(left)} — odpisz, kiedy zechcesz." if left else ""))
        m = GUIDE_RE.match(text) or EXPLAIN_RE.match(text)
        if m:
            kind = "poradnik" if GUIDE_RE.match(text) else "wyjasnienie"
            topic = m.group("temat").strip(" .?!„”\"")
            if len(topic) < 3:
                return "O czym? Napisz np. *poradnik: jak prowadzić rozmowę z klientem* albo *wyjaśnij: IKZE*."
            if not B.sources(con, pid):
                return ("📚 Twoja biblioteka wiedzy jest jeszcze pusta. Wgraj kursy i książki w panelu: zakładka „Uczy się o Tobie” → "
                        "„Nakarm mnie wiedzą” → zaznacz „do biblioteki wiedzy”.")
            n = len(B.search(con, pid, topic, 14))
            if not n:
                return f"📚 W Twojej bibliotece nie znalazłem nic o „{topic}”. Spróbuj innymi słowami albo wgraj materiały na ten temat."
            B.queue(con, pid, kind, topic, "whatsapp")
            return (f"📚 Piszę {'poradnik' if kind == 'poradnik' else 'wyjaśnienie'} „{topic}” na podstawie Twoich materiałów "
                    f"({n} pasujących fragmentów). Przyślę {'PDF' if kind == 'poradnik' else 'odpowiedź'} za kilka minut.")
        if LIBRARY_RE.match(t):
            srcs = B.sources(con, pid)
            if not srcs:
                return "📚 Biblioteka wiedzy jest pusta — wgraj kursy i książki w panelu (Uczy się o Tobie → Nakarm mnie wiedzą)."
            return ("📚 *Twoja biblioteka wiedzy:*\n" + "\n".join(f"• {x['nazwa']}" + (f" ({x['rok']})" if x["rok"] else "") +
                                                               f" — {R.STATUS_PL.get(x['status'], x['status'])}" for x in srcs[:25]) +
                    "\n\nNapisz *poradnik: temat* albo *wyjaśnij: temat*.")
        if WHAT_YOU_KNOW.match(t):
            prof = R.profile_text(con, pid, limit=3200)
            s = R.stats(con, pid)
            if not prof:
                return f"Dopiero się o Tobie uczę ({s['fakty']} faktów, {s['w_kolejce']} kawałków w kolejce). Profil złożę niedługo 🐑"
            return f"*Co o Tobie wiem* ({s['fakty']} faktów, {s['potwierdzone']} potwierdzonych):\n\n{prof}"
        if ASK_ME.match(t):
            R.meta(con, f"wyslano:{pid}", ctx.now().date().isoformat())
            con.commit()
            return send_batch(ctx, con, p) or "Na razie nie mam do Ciebie pytań 🙂 Odezwę się, gdy się czegoś nowego nauczę."
        if ctx.settings().get("uczyc_z_rozmow", True) and len(text) >= 25 and not COMMANDISH.match(t):
            con.execute("INSERT INTO rozmowy(osoba, ts, tekst) VALUES(?,?,?)", (pid, time.time(), text[:4000]))
            con.commit()
    return None


def on_message(ctx, msg):
    return handle(ctx, msg)


def on_user_message(ctx, msg):
    return handle(ctx, msg)


def context(ctx, question, user):
    """Dla odpowiedzi Sebastiana na WhatsAppie: co wie o osobie, która pyta (tylko o niej)."""
    with contextlib.closing(con_of(ctx)) as con:
        pid = pid_of(ctx, user)
        out = R.profile_text(con, pid, question, 2500)
        lib = B.context(con, pid, question)              # 2.35: fragmenty jej kursów i książek
        return (out + "\n\n" + lib).strip() if lib else out


def memory(ctx, phone=None, query="", limit=3000):
    with contextlib.closing(con_of(ctx)) as con:
        return R.profile_text(con, re.sub(r"\D", "", phone or "") or owner_id(ctx), query, limit)


# ================================================================ polecenia w Terminalu

def _person_arg(ctx, con, args):
    R.sync_people(con, users(ctx))
    if args:
        p = R.find_person(con, " ".join(args))
        if not p:
            raise SystemExit(f"Nie znam osoby „{' '.join(args)}”. Osoby: " + ", ".join(x["imie"] for x in R.people(con)))
        return p
    return R.person(con, owner_id(ctx)) or (R.people(con) or [None])[0]


def _cmd_status(ctx, args):
    with contextlib.closing(con_of(ctx)) as con:
        R.sync_people(con, users(ctx))
        for p in R.people(con):
            s = R.stats(con, p["id"])
            print(f"{p['imie']} ({p['rola'] or '—'}): {s['fakty']} faktów, {s['potwierdzone']} potwierdzonych, "
                  f"{s['pytania']} pytań czeka, {s['zrodla']} źródeł, {s['w_kolejce']} kawałków w kolejce")
            print(f"   wrzucaj pliki do: {ctx.folder() / 'wrzuc-tutaj' / p['folder']}")
    print(f"Teraz: {_W['state'] or 'wątek nauki działa w usłudze WhatsApp'}")
    return 0


def _cmd_upload(ctx, args):
    if not args:
        print('Użycie: python sebastian.py dodatek pamiec wgraj ~/Downloads/chatgpt-eksport.zip "Aga"')
        return 1
    lib = "--biblioteka" in args
    args = [a for a in args if a != "--biblioteka"]
    src = Path(args[0]).expanduser()
    if not src.exists():
        print(f"Nie ma: {src}")
        return 1
    with contextlib.closing(con_of(ctx)) as con:
        p = _person_arg(ctx, con, args[1:])
        files = [src] if src.is_file() else [f for f in sorted(src.rglob("*")) if f.is_file() and not f.name.startswith(".")]
        for f in files:
            target = ctx.folder() / "wgrane" / p["id"] / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{f.name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)                            # oryginał zostaje na miejscu
            if lib:
                B.add(con, p["id"], f.name, target)
            else:
                R.add_source(con, p["id"], "plik", f.name, target)
    print(f"Dodane źródła: {len(files)} — dla: {p['imie']}" + (" (biblioteka wiedzy)" if lib else "") +
          ". Sebastian przerobi je w tle (postęp: status albo panel).")
    return 0


def _cmd_questions(ctx, args):
    with contextlib.closing(con_of(ctx)) as con:
        p = _person_arg(ctx, con, args)
        R.make_questions(con, p["id"])
        qs = R.open_questions(con, p["id"])
        print(f"Pytania do: {p['imie']} ({len(qs)})")
        for q in qs:
            print(f"  [{q['id']}] {q['pytanie']}")
        print("Odpowiedź: python sebastian.py dodatek pamiec odpowiedz 12 tak   |   odpowiedz 12 nie \"jak jest naprawdę\"")
    return 0


def _cmd_answer(ctx, args):
    if len(args) < 2 or not args[0].isdigit() or R.norm(args[1]) not in ("tak", "nie", "pomin"):
        print('Użycie: python sebastian.py dodatek pamiec odpowiedz 12 tak|nie|pomin ["poprawka"]')
        return 1
    with contextlib.closing(con_of(ctx)) as con:
        ok = R.answer(con, int(args[0]), R.norm(args[1]), " ".join(args[2:]), "terminal")
    print("Zapisane." if ok else "Nie ma takiego otwartego pytania.")
    return 0 if ok else 1


def _cmd_profile(ctx, args):
    with contextlib.closing(con_of(ctx)) as con:
        p = _person_arg(ctx, con, args)
        print(f"Co Sebastian wie o: {p['imie']}\n")
        print(R.profile_text(con, p["id"], limit=20000) or "(profil jeszcze niezłożony)")
    return 0


def _cmd_run(ctx, args):
    """Przetwórz teraz (bez czekania na usługę): przetworz [ile_kroków]."""
    n = int(args[0]) if args and args[0].isdigit() else 20
    extract = extractor(ctx)
    for i in range(n):
        if not work_once(ctx, extract, chat_pause=0):
            break
        print(f"{i + 1}. {_W['state']}")
    return _cmd_status(ctx, [])


def _cmd_settings(ctx, args):
    for k, v in ctx.settings().items():
        print(f"{k} = {v}")
    return 0


def _cmd_set(ctx, args):
    if len(args) < 2:
        print("Użycie: python sebastian.py dodatek pamiec ustaw pytania_godzina 20:00")
        return 1
    print(f"{args[0]} = {ctx.set_setting(args[0], ' '.join(args[1:]))}")
    return 0


def _cmd_guide(ctx, args):
    """poradnik "temat" [osoba] — od razu, w Terminalu (PDF w data/dodatki/pamiec/poradniki)."""
    if not args:
        print('Użycie: python sebastian.py dodatek pamiec poradnik "jak prowadzić rozmowę z klientem" Aga')
        return 1
    with contextlib.closing(con_of(ctx)) as con:
        p = _person_arg(ctx, con, args[1:])
        jid = B.queue(con, p["id"], "poradnik", args[0], "terminal")
        B.run_job(con, con.execute("SELECT * FROM zlecenia WHERE id=?", (jid,)).fetchone(),
                  lambda prompt, tokens: ctx.ask(prompt, max_tokens=tokens, temperature=0.3), ctx.folder())
        j = con.execute("SELECT * FROM zlecenia WHERE id=?", (jid,)).fetchone()
    print(j["wynik"])
    if j["plik"]:
        print(f"\nPDF: {j['plik']}")
    return 0


COMMANDS = {"poradnik": _cmd_guide, "status": _cmd_status, "wgraj": _cmd_upload, "pytania": _cmd_questions, "odpowiedz": _cmd_answer,
            "profil": _cmd_profile, "przetworz": _cmd_run, "ustawienia": _cmd_settings, "ustaw": _cmd_set}
