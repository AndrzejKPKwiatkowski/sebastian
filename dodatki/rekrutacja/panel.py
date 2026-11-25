"""Rekrutacja — panel Agi (osobny serwer, dostępny w sieci Tailscale) i praca w tle.

Panel Sebastiana (127.0.0.1:8765) zostaje nietknięty. Ten panel ma własne hasło, własną sesję i widzi wyłącznie
dane dodatku Rekrutacja.
"""
import contextlib, datetime as dt, hmac, html as H, json, os, random, re, secrets, subprocess, threading, time
from pathlib import Path

from . import preferencje as PF
from . import dojazd as DJ
from . import cbop as CB, dokumenty as D, gemini as GM, formularze as F, kontakty as K, odpowiedzi as A, oferty as O, owca as OW, poczta as P, rdzen as R, rozmowa as RZ, wiedza as Wd, zrodla as Z

HERE = Path(__file__).resolve().parent
STEPS = ["Powitanie", "Twoja skrzynka", "Skrzynka Sebastiana", "Twoje dane", "Narzędzia", "Czego szukasz", "Jak mam pracować", "Gotowe"]
OPEN_ENDPOINTS = {"login", "first_run", "healthz", "owca_goal", "owca_stage", "owca_art"}   # przyciski z maili owcy: z tokenem


# ================================================================ przygotowanie kompletu dokumentów

def _ok_social_f(f):
    return not any("social" in R.plain(x) or "spolecznosciow" in R.plain(x) for x in f["kryteria"].get("nie_chce", []))


def app_dir(ctx, aid):
    p = ctx.folder() / "aplikacje" / str(aid)
    p.mkdir(parents=True, exist_ok=True)
    return p


def analysis(a):
    with contextlib.suppress(Exception):
        v = json.loads(a.get("analiza") or "{}")
        if isinstance(v, dict):
            return v
    return {}


def signature_path(ctx):
    for name in ("podpis.png", "podpis.jpg"):
        p = ctx.folder() / name
        if p.exists():
            return p
    return None


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
    cv, li = f"{base}_CV_{firm}.pdf", f"{base}_List_motywacyjny_{firm}.pdf"
    job = "" if a["zrodlo"] == "spontaniczna" else (a.get("stanowisko") or "")
    own = (selection or {}).get("rodo_aga") if isinstance(selection, dict) else ""
    rodo = own or R.consent_clause(a.get("firma", ""), rodo, job)       # 2.26: klauzula Agi; inaczej zgoda pracodawcy albo domyślna
    info = analysis(a)
    D.render_cv(f, selection, folder / cv, photo=photo_path(ctx, f), rodo=rodo)
    D.render_letter(f, letter, folder / li, firma=a["firma"], stanowisko=job, today=ctx.now().date(), rodo=rodo,
                    adres_firmy=info.get("adres", ""), podpis=signature_path(ctx))
    return cv, li


def prepare(ctx, aid):
    """Cały przebieg dla jednej aplikacji: pobranie ogłoszenia → dane → CV → list i mail → kontroler prawdy."""
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        a = dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone())
        R.set_status(c, ctx, aid, "przygotowywanie", blad="")
    notes, warn, found_mails, title, page_links = [], [], [], "", []
    try:
        if a["url"] and O.junk_text(a):                                  # 2.36.2: strona blokady zapisana wcześniej — pobieram jeszcze raz
            a["tresc"] = ""
            if re.fullmatch(r"[a-z0-9-]+", a["stanowisko"] or ""):
                a["stanowisko"] = ""
        if a["url"] and not a["tresc"].strip():
            try:
                a["tresc"], title, found_mails, page_links = O.fetch(a["url"], deny=Z.blocked if a["zrodlo"] == "auto" else None)
            except RuntimeError as e:
                notes.append(str(e))
        elif a["url"] and a["zrodlo"] == "auto" and len(a["tresc"]) < 1500:
            with contextlib.suppress(RuntimeError):                       # z agregatora jest tylko skrót — próbuję pełnej treści
                full, title, found_mails, page_links = O.fetch(a["url"], deny=Z.blocked)
                if len(full) > len(a["tresc"]):
                    a["tresc"] = full
        if a["tresc"].strip():
            found_mails = found_mails or O.emails(a["tresc"])
            info = O.analyze(ctx, f, a["tresc"], title, a["url"])
            for k in ("firma", "stanowisko", "miasto"):
                a[k] = a[k].strip() or info[k]                          # to, co wpisała Aga, ma pierwszeństwo
            a["email"] = a["email"].strip() or info["email"] or (found_mails[0] if found_mails and a["zrodlo"] != "auto" else "")
            a["ocena"], a["ocena_opis"], a["rodo"] = info["ocena"], info["uzasadnienie"], info["rodo"]
            extra = {"ocena_modelu": info["ocena"]}
            with contextlib.suppress(Exception):                        # 2.19: czas dojazdu z domu Agi
                extra["dojazd"] = DJ.compute(ctx, info, a)
            a["analiza"] = json.dumps(dict({k: info.get(k) for k in ("adres", "wynagrodzenie", "wymagania", "obowiazki", "oferujemy")}, **extra),
                                      ensure_ascii=False)
            warn = info["ostrzezenia"]
            st0 = ctx.settings()
            if info.get("social_media") and not _ok_social_f(f):
                warn = warn + ["Główną częścią tej pracy są media społecznościowe, a ich nie chcesz."]
            if info.get("niedziele_wieczory") and st0.get("bez_niedziel_wieczorow"):
                warn = warn + ["Ogłoszenie wymaga pracy w niedziele albo wieczorami."]
            if info.get("tylko_prowizja") and st0.get("bez_prowizji"):
                warn = warn + ["Wynagrodzenie wyłącznie prowizyjne."]
            with R.db(ctx) as c:                                        # 2.16: zasady z uwag Agi do wcześniejszych ofert
                pw, likes = PF.check(c, a["tresc"], info.get("po_angielsku"))
            warn = warn + pw
            if likes and a.get("ocena") is not None:
                a["ocena"] = min(100, a["ocena"] + 8)
                a["ocena_opis"] = (a["ocena_opis"] + f" Lubisz takie oferty ({', '.join(likes[:3])}).").strip()
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
                why = warn[0].rstrip(".").lower()
            elif not R.in_area(a["miasto"], int(f["warunki"].get("dojazd_km") or 50)):
                why = f"za daleko ({a['miasto']})"
            elif DJ.too_far(ctx, analysis(a).get("dojazd"), O.netto_max(analysis(a).get("wynagrodzenie"))):
                why = DJ.too_far(ctx, analysis(a).get("dojazd"), O.netto_max(analysis(a).get("wynagrodzenie")))
            elif not a["tresc"].strip():
                why = "nie udało się odczytać ogłoszenia"
            if why:
                with R.db(ctx) as c:
                    R.set_status(c, ctx, aid, "odrzucona", firma=a["firma"], stanowisko=a["stanowisko"], miasto=a["miasto"], tresc=a["tresc"],
                                 klucz=a["klucz"], ocena=a.get("ocena"), ocena_opis=a.get("ocena_opis") or "", notatka="Pominięta automatycznie: " + why,
                                 analiza=a.get("analiza") or "")
                return "odrzucona"
        if not a["firma"] and not a["stanowisko"]:
            notes.append("Nie udało się ustalić firmy ani stanowiska. Uzupełnij je, a przygotuję dokumenty.")
            with R.db(ctx) as c:
                R.set_status(c, ctx, aid, "do_uzupelnienia", tresc=a["tresc"], uwagi=json.dumps(notes, ensure_ascii=False))
            return "do_uzupelnienia"
        web = {}
        if F.channel(a)["typ"] in ("formularz", "brak") and ctx.settings().get("szukaj_maila", True) and a["firma"]:
            with contextlib.suppress(Exception):
                web = K.find_email(ctx, a, K.offer_links("".join(f'<a href="{u}">' for u in page_links), a["url"] or "https://x.invalid/"))
            if web:
                a["email"] = web["email"]
                a["z_sieci"] = True
                how = {"ogloszenie": "na stronie firmy podlinkowanej w ogłoszeniu", "wyszukiwarka": "przez wyszukiwarkę na stronie firmy",
                       "domysl": "na stronie, którą uznałem za stronę firmy"}.get(web["sposob"], "na stronie firmy")
                notes.append(f"Ogłoszenie nie podaje adresu. Adres {web['email']} znalazłem {how}: {web['strona']} — sprawdź, czy to ta firma.")
        selection = D.select_for_offer(ctx, f, a) if a["tresc"].strip() else D.default_selection(f)
        profile = D.tailored_profile(ctx, f, a)
        if profile:
            selection.update(profil_tekst=profile, profil_zrodlo="model", profil_model=profile)
        fit_now = D.match_report(ctx, f, a, analysis(a).get("wymagania"))
        parts = D.score_parts(analysis(a).get("ocena_modelu", a.get("ocena")), fit_now, a.get("ocena"))
        if parts:
            a["ocena"] = parts["razem"]
        a["analiza"] = json.dumps(dict(analysis(a), dopasowanie=fit_now, v=2, ocena_skladniki=parts or {}, ocena_v=1,
                                       list_v=3 if GM.available(ctx) else 2), ensure_ascii=False)
        far = DJ.too_far(ctx, analysis(a).get("dojazd"), O.netto_max(analysis(a).get("wynagrodzenie")))
        if far and a["zrodlo"] != "auto":
            warn = warn + [far[:1].upper() + far[1:] + " — dłużej, niż chcesz (wyjątek tylko przy pensji powyżej "
                           f"{int(float(ctx.settings().get('dojazd_wyjatek_netto', 6500)))} zł netto)."]
        letter, mail, by_model = D.compose(ctx, f, a, selection)
        notes += D.check(ctx, f, a, letter + ("\n\nOpis w CV: " + profile if profile else ""), mail, by_model=by_model)
        if not by_model:
            notes.append("List ułożyłem z Twoich faktów bez modelu (model nie napisał wersji bez błędów). Jest poprawny, ale prostszy — możesz dopisać zdanie od siebie.")
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
        auto_ok = st.get("autopilot") and status == "do_zatwierdzenia" and not warn and (not web or web.get("sposob") == "ogloszenie") and (
            a["zrodlo"] == "spontaniczna" or (a.get("ocena") or 0) >= int(st.get("prog_autopilota", 75)))
        if auto_ok:
            status = "zatwierdzona"
            notes.append("Zatwierdzona przez autopilota (wysokie dopasowanie, kontrola prawdy bez uwag).")
        with R.db(ctx) as c:
            R.set_status(c, ctx, aid, status, firma=a["firma"], stanowisko=a["stanowisko"], miasto=a["miasto"], email=a["email"],
                         tresc=a["tresc"], klucz=a["klucz"], ocena=a.get("ocena"), ocena_opis=a.get("ocena_opis") or "",
                         rodo=a.get("rodo") or "", ostrzezenia=json.dumps(warn, ensure_ascii=False),
                         uwagi=json.dumps(notes, ensure_ascii=False), wybor=json.dumps(selection), temat=D.subject(f, a),
                         mail=mail, list=letter, cv_plik=cv, list_plik=li, kanal=json.dumps(ch), analiza=a.get("analiza") or "")
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
        if not me or not pwd:                                         # aplikacja wraca do kolejki, Aga widzi komunikat w panelu
            ctx.log.warning("Rekrutacja: wysyłka wstrzymana — brak hasła skrzynki Agi")
            with R.db(ctx) as c:
                R.set_status(c, ctx, a["id"], "zatwierdzona")
                R.meta_set(c, "problem_poczty", "Skrzynka Agi nie jest podłączona — podłącz ją w Ustawieniach (Skrzynki). Zatwierdzone aplikacje czekają w kolejce.")
                R.meta_set(c, "nastepna_wysylka", time.time() + 600)
            return None
        if not all(p.exists() for p in files):
            problem = "Brakuje plików PDF — przygotuj dokumenty ponownie."
        if not problem and not R.EMAIL_OK.match(a["email"] or ""):
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
                            "AND w.rodzaj IN ('zaproszenie','oferta','pytanie','zadanie','odmowa','do_potwierdzenia')", (today,)).fetchall()
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
    with contextlib.suppress(Exception), R.db(ctx) as c:
        lines += ["", OW.report_line(ctx, c, ctx.now().date())]
    lines += ["", f"Łącznie wysłanych: {total}. Zaproszenia i rozmowy: {invites}."]
    if queue:
        lines.append(f"W kolejce na kolejny dzień roboczy: {queue}.")
    lines.append(f"Czeka na Ciebie w panelu: {todo}." if todo else "Nic nie czeka na Twoją decyzję.")
    url = panel_url(ctx)
    if url:
        lines += ["", f"Panel: {url}"]
    lines += ["", "Dobrego wieczoru,", "Sebastian"]
    goal_n, done_n, streak_n = 0, 0, 0
    with contextlib.suppress(Exception), R.db(ctx) as c:
        day = ctx.now().date()
        goal_n, _ = OW.goal(c, ctx, day)
        done_n = OW.progress(c, day)["zrobione"]
        streak_n = OW.streak(c, ctx, day)
    data = {"wyslane": len(sent), "lista": [dict(r) for r in sent], "odpowiedzi": [dict(r, etykieta=A.KINDS.get(r["rodzaj"], r["rodzaj"])) for r in replies],
            "znalezione": found, "lacznie": total, "zaproszenia": invites, "kolejka": queue, "czeka": todo, "url": url or "",
            "cel": goal_n if ctx.settings().get("owca", True) else 0, "zrobione": done_n, "seria": streak_n, "tekst": "\n".join(lines)}
    report_text.last = data
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
    html, images = "", None
    with contextlib.suppress(Exception):
        subject, body, html, art = OW.report_email(ctx, report_text.last)
        images = {art: OW.image(art)}
    try:
        send(sender, R.secret(ctx, key), me, subject, body, name="Owca Sebastian" if html else "Sebastian", html=html, images=images)
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


RETRY_MARK = "%Wyślij do Sebastiana%"


def retry_blocked(ctx, now=None):
    """2.36.2: oferty, których portal chwilowo nie pokazał — po przerwie próbuję jeszcze raz (najwyżej 4 razy; odstępy pilnuje O.pace)."""
    now = now or time.time()
    with R.db(ctx) as c:
        if R.meta_get(c, "migracja_2362") == "":
            for a in [dict(r) for r in c.execute("SELECT id,url,firma,tresc,stanowisko,status FROM aplikacje WHERE url LIKE '%pracuj.pl/%' AND COALESCE(firma,'')='' "
                                                 "AND status NOT IN ('wysylanie','duplikat'," + ",".join(repr(x) for x in R.SENT) + ")")]:
                if not (O.junk_text(a) or (a["status"] == "do_uzupelnienia" and not a["tresc"].strip())):
                    continue
                stan = "" if re.fullmatch(r"[a-z0-9-]+", a["stanowisko"] or "") else a["stanowisko"]
                new = a["status"] if a["status"] == "odrzucona" else "nowa"
                c.execute("UPDATE aplikacje SET tresc='', stanowisko=?, status=?, uwagi='[]' WHERE id=?", (stan, new, a["id"]))
                R.note(c, ctx, a["id"], "pracuj.pl pokazał wcześniej stronę blokady zamiast ogłoszenia — pobiorę je jeszcze raz (2.36.2)")
            R.meta_set(c, "migracja_2362", R.stamp(ctx))
            c.commit()
        if R.meta_get(c, "migracja_2363") == "":                    # 2.36.3: oferty zatrzymane na błędzie 429 w 2.36.1 — z powrotem do kolejki
            for a in [dict(r) for r in c.execute("SELECT id FROM aplikacje WHERE status='do_uzupelnienia' AND COALESCE(tresc,'')='' AND url<>'' "
                                                 "AND COALESCE(firma,'')='' AND (uwagi LIKE '%429%' OR uwagi LIKE ? OR uwagi LIKE '%pustą stronę%')", (RETRY_MARK,))]:
                c.execute("UPDATE aplikacje SET status='nowa', uwagi='[]' WHERE id=?", (a["id"],))
                R.note(c, ctx, a["id"], "portal chwilowo blokował Sebastiana — oferta wraca do kolejki (2.36.3)")
            R.meta_set(c, "migracja_2363", R.stamp(ctx))
            c.commit()
        if now - float(R.meta_get(c, "ponow_blokady", "0") or 0) < 15 * 60:
            return 0
        R.meta_set(c, "ponow_blokady", str(now))
        done = 0
        for a in [dict(r) for r in c.execute("SELECT id,url FROM aplikacje WHERE status='do_uzupelnienia' AND COALESCE(tresc,'')='' AND url<>'' "
                                             "AND (uwagi LIKE ? OR uwagi LIKE '%błędem 429%') ORDER BY id", (RETRY_MARK,))]:
            n = int(R.meta_get(c, f"ponow_blokady_{a['id']}", "0") or 0)
            if n >= 4 or O.cooling(a["url"]):
                continue
            R.meta_set(c, f"ponow_blokady_{a['id']}", str(n + 1))
            c.execute("UPDATE aplikacje SET status='nowa', uwagi='[]' WHERE id=? AND status='do_uzupelnienia'", (a["id"],))
            done += 1
        c.commit()
        return done


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
    busy = False
    with contextlib.suppress(Exception):
        busy = Wd.work(ctx)                                           # import wiedzy ma pierwszeństwo — Aga czeka na wynik
    row = None
    if not busy:
        with contextlib.suppress(Exception):
            retry_blocked(ctx)
        with contextlib.suppress(Exception):
            estimate_pay(ctx)                                         # 2.19.2: najpierw oferty, na których Aga zarobi więcej
        row = next_to_prepare(ctx, manual_only=prepared_today >= int(target * 1.3))
    if row:
        prepare(ctx, row["id"])
    with R.db(ctx) as c:
        manual = time.time() - float(R.meta_get(c, "gemini_reczne", "0") or 0) < 300   # trwa polecenie „przepisz” — nie dzielę limitu
    if not busy and not manual:
        with contextlib.suppress(Exception):                          # czekające listy sprzed Gemini piszę na nowo (po jednym na obrót)
            recheck_profile(ctx) or refresh_letter(ctx) or (None if row else (refresh_match(ctx) or refresh_details(ctx)))
    with contextlib.suppress(Exception):                              # 2.20.2: procenty i dojazd zawsze, nie tylko gdy nic innego nie czeka
        refresh_scores(ctx)
    with contextlib.suppress(Exception):
        refresh_commute(ctx)
    with contextlib.suppress(Exception):
        refresh_cv_layout(ctx)
    send_one(ctx)
    with contextlib.suppress(Exception):
        CB.run(ctx)                                                   # CBOP: raz na dobę wieczorem, gdy jest nazwa partnera
    with contextlib.suppress(Exception):
        RZ.tick(ctx, P.send) or OW.stage_tick(ctx, P.send) or OW.tick(ctx, P.send)   # umówione przypomnienia, etapy, cel dnia
    with R.db(ctx) as c:
        talk = st.get("rozmowa", True) and _due(c, "ostatnia_rozmowa", 120)
    if talk:
        try:
            RZ.check_mail(ctx)                                        # Aga odpisała Sebastianowi — odpowiadam w tym samym wątku
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: rozmowa: {type(e).__name__}: {str(e)[:160]}")
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


def migrate_281(ctx):
    """2.8.1: niewłaściwe klauzule RODO w czekających aplikacjach → klauzula domyślna (pliki PDF na nowo)."""
    with R.db(ctx) as c:
        if R.meta_get(c, "migracja_281"):
            return
        rows = [dict(r) for r in c.execute("SELECT * FROM aplikacje WHERE status IN ('do_zatwierdzenia','do_sprawdzenia','do_uzupelnienia','formularz','zatwierdzona','blad') AND cv_plik<>''")]
    f = R.load_facts(ctx)
    crit = f["kryteria"]                                              # Andrzej i Aga: sprzedaż i obsługa klienta też wchodzą w grę
    crit["nie_chce"] = [x for x in crit.get("nie_chce", []) if x not in R.SALES_AVOID]
    crit["chce"] = list(dict.fromkeys(crit.get("chce", []) + ["sprzedaż i doradztwo", "obsługa klienta (biuro obsługi, recepcja, infolinia)"]))
    R.save_facts(ctx, f)
    for a in rows:
        if a["rodo"] and R.is_consent(a["rodo"]):
            continue
        with contextlib.suppress(Exception):
            cv, li = render_files(ctx, f, a, a["list"], json.loads(a["wybor"] or "null"), "")
            with R.db(ctx) as c:
                c.execute("UPDATE aplikacje SET rodo='', cv_plik=?, list_plik=? WHERE id=?", (cv, li, a["id"]))
                R.note(c, ctx, a["id"], "klauzula RODO zamieniona na domyślną (2.8.1)")
                c.commit()
    with R.db(ctx) as c:
        R.meta_set(c, "migracja_281", R.stamp(ctx))


def migrate_282(ctx):
    """2.8.2: czekające aplikacje przygotowane od nowa (analiza oferty, nowy list i mail, klauzula ze stanowiskiem);
    zatwierdzone — tylko PDF-y w nowym układzie, bez zmiany treści."""
    with R.db(ctx) as c:
        if R.meta_get(c, "migracja_282"):
            return
        again = [r["id"] for r in c.execute("SELECT id FROM aplikacje WHERE status IN ('do_zatwierdzenia','do_sprawdzenia','formularz') AND tresc<>''")]
        for aid in again:
            c.execute("UPDATE aplikacje SET status='nowa', uwagi='[]', zrodlo=CASE WHEN zrodlo='auto' THEN 'oferta' ELSE zrodlo END WHERE id=?", (aid,))
            R.note(c, ctx, aid, "przygotowana od nowa po aktualizacji 2.8.2 (nowy list, analiza oferty)")
        c.commit()
        keep = [dict(r) for r in c.execute("SELECT * FROM aplikacje WHERE status='zatwierdzona' AND cv_plik<>''")]
    f = R.load_facts(ctx)
    for a in keep:
        with contextlib.suppress(Exception):
            cv, li = render_files(ctx, f, a, a["list"], json.loads(a["wybor"] or "null"), a["rodo"])
            with R.db(ctx) as c:
                c.execute("UPDATE aplikacje SET cv_plik=?, list_plik=? WHERE id=? AND status='zatwierdzona'", (cv, li, a["id"]))
                c.commit()
    with R.db(ctx) as c:
        R.meta_set(c, "migracja_282", R.stamp(ctx))


REWRITE = ("do_zatwierdzenia", "do_sprawdzenia", "formularz")


def letters_to_rewrite(ctx, statuses=REWRITE):
    with R.db(ctx) as c:
        return [r["id"] for r in c.execute(f"SELECT id FROM aplikacje WHERE status IN ({','.join('?' * len(statuses))}) AND list<>'' "
                                           "AND analiza NOT LIKE '%\"list_v\": 3%' ORDER BY id DESC", statuses)]


def refresh_letter(ctx, statuses=REWRITE, only=None):
    """Jedna aplikacja z listem napisanym przed Gemini → nowy list (tylko gdy Gemini jest dostępne)."""
    if not GM.available(ctx):
        return None
    with R.db(ctx) as c:
        rows = c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(statuses))}) AND list<>'' "
                         "AND analiza NOT LIKE '%\"list_v\": 3%'" + (" AND id=?" if only else "") + " ORDER BY id DESC LIMIT 5",
                         (*statuses, *([only] if only else []))).fetchall()
    f = R.load_facts(ctx)
    for r in rows:
        a = dict(r)
        info = analysis(a)
        sel = json.loads(a["wybor"] or "null")
        t0 = time.time()
        GM.ONLY["on"] = True
        try:
            letter, mail, by_model = D.compose(ctx, f, a, sel)
        finally:
            GM.ONLY["on"] = False
        if not GM.used_since(t0):
            return None                                               # Gemini nie odpisało (limit, błąd) — spróbuję później
        info["list_v"] = 3
        names = (f["osoba"].get("imie", ""), f["osoba"].get("nazwisko", ""))
        with R.db(ctx) as c:
            cur = c.execute("SELECT status FROM aplikacje WHERE id=?", (a["id"],)).fetchone()
            if not cur or cur["status"] not in statuses:
                return None                                           # Aga w międzyczasie zatwierdziła albo odrzuciła — nie ruszam
            if by_model and not D.language_issues(letter, names):
                cv, li = render_files(ctx, f, a, letter, sel, a["rodo"])
                c.execute("UPDATE aplikacje SET list=?, mail=?, cv_plik=?, list_plik=?, analiza=?, zmieniono=? WHERE id=?",
                          (letter, mail, cv, li, json.dumps(info, ensure_ascii=False), R.stamp(ctx), a["id"]))
                R.note(c, ctx, a["id"], "list napisany na nowo (Gemini)")
            else:
                c.execute("UPDATE aplikacje SET analiza=? WHERE id=?", (json.dumps(info, ensure_ascii=False), a["id"]))
            c.commit()
        return a["id"]
    return None


def recheck_profile(ctx):
    """Czekające CV z opisem pisanym pod ofertę: jeśli są w nim słowa spoza faktów (np. „CMS”, „Agile” z ogłoszenia),
    wracam do Twojego zatwierdzonego opisu i składam CV na nowo (2.16.3). Po jednej aplikacji na obrót."""
    with R.db(ctx) as c:
        rows = c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.OPEN))}) AND wybor LIKE '%\"profil_zrodlo\": \"model\"%' "
                         "AND wybor NOT LIKE '%\"profil_v\": 2%' ORDER BY id DESC LIMIT 1", R.OPEN).fetchall()
    for r in rows:
        a = dict(r)
        f = R.load_facts(ctx)
        sel = json.loads(a["wybor"] or "{}")
        text = sel.get("profil_tekst") or ""
        bad = D.vocab_check(f, a, text) + D.rule_check(f, a, text)
        sel["profil_v"] = 2
        if bad:
            for k in ("profil_tekst", "profil_model", "profil_zrodlo"):
                sel.pop(k, None)
        with R.db(ctx) as c:
            c.execute("UPDATE aplikacje SET wybor=? WHERE id=?", (json.dumps(sel, ensure_ascii=False), a["id"]))
            c.commit()
        if bad:
            with contextlib.suppress(Exception):
                cv, li = render_files(ctx, f, a, a["list"] or "", sel, a.get("rodo") or "")
                with R.db(ctx) as c:
                    c.execute("UPDATE aplikacje SET cv_plik=?, list_plik=? WHERE id=?", (cv, li, a["id"]))
                    c.commit()
            with R.db(ctx) as c:
                R.note(c, ctx, a["id"], "opis w CV wrócił do Twojego zatwierdzonego (poprzedni zawierał rzeczy spoza Twoich faktów: "
                       + ", ".join(bad[:5]) + ")")
                c.commit()
        return a["id"]
    return None


def refresh_details(ctx):
    """Czekająca oferta bez wymagań i obowiązków (np. ucięta odpowiedź modelu) → jeszcze raz wyciągam punkty i dopasowanie (2.16.2)."""
    with R.db(ctx) as c:
        rows = c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.OPEN))}) AND length(tresc)>400 "
                         "AND analiza NOT LIKE '%\"szczegoly_v\": 1%' ORDER BY id DESC LIMIT 30", R.OPEN).fetchall()
    for r in rows:
        a = dict(r)
        info = analysis(a)
        if info.get("wymagania") or info.get("obowiazki"):
            continue
        f = R.load_facts(ctx)
        new = O.analyze(ctx, f, a["tresc"], a.get("stanowisko") or "", a.get("url") or "")
        for k in ("wymagania", "obowiazki", "oferujemy", "adres", "wynagrodzenie"):
            if new.get(k) and not info.get(k):
                info[k] = new[k]
        if info.get("wymagania"):
            info["dopasowanie"] = D.match_report(ctx, f, a, info["wymagania"])
            info["v"] = 2
        info["szczegoly_v"] = 1
        with R.db(ctx) as c:
            c.execute("UPDATE aplikacje SET analiza=? WHERE id=?", (json.dumps(info, ensure_ascii=False), a["id"]))
            if info.get("wymagania") or info.get("obowiazki"):
                R.note(c, ctx, a["id"], "uzupełnione wymagania i obowiązki z ogłoszenia")
            c.commit()
        return a["id"]
    return None


def pay_marks(ctx, a):
    """2.22: pensja na rękę i znacznik „dobrze płatna” (umowa o pracę albo niepodana, od progu z Ustawień) dla list."""
    info = analysis(a)
    p = O.pay_info(info.get("wynagrodzenie") or "", a.get("tresc") or "") if info.get("wynagrodzenie") else None
    a["netto"] = p["netto_do"] if p else None
    floor = int(float(ctx.settings().get("priorytet_netto", 5000)))
    a["top"] = bool(p and p["umowa"] in ("uop", "") and p["netto_do"] >= floor)
    return a


def pay_key(ctx, a):
    """Kolejność przygotowania: najpierw umowa o pracę (albo bez podanej umowy) z co najmniej 5000 zł na rękę,
    od najwyższej kwoty; potem pozostałe z podaną pensją (od najwyższej); na końcu bez pensji — w kolejności dodania."""
    info = analysis(a)
    est = info.get("pensja_wstepna") or {}
    net = est.get("netto_do")
    if not net:
        return (2, 0, a["id"])
    floor = int(float(ctx.settings().get("priorytet_netto", 5000)))
    top = est.get("umowa") in ("uop", "") and net >= floor
    return (0 if top else 1, -net, a["id"])


PAY_FETCH = True                                                     # w testach wyłączone — bez internetu


def estimate_pay(ctx, budget=90.0, limit=40):
    """Dla nowych ofert sprawdzam pensję przed przygotowaniem (bez modelu): z treści albo ze strony ogłoszenia."""
    start = time.time()
    with R.db(ctx) as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM aplikacje WHERE status='nowa' AND (analiza='' OR analiza NOT LIKE '%pensja_wstepna%') "
                                           "ORDER BY id LIMIT ?", (limit,))]
    for a in rows:
        if time.time() - start > budget:
            break
        text = a.get("tresc") or ""
        if len(text) < 300 and a.get("url") and PAY_FETCH and not O.cooling(a["url"]):
            with contextlib.suppress(Exception):
                text = O.fetch(a["url"], deny=Z.blocked if a["zrodlo"] == "auto" else None)[0]
                if not (a.get("tresc") or "").strip():                  # 2.36.2: zapisuję, żeby przygotowanie nie otwierało strony drugi raz
                    with R.db(ctx) as c:
                        c.execute("UPDATE aplikacje SET tresc=? WHERE id=? AND COALESCE(tresc,'')=''", (text[:20000], a["id"]))
                        c.commit()
        pay = O.salary(text)
        est = O.pay_info(pay, text) or {}
        est = {"netto_do": est.get("netto_do"), "umowa": est.get("umowa", O.contract(text)), "kwota": pay}
        info = analysis(a)
        info["pensja_wstepna"] = est
        with R.db(ctx) as c:
            c.execute("UPDATE aplikacje SET analiza=? WHERE id=? AND status='nowa'", (json.dumps(info, ensure_ascii=False), a["id"]))
            c.commit()


def next_to_prepare(ctx, manual_only=False):
    """Następna oferta do przygotowania: najpierw dodane przez Agę, w każdej grupie od najlepiej płatnej."""
    with R.db(ctx) as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM aplikacje WHERE status='nowa'")]
    rows = [a for a in rows if not (a["url"] and not (a["tresc"] or "").strip() and O.cooling(a["url"]))]   # 2.36.3: portal ma przerwę — czekają
    manual = [a for a in rows if a["zrodlo"] not in ("auto", "spontaniczna")]
    pool = manual or ([] if manual_only else rows)
    if not pool:
        return None
    best = min(pool, key=lambda a: pay_key(ctx, a))
    return {"id": best["id"]}




def refresh_cv_layout(ctx, limit=5):
    """Czekające CV układam na nowo po zmianie układu: cechy dobrane do ogłoszenia, wszystkie poprawki Agi zostają."""
    wait = ("do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "formularz")
    with R.db(ctx) as c:
        rows = [dict(r) for r in c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(wait))}) AND cv_plik<>'' "
                                           f"AND wybor<>'' AND wybor NOT LIKE '%\"uklad\": {D.CV_LAYOUT}%' ORDER BY id DESC LIMIT ?", wait + (limit,))]
    if not rows:
        return None
    f = R.load_facts(ctx)
    for a in rows:
        raw = json.loads(a["wybor"] or "{}")
        if isinstance(raw.get("wlasne_punkty"), dict):                   # poprawione brzmienia także w CV edytowanych ręcznie
            raw["wlasne_punkty"] = {k: [D.TEXT_FIXES.get(t, t) for t in v] for k, v in raw["wlasne_punkty"].items()}
        sel = D.clean_selection(f, raw)
        if not raw.get("cechy") and f.get("cechy"):
            sel["cechy"] = D.match_traits(f, (a.get("tresc") or "") + " " + (a.get("stanowisko") or "")) or sel["cechy"]
        try:
            cv, li = render_files(ctx, f, a, a["list"], sel, a["rodo"])
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: nowy układ CV dla {a['id']} — {type(e).__name__}: {e}")
            sel_mark = dict(raw, uklad=D.CV_LAYOUT)
            with R.db(ctx) as c:
                c.execute("UPDATE aplikacje SET wybor=? WHERE id=?", (json.dumps(sel_mark, ensure_ascii=False), a["id"]))
                c.commit()
            continue
        with R.db(ctx) as c:
            c.execute("UPDATE aplikacje SET wybor=?, cv_plik=?, list_plik=? WHERE id=? AND status=?",
                      (json.dumps(sel, ensure_ascii=False), cv, li, a["id"], a["status"]))
            c.commit()
    return rows[-1]["id"]


COMMUTE_NOW = set()                                                  # oferty, dla których dojazd liczy się właśnie w tle


def refresh_scores(ctx):
    """2.19: procent dopasowania liczony jawnie — dla wszystkich czekających ofert naraz (bez modelu, szybko)."""
    changed = None
    with R.db(ctx) as c:
        rows = [dict(r) for r in c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.OPEN))}) AND analiza<>'' "
                                           "AND analiza NOT LIKE '%\"ocena_v\": 1%'", R.OPEN)]
        for a in rows:
            info = analysis(a)
            model = info.get("ocena_modelu", a.get("ocena"))
            parts = D.score_parts(model, info.get("dopasowanie") or [], a.get("ocena"))
            info.update(ocena_modelu=model, ocena_skladniki=parts or {}, ocena_v=1)
            c.execute("UPDATE aplikacje SET analiza=?, ocena=? WHERE id=?",
                      (json.dumps(info, ensure_ascii=False), parts["razem"] if parts else a.get("ocena"), a["id"]))
            changed = a["id"]
        c.commit()
    return changed


def commute_due(ctx, a):
    d = analysis(a).get("dojazd")
    d = d if isinstance(d, dict) else {}
    home = (ctx.settings().get("dojazd_skad") or "").strip()
    if d.get("v") == DJ.WERSJA and d.get("skad") == home and not d.get("blad"):
        return False
    try:
        recent = time.time() - float(d.get("proba") or 0) < 900
    except (TypeError, ValueError):
        recent = False
    return not (d.get("blad") and recent)


def update_commute(ctx, aid):
    """Czas dojazdu dla jednej oferty; za długi dojazd przy ofercie znalezionej automatycznie — odkładam."""
    with R.db(ctx) as c:
        row = c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone()
    if not row:
        return None
    a = dict(row)
    info = analysis(a)
    d = DJ.compute(ctx, info, a)
    if d.get("blad"):
        d["proba"] = time.time()
        ctx.log.warning(f"Rekrutacja: dojazd dla oferty {aid} — {d['blad']}")
    far = DJ.too_far(ctx, d, O.netto_max(info.get("wynagrodzenie"), a.get("tresc") or ""))
    with R.db(ctx) as c:
        fresh = c.execute("SELECT analiza, status, ostrzezenia FROM aplikacje WHERE id=?", (aid,)).fetchone()
        info = json.loads(fresh["analiza"] or "{}") if fresh and (fresh["analiza"] or "").startswith("{") else info
        info["dojazd"] = d
        c.execute("UPDATE aplikacje SET analiza=? WHERE id=?", (json.dumps(info, ensure_ascii=False), aid))
        if far and a["zrodlo"] == "auto" and fresh["status"] in ("do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "formularz"):
            R.set_status(c, ctx, aid, "odrzucona", notatka="Pominięta automatycznie: " + far)
            R.note(c, ctx, aid, "odłożona: " + far)
        elif far:
            warn = json.loads(fresh["ostrzezenia"] or "[]")
            text = far[:1].upper() + far[1:] + " — dłużej, niż chcesz."
            if not any(w.startswith(text[:15]) for w in warn):
                c.execute("UPDATE aplikacje SET ostrzezenia=? WHERE id=?", (json.dumps(warn + [text], ensure_ascii=False), aid))
        c.commit()
    return d


def refresh_commute(ctx, budget=25.0):
    """Czasy dojazdu dla czekających ofert — kilka na obrót (2.20.2: niezależnie od innych prac w tle)."""
    start, done = time.time(), None
    wait = ("do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "formularz", "zatwierdzona")
    with R.db(ctx) as c:
        todo = [dict(r) for r in c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(wait))}) AND length(tresc)>200 "
                                           "ORDER BY (gwiazdka<>'') DESC, id DESC LIMIT 300", wait)]
    for a in todo:
        if time.time() - start > budget:
            break
        if commute_due(ctx, a):
            update_commute(ctx, a["id"])
            done = a["id"]
    return done


def refresh_score_commute(ctx):
    """Zgodność wstecz: procenty i czasy dojazdu."""
    a, b = refresh_scores(ctx), refresh_commute(ctx)
    return a or b


def refresh_match(ctx):
    """Jedna czekająca aplikacja ze starym opisem dopasowania → nowe, czytelne wyjaśnienia (2.8.5)."""
    with R.db(ctx) as c:
        rows = c.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.OPEN))}) AND analiza<>'' AND analiza NOT LIKE '%\"v\": 2%' "
                         "ORDER BY id DESC LIMIT 20", R.OPEN).fetchall()
    for r in rows:
        a = dict(r)
        info = analysis(a)
        if info.get("wymagania"):
            info["dopasowanie"] = D.match_report(ctx, R.load_facts(ctx), a, info["wymagania"])
        info["v"] = 2
        with R.db(ctx) as c:
            c.execute("UPDATE aplikacje SET analiza=? WHERE id=?", (json.dumps(info, ensure_ascii=False), a["id"]))
            c.commit()
        return a["id"]
    return None


def migrate_283(ctx):
    """2.8.3: wiadomości rozpoznane na nowo (potwierdzenia, reklamy portali, prośby o potwierdzenie nie są zaproszeniami ani odmowami);
    czekające listy z błędami (pisane do Agi, głosem pracodawcy) przygotowane od nowa."""
    with R.db(ctx) as c:
        if R.meta_get(c, "migracja_283"):
            return
        firms = {r["id"]: r["firma"] for r in c.execute("SELECT id, firma FROM aplikacje")}
        touched = set()
        for w in [dict(r) for r in c.execute("SELECT * FROM wiadomosci WHERE rodzaj IN ('zaproszenie','oferta','zadanie','odmowa','pytanie','inne')")]:
            rule = A.classify_rules(w)
            low = R.plain(f"{w['temat']}\n{w['tresc']}")
            new = rule if rule in ("do_potwierdzenia", "potwierdzenie", "reklama") else ""
            if w["rodzaj"] == "odmowa" and not re.search(A.REJECT_RE, low):
                new = new or "inne"
            if not new or new == w["rodzaj"] or (new != "do_potwierdzenia" and w["rodzaj"] == "zaproszenie" and re.search(A.INVITE_RE, low)):
                continue
            firm = firms.get(w["aplikacja_id"]) or w["od_nazwa"] or "Firma"
            summary = {"do_potwierdzenia": f"{firm}: system rekrutacyjny prosi, żebyś potwierdziła, że to Twoja aplikacja. Kliknij przycisk w wiadomości (otwórz ją w Gmailu).",
                       "potwierdzenie": f"{firm} potwierdza, że Twoja aplikacja dotarła.", "reklama": "Reklama portalu z ogłoszeniami — nic nie trzeba robić."}.get(new, w["streszczenie"])
            act = new == "do_potwierdzenia"
            c.execute("UPDATE wiadomosci SET rodzaj=?, wazne=?, status=?, streszczenie=?, szkic='' WHERE id=?",
                      (new, int(act), "nowa" if act and w["status"] == "nowa" else ("nowa" if act else "zalatwiona"), summary, w["id"]))
            if w["aplikacja_id"]:
                touched.add(w["aplikacja_id"])
        for aid in touched:                                          # status aplikacji z pozostałych, prawdziwych odpowiedzi
            kinds = [r["rodzaj"] for r in c.execute("SELECT rodzaj FROM wiadomosci WHERE aplikacja_id=?", (aid,))]
            cur = c.execute("SELECT status, podziekowanie FROM aplikacje WHERE id=?", (aid,)).fetchone()
            best = next((k for k in ("oferta", "zaproszenie", "odmowa", "pytanie") if k in kinds), "")
            if cur and cur["status"] in ("zaproszenie", "odmowa", "pytanie", "oferta") and cur["status"] not in kinds:
                R.set_status(c, ctx, aid, best or "wyslana")
                R.note(c, ctx, aid, "status poprawiony po ponownym rozpoznaniu odpowiedzi (2.8.3)")
            if cur and cur["podziekowanie"] == "czeka" and "odmowa" not in kinds:
                c.execute("UPDATE aplikacje SET podziekowanie='' WHERE id=?", (aid,))
        f = R.load_facts(ctx)
        names = (f["osoba"].get("imie", ""), f["osoba"].get("nazwisko", ""))
        for a in [dict(r) for r in c.execute("SELECT id, list, status FROM aplikacje WHERE status IN ('do_zatwierdzenia','do_sprawdzenia','formularz','zatwierdzona') AND list<>''")]:
            if D.language_issues(a["list"], names):
                c.execute("UPDATE aplikacje SET status='nowa', uwagi='[]', zrodlo=CASE WHEN zrodlo='auto' THEN 'oferta' ELSE zrodlo END WHERE id=? AND status=?", (a["id"], a["status"]))
                R.note(c, ctx, a["id"], "list miał błędy (pisany do Agi albo głosem pracodawcy) — przygotowuję od nowa (2.8.3)")
        R.meta_set(c, "migracja_283", R.stamp(ctx))
        c.commit()


def migrate_290(ctx):
    """2.10: owca wyśle jutro rano (jednorazowo) „Mam pomysł!” z instrukcją alertów."""
    with R.db(ctx) as c:
        if not R.meta_get(c, "owca_pomysl"):
            day = ctx.now().date() + __import__("datetime").timedelta(days=1)
            while not OW.working_day(ctx, day):
                day += __import__("datetime").timedelta(days=1)
            R.meta_set(c, "owca_pomysl", f"czeka:{day.isoformat()}")     # najbliższy dzień roboczy rano
            c.commit()


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
    with contextlib.suppress(Exception):
        migrate_281(ctx)
        migrate_282(ctx)
        migrate_283(ctx)
        migrate_290(ctx)
    with contextlib.suppress(Exception):
        PF.cleanup(ctx)                                                # 2.16.3: bez „Kraków” itp. na liście „pomijam”
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
                      PERMANENT_SESSION_LIFETIME=dt.timedelta(days=30), MAX_CONTENT_LENGTH=120 * 1024 * 1024)
    app.jinja_env.globals.update(STATUS=R.STATUS, STEPS=STEPS, TOOLS=R.TOOLS, LEVELS=R.LEVELS, WANT=R.WANT, AVOID=R.AVOID)
    app.jinja_env.filters["loads"] = lambda s: json.loads(s or "[]")

    def ext(url):
        """Atrybuty linku do ogłoszenia: na Windowsie (ustawienie „edge”) otwiera Microsoft Edge zamiast domyślnej przeglądarki."""
        from markupsafe import Markup, escape
        u = str(url or "")
        ua = request.headers.get("User-Agent", "") if request else ""
        if ctx.settings().get("edge", True) and "Windows" in ua and " Edg/" not in ua and u.lower().startswith(("http://", "https://")):
            return Markup(f'href="microsoft-edge:{escape(u)}"')
        return Markup(f'href="{escape(u)}" target="_blank" rel="noopener noreferrer"')
    app.jinja_env.globals["ext"] = ext
    def na_reke(pay, text=""):
        try:
            return O.netto_text(str(pay or ""), str(text or ""))
        except Exception:
            ctx.log.exception("Rekrutacja: przeliczenie pensji na rękę")
            return ""
    app.jinja_env.globals["na_reke"] = na_reke

    @app.errorhandler(500)
    def server_error(e):
        """2.27: zamiast gołego „Internal Server Error” — czytelna strona z kodem do wklejenia w czacie."""
        import traceback
        orig = getattr(e, "original_exception", None) or e
        tb = "".join(traceback.format_exception(type(orig), orig, orig.__traceback__))
        code = secrets.token_hex(3)
        ctx.log.error(f"Rekrutacja: błąd {code} na {request.path}\n{tb}")
        with contextlib.suppress(Exception):
            log = ctx.folder() / "bledy.log"
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(f"=== {dt.datetime.now():%Y-%m-%d %H:%M:%S} {code} {request.path}\n{tb}\n")
        last = [l for l in tb.strip().splitlines() if l.strip()][-6:]
        body = ("<!doctype html><meta charset=utf-8><title>Coś poszło nie tak</title>"
                "<body style='font-family:system-ui,sans-serif;max-width:760px;margin:60px auto;padding:0 20px;color:#222'>"
                "<h1 style='font-size:24px'>Ups — ta strona się nie otworzyła</h1>"
                "<p>Sebastian zapisał szczegóły błędu. Skopiuj poniższy fragment do czatu z Claude'em, a dostaniesz poprawkę.</p>"
                f"<pre style='white-space:pre-wrap;background:#f6f1e7;border:1px solid #e3d6bd;border-radius:10px;padding:14px;font-size:13px'>"
                f"Błąd {code} · {request.path}\n" + "\n".join(H.escape(l) for l in last) + "</pre>"
                "<p><a href='/'>Wróć do panelu</a></p></body>")
        return body, 500

    @app.route("/edge.reg")
    def edge_reg():
        """2.19: plik dla Windows — Chrome otwiera linki microsoft-edge: z tego panelu bez pytania (zasada AutoLaunchProtocolsFromOrigins)."""
        origin = f"{request.scheme}://{request.host}"
        if not re.fullmatch(r"https?://[A-Za-z0-9.\-]+(:\d+)?", origin):
            abort(400)
        rule = json.dumps([{"allowed_origins": [origin], "protocol": "microsoft-edge"}]).replace("\\", "\\\\").replace('"', '\\"')
        body = ("Windows Registry Editor Version 5.00\r\n\r\n[HKEY_CURRENT_USER\\Software\\Policies\\Google\\Chrome]\r\n"
                f'"AutoLaunchProtocolsFromOrigins"="{rule}"\r\n')
        from flask import Response
        return Response(b"\xff\xfe" + body.encode("utf-16-le"), mimetype="application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename=Sebastian_Edge_bez_pytania.reg"})

    @app.context_processor
    def theme():
        t = str(ctx.settings().get("motyw") or "bordo")
        return {"theme": t if t in ("bordo", "zielen", "krem") else "bordo"}
    app.jinja_env.filters["dzien"] = lambda s: (s or "")[:16].replace("T", " ")
    app.jinja_env.filters["czysty"] = P.clean_text
    app.jinja_env.filters["powod"] = lambda t: D.clean_reason(t)
    app.jinja_env.filters["host"] = lambda u: (re.sub(r"^https?://(www\.)?", "", u or "").split("/")[0])[:60]
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
        if request.endpoint == "pamiec_wgraj":                                # 2.30: duże eksporty czatów
            request.max_content_length = 4 * 1024 ** 3
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

    def sheep_page(title, text, art="brawo", extra=""):
        return render_template("owca.html", title=title, text=text, art=art, extra=extra, tab="")

    @app.route("/owca/<name>.png")
    def owca_art(name):
        if name not in ("rano", "motywacja", "brawo", "wieczor"):
            abort(404)
        return send_file(OW.ART / f"{name}.png", mimetype="image/png", max_age=86400)

    @app.route("/owca/cel/<tok>/<day>/<int:n>")
    def owca_goal(tok, day, n):
        db = ctx.db()
        try:
            if not hmac.compare_digest(tok, OW.token(db)) or day != ctx.now().date().isoformat():
                return sheep_page("Ten link już nie działa", "Cel można ustawić tylko w dniu, z którego jest mail. Zmienisz go też na stronie „Dziś”.", "rano"), 410
            n = OW.set_goal(db, ctx, ctx.now().date(), n)
        finally:
            db.close()
        return sheep_page(f"Cel na dziś: {n}", "Zapisane! Przejrzyj gotowe aplikacje, a wysyłkę biorę na siebie. Do dzieła!", "motywacja",
                          url_for("todo"))

    @app.route("/owca/etap/<tok>/<int:aid>/<action>")
    def owca_stage(tok, aid, action):
        db = ctx.db()
        try:
            if not hmac.compare_digest(tok, OW.token(db)):
                abort(403)
            if action == "przyjmuje" and not request.args.get("tak"):
                a = db.execute("SELECT firma FROM aplikacje WHERE id=?", (aid,)).fetchone()
                if not a:
                    abort(404)
                return sheep_page(f"Przyjmujesz ofertę od {a['firma']}?", "Wstrzymam wtedy szukanie i wysyłkę nowych aplikacji. Odpowiedzi nadal będę czytać.",
                                  "brawo", url_for("owca_stage", tok=tok, aid=aid, action=action, tak=1))
            msg = OW.stage_action(ctx, db, aid, action)
        finally:
            db.close()
        if msg is None:
            abort(404)
        return sheep_page("Zapisane", msg, "brawo" if action in ("oferta", "przyjmuje") else "rano")

    @app.route("/szybko")
    def quick_add():
        """Zakładka „Wyślij do Sebastiana”: adres i tekst oglądanego ogłoszenia → formularz do potwierdzenia (bez automatów na portalu)."""
        url = R.clean_url(request.args.get("u", "")[:2000])
        text = request.args.get("t", "").strip()[:15000]
        if url and not re.match(r"^https?://", url):
            url = ""
        dup = R.find_duplicate(g.db, "", "", url) if url else 0
        return render_template("szybko.html", url=url, text=text, dup=dup, tab="")

    @app.route("/wiecej-ofert")
    def more_offers():
        base = request.host_url.rstrip("/")
        js = ("javascript:(function(){var t=(document.body.innerText||'').slice(0,12000);"
              "window.open('" + base + "/szybko?u='+encodeURIComponent(location.href)+'&t='+encodeURIComponent(t),'_blank');})()")
        stats = g.db.execute("SELECT streszczenie, data FROM wiadomosci WHERE rodzaj='alert' ORDER BY id DESC LIMIT 12").fetchall()
        week = g.db.execute("SELECT COUNT(*) FROM historia WHERE co LIKE 'znaleziona: alert%' AND kiedy >= ?",
                            ((ctx.now() - __import__('datetime').timedelta(days=7)).isoformat(),)).fetchone()[0]
        done = json.loads(R.meta_get(g.db, "wiecej_ofert_zrobione") or "[]")
        return render_template("wiecej_ofert.html", js=js, stats=stats, week=week, done=done, steps=OW.MORE_STEPS, tab="",
                               cbop=R.meta_get(g.db, "cbop_wynik"), partner=bool(ctx.settings().get("cbop_partner")))

    @app.route("/wiecej-ofert", methods=["POST"])
    def more_offers_tick():
        done = set(json.loads(R.meta_get(g.db, "wiecej_ofert_zrobione") or "[]"))
        k = request.form.get("krok", "")
        done.symmetric_difference_update({k}) if k in {x[0] for x in OW.MORE_STEPS} else None
        R.meta_set(g.db, "wiecej_ofert_zrobione", json.dumps(sorted(done)))
        g.db.commit()
        return redirect(url_for("more_offers") + "#" + k)

    @app.route("/owca/cel", methods=["POST"])
    def owca_set():
        with contextlib.suppress(ValueError):
            OW.set_goal(g.db, ctx, ctx.now().date(), int(request.form.get("cel", "0")))
        return redirect(url_for("home"))

    @app.route("/rozmowa", methods=["GET", "POST"])
    def talk():
        if request.method == "POST":
            what = request.form.get("co", "")
            if what == "napisz" and request.form.get("tresc", "").strip():
                RZ.reply_to(ctx, "panel", request.form["tresc"][:3000])
            elif what == "zapomnij":
                g.db.execute("DELETE FROM rozmowa_pamiec WHERE id=?", (request.form.get("id", 0),)); g.db.commit()
            elif what == "odwolaj":
                g.db.execute("DELETE FROM rozmowa_przypomnienia WHERE id=? AND wyslano=''", (request.form.get("id", 0),)); g.db.commit()
            elif what == "koniec_przerwy":
                RZ.end_pause(g.db, ctx)
            return redirect(url_for("talk") + "#dol")
        RZ.ensure(g.db)
        rows = RZ.history(g.db, 80)
        return render_template("rozmowa.html", tab="rozmowa", rows=rows, mem=RZ.memory(g.db), rem=RZ.pending_reminders(g.db),
                               pause=RZ.pause_until(g.db, ctx), on=ctx.settings().get("rozmowa", True))

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
                         "do": request.form.get(f"d{i}_do", "").strip(), "punkty": lines(f"d{i}_punkty"),
                         "szczegoly": lines(f"d{i}_szczegoly"),
                         "opcjonalne": bool(request.form.get(f"d{i}_opcjonalne"))})
        f["doswiadczenie"] = jobs
        edu = []
        for i in range(int(request.form.get("ile_szkol", 0))):
            edu.append({"uczelnia": request.form.get(f"w{i}_uczelnia", "").strip(), "kierunek": request.form.get(f"w{i}_kierunek", "").strip(),
                        "tytul": request.form.get(f"w{i}_tytul", "").strip(), "okres": request.form.get(f"w{i}_okres", "").strip()})
        f["wyksztalcenie"] = edu
        f["kursy"], f["jezyki"], f["profil"] = lines("kursy"), lines("jezyki"), lines("profil")
        if "cechy" in request.form:
            f["cechy"] = lines("cechy")
        if "profil_wzory" in request.form:
            f["profil_wzory"] = lines("profil_wzory")
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
                "odpowiedzi": msgs + qs, "pytania": qs,
                "gwiazdki": c.execute("SELECT COUNT(*) FROM aplikacje WHERE gwiazdka<>''").fetchone()[0]}

    @app.context_processor
    def common():
        if "db" not in g:
            return {}
        st = ctx.settings()
        return {"n": counts(g.db), "st": st, "okno": window(ctx, st), "problem_poczty": R.meta_get(g.db, "problem_poczty")}

    @app.route("/")
    def home():
        rows = g.db.execute("SELECT * FROM aplikacje WHERE status NOT IN ('duplikat') ORDER BY zmieniono DESC LIMIT 8").fetchall()
        day = ctx.now().date()
        goal_n, own = OW.goal(g.db, ctx, day)
        prog = OW.progress(g.db, day)
        sheep = {"cel": goal_n, "wlasny": own, "zrobione": prog["zrobione"], "seria": OW.streak(g.db, ctx, day), "czeka": prog["czeka"],
                 "procent": min(100, round(100 * prog["zrobione"] / goal_n)) if goal_n else 0, "dzien_roboczy": OW.working_day(ctx, day)}
        return render_template("dzis.html", przerwy=O.pauses(), rows=rows, tab="dzis", me=R.mailboxes(g.db)[0], sheep=sheep, GOALS=OW.GOALS)

    @app.route("/dodaj", methods=["POST"])
    def add():
        url, firma = R.clean_url(request.form.get("url", "")), request.form.get("firma", "").strip()
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
        rows = [pay_marks(ctx, dict(r)) for r in
                g.db.execute(f"SELECT * FROM aplikacje WHERE status IN ({','.join('?' * len(R.TODO))}) ORDER BY zmieniono DESC", R.TODO)]
        rows.sort(key=lambda r: (0 if r["top"] else 1, -(r["netto"] or 0) if r["top"] else 0))   # 2.22: najlepiej płatne na górze
        top = sum(1 for r in rows if r["top"])
        intro = (f"Na górze, ze złotym paskiem: {top} {'oferta' if top == 1 else 'oferty' if top % 10 in (2, 3, 4) and top % 100 not in (12, 13, 14) else 'ofert'} "
                 f"z umową o pracę i co najmniej {int(float(ctx.settings().get('priorytet_netto', 5000)))} zł na rękę — od najwyższej pensji.") if top else ""
        return render_template("lista.html", rows=rows, tab="todo", title="Do zrobienia", intro=intro,
                               empty="Wszystko załatwione. Nic nie czeka na Twoją decyzję.")

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

    # ---- 2.21: Centrum dowodzenia Agi i aktualizacja jednym plikiem
    def updater():
        root = Path(app.config.get("SEBASTIAN_ROOT") or HERE.parents[1])
        import importlib.util
        spec = importlib.util.spec_from_file_location("sebastian_aktualizator", root / "aktualizator.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sd = ctx.folder().parents[1] / "aktualizacje"
        sd.mkdir(parents=True, exist_ok=True)
        return mod, root, sd

    def tiles(root):
        try:
            c = json.loads((root / "data" / "centrum.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            c = {}
        return [{"id": "rekrutacja", "nazwa": "Rekrutacja", "opis": "Oferty, CV, listy i odpowiedzi od pracodawców", "url": url_for("home"), "znak": "R"},
                {"id": "sebastian", "nazwa": "Sebastian", "opis": "Panel główny: poczta, sprawy, nauka, WhatsApp", "url": c.get("sebastian", ""), "znak": "S"},
                {"id": "gwaranci", "nazwa": "Gwaranci Feniks", "opis": "Spotkania gwaranckie zespołu", "url": c.get("gwaranci", ""), "znak": "G"},
                {"id": "pamiec", "nazwa": "Sebastian uczy się o Tobie", "opis": "Jego pytania do Ciebie, Twój profil, wgrywanie wiedzy", "url": "/pamiec", "znak": "🐑"},
                {"id": "terminal", "nazwa": "Terminal", "opis": "Dla Andrzeja — pełny dostęp do Maca", "url": c.get("terminal", ""), "znak": ">_"}]

    @app.route("/centrum")
    def centrum():
        mod, root, sd = updater()
        try:
            past = json.loads((sd / "historia.json").read_text(encoding="utf-8"))[:8]
        except (OSError, ValueError):
            past = []
        return render_template("centrum.html", tab="centrum", tiles=tiles(root), wersja=mod.current_version(root),
                               stan=mod.load_state(sd), trwa=mod.busy(sd), historia=past, blad=request.args.get("blad", ""))

    @app.route("/centrum/aktualizuj", methods=["POST"])
    def centrum_update():
        mod, root, sd = updater()
        stored = R.meta_get(g.db, "haslo", "")
        if not stored or not check_password_hash(stored, request.form.get("haslo", "")):
            return redirect(url_for("centrum", blad="Hasło się nie zgadza — wpisz to samo, którym logujesz się do panelu."))
        if mod.busy(sd):
            return redirect(url_for("centrum", blad="Aktualizacja już trwa — poczekaj, aż się skończy."))
        up = request.files.get("plik")
        data = up.read() if up else b""
        if not data:
            return redirect(url_for("centrum", blad="Wybierz plik aktualizacji (Sebastian_aktualizacja_….py)."))
        ok, info = mod.inspect(data, mod.current_version(root))
        if not ok:
            return redirect(url_for("centrum", blad=info))
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", up.filename or "aktualizacja.py")[-80:]
        path = sd / f"{dt.datetime.now():%Y%m%d-%H%M%S}_{name if name.endswith('.py') else name + '.py'}"
        path.write_bytes(data)
        if app.config.get("TESTING"):
            mod.run(path, root=root, sd=sd, do_git=False, restart=False)
        else:
            mod.start_detached(path, root=root, sd=sd)
        return redirect(url_for("centrum", postep=1))

    @app.route("/centrum/stan")
    def centrum_state():
        mod, root, sd = updater()
        st = mod.load_state(sd)
        st["linie"] = [l for l in (st.get("linie") or []) if l.strip()][-40:]
        st["wersja"] = mod.current_version(root)
        st["trwa"] = mod.busy(sd)
        return st

    @app.route("/centrum/github", methods=["POST"])
    def centrum_github():
        mod, root, sd = updater()
        st = mod.load_state(sd)
        good, msg = mod.push(root, sd, mod.git_command("", st.get("do") or mod.current_version(root), st.get("tytul") or ""))
        mod.save_state(sd, github="zmiany zapisane na GitHubie" if good else "nadal nie udało się wysłać: " + msg)
        return redirect(url_for("centrum"))

    @app.route("/centrum/skrot.url")
    def centrum_shortcut():
        """Skrót na pulpit Windows — dwuklik otwiera Centrum dowodzenia."""
        from flask import Response
        target = f"{request.scheme}://{request.host}{url_for('centrum')}"
        body = f"[InternetShortcut]\r\nURL={target}\r\nIconIndex=0\r\n"
        return Response(body.encode("utf-8"), mimetype="application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename=Centrum_dowodzenia_Agi.url"})

    @app.route("/wazne")
    def starred():
        rows = g.db.execute("SELECT * FROM aplikacje WHERE gwiazdka<>'' ORDER BY gwiazdka DESC").fetchall()
        return render_template("lista.html", rows=rows, tab="wazne", title="★ Ważne oferty", search=False,
                               intro="Oferty, które oznaczyłaś gwiazdką. Gwiazdkę zdejmiesz na stronie oferty.",
                               empty="Nie masz jeszcze ważnych ofert. Wejdź w ofertę i kliknij ☆ obok nazwy firmy.")

    @app.route("/aplikacja/<int:aid>/gwiazdka", methods=["POST"])
    def star(aid):
        a = get(aid)
        on = not a["gwiazdka"]
        g.db.execute("UPDATE aplikacje SET gwiazdka=? WHERE id=?", (R.stamp(ctx) if on else "", aid))
        R.note(g.db, ctx, aid, "oznaczona gwiazdką jako ważna" if on else "gwiazdka zdjęta")
        g.db.commit()
        back = request.form.get("wroc", "")
        return redirect(back if back.startswith("/") and not back.startswith("//") else url_for("detail", aid=aid))

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
        info = analysis(dict(a))
        if info.get("dopasowanie") and not info.get("ocena_v"):          # 2.20.2: procent od razu przy otwarciu
            with contextlib.suppress(Exception):
                refresh_scores(ctx)
                a = get(aid)
                info = analysis(dict(a))
        commute_wait = False
        if a["tresc"] and a["status"] not in ("nowa", "przygotowywanie") and commute_due(ctx, dict(a)):
            commute_wait = True
            if aid not in COMMUTE_NOW:
                COMMUTE_NOW.add(aid)
                def run(aid=aid):
                    try:
                        update_commute(ctx, aid)
                    except Exception:
                        ctx.log.exception("Rekrutacja: dojazd przy otwarciu oferty")
                    finally:
                        COMMUTE_NOW.discard(aid)
                if app.config.get("TESTING"):
                    run()
                    a = get(aid)
                    info = analysis(dict(a))
                    commute_wait = False
                else:
                    threading.Thread(target=run, daemon=True).start()
        where = info.get("adres") or a["miasto"] or ""
        km = R.km_from_krakow(" ".join((where, a["miasto"] or "")))
        from urllib.parse import quote
        maps = ("https://www.google.com/maps/dir/?api=1&travelmode=transit&origin=" + quote(ctx.settings().get("dojazd_skad") or "Kraków")
                + "&destination=" + quote(where)) if where and km != -1 else ""
        fit = [dict(x, ocena=x.get("ocena") or "brak") for x in (info.get("dopasowanie") or []) if isinstance(x, dict)]
        dj = info.get("dojazd") if isinstance(info.get("dojazd"), dict) else {}
        if dj.get("cel") and dj.get("skad") and km != -1:
            maps = ("https://www.google.com/maps/dir/?api=1&travelmode=transit&origin=" + quote(dj["skad"]) + "&destination=" + quote(dj["cel"]))
        try:
            blocks = O.pretty(a["tresc"] or "", a["stanowisko"] or "")
        except Exception:
            ctx.log.exception(f"Rekrutacja: układ treści ogłoszenia {aid}")
            blocks = []
        parts = info.get("ocena_skladniki") if isinstance(info.get("ocena_skladniki"), dict) else {}
        return render_template("aplikacja.html", dj=dj, commute_wait=commute_wait, DJL=DJ.label, parts=parts, blocks=blocks, a=a, hist=hist, msgs=msgs, tab="", TAGS=PF.TAGS, TAGN=PF.TAG_NAMES, feedback=PF.feedback_for(g.db, aid),
                               saved=request.args.get("zapisano") == "1", kit=F.kit(R.load_facts(ctx), a) if a["status"] == "formularz" else [],
                               info=info, where=where, km=km, maps=maps, fit=fit,
                               fit_count={k: sum(1 for x in fit if x["ocena"] == k) for k in ("mam", "czesciowo", "brak")},
                               KINDS=A.KINDS, editable=a["status"] in ("do_zatwierdzenia", "do_sprawdzenia", "do_uzupelnienia", "formularz", "blad", "zatwierdzona", "odrzucona"))

    @app.route("/aplikacja/<int:aid>/uwaga", methods=["POST"])
    def feedback(aid):
        a = dict(get(aid))
        tags = request.form.getlist("tag")
        text = request.form.get("uwaga", "")
        if not tags and not text.strip():
            flash("Zaznacz, co nie pasuje, albo napisz kilka słów.")
            return redirect(url_for("detail", aid=aid) + "#uwaga")
        fid = PF.save_feedback(ctx, aid, tags, text)                  # zapis od razu; nauka (model) w tle, żeby nic nie czekało

        def learn_later():
            with contextlib.suppress(Exception):
                if PF.learn_from(ctx, fid):
                    PF.flag_waiting(ctx, skip=aid)
        if app.config.get("TESTING"):
            learn_later()
        else:
            threading.Thread(target=learn_later, daemon=True, name="rekrutacja-uwaga").start()
        if request.form.get("co") == "pomin" and a["status"] not in R.SENT + ("wysylanie",):
            R.set_status(g.db, ctx, aid, "odrzucona")
            flash("Zapisałem uwagę i pominąłem ofertę. Czego się z niej nauczyłem, zobaczysz w Ustawieniach → Czego szukam.")
            return redirect(url_for("todo"))
        return redirect(url_for("detail", aid=aid, zapisano=1) + "#uwaga")

    @app.route("/preferencje", methods=["POST"])
    def prefs():
        p = PF.load(g.db)
        what, i = request.form.get("co", ""), request.form.get("i", "")
        if what == "angielski":
            p["angielski"] = bool(request.form.get("angielski"))
        elif what in ("usun_unikaj", "usun_lubi", "usun_zasade") and i.isdigit():
            key = {"usun_unikaj": "unikaj", "usun_lubi": "lubi", "usun_zasade": "zasady"}[what]
            if int(i) < len(p[key]):
                p[key].pop(int(i))
        elif what == "dodaj_unikaj" and request.form.get("haslo", "").strip():
            h = request.form["haslo"].strip()[:40]
            if R.plain(h) not in {R.plain(u["haslo"]) for u in p["unikaj"]}:
                p["unikaj"].append({"haslo": h, "skad": 0, "kiedy": R.stamp(ctx)})
        PF.save(g.db, p)
        PF.flag_waiting(ctx)                                           # ostrzeżenia przy czekających ofertach według aktualnych zasad
        flash("Zapisane.")
        return redirect(url_for("settings") + "#nauka")

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

    @app.route("/aplikacja/<int:aid>/cv", methods=["GET", "POST"])
    def edit_cv(aid):
        a = dict(get(aid))
        f = R.load_facts(ctx)
        sel = D.clean_selection(f, json.loads(a["wybor"] or "null"))
        locked = a["status"] in R.SENT + ("wysylanie", "nowa", "przygotowywanie", "duplikat") or not a["cv_plik"]
        if request.method == "POST":
            if locked:
                flash("Tego CV nie można już zmienić." if a["status"] in R.SENT else "CV nie jest jeszcze gotowe.")
                return redirect(url_for("detail", aid=aid))
            if a["status"] == "zatwierdzona":                               # nie podmieniamy plików pod ręką wysyłki
                cur = g.db.execute("UPDATE aplikacje SET status='do_zatwierdzenia' WHERE id=? AND status='zatwierdzona'", (aid,))
                g.db.commit()
                if not cur.rowcount:
                    flash("Ta aplikacja jest właśnie wysyłana — CV zostaje bez zmian.")
                    return redirect(url_for("detail", aid=aid))
                R.note(g.db, ctx, aid, "wstrzymana do ponownego zatwierdzenia (edycja CV)")
                flash("Aplikacja wróciła do zatwierdzenia — po poprawkach kliknij „Zatwierdź i wyślij”.")
            try:
                if request.form.get("co") == "przywroc":
                    sel = D.reset_cv_edit(f, sel)
                    what = "CV: przywrócona wersja Sebastiana"
                else:
                    jobs = [j["id"] for j in f["doswiadczenie"]]
                    pts = {j: request.form.getlist("p_" + j) for j in jobs}
                    sel = D.apply_cv_edit(f, sel, request.form.get("profil", ""), pts, request.form.getlist("pokaz"))
                    if "rodo_formularz" in request.form:                   # 2.26: klauzula RODO poprawiona przez Agę
                        text = re.sub(r"\s+", " ", request.form.get("rodo_tekst", "")).strip()[:2500]
                        default = R.consent_clause(a.get("firma", ""), a.get("rodo") or "", "" if a["zrodlo"] == "spontaniczna" else (a.get("stanowisko") or ""))
                        if text and re.sub(r"\s+", " ", default).strip() != text:
                            sel["rodo_aga"] = text
                        else:
                            sel.pop("rodo_aga", None)
                    if "kursy_formularz" in request.form:                  # 2.23: kursy zaznaczone przez Agę
                        pool = {k["id"] for k in f["kursy"]}
                        chosen = [x for x in request.form.getlist("kursy") if x in pool]
                        if chosen:
                            sel["kursy"] = chosen
                    if "narzedzia_formularz" in request.form:              # 2.34: narzędzia zaznaczone przez Agę
                        pool = {t["id"] for t in f["narzedzia"]}
                        chosen = [x for x in request.form.getlist("narzedzia") if x in pool]
                        if chosen:
                            sel["narzedzia"] = chosen
                    if "cechy_formularz" in request.form:                  # 2.22: cechy zaznaczone przez Agę
                        pool = {c["id"] for c in f.get("cechy", [])}
                        chosen = [x for x in request.form.getlist("cechy") if x in pool]
                        if chosen:
                            sel["cechy"] = chosen
                    what = "CV: poprawki Agi"
                cv, li = render_files(ctx, f, a, a["list"], sel, a["rodo"])
            except ValueError as e:
                flash(str(e))
                return redirect(url_for("edit_cv", aid=aid))
            g.db.execute("UPDATE aplikacje SET wybor=?, cv_plik=?, list_plik=?, zmieniono=? WHERE id=?",
                         (json.dumps(sel, ensure_ascii=False), cv, li, R.stamp(ctx), aid))
            R.note(g.db, ctx, aid, what)
            g.db.commit()
            flash("CV zapisane i ułożone na nowo.")
            return redirect(url_for("edit_cv", aid=aid, ok=1))
        profile, points = D.cv_content(f, sel)
        jobs = [j for j in sorted(f["doswiadczenie"], key=lambda j: (D._ym(j.get("do")), D._ym(j.get("od"))), reverse=True)]
        rows = []
        for j in jobs:
            now = points.get(j["id"]) or [p["tekst"] for p in j["punkty"]][:D.POINTS_PER_JOB]
            pool = [p["tekst"] for p in j["punkty"]]
            rows.append({"j": j, "w_cv": j["id"] in sel["kolejnosc"], "punkty": now,
                         "lista": [{"t": t, "on": True} for t in now if t in pool] + [{"t": t, "on": False} for t in pool if t not in now],
                         "inne": [t for t in now if t not in pool], "wlasne": j["id"] in sel.get("wlasne_punkty", {})})
        traits = [{"id": c["id"], "t": c["tekst"], "on": c["id"] in sel.get("cechy", [])} for c in f.get("cechy", [])]
        courses = [{"id": k["id"], "t": k["tekst"], "on": k["id"] in sel.get("kursy", [])} for k in D.courses_newest_first(f["kursy"])]
        tools = [{"id": t["id"], "t": t["nazwa"] + (f" – {t['poziom']}" if t["poziom"] else ""), "on": t["id"] in sel.get("narzedzia", [])}
                 for t in f["narzedzia"]]
        rodo_default = R.consent_clause(a.get("firma", ""), a.get("rodo") or "", "" if a["zrodlo"] == "spontaniczna" else (a.get("stanowisko") or ""))
        rodo_now = sel.get("rodo_aga") or rodo_default
        return render_template("edytuj_cv.html", a=a, tab="", profil=profile, rows=rows, locked=locked, n=D.POINTS_PER_JOB, cechy=traits, kursy=courses, narzedzia=tools,
                               rodo_now=rodo_now, rodo_own=bool(sel.get("rodo_aga")), rodo_employer=bool(a.get("rodo") and R.is_consent(a["rodo"])),
                               zrodlo=sel.get("profil_zrodlo", ""), edited=bool(sel.get("wlasne_punkty") or sel.get("ukryte") or sel.get("pokazane") or sel.get("rodo_aga")
                                                                                or sel.get("profil_zrodlo") == "aga"))

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
        links = re.findall(r"https?://[^\s<>\"']+", request.form.get("linki", "").replace("&gt;", ">"))
        added = dup = 0
        for url in dict.fromkeys(u for u in (R.clean_url(l) for l in links) if u):
            if R.find_duplicate(g.db, "", "", url):
                dup += 1
                continue
            now = R.stamp(ctx)
            cur = g.db.execute("INSERT INTO aplikacje(utworzono,zmieniono,status,zrodlo,url) VALUES(?,?,?,?,?)", (now, now, "nowa", "oferta", url))
            R.note(g.db, ctx, cur.lastrowid, "dodana przez Agę (lista linków)")
            g.db.execute("INSERT OR IGNORE INTO widziane(url,kiedy,zrodlo_id) VALUES(?,?,0)", (R.norm_url(url), now))
            added += 1
        g.db.commit()
        slow = sum("pracuj.pl" in O.host(u) for u in dict.fromkeys(R.clean_url(l) for l in links))
        flash(f"Dodane: {added}." + (f" Pominięte jako powtórki: {dup}." if dup else "") + (" Przygotuję je po kolei." if added else "")
              + (" Ogłoszenia z pracuj.pl otwieram co pół minuty, żeby portal nie zablokował Maca." if slow and added else ""))
        return redirect(url_for("home"))

    @app.route("/odpowiedzi")
    def replies():
        everything = bool(request.args.get("wszystkie"))
        quiet = "" if everything else f"WHERE w.rodzaj NOT IN ({','.join(repr(k) for k in A.QUIET)}) "
        rows = g.db.execute("SELECT w.*, a.firma, a.stanowisko FROM wiadomosci w LEFT JOIN aplikacje a ON a.id=w.aplikacja_id " + quiet +
                            "ORDER BY (w.status='nowa' AND w.wazne=1) DESC, w.id DESC LIMIT 200").fetchall()
        hidden = 0 if everything else g.db.execute(f"SELECT COUNT(*) FROM wiadomosci WHERE rodzaj IN ({','.join('?' * len(A.QUIET))})", A.QUIET).fetchone()[0]
        qs = g.db.execute("SELECT p.*, a.firma FROM pytania p LEFT JOIN aplikacje a ON a.id=p.aplikacja_id WHERE p.status='otwarte' ORDER BY p.id").fetchall()
        return render_template("odpowiedzi.html", rows=rows, qs=qs, tab="odp", KINDS=A.KINDS, hidden=hidden, everything=everything)

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
        from urllib.parse import quote
        gmail = ("https://mail.google.com/mail/u/0/#search/" + quote("rfc822msgid:" + m["message_id"].strip("<>"))) if m["message_id"] else ""
        return render_template("wiadomosc.html", m=m, qs=qs, tab="odp", KINDS=A.KINDS, gmail=gmail,
                               links=[x for x in json.loads(m["linki"] or "[]") if str(x.get("url", "")).lower().startswith(("http://", "https://"))])

    @app.route("/import-wiedzy", methods=["GET", "POST"])
    def knowledge():
        if request.method == "POST":
            what = request.form.get("co", "")
            if what == "start":
                up = request.files.get("plik")
                n, msg = Wd.start(ctx, request.form.get("tekst", ""), up.read() if up and up.filename else None, up.filename if up else "")
                flash(msg or f"Czytam ({n} {'część' if n == 1 else 'części'}). Strona odświeży się sama.")
            elif what == "zastosuj":
                ids = {int(x) for x in request.form.getlist("k") if x.isdigit()}
                flash(f"Dodane do Twojej bazy faktów: {Wd.apply(ctx, ids)}. Zobaczysz je w Ustawieniach → Twoje dane.")
            elif what == "anuluj":
                Wd.clear(ctx)
            return redirect(url_for("knowledge"))
        return render_template("import.html", job=Wd.load(ctx), tab="ust")

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
                for key in ("bez_niedziel_wieczorow", "bez_prowizji"):
                    ctx.set_setting(key, "tak" if request.form.get(key) else "nie")
                ctx.set_setting("owca", "tak" if request.form.get("owca") else "nie")
                ctx.set_setting("rozmowa", "tak" if request.form.get("rozmowa") else "nie")
                ctx.set_setting("edge", "tak" if request.form.get("edge") else "nie")
                if request.form.get("motyw") in ("bordo", "zielen", "krem"):
                    ctx.set_setting("motyw", request.form["motyw"])
                for key in ("owca_rano", "owca_przypomnienia"):
                    val = re.sub(r"\s+", "", request.form.get(key, ""))
                    if val and re.fullmatch(r"\d{1,2}:\d{2}(,\d{1,2}:\d{2})*", val):
                        ctx.set_setting(key, val)
                for key in ("dojazd_skad", "model_pisania"):
                    if key in request.form:
                        ctx.set_setting(key, re.sub(r"[\r\n<>]", " ", request.form.get(key, "")).strip()[:120])
                if request.form.get("dojazd_tryb") in ("lub", "i"):
                    ctx.set_setting("dojazd_tryb", request.form["dojazd_tryb"])
                for key, lo, hi in (("priorytet_netto", 0, 100000), ("dojazd_max_komunikacja", 10, 240), ("dojazd_max_samochod", 10, 240), ("dojazd_wyjatek_netto", 0, 100000)):
                    with contextlib.suppress(ValueError, TypeError):
                        if request.form.get(key, "").strip():
                            ctx.set_setting(key, max(lo, min(hi, int(re.sub(r"\D", "", request.form[key]) or 0))))
            elif what == "podpis":
                up = request.files.get("podpis")
                for old in ("podpis.png", "podpis.jpg"):
                    (ctx.folder() / old).unlink(missing_ok=True)
                if up and up.filename and not request.form.get("usun"):
                    ext = ".png" if up.filename.lower().endswith(".png") else ".jpg"
                    data = up.read(5_000_000)
                    try:
                        from PIL import Image as _I
                        import io as _io
                        _I.open(_io.BytesIO(data)).verify()
                        (ctx.folder() / ("podpis" + ext)).write_bytes(data)
                    except Exception:
                        error = "To nie wygląda na zdjęcie (PNG albo JPG)."
                for key, lo, hi in (("prog_autopilota", 50, 100), ("prog_dopasowania", 0, 95), ("przypomnienie_po_dniach", 3, 30)):
                    with contextlib.suppress(ValueError):
                        ctx.set_setting(key, max(lo, min(hi, int(request.form.get(key, ctx.settings()[key])))))
            elif what == "zrodlo_dodaj":
                url = R.clean_url(request.form.get("url", ""))
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
            elif what == "klucze":
                ctx.set_setting("pisanie", "gemini" if request.form.get("pisanie_gemini") else "lokalnie")
                lim = request.form.get("gemini_limit_dzienny", "").strip()
                if lim.isdigit():
                    ctx.set_setting("gemini_limit_dzienny", str(max(10, min(2000, int(lim)))))
                ctx.set_setting("gemini_model", re.sub(r"[^a-z0-9.\-]", "", request.form.get("gemini_model", "").lower())[:60])
                for field, name in (("adzuna_id", "adzuna_id"), ("adzuna_key", "adzuna_key"), ("jooble", "jooble"), ("brave", "brave"), ("gemini", "gemini")):
                    val = request.form.get(field, "").strip()
                    if val:
                        R.set_secret(ctx, name, val)
                ctx.set_setting("cbop_partner", re.sub(r"[<>&\r\n]", "", request.form.get("cbop_partner", "")).strip()[:80])
                ctx.set_setting("alerty", "tak" if request.form.get("alerty") else "nie")
                frazy = request.form.get("frazy", "").strip()
                if frazy:
                    ctx.set_setting("frazy", frazy[:600])
                g.db.execute("UPDATE zrodla SET sprawdzono='' WHERE typ IN ('adzuna','jooble')")
                g.db.commit()
                R.meta_set(g.db, "ostatnie_szukanie", 0)
            elif what == "pauza":
                ctx.set_setting("wstrzymane", "nie" if ctx.settings().get("wstrzymane") else "tak")
                return redirect(request.form.get("powrot") or url_for("home"))
            elif what == "raport_teraz":
                flash("Raport wysłany na Twoją skrzynkę." if evening_report(ctx, send=app.config.get("SEND", P.send), force=True) else "Raport nie wyszedł — sprawdź podłączenie skrzynek.")
            if not error:
                if what in ("dane", "narzedzia", "kryteria", "aga", "sebastian", "wysylka", "praca", "klucze"):
                    flash("Zapisane.")
                return redirect(url_for("settings", czesc=what if what.startswith("zrodlo") else ""))
            part = what if what in ("dane", "narzedzia", "kryteria") else ("zrodla" if what.startswith("zrodlo") else part)
        me, seb = R.mailboxes(g.db)
        Z.seed(g.db, ctx)
        sources = g.db.execute("SELECT * FROM zrodla ORDER BY id").fetchall()
        firms = g.db.execute("SELECT COUNT(*) n, SUM(uzyta) u FROM firmy").fetchone()
        keys = {k: bool(R.secret(ctx, k)) for k in ("adzuna_id", "adzuna_key", "jooble", "brave", "gemini")}
        return render_template("ustawienia.html", prefs=PF.load(g.db), f=f, tab="ust", part=part, error=error, me=me, seb=seb, has_photo=bool(photo_path(ctx, f)), has_signature=bool(signature_path(ctx)), writer=D.writer_model(ctx), cbop_wynik=R.meta_get(g.db, "cbop_wynik"), gemini_status=GM.status(ctx),
                               sources=sources, firms=firms, keys=keys)

    try:                                                                     # 2.30: „Uczy się o Tobie” — tylko pamięć Agi
        import dodatki_host as DH

        def only_aga(people):
            info = DH.discover().get("pamiec")
            want = R.plain((DH.load(info)[1].settings().get("osoba_panelu_agi") if info else "") or "Aga")
            return [p for p in people if p.get("rola") != "wlasciciel"
                    and any(R.plain(x).startswith(want) for x in (p["imie"] or "").split())][:1]
        DH.register_web(app, "pamiec", prefix="/pamiec", people_filter=only_aga, back=("/centrum", "← Centrum dowodzenia"))
    except Exception as e:
        ctx.log.warning(f"Pamięć: zakładka niedostępna ({type(e).__name__}: {e})")
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
