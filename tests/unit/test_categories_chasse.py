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

import logging
import pandas as pd
import pytest
from pathlib import Path

from core.engine.agregations_profil import (
    compute_categories_chasse_controles,
    compute_categories_chasse_infractions,
    analyse_categories_chasse,
)


@pytest.fixture
def sample_categories_cfg():
    return {
        "agrainage": {
            "label": "Agrainage",
            "keywords_controles": ["agrain", "nourriss"],
            "natinf_pve": ["27742", "25001"],
            "natinf_pej": ["27742", "25001", "34827"],
        },
        "securite": {
            "label": "Sécurité à la chasse",
            "keywords_controles": ["sécurité", "securite"],
            "natinf_pve": ["26274", "2002"],
            "natinf_pej": ["26274", "2002", "26307"],
        },
        "autres": {
            "label": "Autres infractions",
            "keywords_controles": [],
            "natinf_pve": ["5982"],
            "natinf_pej": ["5982", "2166"],
        },
    }


def test_compute_categories_chasse_controles_empty(sample_categories_cfg):
    empty_df = pd.DataFrame()
    res = compute_categories_chasse_controles(empty_df, sample_categories_cfg)
    assert "df" in res
    assert "donut_data" in res
    df = res["df"]
    assert len(df) == 3
    assert (df["total"] == 0).all()
    assert (df["conforme"] == 0).all()
    assert (df["non_conforme"] == 0).all()


def test_compute_categories_chasse_controles_classification(sample_categories_cfg):
    points = pd.DataFrame([
        {"nom_dossie": "Contrôle agrainage forêt", "type_actio": "Chasse", "resultat_c": "Conforme"},
        {"nom_dossie": "Opération nourrissage", "type_actio": "Chasse", "resultat_c": "Infraction"},
        {"nom_dossie": "Battue du dimanche", "type_actio": "Sécurité à la chasse", "resultat_c": "Conforme"},
        {"nom_dossie": "Contrôle ordinaire", "type_actio": "Police de la chasse", "resultat_c": "Manquement"},
        {"nom_dossie": "Autre surveillance", "type_actio": "Chasse", "resultat_c": "Conforme"},
    ])

    res = compute_categories_chasse_controles(points, sample_categories_cfg)
    df = res["df"]
    
    # Agrainage : 2 dossiers (1 conforme, 1 infraction -> 50% non-conforme)
    agrain_row = df[df["categorie"] == "agrainage"].iloc[0]
    assert agrain_row["total"] == 2
    assert agrain_row["conforme"] == 1
    assert agrain_row["non_conforme"] == 1
    assert agrain_row["taux_non_conforme"] == 50.0

    # Sécurité : 1 dossier conforme
    sec_row = df[df["categorie"] == "securite"].iloc[0]
    assert sec_row["total"] == 1
    assert sec_row["conforme"] == 1
    assert sec_row["non_conforme"] == 0
    assert sec_row["taux_non_conforme"] == 0.0

    # Autres : 2 dossiers (1 conforme, 1 manquement -> 50% non-conforme)
    autres_row = df[df["categorie"] == "autres"].iloc[0]
    assert autres_row["total"] == 2
    assert autres_row["conforme"] == 1
    assert autres_row["non_conforme"] == 1
    assert autres_row["taux_non_conforme"] == 50.0


def test_compute_categories_chasse_controles_resultat_composite(sample_categories_cfg):
    points = pd.DataFrame([
        {"nom_dossie": "Contrôle agrainage forêt", "type_actio": "Chasse", "resultat": "Conforme"},
        {"nom_dossie": "Opération nourrissage", "type_actio": "Chasse", "resultat": "Manquement et infraction"},
        {"nom_dossie": "Battue du dimanche", "type_actio": "Sécurité à la chasse", "resultat": "Infraction"},
    ])

    res = compute_categories_chasse_controles(points, sample_categories_cfg)
    df = res["df"]

    agrain_row = df[df["categorie"] == "agrainage"].iloc[0]
    assert agrain_row["total"] == 2
    assert agrain_row["conforme"] == 1
    assert agrain_row["non_conforme"] == 1
    assert agrain_row["taux_non_conforme"] == 50.0

    sec_row = df[df["categorie"] == "securite"].iloc[0]
    assert sec_row["total"] == 1
    assert sec_row["conforme"] == 0
    assert sec_row["non_conforme"] == 1
    assert sec_row["taux_non_conforme"] == 100.0


def test_compute_categories_chasse_infractions(sample_categories_cfg, capsys, caplog):
    pve = pd.DataFrame([
        {"INF-NATINF": "27742"},  # Agrainage
        {"INF-NATINF": "26274"},  # Sécurité
        {"INF-NATINF": "5982"},   # Autres
        {"INF-NATINF": "99999"},  # Orphelin -> doit aller dans Autres
    ])

    pej = pd.DataFrame([
        {"NATINF_PEJ": "25001"},  # Agrainage
        {"NATINF_PEJ": "34827"},  # Agrainage
        {"NATINF_PEJ": "2002"},   # Sécurité
        {"NATINF_PEJ": "88888"},  # Orphelin -> doit aller dans Autres
    ])

    with caplog.at_level(logging.WARNING):
        res = compute_categories_chasse_infractions(pve, pej, sample_categories_cfg)

    df = res["df"]
    unlisted = res["unlisted_natinf"]

    # Orphelins détectés
    assert "99999" in unlisted
    assert "88888" in unlisted

    # Agrainage : 1 PVe + 2 PEJ = 3
    agrain_row = df[df["categorie"] == "agrainage"].iloc[0]
    assert agrain_row["nb_pve"] == 1
    assert agrain_row["nb_pej"] == 2
    assert agrain_row["total"] == 3

    # Sécurité : 1 PVe + 1 PEJ = 2
    sec_row = df[df["categorie"] == "securite"].iloc[0]
    assert sec_row["nb_pve"] == 1
    assert sec_row["nb_pej"] == 1
    assert sec_row["total"] == 2

    # Autres : 1 PVe + 0 PEJ (officiels) + 1 PVe orphelin + 1 PEJ orphelin = 3
    autres_row = df[df["categorie"] == "autres"].iloc[0]
    assert autres_row["nb_pve"] == 2
    assert autres_row["nb_pej"] == 1
    assert autres_row["total"] == 3

    # Total général = 3 + 2 + 3 = 8
    assert df["total"].sum() == 8

    # Vérification de l'alerte console
    captured = capsys.readouterr()
    assert "[ALERTE OFBILAN]" in captured.out
    assert "99999" in captured.out
    assert "88888" in captured.out


def test_analyse_categories_chasse_with_export(sample_categories_cfg, tmp_path):
    points = pd.DataFrame([
        {"nom_dossie": "Agrainage 1", "type_actio": "Chasse", "resultat_c": "Conforme"},
    ])
    pve = pd.DataFrame([{"INF-NATINF": "27742"}])
    pej = pd.DataFrame([{"NATINF_PEJ": "26274"}])

    res = analyse_categories_chasse(points, pve, pej, sample_categories_cfg, out_dir=tmp_path)
    
    assert (tmp_path / "categories_chasse_controles.csv").exists()
    assert (tmp_path / "categories_chasse_infractions.csv").exists()
    assert (tmp_path / "categories_chasse_controles_donut.png").exists()
    assert (tmp_path / "categories_chasse_infractions_donut.png").exists()


def test_categories_chasse_specific_labels():
    cfg = {
        "autres": {
            "label": "Autres infractions",
            "label_controles": "Autres contrôles chasse",
            "label_infractions": "Autres infractions chasse",
            "keywords_controles": [],
            "natinf_pve": [],
            "natinf_pej": [],
        }
    }
    pts = pd.DataFrame([{"nom_dossie": "Autre action", "type_actio": "Chasse", "resultat_c": "Conforme"}])
    res_ctrl = compute_categories_chasse_controles(pts, cfg)
    assert res_ctrl["df"].iloc[0]["libelle"] == "Autres contrôles chasse"
    assert "Autres contrôles chasse" in res_ctrl["donut_data"]

    pve = pd.DataFrame([{"INF-NATINF": "99999"}])
    pej = pd.DataFrame()
    res_inf = compute_categories_chasse_infractions(pve, pej, cfg)
    assert res_inf["df"].iloc[0]["libelle"] == "Autres infractions chasse"
    assert "Autres infractions chasse" in res_inf["donut_data"]


def test_contient_natinf_multi_codes():
    from core.common.utilitaires_metier import contient_natinf
    assert contient_natinf("26188_27742", ["27742"])
    assert contient_natinf("27742_26188", ["27742"])
    assert contient_natinf("26305_323_27745", ["27745"])
    assert contient_natinf("25001_25001", ["25001"])
    assert not contient_natinf("127742", ["27742"])
    assert not contient_natinf("277429", ["27742"])


