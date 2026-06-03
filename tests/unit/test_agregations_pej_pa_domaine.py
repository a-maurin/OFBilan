"""Régression : PA dérivées des contrôles à manquement (bilan global)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bilans.engine.agregations_profil import analyse_pej_pa_global


def test_pa_par_domaine_depuis_controles_manquement(tmp_path: Path) -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["dc1", "dc2", "dc3"],
            "date_ctrl": pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]),
            "resultat": ["Manquement", "Manquement et infraction", "Conforme"],
            "domaine": ["Eau", "Faune", "Flore"],
            "theme": ["Th1", "Th2", "Th3"],
        }
    )
    pej = pd.DataFrame(
        {
            "ENTITE_ORIGINE_PROCEDURE": ["SD21", "SD21"],
            "DC_ID": ["p1", "p2"],
            "DOMAINE": ["A", "B"],
        }
    )
    pa_ods = pd.DataFrame({"DC_ID": ["dc1"]})
    analyse_pej_pa_global(
        tmp_path,
        point,
        pa_ods,
        pej,
        tmp_path,
        echelle="departement",
        code="21",
    )
    pa_dom = pd.read_csv(tmp_path / "pa_global_par_domaine.csv", sep=";")
    assert len(pa_dom) == 2
    assert int(pa_dom["nb_pa"].sum()) == 2
    resume = pd.read_csv(tmp_path / "pa_global_resume.csv", sep=";")
    assert int(resume.iloc[0]["nb_pa_global"]) == 2
