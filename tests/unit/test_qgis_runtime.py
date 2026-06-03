"""Tests — découverte Python QGIS et délégation sous-processus."""
from __future__ import annotations

from pathlib import Path

from bilans.cartographie import qgis_runtime


def test_find_qgis_python_from_path_file(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "qgis" / "python.exe"
    fake.parent.mkdir(parents=True)
    fake.write_text("", encoding="utf-8")
    cfg = tmp_path / "scripts" / "windows" / "qgis_python_path.txt"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(str(fake) + "\n", encoding="utf-8")
    monkeypatch.setattr(qgis_runtime, "PROJECT_ROOT", tmp_path)
    qgis_runtime._QGIS_PYTHON_CACHE = None
    found = qgis_runtime.find_qgis_python_executable(refresh=True)
    assert found == fake.resolve()


def test_run_cartography_subprocess_empty_profiles() -> None:
    assert qgis_runtime.run_cartography_export_subprocess([], date_deb="2025-01-01", date_fin="2025-12-31", dept_code="21") is True


def test_run_cartography_subprocess_delegates_to_bat(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    bat = tmp_path / "lancer_production_cartographique.bat"
    bat.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setattr(qgis_runtime.sys, "platform", "win32")
    monkeypatch.setattr(qgis_runtime.subprocess, "run", fake_run)
    monkeypatch.setattr(qgis_runtime, "_cartography_launcher_bat", lambda: bat)

    ok = qgis_runtime.run_cartography_export_subprocess(
        ["global", "global_usagers"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="25",
    )
    assert ok is True
    assert calls
    assert "global,global_usagers" in calls[0]
