#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Read vocabulary TSV directly and print hashcards Markdown to stdout.

uv run gen-cards.py 1/1/words.tsv
uv run gen-cards.py --check 1/*/*.tsv 2/*/*.tsv
"""

import argparse
import csv
from pathlib import Path
import sys


def read_vocabulary(path: Path, lang: str | None = None) -> list[dict[str, str]]:
    """TSV: zh, pinyin, one or more translations, optionally ending in pdf_page."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader, None)
        if (not header or len(header) < 3 or header[:2] != ["zh", "pinyin"]
                or len(set(header)) != len(header)
                or any(not key or any(c.isspace() for c in key) for key in header)):
            raise ValueError(f"{path}: expected unique columns zh<TAB>pinyin<TAB><language>... [<TAB>pdf_page]")
        languages = header[2:-1] if header[-1] == "pdf_page" else header[2:]
        if not languages or "pdf_page" in languages:
            raise ValueError(f"{path}: at least one translation column is required; pdf_page must be last")
        if lang is not None and lang not in languages:
            raise ValueError(f"{path}: translation language {lang!r} not found; available: {', '.join(languages)}")
        rows = []
        for number, fields in enumerate(reader, 2):
            if len(fields) != len(header):
                raise ValueError(f"{path}:{number}: expected {len(header)} fields, got {len(fields)}")
            row = dict(zip(header, fields))
            if any(not row[key] or row[key] != row[key].strip() for key in ["zh", "pinyin", *languages]):
                raise ValueError(f"{path}:{number}: required fields must be nonempty and trimmed")
            if any("\r" in value or "\n" in value for value in fields):
                raise ValueError(f"{path}:{number}: multiline fields are not supported")
            page = row.get("pdf_page", "")
            if page and (not page.isascii() or not page.isdecimal() or int(page) < 1):
                raise ValueError(f"{path}:{number}: pdf_page must be a positive integer or empty")
            rows.append(row)
        if not rows:
            raise ValueError(f"{path}: vocabulary is empty")
        return rows


def card(row: dict[str, str], lang: str = "ru") -> str:
    return f"Q: {row['zh']}\nA:\n\n{row['pinyin']}\n\n{row[lang]}\n\n---\n\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", help="Translation column (default: ru when generating; all languages checked otherwise)")
    parser.add_argument("--check", action="store_true", help="Validate only; do not generate cards")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        # Validate every input before emitting any cards; preserve file and row order.
        lang = args.lang
        if not args.check and lang is None:
            lang = "ru"
        rows = [row for path in args.files for row in read_vocabulary(path, lang)]
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f"Error: {exc}\n")
    if args.check:
        print(f"Validated {len(rows)} records in {len(args.files)} files")
    else:
        sys.stdout.write("".join(card(row, lang) for row in rows))


if __name__ == "__main__":
    main()
