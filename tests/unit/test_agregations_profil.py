# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

import pytest
import pandas as pd
from pathlib import Path
from core.engine.agregations_profil import (
    analyse_mensuelle_global,
    analyse_annuelle_global,
    analyse_trimestrielle_global,
    analyse_hebdomadaire_global,
    analyse_pej_pa_global,
)

def test_analyse_mensuelle_global_vectorized(tmp_path: Path):
    point = pd.DataFrame({
        "date_ctrl": ["2025-01-15", "2025-01-20", "2025-02-10"],
        "fc_id": ["FC1", "FC1", "FC2"],
        "resultat": ["Conforme", "Infraction", "Conforme"],
        "code_pa": ["PA1", None, None],
        "dc_id": [101, 102, 103],
    })
    pej = pd.DataFrame({
        "DATE_REF": ["2025-01-05", "2025-02-12"],
        "DC_ID": [201, 202],
    })
    pa = pd.DataFrame()
    pve = pd.DataFrame({
        "INF-DATE-INTG": ["2025-01-18"],
    })

    analyse_mensuelle_global(point, pa, pej, pve, tmp_path)
    res_path = tmp_path / "indicateurs_global_par_mois.csv"
    assert res_path.exists()

    df_res = pd.read_csv(res_path, sep=";")
    assert set(df_res["periode"].tolist()) == {"2025-01", "2025-02"}

    jan = df_res[df_res["periode"] == "2025-01"].iloc[0]
    assert jan["nb_localisations"] == 2
    assert jan["nb_operations_controle"] == 1
    assert jan["nb_localisations_non_conformes"] == 1
    assert jan["nb_pej"] == 1
    assert jan["nb_pve"] == 1

def test_analyse_annuelle_global_vectorized(tmp_path: Path):
    point = pd.DataFrame({"date_ctrl": ["2024-05-01", "2025-06-01"]})
    pej = pd.DataFrame()
    pa = pd.DataFrame()
    pve = pd.DataFrame()

    analyse_annuelle_global(point, pa, pej, pve, tmp_path)
    res_path = tmp_path / "indicateurs_global_par_annee.csv"
    assert res_path.exists()
    df_res = pd.read_csv(res_path, sep=";")
    assert df_res["periode"].astype(str).tolist() == ["2024", "2025"]

def test_analyse_pej_pa_global_with_in_memory_faits(tmp_path: Path):
    point = pd.DataFrame({"dc_id": [1, 2], "nom_commune": ["Dijon", "Beaune"]})
    pej = pd.DataFrame({"DC_ID": [1, 2], "DOMAINE": ["Eau", "Faune"], "THEME": ["Pêche", "Chasse"], "ENTITE_ORIGINE_PROCEDURE": ["SD21", "SD21"]})
    pa = pd.DataFrame()
    pve = pd.DataFrame()

    gdf_faits = pd.DataFrame({
        "dossier": [1, 2],
        "entite": ["SD21", "SD21"],
        "x_infrac": [5.0, 5.1],
        "y_infrac": [47.0, 47.1],
    })

    analyse_pej_pa_global(
        root=tmp_path,
        point=point,
        pa=pa,
        pej=pej,
        out_dir=tmp_path,
        echelle="departement",
        code="21",
        gdf_faits=gdf_faits,
    )
    assert (tmp_path / "pej_global_par_domaine.csv").exists()
