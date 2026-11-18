"""PDF tests use optional ReportLab/fontTools/PyMuPDF; no font downloads in tests."""

import importlib.util
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
HAS_PDF_DEPS = all(importlib.util.find_spec(name) is not None
                   for name in ("reportlab", "fontTools", "pymupdf"))


@unittest.skipUnless(HAS_PDF_DEPS, "PDF tests require reportlab, fonttools and pymupdf")
class PrintCardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymupdf
        import reportlab
        cls.pdf = pymupdf
        cls.api = runpy.run_path(str(ROOT / "print-cards.py"))
        cls.font_path = Path(reportlab.__file__).parent / "fonts/Vera.ttf"
        cls.font = cls.api["register_font"](cls.font_path, "ASCII / 0123456789")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "print-cards.py"), *map(str, args)],
                              capture_output=True, text=True, cwd=self.directory)

    def test_grid_and_back_mapping(self):
        layout = self.api["Layout"]()
        self.assertEqual((layout.columns, layout.rows, layout.capacity), (3, 4, 12))
        self.assertEqual([layout.back_slot(n) for n in range(12)],
                         [2, 1, 0, 5, 4, 3, 8, 7, 6, 11, 10, 9])
        for n in range(12):
            self.assertEqual(layout.back_slot(layout.back_slot(n)), n)
        self.assertEqual(self.api["Layout"](80).capacity, 6)
        for value in (0, 34, 196, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.api["Layout"](value)
        with self.assertRaises(ValueError):
            layout.check_offsets(8, 0)

    def test_front_shrinks_before_wrapping(self):
        layout = self.api["Layout"]()
        width = layout.size - 8 * self.api["mm"]
        height = layout.size - 16 * self.api["mm"]
        # Four wide glyphs barely overflow at 42 pt, like four CJK characters.
        text = "WWWW"
        self.assertGreater(self.api["pdfmetrics"].stringWidth(text, self.font, 42), width)
        wrapped = self.api["fit"](text, self.font, width, height, 42, 18)
        self.assertGreater(len(wrapped.lines), 1)
        card = self.api["Card"](text, "P", "Answer", "Source")
        front = self.api["prepare"]([card], self.font, layout)[0][0]
        self.assertEqual(front.lines, (text,))
        self.assertLess(front.size, 42)
        self.assertGreaterEqual(front.size, 39)
        short = self.api["fit"]("W", self.font, width, height, 42, 18, prefer_one_line=True)
        self.assertEqual(short.size, 42)
        long = self.api["fit"]("W" * 20, self.font, width, height, 42, 18, prefer_one_line=True)
        self.assertGreater(len(long.lines), 1)
        self.assertGreaterEqual(long.size, 18)

    def test_pdf_pairs_partial_sheet_positions_and_embedding(self):
        layout = self.api["Layout"]()
        cards = [self.api["Card"](f"W{n:02d}", f"P{n:02d}", f"Answer {n:02d}", f"Source / #{n}")
                 for n in range(13)]
        data = self.api["render"](cards, self.font, layout)
        with self.pdf.open(stream=data, filetype="pdf") as doc:
            self.assertEqual(len(doc), 4)
            for page in doc:
                self.assertAlmostEqual(page.rect.width, 210 * self.api["mm"], places=2)
                self.assertAlmostEqual(page.rect.height, 297 * self.api["mm"], places=2)
                fonts = page.get_fonts()
                self.assertTrue(fonts)
                self.assertTrue(all(doc.extract_font(font[0])[3] for font in fonts))
            for n in range(13):
                sheet, slot = divmod(n, 12)
                for back, text in ((False, f"W{n:02d}"), (True, f"P{n:02d}")):
                    matches = doc[2 * sheet + back].search_for(text)
                    self.assertEqual(len(matches), 1, text)
                    x, y = layout.origin(layout.back_slot(slot) if back else slot)
                    match = matches[0]
                    self.assertGreaterEqual(match.x0, x)
                    self.assertLessEqual(match.x1, x + layout.size)
                    self.assertGreaterEqual(match.y0, self.api["A4"][1] - y - layout.size)
                    self.assertLessEqual(match.y1, self.api["A4"][1] - y)
            self.assertNotIn("W12", doc[0].get_text())
            self.assertNotIn("P12", doc[1].get_text())

    def test_back_offsets(self):
        layout = self.api["Layout"]()
        cards = [self.api["Card"]("W01", "P01", "Answer", "Label")]
        with self.pdf.open(stream=self.api["render"](cards, self.font, layout), filetype="pdf") as a:
            with self.pdf.open(stream=self.api["render"](cards, self.font, layout, (1, 2)), filetype="pdf") as b:
                p = a[1].search_for("P01")[0]
                q = b[1].search_for("P01")[0]
                self.assertAlmostEqual(q.x0 - p.x0, self.api["mm"], places=2)
                self.assertAlmostEqual(q.y0 - p.y0, -2 * self.api["mm"], places=2)
                self.assertEqual(a[0].get_text(), b[0].get_text())

    def test_number_top_left_and_no_front_context(self):
        layout = self.api["Layout"]()
        cards = [self.api["Card"]("W01", "P01", "Answer", "SECRET SOURCE / Book 2 / Lesson 15", 987)]
        with self.pdf.open(stream=self.api["render"](cards, self.font, layout), filetype="pdf") as doc:
            self.assertNotIn("SECRET", doc[0].get_text())
            self.assertNotIn("Book", doc[0].get_text())
            self.assertNotIn("Lesson", doc[0].get_text())
            self.assertIn("SECRET SOURCE", doc[1].get_text())
            for back in (False, True):
                x, y = layout.origin(layout.back_slot(0) if back else 0)
                matches = doc[int(back)].search_for("987")
                self.assertEqual(len(matches), 1)
                number = matches[0]
                self.assertAlmostEqual(number.x0, x + 4 * self.api["mm"], places=2)
                self.assertLess(number.x1, x + layout.size / 2)
                self.assertLess(number.y1, self.api["A4"][1] - y - layout.size + 10 * self.api["mm"])

    def test_textbook_numbers_independent_of_selected_files(self):
        load = self.api["load_cards"]
        first = load([ROOT / "1/1/words.tsv"], "ru")
        second = load([ROOT / "2/15/words.tsv"], "ru")
        extra = load([ROOT / "2/15/extra-words.tsv"], "ru")
        self.assertEqual([c.number for c in first], list(range(1, 11)))
        self.assertEqual(second[0].number, 525)
        self.assertEqual(second[-1].number, 565)
        self.assertEqual(extra[0].number, 566)
        self.assertEqual(load([ROOT / "2/16/words.tsv"], "ru")[0].number, 578)
        together = load([ROOT / "2/15/extra-words.tsv", ROOT / "2/15/words.tsv"], "ru")
        self.assertEqual([c.number for c in together], [c.number for c in extra + second])
        all_paths = [ROOT / book / str(lesson) / f"{section}.tsv"
                     for book, lessons in (("1", range(1, 15)), ("2", range(15, 27)))
                     for lesson in lessons for section in ("words", "extra-words")
                     if (ROOT / book / str(lesson) / f"{section}.tsv").exists()]
        self.assertEqual([c.number for c in load(all_paths, "ru")], list(range(1, 1235)))

    def test_cli_calibration_and_no_overwrite(self):
        output = self.directory / "test.pdf"
        result = self.cli("--test-sheet", "--font", self.font_path, "-o", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.pdf.open(output) as doc:
            self.assertEqual(len(doc), 2)
            self.assertIn("BACK 12", doc[1].get_text())
        original = output.read_bytes()
        result = self.cli("--test-sheet", "--font", self.font_path, "-o", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), original)

    def test_overflow_missing_language_and_glyphs_do_not_create_pdf(self):
        source = self.directory / "words.tsv"
        output = self.directory / "cards.pdf"
        for text, extra in (
            ("zh\tpinyin\ten\nW\tP\tAnswer\n", []),
            ("zh\tpinyin\ten\n汉\tP\tAnswer\n", ["--lang", "en"]),
            ("zh\tpinyin\ten\nW\tP\t" + "x" * 20000 + "\n", ["--lang", "en"]),
        ):
            source.write_text(text, encoding="utf-8")
            result = self.cli(source, "--font", self.font_path, "-o", output, *extra)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertNotIn("Traceback", result.stderr)

    def test_corrupt_font_cache_is_rejected(self):
        cache = self.directory / "font-cache"
        cache.mkdir()
        (cache / "NotoSansSC-wght.ttf").write_bytes(b"corrupt")
        output = self.directory / "cards.pdf"
        result = self.cli("--test-sheet", "--font-cache", cache, "-o", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stderr)
        self.assertFalse(output.exists())

    @unittest.skipUnless(shutil.which("zsh"), "zsh unavailable; print wrapper smoke test not run")
    def test_zsh_print_wrapper_from_other_directory(self):
        result = subprocess.run(["zsh", "-f", "-c", 'source "$1"\nprint-cards --help\n', "test",
                                 str(ROOT / ".autoenv.zsh")], capture_output=True,
                                text=True, cwd=self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--test-sheet", result.stdout)


if __name__ == "__main__":
    unittest.main()
