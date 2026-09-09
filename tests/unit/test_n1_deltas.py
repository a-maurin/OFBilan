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

from core.engine.agregations_profil import compute_n1_deltas

def test_compute_n1_deltas_augmentation() -> None:
    res = compute_n1_deltas(150, 100)
    assert res["delta_pct"] == 50.0
    assert res["delta_str"] == "+50.0%"
    assert res["alerte_baisse"] is False

def test_compute_n1_deltas_baisse_normale() -> None:
    res = compute_n1_deltas(80, 100)
    assert res["delta_pct"] == -20.0
    assert res["delta_str"] == "-20.0%"
    assert res["alerte_baisse"] is False

def test_compute_n1_deltas_baisse_anormale_alerte() -> None:
    res = compute_n1_deltas(50, 100)
    assert res["delta_pct"] == -50.0
    assert res["alerte_baisse"] is True
    assert "Alerte statistique" in res["message_alerte"]

def test_compute_n1_deltas_previous_zero() -> None:
    res = compute_n1_deltas(50, 0)
    assert res["delta_pct"] is None
    assert res["delta_str"] == "N/A"
    assert res["alerte_baisse"] is False
