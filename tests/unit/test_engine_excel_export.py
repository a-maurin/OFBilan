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
from core.common.excel_exporter import export_bilan_excel

def test_export_bilan_excel_region(tmp_path: Path):
    df_detail = pd.DataFrame({
        "departement": ["21", "21", "71", "39"],
        "domaine": ["Eau", "Faune", "Eau", "Chasse"],
        "theme": ["Pollution", "Espèces", "Pollution", "Sécurité"],
        "nb_operations": [10, 5, 8, 4],
        "nb_localisations": [12, 6, 9, 4],
        "nb_pej": [2, 1, 3, 0],
        "nb_pa": [1, 0, 0, 1],
        "nb_pve": [3, 2, 1, 0]
    })

    excel_file = export_bilan_excel(
        out_dir=tmp_path,
        df_detail=df_detail,
        echelle="region",
        code="r27",
        depts=["21", "71", "39"],
        filename="bilan_test_region.xlsx"
    )

    assert excel_file is not None
    assert excel_file.exists()
    assert excel_file.name == "bilan_test_region.xlsx"

    # Vérification des onglets générés avec pandas ExcelFile
    xls = pd.ExcelFile(excel_file)
    sheets = xls.sheet_names
    assert "Synthese_Regionale" in sheets
    assert "Dept_21" in sheets
    assert "Dept_71" in sheets
    assert "Dept_39" in sheets
    assert "Donnees_Brutes" in sheets


def test_export_bilan_excel_departement(tmp_path: Path):
    df_detail = pd.DataFrame({
        "departement": ["21", "21"],
        "domaine": ["Eau", "Faune"],
        "theme": ["Pollution", "Espèces"],
        "nb_operations": [10, 5],
        "nb_localisations": [12, 6],
        "nb_pej": [2, 1],
        "nb_pa": [1, 0],
        "nb_pve": [3, 2]
    })

    excel_file = export_bilan_excel(
        out_dir=tmp_path,
        df_detail=df_detail,
        echelle="departement",
        code="21",
        filename="bilan_test_dept21.xlsx"
    )

    assert excel_file is not None
    assert excel_file.exists()
    assert excel_file.name == "bilan_test_dept21.xlsx"

    xls = pd.ExcelFile(excel_file)
    sheets = xls.sheet_names
    assert "Synthese_Dept_21" in sheets
    assert "Donnees_Brutes" in sheets
