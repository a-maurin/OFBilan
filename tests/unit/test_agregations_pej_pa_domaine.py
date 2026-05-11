"""Régression : PA/PEJ par domaine sans colonne DOMAINE dans l'export OSCEAN."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bilans.engine.agregations_profil import analyse_pej_pa_global


def test_pa_par_domaine_quand_colonne_domaine_absente(tmp_path: Path) -> None:
    point = pd.DataFrame({"dc_id": ["dc1", "dc2"]})
    pej = pd.DataFrame(
        {
            "ENTITE_ORIGINE_PROCEDURE": ["SD21", "SD21"],
            "DC_ID": ["p1", "p2"],
            "DOMAINE": ["A", "B"],
        }
    )
    pa = pd.DataFrame(
        {
            "DC_ID": ["dc1", "dc1", "dc2"],
            # Pas de colonne DOMAINE : avant correctif, le groupby produisait un CSV vide.
        }
    )
    analyse_pej_pa_global(
        tmp_path,
        point,
        pa,
        pej,
        tmp_path,
        dept_code="21",
    )
    pa_dom = pd.read_csv(tmp_path / "pa_global_par_domaine.csv", sep=";")
    assert len(pa_dom) == 1
    assert pa_dom.iloc[0]["domaine"] == "Hors domaine"
    assert int(pa_dom.iloc[0]["nb_pa"]) == 3
