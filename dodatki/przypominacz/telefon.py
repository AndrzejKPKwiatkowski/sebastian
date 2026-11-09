"""Prawdziwe dzwonienie przez Twilio (opcjonalne).

WhatsApp nie pozwala połączonemu urządzeniu dzwonić, dlatego „telefon” domyślnie jest głosówką. Jeśli chcesz,
żeby Twój telefon naprawdę zadzwonił, a Sebastian powiedział wszystko głosem — załóż konto w Twilio, kup numer
i wpisz dane poleceniem:  python sebastian.py dodatek przypominacz telefon
Token (hasło API) trafia wyłącznie do pęku kluczy macOS. Gdy połączenie się nie uda, idzie zwykła głosówka.
"""
import getpass
from xml.sax.saxutils import escape

import requests

API = "https://api.twilio.com/2010-04-01"


def _creds(ctx):
    s = ctx.settings()
    sid, frm = s.get("twilio_sid", ""), s.get("twilio_numer", "")
    token = ctx.secret("twilio_token")
    if not (sid and frm and token):
        raise RuntimeError("Twilio nie jest ustawione (python sebastian.py dodatek przypominacz telefon)")
    return sid, frm, token


def twiml(text, voice):
    say = f'<Say language="pl-PL" voice="{escape(voice)}">{escape(text)}</Say>'
    return f'<Response><Pause length="1"/>{say}<Pause length="2"/><Say language="pl-PL" voice="{escape(voice)}">Powtarzam.</Say>{say}</Response>'


def call(ctx, text):
    ctx.need("telefon")
    sid, frm, token = _creds(ctx)
    to = "+" + ctx.W.C.WA_OWNER_PHONE.lstrip("+")
    r = requests.post(f"{API}/Accounts/{sid}/Calls.json", auth=(sid, token), timeout=20,
                      data={"To": to, "From": frm, "Twiml": twiml(text[:1800], ctx.settings().get("twilio_glos") or "Polly.Jacek"),
                            "Timeout": 30, "MachineDetection": "Enable"})
    if r.status_code >= 300:
        raise RuntimeError(f"Twilio {r.status_code}: {r.text[:200]}")
    return r.json()["sid"]


def status(ctx, call_sid):
    """→ (stan, odebrane). Stany Twilio: queued, ringing, in-progress, completed, busy, no-answer, failed, canceled."""
    sid, _, token = _creds(ctx)
    r = requests.get(f"{API}/Accounts/{sid}/Calls/{call_sid}.json", auth=(sid, token), timeout=20)
    r.raise_for_status()
    d = r.json()
    state = d.get("status", "nieznany")
    by = (d.get("answered_by") or "").lower()
    answered = state in ("completed", "in-progress") and int(d.get("duration") or 0) > 0 and not by.startswith("machine")
    return state, answered


def setup(ctx, args):
    print("Prawdziwe dzwonienie przez Twilio — opcjonalne (domyślnie Sebastian wysyła głosówkę).")
    print("Potrzebujesz: konta na twilio.com, numeru telefonu kupionego w Twilio (kilka $ miesięcznie)")
    print("i danych z Twilio Console: Account SID (zaczyna się od AC) i Auth Token.")
    print("Konto próbne dzwoni tylko na zweryfikowane numery i dodaje na początku komunikat po angielsku.\n")
    if args and args[0] in ("wylacz", "wyłącz", "off"):
        ctx.set_setting("dzwonek", "glosowka")
        print("Wyłączone — od teraz głosówki.")
        return 0
    if args and args[0] == "test":
        try:
            sid = call(ctx, "Cześć, tu Sebastian. To próbne połączenie. Działa!")
            print(f"Dzwonię… (połączenie {sid})")
            return 0
        except Exception as e:
            print(f"Nie udało się: {e}")
            return 1
    try:
        sid = input("Account SID (AC…): ").strip()
        frm = input("Numer Twilio, z którego Sebastian dzwoni (np. +48…): ").strip().replace(" ", "")
        token = getpass.getpass("Auth Token (nie wyświetla się): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nPrzerwane — nic nie zmieniono.")
        return 1
    if not (sid.startswith("AC") and frm.startswith("+") and token):
        print("Coś się nie zgadza (SID zaczyna się od AC, numer od +). Nic nie zmieniono.")
        return 1
    r = requests.get(f"{API}/Accounts/{sid}.json", auth=(sid, token), timeout=20)
    if r.status_code != 200:
        print(f"Twilio nie przyjęło danych ({r.status_code}). Nic nie zmieniono.")
        return 1
    ctx.set_secret("twilio_token", token)
    ctx.set_setting("twilio_sid", sid)
    ctx.set_setting("twilio_numer", frm)
    ctx.set_setting("dzwonek", "telefon")
    print("✓ Zapisane (token w pęku kluczy macOS). Od teraz wieczorny „telefon” to prawdziwe połączenie.")
    print("Próba: python sebastian.py dodatek przypominacz telefon test")
    print("Powrót do głosówek: python sebastian.py dodatek przypominacz telefon wylacz")
    return 0
