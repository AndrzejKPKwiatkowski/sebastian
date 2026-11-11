"""Rekrutacja — panel Agi (osobny serwer, dostępny w sieci Tailscale) i praca w tle.

Panel Sebastiana (127.0.0.1:8765) zostaje nietknięty. Ten panel ma własne hasło, własną sesję i widzi wyłącznie
dane dodatku Rekrutacja.
"""
import contextlib, datetime as dt, hmac, json, os, random, re, secrets, subprocess, threading, time
from pathlib import Path

from . import dokumenty as D, formularze as F, odpowiedzi as A, oferty as O, poczta as P, rdzen as R, zrodla as Z

HERE = Path(__file__).resolve().parent
STEPS = ["Powitanie", "Twoja skrzynka", "Skrzynka Sebastiana", "Twoje dane", "Narzędzia", "Czego szukasz", "Jak mam pracować", "Gotowe"]
OPEN_ENDPOINTS = {"login", "first_run", "healthz"}


# ================================================================ przygotowanie kompletu dokumentów

def app_dir(ctx, aid):
    p = ctx.folder() / "aplikacje" / str(aid)
    p.mkdir(parents=True, exist_ok=True)
    return p


def photo_path(ctx, f):
    p = ctx.folder() / (f["osoba"].get("zdjecie") or "zdjecie.jpg")
    return p if p.exists() else None


def render_files(ctx, f, a, letter, selection, rodo=""):
    """Zapisuje CV i list jako PDF w data/dodatki/rekrutacja/aplikacje/<id>/; zwraca nazwy plików."""
    folder = app_dir(ctx, a["id"])
    for old in folder.glob("*.pdf"):
        old.unlink()
    base = f"{R.slug(f['osoba'].get('imie', ''), 'CV')}_{R.slug(f['osoba'].get('nazwisko', ''), 'x')}"
    firm = R.slug(a["firma"], "aplikacja")
    cv, li = f"{base}_CV_{firm}.pdf", f"{base}_List_{firm}.pdf"
    D.render_cv(f, selection, folder / cv, photo=photo_path(ctx, f), rodo=rodo or None)
    D.render_letter(f, letter, folder / li, firma=a["firma"], stanowisko="" if a["zrodlo"] == "spontaniczna" else a["stanowisko"],
                    today=ctx.now().date(), rodo=rodo or None)
    return cv, li


def prepare(ctx, aid):
    """Cały przebieg dla jednej aplikacji: pobranie ogłoszenia → dane → CV → list i mail → kontroler prawdy."""
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        a = dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone())
        R.set_status(c, ctx, aid, "przygotowywanie", blad="")
    notes, warn, found_mails, title = [], [], [], ""
    try:
        if a["url"] and not a["tresc"].strip():
            try:
                a["tresc"], title, found_mails = O.fetch(a["url"])
            except RuntimeError as e:
                notes.append(str(e))
        if a["tresc"].strip():
            found_mails = found_mails or O.emails(a["tresc"])
            info = O.analyze(ctx, f, a["tresc"], title, a["url"])
            for k in ("firma", "stanowisko", "miasto"):
                a[k] = a[k].strip() or info[k]                          # to, co wpisała Aga, ma pierwszeństwo
            a["email"] = a["email"].strip() or info["email"] or (found_mails[0] if found_mails and a["zrodlo"] != "auto" else "")
            a["ocena"], a["ocena_opis"], a["rodo"] = info["ocena"], info["uzasadnienie"], info["rodo"]
            warn = info["ostrzezenia"]
        a["klucz"] = R.dedupe_key(a["firma"], a["stanowisko"])
        if "kanal" not in a or not a["kanal"]:
            a["kanal"] = "{}"
        with R.db(ctx) as c:
            dup = R.find_duplicate(c, a["firma"], a["stanowisko"], a["url"], skip_id=aid, zrodlo=a["zrodlo"])
            if dup:
                R.set_status(c, ctx, aid, "duplikat", firma=a["firma"], stanowisko=a["stanowisko"], miasto=a["miasto"], klucz=a["klucz"],
                             tresc=a["tresc"], notatka=f"To ta sama oferta co aplikacja nr {dup}.")
                return "duplikat"
        if a["zrodlo"] == "auto":
            st = ctx.settings()
            why = ""
            if a.get("ocena") is not None and a["ocena"] < int(st.get("prog_dopasowania", 55)):
                why = f"za słabe dopasowanie ({a['ocena']}%)"
            elif warn:
                why = "w ogłoszeniu dominuje sprzedaż albo obsługa klienta"
            elif not R.in_area(a["miasto"], int(f["warunki"].get("dojazd_km") or 50)):
                why = f"za daleko ({a['miasto']})"
            elif not a["tresc"].strip():
                why = "nie udało się odczytać ogłoszenia"
            if why:
                with R.db(ctx) as c:
                    R.set_status(c, ctx, aid, "odrzucona", firma=a["firma"], stanowisko=a["stanowisko"], miasto=a["miasto"], tresc=a["tresc"],
                                 klucz=a["klucz"], ocena=a.get("ocena"), ocena_opis=a.get("ocena_opis") or "", notatka="Pominięta automatycznie: " + why)
                return "odrzucona"
        if not a["firma"] and not a["stanowisko"]:
            notes.append("Nie udało się ustalić firmy ani stanowiska. Uzupełnij je, a przygotuję dokumenty.")
            with R.db(ctx) as c:
                R.set_status(c, ctx, aid, "do_uzupelnienia", tresc=a["tresc"], uwagi=json.dumps(notes, ensure_ascii=False))
            return "do_uzupelnienia"
        selection = D.select_for_offer(ctx, f, a) if a["tresc"].strip() else D.default_selection(f)
        letter, mail, by_model = D.compose(ctx, f, a)
        notes += D.check(ctx, f, a, letter, mail, by_model=by_model)
        if not by_model:
            notes.append("Model nie odpowiedział, więc list i mail są z prostego szablonu. Warto je przeczytać i dopisać zdanie od siebie.")
        cv, li = render_files(ctx, f, a, letter, selection, a.get("rodo") or "")
        ch = F.channel(a)
        suspect = any(n.startswith(("Liczba", "Narzędzie", "Język", "Określenie", "Do sprawdzenia", "W tekście")) for n in notes)
        if ch["typ"] == "brak":
            notes.insert(0, "Brakuje adresu e-mail pracodawcy i linku do formularza. Wpisz adres, a wyślę mailem.")
            status = "do_uzupelnienia"
        elif ch["typ"] == "formularz":
            notes.insert(0, "Ogłoszenie nie podaje adresu e-mail — aplikacja idzie przez formularz na stronie. Poniżej masz gotowy zestaw do wklejenia.")
            status = "formularz"
        else:
            status = "do_sprawdzenia" if suspect else "do_zatwierdzenia"
        st = ctx.settings()
        auto_ok = st.get("autopilot") and status == "do_zatwierdzenia" and not warn and (
            a["zrodlo"] == "spontaniczna" or (a.get("ocena") or 0) >= int(st.get("prog_autopilota", 75)))
        if auto_ok:
            status = "zatwierdzona"
            notes.append("Zatwierdzona przez autopilota (wysokie dopasowanie, kontrola prawdy bez uwag).")
        with R.db(ctx) as c:
            R.set_status(c, ctx, aid, status, firma=a["firma"], stanowisko=a["stanowisko"], miasto=a["miasto"], email=a["email"],
                         tresc=a["tresc"], klucz=a["klucz"], ocena=a.get("ocena"), ocena_opis=a.get("ocena_opis") or "",
                         rodo=a.get("rodo") or "", ostrzezenia=json.dumps(warn, ensure_ascii=False),
                         uwagi=json.dumps(notes, ensure_ascii=False), wybor=json.dumps(selection), temat=D.subject(f, a),
                         mail=mail, list=letter, cv_plik=cv, list_plik=li, kanal=json.dumps(ch))
        return status
    except Exception as e:
        ctx.log.exception("Rekrutacja: przygotowanie aplikacji %s", aid)
        with R.db(ctx) as c:
            R.set_status(c, ctx, aid, "blad", blad=f"{type(e).__name__}: {str(e)[:300]}")
        return "blad"


# ================================================================ wysyłka i raport

def window(ctx, st, now=None):
    """Czy teraz wolno wysyłać (godziny, dni robocze)."""
    now = now or ctx.now()
    a, _, b = str(st.get("godziny", "08:00-16:00")).partition("-")
    if st.get("tylko_dni_robocze", True) and now.weekday() >= 5:
        return False
    return R.hm(a) <= now.time() < R.hm(b, (16, 0))


def sent_today(c, ctx):
    day = ctx.now().date().isoformat()
    return c.execute("SELECT COUNT(*) FROM aplikacje WHERE substr(wyslano,1,10)=?", (day,)).fetchone()[0]


SENDING = threading.Lock()          # trzymany przez cały czas wysyłki; restart panelu czeka, aż się zwolni


def _gap(st):
    lo = float(st.get("odstep_min", 4))
    return random.uniform(lo, max(lo, float(st.get("odstep_max", 9)))) * 60


def send_one(ctx, send=None):
    """Wysyła najstarszą zatwierdzoną aplikację, jeśli wolno. Zwraca id albo None.

    Aplikacja jest najpierw „zajmowana” (zatwierdzona → wysylanie jednym warunkowym UPDATE), więc żaden drugi obrót,
    proces ani restart nie wyśle jej drugi raz. Błąd „na pewno nie wyszło” wraca do kolejki; błąd „mogło wyjść”
    zatrzymuje aplikację do sprawdzenia przez Agę w Wysłanych."""
    send = send or P.send
    st = ctx.settings()
    with SENDING:
        with R.db(ctx) as c:
            if st.get("wstrzymane") or R.meta_get(c, "onboarding") != "gotowe" or not window(ctx, st):
                return None
            if sent_today(c, ctx) >= int(st.get("limit_dzienny", 70)):
                return None
            if float(R.meta_get(c, "nastepna_wysylka", "0") or 0) > time.time():
                return None
            row = c.execute("SELECT * FROM aplikacje WHERE status='zatwierdzona' ORDER BY zmieniono, id LIMIT 1").fetchone()
            if not row:
                return None
            claimed = c.execute("UPDATE aplikacje SET status='wysylanie', zmieniono=? WHERE id=? AND status='zatwierdzona'",
                                (R.stamp(ctx), row["id"])).rowcount
            c.commit()
            if not claimed:
                return None
            a = dict(row)
            me, _ = R.mailboxes(c)
        f = R.load_facts(ctx)
        folder = app_dir(ctx, a["id"])
        files = [folder / a["cv_plik"], folder / a["list_plik"]]
        ch = F.channel(a)
        if ch["typ"] == "recruitee":
            ok, why = (F.recruitee_apply(f, a, files[0], files[1], a["list"]) if all(p.exists() for p in files)
                       else (False, "Brakuje plików PDF — przygotuj dokumenty ponownie."))
            with R.db(ctx) as c:
                if ok:
                    R.set_status(c, ctx, a["id"], "wyslana_recznie", wyslano=R.stamp(ctx))
                    R.note(c, ctx, a["id"], "wysłana przez formularz Recruitee")
                else:
                    R.set_status(c, ctx, a["id"], "formularz", blad=why)
                R.meta_set(c, "nastepna_wysylka", time.time() + _gap(st))
            return a["id"] if ok else None
        problem = ""
        pwd = R.secret(ctx, "aga")
        if not me or not pwd:
            problem = "Skrzynka Agi nie jest podłączona (Ustawienia → Skrzynki)."
        elif not all(p.exists() for p in files):
            problem = "Brakuje plików PDF — przygotuj dokumenty ponownie."
        elif not R.EMAIL_OK.match(a["email"] or ""):
            problem = "Brak adresu e-mail pracodawcy."
        if problem:
            with R.db(ctx) as c:
                R.set_status(c, ctx, a["id"], "blad", blad=problem)
            return None
        try:
            mid = send(me, pwd, a["email"], a["temat"], a["mail"], files, name=R.full_name(f))
        except P.AuthFailed:
            with R.db(ctx) as c:                                  # kolejka zostaje, wysyłka czeka na ponowne podłączenie
                R.set_status(c, ctx, a["id"], "zatwierdzona")
                R.meta_set(c, "problem_poczty", "Gmail odrzucił hasło aplikacji Twojej skrzynki. Podłącz ją ponownie w Ustawieniach.")
                R.meta_set(c, "nastepna_wysylka", time.time() + 1800)
            return None
        except P.NotSent as e:
            ctx.log.warning(f"Rekrutacja: wysyłka {a['id']} odłożona: {e}")
            with R.db(ctx) as c:                                  # chwilowy problem: wraca do kolejki, ponowię za 15 minut
                R.set_status(c, ctx, a["id"], "zatwierdzona")
                R.meta_set(c, "nastepna_wysylka", time.time() + 900)
            return None
        except P.Uncertain as e:
            with R.db(ctx) as c:
                R.set_status(c, ctx, a["id"], "blad", blad=f"{e} Sprawdź w Gmailu (Wysłane), czy wiadomość wyszła, zanim zatwierdzisz ją ponownie.")
                R.meta_set(c, "nastepna_wysylka", time.time() + 300)
            return None
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: wysyłka {a['id']} nieudana: {type(e).__name__}: {str(e)[:160]}")
            with R.db(ctx) as c:
                R.set_status(c, ctx, a["id"], "blad", blad=f"Wysyłka się nie udała: {str(e)[:250]}")
                R.meta_set(c, "nastepna_wysylka", time.time() + 120)
            return None
        with R.db(ctx) as c:
            R.set_status(c, ctx, a["id"], "wyslana", wyslano=R.stamp(ctx), message_id=mid or "")
            R.meta_set(c, "nastepna_wysylka", time.time() + _gap(st))
            R.meta_set(c, "problem_poczty", "")
        return a["id"]


def report_text(ctx):
    f = R.load_facts(ctx)
    today = ctx.now().date().isoformat()
    with R.db(ctx) as c:
        sent = c.execute("SELECT firma,stanowisko,status FROM aplikacje WHERE substr(wyslano,1,10)=? ORDER BY wyslano", (today,)).fetchall()
        total = c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))})", R.SENT).fetchone()[0]
        todo = c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.TODO))})", R.TODO).fetchone()[0]
        queue = c.execute("SELECT COUNT(*) FROM aplikacje WHERE status='zatwierdzona'").fetchone()[0]
        invites = c.execute("SELECT COUNT(*) FROM aplikacje WHERE status IN ('zaproszenie','rozmowa','oferta')").fetchone()[0]
        replies = c.execute("SELECT w.rodzaj, a.firma FROM wiadomosci w LEFT JOIN aplikacje a ON a.id=w.aplikacja_id WHERE substr(w.utworzono,1,10)=? "
                            "AND w.rodzaj IN ('zaproszenie','oferta','pytanie','zadanie','odmowa')", (today,)).fetchall()
        open_q = c.execute("SELECT COUNT(*) FROM pytania WHERE status='otwarte'").fetchone()[0]
        drafts = c.execute("SELECT COUNT(*) FROM wiadomosci WHERE status='nowa' AND wazne=1").fetchone()[0]
        found = c.execute("SELECT COUNT(*) FROM aplikacje WHERE zrodlo='auto' AND substr(utworzono,1,10)=?", (today,)).fetchone()[0]
    todo += open_q + drafts
    name = f["osoba"].get("imie") or "Aga"
    lines = [f"Cześć {('Ago' if name.lower().startswith('agn') or name.lower() == 'aga' else name)},", "",
             f"dzisiaj wysłałem {len(sent)} {_plural(len(sent), 'aplikację', 'aplikacje', 'aplikacji')}."]
    lines += [f"  • {r['firma'] or '(firma)'} — {r['stanowisko'] or 'zapytanie o współpracę'}" for r in sent]
    if replies:
        lines += ["", "Odpowiedzi od pracodawców:"]
        lines += [f"  • {r['firma'] or 'firma'}: {A.KINDS.get(r['rodzaj'], r['rodzaj'])}" for r in replies]
    if found:
        lines += ["", f"Znalazłem dziś {found} nowych ogłoszeń (te słabo pasujące pomijam sam)."]
    lines += ["", f"Łącznie wysłanych: {total}. Zaproszenia i rozmowy: {invites}."]
    if queue:
        lines.append(f"W kolejce na kolejny dzień roboczy: {queue}.")
    lines.append(f"Czeka na Ciebie w panelu: {todo}." if todo else "Nic nie czeka na Twoją decyzję.")
    url = panel_url(ctx)
    if url:
        lines += ["", f"Panel: {url}"]
    lines += ["", "Dobrego wieczoru,", "Sebastian"]
    return f"Rekrutacja: {len(sent)} dziś, {total} łącznie" + (f", {todo} do decyzji" if todo else ""), "\n".join(lines)


def _plural(n, one, few, many):
    return one if n == 1 else (few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many)


def evening_report(ctx, send=None, force=False):
    send = send or P.send
    st = ctx.settings()
    now = ctx.now()
    with R.db(ctx) as c:
        if R.meta_get(c, "onboarding") != "gotowe":
            return False
        if not force and (R.meta_get(c, "raport_dnia") == now.date().isoformat() or now.time() < R.hm(st.get("raport", "20:00"), (20, 0))):
            return False
        me, seb = R.mailboxes(c)
    sender, key = (seb, "sebastian") if seb and R.secret(ctx, "sebastian") else (me, "aga")
    if not me or not R.secret(ctx, key):
        return False
    subject, body = report_text(ctx)
    try:
        send(sender, R.secret(ctx, key), me, subject, body, name="Sebastian")
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: raport nie wyszedł: {type(e).__name__}: {str(e)[:160]}")
        return False
    if not force:
        with R.db(ctx) as c:
            R.meta_set(c, "raport_dnia", now.date().isoformat())
    return True


def _due(c, key, every_s):
    if time.time() - float(R.meta_get(c, key, "0") or 0) < every_s:
        return False
    R.meta_set(c, key, time.time())
    return True


def work_once(ctx):
    """Jeden obrót pracy w tle: źródła, przygotowanie jednej aplikacji, wysyłka, skrzynka, przypomnienia, raport."""
    st = ctx.settings()
    with R.db(ctx) as c:
        if R.meta_get(c, "onboarding") != "gotowe":
            return
        day = ctx.now().date().isoformat()
        prepared_today = c.execute("SELECT COUNT(*) FROM aplikacje WHERE zrodlo IN ('auto','spontaniczna') AND substr(zmieniono,1,10)=? "
                                   "AND status NOT IN ('nowa','odrzucona','duplikat')", (day,)).fetchone()[0]
        waiting = c.execute("SELECT COUNT(*) FROM aplikacje WHERE status IN ('nowa','zatwierdzona','do_zatwierdzenia','do_sprawdzenia')").fetchone()[0]
        search = st.get("szukanie", True) and _due(c, "ostatnie_szukanie", 1800)
        inbox = _due(c, "ostatnia_skrzynka", 60 * float(st.get("skrzynka_co_minut", 10)))
    target = int(st.get("limit_dzienny", 70))
    if search and not st.get("wstrzymane"):
        with contextlib.suppress(Exception):
            Z.discover(ctx, max_new=max(0, target * 2 - waiting))
        if waiting < target and st.get("spontaniczne", True):
            with contextlib.suppress(Exception):
                Z.spontaneous_fill(ctx, max(0, min(10, target - waiting)))
    with R.db(ctx) as c:
        row = c.execute("SELECT id FROM aplikacje WHERE status='nowa' AND zrodlo NOT IN ('auto','spontaniczna') ORDER BY id LIMIT 1").fetchone()
        if not row and prepared_today < int(target * 1.3):
            row = c.execute("SELECT id FROM aplikacje WHERE status='nowa' ORDER BY id LIMIT 1").fetchone()
    if row:
        prepare(ctx, row["id"])
    send_one(ctx)
    if inbox:
        try:
            A.check_inbox(ctx)
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: skrzynka: {type(e).__name__}: {str(e)[:160]}")
        if window(ctx, st) and not st.get("wstrzymane"):
            with contextlib.suppress(Exception):
                A.pending_thanks(ctx)
            with contextlib.suppress(Exception):
                A.follow_ups(ctx)
    evening_report(ctx)


def worker(ctx, stop):
    import fcntl
    lock = open(ctx.folder() / ".praca.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        ctx.log.warning("Rekrutacja: praca w tle działa już w innym procesie — ten proces tylko pokazuje panel.")
        return
    with R.db(ctx) as c:                                     # po restarcie: przerwane przygotowania wracają do kolejki
        c.execute("UPDATE aplikacje SET status='nowa' WHERE status='przygotowywanie'")
        for r in c.execute("SELECT id FROM aplikacje WHERE status='wysylanie'").fetchall():
            R.set_status(c, ctx, r["id"], "blad", blad="Wysyłka została przerwana (restart). Sprawdź w Gmailu (Wysłane), czy wiadomość wyszła, zanim zatwierdzisz ją ponownie.")
        c.commit()
    while not stop.is_set():
        try:
            work_once(ctx)
        except Exception:
            ctx.log.exception("Rekrutacja: praca w tle")
            stop.wait(30)
        stop.wait(4)


# ================================================================ adres w sieci Tailscale

def _tailscale(*args):
    for exe in ("tailscale", "/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        with contextlib.suppress(Exception):
            r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
    return ""


def tailscale_ip():
    out = _tailscale("ip", "-4")
    m = re.search(r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", out)
    if m:
        return m.group(0)
    with contextlib.suppress(Exception):
        r = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=8)
        for ip in re.findall(r"inet (100\.\d{1,3}\.\d{1,3}\.\d{1,3})", r.stdout):
            if 64 <= int(ip.split(".")[1]) <= 127:
                return ip
    return ""


def tailscale_name():
    with contextlib.suppress(Exception):
        return json.loads(_tailscale("status", "--json"))["Self"]["DNSName"].rstrip(".")
    return ""


def panel_url(ctx):
    with contextlib.suppress(Exception), R.db(ctx) as c:
        return R.meta_get(c, "adres_panelu")
    return ""


# ================================================================ aplikacja Flask

def make_app(ctx, hosts=None):
    from flask import Flask, abort, flash, g, redirect, render_template, request, send_file, session, url_for
    from werkzeug.security import check_password_hash, generate_password_hash

    app = Flask(__name__, template_folder=str(HERE / "szablony"), static_folder=None)
    key_path = ctx.folder() / "sesja.key"
    if not key_path.exists():
        key_path.write_text(secrets.token_hex(32), encoding="utf-8")
        with contextlib.suppress(Exception):
            key_path.chmod(0o600)
    app.secret_key = key_path.read_text(encoding="utf-8").strip()
    app.config.update(SESSION_COOKIE_NAME="rekrutacja", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=dt.timedelta(days=30), MAX_CONTENT_LENGTH=4 * 1024 * 1024)
    app.jinja_env.globals.update(STATUS=R.STATUS, STEPS=STEPS, TOOLS=R.TOOLS, LEVELS=R.LEVELS, WANT=R.WANT, AVOID=R.AVOID)
    app.jinja_env.filters["loads"] = lambda s: json.loads(s or "[]")
    app.jinja_env.filters["dzien"] = lambda s: (s or "")[:16].replace("T", " ")
    allowed = hosts                                                           # None = bez sprawdzania (testy)

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    app.jinja_env.globals["csrf"] = csrf

    def onboarding_step(c):
        v = R.meta_get(c, "onboarding", "1")
        return None if v == "gotowe" else max(1, min(len(STEPS), int(v or 1)))

    @app.before_request
    def protect():
        if allowed is not None and request.host.split(":")[0].lower() not in allowed:
            abort(403)
        if request.method == "POST" and request.endpoint not in ("login", "first_run"):
            if not hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "-")):
                abort(400)
        if request.endpoint in OPEN_ENDPOINTS:
            return
        if not session.get("ok"):
            return redirect(url_for("login"))
        g.db = ctx.db()
        R.migrate(g.db)
        step = onboarding_step(g.db)
        g.onboarding = step
        if step and request.endpoint not in ("welcome", "preview_cv", "logout"):
            return redirect(url_for("welcome", k=step))

    @app.teardown_request
    def close(_):
        if "db" in g:
            g.pop("db").close()

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.route("/healthz")
    def healthz():
        return "ok"

    # ---------------------------------------------------------------- logowanie
    def throttled(c):
        return float(R.meta_get(c, "blokada_do", "0") or 0) > time.time()

    def failed(c):
        n = int(R.meta_get(c, "bledne_logowania", "0") or 0) + 1
        R.meta_set(c, "bledne_logowania", n)
        if n >= 5:
            R.meta_set(c, "blokada_do", time.time() + 300)
            R.meta_set(c, "bledne_logowania", 0)

    @app.route("/start/<token>", methods=["GET", "POST"])
    def first_run(token):
        with R.db(ctx) as c:
            good = R.meta_get(c, "token_startowy")
            if not good or not hmac.compare_digest(good, token) or throttled(c):
                if good:
                    failed(c)
                return render_template("login.html", mode="zly_link"), 403
            error = ""
            if request.method == "POST":
                a, b = request.form.get("haslo", ""), request.form.get("haslo2", "")
                if len(a) < 8:
                    error = "Hasło powinno mieć co najmniej 8 znaków."
                elif a != b:
                    error = "Hasła różnią się od siebie. Wpisz je jeszcze raz."
                else:
                    R.meta_set(c, "haslo", generate_password_hash(a))
                    R.meta_set(c, "token_startowy", "")
                    session.clear()
                    session.permanent = True
                    session["ok"] = True
                    return redirect(url_for("home"))
            return render_template("login.html", mode="nowe", error=error)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = ""
        with R.db(ctx) as c:
            stored = R.meta_get(c, "haslo")
            if request.method == "POST":
                if throttled(c):
                    error = "Za dużo prób. Odczekaj 5 minut i spróbuj ponownie."
                elif stored and check_password_hash(stored, request.form.get("haslo", "")):
                    R.meta_set(c, "bledne_logowania", 0)
                    session.clear()
                    session.permanent = True
                    session["ok"] = True
                    return redirect(url_for("home"))
                else:
                    failed(c)
                    error = "To hasło nie pasuje."
            return render_template("login.html", mode="login" if stored else "brak", error=error)

    @app.route("/wyloguj", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---------------------------------------------------------------- formularze bazy faktów (onboarding i ustawienia)
    def lines(name):
        return [x.strip(" \t•-–") for x in request.form.get(name, "").splitlines() if x.strip(" \t•-–")]

    def save_data(f):
        for k in ("imie", "nazwisko", "email", "telefon", "adres", "miasto", "linkedin"):
            f["osoba"][k] = request.form.get("o_" + k, "").strip()
        jobs = []
        for i in range(int(request.form.get("ile_stanowisk", 0))):
            if request.form.get(f"d{i}_usun"):
                continue
            jobs.append({"stanowisko": request.form.get(f"d{i}_stanowisko", "").strip(), "firma": request.form.get(f"d{i}_firma", "").strip(),
                         "miejsce": request.form.get(f"d{i}_miejsce", "").strip(), "od": request.form.get(f"d{i}_od", "").strip(),
                         "do": request.form.get(f"d{i}_do", "").strip(), "punkty": lines(f"d{i}_punkty")})
        f["doswiadczenie"] = jobs
        edu = []
        for i in range(int(request.form.get("ile_szkol", 0))):
            edu.append({"uczelnia": request.form.get(f"w{i}_uczelnia", "").strip(), "kierunek": request.form.get(f"w{i}_kierunek", "").strip(),
                        "tytul": request.form.get(f"w{i}_tytul", "").strip(), "okres": request.form.get(f"w{i}_okres", "").strip()})
        f["wyksztalcenie"] = edu
        f["kursy"], f["jezyki"], f["profil"] = lines("kursy"), lines("jezyki"), lines("profil")
        if not f["osoba"]["imie"] or not f["osoba"]["nazwisko"] or not R.EMAIL_OK.match(f["osoba"]["email"]):
            return "Uzupełnij imię, nazwisko i poprawny adres e-mail."
        if len(f["profil"]) < 2:
            return "Zostaw co najmniej dwa zdania w profilu zawodowym — z nich składam początek CV."
        R.save_facts(ctx, f)
        return ""

    def save_tools(f):
        tools = []
        for i, name in enumerate(R.TOOLS):
            if request.form.get(f"t{i}"):
                tools.append({"nazwa": name, "poziom": request.form.get(f"t{i}_poziom", "")})
        for line in lines("inne_narzedzia"):
            name, _, level = line.partition("–") if "–" in line else line.partition(" - ")
            tools.append({"nazwa": name.strip(), "poziom": level.strip() if level.strip() in R.LEVELS else ""})
        f["narzedzia"] = tools
        f["umiejetnosci"] = lines("umiejetnosci")
        f["prawo_jazdy"] = bool(request.form.get("prawo_jazdy"))
        if len(f["umiejetnosci"]) < 3:
            return "Wpisz co najmniej trzy umiejętności (każdą w osobnej linii)."
        R.save_facts(ctx, f)
        return ""

    def save_criteria(f):
        f["kryteria"]["chce"] = [x for i, x in enumerate(R.WANT) if request.form.get(f"c{i}")] + lines("chce_inne")
        f["kryteria"]["nie_chce"] = [x for i, x in enumerate(R.AVOID) if request.form.get(f"n{i}")] + lines("nie_chce_inne")
        w = f["warunki"]
        for k in ("umowa", "etat", "min_netto", "dostepnosc", "uwagi"):
            w[k] = request.form.get("w_" + k, "").strip()
        with contextlib.suppress(ValueError):
            w["dojazd_km"] = max(0, min(300, int(request.form.get("w_dojazd_km", 50))))
        w["zdalna"], w["poza_krakowem"] = bool(request.form.get("w_zdalna")), bool(request.form.get("w_poza_krakowem"))
        if not f["kryteria"]["chce"]:
            return "Zaznacz przynajmniej jeden rodzaj pracy, którego szukasz."
        R.save_facts(ctx, f)
        return ""

    def save_work():
        for key in ("autopilot", "szukanie", "spontaniczne", "podziekowania", "przypomnienia", "whatsapp"):
            ctx.set_setting(key, "tak" if request.form.get(key) else "nie")
        with contextlib.suppress(ValueError):
            ctx.set_setting("limit_dzienny", max(1, min(70, int(request.form.get("limit_dzienny", 70)))))

    def connect_box(which):
        """Sprawdza logowanie i zapisuje hasło w pęku kluczy. which: 'aga' albo 'sebastian'."""
        addr, pwd = request.form.get("adres", "").strip().lower(), request.form.get("haslo", "")
        ok, msg = app.config.get("TEST_LOGIN", P.test_login)(addr, pwd)
        if not ok:
            return msg
        R.set_secret(ctx, which, P.clean_password(pwd))
        R.meta_set(g.db, "poczta_" + which, addr)
        return ""

    # ---------------------------------------------------------------- pierwsze uruchomienie
    @app.route("/witaj/<int:k>", methods=["GET", "POST"])
    def welcome(k):
        step = g.onboarding
        if step is None:
            return redirect(url_for("home"))
        if k > step:
            return redirect(url_for("welcome", k=step))
        f = R.load_facts(ctx)
        error = ""
        if request.method == "POST":
            if request.form.get("wstecz") and k > 1:
                return redirect(url_for("welcome", k=k - 1))
            if k == 2:
                error = connect_box("aga")
            elif k == 3 and not request.form.get("pomin"):
                error = connect_box("sebastian")
            elif k == 4:
                error = save_data(f)
            elif k == 5:
                error = save_tools(f)
            elif k == 6:
                error = save_criteria(f)
            elif k == 7:
                save_work()
            if not error:
                if k >= len(STEPS):
                    R.meta_set(g.db, "onboarding", "gotowe")
                    return redirect(url_for("home"))
                R.meta_set(g.db, "onboarding", max(step, k + 1))
                return redirect(url_for("welcome", k=k + 1))
            f = R.load_facts(ctx) if k in (2, 3) else f
        me, seb = R.mailboxes(g.db)
        return render_template("witaj.html", k=k, f=f, error=error, me=me, seb=seb or "sebastian.k.kwiatkowski@gmail.com",
                               seb_ok=bool(seb), has_photo=bool(photo_path(ctx, f)))

    @app.route("/podglad-cv.pdf")
    def preview_cv():
        f = R.load_facts(ctx)
        path = ctx.folder() / "podglad_cv.pdf"
        D.render_cv(f, D.default_selection(f), path, photo=photo_path(ctx, f))
        return send_file(path, mimetype="application/pdf", max_age=0)

    # ---------------------------------------------------------------- strony
    def counts(c):
        q = lambda statuses: c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(statuses))})", statuses).fetchone()[0]
        msgs = c.execute("SELECT COUNT(*) FROM wiadomosci WHERE status='nowa' AND wazne=1").fetchone()[0]
        qs = c.execute("SELECT COUNT(*) FROM pytania WHERE status='otwarte'").fetchone()[0]
        return {"dzis": sent_today(c, ctx), "lacznie": q(R.SENT), "do_zrobienia": q(R.TODO), "kolejka": q(("zatwierdzona",)),
                "w_przygotowaniu": q(("nowa", "przygotowywanie")), "zaproszenia": q(("zaproszenie", "rozmowa", "oferta")),
                "odpowiedzi": msgs + qs, "pytania": qs}

    @app.context_processor
    def common():
        if "db" not in g:
            return {}
        st = ctx.settings()
        return {"n": counts(g.db), "st": st, "okno": window(ctx, st), "problem_poczty": R.meta_get(g.db, "problem_poczty")}

    @app.route("/")
    def home():
        rows = g.db.execute("SELECT * FROM aplikacje WHERE status NOT IN ('duplikat') ORDER BY zmieniono DESC LIMIT 8").fetchall()
        return render_template("dzis.html", rows=rows, tab="dzis", me=R.mailboxes(g.db)[0])

    @app.route("/dodaj", methods=["POST"])
    def add():
        url, firma = request.form.get("url", "").strip(), request.form.get("firma", "").strip()
        tresc, email = request.form.get("tresc", "").strip(), request.form.get("email", "").strip().lower()
        stanowisko = request.form.get("stanowisko", "").strip()
        spont = request.form.get("rodzaj") == "spontaniczna"
        if url and not re.match(r"^https?://", url):
            url = "https://" + url
        if spont and not (firma and R.EMAIL_OK.match(email)):
            flash("Do aplikacji bez ogłoszenia potrzebuję nazwy firmy i adresu e-mail.")
            return redirect(url_for("home"))
        if not spont and not (url or tresc):
            flash("Wklej link do ogłoszenia albo jego treść.")
            return redirect(url_for("home"))
        if email and not R.EMAIL_OK.match(email):
            flash("Ten adres e-mail wygląda na niepełny.")
            return redirect(url_for("home"))
        dup = R.find_duplicate(g.db, firma, stanowisko, url, zrodlo="spontaniczna" if spont else "oferta")
        if dup:
            flash("Ta oferta już jest na liście — otwieram ją.")
            return redirect(url_for("detail", aid=dup))
        now = R.stamp(ctx)
        cur = g.db.execute("INSERT INTO aplikacje(utworzono,zmieniono,status,zrodlo,url,firma,stanowisko,email,tresc,klucz) VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (now, now, "nowa", "spontaniczna" if spont else "oferta", url, firma, "" if spont else stanowisko, email, tresc[:20000],
                            R.dedupe_key(firma, stanowisko)))
        R.note(g.db, ctx, cur.lastrowid, "dodana przez Agę")
        g.db.commit()
        return redirect(url_for("detail", aid=cur.lastrowid))

    @app.route("/do-zrobienia")
    def todo():
        rows = g.db.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.TODO))}) ORDER BY zmieniono DESC", R.TODO).fetchall()
        return render_template("lista.html", rows=rows, tab="todo", title="Do zrobienia", empty="Wszystko załatwione. Nic nie czeka na Twoją decyzję.")

    @app.route("/aplikacje")
    def all_apps():
        q, status = request.args.get("q", "").strip(), request.args.get("status", "")
        sql, params = "SELECT * FROM aplikacje WHERE 1=1", []
        if q:
            sql += " AND (firma LIKE ? OR stanowisko LIKE ? OR email LIKE ? OR miasto LIKE ?)"
            params += [f"%{q}%"] * 4
        if status in R.STATUS:
            sql += " AND status=?"
            params.append(status)
        rows = g.db.execute(sql + " ORDER BY zmieniono DESC LIMIT 500", params).fetchall()
        return render_template("lista.html", rows=rows, tab="all", title="Wszystkie aplikacje", q=q, status=status, search=True,
                               empty="Nie ma jeszcze żadnej aplikacji. Dodaj pierwszą ofertę na stronie „Dziś”.")

    def get(aid):
        a = g.db.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone()
        if not a:
            abort(404)
        return a

    @app.route("/aplikacja/<int:aid>")
    def detail(aid):
        a = get(aid)
        hist = g.db.execute("SELECT * FROM historia WHERE aplikacja_id=? ORDER BY id DESC LIMIT 30", (aid,)).fetchall()
        msgs = g.db.execute("SELECT * FROM wiadomosci WHERE aplikacja_id=? ORDER BY id DESC", (aid,)).fetchall()
        return render_template("aplikacja.html", a=a, hist=hist, msgs=msgs, tab="", kit=F.kit(R.load_facts(ctx), a) if a["status"] == "formularz" else [],
                               KINDS=A.KINDS, editable=a["status"] in ("do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "formularz", "blad", "zatwierdzona", "odrzucona"))

    @app.route("/aplikacja/<int:aid>", methods=["POST"])
    def act(aid):
        a = dict(get(aid))
        what = request.form.get("co", "")
        if a["status"] == "wysylanie" and what != "notatka":
            flash("Ta aplikacja jest właśnie wysyłana. Odśwież stronę za chwilę.")
            return redirect(url_for("detail", aid=aid))
        if what in ("zapisz", "zatwierdz", "ponow") and a["status"] not in R.SENT:
            fields = {k: request.form.get(k, a[k]).strip() for k in ("firma", "stanowisko", "miasto", "email", "temat", "mail", "list") if k in request.form}
            fields["email"] = fields.get("email", a["email"]).lower()
            if "tresc" in request.form and request.form["tresc"].strip():
                fields["tresc"] = request.form["tresc"].strip()[:20000]
            a.update(fields)
            fields["klucz"] = R.dedupe_key(a["firma"], a["stanowisko"])
            g.db.execute(f"UPDATE aplikacje SET {','.join(k + '=?' for k in fields)}, zmieniono=? WHERE id=?", (*fields.values(), R.stamp(ctx), aid))
            g.db.commit()
        if what == "ponow" and a["status"] not in R.SENT + ("wysylanie",):
            R.set_status(g.db, ctx, aid, "nowa", uwagi="[]", zrodlo="oferta" if a["zrodlo"] == "auto" else a["zrodlo"])
        elif what in ("zapisz", "zatwierdz") and a["status"] not in R.SENT and a["status"] != "nowa":
            f = R.load_facts(ctx)
            if a["list"].strip() and a["cv_plik"]:
                with contextlib.suppress(Exception):
                    sel = json.loads(a["wybor"] or "null")
                    cv, li = render_files(ctx, f, a, a["list"], sel, a["rodo"])
                    g.db.execute("UPDATE aplikacje SET cv_plik=?, list_plik=? WHERE id=?", (cv, li, aid))
                    g.db.commit()
            notes = D.rule_check(f, a, a["list"]) + D.rule_check(f, a, a["mail"])
            if what == "zatwierdz":
                if F.channel(a)["typ"] not in ("mail", "recruitee"):
                    flash("Wpisz adres e-mail pracodawcy — bez niego nie mam dokąd wysłać.")
                elif not a["list"].strip() or not a["mail"].strip() or not a["cv_plik"]:
                    flash("Dokumenty nie są jeszcze gotowe. Kliknij „Przygotuj ponownie”.")
                else:
                    R.set_status(g.db, ctx, aid, "zatwierdzona", uwagi=json.dumps(notes, ensure_ascii=False), blad="")
                    R.note(g.db, ctx, aid, "zatwierdzona przez Agę")
                    g.db.commit()
                    flash("Zatwierdzone. Wyślę w najbliższym oknie wysyłki." if not window(ctx, ctx.settings()) else "Zatwierdzone. Wysyłam w ciągu kilku minut.")
                    return redirect(url_for("todo"))
            else:
                if a["status"] == "do_uzupelnienia" and R.EMAIL_OK.match(a["email"]) and a["cv_plik"]:
                    R.set_status(g.db, ctx, aid, "do_sprawdzenia" if notes else "do_zatwierdzenia", uwagi=json.dumps(notes, ensure_ascii=False))
                flash("Zapisane.")
        elif what == "cofnij" and a["status"] == "zatwierdzona":
            R.set_status(g.db, ctx, aid, "do_zatwierdzenia")
        elif what == "odrzuc" and a["status"] not in R.SENT:
            R.set_status(g.db, ctx, aid, "odrzucona")
            return redirect(url_for("todo"))
        elif what == "recznie" and a["status"] not in R.SENT:
            R.set_status(g.db, ctx, aid, "wyslana_recznie", wyslano=R.stamp(ctx))
        elif what == "status" and a["status"] in R.SENT and request.form.get("status") in R.SENT:
            R.set_status(g.db, ctx, aid, request.form["status"])
        elif what == "notatka":
            g.db.execute("UPDATE aplikacje SET notatka=? WHERE id=?", (request.form.get("notatka", "").strip()[:2000], aid))
            g.db.commit()
        return redirect(url_for("detail", aid=aid))

    @app.route("/plik/<int:aid>/<which>")
    def file(aid, which):
        a = get(aid)
        name = a["cv_plik"] if which == "cv" else a["list_plik"] if which == "list" else ""
        path = app_dir(ctx, aid) / name
        if not name or not path.is_file():
            abort(404)
        return send_file(path, mimetype="application/pdf", download_name=name, as_attachment=bool(request.args.get("pobierz")), max_age=0)

    @app.route("/dodaj-wiele", methods=["POST"])
    def add_many():
        links = re.findall(r"https?://\S+", request.form.get("linki", ""))
        added = dup = 0
        for url in dict.fromkeys(l.rstrip(").,;") for l in links):
            if R.find_duplicate(g.db, "", "", url):
                dup += 1
                continue
            now = R.stamp(ctx)
            cur = g.db.execute("INSERT INTO aplikacje(utworzono,zmieniono,status,zrodlo,url) VALUES(?,?,?,?,?)", (now, now, "nowa", "oferta", url))
            R.note(g.db, ctx, cur.lastrowid, "dodana przez Agę (lista linków)")
            g.db.execute("INSERT OR IGNORE INTO widziane(url,kiedy,zrodlo_id) VALUES(?,?,0)", (R.norm_url(url), now))
            added += 1
        g.db.commit()
        flash(f"Dodane: {added}." + (f" Pominięte jako powtórki: {dup}." if dup else "") + (" Przygotuję je po kolei." if added else ""))
        return redirect(url_for("home"))

    @app.route("/odpowiedzi")
    def replies():
        rows = g.db.execute("SELECT w.*, a.firma, a.stanowisko FROM wiadomosci w LEFT JOIN aplikacje a ON a.id=w.aplikacja_id "
                            "ORDER BY (w.status='nowa' AND w.wazne=1) DESC, w.id DESC LIMIT 200").fetchall()
        qs = g.db.execute("SELECT p.*, a.firma FROM pytania p LEFT JOIN aplikacje a ON a.id=p.aplikacja_id WHERE p.status='otwarte' ORDER BY p.id").fetchall()
        return render_template("odpowiedzi.html", rows=rows, qs=qs, tab="odp", KINDS=A.KINDS)

    @app.route("/wiadomosc/<int:wid>", methods=["GET", "POST"])
    def message(wid):
        m = g.db.execute("SELECT w.*, a.firma, a.stanowisko FROM wiadomosci w LEFT JOIN aplikacje a ON a.id=w.aplikacja_id WHERE w.id=?", (wid,)).fetchone()
        if not m:
            abort(404)
        if request.method == "POST":
            what = request.form.get("co", "")
            if what == "pytania":
                for q in g.db.execute("SELECT id FROM pytania WHERE wiadomosc_id=? AND status='otwarte'", (wid,)).fetchall():
                    ans = request.form.get(f"q{q['id']}", "").strip()
                    if ans:
                        A.answer_question(ctx, q["id"], ans, remember=bool(request.form.get("zapamietaj")))
                flash("Dziękuję. Szkic odpowiedzi jest gotowy poniżej.")
            elif what == "wyslij":
                text = request.form.get("szkic", "").strip()
                if len(text) < 20:
                    flash("Szkic jest pusty.")
                else:
                    try:
                        A.send_draft(ctx, wid, text, send=app.config.get("SEND"))
                        flash("Odpowiedź wysłana.")
                        return redirect(url_for("replies"))
                    except P.NotSent:
                        flash("Nie udało się połączyć z Gmailem. Nic nie wyszło — spróbuj za chwilę.")
                    except P.Uncertain:
                        flash("Połączenie przerwało się w trakcie. Sprawdź w Gmailu (Wysłane), czy odpowiedź wyszła.")
                    except Exception as e:
                        flash(str(e) if "już wysłana" in str(e) else f"Nie udało się wysłać ({type(e).__name__}).")
            elif what == "zalatwione":
                g.db.execute("UPDATE wiadomosci SET status='zalatwiona' WHERE id=?", (wid,))
                g.db.execute("UPDATE pytania SET status='pominiete' WHERE wiadomosc_id=? AND status='otwarte'", (wid,))
                g.db.commit()
                return redirect(url_for("replies"))
            elif what == "rodzaj" and request.form.get("rodzaj") in A.KINDS:
                g.db.execute("UPDATE wiadomosci SET rodzaj=?, wazne=? WHERE id=?", (request.form["rodzaj"], int(request.form["rodzaj"] in A.IMPORTANT), wid))
                g.db.commit()
            return redirect(url_for("message", wid=wid))
        qs = g.db.execute("SELECT * FROM pytania WHERE wiadomosc_id=? ORDER BY id", (wid,)).fetchall()
        return render_template("wiadomosc.html", m=m, qs=qs, tab="odp", KINDS=A.KINDS)

    @app.route("/paczka-dla-claude.txt")
    def claude_pack():
        f = R.load_facts(ctx)
        rows = g.db.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.TODO))}) ORDER BY id DESC LIMIT 15", R.TODO).fetchall()
        out = ["Paczka dla Claude'a — trudne przypadki z panelu Rekrutacja. Wklej ją w rozmowie i napisz, czego potrzebujesz.", "",
               "FAKTY O KANDYDATCE:", R.facts_brief(f, ids=False), "", "KRYTERIA: chce — " + "; ".join(f["kryteria"]["chce"]),
               "nie chce — " + "; ".join(f["kryteria"]["nie_chce"]), ""]
        for r in rows:
            out += [f"=== Aplikacja {r['id']}: {r['firma']} — {r['stanowisko']} [{R.STATUS.get(r['status'])}]", f"Link: {r['url']}",
                    "Uwagi: " + "; ".join(json.loads(r["uwagi"] or "[]")), (r["tresc"] or "")[:3000], ""]
        for m in g.db.execute("SELECT * FROM wiadomosci WHERE status='nowa' AND wazne=1 ORDER BY id DESC LIMIT 10"):
            out += [f"=== Wiadomość od {m['od']}: {m['temat']}", m["tresc"][:3000], ""]
        from flask import Response
        return Response("\n".join(out), mimetype="text/plain; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=paczka-dla-claude.txt"})

    @app.route("/ustawienia", methods=["GET", "POST"])
    def settings():
        f = R.load_facts(ctx)
        part = request.args.get("czesc", "")
        error = ""
        if request.method == "POST":
            what = request.form.get("co", "")
            if what == "dane":
                error = save_data(f)
            elif what == "narzedzia":
                error = save_tools(f)
            elif what == "kryteria":
                error = save_criteria(f)
            elif what in ("aga", "sebastian"):
                error = connect_box(what)
            elif what == "wysylka":
                try:
                    ctx.set_setting("limit_dzienny", max(1, min(70, int(request.form.get("limit_dzienny", 70)))))
                    for key in ("godziny", "raport"):
                        val = request.form.get(key, "").strip()
                        if re.fullmatch(r"\d{1,2}:\d{2}(-\d{1,2}:\d{2})?", val):
                            ctx.set_setting(key, val)
                except Exception:
                    error = "Nie udało się zapisać ustawień wysyłki."
            elif what == "praca":
                save_work()
                for key, lo, hi in (("prog_autopilota", 50, 100), ("prog_dopasowania", 0, 95), ("przypomnienie_po_dniach", 3, 30)):
                    with contextlib.suppress(ValueError):
                        ctx.set_setting(key, max(lo, min(hi, int(request.form.get(key, ctx.settings()[key])))))
            elif what == "zrodlo_dodaj":
                url = request.form.get("url", "").strip()
                url = url if re.match(r"^https?://", url) else ("https://" + url if url else "")
                if not url or not O.safe_url(url):
                    error = "Ten adres nie wygląda na publiczną stronę."
                elif Z.blocked(url):
                    error = f"{Z.blocked(url)} nie zgadza się na automatyczne przeglądanie. Oferty z tego portalu wklejaj linkami na stronie „Dziś”."
                else:
                    g.db.execute("INSERT OR IGNORE INTO zrodla(typ,url,nazwa,dodano) VALUES(?,?,?,?)", (Z.kind_of(url), url, request.form.get("nazwa", "").strip()[:120], R.stamp(ctx)))
                    g.db.commit()
                    R.meta_set(g.db, "ostatnie_szukanie", 0)
            elif what in ("zrodlo_usun", "zrodlo_przelacz"):
                sid = int(request.form.get("id", 0))
                if what == "zrodlo_usun":
                    g.db.execute("DELETE FROM zrodla WHERE id=?", (sid,))
                else:
                    g.db.execute("UPDATE zrodla SET wlaczone=1-wlaczone, sprawdzono='' WHERE id=?", (sid,))
                g.db.commit()
            elif what == "szukaj_teraz":
                g.db.execute("UPDATE zrodla SET sprawdzono=''")
                g.db.commit()
                R.meta_set(g.db, "ostatnie_szukanie", 0)
                flash("Przeglądam źródła. Nowe oferty pojawią się w ciągu kilkunastu minut.")
                return redirect(url_for("settings", czesc="zrodla"))
            elif what == "firmy":
                added, skipped = Z.import_firms(g.db, ctx, request.form.get("firmy", ""))
                flash(f"Dodane firmy: {added}." + (f" Pominięte (powtórki albo brak adresu): {skipped}." if skipped else ""))
                return redirect(url_for("settings", czesc="firmy"))
            elif what == "pauza":
                ctx.set_setting("wstrzymane", "nie" if ctx.settings().get("wstrzymane") else "tak")
                return redirect(request.form.get("powrot") or url_for("home"))
            elif what == "raport_teraz":
                flash("Raport wysłany na Twoją skrzynkę." if evening_report(ctx, send=app.config.get("SEND", P.send), force=True) else "Raport nie wyszedł — sprawdź podłączenie skrzynek.")
            if not error:
                if what in ("dane", "narzedzia", "kryteria", "aga", "sebastian", "wysylka", "praca"):
                    flash("Zapisane.")
                return redirect(url_for("settings", czesc=what if what.startswith("zrodlo") else ""))
            part = what if what in ("dane", "narzedzia", "kryteria") else ("zrodla" if what.startswith("zrodlo") else part)
        me, seb = R.mailboxes(g.db)
        Z.seed(g.db, ctx)
        sources = g.db.execute("SELECT * FROM zrodla ORDER BY id").fetchall()
        firms = g.db.execute("SELECT COUNT(*) n, SUM(uzyta) u FROM firmy").fetchone()
        return render_template("ustawienia.html", f=f, tab="ust", part=part, error=error, me=me, seb=seb, has_photo=bool(photo_path(ctx, f)),
                               sources=sources, firms=firms)

    return app


# ================================================================ uruchomienie (panel + praca w tle)

def serve(ctx):
    from werkzeug.serving import make_server
    st = ctx.settings()
    port = int(st.get("port", 8790))
    mode = str(st.get("nasluch", "tailscale"))
    ip = ""
    if mode == "tailscale":
        for _ in range(8):                                    # po starcie Maca Tailscale wstaje chwilę później
            ip = tailscale_ip()
            if ip:
                break
            time.sleep(15)
    name = tailscale_name() if ip else ""
    hosts = {"127.0.0.1", "localhost"} | {h for h in (ip, name.lower(), name.split(".")[0].lower(), str(st.get("dodatkowy_host", "")).lower()) if h}
    app = make_app(ctx, hosts=None if mode == "wszedzie" else hosts)
    binds = ["0.0.0.0"] if mode == "wszedzie" else ["127.0.0.1"] + ([ip] if ip else [])
    public = f"http://{name or ip}:{port}" if ip else f"http://127.0.0.1:{port}"
    with R.db(ctx) as c:
        R.meta_set(c, "adres_panelu", public)
    stop = threading.Event()
    threading.Thread(target=worker, args=(ctx, stop), daemon=True, name="rekrutacja-praca").start()
    servers = [make_server(b, port, app, threaded=True) for b in binds]
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    if mode == "tailscale":
        def watch(first=ip):
            """Tailscale wstał później albo zmienił adres → kończę proces, launchd uruchamia mnie od nowa (KeepAlive)."""
            while True:
                time.sleep(60)
                now_ip = tailscale_ip()
                if now_ip and now_ip != first:
                    ctx.log.info(f"Rekrutacja: adres Tailscale {now_ip} — restart panelu")
                    SENDING.acquire()                         # nie przerywam wysyłki w połowie
                    os._exit(0)
        threading.Thread(target=watch, daemon=True, name="rekrutacja-tailscale").start()
    ctx.log.info(f"Rekrutacja: panel pod {public} (nasłuch: {', '.join(binds)})")
    print(f"Panel Rekrutacja: {public}" + ("" if ip or mode != "tailscale" else "  (Tailscale nie odpowiada — panel działa tylko na tym Macu)"), flush=True)
    try:
        servers[0].serve_forever()
    finally:
        stop.set()
