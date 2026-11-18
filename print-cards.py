#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["reportlab>=4.4,<5", "fonttools>=4.58,<5"]
# ///
"""Square A4 flashcards, paired front/back pages for long-edge duplex printing.

uv run print-cards.py --test-sheet -o calibration.pdf
uv run print-cards.py 2/15/words.tsv --lang ru -o lesson-15-print.pdf
Print at actual size (100%), portrait, duplex, flip on the LONG edge.
"""

import argparse
from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
import runpy
import sys
import urllib.request

from fontTools.ttLib import TTFont as SourceFont, TTLibError
from fontTools.varLib.instancer import instantiateVariableFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "2894aab31764f10f29c421bdfd2340d3b382d384/ofl/notosanssc/"
            "NotoSansSC%5Bwght%5D.ttf")
FONT_SHA256 = "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da"
FONT_LICENSE = "https://github.com/google/fonts/blob/2894aab31764f10f29c421bdfd2340d3b382d384/ofl/notosanssc/OFL.txt"


@dataclass(frozen=True)
class Layout:
    size_mm: float = 65

    def __post_init__(self):
        if not math.isfinite(self.size_mm) or not 35 <= self.size_mm <= 195:
            raise ValueError("--size-mm must be between 35 and 195")

    @property
    def size(self):
        return self.size_mm * mm

    @property
    def columns(self):
        return math.floor((A4[0] - 15 * mm) / self.size + 1e-8)

    @property
    def rows(self):
        return math.floor((A4[1] - 15 * mm) / self.size + 1e-8)

    @property
    def capacity(self):
        return self.columns * self.rows

    @property
    def left(self):
        return (A4[0] - self.columns * self.size) / 2

    @property
    def bottom(self):
        return (A4[1] - self.rows * self.size) / 2

    def back_slot(self, slot):
        row, column = divmod(slot, self.columns)
        return row * self.columns + self.columns - 1 - column

    def origin(self, slot):
        row, column = divmod(slot, self.columns)
        return (self.left + column * self.size,
                self.bottom + (self.rows - 1 - row) * self.size)

    def check_offsets(self, x, y):
        if not all(math.isfinite(n) for n in (x, y)):
            raise ValueError("Back offsets must be finite numbers")
        if abs(x) > self.left / mm or abs(y) > self.bottom / mm:
            raise ValueError("Back offset would move the cutting grid outside the page")


def default_font(cache: Path) -> Path:
    """Download only the pinned, hash-checked OFL font into the project cache."""
    target = cache / "NotoSansSC-wght.ttf"
    if target.exists():
        data = target.read_bytes()
    else:
        print("Downloading Noto Sans SC (17 MB) to " + str(target), file=sys.stderr)
        with urllib.request.urlopen(FONT_URL, timeout=60) as response:
            data = response.read(32 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != FONT_SHA256:
            raise ValueError("Downloaded font checksum mismatch; no font cached")
        cache.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != FONT_SHA256:
        raise ValueError(f"Cached font checksum mismatch: {target}; remove it explicitly or use --font")
    return target


def register_font(path: Path, text: str) -> str:
    """Embed TrueType outlines and reject missing glyphs rather than print tofu."""
    with SourceFont(path, recalcTimestamp=False) as source:
        if "glyf" not in source:
            raise ValueError("--font must have TrueType outlines (a .ttf, not CFF/OpenType or a collection)")
        if "OS/2" in source and source["OS/2"].fsType & (0x2 | 0x100 | 0x200):
            raise ValueError("Font licensing flags prohibit the outline embedding/subsetting required here")
        cmap = source.getBestCmap()
        if not cmap:
            raise ValueError("Font has no Unicode character map")
        missing = sorted({c for c in text if not c.isspace() and ord(c) not in cmap})
        if missing:
            examples = " ".join(f"{c!r} (U+{ord(c):04X})" for c in missing[:12])
            raise ValueError(f"Font {path.name} lacks glyphs: {examples}; choose another --font")
        if "fvar" in source:
            axes = {axis.axisTag: (min(axis.maxValue, max(axis.minValue, 400))
                                  if axis.axisTag == "wght" else axis.defaultValue)
                    for axis in source["fvar"].axes}
            instantiateVariableFont(source, axes, inplace=True)
        font_bytes = io.BytesIO()
        source.save(font_bytes)
    name = "PrintCards-" + hashlib.sha256(font_bytes.getvalue()).hexdigest()[:16]
    font_bytes.seek(0)
    pdfmetrics.registerFont(TTFont(name, font_bytes))
    return name


def wrap(text, font, size, width):
    """Wrap at spaces; split overlong tokens, including Chinese, by character."""
    lines = []
    line = ""
    for word in text.split():
        candidate = (line + " " + word) if line else word
        if pdfmetrics.stringWidth(candidate, font, size) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        for character in word:
            if pdfmetrics.stringWidth(character, font, size) > width:
                return None
            if line and pdfmetrics.stringWidth(line + character, font, size) > width:
                lines.append(line)
                line = ""
            line += character
    if line:
        lines.append(line)
    return lines


@dataclass(frozen=True)
class TextBlock:
    lines: tuple[str, ...]
    size: float
    ascent: float
    descent: float
    leading: float

    @property
    def height(self):
        return self.ascent - self.descent + (len(self.lines) - 1) * self.leading


def block(text, font, size, width):
    lines = wrap(text, font, size, width)
    if not lines:
        return None
    ascent, descent = pdfmetrics.getAscentDescent(font, size)
    return TextBlock(tuple(lines), size, ascent, descent, max(size * 1.25, ascent - descent))


def fit(text, font, width, height, largest, smallest, prefer_one_line=False):
    # Keep a headword together before considering a larger, wrapped rendering.
    for single_line in ((True, False) if prefer_one_line else (False,)):
        for step in range(round((largest - smallest) * 2) + 1):
            result = block(text, font, largest - step * 0.5, width)
            if (result and result.height <= height
                    and (not single_line or len(result.lines) == 1)):
                return result
    raise ValueError("Text does not fit at the minimum font size")


@dataclass(frozen=True)
class Card:
    front: str
    pinyin: str
    translation: str
    label: str
    number: int | None = None


def textbook_offsets(read):
    """One sequence across both volumes, independent of selected input files."""
    offsets = {}
    count = 0
    for book, lessons in (("1", range(1, 15)), ("2", range(15, 27))):
        for lesson in lessons:
            for section in ("words", "extra-words"):
                path = ROOT / book / str(lesson) / f"{section}.tsv"
                if section == "extra-words" and not path.exists():
                    continue
                offsets[path.resolve()] = count
                count += len(read(path))
    return offsets


def load_cards(paths, lang):
    read = runpy.run_path(str(ROOT / "gen-cards.py"))["read_vocabulary"]
    paths = list(paths)
    is_textbook = lambda p: any(p.resolve().is_relative_to(ROOT / book) for book in ("1", "2"))
    offsets = textbook_offsets(read) if any(is_textbook(p) for p in paths) else {}
    result = []
    for path in paths:
        if path.parent.parent.name in ("1", "2") and path.parent.name.isdecimal():
            label = f"Book {path.parent.parent.name} / Lesson {path.parent.name} / {path.stem}"
        else:
            label = f"{path.parent.name} / {path.stem}"
        for index, row in enumerate(read(path, lang), 1):
            page = f" / PDF {row['pdf_page']}" if row.get("pdf_page") else ""
            number = offsets[path.resolve()] + index if path.resolve() in offsets else len(result) + 1
            result.append(Card(row["zh"], row["pinyin"], row[lang], f"{label} / #{number}{page}", number))
    return result


def calibration_cards(layout):
    return [Card(f"FRONT {n:02d}", f"BACK {n:02d}",
                 f"The reverse must say FRONT {n:02d}. Check all four edges before cutting.",
                 f"Calibration / card {n:02d}", n) for n in range(1, layout.capacity + 1)]


def prepare(cards, font, layout):
    """Preflight every text block before any output file is created."""
    width = layout.size - 8 * mm
    height = layout.size - 16 * mm
    plans = []
    for item in cards:
        try:
            front = fit(item.front, font, width, height, 42, 18, prefer_one_line=True)
            label = fit(item.label, font, width, 8 * mm, 6, 4.5)
            for step in range(21):
                scale = 1 - step * 0.02
                pinyin = block(item.pinyin, font, 16 * scale, width)
                translation = block(item.translation, font, 12 * scale, width)
                if pinyin and translation and pinyin.height + 3 * mm + translation.height <= height - 4 * mm:
                    break
            else:
                raise ValueError("Answer does not fit (minimum pinyin 9.6 pt, translation 7.2 pt)")
            plans.append((front, pinyin, translation, label))
        except ValueError as exc:
            raise ValueError(f"{item.label} ({item.front}): {exc}; use a larger --size-mm or shorten the entry") from exc
    return plans


def draw_block(pdf, text, font, center_x, top):
    pdf.setFont(font, text.size)
    baseline = top - text.ascent
    for line in text.lines:
        pdf.drawCentredString(center_x, baseline, line)
        baseline -= text.leading


def render(cards, font, layout, offsets=(0, 0)):
    plans = prepare(cards, font, layout)
    sheets = math.ceil(len(cards) / layout.capacity)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, invariant=1, pageCompression=1, initialFontName=font)
    pdf.setTitle("Chinese vocabulary - square duplex flashcards")
    pdf.setAuthor("zh-cards")
    for sheet in range(sheets):
        for back in (False, True):
            dx, dy = (offsets[0] * mm, offsets[1] * mm) if back else (0, 0)
            pdf.setFillGray(0.35)
            pdf.setFont(font, 7)
            side = "BACK" if back else "FRONT"
            pdf.drawCentredString(A4[0] / 2, A4[1] - 5 * mm, f"TOP - {side} - sheet {sheet + 1}/{sheets}")
            pdf.drawCentredString(A4[0] / 2, 3 * mm, "A4 portrait / Actual size 100% / Duplex: flip on LONG edge")
            pdf.setStrokeGray(0.7)
            pdf.setLineWidth(0.3)
            for col in range(layout.columns + 1):
                x = layout.left + col * layout.size + dx
                pdf.line(x, layout.bottom + dy, x, layout.bottom + layout.rows * layout.size + dy)
            for row in range(layout.rows + 1):
                y = layout.bottom + row * layout.size + dy
                pdf.line(layout.left + dx, y, layout.left + layout.columns * layout.size + dx, y)
            first = sheet * layout.capacity
            for slot, (front, pinyin, translation, label) in enumerate(plans[first:first + layout.capacity]):
                x, y = layout.origin(layout.back_slot(slot) if back else slot)
                x += dx
                y += dy
                center = x + layout.size / 2
                pdf.setFillGray(0.4)
                number = cards[first + slot].number
                pdf.setFont(font, 8)
                pdf.drawString(x + 4 * mm, y + layout.size - 4 * mm - pdfmetrics.getAscent(font, 8),
                               str(number if number is not None else first + slot + 1))
                pdf.setFillGray(0)
                if back:
                    pdf.setFillGray(0.4)
                    draw_block(pdf, label, font, center, y + 4 * mm + (8 * mm + label.height) / 2)
                    pdf.setFillGray(0)
                    content_bottom = y + 12 * mm
                    height = layout.size - 20 * mm
                    total = pinyin.height + 3 * mm + translation.height
                    top = content_bottom + (height + total) / 2
                    draw_block(pdf, pinyin, font, center, top)
                    draw_block(pdf, translation, font, center, top - pinyin.height - 3 * mm)
                else:
                    draw_block(pdf, front, font, center, y + (layout.size + front.height) / 2)
            pdf.showPage()
    pdf.save()
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--lang", default="ru", help="Translation column (default: ru)")
    parser.add_argument("--size-mm", type=float, default=65, help="Square side, 35..195 mm (default: 65)")
    parser.add_argument("--test-sheet", action="store_true", help="Numbered front/back calibration sheet, no TSV required")
    parser.add_argument("--font", type=Path, help="Custom embeddable TrueType font; must cover all input characters")
    parser.add_argument("--font-cache", type=Path, default=ROOT / ".cache/print-cards",
                        help="Cache for the pinned Noto Sans SC font (first run downloads it)")
    parser.add_argument("--back-offset-x-mm", type=float, default=0, help="Shift backs right (+) or left (-)")
    parser.add_argument("--back-offset-y-mm", type=float, default=0, help="Shift backs up (+) or down (-)")
    args = parser.parse_args()
    if args.test_sheet == bool(args.files):
        parser.error("Supply TSV files or --test-sheet, not both")
    try:
        layout = Layout(args.size_mm)
        layout.check_offsets(args.back_offset_x_mm, args.back_offset_y_mm)
        if args.output.exists() or args.output.is_symlink():
            raise ValueError(f"Refusing to overwrite: {args.output}")
        cards = calibration_cards(layout) if args.test_sheet else load_cards(args.files, args.lang)
        all_text = " ".join(f"{c.front} {c.pinyin} {c.translation} {c.label}" for c in cards)
        all_text += " TOP - FRONT BACK sheet 0123456789/ A4 portrait Actual size 100% Duplex: flip on LONG edge"
        font = register_font(args.font or default_font(args.font_cache), all_text)
        data = render(cards, font, layout, (args.back_offset_x_mm, args.back_offset_y_mm))
        with args.output.open("xb") as stream:
            stream.write(data)
        sheets = math.ceil(len(cards) / layout.capacity)
        print(f"{args.output}: {len(cards)} cards, {layout.columns}x{layout.rows}, "
              f"{layout.size_mm:g} mm squares, {sheets} sheets / {sheets * 2} PDF pages")
    except (OSError, ValueError, RuntimeError, TTLibError, TTFError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
