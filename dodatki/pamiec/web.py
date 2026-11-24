"""Pamięć — zakładka „Sebastian uczy się o Tobie” (w panelu głównym i w panelu Agi).

register(app, ctx, prefix, people_filter, back) — strona bez JavaScriptu (same formularze), własne style.
people_filter(osoby) → osoby, które ten panel może oglądać (panel Agi: tylko ona).
"""
import contextlib, datetime as dt, re
from pathlib import Path

import jinja2
from flask import abort, redirect, request, send_file, session

from . import biblioteka as B
from . import rdzen as R

_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(str(Path(__file__).parent / "szablony")), autoescape=True)
MAX_UPLOAD = 4 * 1024 ** 3


def register(app, ctx, prefix="/pamiec", people_filter=None, back=("/", "← Panel")):
    people_filter = people_filter or (lambda ps: ps)

    def con():
        c = R.db(ctx.folder())
        with contextlib.suppress(Exception):
            import dodatki_host as DH
            R.sync_people(c, R.with_extra(DH._w().all_users(), ctx.settings()))
        return c

    def allowed(c):
        return people_filter(R.people(c))

    def pick(c, pid):
        ps = allowed(c)
        p = next((x for x in ps if x["id"] == pid), None) or (ps[0] if ps else None)
        if not p:
            abort(404)
        return p, ps

    def csrf():
        if "csrf" not in session:
            import secrets
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    def go(pid, msg=""):
        return redirect(f"{prefix}?osoba={pid}" + (f"&info={msg}" if msg else "") + "#gora")

    @app.route(prefix, endpoint="pamiec_strona")
    def page():
        with contextlib.closing(con()) as c:
            p, ps = pick(c, request.args.get("osoba", ""))
            R.make_questions(c, p["id"])
            cat = request.args.get("kat", "")
            facts = [dict(r) for r in c.execute(
                "SELECT * FROM fakty WHERE osoba=? AND (?='' OR kategoria=?) ORDER BY CASE status WHEN 'nowy' THEN 0 WHEN 'potwierdzony' THEN 1 ELSE 2 END, "
                "id DESC LIMIT 300", (p["id"], cat, cat))]
            prof = {r["kategoria"]: r for r in c.execute("SELECT * FROM profil WHERE osoba=?", (p["id"],))}
            sources = [dict(r) for r in c.execute("SELECT * FROM zrodla WHERE osoba=? AND COALESCE(cel,'osoba')<>'biblioteka' "
                                                  "ORDER BY id DESC LIMIT 40", (p["id"],))]
            library, orders = B.sources(c, p["id"]), B.jobs(c, p["id"])
            fixes = [dict(r) for r in c.execute("SELECT * FROM poprawki WHERE osoba=? ORDER BY id DESC LIMIT 20", (p["id"],))]
            html = _ENV.get_template("pamiec.html").render(
                p=p, ps=ps, qs=R.open_questions(c, p["id"])[:15], facts=facts, prof=prof, cats=R.CATEGORIES, cat=cat,
                sources=sources, fixes=fixes, st=R.stats(c, p["id"]), kind_pl=R.KIND_PL, status_pl=R.STATUS_PL,
                drop=str(ctx.folder() / "wrzuc-tutaj" / p["folder"]), prefix=prefix, back=back, csrf=csrf(),
                info=request.args.get("info", ""), first=R.first_name(p), library=library, orders=orders,
                lib_pieces=sum(x["kawalkow"] or 0 for x in library))
        return html

    @app.route(prefix + "/wgraj", methods=["POST"], endpoint="pamiec_wgraj")
    def upload():
        request.max_content_length = MAX_UPLOAD
        with contextlib.closing(con()) as c:
            p, _ = pick(c, request.form.get("osoba", ""))
            lib = request.form.get("cel") == "biblioteka"
            year = int(request.form.get("rok") or 0) if (request.form.get("rok") or "").isdigit() else 0
            n = 0
            for f in request.files.getlist("plik"):
                if not f or not f.filename:
                    continue
                name = re.sub(r"[^\w.\- ]+", "_", Path(f.filename).name)[:120] or "plik"
                target = ctx.folder() / "wgrane" / p["id"] / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{n}-{name}"
                target.parent.mkdir(parents=True, exist_ok=True)
                f.save(target)
                if lib:
                    B.add(c, p["id"], name, target, year)
                else:
                    R.add_source(c, p["id"], "plik", name, target)
                n += 1
        where = " do biblioteki wiedzy" if lib else ""
        return go(p["id"], f"Dodane pliki{where}: {n}. Przerabiam je w tle." if n else "Nie wybrano pliku.")

    @app.route(prefix + "/tekst", methods=["POST"], endpoint="pamiec_tekst")
    def paste():
        with contextlib.closing(con()) as c:
            p, _ = pick(c, request.form.get("osoba", ""))
            text = (request.form.get("tekst") or "").strip()
            if len(text) < 10:
                return go(p["id"], "Wklej proszę dłuższy tekst.")
            name = (request.form.get("nazwa") or "Wklejony tekst").strip()[:120]
            if request.form.get("cel") == "biblioteka":
                B.add(c, p["id"], name, year=int(request.form.get("rok") or 0) if (request.form.get("rok") or "").isdigit() else 0, text=text[:5_000_000])
                return go(p["id"], "Dodane do biblioteki wiedzy.")
            R.add_source(c, p["id"], "tekst", name, text=text[:2_000_000])
        return go(p["id"], "Dziękuję! Przemyślę ten tekst w tle.")

    @app.route(prefix + "/odpowiedz", methods=["POST"], endpoint="pamiec_odpowiedz")
    def reply():
        with contextlib.closing(con()) as c:
            p, _ = pick(c, request.form.get("osoba", ""))
            q = c.execute("SELECT osoba FROM pytania WHERE id=?", (request.form.get("id", "0"),)).fetchone()
            if not q or q["osoba"] != p["id"]:
                abort(404)
            verdict = request.form.get("werdykt", "")
            if verdict not in ("tak", "nie", "pomin"):
                abort(400)
            R.answer(c, int(request.form["id"]), verdict, request.form.get("poprawka", ""), "panel")
        return go(p["id"], "Zapisane — dziękuję! 🐑")

    @app.route(prefix + "/fakt", methods=["POST"], endpoint="pamiec_fakt")
    def fact():
        with contextlib.closing(con()) as c:
            p, _ = pick(c, request.form.get("osoba", ""))
            f = c.execute("SELECT osoba FROM fakty WHERE id=?", (request.form.get("id", "0"),)).fetchone()
            if not f or f["osoba"] != p["id"]:
                abort(404)
            verdict = request.form.get("werdykt", "")
            if verdict not in ("tak", "nie"):
                abort(400)
            R.fact_verdict(c, int(request.form["id"]), verdict, request.form.get("poprawka", ""))
        return go(p["id"], "Zapisane.")

    @app.route(prefix + "/zlecenie", methods=["POST"], endpoint="pamiec_zlecenie")
    def order():
        with contextlib.closing(con()) as c:
            p, _ = pick(c, request.form.get("osoba", ""))
            topic = (request.form.get("temat") or "").strip()
            kind = request.form.get("rodzaj", "")
            if kind not in ("poradnik", "wyjasnienie") or len(topic) < 3:
                return go(p["id"], "Wpisz temat (co najmniej 3 znaki).")
            if not B.search(c, p["id"], topic, 1):
                return go(p["id"], f"W bibliotece nie znalazłem nic o „{topic}”. Spróbuj innymi słowami.")
            B.queue(c, p["id"], kind, topic, "panel")
        return go(p["id"], "Zlecone — wynik pojawi się w „Bibliotece wiedzy” za kilka minut (odśwież stronę).")

    @app.route(prefix + "/plik/<int:jid>", endpoint="pamiec_plik")
    def guide_file(jid):
        with contextlib.closing(con()) as c:
            j = c.execute("SELECT * FROM zlecenia WHERE id=?", (jid,)).fetchone()
            if not j or not j["plik"] or j["osoba"] not in {x["id"] for x in allowed(c)} or not Path(j["plik"]).exists():
                abort(404)
            path = Path(j["plik"])
        return send_file(path, as_attachment=True, download_name=path.name.split("-", 2)[-1] if path.name.count("-") >= 2 else path.name)

    @app.route(prefix + "/nieaktualne", methods=["POST"], endpoint="pamiec_nieaktualne")
    def outdated():
        with contextlib.closing(con()) as c:
            p, _ = pick(c, request.form.get("osoba", ""))
            src = c.execute("SELECT * FROM zrodla WHERE id=? AND osoba=? AND cel='biblioteka'", (request.form.get("id", "0"), p["id"])).fetchone()
            if not src:
                abort(404)
            c.execute("UPDATE zrodla SET status=? WHERE id=?", ("gotowe" if src["status"] == "nieaktualne" else "nieaktualne", src["id"]))
            c.commit()
        return go(p["id"], "Zapisane.")
