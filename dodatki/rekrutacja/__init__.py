"""Dodatek Rekrutacja (Sebastian 2.8).

Osobny panel dla Agi w sieci Tailscale: baza faktów z CV, dopasowane CV i list przewodni z kontrolą prawdy,
wysyłka mailem po zatwierdzeniu, raport wieczorny. Panel i praca w tle działają jako własna usługa
(pl.sebastian.rekrutacja), żeby nie blokować pętli WhatsAppa.

    python sebastian.py dodatek rekrutacja usluga instaluj     # panel i praca w tle, start po zalogowaniu do Maca
    python sebastian.py dodatek rekrutacja adres               # adres panelu i link pierwszego uruchomienia
"""
import contextlib, os, plistlib, secrets, subprocess, sys
from pathlib import Path

from . import rdzen as R

LABEL = "pl.sebastian.rekrutacja"


def _plist():
    return Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")


def _root():
    return Path(__file__).resolve().parents[2]


def _token(ctx, new=False):
    """Jednorazowy link do ustawienia hasła: istnieje, dopóki hasło nie jest ustawione (albo po poleceniu haslo)."""
    with R.db(ctx) as c:
        tok = R.meta_get(c, "token_startowy")
        if new or (not tok and not R.meta_get(c, "haslo")):
            tok = secrets.token_urlsafe(18)
            R.meta_set(c, "token_startowy", tok)
        return tok


def cmd_start(ctx, args):
    from . import panel
    panel.serve(ctx)
    return 0


def cmd_usluga(ctx, args):
    action = (args[0] if args else "status").lower()
    if sys.platform != "darwin":
        print("Usługę w tle instaluje się na Macu. Do prób: python sebastian.py dodatek rekrutacja start")
        return 1
    uid, path = str(os.getuid()), _plist()
    if action in ("instaluj", "usun", "usuń"):
        subprocess.run(["launchctl", "bootout", "gui/" + uid, str(path)], capture_output=True)
        if action != "instaluj":
            path.unlink(missing_ok=True)
            print("Usługa Rekrutacja wyłączona. Dane zostają w data/dodatki/rekrutacja/.")
            return 0
        root, data = _root(), ctx.folder().parents[1]
        (data / "logs").mkdir(exist_ok=True)
        py = root / ".venv" / "bin" / "python"
        job = {"Label": LABEL, "ProgramArguments": [str(py if py.exists() else sys.executable), str(root / "sebastian.py"), "dodatek", "rekrutacja", "start"],
               "WorkingDirectory": str(root), "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 20,
               "EnvironmentVariables": {"SEBASTIAN_DATA": str(data), "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
               "StandardOutPath": str(data / "logs" / "rekrutacja.log"), "StandardErrorPath": str(data / "logs" / "rekrutacja.err")}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(job))
        subprocess.run(["launchctl", "bootstrap", "gui/" + uid, str(path)], check=True)
        print("Usługa Rekrutacja działa i będzie startować po zalogowaniu do Maca.")
        return cmd_adres(ctx, [])
    r = subprocess.run(["launchctl", "print", f"gui/{uid}/{LABEL}"], capture_output=True, text=True)
    print("Usługa: " + ("działa" if r.returncode == 0 and "state = running" in r.stdout else
                         "zainstalowana, ale nie działa — zobacz data/logs/rekrutacja.err" if r.returncode == 0 else "nie jest zainstalowana"))
    return 0


def cmd_adres(ctx, args):
    from . import panel
    st = ctx.settings()
    ip = panel.tailscale_ip() if st.get("nasluch") == "tailscale" else ""
    name = panel.tailscale_name() if ip else ""
    base = f"http://{name or ip or '127.0.0.1'}:{int(st.get('port', 8790))}"
    print(f"Panel Rekrutacja:   {base}")
    if not ip and st.get("nasluch") == "tailscale":
        print("  (Tailscale na tym Macu nie odpowiada — włącz go, a potem: python sebastian.py dodatek rekrutacja usluga instaluj)")
    tok = _token(ctx)
    if tok:
        print(f"Pierwsze wejście:   {base}/start/{tok}")
        print("  Ten link wyślij Adze. Działa raz: Aga ustawia na nim własne hasło i przechodzi przez powitanie.")
    else:
        print("Hasło jest już ustawione. Nowy link do zmiany hasła: python sebastian.py dodatek rekrutacja haslo")
    return 0


def cmd_haslo(ctx, args):
    _token(ctx, new=True)
    print("Przygotowałem nowy jednorazowy link do ustawienia hasła (stare hasło działa, dopóki Aga nie ustawi nowego).")
    return cmd_adres(ctx, [])


def cmd_status(ctx, args):
    with R.db(ctx) as c:
        me, seb = R.mailboxes(c)
        step = R.meta_get(c, "onboarding", "1")
        print("Pierwsze uruchomienie: " + ("zakończone" if step == "gotowe" else f"krok {step} z 8"))
        print(f"Skrzynka Agi:        {me or '— niepodłączona'}" + ("" if not me or R.secret(ctx, 'aga') else "  (brak hasła w pęku kluczy!)"))
        print(f"Skrzynka Sebastiana: {seb or '— niepodłączona (raport pójdzie ze skrzynki Agi)'}")
        rows = c.execute("SELECT status, COUNT(*) n FROM aplikacje GROUP BY status ORDER BY n DESC").fetchall()
        print("Aplikacje: " + (", ".join(f"{R.STATUS.get(r['status'], r['status'])}: {r['n']}" for r in rows) or "brak"))
        print(f"Adres panelu: {R.meta_get(c, 'adres_panelu') or '— usługa jeszcze nie startowała'}")
    st = ctx.settings()
    print(f"Wysyłka: {'WSTRZYMANA' if st.get('wstrzymane') else 'włączona'}, {st.get('godziny')}, limit {st.get('limit_dzienny')} dziennie, raport {st.get('raport')}")
    return 0


def cmd_ustawienia(ctx, args):
    for k, v in ctx.settings().items():
        print(f"{k} = {v}")
    return 0


def cmd_ustaw(ctx, args):
    if len(args) < 2:
        print("Użycie: python sebastian.py dodatek rekrutacja ustaw KLUCZ WARTOŚĆ")
        return 1
    try:
        print(f"{args[0]} = {ctx.set_setting(args[0], ' '.join(args[1:]))}")
    except Exception as e:
        print(e)
        return 1
    if args[0] in ("port", "nasluch", "dodatkowy_host"):
        print("Zadziała po przeładowaniu: python sebastian.py dodatek rekrutacja usluga instaluj")
    return 0


def cmd_szukaj(ctx, args):
    from . import zrodla as Z
    with R.db(ctx) as c:
        Z.seed(c, ctx)
        c.execute("UPDATE zrodla SET sprawdzono=''")
        c.commit()
    n = Z.discover(ctx, max_new=int(args[0]) if args and args[0].isdigit() else 40)
    print(f"Nowe oferty w kolejce: {n}")
    with R.db(ctx) as c:
        for r in c.execute("SELECT * FROM zrodla ORDER BY id"):
            print(f"  {'✓' if r['wlaczone'] else '·'} {r['nazwa'] or r['url']}: {r['wynik'] or '—'}")
    return 0


def cmd_skrzynka(ctx, args):
    from . import odpowiedzi as A
    print(f"Nowe wiadomości od pracodawców: {A.check_inbox(ctx)}")
    return 0


def cmd_raport(ctx, args):
    from . import panel
    print("Raport wysłany." if panel.evening_report(ctx, force=True) else "Raport nie wyszedł — sprawdź skrzynki (status).")
    return 0


def cmd_uzupelnij(ctx, args):
    """Scala zatwierdzone uzupełnienia (JSON) z bazą faktów. Niczego nie usuwa poza tym, co plik wprost wskazuje."""
    import json
    from pathlib import Path
    if not args:
        print("Użycie: python sebastian.py dodatek rekrutacja uzupelnij PLIK.json")
        return 1
    patch = json.loads(Path(args[0]).expanduser().read_text(encoding="utf-8"))
    print(apply_patch(ctx, patch))
    return 0


def apply_patch(ctx, patch):
    f = R.load_facts(ctx)
    n = R.norm
    added = 0
    flat = lambda lst: [x["tekst"] if isinstance(x, dict) else x for x in lst]

    def add_list(key, items):
        nonlocal added
        cur = flat(f[key])
        for t in items:
            if n(t) not in {n(x) for x in cur}:
                cur.append(t)
                added += 1
        f[key] = cur

    for key in ("profil", "umiejetnosci", "kursy", "jezyki"):
        add_list(key, patch.get(key, []))
    kursy = flat(f["kursy"])
    for rule in patch.get("kursy_zmien", []):
        kursy = [rule["na"] if n(rule["zawiera"]) in n(k) else k for k in kursy]
    kursy = [k for k in kursy if not any(n(x) in n(k) for x in patch.get("kursy_usun", []))]
    f["kursy"] = list(dict.fromkeys(kursy))
    jobs = [dict(j, punkty=flat(j["punkty"])) for j in f["doswiadczenie"]]
    for s in patch.get("stanowiska", []):
        if not any(n(j["stanowisko"]) == n(s["stanowisko"]) and n(j.get("firma", "")) == n(s.get("firma", "")) for j in jobs):
            jobs.append(dict(s))
            added += 1
    for p in patch.get("punkty", []):
        j = next((j for j in jobs if (p.get("firma") and n(p["firma"]) in n(j.get("firma", ""))) or
                  (p.get("stanowisko") and n(p["stanowisko"]) == n(j["stanowisko"]))), None)
        if j is not None and n(p["tekst"]) not in {n(x) for x in j["punkty"]}:
            j["punkty"].append(p["tekst"])
            added += 1
    f["doswiadczenie"] = jobs
    tools = [{"nazwa": t["nazwa"], "poziom": t["poziom"]} for t in f["narzedzia"]]
    tools = [t for t in tools if not any(n(x) in n(t["nazwa"]) for x in patch.get("narzedzia_usun", []))]
    for t in patch.get("narzedzia", []):
        cur = next((x for x in tools if n(x["nazwa"]) == n(t["nazwa"])), None)
        if cur:
            cur["poziom"] = t.get("poziom") or cur["poziom"]
        else:
            tools.append({"nazwa": t["nazwa"], "poziom": t.get("poziom", "")})
            added += 1
    f["narzedzia"] = tools
    crit = f["kryteria"]
    crit["nie_chce"] = list(dict.fromkeys(crit.get("nie_chce", []) + patch.get("nie_chce", [])))
    for k, v in (patch.get("osoba") or {}).items():
        f["osoba"][k] = v
    for k, v in (patch.get("warunki") or {}).items():
        f["warunki"][k] = v
    for k, v in (patch.get("ustawienia") or {}).items():
        ctx.set_setting(k, v)
    R.save_facts(ctx, f)
    hist = 0
    with R.db(ctx) as c:
        for h in patch.get("historia", []):
            if R.find_duplicate(c, h["firma"], h.get("stanowisko", ""), zrodlo="oferta"):
                continue
            now = R.stamp(ctx)
            cur = c.execute("INSERT INTO aplikacje(utworzono,zmieniono,status,zrodlo,firma,stanowisko,miasto,klucz,notatka,wyslano) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (now, now, h.get("status", "wyslana_recznie"), "oferta", h["firma"], h.get("stanowisko", ""), h.get("miasto", "Kraków"),
                             R.dedupe_key(h["firma"], h.get("stanowisko", "")), h.get("notatka", "Aplikacja wysłana przed uruchomieniem Sebastiana."), ""))
            R.note(c, ctx, cur.lastrowid, "dopisana z historii poszukiwań (przed Sebastianem)")
            hist += 1
        c.commit()
    return f"Baza faktów: dodane {added}. Historia aplikacji: dopisane {hist}."


COMMANDS = {"uzupelnij": cmd_uzupelnij, "szukaj": cmd_szukaj, "skrzynka": cmd_skrzynka, "raport": cmd_raport, "start": cmd_start, "usluga": cmd_usluga, "adres": cmd_adres, "haslo": cmd_haslo, "status": cmd_status,
            "ustawienia": cmd_ustawienia, "ustaw": cmd_ustaw}
