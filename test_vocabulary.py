"""TSV integrity and regressions for confirmed textbook corrections."""

from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parent
read_vocabulary = runpy.run_path(str(ROOT / "gen-cards.py"))["read_vocabulary"]


def entries(book, lesson, section="words"):
    rows = read_vocabulary(ROOT / str(book) / str(lesson) / f"{section}.tsv")
    return [(r["zh"], r["pinyin"], r["ru"]) for r in rows]


class VocabularyTests(unittest.TestCase):
    def test_all_sources_and_counts(self):
        expected = {ROOT / "1" / str(n) / "words.tsv" for n in range(1, 15)}
        expected |= {ROOT / "1" / str(n) / "extra-words.tsv" for n in range(7, 15)}
        expected |= {ROOT / "2" / str(n) / f"{s}.tsv"
                     for n in range(15, 27) for s in ("words", "extra-words")}
        expected.add(ROOT / "我一定要找到她…/words.tsv")
        actual = set()
        for directory in ("1", "2", "我一定要找到她…"):
            actual.update((ROOT / directory).rglob("*.tsv"))
            for ext in ("zh", "pinyin", "ru"):
                self.assertFalse(list((ROOT / directory).rglob(f"*.{ext}")))
        self.assertEqual(actual, expected)
        counts = {}
        for path in actual:
            with self.subTest(path=path):
                rows = read_vocabulary(path)
                self.assertTrue(path.read_bytes().endswith(b"\n"))
                book = path.relative_to(ROOT).parts[0]
                key = (book, path.stem)
                counts[key] = counts.get(key, 0) + len(rows)
                if book == "2":
                    self.assertTrue(all(1 <= int(r["pdf_page"]) <= 308 for r in rows))
                else:
                    self.assertTrue(all(not r.get("pdf_page") for r in rows))
        self.assertEqual(counts, {
            ("1", "words"): 433, ("1", "extra-words"): 91,
            ("2", "words"): 531, ("2", "extra-words"): 179,
            ("我一定要找到她…", "words"): 9,
        })

    def test_confirmed_corrections_and_distinct_readings(self):
        self.assertIn(("他", "tā", "он"), entries(1, 3))
        for lesson in (4, 7):
            self.assertIn(("马大为", "Mǎ Dàwéi", "Ма Давэй"), entries(1, lesson))
        self.assertIn(("小姐", "xiǎojiě", "девушка; мисс"), entries(1, 5))
        self.assertIn(("四", "sì", "четыре"), entries(1, 5))
        self.assertIn(("律师", "lǜshī", "адвокат"), entries(1, 8, "extra-words"))
        self.assertIn(("面", "miàn", "лапша"), entries(1, 9))
        self.assertEqual([p for zh, p, _ in entries(2, 15) if zh == "得"], ["de", "děi"])


if __name__ == "__main__":
    unittest.main()
