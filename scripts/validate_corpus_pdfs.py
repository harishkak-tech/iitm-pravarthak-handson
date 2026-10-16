"""Validate extracted styled-PDF content against the UTF-8 corpus sources."""

from collections import Counter
from pathlib import Path
import re

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def main():
    total_pages = 0
    files = sorted((ROOT / "docs/corpus_txt").glob("*.txt"))
    for path in files:
        source = path.read_text(encoding="utf-8")
        counts = Counter(p.strip() for p in re.split(r"\n\s*\n", source) if p.strip())
        assert all(n == 1 for n in counts.values()), f"Duplicate paragraph: {path.name}"
        source = "\n".join(line for line in source.splitlines() if not re.fullmatch(r"[-=]+", line))
        with pymupdf.open(ROOT / "docs/corpus_pdf_styled" / (path.stem + ".pdf")) as pdf:
            extracted = "\n".join(
                page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, page.rect.height - 40))
                for page in pdf
            )
            expected, actual = source.split(), extracted.split()
            if expected != actual:
                position = next((i for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]), min(len(expected), len(actual)))
                raise AssertionError(f"PDF text mismatch: {path.name} at {position}: {expected[position:position+8]!r} vs {actual[position:position+8]!r}")
            total_pages += len(pdf)
            print(f"Verified {path.name}: {len(pdf)} pages")
    print(f"Validated {len(files)} PDFs ({total_pages} pages), exact text order and no duplicate paragraphs")


if __name__ == "__main__":
    main()
