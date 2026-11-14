"""2.14.4: wspólny, elegancki wygląd maili Sebastiana."""
import unittest

import mail_szablon as MS


class Szablon(unittest.TestCase):
    def test_render(self):
        h = MS.render("Spotkanie potwierdzone", "<b>Anna</b> potwierdziła.", [("Kiedy", "pon 17.11, 10:00"), ("Gdzie", "")],
                      [("Akceptuję", "https://x/a"), ("Nie mogę", "https://x/n")], "Stopka", preheader="Krótko")
        self.assertIn("Spotkanie potwierdzone", h)
        self.assertIn("pon 17.11, 10:00", h)
        self.assertNotIn(">Gdzie<", h)                                   # puste wiersze pomijane
        self.assertEqual(h.count("background:#111111;color:#ffffff"), 1)  # jeden przycisk główny
        self.assertIn("Krótko", h)
        self.assertIn("<table role=\"presentation\"", h)

    def test_escaping_and_letter(self):
        h = MS.render("<script>", MS.text_to_html("A <b>\n\nhttps://example.com/x"))
        self.assertNotIn("<script>", h)
        self.assertIn('href="https://example.com/x"', h)
        letter = MS.letter("Hej Ago,\nprzypominam się.", "Owca Sebastian")
        self.assertIn("— Owca Sebastian", letter)
        self.assertIn("Hej Ago,<br>przypominam się.", letter)


if __name__ == "__main__":
    unittest.main()
