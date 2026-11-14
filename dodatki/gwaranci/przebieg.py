"""Gwaranci — przebieg rezerwacji: maile z zaproszeniem, decyzje gwaranta, przypomnienia, powiadomienia dla właściciela."""
import contextlib, datetime as dt

from . import rdzen as R


def base_url(ctx, c):
    return (R.meta_get(c, "adres_publiczny") or ctx.settings().get("adres", "") or "").rstrip("/")


def notify_owner(ctx, text, purpose="info"):
    if not ctx.settings().get("whatsapp", True):
        return
    with contextlib.suppress(Exception):
        ctx.send_text(text[:1500], purpose=purpose)


def _when(b):
    s = R.parse(b["start"])
    m = s.hour * 60 + s.minute
    return f"{R.fdate(s)}, {R.hm(m)}–{R.hm(m + b['minuty'])}"


def _rows(c, b):
    ppl = R.people(c)
    return [("Spotkanie", f"{R.TYPES[b['typ']][0]} · {R.dur(b['minuty'])}"), ("Kiedy", _when(b)), ("Gdzie", R.place_label(b)),
            ("Adept", f"{ppl[b['adept']]['imie_nazwisko']} · {ppl[b['adept']]['stanowisko']}"),
            ("Gwarant", f"{ppl[b['gwarant']]['imie_nazwisko']}")] + ([("Od adepta", b["notatka"])] if b.get("notatka") else [])


def after_booking(ctx, c, b):
    """Nowa prośba: zaproszenie do kalendarza dla gwaranta (z przyciskami Akceptuję / Nie mogę) i potwierdzenie dla adepta."""
    ppl = R.people(c)
    g, a = ppl[b["gwarant"]], ppl[b["adept"]]
    url = base_url(ctx, c)
    errors = []
    if b.get("calcom_uid"):
        return _after_calcom_booking(ctx, c, b, g, a, url)
    err = R.send_or_queue(ctx, c, g["email"], f"Prośba o spotkanie gwaranckie: {a['imie_nazwisko']}, {_when(b)}",
                    f"Cześć {g['imie_nazwisko'].split()[0]}!\n\n{a['imie_nazwisko']} prosi Cię o spotkanie gwaranckie.\n\n"
                    + R.description(ctx, c, b) + f"\n\nAkceptuję: {url}/decyzja/{b['token']}/tak\nNie mogę: {url}/decyzja/{b['token']}/nie\n",
                    html=R.html_mail("Prośba o spotkanie gwaranckie",
                                     f"Cześć {g['imie_nazwisko'].split()[0]}! <b>{a['imie_nazwisko']}</b> prosi Cię o spotkanie gwaranckie. "
                                     "Termin pasuje do Twojej dostępności i jest wolny w Twoim kalendarzu.",
                                     _rows(c, b), [("Akceptuję", f"{url}/decyzja/{b['token']}/tak"), ("Nie mogę", f"{url}/decyzja/{b['token']}/nie")],
                                     "Możesz też odpowiedzieć przyciskami Tak / Nie w zaproszeniu Google Calendar. Prosimy o odpowiedź w ciągu 24 h."),
                    ics=R._event_ics(ctx, c, b), booking_id=b["id"])
    if err:
        errors.append(f"mail do gwaranta: {err}")
    if a.get("email"):
        with contextlib.suppress(Exception):
            R.send_or_queue(ctx, c, a["email"], f"Twoje spotkanie gwaranckie – {R.TYPES[b['typ']][0]}, {_when(b)}",
                        f"Cześć {a['imie_nazwisko'].split()[0]}!\n\nProśba poszła do: {g['imie_nazwisko']}. Gdy zaakceptuje, dostaniesz "
                        "zaproszenie do kalendarza.\n\n" + R.description(ctx, c, b),
                        html=R.html_mail("Prośba wysłana", f"Cześć {a['imie_nazwisko'].split()[0]}! Prośba poszła do: <b>{g['imie_nazwisko']}</b>. "
                                         "Gdy zaakceptuje (najpóźniej w ciągu 24 h), dostaniesz zaproszenie do kalendarza.", _rows(c, b),
                                         [("Moje spotkania", f"{url}/moje")],
                                         "Po spotkaniu wypełnij feedback po usłudze i wyślij gwarantowi kilka zdań: czego się nauczyłeś/nauczyłaś "
                                         "i za co jesteś wdzięczny/wdzięczna. Gwaranci robią to bez wynagrodzenia — Twoje słowa są dla nich "
                                         "najważniejszym podziękowaniem."))
    notify_owner(ctx, f"🗓️ Gwaranci: {a['imie_nazwisko']} → {g['imie_nazwisko']} · {R.TYPES[b['typ']][0]} · {_when(b)} (czeka na akceptację)"
                 + (f"\nℹ️ cal.com nie przyjął rezerwacji ({b['calcom_blad']}) — prośba poszła mailem z zaproszeniem." if b.get("calcom_blad") else "")
                 + (f"\n⚠️ {'; '.join(errors)}" if errors else ""), "rezerwacja")
    return errors


FEEDBACK = ("Po spotkaniu wypełnij feedback po usłudze i wyślij gwarantowi kilka zdań: czego się nauczyłeś/nauczyłaś "
            "i za co jesteś wdzięczny/wdzięczna. Gwaranci robią to bez wynagrodzenia — Twoje słowa są dla nich najważniejszym podziękowaniem.")


def _after_calcom_booking(ctx, c, b, g, a, url):
    """Gwarant z cal.com: prośbę i zaproszenia wysyła jego cal.com — ja dokładam tylko maila dla adepta i powiadomienie dla Ciebie."""
    if a.get("email"):
        with contextlib.suppress(Exception):
            R.send_mail(ctx, c, a["email"], f"Twoje spotkanie gwaranckie – {R.TYPES[b['typ']][0]}, {_when(b)}",
                        f"Cześć {a['imie_nazwisko'].split()[0]}!\n\nProśba poszła do: {g['imie_nazwisko']} (przez cal.com). "
                        "Gdy zaakceptuje, cal.com wyśle Ci potwierdzenie z wpisem do kalendarza.\n\n" + R.description(ctx, c, b) + "\n\n" + FEEDBACK,
                        html=R.html_mail("Prośba wysłana", f"Cześć {a['imie_nazwisko'].split()[0]}! Prośba poszła do: <b>{g['imie_nazwisko']}</b>. "
                                         "Gdy zaakceptuje, <b>cal.com</b> wyśle Ci potwierdzenie z wpisem do kalendarza.", _rows(c, b),
                                         [("Moje spotkania", f"{url}/moje")], FEEDBACK))
    notify_owner(ctx, f"🗓️ Gwaranci: {a['imie_nazwisko']} → {g['imie_nazwisko']} · {R.TYPES[b['typ']][0]} · {_when(b)} "
                 "(zapisane w cal.com, czeka na akceptację)", "rezerwacja")
    return []


def calcom_key(ctx):
    with contextlib.suppress(Exception):
        return ctx.secret("calcom_klucz") or ""
    return ""


def sync_calcom(ctx, c, when):
    """Statusy rezerwacji z cal.com: akceptacja, odrzucenie, odwołanie w cal.com trafiają do Sebastiana."""
    key = calcom_key(ctx)
    ppl = R.people(c)
    rows = c.execute("SELECT * FROM rezerwacje WHERE calcom_uid!='' AND status IN ('czeka','potwierdzone')").fetchall()
    for r in rows:
        b = dict(r)
        if R.parse(b["start"]) < when - dt.timedelta(hours=12):
            continue
        st = R.calcom_booking_status(b["calcom_uid"], key)
        g, a = ppl.get(b["gwarant"], {}), ppl.get(b["adept"], {})
        if st == "accepted" and b["status"] == "czeka":
            R.set_status(c, b["id"], "potwierdzone")
            notify_owner(ctx, f"✅ Gwaranci: {g.get('imie_nazwisko', '?')} potwierdził(a) w cal.com spotkanie z {a.get('imie_nazwisko', '?')} · {_when(b)}", "decyzja")
        elif st == "rejected" and b["status"] == "czeka":
            b = R.set_status(c, b["id"], "odrzucone")
            if a.get("email"):
                with contextlib.suppress(Exception):
                    R.send_mail(ctx, c, a["email"], "Wybierz proszę inny termin spotkania gwaranckiego",
                                f"{g.get('imie_nazwisko', 'Gwarant')} nie może w tym terminie. Wybierz inny: {base_url(ctx, c)}/rezerwuj",
                                html=R.html_mail("Wybierz inny termin", f"<b>{g.get('imie_nazwisko', 'Gwarant')}</b> nie może w tym terminie. "
                                                 "Wybierz proszę inny — system znów dobierze gwaranta.", _rows(c, b),
                                                 [("Wybierz termin", f"{base_url(ctx, c)}/rezerwuj?typ={b['typ']}")]))
            notify_owner(ctx, f"↩️ Gwaranci: {g.get('imie_nazwisko', '?')} odrzucił(a) w cal.com ({a.get('imie_nazwisko', '?')}, {_when(b)}). "
                         "Adept dostał prośbę o inny termin.", "decyzja")
        elif st == "cancelled":
            R.set_status(c, b["id"], "anulowane")
            notify_owner(ctx, f"✖️ Gwaranci: spotkanie {a.get('imie_nazwisko', '?')} z {g.get('imie_nazwisko', '?')} ({_when(b)}) odwołane w cal.com.", "anulowanie")


def decide(ctx, c, b, yes, source="link"):
    """Decyzja gwaranta. Zwraca zaktualizowaną rezerwację (albo tę samą, gdy decyzja już zapadła)."""
    if b["status"] != "czeka":
        return b
    ppl = R.people(c)
    g, a = ppl[b["gwarant"]], ppl[b["adept"]]
    url = base_url(ctx, c)
    if yes:
        b = R.set_status(c, b["id"], "potwierdzone")
        if a.get("email"):
            with contextlib.suppress(Exception):
                R.send_mail(ctx, c, a["email"], f"Potwierdzone: spotkanie gwaranckie z {g['imie_nazwisko']}, {_when(b)}",
                            f"{g['imie_nazwisko']} potwierdził(a) spotkanie.\n\n" + R.description(ctx, c, b),
                            html=R.html_mail("Spotkanie potwierdzone", f"<b>{g['imie_nazwisko']}</b> potwierdził(a) Wasze spotkanie. "
                                             "Wpis jest w załączniku — kliknij „Tak”, żeby dodać go do kalendarza.", _rows(c, b),
                                             [("Moje spotkania", f"{url}/moje")],
                                             "Po spotkaniu: feedback po usłudze i kilka zdań podziękowania dla gwaranta."),
                            ics=R._event_ics(ctx, c, b, with_adept=True, accepted=True))
        if source == "link" and g.get("email"):                 # przy kliknięciu linku wpis trafia też do kalendarza gwaranta
            with contextlib.suppress(Exception):
                R.send_mail(ctx, c, g["email"], f"Potwierdzone: {a['imie_nazwisko']}, {_when(b)}",
                            "Dziękujemy! Wpis jest w załączniku.\n\n" + R.description(ctx, c, b),
                            html=R.html_mail("Dziękujemy!", "Spotkanie jest potwierdzone, adept dostał wiadomość. Wpis do kalendarza w załączniku.",
                                             _rows(c, b)),
                            ics=R._event_ics(ctx, c, b, with_adept=True, accepted=True))
        notify_owner(ctx, f"✅ Gwaranci: {g['imie_nazwisko']} potwierdził(a) spotkanie z {a['imie_nazwisko']} · {_when(b)}", "decyzja")
    else:
        b = R.set_status(c, b["id"], "odrzucone")
        with contextlib.suppress(Exception):
            R.send_mail(ctx, c, g["email"], f"Odwołane: {a['imie_nazwisko']}, {_when(b)}", "Zapisaliśmy, że nie możesz. Usuwamy wpis.",
                        ics=R._event_ics(ctx, c, b, method="CANCEL"), method="CANCEL")
        if a.get("email"):
            with contextlib.suppress(Exception):
                R.send_mail(ctx, c, a["email"], "Wybierz proszę inny termin spotkania gwaranckiego",
                            f"{g['imie_nazwisko']} nie może w tym terminie. Wybierz inny: {url}/rezerwuj",
                            html=R.html_mail("Wybierz inny termin", f"<b>{g['imie_nazwisko']}</b> nie może w tym terminie. "
                                             "Wybierz proszę inny — system znów dobierze gwaranta.", _rows(c, b),
                                             [("Wybierz termin", f"{url}/rezerwuj?typ={b['typ']}")]))
        notify_owner(ctx, f"↩️ Gwaranci: {g['imie_nazwisko']} nie może ({a['imie_nazwisko']}, {_when(b)}). Adept dostał prośbę o inny termin.", "decyzja")
    return b


def cancel_by_adept(ctx, c, b):
    if b["status"] not in R.ACTIVE:
        return b
    ppl = R.people(c)
    g, a = ppl[b["gwarant"]], ppl[b["adept"]]
    if b.get("calcom_uid"):                                    # odwołanie w cal.com gwaranta — cal.com zawiadamia obie strony
        try:
            R.calcom_cancel(b["calcom_uid"], f"{a['imie_nazwisko']} odwołał(a) spotkanie w panelu gwarantów.", calcom_key(ctx))
            note = ""
        except Exception as e:
            note = f"\n⚠️ Nie udało się odwołać w cal.com ({e}) — odwołaj ręcznie w cal.com {g['imie_nazwisko']}."
        R.set_status(c, b["id"], "anulowane")
        notify_owner(ctx, f"✖️ Gwaranci: {a['imie_nazwisko']} odwołał(a) spotkanie z {g['imie_nazwisko']} · {_when(b)}" + note, "anulowanie")
        return R.booking(c, b["id"])
    b = R.set_status(c, b["id"], "anulowane")
    with contextlib.suppress(Exception):
        R.send_mail(ctx, c, g["email"], f"Odwołane: {a['imie_nazwisko']}, {_when(b)}",
                    f"{a['imie_nazwisko']} odwołał(a) spotkanie. Wpis znika z kalendarza.",
                    ics=R._event_ics(ctx, c, b, method="CANCEL"), method="CANCEL")
    notify_owner(ctx, f"✖️ Gwaranci: {a['imie_nazwisko']} odwołał(a) spotkanie z {g['imie_nazwisko']} · {_when(b)}", "anulowanie")
    return b


def periodic(ctx, c, when=None, refresh=True, mail=True):
    """Praca w tle: świeża zajętość gwarantów, odpowiedzi Tak/Nie z Gmaila, przypomnienia, wygasanie."""
    when = when or R.now(ctx)
    st = ctx.settings()
    if refresh:
        every = int(st.get("odswiezanie_min", 5)) * 60
        for pid in R.ready_guarantors(c):
            g = R.guarantor(c, pid)
            last = R.parse(g["odczyt"]) if g["odczyt"] else None
            if not last or (when - last).total_seconds() >= every:
                with contextlib.suppress(Exception):
                    R.refresh_busy(c, pid, when=when)
        last = R.meta_get(c, "calcom_sync")
        if not last or (when - R.parse(last)).total_seconds() >= every:
            with contextlib.suppress(Exception):
                sync_calcom(ctx, c, when)
            R.meta_set(c, "calcom_sync", R.iso(when))
    with contextlib.suppress(Exception):                       # maile, których Gmail wcześniej nie przyjął
        for r, err in R.flush_queue(ctx, c, when):
            if err:
                notify_owner(ctx, f"⚠️ Gwaranci: mail do {r['do_kogo']} („{r['temat']}”) nie wyszedł mimo kilku prób: {err}", "poczta")
            elif r["proby"] >= 1 and r["rezerwacja"]:
                notify_owner(ctx, f"✉️ Gwaranci: mail do {r['do_kogo']} („{r['temat']}”) wyszedł za {r['proby'] + 1}. razem.", "poczta")
    if mail:
        with contextlib.suppress(Exception):
            for b, ans in R.check_replies(ctx, c):
                decide(ctx, c, b, ans == "tak", source="gmail")
    ppl = R.people(c)
    for r in c.execute("SELECT * FROM rezerwacje WHERE status='czeka' AND calcom_uid=''").fetchall():
        b = dict(r)
        start, made = R.parse(b["start"]), R.parse(b["utworzono"])
        if start - when < dt.timedelta(hours=2):
            b = R.set_status(c, b["id"], "wygaslo")
            a = ppl.get(b["adept"], {})
            if a.get("email"):
                with contextlib.suppress(Exception):
                    R.send_mail(ctx, c, a["email"], "Spotkanie gwaranckie bez potwierdzenia",
                                f"Gwarant nie potwierdził spotkania ({_when(b)}). Wybierz proszę inny termin: {base_url(ctx, c)}/rezerwuj")
            notify_owner(ctx, f"⌛ Gwaranci: {ppl.get(b['gwarant'], {}).get('imie_nazwisko', '?')} nie odpowiedział(a) — spotkanie {_when(b)} wygasło.", "wygaslo")
        elif not b["przypomniano"] and when - made >= dt.timedelta(hours=int(st.get("przypomnienie_h", 20))):
            c.execute("UPDATE rezerwacje SET przypomniano=1 WHERE id=?", (b["id"],))
            c.commit()
            g = ppl.get(b["gwarant"], {})
            url = base_url(ctx, c)
            with contextlib.suppress(Exception):
                R.send_mail(ctx, c, g.get("email", ""), f"Przypomnienie: prośba o spotkanie gwaranckie, {_when(b)}",
                            f"Czeka na Twoją decyzję.\nAkceptuję: {url}/decyzja/{b['token']}/tak\nNie mogę: {url}/decyzja/{b['token']}/nie",
                            html=R.html_mail("Czeka na Twoją decyzję", "Adept czeka na odpowiedź — wystarczy jedno kliknięcie.", _rows(c, b),
                                             [("Akceptuję", f"{url}/decyzja/{b['token']}/tak"), ("Nie mogę", f"{url}/decyzja/{b['token']}/nie")]))
            notify_owner(ctx, f"⏰ Gwaranci: {g.get('imie_nazwisko', '?')} od {st.get('przypomnienie_h', 20)} h nie odpowiada na prośbę "
                         f"{ppl.get(b['adept'], {}).get('imie_nazwisko', '?')} ({_when(b)}). Wysłałem przypomnienie.", "przypomnienie")
