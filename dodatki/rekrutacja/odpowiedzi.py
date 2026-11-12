"""Rekrutacja — odpowiedzi pracodawców (część B).

Sebastian czyta skrzynkę Agi wyłącznie w trybie podglądu (nic nie oznacza jako przeczytane), dopasowuje wiadomości do
wysłanych aplikacji i rozpoznaje ich rodzaj. Wiadomości niezwiązane z rekrutacją są pomijane i nie są zapisywane.

  zaproszenie / oferta   → od razu WhatsApp i mail do Agi, szkic odpowiedzi do zatwierdzenia
  pytanie / prośba       → szkic odpowiedzi z bazy faktów albo pytanie do Agi w panelu
  zadanie / test         → od razu WhatsApp z terminem
  odmowa                 → krótkie, uprzejme podziękowanie (automatycznie, jeśli włączone)
  potwierdzenie wpływu   → tylko odnotowane
"""
import contextlib, datetime as dt, json, re

from . import dokumenty as D, poczta as P, rdzen as R

KINDS = {"zaproszenie": "zaproszenie na rozmowę", "oferta": "propozycja pracy", "pytanie": "pytanie lub prośba",
         "zadanie": "zadanie rekrutacyjne", "do_potwierdzenia": "potwierdź aplikację", "odmowa": "odmowa",
         "potwierdzenie": "potwierdzenie otrzymania", "reklama": "reklama portalu", "inne": "inna wiadomość"}
QUIET = ("potwierdzenie", "reklama", "inne")                             # bez powiadomień, bez maila, nie w raporcie
AUTO_SENDER = r"(no.?reply|do.?not.?reply|nie.?odpowiadaj|system@|mailer|notification|powiadomien|newsletter|erecruiter|recruitee|" \
              r"smartrecruiters|teamtailor|workday|greenhouse|lever\.co|pracuj\.pl|olx|linkedin|indeed|jooble|adzuna|rocketjobs|justjoin|nofluff)"
INVITE_RE = (r"(zaprasza\w* (pania |cie |ciebie )?na (rozmow|spotkan|wideorozmow|wywiad)|zapraszamy (do|na) (biura|siedziby|rozmow|spotkan)|"
             r"termin rozmowy|umowmy sie|proponuj\w* (termin|spotkanie|rozmow)|rozmowa (odbedzie|bedzie) sie|"
             r"(rozmow|spotkan)\w* (kwalifikacyjn|rekrutacyjn)\w* (w dniu|dnia|odbedzie|w terminie|o godz)|kiedy (pani )?(moze|mozesz) (porozmawiac|przyjsc))")
CONFIRM_ACTION_RE = (r"(czy to (twoja|pani) aplikacja|potwierdz\w* (swoja |twoja |pani )?(aplikacj|zgloszeni|kandydatur|adres|wlasnosc|ze to)|"
                     r"zdecyduj,? co (mamy|mam) z nia zrobic|aktywuj (konto|profil)|zweryfikuj (adres|e-?mail|konto)|kliknij,? aby potwierdzic)")
RECEIVED_RE = (r"(automatyczn|auto.?repl|nie odpowiadaj|wygenerowana automatycznie|potwierdzamy otrzymanie|otrzymalismy (pani|twoja|twoje|zgloszen|aplikac|cv)|"
               r"dziekujemy za (przeslanie|zlozenie|aplikacj|twoje zgloszen|pani zgloszen|zainteresowanie|cv)|zgloszenie (wlasnie )?(trafilo|dotarlo|zostalo przyjete)|"
               r"aplikacja (zostala )?(przyjeta|wyslana|dotarla)|odezwiemy sie|skontaktuj\w* sie (wylacznie |tylko |jedynie )?z (wybranymi|wybrany\w*|osobami)|"
               r"(wybranymi|wybrany\w*) (kandydat\w*|osob\w*)|rozpoczelismy proces|przyjelismy|wypelnienie kwestionariusza|dziekujemy za (wypelnienie|udzial))")
PROMO_RE = (r"(sprawdz (kompetencje|swoje szanse|jak wypadasz)|innych kandydatow|podobne oferty|polecane oferty|rekomendowane oferty|oferty dla ciebie|"
            r"nowe oferty pracy|zobacz (oferty|wiecej ofert)|wypisz sie|zrezygnuj z subskrypcji|newsletter|premium|kup |pakiet|promocj|zarabiaj)")
IMPORTANT = ("zaproszenie", "oferta", "pytanie", "zadanie")
RECRUIT_WORDS = ("rekrutac", "aplikac", "kandydat", "cv", "stanowisk", "rozmow", "spotkani", "zgloszeni", "oferta pracy", "ogloszeni",
                 "dziekujemy za", "dziekuje za", "interview", "application", "candidate")


# ================================================================ dopasowanie do aplikacji

def _domain(addr):
    d = (addr or "").rsplit("@", 1)[-1].lower()
    return "" if d in ("gmail.com", "wp.pl", "o2.pl", "onet.pl", "interia.pl", "op.pl", "yahoo.com", "outlook.com", "hotmail.com",
                       "googlemail.com", "icloud.com", "poczta.fm", "tlen.pl", "gazeta.pl", "interia.eu", "vp.pl") else d


def _after(m_date, sent):
    """Czy wiadomość przyszła po wysłaniu aplikacji (porównanie czasu, nie tekstu)."""
    with contextlib.suppress(Exception):
        a, b = dt.datetime.fromisoformat(m_date), dt.datetime.fromisoformat(sent)
        if a.tzinfo is None or b.tzinfo is None:
            a, b = a.replace(tzinfo=None), b.replace(tzinfo=None)
        return a >= b - dt.timedelta(minutes=5)
    return False


def match(c, m):
    """Id aplikacji, której dotyczy wiadomość, albo 0. Bez nagłówków wątku: tylko wiadomość rekrutacyjna, która przyszła
    po wysłaniu aplikacji, od adresu albo z domeny pracodawcy (albo z nazwą firmy)."""
    refs = f"{m.get('in_reply_to', '')} {m.get('references', '')}"
    if refs.strip():
        for r in c.execute("SELECT id, message_id FROM aplikacje WHERE message_id<>''"):
            if r["message_id"] and r["message_id"] in refs:
                return r["id"]
    if not looks_recruiting(m):
        return 0
    sent = [r for r in c.execute(f"SELECT id, email, firma, stanowisko, wyslano FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))}) "
                                 "AND wyslano<>'' ORDER BY wyslano DESC", R.SENT).fetchall() if _after(m.get("data", ""), r["wyslano"])]
    for r in sent:
        if (m.get("od") or "").lower() == (r["email"] or "").lower():
            return r["id"]
    dom = _domain(m.get("od", ""))
    if dom:
        for r in sent:
            if _domain(r["email"]) == dom:
                return r["id"]
    hay = R.norm(f"{m.get('temat', '')} {m.get('od_nazwa', '')} {m.get('tresc', '')[:3000]}")
    for r in sent:
        firm = R.norm(r["firma"])
        if firm and len(firm) >= 5 and re.search(rf"\b{re.escape(firm)}\b", hay):
            return r["id"]
    return 0


def looks_recruiting(m):
    low = R.plain(f"{m.get('temat', '')} {m.get('tresc', '')[:2000]}")
    return sum(w in low for w in RECRUIT_WORDS) >= 2


# ================================================================ rozpoznanie rodzaju

REJECT_RE = (r"(nie zakwalifikowal|zdecydowalismy sie na (innego|inna|kandydat)|wybralismy (innego|inna|innych|kandydat)|nie bedziemy kontynuowac|"
             r"(pani|twoja) kandydatura (nie|zostala odrzucona)|nie przeszla|zakonczyl\w* proces rekrutac\w*,? (bez|i nie)|"
             r"nie mozemy zaproponowac|nie zostala (pani|pan) wybran|nie spelnia (pani )?wymagan|postanowilismy kontynuowac z innym)")


def automated(m):
    return bool(m.get("auto") or re.search(AUTO_SENDER, R.plain(f"{m.get('od', '')} {m.get('od_nazwa', '')}")))


def classify_rules(m):
    low = R.plain(f"{m.get('temat', '')}\n{m.get('tresc', '')}")
    if re.search(CONFIRM_ACTION_RE, low):
        return "do_potwierdzenia"
    rejection = re.search(REJECT_RE, low)
    if rejection:
        return "odmowa"
    if re.search(INVITE_RE, low):
        return "zaproszenie"
    if automated(m) and re.search(PROMO_RE, low):
        return "reklama"
    if re.search(RECEIVED_RE, low):
        return "potwierdzenie"
    if m.get("auto"):
        return "potwierdzenie"
    if re.search(r"(zadanie rekrutacyjne|zadanie do wykonania|test kompetenc|case study|prosimy o wykonanie)", low):
        return "zadanie"
    if re.search(r"(propozycj\w* (zatrudnienia|pracy|wspolpracy)|oferte zatrudnienia|chcielibysmy zatrudnic)", low):
        return "oferta"
    if "?" in m.get("tresc", "") or re.search(r"(prosze o (przeslanie|informacje|podanie)|prosimy o (przeslanie|informacje|podanie)|oczekiwania finansowe|dostepnosc)", low):
        return "pytanie"
    return "inne"


def classify(ctx, m, app):
    rule = classify_rules(m)
    firm = app.get("firma") or m.get("od_nazwa") or "Firma"
    fixed = {"do_potwierdzenia": f"{firm}: system rekrutacyjny prosi, żebyś potwierdziła, że to Twoja aplikacja. Kliknij przycisk w wiadomości.",
             "potwierdzenie": f"{firm} potwierdza, że Twoja aplikacja dotarła.",
             "reklama": "Reklama portalu z ogłoszeniami — nic nie trzeba robić."}
    if rule in fixed and (automated(m) or rule != "potwierdzenie"):
        return {"rodzaj": rule, "streszczenie": fixed[rule], "termin": "", "pytania": [], "pewne": True}
    prompt = f"""Przeczytaj wiadomość do kandydatki (Agi), która aplikowała na stanowisko „{app.get('stanowisko') or 'bez ogłoszenia'}” w firmie „{app.get('firma', '')}”.

RODZAJE (wybierz jeden, uważnie):
- "zaproszenie": pracodawca ZAPRASZA na rozmowę lub spotkanie — proponuje termin albo prosi o kontakt, żeby go umówić.
- "potwierdzenie": automatyczne lub zwykłe potwierdzenie, że aplikacja dotarła, „odezwiemy się”, „rozpoczęliśmy rekrutację”. To NIE jest zaproszenie.
- "do_potwierdzenia": system prosi, żeby kandydatka kliknęła i potwierdziła aplikację albo adres e-mail.
- "reklama": reklama lub newsletter portalu (np. „sprawdź kompetencje innych kandydatów”, „podobne oferty”).
- "pytanie": pracodawca o coś pyta albo prosi o informacje lub dokumenty.
- "zadanie": zadanie lub test do wykonania. "oferta": propozycja zatrudnienia. "odmowa": odrzucenie kandydatury. "inne": nic z powyższych.

WIADOMOŚĆ
Od: {m.get('od_nazwa', '')} <{m.get('od', '')}>
Temat: {m.get('temat', '')}
{m.get('tresc', '')[:5000]}

Zwróć JSON:
{{"rodzaj": jedno z "zaproszenie", "oferta", "pytanie", "zadanie", "odmowa", "potwierdzenie", "inne",
  "streszczenie": "jedno krótkie zdanie po polsku do Agi, w drugiej osobie (np. „Firma X zaprasza Cię na rozmowę w piątek.”, „Firma X pyta o Twoją dostępność.”)",
  "termin": "termin rozmowy albo odpowiedzi, dokładnie jak w wiadomości, albo pusty tekst",
  "pytania": ["konkretne pytania pracodawcy do kandydatki, jeśli są"]}}"""
    out = None
    with contextlib.suppress(Exception):
        out = ctx.ask(prompt, as_json=True, max_tokens=500, temperature=0.0)
    if not isinstance(out, dict) or out.get("rodzaj") not in KINDS:
        return {"rodzaj": rule, "streszczenie": (m.get("tresc") or "")[:240], "termin": "", "pytania": [], "pewne": False}
    kind = out["rodzaj"]
    if rule in ("odmowa", "zaproszenie", "oferta") and kind in ("inne", "potwierdzenie", "reklama"):
        kind = rule                                                    # reguła łapie ważne sprawy, których model nie docenił
    if kind in ("zaproszenie", "oferta", "zadanie") and rule in ("potwierdzenie", "do_potwierdzenia", "reklama"):
        kind = rule                                                    # model nie zrobi zaproszenia z potwierdzenia czy reklamy
    low_all = R.plain(f"{m.get('temat', '')}\n{m.get('tresc', '')}")
    if kind == "odmowa" and not re.search(REJECT_RE, low_all):
        kind = "potwierdzenie" if rule == "potwierdzenie" or re.search(RECEIVED_RE, low_all) else "inne"
    if kind == "zaproszenie" and rule != "zaproszenie" and automated(m):
        kind = "potwierdzenie" if re.search(RECEIVED_RE, R.plain(m.get("tresc", ""))) else "inne"   # system bez słowa o rozmowie
    sure = out["rodzaj"] == kind and rule != "zaproszenie" and (kind != "odmowa" or bool(re.search(REJECT_RE, low_all)))
    if kind == "odmowa" and rule == "zaproszenie":
        kind = "zaproszenie"                                           # przy sprzeczności wygrywa bezpieczniejsze: Aga zobaczy wiadomość
    pyt = [str(x).strip()[:300] for x in (out.get("pytania") or []) if str(x).strip()][:6]
    return {"rodzaj": kind, "streszczenie": str(out.get("streszczenie") or "")[:500], "termin": str(out.get("termin") or "")[:120], "pytania": pyt,
            "pewne": sure}


# ================================================================ szkice odpowiedzi

def draft_reply(ctx, f, app, m, info, extra=""):
    """Szkic odpowiedzi wyłącznie z faktów (i odpowiedzi Agi). (tekst, [pytania bez odpowiedzi])."""
    w = f["warunki"]
    known = (f"Oczekiwania finansowe: od {w.get('min_netto')} zł netto miesięcznie." if w.get("min_netto") else "") + \
            (f" Dostępność: {w.get('dostepnosc')}." if w.get("dostepnosc") else "")
    prompt = f"""Napisz w imieniu kandydatki krótką odpowiedź na wiadomość pracodawcy. Po polsku, w formach żeńskich, uprzejmie,
naturalnie i konkretnie, bez frazesów i bez myślników. Zaczynasz od „Dzień dobry,”. BEZ podpisu.

WOLNO podać wyłącznie informacje z FAKTÓW. Jeśli pracodawca pyta o coś, czego nie ma w FAKTACH (np. konkretny termin,
dokument, dane), NIE zmyślaj: wpisz to pytanie do listy "brakuje".
Przy zaproszeniu: podziękuj i potwierdź chęć udziału; jeśli zaproponowano termin, napisz, że pasuje, tylko gdy FAKTY to potwierdzają —
w przeciwnym razie dodaj do "brakuje": „Czy proponowany termin Ci pasuje?”.

FAKTY:
{R.facts_brief(f, ids=False)}
{known}
{extra}

STANOWISKO: {app.get('stanowisko') or 'aplikacja bez ogłoszenia'} — {app.get('firma', '')}
WIADOMOŚĆ PRACODAWCY:
{m.get('tresc', '')[:4000]}

Zwróć JSON {{"odpowiedz": "...", "brakuje": ["pytania do kandydatki, bez których nie da się odpowiedzieć"]}}"""
    out = None
    with contextlib.suppress(Exception):
        out = ctx.ask(prompt, as_json=True, max_tokens=700, temperature=0.3)
    if not isinstance(out, dict) or len(str(out.get("odpowiedz", "")).split()) < 8:
        base = {"zaproszenie": "dziękuję za zaproszenie. Chętnie wezmę udział w rozmowie.",
                "oferta": "dziękuję za propozycję. Bardzo się cieszę i chętnie porozmawiam o szczegółach.",
                "zadanie": "dziękuję za przesłanie zadania. Potwierdzam, że je otrzymałam.",
                "pytanie": "dziękuję za wiadomość."}.get(info["rodzaj"], "dziękuję za wiadomość.")
        return f"Dzień dobry,\n\n{base}\n\n{D.signature(f)}", (info.get("pytania") or []) if info["rodzaj"] == "pytanie" else []
    missing = [str(x).strip()[:300] for x in (out.get("brakuje") or []) if str(x).strip()][:5]
    return D.tidy(out["odpowiedz"], f), missing


def thanks_text(f, app):
    role = f" na stanowisko {app['stanowisko']}" if app.get("stanowisko") else ""
    return (f"Dzień dobry,\n\ndziękuję za informację i za poświęcony czas. Szkoda, że tym razem się nie udało, ale cieszę się, że mogłam "
            f"wziąć udział w rekrutacji{role}. Jeśli w przyszłości pojawi się rola, w której mogłabym się przydać, chętnie się zgłoszę."
            f"\n\nŻyczę dobrego dnia.\n\n{D.signature(f)}")


def reminder_text(f, app):
    role = f"na stanowisko {app['stanowisko']}" if app.get("stanowisko") else "z pytaniem o możliwość współpracy"
    return (f"Dzień dobry,\n\nkilka dni temu przesłałam swoją aplikację {role}. Chciałabym uprzejmie zapytać, czy jest ona jeszcze "
            f"rozpatrywana. Nadal jestem zainteresowana i chętnie odpowiem na dodatkowe pytania.\n\n{D.signature(f)}")


def re_subject(subject):
    return subject if re.match(r"^\s*(re|odp|odp\.)\s*:", subject or "", re.I) else f"Re: {subject or ''}".strip()


# ================================================================ powiadomienia (WhatsApp przez kolejkę Sebastiana)

def aga_phone(ctx, f):
    st = ctx.settings()
    phone = re.sub(r"\D", "", str(st.get("whatsapp_numer", "") or f["osoba"].get("telefon", "")))
    if len(phone) == 9:
        phone = "48" + phone
    with contextlib.suppress(Exception):
        W = ctx.W
        if phone and any(u["phone"] == phone for u in W.all_users()):
            return phone
    return ""


def whatsapp(ctx, f, text, dedupe):
    """Wiadomość do Agi na WhatsAppie (tylko jeśli jej numer jest na liście dozwolonych). True, gdy trafiła do kolejki."""
    if not ctx.settings().get("whatsapp", True):
        return False
    phone = aga_phone(ctx, f)
    if not phone:
        return False
    with contextlib.suppress(Exception):
        W = ctx.W
        with contextlib.closing(W.db()) as con:
            when = W.quiet_end() if W.in_quiet() else None
            W.enqueue(con, "text", text[:3000], purpose="rekrutacja", not_before=when, dedupe=dedupe, to=phone)
            return True
    return False


def notify_mail(ctx, subject, body, send):
    with R.db(ctx) as c:
        me, seb = R.mailboxes(c)
    sender, key = (seb, "sebastian") if seb and R.secret(ctx, "sebastian") else (me, "aga")
    if me and R.secret(ctx, key):
        with contextlib.suppress(Exception):
            send(sender, R.secret(ctx, key), me, subject, body, name="Sebastian")
            return True
    return False


# ================================================================ przegląd skrzynki

def check_inbox(ctx, send=None, fetch=None):
    send, fetch = send or P.send, fetch or P.fetch_new
    with R.db(ctx) as c:
        me, _ = R.mailboxes(c)
        after = int(R.meta_get(c, "imap_uid", "0") or 0)
        any_sent = c.execute(f"SELECT COUNT(*) FROM aplikacje WHERE status IN ({','.join('?' * len(R.SENT))})", R.SENT).fetchone()[0]
    pwd = R.secret(ctx, "aga")
    if not me or not pwd or not any_sent:
        return 0
    with R.db(ctx) as c:
        first = c.execute("SELECT MIN(wyslano) FROM aplikacje WHERE wyslano<>''").fetchone()[0] or ""
        _, seb = R.mailboxes(c)
    days = 21
    with contextlib.suppress(Exception):
        days = max(1, min(21, (ctx.now() - dt.datetime.fromisoformat(first)).days + 2))   # nie czytam poczty sprzed pierwszej wysyłki
    msgs = fetch(me, pwd, after_uid=after, since_days=days, limit=60)
    f = R.load_facts(ctx)
    handled = 0
    own = {me.lower(), (seb or "").lower()} - {""}
    for m in msgs:
        def done():
            with R.db(ctx) as c2:
                R.meta_set(c2, "imap_uid", max(int(R.meta_get(c2, "imap_uid", "0") or 0), int(m["uid"])))
        with R.db(ctx) as c:
            skip = (m.get("nasza") or (m["od"] or "").lower() in own or
                    (m["message_id"] and c.execute("SELECT 1 FROM wiadomosci WHERE message_id=?", (m["message_id"],)).fetchone()))
            aid = 0 if skip else match(c, m)
            if skip or (not aid and not looks_recruiting(m)) or (first and m.get("data") and not _after(m["data"], first)):
                done()
                continue                                            # własna wiadomość, powtórka albo zwykła poczta Agi — nie zapisuję
            app = dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone()) if aid else {"firma": m["od_nazwa"] or m["od"], "stanowisko": ""}
        info = classify(ctx, m, app)
        kind = info["rodzaj"]
        draft, missing = ("", [])
        if kind in ("zaproszenie", "oferta", "pytanie", "zadanie"):
            draft, missing = draft_reply(ctx, f, app, m, info)
        with R.db(ctx) as c:
            act = kind in IMPORTANT or kind == "do_potwierdzenia"
            cur = c.execute("INSERT INTO wiadomosci(uid,message_id,od,od_nazwa,temat,data,tresc,aplikacja_id,rodzaj,wazne,streszczenie,termin,szkic,status,utworzono,references_,linki) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (m["uid"], m["message_id"], m["od"], m["od_nazwa"], m["temat"], m["data"], m["tresc"], 0 if kind == "reklama" else aid, kind, int(act),
                             info["streszczenie"], info["termin"], draft, "nowa" if act else "zalatwiona", R.stamp(ctx),
                             f"{m['references']} {m['message_id']}".strip(), json.dumps(m.get("linki") or [], ensure_ascii=False)))
            wid = cur.lastrowid
            for q in missing:
                c.execute("INSERT INTO pytania(aplikacja_id,wiadomosc_id,pytanie,utworzono) VALUES(?,?,?,?)", (aid, wid, q, R.stamp(ctx)))
            if aid and kind != "reklama":
                new_status = {"zaproszenie": "zaproszenie", "oferta": "oferta", "pytanie": "pytanie", "zadanie": "zaproszenie", "odmowa": "odmowa"}.get(kind)
                cur_status = c.execute("SELECT status FROM aplikacje WHERE id=?", (aid,)).fetchone()["status"]
                rank = ["wyslana", "wyslana_recznie", "pytanie", "odmowa", "zaproszenie", "rozmowa", "oferta"]
                if new_status and (cur_status not in rank or rank.index(new_status) >= rank.index(cur_status) or cur_status == "pytanie"):
                    R.set_status(c, ctx, aid, new_status, odpowiedz_kiedy=R.stamp(ctx))
                else:
                    c.execute("UPDATE aplikacje SET odpowiedz_kiedy=? WHERE id=?", (R.stamp(ctx), aid))
                R.note(c, ctx, aid, f"odpowiedź: {KINDS[kind]}")
            c.commit()
        done()
        handled += 1
        firm = app.get("firma") or m["od"]
        url = ""
        with contextlib.suppress(Exception), R.db(ctx) as c:
            url = R.meta_get(c, "adres_panelu")
        if kind in ("zaproszenie", "oferta", "zadanie"):
            label = {"zaproszenie": "📅 Zaproszenie na rozmowę", "oferta": "🎉 Propozycja pracy", "zadanie": "📝 Zadanie rekrutacyjne"}[kind]
            text = (f"*{label}*\n{firm}{' — ' + app['stanowisko'] if app.get('stanowisko') else ''}\n\n{info['streszczenie']}"
                    + (f"\n\nTermin: {info['termin']}" if info["termin"] else "") + (f"\n\nSzkic odpowiedzi czeka w panelu: {url}" if url else ""))
            whatsapp(ctx, f, text, dedupe=f"rek:{wid}")
            notify_mail(ctx, f"{label.split(' ', 1)[1]}: {firm}", text.replace("*", ""), send)
        elif kind == "pytanie":
            whatsapp(ctx, f, f"*❓ {firm} pyta*\n{info['streszczenie']}" + ("\n\nPotrzebuję Twojej odpowiedzi w panelu." if missing else "\n\nSzkic odpowiedzi czeka w panelu."),
                     dedupe=f"rek:{wid}")
        elif kind == "odmowa" and aid and ctx.settings().get("podziekowania", True):
            if info.get("pewne") and not re.search(r"(no.?reply|do.?not.?reply|nie.?odpowiadaj|mailer-daemon|postmaster|notification|powiadomien)", m["od"] or ""):
                with R.db(ctx) as c:                                # wyślę w oknie wysyłki (godziny, pauza)
                    c.execute("UPDATE aplikacje SET podziekowanie='czeka' WHERE id=? AND podziekowanie=''", (aid,))
                    c.execute("UPDATE wiadomosci SET szkic=? WHERE id=?", (thanks_text(f, app), wid))
                    c.commit()
            else:
                with R.db(ctx) as c:                                # niepewna odmowa: Aga sama zdecyduje
                    c.execute("UPDATE wiadomosci SET wazne=1, status='nowa', szkic=? WHERE id=?", (thanks_text(f, app), wid))
                    c.commit()
    return handled


def pending_thanks(ctx, send=None, limit=5):
    """Wysyła odłożone podziękowania po odmowach (wołane w oknie wysyłki)."""
    send = send or P.send
    with R.db(ctx) as c:
        rows = c.execute("SELECT a.id aid, (SELECT MAX(w.id) FROM wiadomosci w WHERE w.aplikacja_id=a.id AND w.rodzaj='odmowa') wid "
                         "FROM aplikacje a WHERE a.podziekowanie='czeka' LIMIT ?", (limit,)).fetchall()
    n = 0
    for r in rows:
        if r["wid"] and send_thanks(ctx, r["aid"], r["wid"], send):
            n += 1
    return n


def send_thanks(ctx, aid, wid, send):
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        app = dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (aid,)).fetchone())
        msg = dict(c.execute("SELECT * FROM wiadomosci WHERE id=?", (wid,)).fetchone())
        me, _ = R.mailboxes(c)
        if app.get("podziekowanie") not in ("", "czeka"):
            return False
        if not c.execute("UPDATE aplikacje SET podziekowanie='wysylanie' WHERE id=? AND podziekowanie IN ('','czeka')", (aid,)).rowcount:
            return False
        c.commit()
    try:
        send(me, R.secret(ctx, "aga"), msg["od"], re_subject(msg["temat"]), thanks_text(f, app), name=R.full_name(f),
             in_reply_to=msg["message_id"], references=msg["references_"])
    except Exception as e:
        ctx.log.warning(f"Rekrutacja: podziękowanie nie wyszło: {type(e).__name__}")
        with R.db(ctx) as c:                                    # na pewno nie wyszło → spróbuję później; inaczej nie ponawiam
            c.execute("UPDATE aplikacje SET podziekowanie=? WHERE id=?", ("czeka" if isinstance(e, P.NotSent) else "błąd", aid))
            c.commit()
        return False
    with R.db(ctx) as c:
        c.execute("UPDATE aplikacje SET podziekowanie=? WHERE id=?", (R.stamp(ctx), aid))
        R.note(c, ctx, aid, "wysłane podziękowanie po odmowie")
        c.commit()
    return True


def send_draft(ctx, wid, text, send=None):
    """Wysyła (zatwierdzony przez Agę) szkic odpowiedzi w tym samym wątku."""
    send = send or P.send
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        msg = dict(c.execute("SELECT * FROM wiadomosci WHERE id=?", (wid,)).fetchone())
        me, _ = R.mailboxes(c)
        if not c.execute("UPDATE wiadomosci SET wyslano='wysylanie' WHERE id=? AND wyslano=''", (wid,)).rowcount:
            raise RuntimeError("Ta odpowiedź została już wysłana.")
        c.commit()
    try:
        send(me, R.secret(ctx, "aga"), msg["od"], re_subject(msg["temat"]), text, name=R.full_name(f),
             in_reply_to=msg["message_id"], references=msg["references_"])
    except P.NotSent:
        with R.db(ctx) as c:
            c.execute("UPDATE wiadomosci SET wyslano='' WHERE id=?", (wid,))
            c.commit()
        raise
    with R.db(ctx) as c:
        c.execute("UPDATE wiadomosci SET status='zalatwiona', szkic=?, wyslano=? WHERE id=?", (text, R.stamp(ctx), wid))
        if msg["aplikacja_id"]:
            R.note(c, ctx, msg["aplikacja_id"], "wysłana odpowiedź do pracodawcy")
        c.commit()


def answer_question(ctx, qid, answer, remember=True):
    """Aga odpowiada na pytanie → odpowiedź trafia do bazy faktów, a szkic odpowiedzi do pracodawcy jest pisany na nowo."""
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        q = dict(c.execute("SELECT * FROM pytania WHERE id=?", (qid,)).fetchone())
        c.execute("UPDATE pytania SET odpowiedz=?, status='zamkniete', zamknieto=? WHERE id=?", (answer, R.stamp(ctx), qid))
        c.commit()
        still_open = c.execute("SELECT COUNT(*) FROM pytania WHERE wiadomosc_id=? AND status='otwarte'", (q["wiadomosc_id"],)).fetchone()[0]
        answers = [dict(r) for r in c.execute("SELECT pytanie, odpowiedz FROM pytania WHERE wiadomosc_id=? AND status='zamkniete'", (q["wiadomosc_id"],))]
        msg = c.execute("SELECT * FROM wiadomosci WHERE id=?", (q["wiadomosc_id"],)).fetchone()
        app = dict(c.execute("SELECT * FROM aplikacje WHERE id=?", (q["aplikacja_id"],)).fetchone()) if q["aplikacja_id"] else {"firma": "", "stanowisko": ""}
    if remember and len(answer) <= 400:
        f.setdefault("odpowiedzi", {})[q["pytanie"][:200]] = answer
        R.save_facts(ctx, f)
    if msg and not still_open:
        extra = "ODPOWIEDZI KANDYDATKI NA PYTANIA:\n" + "\n".join(f"- {a['pytanie']}: {a['odpowiedz']}" for a in answers)
        draft, _ = draft_reply(ctx, R.load_facts(ctx), app, dict(msg), {"rodzaj": msg["rodzaj"], "pytania": []}, extra=extra)
        with R.db(ctx) as c:
            c.execute("UPDATE wiadomosci SET szkic=? WHERE id=?", (draft, msg["id"]))
            c.commit()


# ================================================================ przypomnienie po ciszy

def follow_ups(ctx, send=None, limit=5):
    send = send or P.send
    st = ctx.settings()
    days = int(st.get("przypomnienie_po_dniach", 10))
    if not st.get("przypomnienia", True) or days <= 0:
        return 0
    cut = (ctx.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    f = R.load_facts(ctx)
    with R.db(ctx) as c:
        me, _ = R.mailboxes(c)
        rows = [dict(r) for r in c.execute("SELECT * FROM aplikacje WHERE status='wyslana' AND przypomnienie='' AND odpowiedz_kiedy='' "
                                           "AND wyslano<>'' AND wyslano<? AND message_id<>'' AND email<>'' ORDER BY wyslano LIMIT ?", (cut, limit))]
    done = 0
    for a in rows:
        try:
            send(me, R.secret(ctx, "aga"), a["email"], re_subject(a["temat"]), reminder_text(f, a), name=R.full_name(f),
                 in_reply_to=a["message_id"], references="")
        except Exception as e:
            ctx.log.warning(f"Rekrutacja: przypomnienie {a['id']} nie wyszło: {type(e).__name__}")
            break
        with R.db(ctx) as c:
            c.execute("UPDATE aplikacje SET przypomnienie=? WHERE id=?", (R.stamp(ctx), a["id"]))
            R.note(c, ctx, a["id"], f"wysłane przypomnienie po {days} dniach ciszy")
            c.commit()
        done += 1
    return done
