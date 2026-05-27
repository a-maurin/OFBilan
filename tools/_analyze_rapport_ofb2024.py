"""Analyse rapide du rapport d'activité OFB 2024 (référence brochure)."""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "data" / "out" / "_ref_rapport_ofb2024"
DEFAULT_PDF = OUT / "rapport-activites-ofb2024.pdf"


def _pdf_path() -> Path:
    override = os.environ.get("RAPPORT_OFB2024_PDF", "").strip()
    return Path(override) if override else DEFAULT_PDF


def main() -> None:
    pdf = _pdf_path()
    if not pdf.is_file():
        print(
            f"PDF introuvable : {pdf}\n"
            "Placez le fichier sous data/out/_ref_rapport_ofb2024/ "
            "ou définissez RAPPORT_OFB2024_PDF.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    doc = fitz.open(pdf)
    print("pages", doc.page_count)
    fills = Counter()
    for i in range(doc.page_count):
        for d in doc[i].get_drawings():
            if d.get("fill"):
                fills[str(d["fill"])] += 1
    print("top fills", fills.most_common(12))

    for i in [21, 22, 23, 26, 27, 30]:
        if i < doc.page_count:
            doc[i].get_pixmap(matrix=fitz.Matrix(0.28, 0.28)).save(OUT / f"page_{i + 1:02d}.png")

    for i in range(doc.page_count):
        for b in doc[i].get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    if s.get("size", 0) >= 18 and re.search(r"\d", s.get("text", "")):
                        print(
                            i + 1,
                            round(s["size"], 1),
                            hex(s.get("color", 0)),
                            s.get("font"),
                            s.get("text", "")[:50],
                        )
                        break
    doc.close()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    main()
