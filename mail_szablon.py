"""Wspólny wygląd maili Sebastiana (2.14.4).

Każdy mail, który Sebastian wysyła od siebie (powiadomienia, zaproszenia, przypomnienia, raporty, owca), składa się tutaj:
spokojny, minimalistyczny układ jak w dobrych mailach transakcyjnych — jasne tło, jedna biała karta, mała sygnatura u góry,
wyraźny tytuł, krótki tekst, szczegóły w cienkich wierszach, najwyżej dwa przyciski, cicha stopka.

Zasady (dla przyszłych maili):
  * treść od razu do rzeczy, 1–3 krótkie akapity; szczegóły w `rows`, nie w akapitach;
  * jeden przycisk główny (czarny), ewentualnie jeden drugorzędny (obrys);
  * bez emoji w tytułach i bez wykrzykników w nadmiarze; temat maila krótki i rzeczowy;
  * zawsze wersja tekstowa obok HTML (robi to wysyłka) — HTML tylko ją ubiera.
Maile pisane w imieniu Agi do pracodawców NIE używają szablonu: rekruterzy dostają zwykły, osobisty tekst.

Układ na tabelach i stylach w linii — tak, żeby wyglądał tak samo w Gmailu, Apple Mail i Outlooku.
"""
import html as _h
import re

FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif"
BG = "#f4f4f2"            # tło: ciepła, bardzo jasna szarość
CARD = "#ffffff"
LINE = "#e9e9e6"          # cienkie linie
INK = "#111111"           # tytuły i przyciski
TEXT = "#2c2c2e"          # tekst
SOFT = "#86868b"          # podpisy, stopka
BRAND = "Sebastian"
TAGLINE = "Asystent Krakowa inPartners"


def esc(s):
    return _h.escape(str(s if s is not None else ""), quote=True)


def text_to_html(text):
    """Zwykły tekst → akapity HTML (z linkami), do maili pisanych jak list."""
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        p = esc(para.strip()).replace("\n", "<br>")
        p = re.sub(r"(https?://[^\s<]+)", lambda m: f'<a href="{m.group(1)}" style="color:{INK};text-decoration:underline">{m.group(1)}</a>', p)
        if p:
            out.append(f'<p style="margin:0 0 14px">{p}</p>')
    return "".join(out)


def button(label, href, primary=True):
    if primary:
        style = f"background:{INK};color:#ffffff;border:1px solid {INK}"
    else:
        style = f"background:#ffffff;color:{INK};border:1px solid #d6d6d2"
    return (f'<a href="{esc(href)}" style="display:inline-block;{style};text-decoration:none;font-weight:600;font-size:15px;'
            f'line-height:20px;padding:12px 22px;border-radius:10px;margin:0 8px 8px 0">{esc(label)}</a>')


def details(rows):
    """Szczegóły: etykieta nad wartością, rozdzielone cienką linią."""
    rows = [(k, v) for k, v in rows if str(v or "").strip()]
    if not rows:
        return ""
    cells = "".join(
        f'<tr><td style="padding:12px 0;border-top:1px solid {LINE}">'
        f'<div style="font-size:11px;line-height:16px;letter-spacing:.08em;text-transform:uppercase;color:{SOFT}">{esc(k)}</div>'
        f'<div style="font-size:15px;line-height:22px;color:{INK};margin-top:2px">{esc(v)}</div></td></tr>' for k, v in rows)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:6px 0 22px;border-bottom:1px solid {LINE}">{cells}</table>')


def render(title, intro="", rows=(), buttons=(), outro="", preheader="", image_cid="", image_alt="", brand=BRAND,
           tagline=TAGLINE, footer="", body_html="", subtitle=""):
    """Cały mail HTML.
    intro/outro: HTML (zaufany, z kodu) albo zwykły tekst — zwykły tekst warto przepuścić przez text_to_html;
    rows: [(etykieta, wartość)]; buttons: [(etykieta, adres)] — pierwszy główny, kolejne drugorzędne;
    body_html: dowolny dodatkowy blok (np. statystyki owcy) między wstępem a szczegółami."""
    btns = "".join(button(t, u, i == 0) for i, (t, u) in enumerate(buttons or []))
    img = (f'<tr><td style="padding:0 0 18px"><img src="cid:{esc(image_cid)}" width="96" height="96" alt="{esc(image_alt)}" '
           f'style="display:block;border:0;width:96px;height:96px"></td></tr>') if image_cid else ""
    sub = f'<div style="font-size:16px;line-height:24px;color:{SOFT};margin-top:6px">{esc(subtitle)}</div>' if subtitle else ""
    pre = (f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{esc(preheader)}</div>'
           if preheader else "")
    foot = footer or f"{esc(brand)} · {esc(tagline)}<br>Wiadomość wysłana automatycznie."
    return f'''<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"><title>{esc(title)}</title></head>
<body style="margin:0;padding:0;background:{BG};-webkit-font-smoothing:antialiased">{pre}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:36px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:580px">
<tr><td style="padding:0 6px 14px;font-family:{FONT};font-size:11px;line-height:16px;letter-spacing:.16em;text-transform:uppercase;color:{SOFT}">{esc(brand)}</td></tr>
<tr><td style="background:{CARD};border:1px solid {LINE};border-radius:14px;padding:40px 40px 32px;font-family:{FONT}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{img}
<tr><td style="font-size:24px;line-height:31px;font-weight:600;letter-spacing:-0.01em;color:{INK}">{esc(title)}{sub}</td></tr>
<tr><td style="padding-top:18px;font-size:15px;line-height:24px;color:{TEXT}">{intro}</td></tr>
{f'<tr><td style="padding-top:4px">{body_html}</td></tr>' if body_html else ''}
{f'<tr><td>{details(rows)}</td></tr>' if rows else ''}
{f'<tr><td style="padding-top:6px">{btns}</td></tr>' if btns else ''}
{f'<tr><td style="padding-top:16px;font-size:13px;line-height:20px;color:{SOFT}">{outro}</td></tr>' if outro else ''}
</table></td></tr>
<tr><td style="padding:18px 6px 0;font-family:{FONT};font-size:12px;line-height:18px;color:{SOFT}">{foot}</td></tr>
</table></td></tr></table></body></html>'''


def letter(text, signature="Sebastian", brand=BRAND, tagline=TAGLINE, title=""):
    """Mail-rozmowa (odpowiedź, przypomnienie): sam tekst w karcie i podpis — bez przycisków i tabel."""
    body = text_to_html(text) + f'<p style="margin:18px 0 0;color:{SOFT}">— {esc(signature)}</p>'
    if title:
        return render(title, body, brand=brand, tagline=tagline)
    html = render("", body, brand=brand, tagline=tagline)
    return html.replace(f'<tr><td style="font-size:24px;line-height:31px;font-weight:600;letter-spacing:-0.01em;color:{INK}"></td></tr>\n'
                        f'<tr><td style="padding-top:18px;', '<tr><td style="padding-top:0;')
