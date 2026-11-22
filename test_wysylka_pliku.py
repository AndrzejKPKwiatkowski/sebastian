"""2.31: wysyłanie plików (np. PDF) na WhatsAppie — polecenie wa-send-file."""
import contextlib, io, unittest
from pathlib import Path
from unittest.mock import patch

import whatsapp as W
import whatsapp_link
from test_whatsapp import Base, OWNER

AGA = "48500999888"


class SendFile(Base):
    def setUp(self):
        super().setUp()
        W.save_settings({"WA_USERS": [{"phone": AGA, "name": "Aga Kwiatkowska", "call": "Aga", "access": "pelny"}]})
        W.C = W.load_settings()
        self.pdf = Path(self.temp.name) / "Sebastian_instrukcja_dla_Agi.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test")

    def test_find_user(self):
        self.assertEqual(W.find_user("Aga")["phone"], AGA)
        self.assertEqual(W.find_user("aga kwiatkowska")["phone"], AGA)
        self.assertEqual(W.find_user("+48 500 999 888")["phone"], AGA)
        self.assertEqual(W.find_user("ja")["role"], "wlasciciel")
        self.assertIsNone(W.find_user("Zenek"))

    def test_text_then_pdf_delivered_in_order(self):
        out = io.StringIO()
        with patch.object(W, "self_mode", lambda: False), contextlib.redirect_stdout(out):
            self.assertEqual(W.cmd_send_file("Aga", str(self.pdf), "Cześć Aga! Już się o Tobie uczę :)"), 0)
        self.assertIn("wiadomość + plik Sebastian_instrukcja_dla_Agi.pdf → Aga Kwiatkowska", out.getvalue())
        t = W.FileTransport()
        t.start()
        with self.con() as con:
            self.assertEqual(W.flush(con, t), 2)
            rows = con.execute("SELECT kind, to_phone, status FROM outbox ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("text", AGA, "sent"), ("doc", AGA, "sent")])
        sent = sorted(p.name for p in t.dir.iterdir())
        self.assertTrue(any(n.endswith("Sebastian_instrukcja_dla_Agi.pdf") and n.startswith(AGA) for n in sent))
        self.assertTrue(self.pdf.exists())                                   # oryginał zostaje

    def test_unknown_person_and_missing_file(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(W.cmd_send_file("Zenek", str(self.pdf)), 1)
        self.assertIn("nie ma na liście", out.getvalue())
        with self.assertRaises(FileNotFoundError), self.con() as con:
            W.send_file(con, W.find_user("Aga"), "/nie/ma/takiego.pdf")

    def test_linked_transport_builds_document(self):
        calls = {}

        class Client:
            def build_document_message(self, data, caption=None, title=None, filename=None, mimetype=None):
                calls.update(data=data, filename=filename, mimetype=mimetype, caption=caption)
                return "MSG"

            def send_message(self, jid, msg):
                calls["sent"] = (jid, msg)
                return "ok"
        tr = whatsapp_link.LinkedTransport.__new__(whatsapp_link.LinkedTransport)
        tr.client = Client()
        tr.target = lambda to: f"jid:{to}"
        tr._sent = lambda resp, jid: resp
        f = Path(self.temp.name) / "20261122-171000-Instrukcja.pdf"
        f.write_bytes(b"%PDF")
        self.assertEqual(tr.send_document(f, "", AGA), "ok")
        self.assertEqual((calls["filename"], calls["mimetype"], calls["sent"]), ("Instrukcja.pdf", "application/pdf", (f"jid:{AGA}", "MSG")))


if __name__ == "__main__":
    unittest.main()
