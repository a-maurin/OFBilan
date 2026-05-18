"""Règles de ventilation temporelle en mode ``auto``."""

from __future__ import annotations

import pandas as pd

from bilans.engine import orchestrateur_profils as op
from bilans.engine.generation_pdf_profil import resolve_ventilation_mode_global
from bilans.engine.ventilation_temporelle import (
    VENTILATION_JOURS_DEUX_ANS,
    VENTILATION_JOURS_UN_AN,
    resolve_ventilation_auto,
)


def _profile_auto(seuil: int = 366) -> dict:
    return {"periode_analyse": {"ventilation": {"type": "auto", "seuil_jours": seuil}}}


def test_hebdomadaire_si_duree_inferieure_ou_egale_a_un_an() -> None:
    d1 = pd.Timestamp("2025-01-01")
    d2 = pd.Timestamp("2025-12-31")
    assert (d2 - d1).days == 364
    mode, *_ = op._resolve_ventilation_mode_from_profile(_profile_auto(), date_deb_ts=d1, date_fin_ts=d2)
    assert mode == "hebdomadaire"
    assert resolve_ventilation_mode_global(d1, d2) == "hebdomadaire"


def test_hebdomadaire_a_exactement_un_an() -> None:
    """Année civile 2024 → 2025 (366 j, année bissextile) : hebdomadaire."""
    d1 = pd.Timestamp("2024-01-01")
    d2 = pd.Timestamp("2025-01-01")
    assert (d2 - d1).days == VENTILATION_JOURS_UN_AN
    assert resolve_ventilation_auto((d2 - d1).days) == "hebdomadaire"


def test_hebdomadaire_a_six_mois() -> None:
    d1 = pd.Timestamp("2025-01-01")
    d2 = pd.Timestamp("2025-07-01")
    assert (d2 - d1).days < VENTILATION_JOURS_UN_AN
    assert resolve_ventilation_auto((d2 - d1).days) == "hebdomadaire"


def test_mensuelle_entre_un_an_et_deux_ans() -> None:
    p = _profile_auto()
    d1 = pd.Timestamp("2024-01-01")
    d2 = pd.Timestamp("2025-11-30")
    mode, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert mode == "mensuelle"
    assert resolve_ventilation_mode_global(d1, d2) == "mensuelle"


def test_trimestrielle_a_exactement_deux_ans() -> None:
    d1 = pd.Timestamp("2018-01-01")
    d2 = pd.Timestamp("2020-01-01")
    assert (d2 - d1).days == VENTILATION_JOURS_DEUX_ANS
    assert resolve_ventilation_auto((d2 - d1).days, seuil_jours=366) == "trimestrielle"


def test_auto_trimestrielle_si_duree_entre_deux_ans_et_seuil() -> None:
    """Avec un seuil > 2 ans, une période ≥ 2 ans mais ≤ seuil reste trimestrielle."""
    p = {"periode_analyse": {"ventilation": {"type": "auto", "seuil_jours": 800}}}
    d1 = pd.Timestamp("2020-01-01")
    d2 = pd.Timestamp("2022-01-10")
    mode, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert mode == "trimestrielle"


def test_auto_annuelle_si_duree_au_dela_du_seuil() -> None:
    p = {"periode_analyse": {"ventilation": {"type": "auto", "seuil_jours": 800}}}
    d1 = pd.Timestamp("2010-01-01")
    d2 = pd.Timestamp("2025-01-01")
    mode, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert mode == "annuelle"


def test_ventilation_forcee_mensuelle() -> None:
    p = {"periode_analyse": {"ventilation": {"type": "mensuelle"}}}
    d1 = pd.Timestamp("2025-01-01")
    d2 = pd.Timestamp("2025-12-31")
    mode, vent_type, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert mode == "mensuelle"
    assert str(vent_type).lower() == "mensuelle"
