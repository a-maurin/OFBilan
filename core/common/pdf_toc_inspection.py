"""Extraction légère des titres de sections depuis un PDF généré (tests d'intégration)."""
from __future__ import annotations

import re
from pathlib import Path

_SECTION_HEADING_RE = re.compile(
    r"^(\d+(?:\.\d+)*\.)\s+(.+)$",
)


def extract_pdf_section_headings(pdf_path: Path) -> list[str]:
    """
    Retourne les titres de sections repérés dans le corps du PDF (lignes « N. … »).

    Ignore le sommaire autant que possible en ne conservant que les occurrences
    après la première apparition de chaque préfixe numérique (corps du document).
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("pypdf requis pour l'inspection TOC (dépendance dev).") from exc

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    seen_prefix: set[str] = set()
    headings: list[str] = []
    for line in lines:
        match = _SECTION_HEADING_RE.match(line)
        if not match:
            continue
        prefix, title = match.group(1), match.group(2).strip()
        full = f"{prefix} {title}".strip()
        if prefix in seen_prefix:
            continue
        seen_prefix.add(prefix)
        headings.append(full)
    return headings


def assert_section_headings_order(
    headings: list[str],
    expected_substrings: list[str],
) -> None:
    """Vérifie que chaque fragment attendu apparaît dans l'ordre dans ``headings``."""
    pos = -1
    for fragment in expected_substrings:
        idx = next((i for i, h in enumerate(headings) if fragment in h), -1)
        assert idx >= 0, f"Titre introuvable contenant « {fragment} » dans {headings!r}"
        assert idx > pos, (
            f"Ordre invalide pour « {fragment} » (index {idx}, précédent {pos}) : {headings!r}"
        )
        pos = idx
