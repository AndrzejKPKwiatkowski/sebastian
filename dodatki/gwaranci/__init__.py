"""Dodatek Gwaranci (Sebastian 2.14.3) — spotkania gwaranckie Feniksów.

Gwarant dostaje osobisty link, podłącza kalendarz (tylko zajętość), zaznacza kiedy może i ile spotkań w tygodniu.
Adept wybiera typ i godzinę, Sebastian dobiera gwaranta (bezpośredni menedżer → pośredni → ta sama struktura → inna)
i wysyła zaproszenie z Gmaila. Ty dostajesz krótkie powiadomienia na WhatsAppie.

    python sebastian.py dodatek gwaranci usluga instaluj     # panel i praca w tle (start po zalogowaniu do Maca)
    python sebastian.py dodatek gwaranci internet wlacz      # publiczny adres https (Tailscale Funnel)
    python sebastian.py dodatek gwaranci linki               # osobiste linki do rozesłania
    python sebastian.py dodatek gwaranci calcom              # kto ma podpięty cal.com; podpięcie: calcom "Imię Nazwisko" https://cal.com/…
"""
import contextlib, getpass, os, plistlib, re, subprocess, sys
from pathlib import Path

from . import rdzen as R

LABEL = "pl.sebastian.gwaranci"


def _plist():
    return Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")


def _root():
    return Path(__file__).resolve().parents[2]


def _base(ctx, c):
    return (R.meta_get(c, "adres_publiczny") or ctx.settings().get("adres") or f"http://127.0.0.1:{ctx.settings().get('port', 8791)}").rstrip("/")


def cmd_start(ctx, args):
    from . import panel
    panel.serve(ctx)
    return 0


def cmd_usluga(ctx, args):
    action = (args[0] if args else "status").lower()
    if sys.platform != "darwin":
        print("Usługę instaluje się na Macu. Do prób: python sebastian.py dodatek gwaranci start")
        return 1
    uid, path = str(os.getuid()), _plist()
    if action in ("instaluj", "usun", "usuń"):
        subprocess.run(["launchctl", "bootout", "gui/" + uid, str(path)], capture_output=True)
        if action != "instaluj":
            path.unlink(missing_ok=True)
            print("Usługa Gwaranci wyłączona. Dane zostają w data/dodatki/gwaranci/.")
            return 0
        root, data = _root(), ctx.folder().parents[1]
        (data / "logs").mkdir(exist_ok=True)
        py = root / ".venv" / "bin" / "python"
        job = {"Label": LABEL, "ProgramArguments": [str(py if py.exists() else sys.executable), str(root / "sebastian.py"), "dodatek", "gwaranci", "start"],
               "WorkingDirectory": str(root), "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 20,
               "EnvironmentVariables": {"SEBASTIAN_DATA": str(data), "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
               "StandardOutPath": str(data / "logs" / "gwaranci.log"), "StandardErrorPath": str(data / "logs" / "gwaranci.err")}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(job))
        subprocess.run(["launchctl", "bootstrap", "gui/" + uid, str(path)], check=True)
        print("Usługa Gwaranci działa i będzie startować po zalogowaniu do Maca.")
        return cmd_adres(ctx, [])
    r = subprocess.run(["launchctl", "print", f"gui/{uid}/{LABEL}"], capture_output=True, text=True)
    print("Usługa: " + ("działa" if r.returncode == 0 and "state = running" in r.stdout else
                         "zainstalowana, ale nie działa — zobacz data/logs/gwaranci.err" if r.returncode == 0 else "nie jest zainstalowana"))
    return 0


def cmd_internet(ctx, args):
    """Tailscale Funnel: publiczny adres https://<mac>.<sieć>.ts.net prowadzący do panelu (tylko ten jeden port)."""
    from . import panel as PN
    action = (args[0] if args else "status").lower()
    port = int(ctx.settings().get("port", 8791))
    if action in ("wlacz", "włącz"):
        code, out = PN._tailscale("funnel", "--bg", f"http://127.0.0.1:{port}")
        print(out)
        m = re.search(r"https://[a-z0-9.-]+\.ts\.net", out or "")
        url = m.group(0) if m else (f"https://{PN.tailscale_name()}" if code == 0 and PN.tailscale_name() else "")
        if code != 0 or not url:
            print("\nNie udało się włączyć Funnel. Najczęściej trzeba go raz zezwolić w panelu Tailscale: otwórz link powyżej "
                  "(jeśli jest) albo login.tailscale.com → Access controls → włącz „Funnel” dla tego Maca, i uruchom polecenie ponownie.")
            return 1
        with contextlib.closing(R.db(ctx)) as c:
            R.meta_set(c, "adres_publiczny", url)
        print(f"\n✅ Panel jest dostępny w internecie: {url}")
        return 0
    if action in ("wylacz", "wyłącz"):
        code, out = PN._tailscale("funnel", "--https=443", "off")
        print(out or "Funnel wyłączony.")
        with contextlib.closing(R.db(ctx)) as c:
            R.meta_set(c, "adres_publiczny", "")
        return 0
    code, out = PN._tailscale("funnel", "status")
    print(out or "Funnel: brak danych.")
    return 0


def cmd_adres(ctx, args):
    with contextlib.closing(R.db(ctx)) as c:
        print(f"Panel Gwaranci: {_base(ctx, c)}")
        if not R.meta_get(c, "adres_publiczny"):
            print("  (Tylko na tym Macu i w Tailscale. Dla zespołu włącz: python sebastian.py dodatek gwaranci internet wlacz)")
    return 0


def cmd_poczta(ctx, args):
    with contextlib.closing(R.db(ctx)) as c:
        addr, pwd = R.mailbox(ctx, c)
        if args and args[0] == "test":                     # próbny mail z zaproszeniem (.ics) na skrzynkę Sebastiana albo podany adres
            to = args[1] if len(args) > 1 else addr
            print(f"Wysyłam próbny mail z zaproszeniem: {addr} → {to} …")
            ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Sebastian//Gwaranci//PL\r\nMETHOD:REQUEST\r\nBEGIN:VEVENT\r\n"
                   "UID:test-gwaranci@sebastian\r\nDTSTAMP:20260101T000000Z\r\nDTSTART:20300101T090000Z\r\nDTEND:20300101T093000Z\r\n"
                   "SUMMARY:Test Sebastiana\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
            try:
                R.send_mail(ctx, c, to, "Test Sebastiana – Gwaranci", "Próbny mail z zaproszeniem.", ics=ics)
                print("✅ Wyszedł. Sprawdź skrzynkę odbiorcy.")
                return 0
            except Exception as e:
                print(f"❌ {type(e).__name__}: {e}")
                return 1
        n = c.execute("SELECT COUNT(*) FROM poczta_kolejka WHERE wyslano='' AND proby<12").fetchone()[0]
        if n:
            print(f"W kolejce czeka {n} mail(i) — Sebastian ponawia je sam co kilka minut.")
        if addr and pwd and "--zmien" not in args:
            print(f"Zaproszenia wysyłam ze skrzynki: {addr} (jako „{ctx.settings().get('nadawca')}”).")
            print("Inna skrzynka: python sebastian.py dodatek gwaranci poczta --zmien")
            return 0
        addr = input("Adres Gmail Sebastiana (np. sebastian.k.kwiatkowski@gmail.com): ").strip()
        pwd = getpass.getpass("Hasło aplikacji Google (16 liter, nie zwykłe hasło; nie będzie widoczne): ")
        R.meta_set(c, "poczta", addr)
        ctx.set_secret("poczta", "".join(pwd.split()))
        print("Zapisane w pęku kluczy macOS.")
    return 0


def _attach_calcom(c, name, link):
    p = R.find_person(c, name)
    ref = R.parse_calcom(link)
    if not p:
        return f"Nie znam osoby „{name}”."
    if not ref:
        return "To nie wygląda na link do wydarzenia cal.com (np. https://cal.com/nazwa/spotkanie-gwaranckie)."
    if not R.can_guarantee(p):
        return f"{p['imie_nazwisko']} nie jest jeszcze gwarantem (gwarantem zostaje się po pierwszym awansie)."
    g = R.guarantor(c, p["id"]) or {}
    R.save_guarantor(c, p["id"], calcom=ref, gotowe=1, limit_tyg=g.get("limit_tyg") or R.max_limit(p))
    n, err = R.refresh_calcom(c, p["id"])
    return (f"{p['imie_nazwisko']}: cal.com podpięty ({ref})" + (f", {n} wolnych terminów." if not err else f" — ⚠ {err}"))


def cmd_calcom(ctx, args):
    with contextlib.closing(R.db(ctx)) as c:
        if args and args[0] == "klucz":
            print("Klucz API z cal.com → Settings → Developer → API Keys (opcjonalny: pozwala Sebastianowi odczytać akceptacje i odwołania).")
            key = getpass.getpass("Klucz API (cal_live_…, nie będzie widoczny): ").strip()
            if key:
                ctx.set_secret("calcom_klucz", key)
                print("Zapisane w pęku kluczy macOS.")
            return 0
        if args and args[0] == "test":                     # co cal.com mówi o wydarzeniu i ostatni błąd rezerwacji
            last = R.meta_get(c, "calcom_ostatni_blad")
            print("Ostatni błąd rezerwacji w cal.com: " + (last or "brak"))
            for r in c.execute("SELECT osoba, calcom FROM gwaranci WHERE calcom!=''").fetchall():
                user, ev = r["calcom"].split("/", 1)
                code, js = R.calcom_http("GET", "/event-types", params={"username": user, "eventSlug": ev}, version="2024-06-14")
                d = (js or {}).get("data")
                d = d[0] if isinstance(d, list) and d else d
                if code != 200 or not isinstance(d, dict):
                    print(f"{r['calcom']}: cal.com {code} {str(js)[:200]}")
                    continue
                req = [f.get("slug") or f.get("name") for f in d.get("bookingFields") or [] if f.get("required") and not f.get("hidden")]
                print(f"{r['calcom']}: długość {d.get('lengthInMinutes')} min (opcje: {d.get('lengthInMinutesOptions') or '—'}), "
                      f"wymaga potwierdzenia: {bool(d.get('confirmationPolicy') or d.get('requiresConfirmation'))}, "
                      f"pola obowiązkowe: {', '.join(map(str, req)) or '—'}, miejsca: {[l.get('type') for l in d.get('locations') or []]}")
            return 0
        if len(args) >= 2:
            print(_attach_calcom(c, " ".join(args[:-1]), args[-1]))
            return 0
        rows = c.execute("SELECT osoba, calcom, blad, odczyt FROM gwaranci WHERE calcom!=''").fetchall()
        ppl = R.people(c)
        for r in rows:
            print(f"{ppl.get(r['osoba'], {}).get('imie_nazwisko', r['osoba']):<26} https://cal.com/{r['calcom']}"
                  + (f"  ⚠ {r['blad'][:80]}" if r["blad"] else (f"  odczyt {r['odczyt'][11:16]}" if r["odczyt"] else "")))
        if not rows:
            print("Nikt nie ma jeszcze podpiętego cal.com.")
        print('Podpięcie: python sebastian.py dodatek gwaranci calcom "Imię Nazwisko" https://cal.com/nazwa/wydarzenie')
    return 0


def cmd_linki(ctx, args):
    with contextlib.closing(R.db(ctx)) as c:
        base = _base(ctx, c)
        if args:
            p = R.find_person(c, " ".join(args))
            if not p:
                print("Nie znam tej osoby.")
                return 1
            print(f"{p['imie_nazwisko']}: {base}/l/{p['token']}")
            return 0
        ppl = R.people(c)
        for p in sorted(ppl.values(), key=lambda p: (R.structure_of(ppl, p["id"]) or "", p["imie_nazwisko"])):
            role = "gwarant" if R.can_guarantee(p) else "adept"
            print(f"{p['imie_nazwisko']:<26} {role:<8} {base}/l/{p['token']}")
    return 0


def cmd_awans(ctx, args):
    text = " ".join(args)
    with contextlib.closing(R.db(ctx)) as c:
        print(_promote(c, text))
    return 0


def _promote(c, text):
    m = re.match(r"(.+?)\s+(?:na\s+)?((?:senior |vip )?planner(?: ii)?|consultant(?: ii)?|trainee|m[1-9].*|d[1-9].*)$", text.strip(), re.I)
    if not m:
        return "Napisz np.: awans Wiktor Król na Senior Planner"
    p = R.find_person(c, m.group(1))
    if not p:
        return f"Nie znam osoby „{m.group(1)}”."
    pos = m.group(2).strip()
    pos = " ".join(w.upper() if re.fullmatch(r"(?i)ii|m\d|d\d|vip", w) else w.capitalize() for w in pos.split())
    p = R.set_position(c, p["id"], pos)
    return f"{p['imie_nazwisko']}: {pos}. Limit spotkań gwaranckich: {R.max_limit(p)} w tygodniu."


def cmd_dodaj(ctx, args):
    if len(args) < 2:
        print('Użycie: python sebastian.py dodatek gwaranci dodaj "Imię Nazwisko" "Przełożony" [Stanowisko]')
        return 1
    with contextlib.closing(R.db(ctx)) as c:
        try:
            p = R.add_person(c, args[0], " ".join(args[2:]) or "Trainee", args[1])
        except ValueError as e:
            print(e)
            return 1
        print(f"Dodano: {p['imie_nazwisko']}. Link: {_base(ctx, c)}/l/{p['token']}")
    return 0


def cmd_struktura(ctx, args):
    """Wczytuje data/dodatki/gwaranci/struktura.json: nowe osoby dopisuje, istniejącym poprawia stanowisko i przełożonego."""
    import json
    path = ctx.folder() / R.STRUCTURE_FILE
    if not path.exists():
        print(f"Brak pliku {path}.")
        return 1
    with contextlib.closing(R.db(ctx)) as c:
        n = R.import_people(c, json.loads(path.read_text(encoding="utf-8")).get("osoby", []), update=True)
        print(f"Struktura wczytana: {n} osób (nowe dopisane, istniejące zaktualizowane). Osobiste linki się nie zmieniły.")
    return 0


def status_text(ctx, c):
    ppl = R.people(c)
    ready = R.ready_guarantors(c)
    lines = [f"Gwaranci gotowi: {len(ready)}"]
    for pid, g in ready.items():
        n, _ = R.week_load(c, pid, R.now(ctx))
        lines.append(f"• {ppl[pid]['imie_nazwisko']} — {n}/{g['limit_tyg']} w tym tygodniu" + (" (wstrzymany)" if g["wstrzymany"] else "")
                     + (" · cal.com" if g.get("calcom") else "") + (f" ⚠ kalendarz: {g['blad'][:60]}" if g["blad"] else ""))
    pend = c.execute("SELECT COUNT(*) n FROM rezerwacje WHERE status='czeka'").fetchone()["n"]
    conf = c.execute("SELECT COUNT(*) n FROM rezerwacje WHERE status='potwierdzone'").fetchone()["n"]
    asks = c.execute("SELECT COUNT(*) n FROM prosby WHERE status='nowa'").fetchone()["n"]
    lines.append(f"Czeka na akceptację: {pend} · potwierdzone: {conf}" + (f" · prośby o dostęp: {asks}" if asks else ""))
    lines.append(f"Panel: {_base(ctx, c)}")
    return "\n".join(lines)


def cmd_status(ctx, args):
    with contextlib.closing(R.db(ctx)) as c:
        print(status_text(ctx, c))
        addr, pwd = R.mailbox(ctx, c)
        print(f"Skrzynka zaproszeń: {addr or '— brak'}" + ("" if not addr or pwd else " (brak hasła!)"))
    return 0


def cmd_odswiez(ctx, args):
    from . import przebieg as PB
    with contextlib.closing(R.db(ctx)) as c:
        for pid in R.ready_guarantors(c):
            n, err = R.refresh_busy(c, pid)
            print(f"{R.person(c, pid)['imie_nazwisko']}: {n} zajętych terminów" + (f" — błąd: {err}" if err else ""))
        PB.periodic(ctx, c, refresh=False)
    print("Gotowe.")
    return 0


def cmd_ustawienia(ctx, args):
    for k, v in ctx.settings().items():
        print(f"{k} = {v}")
    return 0


def cmd_ustaw(ctx, args):
    if len(args) < 2:
        print("Użycie: python sebastian.py dodatek gwaranci ustaw KLUCZ WARTOŚĆ")
        return 1
    print(f"{args[0]} = {ctx.set_setting(args[0], ' '.join(args[1:]))}")
    return 0


def on_message(ctx, msg):
    """WhatsApp od właściciela: tylko wiadomości zaczynające się od „gwaranci”."""
    text = (msg.get("text") or "").strip()
    m = re.match(r"(?i)^gwaranci\b[\s:,-]*(.*)$", text)
    if not m:
        return None
    rest = m.group(1).strip()
    with contextlib.closing(R.db(ctx)) as c:
        if not rest or re.match(r"(?i)^(stan|status)$", rest):
            return status_text(ctx, c)
        mm = re.match(r"(?i)^link\s+(.+)$", rest)
        if mm:
            p = R.find_person(c, mm.group(1))
            return f"{p['imie_nazwisko']}: {_base(ctx, c)}/l/{p['token']}" if p else f"Nie znam osoby „{mm.group(1)}”."
        mm = re.match(r"(?i)^cal\.?com\s+(.+?)\s+(\S*cal\.com/\S+)$", rest)
        if mm:
            return _attach_calcom(c, mm.group(1), mm.group(2))
        mm = re.match(r"(?i)^awans\s+(.+)$", rest)
        if mm:
            return _promote(c, mm.group(1))
        mm = re.match(r"(?i)^dodaj\s+(.+?)\s+od\s+(.+?)(?:\s*,\s*(.+))?$", rest)
        if mm:
            try:
                p = R.add_person(c, mm.group(1), mm.group(3) or "Trainee", mm.group(2))
            except ValueError as e:
                return str(e)
            return f"Dodano {p['imie_nazwisko']} (od: {mm.group(2)}). Link: {_base(ctx, c)}/l/{p['token']}"
        return ("Gwaranci — polecenia: „gwaranci”, „gwaranci link Imię Nazwisko”, „gwaranci awans Imię Nazwisko na Planner”, "
                "„gwaranci dodaj Imię Nazwisko od Imię Nazwisko”, „gwaranci calcom Imię Nazwisko https://cal.com/…”.")


COMMANDS = {"start": cmd_start, "usluga": cmd_usluga, "internet": cmd_internet, "adres": cmd_adres, "poczta": cmd_poczta,
            "linki": cmd_linki, "calcom": cmd_calcom, "struktura": cmd_struktura, "awans": cmd_awans, "dodaj": cmd_dodaj, "status": cmd_status, "odswiez": cmd_odswiez,
            "ustawienia": cmd_ustawienia, "ustaw": cmd_ustaw}
