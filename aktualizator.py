"""Sebastian 2.21 — aktualizacja jednym plikiem, bez terminala.

Aga (albo Andrzej) wrzuca w Centrum dowodzenia plik Sebastian_aktualizacja_X.py. Ten moduł:
  1. sprawdza, czy to naprawdę aktualizacja Sebastiana i czy pasuje do zainstalowanej wersji,
  2. uruchamia ją w folderze Sebastiana (tak jak w terminalu: python Sebastian_aktualizacja_X.py),
  3. zapisuje zmiany w git i wysyła je na GitHuba (git push),
  4. na bieżąco zapisuje postęp w data/aktualizacje/stan.json — strona Centrum go pokazuje.

Działa jako osobny proces (nie zależy od panelu, który aktualizacja restartuje):
    python aktualizator.py uruchom data/aktualizacje/<plik>.py
"""
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 60 * 1024 * 1024
MARKERS = ("VERSION_FROM, VERSION_TO = ", "P = json.loads(base64.b64decode(", "def main():")


def state_dir(root=ROOT):
    d = Path(os.environ.get("SEBASTIAN_DATA") or (root / "data")).expanduser() / "aktualizacje"
    d.mkdir(parents=True, exist_ok=True)
    return d


def current_version(root=ROOT):
    m = re.search(r'HOST_VERSION = "([^"]+)"', (root / "dodatki_host.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def inspect(data, current):
    """Czy plik to aktualizacja Sebastiana i czy pasuje. Zwraca (True, info) albo (False, komunikat dla Agi)."""
    if len(data) > MAX_BYTES:
        return False, "Ten plik jest za duży jak na aktualizację Sebastiana."
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False, "To nie jest plik aktualizacji Sebastiana (zły format). Pobierz z czatu plik Sebastian_aktualizacja_….py."
    if not text.lstrip().startswith(("#!/usr/bin/env python3", '"""Sebastian')) or not all(m in text for m in MARKERS):
        return False, "To nie wygląda na aktualizację Sebastiana. Wrzuć plik o nazwie Sebastian_aktualizacja_….py z czatu."
    m = re.search(r'VERSION_FROM, VERSION_TO = "([^"]*)", "([^"]+)"', text)
    if not m:
        return False, "Nie umiem odczytać numeru wersji z tego pliku."
    froms, to = [v.strip() for v in m.group(1).split(",") if v.strip()], m.group(2)
    title = re.search(r'"""Sebastian [^\n]*?—\s*([^\n]*)', text)
    info = {"z": froms, "do": to, "tytul": (title.group(1).replace('"""', "").strip().rstrip(".") if title else ""), "teraz": current}
    if to == current:
        return False, f"Sebastian ma już wersję {to} — ta aktualizacja jest zainstalowana."
    if current not in froms:
        if froms and vkey(to) < vkey(current):
            return False, f"To starsza aktualizacja ({to}), a Sebastian ma już {current}. Nic nie trzeba robić."
        return False, (f"Ta aktualizacja jest dla wersji {' / '.join(froms[:4])}, a Sebastian ma {current}. "
                       f"Napisz w czacie: „Sebastian ma wersję {current}” — dostaniesz pasujący plik.")
    return True, info


def save_state(sd, **kw):
    path = sd / "stan.json"
    try:
        st = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    st.update(kw, czas=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return st


def load_state(sd):
    try:
        return json.loads((sd / "stan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def busy(sd, max_age=1800):
    st = load_state(sd)
    if st.get("stan") != "trwa":
        return False
    try:
        start = dt.datetime.strptime(st.get("start", ""), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return (dt.datetime.now() - start).total_seconds() < max_age          # zawieszona dłużej niż 30 min — można od nowa


def git_command(output, version, title):
    """Polecenie git z końca aktualizacji (tam jest dokładna lista plików) — albo bezpieczne domyślne."""
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("git add ") and "git commit" in line:
            return re.sub(r"\s*&&\s*git status --short", "", line)
    msg = f"Sebastian {version}: {title}".strip(": ")
    return f"git add -u && git add dodatki docs && git commit -m {shlex.quote(msg)} && git push"


def env_for(root):
    env = dict(os.environ)
    env["VIRTUAL_ENV"] = env.get("VIRTUAL_ENV") or sys.prefix
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
                                   env.get("PATH", "")])
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("GIT_TERMINAL_PROMPT", "0")                         # git nie może czekać na hasło, którego nikt nie wpisze
    return env


def push(root, sd, command=None):
    """Zapis na GitHubie. Zwraca (ok, opis)."""
    env = env_for(root)
    command = command or "git push"
    r = subprocess.run(["/bin/sh", "-c", command], cwd=root, capture_output=True, text=True, timeout=300, env=env,
                       stdin=subprocess.DEVNULL)
    out = (r.stdout + "\n" + r.stderr).strip()
    if r.returncode != 0 and "nothing to commit" in out and "git push" in command:
        r = subprocess.run(["git", "push"], cwd=root, capture_output=True, text=True, timeout=300, env=env, stdin=subprocess.DEVNULL)
        out = (r.stdout + "\n" + r.stderr).strip()
    if r.returncode == 0:
        return True, "zmiany zapisane na GitHubie"
    return False, "\n".join(out.splitlines()[-6:])


def run(file, root=ROOT, python=None, sd=None, do_git=True, restart=True):
    """Cała aktualizacja z zapisem postępu. Zwraca końcowy stan."""
    sd = sd or state_dir(root)
    file = Path(file)
    ok, info = inspect(file.read_bytes(), current_version(root))
    if not ok:
        return save_state(sd, stan="blad", komunikat=info, linie=[], koniec=True)
    st = save_state(sd, stan="trwa", plik=file.name, z=current_version(root), do=info["do"], tytul=info["tytul"], linie=[],
                    krok="Start", github="", komunikat="", start=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), koniec=False)
    lines = []
    proc = subprocess.Popen([python or sys.executable, str(file)], cwd=root, env=env_for(root), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    last = 0.0
    for line in proc.stdout:
        line = line.rstrip("\n")
        lines.append(line)
        step = re.match(r"\s*(\d/\d [^…]*)", line)
        if step:
            st["krok"] = step.group(1).strip()
        if time.time() - last > 0.7 or step:
            save_state(sd, linie=lines[-400:], krok=st["krok"])
            last = time.time()
    code = proc.wait()
    output = "\n".join(lines)
    save_state(sd, linie=lines[-400:])
    if code != 0 or f"Gotowe: Sebastian {info['do']}" not in output:
        msg = next((l.strip() for l in reversed(lines) if l.strip()), "Aktualizacja przerwała się bez komunikatu.")
        final = save_state(sd, stan="blad", krok="Przerwane", koniec=True,
                           komunikat="Aktualizacja się nie udała, a Sebastian działa dalej na poprzedniej wersji. " + msg[:600])
        history(sd, final)
        return final
    github = "pominięte (test)"
    if do_git:
        save_state(sd, krok="Zapis na GitHubie")
        good, github = push(root, sd, git_command(output, info["do"], info["tytul"]))
        if not good:
            github = "nie udało się wysłać na GitHuba — Sebastian jest zaktualizowany, wyślemy później: " + github
    final = save_state(sd, stan="ok", krok="Gotowe", koniec=True, github=github, komunikat="")
    history(sd, final)
    if restart and sys.platform == "darwin":                              # Centrum Andrzeja na nowej wersji (jeśli jest usługą)
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/pl.sebastian.centrum"], capture_output=True, timeout=30)
    return final


def history(sd, st):
    path = sd / "historia.json"
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        items = []
    items.insert(0, {k: st.get(k) for k in ("czas", "stan", "z", "do", "tytul", "github", "plik")})
    path.write_text(json.dumps(items[:50], ensure_ascii=False, indent=1), encoding="utf-8")


def start_detached(file, root=ROOT, python=None, sd=None):
    """Uruchamia aktualizację jako niezależny proces — przeżyje restart panelu, z którego ją włączono."""
    sd = sd or state_dir(root)
    save_state(sd, stan="trwa", krok="Start", linie=[], koniec=False, komunikat="", github="",
               start=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log = open(sd / "ostatnia.log", "w", encoding="utf-8")
    subprocess.Popen([python or sys.executable, str(root / "aktualizator.py"), "uruchom", str(file), str(sd)], cwd=root, env=env_for(root),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)


def main(argv):
    if len(argv) >= 2 and argv[0] == "uruchom":
        st = run(argv[1], sd=Path(argv[2]) if len(argv) > 2 else None)
        print(json.dumps(st, ensure_ascii=False)[:2000])
        return 0 if st.get("stan") == "ok" else 1
    if argv[:1] == ["github"]:
        good, msg = push(ROOT, state_dir())
        print(msg)
        return 0 if good else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
