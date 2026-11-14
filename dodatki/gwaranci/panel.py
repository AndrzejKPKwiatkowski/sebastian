"""Gwaranci — panel (osobny serwer Flask) i praca w tle.

Każda osoba wchodzi przez swój osobisty link (/l/<token>) — bez haseł. Gwarant za pierwszym razem przechodzi krótki onboarding:
mail → link do kalendarza (tylko zajętość) → kiedy może i ile spotkań w tygodniu. Adept wybiera typ i godzinę, a gwaranta
dobiera system. Panel wystawiam do internetu przez Tailscale Funnel (polecenie: dodatek gwaranci internet wlacz).
"""
import contextlib, datetime as dt, hmac, json, os, secrets, subprocess, threading, time
from pathlib import Path

from . import przebieg as PB, rdzen as R

HERE = Path(__file__).resolve().parent
OPEN = {"wejscie", "link", "dostep", "decyzja", "healthz", "static_css"}


def _tailscale(*args):
    for exe in ("tailscale", "/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        with contextlib.suppress(Exception):
            r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=20)
            return r.returncode, (r.stdout + r.stderr).strip()
    return 1, "Nie znalazłem programu tailscale."


def tailscale_ip():
    import re
    code, out = _tailscale("ip", "-4")
    m = re.search(r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", out or "")
    return m.group(0) if code == 0 and m else ""


def tailscale_name():
    with contextlib.suppress(Exception):
        code, out = _tailscale("status", "--json")
        return json.loads(out)["Self"]["DNSName"].rstrip(".")
    return ""


def make_app(ctx):
    from flask import Flask, abort, g, redirect, render_template, request, session, url_for

    app = Flask(__name__, template_folder=str(HERE / "szablony"), static_folder=None)
    key = ctx.folder() / "sesja.key"
    if not key.exists():
        key.write_text(secrets.token_hex(32), encoding="utf-8")
        with contextlib.suppress(Exception):
            key.chmod(0o600)
    app.secret_key = key.read_text(encoding="utf-8").strip()
    app.config.update(SESSION_COOKIE_NAME="gwaranci", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=dt.timedelta(days=120))
    app.jinja_env.globals.update(TYPES=R.TYPES, STATUS=R.STATUS, DAYS_SHORT=R.DAYS_SHORT, hm=R.hm, dur=R.dur, fdate=R.fdate,
                                 parse=R.parse, place_label=R.place_label)

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    app.jinja_env.globals["csrf"] = csrf

    def now():
        return R.now(ctx)

    @app.before_request
    def before():
        g.db = R.db(ctx)
        g.me = R.person(g.db, session.get("pid", "")) if session.get("pid") else None
        if request.method == "POST" and request.endpoint not in ("dostep",):
            if not hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "-")):
                abort(400)
        if request.endpoint in OPEN:
            return
        if not g.me:
            return redirect(url_for("wejscie"))
        if not g.me.get("email") and request.endpoint not in ("dane", "wyloguj"):
            return redirect(url_for("dane"))

    @app.teardown_request
    def close(_):
        if "db" in g:
            g.pop("db").close()

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    def page(tpl, **kw):
        ppl = R.people(g.db)
        me = g.me
        is_g = bool(me and R.can_guarantee(me))
        return render_template(tpl, me=me, is_g=is_g, is_admin=bool(me and me.get("admin")), ppl=ppl,
                               struct=lambda pid: R.structure_of(ppl, pid), **kw)

    def msg(title, text, button=None, code=200):
        return page("komunikat.html", title=title, text=text, button=button), code

    @app.route("/healthz")
    def healthz():
        return "ok"

    @app.route("/")
    def home():
        gw = R.guarantor(g.db, g.me["id"])
        if R.can_guarantee(g.me) and not (gw and gw["gotowe"]):
            return redirect(url_for("onboarding"))
        return redirect(url_for("rezerwuj"))

    @app.route("/witaj")
    def wejscie():
        if g.me:
            return redirect(url_for("home"))
        return page("wejscie.html")

    @app.route("/l/<tok>")
    def link(tok):
        p = R.by_token(g.db, tok)
        if not p:
            return msg("Ten link nie działa", "Poproś Andrzeja albo swojego menedżera o nowy osobisty link.", code=404)
        session.clear()
        session.permanent = True
        session["pid"] = p["id"]
        return redirect(url_for("home"))

    @app.route("/wyloguj")
    def wyloguj():
        session.clear()
        return redirect(url_for("wejscie"))

    @app.route("/dostep", methods=["POST"])
    def dostep():
        name = " ".join(request.form.get("imie_nazwisko", "").split())[:80]
        mail = request.form.get("email", "").strip()[:120]
        boss = " ".join(request.form.get("przelozony", "").split())[:80]
        if len(name.split()) < 2 or not R.EMAIL_OK.match(mail):
            return msg("Uzupełnij dane", "Podaj imię i nazwisko oraz poprawny adres e-mail.", ("Wróć", url_for("wejscie")), 400)
        g.db.execute("INSERT INTO prosby(imie_nazwisko,email,telefon,przelozony,utworzono) VALUES(?,?,?,?,?)",
                     (name, mail, request.form.get("telefon", "")[:30], boss, now().isoformat(timespec="seconds")))
        g.db.commit()
        known = R.find_person(g.db, name)
        PB.notify_owner(ctx, f"🙋 Gwaranci: prośba o dostęp — {name} ({mail})" + (f", przełożony: {boss}" if boss else "")
                        + (f". Jest w strukturze — wyślij link: „gwaranci link {name}”." if known else
                           f". Nie ma go w strukturze — dodaj: „gwaranci dodaj {name} od {boss or 'Imię Nazwisko przełożonego'}”."), "dostep")
        return msg("Dziękujemy!", "Prośba trafiła do Sebastiana. Osobisty link dostaniesz od Andrzeja albo swojego menedżera.")

    @app.route("/dane", methods=["GET", "POST"])
    def dane():
        if request.method == "POST":
            mail = request.form.get("email", "").strip()[:120]
            if not R.EMAIL_OK.match(mail):
                return page("dane.html", error="To nie wygląda na adres e-mail.")
            g.db.execute("UPDATE osoby SET email=?, telefon=? WHERE id=?", (mail, request.form.get("telefon", "").strip()[:30], g.me["id"]))
            g.db.commit()
            return redirect(url_for("home"))
        return page("dane.html", error="")

    # ------------------------------------------------------------ onboarding gwaranta
    @app.route("/gwarant/start", methods=["GET", "POST"])
    def onboarding():
        if not R.can_guarantee(g.me):
            return msg("Panel gwaranta", "Gwarantem zostaje się po pierwszym awansie. Do rezerwacji spotkań przejdź dalej.", ("Rezerwuj", url_for("rezerwuj")))
        gw = R.guarantor(g.db, g.me["id"]) or {"kalendarze": [], "dostepnosc": [], "limit_tyg": 0, "gotowe": 0, "blad": "", "odczyt": ""}
        step = request.args.get("k", "1")
        info = ""
        if request.method == "POST" and step == "1" and request.form.get("zrodlo") == "calcom":
            ref = R.parse_calcom(request.form.get("calcom", ""))
            if not ref:
                return page("onboarding.html", step="1", gw=gw, error="Wklej link do wydarzenia, np. https://cal.com/twoja-nazwa/spotkanie-gwaranckie.", info="")
            R.save_guarantor(g.db, g.me["id"], calcom=ref)
            n, err = R.refresh_calcom(g.db, g.me["id"], when=now())
            if err:
                R.save_guarantor(g.db, g.me["id"], calcom="")
                return page("onboarding.html", step="1", gw=R.guarantor(g.db, g.me["id"]),
                            error=f"Nie udało się odczytać wydarzenia z cal.com ({err}). Sprawdź, czy link otwiera Twoją stronę rezerwacji.", info="")
            return redirect(url_for("onboarding", k="2", n=n))
        if request.method == "POST" and step == "1":
            urls = [R.clean_calendar_url(u) for u in request.form.get("kalendarze", "").splitlines() if u.strip()]
            urls = [u for u in urls if u][:4]
            if not urls:
                return page("onboarding.html", step="1", gw=gw, error="Wklej link zaczynający się od https:// (Tajny adres w formacie iCal).", info="")
            R.save_guarantor(g.db, g.me["id"], kalendarze=urls, calcom="")
            n, err = R.refresh_busy(g.db, g.me["id"], when=now())
            if err and not n:
                return page("onboarding.html", step="1", gw=R.guarantor(g.db, g.me["id"]),
                            error=f"Nie udało się odczytać kalendarza: {err}. Sprawdź, czy to „Tajny adres w formacie iCal”.", info="")
            return redirect(url_for("onboarding", k="2", n=n))
        if request.method == "POST" and step == "2":
            avail = []
            with contextlib.suppress(Exception):
                avail = [[int(d), int(a), int(b)] for d, a, b in json.loads(request.form.get("dostepnosc", "[]"))
                         if 0 <= int(d) <= 6 and 0 <= int(a) < int(b) <= 24 * 60]
            mx = R.max_limit(g.me)
            lim = max(1, min(mx, int(request.form.get("limit", 1) or 1)))
            if gw.get("calcom"):                                # dostępność ustawia się w cal.com
                avail = gw.get("dostepnosc") or []
            elif not avail:
                return page("onboarding.html", step="2", gw=gw, error="Zaznacz przynajmniej jedną godzinę.", info="", mx=mx, lim=lim)
            first = not gw.get("gotowe")
            R.save_guarantor(g.db, g.me["id"], dostepnosc=avail, limit_tyg=lim, gotowe=1)
            if first:
                PB.notify_owner(ctx, f"🧭 Gwaranci: {g.me['imie_nazwisko']} jest gotowy/gotowa — {lim} spotk. w tygodniu, "
                                + (f"cal.com: {gw['calcom']}." if gw.get("calcom") else f"{sum(b - a for _, a, b in avail) // 60} h dostępności."), "gotowy")
            return redirect(url_for("onboarding", k="3"))
        if step == "2":
            info = request.args.get("n", "")
            mx = R.max_limit(g.me)
            return page("onboarding.html", step="2", gw=gw, error="", info=info, mx=mx,
                        lim=gw.get("limit_tyg") or (min(4, mx) if R.is_manager(g.me["stanowisko"]) else mx))
        return page("onboarding.html", step=step if step in ("1", "3") else "1", gw=gw, error="", info="")

    @app.route("/gwarant")
    def gwarant():
        if not R.can_guarantee(g.me):
            return redirect(url_for("rezerwuj"))
        gw = R.guarantor(g.db, g.me["id"])
        if not gw or not gw["gotowe"]:
            return redirect(url_for("onboarding"))
        rows = [dict(r) for r in g.db.execute("SELECT * FROM rezerwacje WHERE gwarant=? ORDER BY start", (g.me["id"],))]
        t = now()
        tab = request.args.get("tab", "czeka")
        pending = [b for b in rows if b["status"] == "czeka"]
        upcoming = [b for b in rows if b["status"] == "potwierdzone" and R.parse(b["start"]) >= t]
        past = [b for b in rows if b["status"] == "potwierdzone" and R.parse(b["start"]) < t][::-1]
        n, mins = R.week_load(g.db, g.me["id"], t)
        return page("gwarant.html", gw=gw, tab=tab, pending=pending, upcoming=upcoming, past=past, n=n, mins=mins, mx=R.max_limit(g.me))

    @app.route("/gwarant/wstrzymaj", methods=["POST"])
    def wstrzymaj():
        gw = R.guarantor(g.db, g.me["id"])
        if gw:
            R.save_guarantor(g.db, g.me["id"], wstrzymany=0 if gw["wstrzymany"] else 1)
        return redirect(url_for("gwarant"))

    @app.route("/decyzja/<tok>/<odp>", methods=["GET", "POST"])
    def decyzja(tok, odp):
        b = R.booking_by_token(g.db, tok)
        if not b or odp not in ("tak", "nie"):
            return msg("Ten link nie działa", "Nie znalazłem tej prośby.", code=404)
        if request.method == "GET":                            # skanery poczty klikają w linki — decyzja dopiero po przycisku
            return page("decyzja.html", b=b, odp=odp, tok=tok)
        if b["status"] != "czeka":
            return msg("Już zapisane", f"Ta prośba ma status: {R.STATUS.get(b['status'], b['status'])}.")
        b = PB.decide(ctx, g.db, b, odp == "tak")
        return msg("Dziękujemy!" if odp == "tak" else "Zapisane",
                   "Spotkanie potwierdzone — adept dostał wiadomość, a wpis trafił do kalendarzy." if odp == "tak"
                   else "Adept dostał prośbę o wybranie innego terminu.")

    # ------------------------------------------------------------ rezerwacja (adept)
    @app.route("/rezerwuj")
    def rezerwuj():
        typ = request.args.get("typ", "analiza")
        typ = typ if typ in R.TYPES else "analiza"
        st, t = ctx.settings(), now()
        avail = R.days_with_slots(g.db, st, g.me["id"], typ, t)
        keys = sorted(avail)
        sel = request.args.get("d", "")
        sel = dt.date.fromisoformat(sel) if sel else (keys[0] if keys else None)
        if sel and sel not in avail:
            sel = keys[0] if keys else None
        mo = int(request.args.get("m", 0) or 0)
        first = dt.date(t.year, t.month, 1)
        y, m = divmod(first.month - 1 + mo, 12)
        month = dt.date(first.year + y, m + 1, 1)
        nxt = dt.date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        last_day = t.date() + dt.timedelta(days=int(st.get("okno_dni", 35)))
        max_mo = (last_day.year - first.year) * 12 + last_day.month - first.month
        day_slots = R.slots(g.db, st, g.me["id"], typ, sel, t) if sel else []
        ppl = R.people(g.db)
        boss = R.nearest_manager(ppl, g.me["id"])
        mine = [dict(r) for r in g.db.execute("SELECT * FROM rezerwacje WHERE adept=? AND status IN ('czeka','potwierdzone') ORDER BY start", (g.me["id"],))]
        return page("rezerwuj.html", typ=typ, avail=avail, sel=sel, month=month, ndays=(nxt - month).days, mo=mo, max_mo=max_mo, day_slots=day_slots,
                    loc=request.args.get("loc", "online"), gdzie=request.args.get("gdzie", ""), boss=ppl.get(boss), today=t.date(),
                    mine=mine, ready=len(R.ready_guarantors(g.db)))

    @app.route("/rezerwuj/potwierdz", methods=["GET", "POST"])
    def potwierdz():
        typ = request.values.get("typ", "")
        if typ not in R.TYPES:
            abort(400)
        start = R.parse(request.values.get("start", ""))
        loc = "miejsce" if request.values.get("loc") == "miejsce" else "online"
        gdzie = request.values.get("gdzie", "").strip()
        st = ctx.settings()
        if loc == "miejsce" and not gdzie:
            return redirect(url_for("rezerwuj", typ=typ, d=start.date().isoformat(), loc=loc, brak="1"))
        cand = R.Snapshot(g.db, st).candidates(g.me["id"], start, R.TYPES[typ][1])
        if request.method == "GET":
            if not cand:
                return msg("Termin zajęty", "Ten termin przed chwilą przestał być wolny. Wybierz inny.", ("Wróć", url_for("rezerwuj", typ=typ)))
            return page("potwierdz.html", typ=typ, start=start, loc=loc, gdzie=gdzie, g_=R.person(g.db, cand[0]["gwarant"]),
                        przez_calcom=bool((R.guarantor(g.db, cand[0]["gwarant"]) or {}).get("calcom")))
        pid = cand[0]["gwarant"] if cand else ""
        with contextlib.suppress(Exception):                    # świeży odczyt kalendarza przydzielonego gwaranta tuż przed rezerwacją
            if pid:
                R.refresh_busy(g.db, pid, when=now())
        try:
            b = R.book(g.db, st, g.me["id"], typ, start, loc, gdzie, request.form.get("notatka", ""), when=now())
        except ValueError as e:
            return msg("Termin zajęty", str(e), ("Wybierz inny", url_for("rezerwuj", typ=typ)))
        errors = PB.after_booking(ctx, g.db, b)
        gp = R.person(g.db, b["gwarant"])
        return msg("Prośba wysłana 🎉", f"Twój gwarant: {gp['imie_nazwisko']}. Gdy zaakceptuje (najpóźniej w ciągu 24 h), dostaniesz maila "
                   + ("z potwierdzeniem z cal.com." if b.get("calcom_uid") else "z zaproszeniem do kalendarza.") + (" (Mail do gwaranta wyjdzie za kilka minut — Gmail chwilowo nie odpowiadał.)" if errors and all("kolejce" in e for e in errors)
                      else " (Uwaga: mail nie wyszedł — Sebastian dał znać Andrzejowi.)" if errors else ""),
                   ("Moje spotkania", url_for("moje")))

    @app.route("/moje")
    def moje():
        rows = [dict(r) for r in g.db.execute("SELECT * FROM rezerwacje WHERE adept=? ORDER BY start DESC LIMIT 60", (g.me["id"],))]
        return page("moje.html", rows=rows, t=now())

    @app.route("/moje/anuluj/<tok>", methods=["POST"])
    def anuluj(tok):
        b = R.booking_by_token(g.db, tok)
        if not b or b["adept"] != g.me["id"]:
            abort(404)
        PB.cancel_by_adept(ctx, g.db, b)
        return redirect(url_for("moje"))

    # ------------------------------------------------------------ administrator
    @app.route("/admin", methods=["GET", "POST"])
    def admin():
        if not g.me.get("admin"):
            abort(403)
        note = ""
        if request.method == "POST":
            act = request.form.get("akcja")
            try:
                if act == "stanowisko":
                    R.set_position(g.db, request.form["osoba"], request.form["stanowisko"])
                    note = "Zapisane."
                elif act == "dodaj":
                    p = R.add_person(g.db, request.form["imie_nazwisko"], request.form.get("stanowisko", "Trainee"),
                                     request.form.get("przelozony", ""), request.form.get("email", ""))
                    g.db.execute("UPDATE prosby SET status='dodana' WHERE imie_nazwisko=?", (p["imie_nazwisko"],))
                    g.db.commit()
                    note = f"Dodano: {p['imie_nazwisko']}."
                elif act == "prosba_ok":
                    g.db.execute("UPDATE prosby SET status='zalatwiona' WHERE id=?", (request.form["id"],))
                    g.db.commit()
            except Exception as e:
                note = str(e)
        ppl = R.people(g.db)
        gws = {r["osoba"]: R.guarantor(g.db, r["osoba"]) for r in g.db.execute("SELECT osoba FROM gwaranci")}
        rows = [dict(r) for r in g.db.execute("SELECT * FROM rezerwacje ORDER BY start DESC LIMIT 80")]
        asks = [dict(r) for r in g.db.execute("SELECT * FROM prosby WHERE status='nowa' ORDER BY id DESC")]
        base = PB.base_url(ctx, g.db) or request.host_url.rstrip("/")
        t = now()
        load = {pid: R.week_load(g.db, pid, t) for pid in gws}
        return page("admin.html", gws=gws, rows=rows, asks=asks, base=base, note=note, load=load,
                    order=sorted(ppl.values(), key=lambda p: (R.structure_of(ppl, p["id"]) or "", p["imie_nazwisko"])))

    @app.errorhandler(404)
    def e404(_):
        return msg("Nie ma takiej strony", "Wróć na stronę główną.", ("Strona główna", "/"), 404)

    return app


def worker(ctx, stop):
    """Co minutę: zajętość z kalendarzy, odpowiedzi z Gmaila, przypomnienia."""
    while not stop.is_set():
        try:
            with contextlib.closing(R.db(ctx)) as c:
                PB.periodic(ctx, c)
        except Exception as e:
            ctx.log.warning(f"Gwaranci (praca w tle): {type(e).__name__}: {e}")
        stop.wait(60)


def serve(ctx):
    from werkzeug.serving import make_server
    port = int(ctx.settings().get("port", 8791))
    ip = ""
    for _ in range(8):
        ip = tailscale_ip()
        if ip:
            break
        time.sleep(10)
    app = make_app(ctx)
    binds = ["127.0.0.1"] + ([ip] if ip else [])
    stop = threading.Event()
    threading.Thread(target=worker, args=(ctx, stop), daemon=True, name="gwaranci-praca").start()
    servers = [make_server(b, port, app, threaded=True) for b in binds]
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print(f"Panel Gwaranci: http://127.0.0.1:{port}" + (f" oraz http://{ip}:{port} (Tailscale)" if ip else ""), flush=True)
    try:
        servers[0].serve_forever()
    finally:
        stop.set()
