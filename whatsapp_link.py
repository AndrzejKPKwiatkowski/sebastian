"""Sebastian 2.3 — połączenie z WhatsAppem jako „połączone urządzenie” (biblioteka neonize / whatsmeow).

Osobny moduł, bo biblioteka jest potrzebna tylko na Macu z włączonym WhatsAppem (testy i reszta Sebastiana
działają bez niej). Sesja (klucze szyfrowania) leży w data/whatsapp/sesja.sqlite3 — jak hasło: 🔒.

Filtr bezpieczeństwa: do Sebastiana trafiają WYŁĄCZNIE wiadomości właściciela —
  • osobny numer Sebastiana: wiadomości przychodzące od numeru właściciela (także w adresacji „LID”),
  • ten sam numer (czat „Ty”): tylko wiadomości, które właściciel wysłał sam do siebie.
Grupy, inni ludzie i statusy są ignorowane (nie są nawet zapisywane).
"""
import contextlib, threading, time
from pathlib import Path


def ensure_library():
    """Import biblioteki z czytelnym błędem (brak neonize / libmagic / ffmpeg)."""
    try:
        import neonize  # noqa: F401
        from neonize.client import NewClient  # noqa: F401
    except ImportError as e:
        if "magic" in str(e).lower() or "libmagic" in str(e).lower():
            raise RuntimeError("brak libmagic — brew install libmagic") from e
        raise RuntimeError("brak biblioteki neonize — python -m pip install -r requirements-whatsapp.txt") from e


def _jid(number):
    from neonize.utils import build_jid
    return build_jid(number)


class LinkedTransport:
    def __init__(self, on_message, session, owner, log):
        ensure_library()
        from neonize.client import NewClient
        from neonize.events import ConnectedEv, DisconnectedEv, LoggedOutEv, MessageEv
        self.log, self.owner, self.on_message = log, owner, on_message
        self.client = NewClient(str(session))
        self.connected = self.logged_out = self.needs_login = self.stopping = False
        self.me = self.me_lid = self.owner_lid = None
        self.sent_ids = set()
        self.thread = None
        c = self.client

        @c.event(ConnectedEv)
        def _connected(client, ev):
            self.connected = True
            self.identify()
            self.log.info("WhatsApp: połączono" + (f" (konto +{self.me})" if self.me else ""))

        @c.event(DisconnectedEv)
        def _disconnected(client, ev):
            self.connected = False
            self.log.info("WhatsApp: rozłączono — biblioteka połączy się ponownie sama.")

        @c.event(LoggedOutEv)
        def _logged_out(client, ev):
            self.connected, self.logged_out = False, True
            self.log.warning("WhatsApp wylogował Sebastiana (usunięte z Połączonych urządzeń albo telefon długo offline). "
                             "Połącz ponownie: python sebastian.py wa-login")

        @c.event(MessageEv)
        def _message(client, ev):
            try:
                msg = self.parse(ev)
            except Exception as e:
                self.log.warning(f"WhatsApp: nie odczytano wiadomości ({type(e).__name__})")
                return
            if msg:
                self.on_message(msg)

        def _qr(client, data):          # w usłudze kod QR oznacza: sesja nieważna — nie pokazujemy go w logu
            if not self.needs_login:
                self.log.warning("WhatsApp prosi o ponowne połączenie. Uruchom w Terminalu: python sebastian.py wa-login")
            self.needs_login = True
            threading.Thread(target=self.stop, daemon=True).start()
        c.event.qr(_qr)

    # ---------------------------------------------------------------- kim jestem, do kogo piszę

    def identify(self):
        with contextlib.suppress(Exception):
            me = self.client.get_me()
            self.me = me.JID.User or None
            self.me_lid = me.LID.User or None
        with contextlib.suppress(Exception):     # nowa adresacja WhatsAppa (LID) — ten sam człowiek, inny identyfikator
            self.owner_lid = self.client.get_lid_from_pn(_jid(self.owner)).User or self.owner_lid

    @property
    def self_mode(self):
        return bool(self.me) and self.me == self.owner

    def target(self):
        return _jid(self.me if self.self_mode else self.owner)

    # ---------------------------------------------------------------- odbiór

    def parse(self, ev):
        """MessageEv → dict albo None (gdy to nie wiadomość od właściciela)."""
        info = ev.Info
        src = info.MessageSource
        if src.IsGroup or info.ID in self.sent_ids:
            return None
        if self.me is None:
            self.identify()
        if src.Chat.Server == "broadcast" or src.Chat.User == "status":
            return None
        if self.self_mode:
            if not src.IsFromMe or src.Chat.User not in {self.me, self.me_lid} - {None}:
                return None
        else:
            if src.IsFromMe:
                return None
            users = {src.Sender.User, src.SenderAlt.User}
            if self.owner not in users and not (self.owner_lid and self.owner_lid in users) and src.Sender.Server == "lid":
                with contextlib.suppress(Exception):
                    users.add(self.client.get_pn_from_lid(src.Sender).User)
            if self.owner not in users and not (self.owner_lid and self.owner_lid in users):
                return None
            if src.Sender.Server == "lid":
                self.owner_lid = src.Sender.User
        ts = info.Timestamp or 0
        ts = ts / 1000 if ts > 10_000_000_000 else ts
        m = ev.Message
        with contextlib.suppress(Exception):
            from neonize.utils.enum import ReceiptType
            self.client.mark_read(info.ID, chat=src.Chat, sender=src.Sender, receipt=ReceiptType.READ)
        if m.HasField("audioMessage"):
            return {"id": info.ID, "kind": "voice", "text": "", "audio_bytes": self.client.download_any(m), "ts": ts}
        text = m.conversation or (m.extendedTextMessage.text if m.HasField("extendedTextMessage") else "")
        if not text.strip():
            return None
        return {"id": info.ID, "kind": "text", "text": text, "ts": ts}

    # ---------------------------------------------------------------- wysyłka

    def send_text(self, text):
        resp = self.client.send_message(self.target(), text)
        self.sent_ids.add(resp.ID)
        return resp.ID

    def send_voice(self, ogg):
        msg = self.client.build_audio_message(Path(ogg).read_bytes(), ptt=True)
        msg.audioMessage.mimetype = "audio/ogg; codecs=opus"      # tak WhatsApp rozpoznaje głosówkę (PTT)
        resp = self.client.send_message(self.target(), msg)
        self.sent_ids.add(resp.ID)
        return resp.ID

    def typing(self, on):
        from neonize.utils.enum import ChatPresence, ChatPresenceMedia
        state = ChatPresence.CHAT_PRESENCE_COMPOSING if on else ChatPresence.CHAT_PRESENCE_PAUSED
        self.client.send_chat_presence(self.target(), state, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)

    # ---------------------------------------------------------------- praca w tle

    def start(self):
        def loop():
            while not self.stopping and not self.needs_login and not self.logged_out:
                try:
                    self.client.connect()           # blokuje do czasu stop()/rozłączenia
                except Exception as e:
                    self.log.warning(f"WhatsApp: błąd połączenia ({type(e).__name__}: {str(e)[:150]}) — ponowię za minutę.")
                self.connected = False
                for _ in range(60):
                    if self.stopping:
                        return
                    time.sleep(1)
        self.thread = threading.Thread(target=loop, name="whatsapp", daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping = True
        with contextlib.suppress(Exception):
            self.client.stop()


def pair(session, qr_png, phone=None, timeout=300):
    """Parowanie: QR w Terminalu (i w pliku PNG) albo kod do wpisania w telefonie. Zwraca numer połączonego konta."""
    ensure_library()
    import segno
    from neonize.client import NewClient
    from neonize.events import ConnectedEv, PairStatusEv
    Path(session).parent.mkdir(parents=True, exist_ok=True)
    client = NewClient(str(session))
    done, result, asked = threading.Event(), {}, []

    @client.event(ConnectedEv)
    def _connected(c, ev):
        with contextlib.suppress(Exception):
            result["me"] = c.get_me().JID.User
        done.set()

    @client.event(PairStatusEv)
    def _pair(c, ev):
        if ev.Error:
            result["error"] = ev.Error
            done.set()

    def _qr(c, data):
        if phone:
            if not asked:
                asked.append(1)

                def ask_code():
                    try:
                        code = c.PairPhone(phone, show_push_notification=True)
                        print(f"\n  KOD DO WPISANIA W TELEFONIE:  {code}\n")
                    except Exception as e:
                        result["error"] = f"kod: {e}"
                        done.set()
                threading.Thread(target=ask_code, daemon=True).start()
            return
        qr = segno.make_qr(data)
        qr.terminal(compact=True)
        with contextlib.suppress(Exception):
            qr.save(str(qr_png), scale=8, border=3)
        print("(kod QR odświeża się co ~20 sekund — skanuj ten najnowszy)")
    client.event.qr(_qr)

    t = threading.Thread(target=client.connect, daemon=True)
    t.start()
    done.wait(timeout)
    with contextlib.suppress(Exception):
        client.stop()
    t.join(15)
    Path(qr_png).unlink(missing_ok=True)
    if result.get("error"):
        raise RuntimeError(f"Parowanie nieudane: {result['error']}")
    if not done.is_set():
        raise RuntimeError("Nie połączono w ciągu 5 minut. Spróbuj ponownie: python sebastian.py wa-login")
    return result.get("me")


def logout(session):
    ensure_library()
    from neonize.client import NewClient
    if not Path(session).exists():
        return
    client = NewClient(str(session))
    done = threading.Event()
    from neonize.events import ConnectedEv

    @client.event(ConnectedEv)
    def _c(c, ev):
        with contextlib.suppress(Exception):
            c.logout()
        done.set()
    t = threading.Thread(target=client.connect, daemon=True)
    t.start()
    done.wait(30)
    with contextlib.suppress(Exception):
        client.stop()
