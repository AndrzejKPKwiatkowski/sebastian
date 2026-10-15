"""Sebastian 2.1 — czytanie załączników z poczty.

Załącznik jest pobierany z serwera dopiero wtedy, gdy model czyta wątek, do którego należy
(tylko odczyt, BODY.PEEK — nic się nie zmienia w skrzynce). Plik trafia na chwilę do
data/learner/tmp i jest od razu usuwany; zostaje sam wyciągnięty tekst.
Ten sam plik (np. umowa przesyłana w kolejnych odpowiedziach) jest czytany tylko raz.
"""
import contextlib, email, email.policy, hashlib, json, mimetypes, os, re, tempfile
from datetime import datetime
from pathlib import Path

import learner as L

DOC_EXT = (".pdf", ".docx", ".doc", ".rtf", ".odt", ".xlsx", ".pptx", ".txt", ".csv", ".md", ".html", ".htm")
IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")
MAX_STORED_CHARS = 200_000


def wanted(filename):
    name = (filename or "").lower()
    if name.endswith(DOC_EXT):
        return True
    return bool(L.C.OCR_IMAGES and name.endswith(IMG_EXT))


def names_have_attachments(names_json):
    """Sebastian zapisuje listę nazw plików — czy jest wśród nich coś do przeczytania?"""
    try:
        names = json.loads(names_json or "[]")
    except ValueError:
        return False
    return any(wanted(n) and not re.match(r"^image\d{3}\.(png|jpe?g|gif)$", n.lower()) for n in names)


def applies(m):
    """Czy dla tej wiadomości czytamy załączniki (ustawienia: włączone, zakres, od kiedy)."""
    if not L.C.ATTACHMENTS_ENABLED or m.get("source") not in ("email", None, ""):
        return False
    if m.get("scope") not in L.C.ATTACHMENTS_SCOPES:
        return False
    if L.C.ATTACHMENTS_SINCE:
        import learner_mail as LM
        if (LM.to_utc(m.get("date")) or "")[:10] < L.C.ATTACHMENTS_SINCE:
            return False
    return True


def has_attachments(m):
    if m.get("origin") == "seb":
        return names_have_attachments(m.get("attachments"))
    return m.get("att") == 1


class ImapPool:
    """Połączenia IMAP otwierane na czas czytania jednego wątku."""
    def __init__(self):
        self.conns, self.failed = {}, set()

    def get(self, account_id):
        if account_id in self.failed:
            return None
        if account_id not in self.conns:
            import learner_mail as LM
            acct = next((a for a in LM.accounts() if a["id"] == account_id), None)
            if acct is None:
                self.failed.add(account_id)
                return None
            try:
                self.conns[account_id] = L.S.connect(acct)
            except Exception as e:
                L.log.warning(f"  Załączniki: brak połączenia z kontem {account_id} ({type(e).__name__})")
                self.failed.add(account_id)
                return None
        return self.conns[account_id]

    def close(self):
        for m in self.conns.values():
            with contextlib.suppress(Exception):
                m.logout()
        self.conns.clear()


def msg_key(m):
    return f"{m['origin']}:{m['id']}"


def cached(con, key):
    return [(r["filename"], r["text"]) for r in con.execute(
        "SELECT ma.filename, a.text FROM message_attachments ma JOIN attachments a ON a.sha1=ma.sha1 "
        "WHERE ma.msg_key=? ORDER BY ma.rowid", (key,))]


def done(con, key, state, note=""):
    con.execute("INSERT OR REPLACE INTO att_done(msg_key,state,note,checked) VALUES(?,?,?,?)",
                (key, state, note[:200], datetime.now().isoformat()))
    con.commit()


def fetch_raw(pool, m):
    """Cała wiadomość z serwera (tylko odczyt). None + powód, gdy się nie da."""
    imap = pool.get(m["account"])
    if imap is None:
        return None, "offline"
    import learner_mail as LM
    typ, _ = imap.select(LM.quote(m["folder"]), readonly=True)
    if typ != "OK":
        return None, "folder niedostępny"
    _, vv = imap.response("UIDVALIDITY")
    validity = vv[0].decode() if vv and vv[0] else ""
    if m.get("validity") and validity and str(m["validity"]) != validity:
        return None, "wiadomość przeniesiona na serwerze"
    typ, data = imap.uid("fetch", str(m["uid"]), "(RFC822.SIZE)")
    size = re.search(rb"RFC822\.SIZE (\d+)", b" ".join(x if isinstance(x, bytes) else x[0] for x in (data or []) if x))
    if size and int(size.group(1)) > L.C.ATTACH_MAX_MB * 1024 * 1024:
        return None, "wiadomość za duża"
    typ, data = imap.uid("fetch", str(m["uid"]), "(BODY.PEEK[])")
    raw = next((x[1] for x in (data or []) if isinstance(x, tuple)), None)
    if typ != "OK" or raw is None:
        return None, "nie pobrano"
    return raw, ""


def parts_of(raw):
    """Załączniki do przeczytania: (nazwa, typ, bajty). Pomija stopki, ikonki i obrazki w treści."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    out = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        name = part.get_filename()
        if not name or not wanted(name):
            continue
        disposition = (part.get_content_disposition() or "").lower()
        is_image = name.lower().endswith(IMG_EXT)
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:
            continue
        if is_image and (disposition == "inline" or len(payload) < L.C.ATTACH_MIN_IMAGE_KB * 1024):
            continue
        if not payload:
            continue
        mime = part.get_content_type()
        if mime in ("application/octet-stream", ""):
            mime = mimetypes.guess_type(name)[0] or mime
        out.append((name, mime, payload))
    return out


def extract(con, name, mime, payload):
    """Tekst z pliku (z pamięci podręcznej, jeśli ten sam plik był już czytany)."""
    sha1 = hashlib.sha1(payload).hexdigest()
    row = con.execute("SELECT text FROM attachments WHERE sha1=?", (sha1,)).fetchone()
    if row is not None:
        return sha1, row["text"]
    tmp_dir = L.LEARN / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=Path(name).suffix.lower(), dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        text = L.extract_text(Path(tmp), {"name": name, "mime": mime}) or ""
    except Exception as e:
        L.log.warning(f"  Załącznik {name[:60]}: nie odczytano ({type(e).__name__})")
        text = ""
    finally:
        Path(tmp).unlink(missing_ok=True)    # plik znika z dysku natychmiast
    text = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()[:MAX_STORED_CHARS]
    con.execute("INSERT OR REPLACE INTO attachments(sha1,filename,mime,size,text,created) VALUES(?,?,?,?,?,?)",
                (sha1, name[:300], mime, len(payload), text, datetime.now().isoformat()))
    con.commit()
    return sha1, text


def for_message(con, pool, m):
    """Lista (nazwa, tekst) załączników wiadomości; pobiera z serwera tylko za pierwszym razem."""
    if not (applies(m) and has_attachments(m)):
        return []
    key = msg_key(m)
    state = con.execute("SELECT state FROM att_done WHERE msg_key=?", (key,)).fetchone()
    if state is not None:
        return cached(con, key)
    try:
        raw, reason = fetch_raw(pool, m)
    except Exception as e:
        raw, reason = None, f"błąd: {type(e).__name__}"
        with contextlib.suppress(Exception):
            pool.conns.pop(m["account"]).logout()
    if raw is None:
        if reason != "offline":           # offline = spróbujemy przy następnym czytaniu wątku
            done(con, key, "skip", reason)
        return []
    found = 0
    for name, mime, payload in parts_of(raw):
        sha1, text = extract(con, name, mime, payload)
        con.execute("INSERT OR IGNORE INTO message_attachments(msg_key,sha1,filename) VALUES(?,?,?)", (key, sha1, name[:300]))
        found += 1
    done(con, key, "ok", f"plików: {found}")
    return cached(con, key)


def render(items, seen):
    """Bloki tekstu załączników do wstawienia pod treścią maila."""
    out = []
    for name, text in items:
        digest = hashlib.sha1((text or "").encode()).hexdigest()
        if digest in seen:
            out.append(f"📎 Załącznik: {name} (ten sam plik co wyżej w wątku)")
            continue
        seen.add(digest)
        if not (text or "").strip():
            out.append(f"📎 Załącznik: {name} (bez tekstu do odczytania)")
            continue
        body = text if len(text) <= L.C.ATTACH_MAX_CHARS else text[:L.C.ATTACH_MAX_CHARS] + "\n[… dalsza część załącznika pominięta …]"
        out.append(f"📎 Załącznik: {name}\n<<< treść załącznika\n{body}\n>>> koniec załącznika")
    return out


# ================================================================ archiwum: które maile mają załączniki

def check_flags(con, limit=600):
    """Dla maili z archiwum pobranych przed wersją 2.1 sprawdza nagłówek Content-Type
    (kilkadziesiąt bajtów na mail), żeby wiedzieć, które wątki mają załączniki."""
    import learner_mail as LM
    if not L.C.ATTACHMENTS_ENABLED:
        return 0
    rows = con.execute("SELECT id, account, folder, validity, uid FROM history_mails WHERE att IS NULL "
                       "ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        return 0
    groups = {}
    for r in rows:
        groups.setdefault((r["account"], r["folder"], r["validity"]), []).append(r)
    pool, checked = ImapPool(), 0
    try:
        for (account, folder, validity), items in groups.items():
            if L.STOP:
                break
            imap = pool.get(account)
            if imap is None:
                continue
            typ, _ = imap.select(LM.quote(folder), readonly=True)
            _, vv = imap.response("UIDVALIDITY")
            current = vv[0].decode() if vv and vv[0] else ""
            if typ != "OK" or (current and current != str(validity)):
                con.executemany("UPDATE history_mails SET att=0 WHERE id=?", [(r["id"],) for r in items])
                checked += len(items)
                continue
            by_uid = {r["uid"]: r["id"] for r in items}
            for i in range(0, len(items), 100):
                batch = [str(r["uid"]) for r in items[i:i + 100]]
                typ, data = imap.uid("fetch", ",".join(batch), "(UID BODY.PEEK[HEADER.FIELDS (CONTENT-TYPE)])")
                found = {u: int(b"multipart/mixed" in parts.get("h", b"").lower())
                         for u, parts in LM.split_fetch(data).items()}
                for u in batch:
                    rid = by_uid.get(int(u))
                    con.execute("UPDATE history_mails SET att=? WHERE id=?", (found.get(int(u), 0), rid))
                    checked += 1
            con.commit()
    finally:
        pool.close()
    con.commit()
    return checked
