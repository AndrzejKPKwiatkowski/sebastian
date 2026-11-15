"""Sebastian 2.15 — Centrum dowodzenia: jeden ekran z kafelkami do paneli i terminala.

Działa lokalnie na 127.0.0.1:8800; z zewnątrz (tylko Twój laptop, wg ACL) dostępne przez `tailscale serve`.
Adresy i nazwy sieci czytane są z data/centrum.json (plik lokalny, poza repozytorium).

    python centrum.py            # uruchomienie ręczne (zwykle robi to usługa pl.sebastian.centrum)
"""
import json, socket
from pathlib import Path

from flask import Flask, jsonify, Response

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "data" / "centrum.json"
PORT = 8800

app = Flask(__name__)


def cfg():
    try:
        return json.loads(CFG.read_text())
    except (OSError, ValueError):
        return {}


def up(port, host="127.0.0.1", timeout=0.6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def kafelki():
    c = cfg()
    return [
        {"id": "rekrutacja", "nazwa": "Rekrutacja", "opis": "Aplikacje o pracę dla Agi, CV, odpowiedzi",
         "url": c.get("rekrutacja", ""), "port": 8790},
        {"id": "sebastian", "nazwa": "Sebastian", "opis": "Panel główny: poczta, sprawy, nauka, WhatsApp",
         "url": c.get("sebastian", ""), "port": 8765},
        {"id": "gwaranci", "nazwa": "Gwaranci Feniks", "opis": "Spotkania gwaranckie zespołu",
         "url": c.get("gwaranci", ""), "port": 8791},
        {"id": "terminal", "nazwa": "Terminal", "opis": "Pełny zsh na tym Macu",
         "url": c.get("terminal", ""), "port": 7681},
    ]


@app.route("/api/status")
def api_status():
    lista = []
    for k in kafelki():
        lista.append({"id": k["id"], "up": up(k["port"])})
    return jsonify({"kafelki": lista, "ollama": up(11434)})


@app.route("/")
def index():
    return Response(STRONA.replace("__KAFELKI__", json.dumps(kafelki(), ensure_ascii=False)), mimetype="text/html")


STRONA = r"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Centrum dowodzenia</title>
<style>
  :root { --bg:#f5f5f7; --card:#ffffff; --txt:#1d1d1f; --sub:#6e6e73; --line:rgba(0,0,0,.08);
          --ok:#30d158; --bad:#ff453a; --acc:#0a84ff; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#000000; --card:#1c1c1e; --txt:#f5f5f7; --sub:#98989d; --line:rgba(255,255,255,.1); }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:15px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif;
         -webkit-font-smoothing:antialiased; }
  main { max-width:1040px; margin:0 auto; padding:56px 24px 72px; }
  header { margin-bottom:36px; }
  h1 { font-size:34px; font-weight:700; letter-spacing:-.02em; margin:0 0 6px; }
  .lead { color:var(--sub); margin:0; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:18px; }
  a.card { display:flex; flex-direction:column; gap:14px; padding:24px; border-radius:20px;
           background:var(--card); border:1px solid var(--line); color:inherit; text-decoration:none;
           box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.05);
           transition:transform .18s ease, box-shadow .18s ease; min-height:150px; }
  a.card:hover { transform:translateY(-2px); box-shadow:0 2px 4px rgba(0,0,0,.05),0 14px 32px rgba(0,0,0,.09); }
  .ikona { width:44px; height:44px; border-radius:12px; background:linear-gradient(135deg,#0a84ff,#64d2ff);
           display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; font-size:18px; }
  .nazwa { font-size:18px; font-weight:600; margin:0; }
  .opis { color:var(--sub); font-size:14px; margin:0; }
  .stan { margin-top:auto; display:flex; align-items:center; gap:8px; font-size:13px; color:var(--sub); }
  .kropka { width:8px; height:8px; border-radius:50%; background:#8e8e93; }
  .kropka.ok { background:var(--ok); } .kropka.bad { background:var(--bad); }
  .pasek { margin-top:40px; display:flex; gap:10px; flex-wrap:wrap; color:var(--sub); font-size:13px; }
  .pasek span { background:var(--card); border:1px solid var(--line); border-radius:999px; padding:6px 12px; }
  footer { margin-top:48px; color:var(--sub); font-size:12px; }
</style>
</head>
<body>
<main>
  <header>
    <h1>Centrum dowodzenia</h1>
    <p class="lead">Wszystkie aplikacje Sebastiana w jednym miejscu.</p>
  </header>
  <section class="grid" id="grid"></section>
  <div class="pasek">
    <span id="ollama">Model lokalny: sprawdzam…</span>
    <span id="czas"></span>
  </div>
  <footer>Dostęp tylko z zaufanych urządzeń (Tailscale). Odświeża się co 20 s.</footer>
</main>
<script>
const KAFELKI = __KAFELKI__;
const ZNAKI = { rekrutacja:"R", sebastian:"S", gwaranci:"G", terminal:">_" };

function render(stan) {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  KAFELKI.forEach(k => {
    const s = (stan.kafelki || []).find(x => x.id === k.id);
    const up = s ? s.up : false;
    const a = document.createElement("a");
    a.className = "card";
    a.href = k.url || "#";
    if (k.url) { a.target = "_blank"; a.rel = "noopener"; }
    a.innerHTML =
      '<div class="ikona">' + (ZNAKI[k.id] || "•") + '</div>' +
      '<p class="nazwa"></p><p class="opis"></p>' +
      '<div class="stan"><span class="kropka ' + (up ? "ok" : "bad") + '"></span>' +
      '<span>' + (up ? "działa" : "nie odpowiada") + '</span></div>';
    a.querySelector(".nazwa").textContent = k.nazwa;
    a.querySelector(".opis").textContent = k.opis;
    grid.appendChild(a);
  });
  document.getElementById("ollama").textContent =
    "Model lokalny: " + (stan.ollama ? "działa" : "nie odpowiada");
  document.getElementById("czas").textContent =
    "Aktualizacja: " + new Date().toLocaleTimeString("pl-PL", {hour:"2-digit", minute:"2-digit"});
}

function odswiez() {
  fetch("/api/status").then(r => r.json()).then(render).catch(() => {});
}
render({kafelki: []});
odswiez();
setInterval(odswiez, 20000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
