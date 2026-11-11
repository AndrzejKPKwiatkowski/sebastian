"""Rekrutacja — formularze (część C).

Automatycznie wysyłam tylko tam, gdzie pracodawca udostępnia do tego publiczny interfejs: tablice Recruitee
(POST /api/offers/<slug>/candidates — ten sam, z którego korzysta ich strona kariery). Pozostałe formularze (systemy
rekrutacyjne z logowaniem, CAPTCHA, portale) dostają „zestaw jednego kliknięcia”: link, gotowe pliki i odpowiedzi do
skopiowania w panelu, a po wysłaniu Aga klika „Wysłałam”.
"""
import json, re
from urllib.parse import urlparse

from . import rdzen as R

CONSENT = ("rodo", "gdpr", "zgod", "consent", "przetwarzan", "privacy", "prywatnos", "regulamin")


def channel(app):
    """Jak wysłać: {"typ": "mail"|"recruitee"|"formularz"|"brak", ...}."""
    with_k = {}
    try:
        with_k = json.loads(app.get("kanal") or "{}") or {}
    except ValueError:
        pass
    if R.EMAIL_OK.match(app.get("email") or ""):
        return {"typ": "mail"}
    if with_k.get("typ") == "recruitee" and with_k.get("slug"):
        return with_k
    u = urlparse(app.get("url") or "")
    m = re.match(r"^/o/([^/?#]+)", u.path or "")
    if (u.hostname or "").endswith(".recruitee.com") and m:
        return {"typ": "recruitee", "host": u.hostname, "slug": m.group(1)}
    if app.get("url"):
        return {"typ": "formularz"}
    return {"typ": "brak"}


def recruitee_questions(host, slug, get=None):
    import requests
    get = get or requests.get
    r = get(f"https://{host}/api/offers/{slug}", timeout=25)
    r.raise_for_status()
    return (r.json().get("offer") or {}).get("open_questions") or []


def recruitee_apply(f, app, cv_path, letter_path, letter_text, post=None, get=None):
    """(True, "") albo (False, powód). Wysyła tylko, gdy wszystkie wymagane pytania da się uczciwie wypełnić."""
    import requests
    post = post or requests.post
    k = channel(app)
    host, slug = k.get("host"), k.get("slug")
    if not host or not slug:
        return False, "Brak danych tablicy Recruitee."
    try:
        questions = recruitee_questions(host, slug, get=get)
    except Exception as e:
        return False, f"Nie udało się odczytać formularza ({type(e).__name__})."
    data = {"candidate[name]": R.full_name(f), "candidate[email]": f["osoba"].get("email", ""),
            "candidate[phone]": f["osoba"].get("telefon", ""), "candidate[cover_letter]": letter_text}
    n = 0
    for q in questions:
        kind, body = str(q.get("kind", "")), R.plain(q.get("body") or q.get("question") or "")
        if kind in ("legal", "boolean") and any(w in body for w in CONSENT):
            data[f"candidate[open_question_answers_attributes][{n}][open_question_id]"] = str(q.get("id"))
            data[f"candidate[open_question_answers_attributes][{n}][flag]"] = "true"
            n += 1
        elif q.get("required"):
            return False, f"Formularz ma wymagane pytanie, na które nie odpowiem za Ciebie: „{(q.get('body') or '')[:120]}”."
    files = {"candidate[cv]": (cv_path.name, cv_path.read_bytes(), "application/pdf")}
    try:
        r = post(f"https://{host}/api/offers/{slug}/candidates?async=true", data=data, files=files, timeout=60)
    except Exception as e:
        return False, f"Nie udało się połączyć z formularzem ({type(e).__name__})."
    if r.status_code in (200, 201):
        return True, ""
    if r.status_code in (401, 403):
        return False, "Ta firma wyłączyła wysyłanie przez interfejs — wyślij przez formularz na stronie."
    return False, f"Formularz odrzucił zgłoszenie (kod {r.status_code}). Wyślij przez stronę ogłoszenia."


def kit(f, app):
    """Pola do skopiowania w panelu (formularz na stronie pracodawcy)."""
    o, w = f["osoba"], f["warunki"]
    fields = [("Imię", o.get("imie", "")), ("Nazwisko", o.get("nazwisko", "")), ("E-mail", o.get("email", "")),
              ("Telefon", o.get("telefon", "")), ("Miasto", re.sub(r"^\d{2}-\d{3}\s*", "", o.get("miasto", ""))),
              ("LinkedIn", o.get("linkedin", "")),
              ("Oczekiwania finansowe", f"od {w['min_netto']} zł netto miesięcznie" if w.get("min_netto") else ""),
              ("Dostępność", w.get("dostepnosc", "")), ("Forma zatrudnienia", w.get("umowa", "")),
              ("Prawo jazdy", "kat. B" if f.get("prawo_jazdy") else "")]
    fields += [(q, a) for q, a in (f.get("odpowiedzi") or {}).items()]
    return [(k, v) for k, v in fields if v]
