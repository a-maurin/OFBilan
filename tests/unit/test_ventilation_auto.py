"""Règles de ventilation temporelle en mode ``auto``."""

from __future__ import annotations

import pandas as pd

from bilans.engine import orchestrateur_profils as op
from bilans.engine.generation_pdf_profil import resolve_ventilation_mode_global


def _profile_auto(seuil: int = 366) -> dict:
    return {"periode_analyse": {"ventilation": {"type": "auto", "seuil_jours": seuil}}}


def test_auto_mensuelle_si_duree_inferieure_a_deux_ans() -> None:
    p = _profile_auto()
    d1 = pd.Timestamp("2024-01-01")
    d2 = pd.Timestamp("2025-11-30")
    mode, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert mode == "mensuelle"
    assert resolve_ventilation_mode_global(d1, d2) == "mensuelle"


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


def test_hebdomadaire_si_auto_mensuelle_et_donnees_concentrees_sous_un_an() -> None:
    """Période 2025 calendaire, données seulement juin–juillet → ventilation hebdomadaire."""
    p = _profile_auto()
    d1 = pd.Timestamp("2025-01-01")
    d2 = pd.Timestamp("2025-12-31")
    base, vent_type, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert base == "mensuelle"
    point = pd.DataFrame(
        {
            "date_ctrl": pd.to_datetime(
                ["2025-06-05", "2025-06-12", "2025-07-20"],
            ),
        }
    )
    empty = pd.DataFrame()
    assert op._maybe_override_ventilation_hebdomadaire(
        base, vent_type, d1, d2, point, empty, empty, empty
    ) == "hebdomadaire"


def test_pas_hebdomadaire_si_donnees_couvrent_toute_la_periode() -> None:
    p = _profile_auto()
    d1 = pd.Timestamp("2025-01-01")
    d2 = pd.Timestamp("2025-12-31")
    base, vent_type, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    point = pd.DataFrame({"date_ctrl": pd.to_datetime(["2025-01-01", "2025-12-31"])})
    empty = pd.DataFrame()
    assert op._maybe_override_ventilation_hebdomadaire(
        base, vent_type, d1, d2, point, empty, empty, empty
    ) == "mensuelle"


def test_pas_hebdomadaire_si_ventilation_forcee_mensuelle() -> None:
    """Ventilation explicite ``mensuelle`` : pas de substitution hebdomadaire."""
    p = {"periode_analyse": {"ventilation": {"type": "mensuelle"}}}
    d1 = pd.Timestamp("2025-01-01")
    d2 = pd.Timestamp("2025-12-31")
    base, vent_type, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert base == "mensuelle"
    assert str(vent_type).lower() == "mensuelle"
    point = pd.DataFrame({"date_ctrl": pd.to_datetime(["2025-06-01"])})
    empty = pd.DataFrame()
    assert op._maybe_override_ventilation_hebdomadaire(
        base, vent_type, d1, d2, point, empty, empty, empty
    ) == "mensuelle"


def test_pas_hebdomadaire_si_periode_plus_d_un_an() -> None:
    """Au-delà de 366 jours de périmètre : pas de bascule hebdomadaire même si données clairsemées."""
    p = _profile_auto()
    d1 = pd.Timestamp("2024-01-01")
    d2 = pd.Timestamp("2025-07-01")
    base, vent_type, *_ = op._resolve_ventilation_mode_from_profile(p, date_deb_ts=d1, date_fin_ts=d2)
    assert base == "mensuelle"
    point = pd.DataFrame({"date_ctrl": pd.to_datetime(["2024-06-01", "2024-07-01"])})
    empty = pd.DataFrame()
    assert op._maybe_override_ventilation_hebdomadaire(
        base, vent_type, d1, d2, point, empty, empty, empty
    ) == "mensuelle"
