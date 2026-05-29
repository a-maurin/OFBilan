"""Zones lecteur agrainage (4 postes : cœur, aire, TUB, hors PNF/TUB)."""

from __future__ import annotations

import pandas as pd

from bilans.common.utilitaires_metier import (
    ZONE_LECTEUR_AIRE,
    ZONE_LECTEUR_COEUR,
    ZONE_LECTEUR_HORS,
    ZONE_LECTEUR_TUB,
    build_tab_resultats_controles,
    classify_zone_lecteur_series,
    format_zone_lecteur_counts,
    zone_lecteur_counts_for_pdf_cell,
    zone_lecteur_label,
)


def test_zone_lecteur_label_priorite_sig_puis_tub() -> None:
    tub = {"21001"}
    assert zone_lecteur_label("Coeur_PNF", "21001", tub) == ZONE_LECTEUR_COEUR
    assert zone_lecteur_label("Aire_adhesion_PNF", "21001", tub) == ZONE_LECTEUR_AIRE
    assert zone_lecteur_label("Hors_perimetres_sig", "21001", tub) == ZONE_LECTEUR_TUB
    assert zone_lecteur_label("Hors_perimetres_sig", "21999", tub) == ZONE_LECTEUR_HORS
    assert zone_lecteur_label(None, None, tub) == "n.d."


def test_classify_zone_lecteur_series_exclusive() -> None:
    df = pd.DataFrame(
        {
            "pnf_zone_sig": ["Coeur_PNF", "Aire_adhesion_PNF", "Hors_perimetres_sig", "Hors_perimetres_sig"],
            "insee_comm": ["21001", "21002", "21003", "21004"],
        }
    )
    tub = {"21003"}
    zones = classify_zone_lecteur_series(df, tub)
    assert list(zones) == [ZONE_LECTEUR_COEUR, ZONE_LECTEUR_AIRE, ZONE_LECTEUR_TUB, ZONE_LECTEUR_HORS]


def test_format_zone_lecteur_counts_omit_zero() -> None:
    zones = pd.Series([ZONE_LECTEUR_COEUR, ZONE_LECTEUR_HORS, ZONE_LECTEUR_HORS])
    mask = pd.Series([True, True, True])
    assert format_zone_lecteur_counts(zones, mask) == f"{ZONE_LECTEUR_COEUR} : 1, {ZONE_LECTEUR_HORS} : 2"


def test_zone_lecteur_counts_for_pdf_cell_multiline() -> None:
    raw = f"{ZONE_LECTEUR_COEUR} : 4, {ZONE_LECTEUR_AIRE} : 2, {ZONE_LECTEUR_TUB} : 58"
    assert zone_lecteur_counts_for_pdf_cell(raw) == (
        f"{ZONE_LECTEUR_COEUR} : 4<br/>{ZONE_LECTEUR_AIRE} : 2<br/>{ZONE_LECTEUR_TUB} : 58"
    )
    assert zone_lecteur_counts_for_pdf_cell("n.d.") == "n.d."


def test_build_tab_resultats_controles_zone_lecteur_4() -> None:
    point = pd.DataFrame(
        {
            "resultat": ["Conforme", "Conforme", "Infraction", "En attente"],
            "pnf_zone_sig": ["Coeur_PNF", "Hors_perimetres_sig", "Aire_adhesion_PNF", "Hors_perimetres_sig"],
            "insee_comm": ["21001", "21002", "21003", "21004"],
        }
    )
    tab = build_tab_resultats_controles(
        point,
        zone_lecteur_4_zones=True,
        tub_codes={"21002"},
    )
    conf = tab.loc[tab["resultat"] == "Conforme", "coeur_hors_coeur"].iloc[0]
    assert ZONE_LECTEUR_COEUR in conf
    assert ZONE_LECTEUR_TUB in conf
    assert "21002" not in conf
    att = tab.loc[tab["resultat"] == "En attente", "coeur_hors_coeur"].iloc[0]
    assert att == "n.d."
