# zh-cards

Chinese vocabulary with tone-marked pinyin and multilingual translation columns,
stored as TSV files and converted directly into Markdown decks for
[hashcards](https://github.com/eudoxia0/hashcards).

The vocabulary currently included uses Russian translations; the format and
generator also support other languages and multiple translations per entry.

## Quick start

The normal workflow uses [zsh-autoenv](https://github.com/Tarrasch/zsh-autoenv).
Enable it in your own zsh configuration: entering the project directory loads
`.autoenv.zsh`, and leaving the project subtree runs `.autoenv_leave.zsh` to
remove the helpers. Review the files and authorize them when the plugin asks;
changes to their contents can require renewed authorization.

### With Nix

With [Nix](https://nixos.org/) and flakes enabled, run this from the repository
root. Your zsh configuration should also load the plugin in the development shell:

```zsh
nix develop -c zsh
cd . # Trigger the directory-entry hook when already in the project
mkdir -p cards
gen-words ru 2/15 > cards/Lesson-15.md
hashcards drill cards
```

The development shell provides `hashcards`, `uv`, `zsh`, and `glow` on Linux and macOS
(x86-64 and ARM64). It uses the upstream hashcards flake; dependencies are pinned
in `flake.lock`. Configure zsh-autoenv in your personal shell setup.

### Without Nix

Install [uv](https://docs.astral.sh/uv/) and hashcards separately. In a zsh session
with zsh-autoenv enabled, enter the repository and run:

```zsh
mkdir -p cards
gen-words ru 2/15 > cards/Lesson-15.md
hashcards drill cards
```

The Python scripts use inline dependency metadata (PEP 723), so no project
virtual environment or manual `pip install` is required.

## Vocabulary layout

| Directory | Contents |
| --- | --- |
| `1/1/`–`1/14/` | First textbook, lessons 1–14 |
| `2/15/`–`2/26/` | Second textbook, lessons 15–26 |
| `我一定要找到她…/` | Selected vocabulary from the Chinese Breeze reader |

Each directory contains `words.tsv` and, where applicable, `extra-words.tsv`.
Edit these TSV files directly; the generators read them as input.

### TSV format

Files are UTF-8 with a header and actual tab separators:

```tsv
zh	pinyin	ru
你	nǐ	ты
```

After `zh` and `pinyin`, include one or more translation columns named by language,
such as `ru`, `en`, or `pt-BR`. Russian is not a required column:

```tsv
zh	pinyin	ru	en
你	nǐ	ты	you
```

An optional final column, `pdf_page`, may record the physical, **1-based PDF page number**
(not the printed page label). Second-book files retain these references; the
first-book and reader files currently use three columns.

```tsv
zh	pinyin	ru	pdf_page
得	de	структурная частица	13
```

- Start with `zh` and `pinyin`, followed by translation columns in any order;
  put `pdf_page` last if present. Column names must be unique, nonempty, and
  contain no whitespace. `zh`, `pinyin`, and `pdf_page` are reserved names.
- Chinese, pinyin, and every translation field must be nonempty and have no
  leading or trailing whitespace. Sparse/incomplete translations are not supported.
- Use tone marks rather than tone numbers in pinyin.
- Do not use blank records or tabs/newlines inside fields. Quotes are literal
  characters, not CSV quoting syntax.
- When `pdf_page` is present, page numbers must be positive integers or
  empty. Omit the column entirely if no page references are known for the file.
- Preserve source order and distinct readings or meanings, including repeated
  headwords such as 得/de and 得/děi.

The textbook lists include unnumbered word components and proper names.
Supplementary vocabulary remains separate. Translations include textbook wording
and personal study notes; the lists are not intended as a general-purpose dictionary.

## Generate decks with the zsh helpers

`.autoenv.zsh` defines `gen-words`, `gen-extra-words`, `gen-card`, and `ru-gen-*`.
With zsh-autoenv enabled, enter the project directory and approve the reviewed
files if prompted. The helpers generate decks from TSV without manual uv calls.

From the repository root, after loading the helpers:

```zsh
mkdir -p cards

# Main vocabulary only
gen-words ru 1/1 > cards/Lesson-1.md

# Supplementary vocabulary in a separate deck
gen-extra-words ru 2/15 > cards/Lesson-15-extra.md

# The reader's existing selection
gen-words ru '我一定要找到她…' > cards/Chinese-Breeze.md

# All main-vocabulary decks for book 2, written inside cards/
(cd cards && ru-gen-2-words)
```

| Helper | Behaviour |
| --- | --- |
| `gen-words <lang> [directory ...]` | Print main-vocabulary cards; default directory is the current one |
| `gen-extra-words <lang> [directory ...]` | Print supplementary-vocabulary cards |
| `gen-card <zh> <pinyin> <translation>` | Print one manually supplied card |
| `print-cards <TSV files ...> -o <PDF>` | Generate square duplex flashcards for printing |
| `ru-gen-1-words` | Write main-vocabulary `Lesson-<number>.md` decks for book 1 |
| `ru-gen-2-words` | Write main-vocabulary `Lesson-<number>.md` decks for book 2 |
| `ru-gen-我一定要找到她…-words` | Write the reader's main-vocabulary deck |

Book-wide aliases resolve sources from the repository root and write decks to
the current directory. Only aliases prefixed with `ru-` specifically select
Russian; generic helpers accept any translation language, for example
`gen-words en <directory>` when that TSV has an `en` column.
With the plugin's default leave handling enabled, exiting the project subtree
automatically runs `.autoenv_leave.zsh` and removes the helpers; entering a
subdirectory such as `cards/` keeps them available.

### Without zsh-autoenv / manual debugging

If the plugin is not installed, or when debugging the helper definitions, you
can explicitly run `source .autoenv.zsh` from the repository root in zsh after
reviewing it. In that manual mode, run `source /path/to/zh-cards/.autoenv_leave.zsh`
to remove the helpers when finished. This is a fallback, not the normal
zsh-autoenv workflow.

Create the output directory first. Shell redirection overwrites an existing
deck file. Keep generated decks in a dedicated directory so hashcards does not
read documentation files as decks.

### Direct CLI for automation or non-zsh shells

The same generator can be called without loading shell helpers:

```sh
uv run gen-cards.py 1/1/words.tsv > cards/Lesson-1.md
uv run gen-cards.py 2/15/words.tsv 2/15/extra-words.tsv > cards/Lesson-15.md
```

The generator writes to stdout, preserves the supplied file/row order, and
validates every input before emitting cards. It fails on malformed records
instead of silently skipping them. Select the answer column with `--lang`;
the default is `ru`. For example,
after adding an `en` translation column to a file:

```sh
uv run gen-cards.py --lang en path/to/multilingual.tsv > cards/English-Answers.md
```

The selected language must be present in every input file. A missing column
produces an error listing the available translation languages, not a fallback.

Each card shows Chinese on the front and pinyin plus the selected translation
on the back. With the current Russian data:

```text
Q: 你
A:

nǐ

ты

---
```

Regenerate a deck after editing its TSV. Hashcards identifies cards by their
content, so changing a card can reset its review progress.

## Print square flashcards

With the zsh-autoenv helpers loaded, first generate a calibration sheet:

```zsh
print-cards --test-sheet -o calibration.pdf
```

Then select the vocabulary to print. Supplementary words are included only when
you explicitly supply their TSV file:

```zsh
print-cards 2/15/words.tsv --lang ru -o lesson-15-print.pdf
print-cards 2/15/words.tsv 2/15/extra-words.tsv -o lesson-15-all-print.pdf
```

Without the shell helpers, use `uv run print-cards.py` with the same arguments.
The script shares the TSV reader with `gen-cards.py`; it does not generate or
read intermediate Markdown decks.

### Layout and printer settings

- Default: **65 × 65 mm squares, 12 cards per A4 sheet (3 columns × 4 rows)**,
  with cutting lines.
- Front: large Chinese text and a small number in the upper-left corner, **no
  book/lesson/source hints**. Back: the same number, pinyin, selected translation,
  and a small source/lesson/page label.
- Textbook entries use one continuous sequence across both volumes: lessons in
  numeric order, main words followed by supplementary words within each lesson,
  including components and proper names. Book 2 currently starts at **525**.
  Printing a subset or changing the input-file order does not renumber entries.
  These numbers are derived from the current textbook TSVs, not permanent IDs:
  inserting/deleting earlier entries changes later numbers. Other input files,
  including the reader, use sequential numbers within the selected PDF instead.
- Pages are paired: front 1, back 1, front 2, back 2, etc. Back columns are
  reversed automatically, including unused cells on a partially filled sheet.
- Print on **A4, portrait, actual size / 100%, duplex, flip on the long edge**.
  Do not use fit-to-page, booklet mode, or multiple PDF pages per paper side.
- First print the two calibration pages on one sheet. Match the numbered fronts
  and backs and check the cutting lines against a light before printing a batch.
  Real printer alignment still needs this physical check.

`--size-mm 60` changes the square side to 60 mm; rows and columns are chosen
automatically with at least 7.5 mm outer margins. `--size-mm 80` gives six cards
per sheet (2 × 3). Headwords on the front first shrink from 42 pt down to 18 pt
to stay on a single line, rather than wrapping a final character onto its own
line. Only entries that still cannot fit in one line at 18 pt use multiple lines.
Answers wrap and shrink within minimum font sizes; if text still does not fit,
generation fails with the entry label instead of clipping.
Existing output files are never overwritten.

If your printer consistently shifts the backs, use `--back-offset-x-mm` and
`--back-offset-y-mm`. Positive values move the PDF's back content and cutting
grid right and up respectively; negative values move them left and down.
Start with the calibration sheet and choose corrections based on the result.

### Embedded fonts

By default the first run downloads a pinned, SHA-256-checked
[Noto Sans SC](https://github.com/google/fonts/tree/2894aab31764f10f29c421bdfd2340d3b382d384/ofl/notosanssc)
font (about 17 MB, [SIL Open Font License](https://github.com/google/fonts/blob/2894aab31764f10f29c421bdfd2340d3b382d384/ofl/notosanssc/OFL.txt)).
It is cached in `.cache/print-cards/` (ignored by Git), then embedded/subsetted
into the PDF. After the initial download, the font is available offline.
`--font-cache <directory>` changes the cache location.

Use `--font /path/to/font.ttf` for another embeddable font or offline operation
without downloading the default. It must use TrueType outlines and cover every
character in the selected data and labels, including tone marks. Font collections
and CFF/OpenType outlines are not supported. Unsupported characters or restrictive
embedding flags cause an error rather than silently printing missing-glyph boxes.
Use a font whose license permits embedding. The default font supports the
current Chinese, pinyin, and Russian data; other languages may need another font.

## Extract source PDF pages

Source PDFs are not included in Git. With your local copy available:

```sh
uv run split-pdf.py --info
uv run split-pdf.py --pages 38-39,41-43 --format both --output extracted
uv run split-pdf.py path/to/another.pdf --pages 1-3 --format png --output other-pages
```

The default source is `NPKKYa_-_Uchebnik-2.pdf`. Pages are physical PDF pages,
starting at 1. Exports can be PNG, single-page PDF, or both; PNG defaults to
150 dpi (`--dpi` overrides it). Use `--pages all` to export every page.
Existing outputs are not overwritten, and the original PDF is unchanged.

This script does **not** perform OCR. Check transcriptions against page images:
some PDFs, including the Chinese Breeze reader, have a corrupted text layer.

## Validation and tests

```sh
uv run gen-cards.py --check 1/*/*.tsv 2/*/*.tsv 我一定要找到她…/*.tsv
PYTHONDONTWRITEBYTECODE=1 uv run --no-project python -m unittest -v
```

Tests cover TSV structure, record counts, known corrections, and Markdown
generation. The native shell integration test is skipped if zsh is unavailable.
These checks do not establish transcription accuracy; vocabulary changes still
need comparison with the source.

`--check` without `--lang` validates all translation columns without requiring
Russian. Use `--check --lang en` to additionally require an English column in
every input file. All declared translations must be filled in either mode.

PDF tests additionally need ReportLab, fontTools, and PyMuPDF. Run them with:

```sh
uv run --no-project --with 'reportlab>=4.4,<5' --with 'fonttools>=4.58,<5' \
  --with 'pymupdf>=1.24,<2' python -m unittest -v test_print_cards.py
```

These tests check page size, long-edge front/back matching, partial sheets,
embedded fonts, offsets, overflow rejection, and overwrite protection. They use
a local test font and do not download Noto Sans SC. Without these dependencies,
PDF tests are skipped by the standard-library test run.

To check the Nix environment:

```sh
nix flake check
nix develop -c hashcards --help
```

Generated Markdown decks, PDF/PNG files, and review databases are ignored by Git.
`README.md` and `AGENTS.md` are tracked exceptions to the Markdown ignore rule.
