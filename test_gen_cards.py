"""Standard-library tests: uv run --no-project python -m unittest -v."""

import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "gen-cards.py"
_script = runpy.run_path(str(SCRIPT))
card = _script["card"]
read_vocabulary = _script["read_vocabulary"]


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def fixture(self, text, name="words.tsv"):
        path = self.directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, cwd=self.directory)

    def test_exact_legacy_markdown_and_optional_page(self):
        path = self.fixture("zh\tpinyin\tru\tpdf_page\n你\tnǐ\tты\t27\n")
        expected = "Q: 你\nA:\n\nnǐ\n\nты\n\n---\n\n"
        self.assertEqual(card(read_vocabulary(path)[0]), expected)
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)
        path = self.fixture("zh\tpinyin\tru\n你\tnǐ\tты\n")
        self.assertEqual(self.run_cli(path).stdout, expected)

    def test_check_only_and_file_order(self):
        a = self.fixture("zh\tpinyin\tru\n得\tde\tчастица\n得\tděi\tнадо\n")
        b = self.fixture("zh\tpinyin\tru\tpdf_page\n你\tnǐ\tты\t\n", "extra words.tsv")
        result = self.run_cli("--check", a, b)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 records in 2 files", result.stdout)
        self.assertNotIn("Q:", result.stdout)
        self.assertEqual(self.run_cli(a, b).stdout,
                         "".join(card(row) for p in (a, b) for row in read_vocabulary(p)))

    def test_literal_quotes_and_pipes(self):
        path = self.fixture('zh\tpinyin\tru\n你\tnǐ\t"ты" | вы\n')
        self.assertEqual(read_vocabulary(path)[0]["ru"], '"ты" | вы')

    def test_multilingual_selection_and_metadata(self):
        path = self.fixture("zh\tpinyin\tru\ten\tpdf_page\n你\tnǐ\tты\tyou\t27\n")
        result = self.run_cli("--lang", "en", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Q: 你\nA:\n\nnǐ\n\nyou\n\n---\n\n")
        self.assertEqual(self.run_cli(path).stdout, "Q: 你\nA:\n\nnǐ\n\nты\n\n---\n\n")
        for lang in ("zh", "pinyin", "pdf_page", "de", ""):
            result = self.run_cli("--lang", lang, path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("available: ru, en", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_non_russian_file_and_language_neutral_check(self):
        path = self.fixture("zh\tpinyin\tpt-BR\ten\n你\tnǐ\tvocê\tyou\n")
        for args in (("--check", path), ("--check", "--lang", "pt-BR", path),
                     ("--lang", "pt-BR", path)):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("você", self.run_cli("--lang", "pt-BR", path).stdout)
        result = self.run_cli(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'ru' not found", result.stderr)
        self.assertNotEqual(self.run_cli("--check", "--lang", "ru", path).returncode, 0)

    def test_missing_language_in_later_file_has_no_partial_output(self):
        first = self.fixture("zh\tpinyin\ten\n你\tnǐ\tyou\n", "first.tsv")
        second = self.fixture("zh\tpinyin\tru\n我\twǒ\tя\n")
        result = self.run_cli("--lang", "en", first, second)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.run_cli("--check", first, second).returncode, 0)

    def test_reject_invalid_input_without_partial_cards(self):
        good = self.fixture("zh\tpinyin\tru\n你\tnǐ\tты\n", "good.tsv")
        for text in (
            "", "ru\tpinyin\tzh\nты\tnǐ\t你\n", "zh\tpinyin\tru\n",
            "zh\tpinyin\tru\n\n", "zh\tpinyin\tru\n你\t\tты\n",
            "zh\tpinyin\tru\n你\tnǐ\n", "zh\tpinyin\tru\n你\tnǐ\tты\textra\n",
            "zh\tpinyin\tru\n 你\tnǐ\tты\n",
            "zh\tpinyin\tru\tpdf_page\n你\tnǐ\tты\t0\n",
            "zh\tpinyin\tru\tpdf_page\n你\tnǐ\tты\t 1\n",
            "zh\tpinyin\n你\tnǐ\n",
            "zh\tpinyin\tpdf_page\n你\tnǐ\t27\n",
            "zh\tpinyin\tru\tru\n你\tnǐ\tты\tты\n",
            "zh\tpinyin\tru\tzh\n你\tnǐ\tты\t你\n",
            "zh\tpinyin\t\n你\tnǐ\tты\n",
            "zh\tpinyin\t en\n你\tnǐ\tyou\n",
            "zh\tpinyin\tpdf_page\ten\n你\tnǐ\t27\tyou\n",
            "zh\tpinyin\tru\ten\n你\tnǐ\tты\t\n",
        ):
            with self.subTest(text=text):
                bad = self.fixture(text)
                result = self.run_cli(good, bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
        self.assertNotEqual(self.run_cli(good, self.directory / "absent.tsv").returncode, 0)
        self.assertNotEqual(self.run_cli("--lang", "en", good).returncode, 0)

    @unittest.skipUnless(shutil.which("zsh"), "zsh unavailable; native shell smoke test not run")
    def test_zsh_wrapper_from_other_directory(self):
        result = subprocess.run(["zsh", "-f", "-c",
                                 # Parse alias use only after sourcing its definition.
                                 'source "$1"\neval \'gen-words ru "$2"\'\n', "test",
                                 str(ROOT / ".autoenv.zsh"), str(ROOT / "1/1")],
                                capture_output=True, text=True, cwd=self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = "".join(card(row) for row in read_vocabulary(ROOT / "1/1/words.tsv"))
        self.assertEqual(result.stdout, expected)
        self.fixture("zh\tpinyin\ten\n你\tnǐ\tyou\n")
        result = subprocess.run(["zsh", "-f", "-c",
                                 'source "$1"\neval \'gen-words en "$2"\'\n', "test",
                                 str(ROOT / ".autoenv.zsh"), str(self.directory)],
                                capture_output=True, text=True, cwd=self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Q: 你\nA:\n\nnǐ\n\nyou\n\n---\n\n")


if __name__ == "__main__":
    unittest.main()
