"""Tests des utilitaires du script tools/audit_pve_totaux.py (sans données sources)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def audit_pve_mod():
    path = ROOT / "tools" / "audit_pve_totaux.py"
    spec = importlib.util.spec_from_file_location("audit_pve_totaux", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_list_pve_detail_csv_paths_excludes_zone_exports(tmp_path: Path, audit_pve_mod) -> None:
    (tmp_path / "pve_foo_detail.csv").write_text("h\n1\n", encoding="utf-8")
    (tmp_path / "pve_foo_par_zone.csv").write_text("h\n2\n", encoding="utf-8")
    names = [p.name for p in audit_pve_mod.list_pve_detail_csv_paths(tmp_path)]
    assert names == ["pve_foo_detail.csv"]


def test_count_csv_body_rows_utf8_with_header(tmp_path: Path, audit_pve_mod) -> None:
    p = tmp_path / "t.csv"
    p.write_text("a;b\n1;2\n3;4\n", encoding="utf-8")
    assert audit_pve_mod.count_csv_body_rows(p) == 2
