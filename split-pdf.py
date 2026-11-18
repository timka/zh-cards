#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf>=1.24,<2"]
# ///
"""Export physical PDF pages (1-based), without OCR or changing the source.

Examples:
    uv run split-pdf.py --info
    uv run split-pdf.py --pages 3,10-12 --format both
    uv run split-pdf.py --pages all --format pdf
"""

import argparse
from pathlib import Path

import pymupdf


def parse_pages(spec: str, count: int) -> list[int]:
    if spec.strip().lower() == "all":
        return list(range(1, count + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        bounds = part.strip().split("-")
        if len(bounds) not in (1, 2) or not all(x.isdecimal() for x in bounds):
            raise ValueError(f"Invalid page range: {part!r}")
        first, last = int(bounds[0]), int(bounds[-1])
        if not 1 <= first <= last <= count:
            raise ValueError(f"Page range must be within 1..{count}: {part!r}")
        pages.update(range(first, last + 1))
    return sorted(pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", nargs="?", type=Path, default=Path("NPKKYa_-_Uchebnik-2.pdf"))
    parser.add_argument("--info", action="store_true", help="Show page count; do not export")
    parser.add_argument("--pages", help="Physical page numbers, e.g. 3,10-12 or all (not printed page labels)")
    parser.add_argument("--output", type=Path, help="Output directory (default: <source stem>-pages)")
    parser.add_argument("--format", choices=("png", "pdf", "both"), default="png")
    parser.add_argument("--dpi", type=int, default=150, help="PNG resolution (default: 150)")
    args = parser.parse_args()
    if args.dpi <= 0:
        parser.error("--dpi must be positive")
    if not args.info and not args.pages:
        parser.error("Specify --info or --pages (use --pages all to export everything)")
    try:
        with pymupdf.open(args.source) as doc:
            if not doc.is_pdf:
                raise ValueError("Source must be a PDF")
            if doc.needs_pass:
                raise ValueError("Password-protected PDFs are not supported")
            print(f"{args.source}: {len(doc)} pages")
            if args.info:
                return
            pages = parse_pages(args.pages, len(doc))
            output = args.output or args.source.with_name(args.source.stem + "-pages")
            extensions = ("png", "pdf") if args.format == "both" else (args.format,)
            targets = [(n, ext, output / f"page-{n:04d}.{ext}") for n in pages for ext in extensions]
            for _, _, target in targets:
                if target.exists() or target.is_symlink():
                    raise ValueError(f"Refusing to overwrite: {target}")
            output.mkdir(parents=True, exist_ok=True)
            for number, ext, target in targets:
                # Exclusive creation also protects against concurrent exporters.
                with target.open("xb") as stream:
                    if ext == "png":
                        pix = doc[number - 1].get_pixmap(dpi=args.dpi, colorspace=pymupdf.csRGB, alpha=False)
                        stream.write(pix.tobytes("png"))
                    else:
                        with pymupdf.open() as single:
                            single.insert_pdf(doc, from_page=number - 1, to_page=number - 1)
                            stream.write(single.tobytes(garbage=4, deflate=True))
                print(target)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
