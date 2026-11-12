"""Rekrutacja — poczta: sprawdzenie logowania i wysyłka z załącznikami (Gmail, hasło aplikacji)."""
import contextlib, email, email.policy, imaplib, re, smtplib, ssl
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

HOSTS = {"gmail.com": ("imap.gmail.com", "smtp.gmail.com", 587), "googlemail.com": ("imap.gmail.com", "smtp.gmail.com", 587)}


def hosts(address):
    return HOSTS.get(address.rsplit("@", 1)[-1].lower())


def clean_password(pwd):
    return "".join(str(pwd or "").split())          # Google pokazuje hasło aplikacji w czterech grupach ze spacjami


def test_login(address, pwd):
    """(True, "") albo (False, komunikat po polsku). Tylko logowanie — niczego nie czyta i nie wysyła."""
    h = hosts(address)
    if not h:
        return False, "Na razie obsługuję skrzynki Gmail (adres kończący się na @gmail.com)."
    pwd = clean_password(pwd)
    if len(pwd) != 16:
        return False, "Hasło aplikacji Google ma 16 liter (bez spacji). To nie jest zwykłe hasło do konta."
    try:
        box = imaplib.IMAP4_SSL(h[0], timeout=25)
        try:
            box.login(address, pwd)
        finally:
            with contextlib.suppress(Exception):
                box.logout()
        with smtplib.SMTP(h[1], h[2], timeout=25) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(address, pwd)
    except (imaplib.IMAP4.error, smtplib.SMTPAuthenticationError):
        return False, ("Google odrzucił logowanie. Sprawdź, czy to hasło aplikacji (nie hasło do konta), "
                       "czy weryfikacja dwuetapowa jest włączona i czy adres jest wpisany bez literówki.")
    except Exception as e:
        return False, f"Nie udało się połączyć z Gmailem ({type(e).__name__}). Sprawdź internet i spróbuj ponownie."
    return True, ""


MARK = "X-Sebastian-Rekrutacja"


class NotSent(RuntimeError):
    """Wiadomość na pewno nie wyszła (połączenie, logowanie) — można spokojnie ponowić później."""


class AuthFailed(NotSent):
    """Gmail odrzucił hasło — ponawianie nic nie da, trzeba podłączyć skrzynkę ponownie."""


class Uncertain(RuntimeError):
    """Błąd w trakcie albo po przekazaniu wiadomości — mogła wyjść, nie ponawiam automatycznie."""


def send(address, pwd, to, subject, body, attachments=(), name="", reply_to="", in_reply_to="", references=""):
    """Wysyła jedną wiadomość; zwraca Message-ID. Gmail sam odkłada kopię do „Wysłane”.
    Błędy: NotSent / AuthFailed (nic nie wyszło) albo Uncertain (mogło wyjść)."""
    h = hosts(address)
    if not h:
        raise RuntimeError("Nieobsługiwana skrzynka nadawcy.")
    msg = EmailMessage()
    msg["From"] = formataddr((name, address)) if name else address
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=address.rsplit("@", 1)[-1])
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = (references + " " + in_reply_to).strip()
    msg[MARK] = "1"                              # po tym znaczniku nie czytam własnych wiadomości jako odpowiedzi
    msg.set_content(body)
    for path in attachments:
        path = Path(path)
        msg.add_attachment(path.read_bytes(), maintype="application", subtype="pdf", filename=path.name)
    try:
        s = smtplib.SMTP(h[1], h[2], timeout=60)
        s.starttls(context=ssl.create_default_context())
        s.login(address, clean_password(pwd))
    except smtplib.SMTPAuthenticationError as e:
        raise AuthFailed("Gmail odrzucił hasło aplikacji.") from e
    except Exception as e:
        raise NotSent(f"Brak połączenia z Gmailem ({type(e).__name__}).") from e
    try:
        refused = s.send_message(msg)
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused) as e:
        with contextlib.suppress(Exception):
            s.quit()
        raise RuntimeError(f"Gmail odrzucił adres odbiorcy ({to}).") from e
    except Exception as e:
        raise Uncertain(f"Połączenie przerwało się w trakcie wysyłki ({type(e).__name__}).") from e
    with contextlib.suppress(Exception):
        s.quit()                                     # błąd przy zamykaniu nie zmienia tego, że Gmail przyjął wiadomość
    if refused:
        raise RuntimeError(f"Gmail odrzucił adres odbiorcy ({to}).")
    return msg["Message-ID"]


# ================================================================ odbiór (tylko odczyt: readonly + BODY.PEEK — nic nie oznaczam jako przeczytane)

def _dec(value):
    with contextlib.suppress(Exception):
        return str(make_header(decode_header(value or "")))
    return str(value or "")


def clean_text(text):
    """Czytelna treść: encje HTML (&nbsp; itd.) zamienione, bez pustych ciągów linii i spacji."""
    import html as _h
    t = _h.unescape(_h.unescape(str(text or ""))).replace("\xa0", " ").replace("\u200b", "").replace("\r", "")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in t.split("\n")]
    t = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def links(msg, limit=8):
    """Przyciski i linki z treści HTML: [{"tekst", "url"}] — najpierw te, które wyglądają na działanie (potwierdź, aplikacja)."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.out, self.href, self.buf = [], None, []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.href, self.buf = dict(attrs).get("href"), []

        def handle_data(self, d):
            if self.href is not None:
                self.buf.append(d)

        def handle_endtag(self, tag):
            if tag == "a" and self.href:
                label = clean_text(" ".join(self.buf)).replace("\n", " ")[:80]
                if re.match(r"^https?://", self.href) and label and not re.search(r"(?i)wypisz|unsubscribe|polityk|privacy|regulamin|facebook|linkedin\.com/(company|in)|instagram", label + " " + self.href):
                    self.out.append({"tekst": label, "url": self.href[:1500]})
            self.href = None if tag == "a" else self.href

    found = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_type() == "text/html" and not part.get_filename():
            with contextlib.suppress(Exception):
                p = P()
                p.feed(part.get_content())
                found += p.out
    uniq = list({x["url"]: x for x in found}.values())
    act = re.compile(r"(?i)potwierd|aplikac|tak|moja|zgod|akceptuj|zobacz|przejd|kliknij|konto|odpowiedz|formularz|test|zadanie|termin|umów")
    return (sorted(uniq, key=lambda x: 0 if act.search(x["tekst"]) else 1))[:limit]


def _text(msg, limit=12000):
    parts = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        with contextlib.suppress(Exception):
            body = part.get_content()
            if ctype == "text/html":
                from .oferty import to_text
                body = to_text(body)[0]
            parts.append((ctype, body))
    plain = [b for t, b in parts if t == "text/plain"]
    text = (plain or [b for _, b in parts] or [""])[0]
    text = re.split(r"\n(?:-{2,}\s*Original Message|W dniu .{5,80} napisał|On .{5,80} wrote:|Od: .{3,80}\nWysłano:)", text)[0]
    text = "\n".join(l for l in text.splitlines() if not l.startswith(">"))
    return clean_text(text)[:limit]


def fetch_new(address, pwd, after_uid=0, since_days=30, limit=200):
    """Nowe wiadomości ze skrzynki odbiorczej: [{uid, message_id, od, od_nazwa, temat, data, in_reply_to, references, tresc}]."""
    h = hosts(address)
    if not h:
        return []
    out = []
    box = imaplib.IMAP4_SSL(h[0], timeout=40)
    try:
        box.login(address, clean_password(pwd))
        box.select("INBOX", readonly=True)
        if after_uid:
            typ, data = box.uid("search", None, f"UID {int(after_uid) + 1}:*")
        else:
            import datetime as _dt
            since = (_dt.date.today() - _dt.timedelta(days=since_days)).strftime("%d-%b-%Y")
            typ, data = box.uid("search", None, "SINCE", since)
        uids = sorted(int(x) for x in (data[0] or b"").split() if int(x) > int(after_uid or 0))[:limit]   # od najstarszych
        for uid in uids:
            typ, got = box.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((x[1] for x in got if isinstance(x, tuple)), None)
            if not raw:
                continue
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            name, addr = parseaddr(_dec(msg.get("From", "")))
            date = ""
            with contextlib.suppress(Exception):
                date = parsedate_to_datetime(msg.get("Date")).isoformat(timespec="seconds")
            out.append({"uid": uid, "message_id": (msg.get("Message-ID") or "").strip(), "od": addr.lower(), "od_nazwa": name,
                        "temat": _dec(msg.get("Subject", ""))[:300], "data": date, "in_reply_to": (msg.get("In-Reply-To") or "").strip(),
                        "references": " ".join((msg.get("References") or "").split()), "nasza": bool(msg.get("X-Sebastian-Rekrutacja")),
                        "auto": bool(msg.get("Auto-Submitted", "no") != "no"
                        or msg.get("X-Autoreply") or msg.get("X-Autorespond") or "auto-reply" in (msg.get("Precedence") or "")),
                        "tresc": _text(msg), "linki": links(msg)})
    finally:
        with contextlib.suppress(Exception):
            box.logout()
    return out
