"""Sebastian 2.7 — gniazdo na dodatki.

Dodatek to osobny folder z dwoma plikami — ten sam układ co w Sebastianie 3:
    dodatki/<id>/dodatek.json    opis: id, nazwa, wersja, uprawnienia, ustawienia, polecenia, pomoc
    dodatki/<id>/__init__.py     kod: on_message(ctx, msg), tick(ctx), COMMANDS = {"nazwa": funkcja}

Dodatki wbudowane leżą w dodatki/ (w repozytorium), Twoje własne w data/dodatki/ (tylko na Macu).
Główny kod Sebastiana woła tylko trzy rzeczy: on_message (wiadomość od właściciela), tick (co kilka sekund
w usłudze WhatsApp) i help_text (do „pomoc”). Dodatek dostaje `ctx` — jedyne drzwi do Sebastiana,
z uprawnieniami z manifestu. Błąd w dodatku nigdy nie psuje WhatsAppa: jest zapisywany w logu, a po
3 błędach z rzędu dodatek pauzuje na 10 minut.
"""
import contextlib, datetime as dt, importlib.util, json, logging, re, sqlite3, subprocess, sys, time
from pathlib import Path

W = None                      # moduł whatsapp (związany przez bind)
log = logging.getLogger("sebastian.dodatki")
HOST_VERSION = "2.8"
PERMISSIONS = {
    "whatsapp.wysylanie": "wysyła Ci wiadomości i głosówki na WhatsAppie",
    "whatsapp.obserwacja": "czyta (tylko odczyt) Twoje rozmowy z obserwowanego WhatsAppa",
    "poczta.odczyt": "czyta to, co Sebastian wie z poczty, notatek i nauki",
    "kalendarz.odczyt": "czyta Twój kalendarz",
    "zadania.zapis": "dodaje zadania do listy zadań",
    "model": "korzysta z lokalnego modelu (Ollama)",
    "telefon": "dzwoni na Twój telefon przez usługę zewnętrzną (Twilio) — tylko gdy ją skonfigurujesz",
}
_LOADED = {}
_STATE = {}                   # id → {"errors": n, "paused_until": ts, "last_tick": ts}


class AddonError(RuntimeError):
    pass


class PermissionDenied(AddonError):
    pass


def bind(whatsapp_module):
    global W
    W = whatsapp_module
    if getattr(W, "S", None) is None:          # np. w osobnym procesie: moduł WhatsAppa jeszcze niezwiązany z Sebastianem
        import sebastian
        W.bind(sebastian)
    return sys.modules[__name__]


def _w():
    if W is None or getattr(W, "S", None) is None:
        import whatsapp
        bind(whatsapp)
    return W


def code_root():
    return Path(__file__).resolve().parent


def data_root():
    return Path(_w().S.DATA) / "dodatki"


def search_paths():
    return [code_root() / "dodatki", data_root()]


# ================================================================ manifest i odkrywanie

def validate(manifest, folder=None):
    problems = []
    aid = manifest.get("id", "")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", str(aid)):
        problems.append("id: małe litery, cyfry i _, 2–40 znaków")
    if folder is not None and aid and Path(folder).name != aid:
        problems.append(f"folder nazywa się {Path(folder).name}, a id to {aid}")
    for key in ("nazwa", "wersja", "opis"):
        if not str(manifest.get(key, "")).strip():
            problems.append(f"brak pola {key}")
    for p in manifest.get("uprawnienia", []):
        if p not in PERMISSIONS:
            problems.append(f"nieznane uprawnienie {p}")
    if not isinstance(manifest.get("ustawienia", {}), dict):
        problems.append("ustawienia muszą być słownikiem")
    return problems


def discover():
    """Wszystkie dodatki: wbudowane i Twoje (data/dodatki). Zepsuty manifest = wpis z listą problemów."""
    found = {}
    for base in search_paths():
        if not base.is_dir():
            continue
        for folder in sorted(p for p in base.iterdir() if p.is_dir() and (p / "dodatek.json").exists()):
            info = {"folder": folder, "builtin": base == code_root() / "dodatki"}
            try:
                info["manifest"] = json.loads((folder / "dodatek.json").read_text(encoding="utf-8"))
                info["problems"] = validate(info["manifest"], folder)
            except Exception as e:
                info["manifest"], info["problems"] = {"id": folder.name}, [f"dodatek.json: {e}"]
            if not (folder / "__init__.py").exists():
                info["problems"].append("brak __init__.py")
            info["id"] = info["manifest"].get("id") or folder.name
            if info["id"] in found:
                continue                                   # wbudowany ma pierwszeństwo przed kopią o tym samym id
            found[info["id"]] = info
    return found


def _switches_path():
    return data_root() / "wlaczone.json"


def switches():
    with contextlib.suppress(Exception):
        return json.loads(_switches_path().read_text(encoding="utf-8"))
    return {}


def is_enabled(info):
    if info.get("problems"):
        return False
    sw = switches()
    if info["id"] in sw:
        return bool(sw[info["id"]])
    return bool(info["builtin"] and info["manifest"].get("domyslnie_wlaczony", False))


def set_enabled(aid, on):
    info = discover().get(aid)
    if not info:
        raise AddonError(f"Nie znam dodatku „{aid}”. Lista: python sebastian.py dodatki")
    if on and info["problems"]:
        raise AddonError("Ten dodatek ma błędy: " + "; ".join(info["problems"]))
    sw = switches()
    sw[aid] = bool(on)
    data_root().mkdir(parents=True, exist_ok=True)
    _switches_path().write_text(json.dumps(sw, indent=2, ensure_ascii=False), encoding="utf-8")


def load(info):
    aid = info["id"]
    if aid in _LOADED:
        return _LOADED[aid]
    spec = importlib.util.spec_from_file_location(f"sebastian_dodatek_{aid}", info["folder"] / "__init__.py",
                                                  submodule_search_locations=[str(info["folder"])])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _LOADED[aid] = (mod, Context(info))
    return _LOADED[aid]


def active():
    """(moduł, ctx) włączonych dodatków; dodatek, który nie chce się wczytać, jest pomijany (z wpisem w logu)."""
    out = []
    for info in discover().values():
        if not is_enabled(info):
            continue
        try:
            out.append(load(info))
        except Exception as e:
            _fail(info["id"], "wczytanie", e)
    return out


def _fail(aid, where, e):
    st = _STATE.setdefault(aid, {"errors": 0, "paused_until": 0, "last_tick": 0})
    st["errors"] += 1
    log.warning(f"Dodatek {aid} ({where}): {type(e).__name__}: {str(e)[:200]}")
    if st["errors"] >= 3:
        st["paused_until"], st["errors"] = time.time() + 600, 0
        log.warning(f"Dodatek {aid}: 3 błędy z rzędu — pauza 10 minut.")


def _paused(aid):
    return _STATE.get(aid, {}).get("paused_until", 0) > time.time()


# ================================================================ haki wołane przez Sebastiana

def on_message(con, kind, text, user=None):
    """Wiadomość od właściciela (tekst albo przepisana głosówka). True = dodatek ją obsłużył (bez zwykłej odpowiedzi)."""
    msg = {"kind": kind, "text": text or "", "voice": kind == "voice", "user": user}
    for mod, ctx in active():
        if _paused(ctx.id) or not hasattr(mod, "on_message"):
            continue
        try:
            ctx._con = con
            out = mod.on_message(ctx, msg)
            _STATE.setdefault(ctx.id, {"errors": 0, "paused_until": 0, "last_tick": 0})["errors"] = 0
        except Exception as e:
            _fail(ctx.id, "wiadomość", e)
            continue
        finally:
            ctx._con = None
        if isinstance(out, str) and out.strip():
            _w().enqueue(con, "text", out.strip()[:3500], purpose=f"reply:{ctx.id}", to="")
            return True
        if out is True:
            return True
    return False


def tick(con):
    """Co obrót pętli WhatsAppa; każdy dodatek najwyżej raz na `tik_co_sekund` (z manifestu, domyślnie 30)."""
    for mod, ctx in active():
        if _paused(ctx.id) or not hasattr(mod, "tick"):
            continue
        st = _STATE.setdefault(ctx.id, {"errors": 0, "paused_until": 0, "last_tick": 0})
        every = float(ctx.manifest.get("tik_co_sekund", 30))
        if time.time() - st["last_tick"] < every:
            continue
        st["last_tick"] = time.time()
        try:
            ctx._con = con
            mod.tick(ctx)
            st["errors"] = 0
        except Exception as e:
            _fail(ctx.id, "tik", e)
        finally:
            ctx._con = None


def help_text():
    lines = []
    for mod, ctx in active():
        for line in ctx.manifest.get("pomoc", []):
            lines.append(f"• {line}")
    return ("\n\n*Dodatki:*\n" + "\n".join(lines)) if lines else ""


def status_lines():
    out = []
    for info in discover().values():
        state = "błędy: " + "; ".join(info["problems"]) if info["problems"] else ("włączony" if is_enabled(info) else "wyłączony")
        out.append(f"{info['id']} {info['manifest'].get('wersja', '')} — {state}")
    return out


# ================================================================ ctx — drzwi dodatku do Sebastiana

class Context:
    def __init__(self, info):
        self.info = info
        self.manifest = info["manifest"]
        self.id = info["id"]
        self.perms = set(self.manifest.get("uprawnienia", []))
        self.log = logging.getLogger(f"sebastian.dodatek.{self.id}")
        self._con = None

    # ---------------------------------------------------------------- podstawy
    def need(self, perm):
        if perm not in self.perms:
            raise PermissionDenied(f"Dodatek {self.id} nie ma uprawnienia {perm}")

    @property
    def W(self):
        return _w()

    def folder(self):
        p = data_root() / self.id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def db(self):
        con = sqlite3.connect(self.folder() / "stan.sqlite3", timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def settings(self):
        merged = dict(self.manifest.get("ustawienia", {}))
        with contextlib.suppress(Exception):
            merged.update(json.loads((self.folder() / "ustawienia.json").read_text(encoding="utf-8")))
        return merged

    def set_setting(self, key, value):
        defaults = self.manifest.get("ustawienia", {})
        if key not in defaults:
            raise AddonError(f"Nie ma ustawienia „{key}”. Dostępne: {', '.join(defaults)}")
        base = defaults[key]
        if isinstance(base, bool):
            value = str(value).lower() in ("1", "tak", "true", "t", "yes", "on")
        elif isinstance(base, int):
            value = int(value)
        elif isinstance(base, float):
            value = float(str(value).replace(",", "."))
        path = self.folder() / "ustawienia.json"
        cur = {}
        with contextlib.suppress(Exception):
            cur = json.loads(path.read_text(encoding="utf-8"))
        cur[key] = value
        path.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
        return value

    def now(self):
        return _w().now()

    def owner_name(self):
        return _w().owner_name() or ""

    def in_quiet(self, at=None):
        return _w().in_quiet(at)

    def quiet_start(self):
        return _w().hm(_w().C.WA_QUIET.split("-")[0])

    def wa_con(self):
        """Połączenie z bazą WhatsAppa: to z pętli usługi albo nowe (polecenia w Terminalu)."""
        return self._con if self._con is not None else contextlib.closing(_w().db())

    # ---------------------------------------------------------------- wysyłanie (do właściciela)
    def send_text(self, text, purpose="info"):
        self.need("whatsapp.wysylanie")
        con = self._con
        if con is not None:
            return _w().enqueue(con, "text", text, purpose=f"{self.id}:{purpose}", to="")
        with contextlib.closing(_w().db()) as c:
            return _w().enqueue(c, "text", text, purpose=f"{self.id}:{purpose}", to="")

    def send_voice(self, text, name="glos"):
        """Głosówka do właściciela (Piper / say). False, gdy głosu nie da się zrobić."""
        self.need("whatsapp.wysylanie")
        Wm = _w()
        ogg, _ = Wm.synthesize(text, Wm.home() / "nagrania" / f"{self.id}-{name}-{Wm.now():%Y%m%d-%H%M%S}")
        if not ogg:
            return False
        if self._con is not None:
            Wm.enqueue(self._con, "voice", text, audio=ogg, purpose=f"{self.id}:{name}", to="")
        else:
            with contextlib.closing(Wm.db()) as c:
                Wm.enqueue(c, "voice", text, audio=ogg, purpose=f"{self.id}:{name}", to="")
        return True

    # ---------------------------------------------------------------- model
    def ask(self, prompt, as_json=False, max_tokens=900, temperature=0.2):
        self.need("model")
        raw = _w().ask(prompt, as_json=as_json, max_tokens=max_tokens, temperature=temperature)
        return _w().parse_json(raw) if as_json else raw

    # ---------------------------------------------------------------- odczyt
    def calendar(self, day):
        """Wydarzenia dnia: [{"start": datetime|None, "end": datetime|None, "all_day": bool, "title", "where"}]."""
        self.need("kalendarz.odczyt")
        Wm = _w()
        S = Wm.S
        out = []
        with contextlib.suppress(Exception), contextlib.closing(S.db()) as c:
            import calendar_actions as CA
            import recurring_ical_events
            start = dt.datetime.combine(day, dt.time(), S.TZ)
            end = start + dt.timedelta(days=1)
            for row in c.execute("SELECT * FROM calendar_sources WHERE enabled=1"):
                with contextlib.suppress(Exception):
                    for ev in recurring_ical_events.of(CA.parse_source(row["content"])).between(start, end):
                        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
                            continue
                        raw_start = ev.decoded("DTSTART")
                        all_day = not isinstance(raw_start, dt.datetime)
                        a = CA.aware(raw_start)
                        b = None
                        with contextlib.suppress(Exception):
                            if ev.get("DTEND") is not None:
                                b = CA.aware(ev.decoded("DTEND"))
                            elif ev.get("DURATION") is not None:
                                b = a + ev.decoded("DURATION")
                        out.append({"start": None if all_day else a, "end": None if all_day else (b or a + dt.timedelta(hours=1)),
                                    "all_day": all_day, "title": str(ev.get("SUMMARY", "Bez tytułu"))[:120],
                                    "where": str(ev.get("LOCATION", ""))[:80]})
            for row in c.execute("SELECT * FROM calendar_drafts WHERE reserved=1"):
                with contextlib.suppress(Exception):
                    d = json.loads(row["data"])
                    if d.get("date") != day.isoformat():
                        continue
                    if d.get("time"):
                        a = dt.datetime.combine(day, Wm.hm(d["time"]), S.TZ)
                        mins = int(d.get("duration") or d.get("minutes") or 60)
                        out.append({"start": a, "end": a + dt.timedelta(minutes=mins), "all_day": False,
                                    "title": str(d.get("title", ""))[:120], "where": str(d.get("location", ""))[:80]})
                    else:
                        out.append({"start": None, "end": None, "all_day": True, "title": str(d.get("title", ""))[:120],
                                    "where": str(d.get("location", ""))[:80]})
        seen, unique = set(), []
        for e in sorted(out, key=lambda x: (x["start"] is not None, x["start"] or dt.datetime.min.replace(tzinfo=S.TZ))):
            key = (e["start"], e["title"])
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique

    def search_knowledge(self, query, limit=3000):
        """Poczta, notatki, nauka — to samo, czego Sebastian używa do odpowiedzi właścicielowi."""
        self.need("poczta.odczyt")
        Wm = _w()
        with Wm.as_user(Wm.owner_user()):
            return Wm.search_context(query, limit=limit)

    def search_whatsapp(self, words, days=30, limit=12):
        """Twoje rozmowy z obserwowanego WhatsAppa (tylko odczyt): ostatnie wiadomości zawierające któreś słowo."""
        self.need("whatsapp.obserwacja")
        Wm = _w()
        path = Wm.home() / "obserwacja.sqlite3"
        words = [w for w in words if len(w) >= 3][:8]
        if not path.exists() or not words:
            return []
        since = int(time.time() - days * 86400)
        out = []
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            q = " OR ".join("lower(text) LIKE ?" for _ in words)
            params = [f"%{w.lower()[:max(4, len(w) - 3)] if len(w) > 5 else w.lower()}%" for w in words]
            for r in con.execute(f"SELECT chat_name, sender_name, from_me, ts, text FROM wmsg WHERE ts>=? AND is_group=0 "
                                 f"AND text<>'' AND ({q}) ORDER BY ts DESC LIMIT ?", [since, *params, limit]):
                out.append({"chat": r["chat_name"] or "", "who": "Ty" if r["from_me"] else (r["sender_name"] or r["chat_name"] or ""),
                            "when": dt.datetime.fromtimestamp(r["ts"], Wm.S.TZ), "text": r["text"][:300]})
        except sqlite3.Error:
            pass
        finally:
            con.close()
        return out

    def people_context(self, text):
        self.need("whatsapp.obserwacja")
        with contextlib.suppress(Exception):
            import whatsapp_watch as WW
            return WW.people_context(text, limit=1500)
        return ""

    # ---------------------------------------------------------------- zapis
    def add_task(self, text):
        self.need("zadania.zapis")
        Wm = _w()
        with Wm.as_user(Wm.owner_user()):
            if self._con is not None:
                return Wm.add_task(self._con, text)
            with contextlib.closing(Wm.db()) as c:
                return Wm.add_task(c, text)

    # ---------------------------------------------------------------- sekrety (pęk kluczy macOS)
    def secret(self, name):
        if sys.platform != "darwin":
            return None
        r = subprocess.run(["security", "find-generic-password", "-s", f"sebastian-{self.id}", "-a", name, "-w"],
                           capture_output=True, text=True)
        return r.stdout.strip() or None if r.returncode == 0 else None

    def set_secret(self, name, value):
        if sys.platform != "darwin":
            raise AddonError("Hasła zapisuję tylko w pęku kluczy macOS.")
        subprocess.run(["security", "add-generic-password", "-U", "-s", f"sebastian-{self.id}", "-a", name, "-w", value],
                       check=True, capture_output=True)


# ================================================================ polecenia: python sebastian.py dodatki / dodatek …

def cmd_list(action="lista", aid=None):
    if action in ("wlacz", "włącz", "wylacz", "wyłącz"):
        if not aid:
            print("Podaj nazwę dodatku, np.: python sebastian.py dodatki wlacz przypominacz")
            return 1
        try:
            set_enabled(aid, action.startswith("wl") or action.startswith("wł"))
        except AddonError as e:
            print(e)
            return 1
        print(f"{aid}: {'włączony' if action.startswith(('wl', 'wł')) else 'wyłączony'}. "
              "Zadziała po przeładowaniu: python sebastian.py wa-start")
        return 0
    found = discover()
    if not found:
        print("Brak dodatków.")
        return 0
    for info in found.values():
        m = info["manifest"]
        state = "⚠ błędy: " + "; ".join(info["problems"]) if info["problems"] else ("✓ włączony" if is_enabled(info) else "· wyłączony")
        print(f"{info['id']} {m.get('wersja', '')} — {m.get('nazwa', '')} [{state}]" + ("" if info["builtin"] else " (Twój)"))
        if m.get("opis"):
            print(f"    {m['opis']}")
        for p in m.get("uprawnienia", []):
            print(f"    • {PERMISSIONS.get(p, p)}")
        for c in m.get("polecenia", []):
            print(f"    python sebastian.py dodatek {info['id']} {c['nazwa']}  — {c.get('opis', '')}")
    return 0


def cmd_run(aid, command="", args=()):
    info = discover().get(aid)
    if not info:
        print(f"Nie znam dodatku „{aid}”. Lista: python sebastian.py dodatki")
        return 1
    if info["problems"]:
        print("Ten dodatek ma błędy: " + "; ".join(info["problems"]))
        return 1
    mod, ctx = load(info)
    commands = getattr(mod, "COMMANDS", {})
    if not command or command not in commands:
        print(f"Polecenia dodatku {aid}:")
        for c in info["manifest"].get("polecenia", []):
            print(f"  python sebastian.py dodatek {aid} {c['nazwa']}  — {c.get('opis', '')}")
        return 0 if not command else 1
    if not is_enabled(info):
        print(f"(Dodatek {aid} jest wyłączony — usługa WhatsApp go nie używa. Włączysz: python sebastian.py dodatki wlacz {aid})")
    out = commands[command](ctx, list(args))
    return out if isinstance(out, int) else 0
