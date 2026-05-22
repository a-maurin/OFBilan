"""Analyse rapide du rapport d'activité OFB 2024 (référence brochure)."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz

PDF = Path(r"c:\Users\aguirre.maurin\Downloads\rapport-activites-ofb2024.pdf")
OUT = Path(__file__).resolve().parents[1] / "data" / "out" / "_ref_rapport_ofb2024"


def main() -> None:
    doc = fitz.open(PDF)
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
