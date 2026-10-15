"""Sebastian 2.0 — nauka z poczty.

Źródła:
  1. wiadomości z bazy Sebastiana (nowa poczta + Twoje decyzje, notatki, WhatsApp, narady),
  2. archiwum skrzynek dociągane w tle przez IMAP (tylko odczyt, BODY.PEEK — nic nie zmienia
     się na serwerze, maile nie są oznaczane jako przeczytane). Archiwum trafia do bazy nauki,
     nie do kolejki decyzji w panelu.

Wiadomości są składane w wątki (nagłówki Message-ID / References). Wątek jest jednostką
nauki: gdy przyjdzie nowa odpowiedź, cały wątek zostaje przeczytany ponownie.
"""
import contextlib, email, email.policy, email.utils, hashlib, json, re, time
from datetime import datetime, timedelta, timezone

import learner as L

NOISE_SENDERS = re.compile(r"(no-?reply|do-?not-?reply|nie-?odpowiadaj|newsletter|mailer-daemon|postmaster|"
                           r"notification|powiadomieni|bounce|marketing@|promo)", re.I)
BULK_SQL = ("(instr(lower(body),'unsubscribe')>0 OR instr(lower(body),'wypisz')>0 "
            "OR instr(lower(body),'subskrypcj')>0 OR instr(lower(body),'newsletter')>0)")
SKIP_CATEGORIES = ("newsletter", "podejrzane")
QUOTE_START = re.compile(
    r"^\s*(?:>?\s*)(?:W dniu .{4,160}?(?:napisał|napisała|napisał\(a\)).{0,40}:"
    r"|On .{4,200}?wrote:"
    r"|-{2,}\s*(?:Original Message|Wiadomość oryginalna|Oryginalna wiadomość|Forwarded message|"
    r"Wiadomość przekazana dalej|Przekazana wiadomość)\s*-{2,}"
    r"|(?:Od|From):\s.+\n\s*(?:Wysłano|Wysłane|Data|Sent|Date):\s)", re.I | re.M)
SUBJECT_PREFIX = re.compile(r"^\s*((re|fw|fwd|odp|pd|aw|wg)\s*(\[\d+\])?\s*:\s*)+", re.I)


# ================================================================ pomocnicze

def to_utc(value):
    """Data maila → 'RRRR-MM-DDTHH:MM:SSZ' (porównywalna tekstowo z datami z Dysku)."""
    if not value:
        return ""
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        try:
            d = email.utils.parsedate_to_datetime(value)
        except Exception:
            return ""
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def thread_root(refs, mid, fallback):
    ids = re.findall(r"<[^>]+>", refs or "")
    if ids:
        return ids[0].lower()
    if mid:
        return mid.strip().lower()
    return fallback


def clean_subject(subject):
    s = SUBJECT_PREFIX.sub("", subject or "").strip()
    return s or "(bez tematu)"


def strip_quoted(body):
    """Usuwa cytowaną wcześniejszą korespondencję — wątek i tak zawiera te wiadomości."""
    body = body or ""
    m = QUOTE_START.search(body)
    if m and body[:m.start()].strip():
        body = body[:m.start()].rstrip() + "\n[… cytowana wcześniejsza korespondencja pominięta …]"
    lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith(">")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def sender_noise(sender):
    if NOISE_SENDERS.search(sender or ""):
        return True
    return any(p.lower() in (sender or "").lower() for p in L.C.MAIL_SKIP_SENDERS)


def accounts():
    with contextlib.suppress(Exception):
        accts = L.S.config()["accounts"]
        if L.C.MAIL_ACCOUNTS:
            accts = [a for a in accts if a["id"] in L.C.MAIL_ACCOUNTS]
        return accts
    return []


# ================================================================ źródło 1: baza Sebastiana

def sebastian_messages():
    sc = L.sebastian_db()
    if sc is None:
        return []
    with contextlib.closing(sc):
        cols = {r[1] for r in sc.execute("PRAGMA table_info(messages)")}
        want = ["id", "source", "scope", "account", "folder", "validity", "uid", "mid", "refs", "sender",
                "subject", "date", "status", "category_override",
                "sender_name", "decided_at", "topic", "topic_sub", "comment", "task_title", "is_task", "skip_reason",
                "attachments"]
        select = ", ".join(c if c in cols else f"'' AS {c}" for c in want)
        rows = sc.execute(f"SELECT {select}, json_extract(analysis,'$.category') AS ai_category, "
                          f"{BULK_SQL} AS bulk FROM messages WHERE source<>'demo'").fetchall()
    sent_folders = {a["id"]: a.get("sent_folder", "") for a in accounts()}
    out = []
    for r in rows:
        d = dict(r)
        d["origin"] = "seb"
        d["is_sent"] = bool(sent_folders.get(d["account"]) and d["folder"] == sent_folders.get(d["account"]))
        out.append(d)
    return out


# ================================================================ źródło 2: archiwum IMAP

LIST_RE = re.compile(rb'^\((?P<flags>[^)]*)\)\s+(?P<delim>"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)$')
SKIP_FLAGS = ("\\noselect", "\\nonexistent", "\\trash", "\\junk", "\\drafts", "\\flagged", "\\important")
SKIP_NAMES = re.compile(r"(spam|junk|trash|kosz|usuni|deleted|drafts|szkic|wersje robocze|robocze|outbox|skrzynka nadawcza)", re.I)


def parse_list(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, bytes):
            continue
        m = LIST_RE.match(row.strip())
        if not m:
            continue
        name = m.group("name").strip()
        if name.startswith(b'"') and name.endswith(b'"'):
            name = name[1:-1].replace(b'\\"', b'"').replace(b"\\\\", b"\\")
        out.append((name.decode("utf-8", "replace"), m.group("flags").decode().lower()))
    return out


def pick_folders(a, listing):
    if L.C.MAIL_FOLDERS.get(a["id"]):
        wanted = L.C.MAIL_FOLDERS[a["id"]]
        return [(n, f) for n, f in listing if n in wanted]
    if "gmail" in a.get("host", ""):
        allmail = [(n, f) for n, f in listing if "\\all" in f]
        if allmail:
            return allmail[:1]
    chosen = []
    for name, flags in listing:
        if any(x in flags for x in SKIP_FLAGS) or "\\all" in flags:
            continue
        if SKIP_NAMES.search(name) and "\\sent" not in flags:
            continue
        chosen.append((name, flags))
    return chosen


def quote(folder):
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_fetch(data):
    """Odpowiedź UID FETCH dla wielu maili → {uid: {'h': nagłówki, 't': treść}}."""
    result, cur, uid = [], None, None

    def flush():
        if cur is not None and uid is not None:
            result.append((uid, cur))

    for item in data or []:
        meta = item[0] if isinstance(item, tuple) else item
        if not isinstance(meta, bytes):
            continue
        if re.match(rb"^\d+ \(", meta):
            flush()
            cur, uid = {}, None
        if cur is None:
            continue
        m = re.search(rb"UID (\d+)", meta)
        if m:
            uid = int(m.group(1))
        if isinstance(item, tuple):
            key = "h" if b"HEADER" in meta else "t" if b"TEXT" in meta else None
            if key:
                cur[key] = item[1]
    flush()
    return dict(result)


def parse_partial(parts):
    header, text = parts.get("h", b""), parts.get("t", b"")
    fields = L.S.parse_mail(header + text, L.C.MAIL_MAX_CHARS)
    msg = email.message_from_bytes(header, policy=email.policy.default)
    rcpt = []
    for key in ("To", "Cc"):
        with contextlib.suppress(Exception):
            rcpt += [addr.lower() for _, addr in email.utils.getaddresses([str(x) for x in msg.get_all(key, [])]) if addr]
    fields["recipients"] = ", ".join(rcpt[:20])
    body = fields.get("body", "").lower()
    fields["bulk"] = int(bool(msg.get("List-Unsubscribe")) or "unsubscribe" in body or "wypisz" in body)
    fields["att"] = int(msg.get_content_type() == "multipart/mixed")
    return fields


def fetch_history(con, per_account=None):
    """Dociąga kolejną porcję archiwum (najnowsze najpierw). Zwraca liczbę nowych wiadomości."""
    per_account = per_account or L.C.MAIL_HISTORY_BATCH
    own = set(L.own_addresses())
    total_added = 0
    for a in accounts():
        if L.STOP:
            break
        failed_at = L.meta_get(con, "mail_fail_" + a["id"], "") or ""
        if failed_at and failed_at > (datetime.now() - timedelta(hours=6)).isoformat():
            continue   # konto bez działającego logowania — spróbujemy za kilka godzin
        try:
            m = L.S.connect(a)
        except Exception as e:
            L.meta_set(con, "mail_fail_" + a["id"], datetime.now().isoformat())
            con.execute("INSERT OR REPLACE INTO history_folders(account,folder,checked,error) VALUES(?,?,?,?)",
                        (a["id"], "*", datetime.now().isoformat(), str(e)[:200]))
            con.commit()
            L.log.warning(f"Poczta {a['id']}: brak połączenia ({str(e)[:120]})")
            continue
        con.execute("DELETE FROM history_folders WHERE account=? AND folder='*'", (a["id"],))
        con.execute("DELETE FROM meta WHERE key=?", ("mail_fail_" + a["id"],))
        budget = per_account
        try:
            typ, rows = m.list()
            folders = pick_folders(a, parse_list(rows if typ == "OK" else []))
            for folder, flags in folders:
                if budget <= 0 or L.STOP:
                    break
                try:
                    budget -= fetch_folder(con, m, a, folder, flags, own, budget)
                except Exception as e:
                    con.execute("INSERT OR REPLACE INTO history_folders(account,folder,flags,checked,error) VALUES(?,?,?,?,?)",
                                (a["id"], folder, flags, datetime.now().isoformat(), str(e)[:200]))
                    con.commit()
            total_added += per_account - budget
        finally:
            with contextlib.suppress(Exception):
                m.logout()
    return total_added


def fetch_folder(con, m, a, folder, flags, own, budget):
    typ, _ = m.select(quote(folder), readonly=True)
    if typ != "OK":
        raise RuntimeError("nie można otworzyć folderu")
    _, vv = m.response("UIDVALIDITY")
    validity = vv[0].decode() if vv and vv[0] else "0"
    if L.C.MAIL_HISTORY_SINCE:
        since = datetime.fromisoformat(L.C.MAIL_HISTORY_SINCE).strftime("%d-%b-%Y")
        typ, data = m.uid("search", None, "SINCE", since)
    else:
        typ, data = m.uid("search", None, "ALL")
    if typ != "OK":
        raise RuntimeError("błąd listy UID")
    ids = sorted((int(x) for x in (data[0] or b"").split()), reverse=True)
    known = {r[0] for r in con.execute("SELECT uid FROM history_mails WHERE account=? AND folder=? AND validity=?",
                                       (a["id"], folder, validity))}
    todo = [u for u in ids if u not in known][:budget]
    is_sent_folder = "\\sent" in flags
    added = 0
    for i in range(0, len(todo), 25):
        if L.STOP:
            break
        batch = todo[i:i + 25]
        typ, data = m.uid("fetch", ",".join(map(str, batch)),
                          "(UID RFC822.SIZE BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.200000>)")
        if typ != "OK":
            raise RuntimeError("błąd pobierania")
        for uid, parts in split_fetch(data).items():
            try:
                fld = parse_partial(parts)
            except Exception:
                continue
            sent = int(is_sent_folder or fld["sender"] in own)
            con.execute("""INSERT OR IGNORE INTO history_mails(account,scope,folder,validity,uid,mid,refs,sender,sender_name,
                           recipients,subject,date,body,truncated,is_sent,bulk,fetched,att) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (a["id"], a.get("scope", "private"), folder, validity, uid, fld["mid"], fld["refs"], fld["sender"],
                         fld.get("sender_name", ""), fld["recipients"], fld["subject"], fld["date"], fld["body"],
                         fld["truncated"], sent, fld["bulk"], datetime.now().isoformat(), fld["att"]))
            added += 1
        con.commit()
    fetched = con.execute("SELECT COUNT(*) FROM history_mails WHERE account=? AND folder=? AND validity=?",
                          (a["id"], folder, validity)).fetchone()[0]
    con.execute("INSERT OR REPLACE INTO history_folders(account,folder,validity,flags,total,fetched,checked,error) "
                "VALUES(?,?,?,?,?,?,?,'')", (a["id"], folder, validity, flags, len(ids), fetched, datetime.now().isoformat()))
    con.commit()
    if added:
        L.log.info(f"Archiwum {a['id']} / {folder}: +{added} (razem {fetched}/{len(ids)})")
    return added


def history_messages(con):
    rows = con.execute("SELECT id, account, scope, folder, validity, uid, mid, refs, sender, sender_name, recipients, "
                       "subject, date, is_sent, bulk, att FROM history_mails").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d.update(origin="hist", source="email", status="", category_override="", ai_category="",
                 decided_at="", is_sent=bool(r["is_sent"]))
        out.append(d)
    return out


# ================================================================ wątki

def keep(msg, own):
    if msg["source"] == "demo":
        return False
    if msg["source"] in L.IMPORT_SOURCES:
        return True
    if msg["is_sent"] or (msg["sender"] or "").lower() in own:
        return True
    if msg.get("status") == "ignored":
        return False
    if msg.get("decided_at") and msg.get("status") in ("open", "done"):
        return True    # Twoja świadoma decyzja w panelu = sprawa warta uwagi
    if (msg.get("category_override") or msg.get("ai_category") or "") in SKIP_CATEGORIES:
        return False
    if sender_noise(msg.get("sender")):
        return False
    if msg.get("bulk"):
        return False
    return True


def group_threads(messages, own):
    """Deduplikacja (Message-ID) i grupowanie w wątki. Zwraca {thread_id: [wiadomości]}."""
    by_key = {}
    for msg in messages:
        msg["is_sent"] = bool(msg["is_sent"] or (msg["sender"] or "").lower() in own)
        key = (msg["mid"] or "").strip().lower() or f"{msg['origin']}|{msg['account']}|{msg['folder']}|{msg['uid']}"
        prev = by_key.get(key)
        if prev is None or (prev["origin"] == "hist" and msg["origin"] == "seb"):
            if prev is not None:   # zachowaj odbiorców i flagę wysłania z archiwum
                msg["recipients"] = msg.get("recipients") or prev.get("recipients", "")
                msg["is_sent"] = msg["is_sent"] or prev["is_sent"]
            by_key[key] = msg
        elif msg["origin"] == "hist" and prev["origin"] == "seb":
            prev["recipients"] = prev.get("recipients") or msg.get("recipients", "")
            prev["is_sent"] = prev["is_sent"] or msg["is_sent"]
    threads = {}
    for msg in by_key.values():
        if msg["source"] in L.IMPORT_SOURCES:
            tid = "import:" + hashlib.sha1(f"{msg['scope']}|{msg['folder']}".encode()).hexdigest()[:16]
        else:
            root = thread_root(msg["refs"], msg["mid"], f"{msg['account']}|{msg['folder']}|{msg['uid']}")
            tid = "mail:" + hashlib.sha1(root.encode()).hexdigest()[:16]
        threads.setdefault(tid, []).append(msg)
    return {tid: msgs for tid, msgs in threads.items() if any(keep(m, own) for m in msgs)}


def thread_entry(tid, msgs):
    msgs = sorted(msgs, key=lambda m: to_utc(m["date"]) or "")
    last = to_utc(msgs[-1]["date"]) or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scope = "work" if any(m["scope"] == "work" for m in msgs) else "private"
    if tid.startswith("import:"):
        name = re.sub(r"\s*\[\d+/\d+\]$", "", msgs[0]["subject"] or "notatka")
        path = f"Notatki i rozmowy/{'firmowe' if scope == 'work' else 'prywatne'}/{name}"
        mime = "text/note"
    else:
        name = clean_subject(msgs[0]["subject"])
        path = f"Poczta {'firmowa' if scope == 'work' else 'prywatna'}/{last[:7]}/{name}"
        mime = "message/thread"
    recent = datetime.now(timezone.utc) - timedelta(days=L.C.MAIL_RECENT_DAYS)
    priority = 0 if last >= recent.strftime("%Y-%m-%dT%H:%M:%SZ") else 4
    sig = hashlib.sha1(json.dumps(sorted(
        [m["origin"], m["id"], m.get("status", ""), m.get("decided_at", ""), m.get("comment", ""), m.get("task_title", "")]
        for m in msgs), default=str).encode()).hexdigest()
    import learner_attach as LA
    with_att = [m["id"] for m in msgs if LA.applies(m) and LA.has_attachments(m)]
    if with_att:   # 2.1: wątki z załącznikami dostają nowy podpis → zostaną przeczytane ponownie, z plikami
        sig = hashlib.sha1(f"{sig}|zalaczniki-v1|{sorted(with_att)}".encode()).hexdigest()
    return dict(id=tid, name=name[:200], path=path, mime=mime, modified=last, priority=priority, scope=scope,
                sig=sig, members=[(m["origin"], m["id"]) for m in msgs], count=len(msgs))


def scan_mail(con):
    """Odświeża listę wątków do nauki (bez modelu — szybkie)."""
    own = set(L.own_addresses())
    messages = sebastian_messages() + history_messages(con)
    threads = group_threads(messages, own)
    new = changed = 0
    for tid, msgs in threads.items():
        e = thread_entry(tid, msgs)
        row = con.execute("SELECT sig FROM files WHERE id=?", (tid,)).fetchone()
        if row is None:
            con.execute("INSERT INTO files(id,name,path,mime,size,modified,priority,scope,sig) VALUES(?,?,?,?,?,?,?,?,?)",
                        (tid, e["name"], e["path"], e["mime"], e["count"], e["modified"], e["priority"], e["scope"], e["sig"]))
            new += 1
        elif row["sig"] != e["sig"]:
            con.execute("UPDATE files SET name=?,path=?,size=?,modified=?,priority=?,scope=?,sig=?,status='new',note=NULL WHERE id=?",
                        (e["name"], e["path"], e["count"], e["modified"], e["priority"], e["scope"], e["sig"], tid))
            changed += 1
        else:
            continue
        con.execute("DELETE FROM mail_members WHERE thread_id=?", (tid,))
        con.executemany("INSERT OR IGNORE INTO mail_members VALUES(?,?,?)", [(tid, o, i) for o, i in e["members"]])
    con.commit()
    L.meta_set(con, "last_mail_scan", datetime.now().isoformat())
    if new or changed:
        L.log.info(f"Poczta: wątków {len(threads)}, nowe {new}, zaktualizowane {changed}.")
    return new + changed


def load_members(con, tid):
    out = []
    members = con.execute("SELECT origin, ref_id FROM mail_members WHERE thread_id=?", (tid,)).fetchall()
    seb_ids = [r["ref_id"] for r in members if r["origin"] == "seb"]
    hist_ids = [r["ref_id"] for r in members if r["origin"] == "hist"]
    if seb_ids:
        sc = L.sebastian_db()
        if sc is not None:
            with contextlib.closing(sc):
                cols = {r[1] for r in sc.execute("PRAGMA table_info(messages)")}
                extra = [c for c in ("sender_name", "decided_at", "topic", "topic_sub", "comment", "task_title", "is_task",
                                     "attachments", "validity", "uid") if c in cols]
                q = ",".join("?" * len(seb_ids))
                for r in sc.execute(f"SELECT id, source, scope, account, folder, sender, subject, date, body, status"
                                    f"{''.join(', ' + c for c in extra)} FROM messages WHERE id IN ({q})", seb_ids):
                    d = dict(r)
                    d["origin"] = "seb"
                    out.append(d)
    if hist_ids:
        q = ",".join("?" * len(hist_ids))
        for r in con.execute(f"SELECT * FROM history_mails WHERE id IN ({q})", hist_ids):
            d = dict(r)
            d["origin"] = "hist"
            out.append(d)
    return out


def thread_text(con, tid):
    """Tekst wątku dla modelu: nagłówek + wiadomości od najstarszej (najnowsze mają pierwszeństwo przy limicie)."""
    own = set(L.own_addresses())
    sent_folders = {a["id"]: a.get("sent_folder", "") for a in accounts()}
    msgs = load_members(con, tid)
    seen, unique = set(), []
    for m in sorted(msgs, key=lambda m: (to_utc(m["date"]), m["origin"] != "seb")):
        key = (m["subject"], to_utc(m["date"]), (m["sender"] or "").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    if not unique:
        return "", ""
    import learner_attach as LA
    blocks, pool, seen_files, n_files = [], LA.ImapPool(), set(), 0
    for m in unique:
        is_sent = bool(m.get("is_sent")) or (m["sender"] or "").lower() in own or \
            (sent_folders.get(m["account"]) and m["folder"] == sent_folders.get(m["account"]))
        when = (to_utc(m["date"]) or "")[:16].replace("T", " ")
        if m.get("source") in L.IMPORT_SOURCES:
            head = f"=== {m['subject']} (import: {m['source']})"
        elif is_sent:
            head = f"=== {when} · WYSŁANE PRZEZE MNIE (konto {m['account']})" + \
                   (f" · do: {m['recipients']}" if m.get("recipients") else "")
        else:
            who = f"{m.get('sender_name') or ''} <{m['sender']}>".strip()
            head = f"=== {when} · OD: {who} (konto {m['account']})"
        lines = [head]
        if m["origin"] == "seb" and m.get("decided_at"):
            status = {"open": "w toku / do zadań", "done": "zrobione", "ignored": "pominięte"}.get(m.get("status"), m.get("status"))
            info = [f"status: {status}"]
            topic = " / ".join(x for x in (m.get("topic"), m.get("topic_sub")) if x)
            if topic:
                info.append(f"kategoria: {topic}")
            if m.get("task_title"):
                info.append(f"zadanie: {m['task_title']}")
            if m.get("comment"):
                info.append(f"mój komentarz: {m['comment']}")
            lines.append("Moja decyzja w panelu Sebastiana — " + "; ".join(info))
        lines.append(strip_quoted(m["body"]) if m.get("source") not in L.IMPORT_SOURCES else (m["body"] or ""))
        try:
            files = LA.for_message(con, pool, m)
        except Exception as e:
            L.log.warning(f"  Załączniki: {type(e).__name__}: {str(e)[:120]}")
            files = []
        n_files += len(files)
        lines += LA.render(files, seen_files)
        blocks.append("\n".join(lines))
    pool.close()
    if n_files:
        L.log.info(f"  📎 załączników w wątku: {n_files}")
    kept, size = [], 0
    for b in reversed(blocks):          # najnowsze najpierw, aż do limitu
        if size + len(b) > L.C.MAIL_THREAD_MAX_CHARS and kept:
            kept.append("[… wcześniejsze wiadomości wątku pominięte ze względu na długość …]")
            break
        kept.append(b)
        size += len(b)
    kept.reverse()
    participants = sorted({(m["sender"] or "").lower() for m in unique if m.get("sender")} - own)
    accts = sorted({m["account"] for m in unique})
    dates = [to_utc(m["date"])[:10] for m in unique if to_utc(m["date"])]
    header = [f"Wątek: {clean_subject(unique[0]['subject'])}",
              f"Konta: {', '.join(accts)} · wiadomości: {len(unique)}" + (f" · okres: {min(dates)} – {max(dates)}" if dates else ""),
              f"Inni uczestnicy: {', '.join(participants[:15]) or '—'}", "", ""]
    seb_links = [f"http://127.0.0.1:8765/message/{m['id']}" for m in unique if m["origin"] == "seb" and m.get("source") == "email"]
    origin = ("panel Sebastiana: " + ", ".join(seb_links[-5:])) if seb_links else \
        f"archiwum poczty (konto {', '.join(accts)})"
    return "\n".join(header) + "\n\n".join(kept), origin


# ================================================================ rytm pracy

def tick(con):
    """Wywoływane w każdej rundzie pętli nauki: odświeża listę wątków co MAIL_SCAN_MINUTES."""
    if L.meta_get(con, "history_dirty") == "1" or L.hours_since(con, "last_mail_scan") * 60 >= L.C.MAIL_SCAN_MINUTES:
        L.meta_set(con, "history_dirty", "0")
        scan_mail(con)


def history_worker():
    """Wątek w tle: dociąga archiwum skrzynek niezależnie od czytania przez model.
    Archiwum pobiera się szybciej, niż model czyta — dzięki temu stare wątki są zwykle
    kompletne, zanim przyjdzie na nie kolej, i nie trzeba ich czytać kilka razy."""
    import contextlib as _c
    with _c.closing(L.db()) as con:
        while not L.STOP:
            try:
                paused = (L.meta_get(con, "history_pause_until", "") or "") > datetime.now().isoformat()
                if paused:
                    L.sleep(300)
                    continue
                L.meta_set(con, "last_history_fetch", datetime.now().isoformat())
                fetched = fetch_history(con, per_account=L.C.MAIL_HISTORY_BATCH)
                import learner_attach as LA
                flagged = LA.check_flags(con)
                if flagged:
                    L.meta_set(con, "history_dirty", "1")
                if fetched or flagged:
                    L.meta_set(con, "history_dirty", "1")
                    L.sleep(5)
                else:   # archiwum przeczytane — nowe foldery/wiadomości sprawdzaj co kilka godzin
                    L.meta_set(con, "history_pause_until", (datetime.now() + timedelta(hours=6)).isoformat())
            except Exception as e:
                L.log.warning(f"Archiwum poczty: {type(e).__name__}: {str(e)[:150]} — ponowię za 15 min.")
                L.sleep(900)


def cmd_mail_test(account_id=""):
    """Sprawdza logowanie (Pęk kluczy) i pokazuje foldery, które nauka przeczyta."""
    con = L.db()
    for a in accounts():
        if account_id and a["id"] != account_id:
            continue
        print(f"\n▶ {a['id']} ({a['user']})")
        try:
            m = L.S.connect(a)
        except Exception as e:
            print(f"   ✗ {e}")
            continue
        try:
            typ, rows = m.list()
            listing = parse_list(rows if typ == "OK" else [])
            chosen = pick_folders(a, listing)
            for name, flags in chosen:
                typ, _ = m.select(quote(name), readonly=True)
                count = ""
                if typ == "OK":
                    typ, data = m.uid("search", None, "ALL")
                    count = f"{len((data[0] or b'').split())} wiadomości" if typ == "OK" else ""
                label = "  [wysłane]" if "\\sent" in flags else ""
                print(f"   ✓ {name:<40} {count}{label}")
            skipped = [n for n, _ in listing if n not in {c for c, _ in chosen}]
            if skipped:
                print(f"   pomijane: {', '.join(skipped[:12])}{' …' if len(skipped) > 12 else ''}")
        finally:
            with contextlib.suppress(Exception):
                m.logout()
    con.close()
