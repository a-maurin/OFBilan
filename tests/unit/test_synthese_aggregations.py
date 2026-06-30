"""Tests agrégations profil synthese_activite_PA_PJ."""

from __future__ import annotations

import pandas as pd

from core.engine.synthese_aggregations import (
    activite_par_type_usager,
    activite_police_par_theme,
    activite_usager_par_theme,
    analyse_pve_synthese,
    pej_hors_fiche_controle,
    procedures_par_theme,
)
from core.common.utilitaires_metier import (
    agg_effectifs_usagers_par_theme,
    agg_resultat_counts_par_type_usager,
    agg_resultat_effectifs_par_type_usager,
    format_type_usager_display,
    map_type_usager,
)


def test_pej_hors_controle_exclut_dc_id_lies_aux_controles() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1", "CTRL-2"],
            "theme": ["Thème A", "Thème B"],
            "resultat": ["Infraction", "Conforme"],
        }
    )
    pej = pd.DataFrame(
        {
            "DC_ID": ["CTRL-1", "PEJ-99"],
            "ENTITE_ORIGINE_PROCEDURE": ["SD21", "SD21"],
            "THEME": ["Thème A", "Thème C"],
        }
    )
    hors = pej_hors_fiche_controle(pej, point, "departement", "21")
    assert len(hors) == 1
    assert hors.iloc[0]["DC_ID"] == "PEJ-99"

    act = activite_police_par_theme(point, pej, "departement", "21")
    row_a = act.loc[act["theme"] == "Thème A"].iloc[0]
    row_c = act.loc[act["theme"] == "Thème C"].iloc[0]
    assert int(row_a["nb_localisations"]) == 1
    assert int(row_a["nb_pej_hors_controle"]) == 0
    assert int(row_a["nb_total"]) == 1
    assert int(row_c["nb_localisations"]) == 0
    assert int(row_c["nb_pej_hors_controle"]) == 1
    assert int(row_c["nb_total"]) == 1


def test_procedures_usager_par_theme_sans_type_usager_dans_pa_ods() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1"],
            "theme": ["Thème A"],
            "type_usager": ["Agriculteur 1"],
            "resultat": ["Manquement"],
            "code_pa": ["PA1"],
        }
    )
    pej = pd.DataFrame(
        {
            "DC_ID": ["PEJ-1"],
            "ENTITE_ORIGINE_PROCEDURE": ["SD21"],
            "THEME": ["Thème B"],
            "type_usager": ["Pêcheur"],
        }
    )
    pa = pd.DataFrame({"DC_ID": ["PA-1"], "ENTITE_ORIGINE_PROCEDURE": ["SD21"], "THEME": ["Thème A"]})
    from core.engine.synthese_aggregations import procedures_usager_par_theme

    out = procedures_usager_par_theme(pej, pa, point, "departement", "21")
    assert not out.empty
    assert "type_usager" in out.columns
    assert int(out["nb_pa"].sum()) >= 1
    assert int(out["nb_pej"].sum()) == 1


def test_activite_usager_par_theme_compte_les_effectifs() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1"],
            "theme": ["Thème A"],
            "type_usager": ["Particulier 3, Collectivité 2"],
            "resultat": ["Conforme"],
        }
    )
    pej = pd.DataFrame(columns=["DC_ID", "ENTITE_ORIGINE_PROCEDURE", "THEME"])
    out = activite_usager_par_theme(point, pej, "departement", "21")
    assert int(out["nb_effectifs"].sum()) == 5
    assert int(out.loc[out["theme"] == "Thème A", "nb_effectifs"].sum()) == 5


def test_resultat_effectifs_par_type_usager() -> None:
    point = pd.DataFrame(
        {
            "type_usager": ["Particulier 3, Collectivité 2"],
            "resultat": ["Conforme"],
        }
    )
    out = agg_resultat_effectifs_par_type_usager(point)
    assert int(out["Conforme"].sum()) == 5
    assert int(out["Total"].sum()) == 5


def test_resultat_counts_par_type_usager_dedupplique_par_fc_id() -> None:
    point = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "type_usager": ["Collectivité 2", "Collectivité 2"],
            "resultat": ["Conforme", "Conforme"],
        }
    )

    out = agg_resultat_counts_par_type_usager(point)

    assert int(out["Conforme"].sum()) == 1
    assert int(out["Total"].sum()) == 1


def test_resultat_effectifs_par_type_usager_dedupplique_par_fc_id() -> None:
    point = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "type_usager": ["Collectivité 2", "Collectivité 2"],
            "resultat": ["Conforme", "Conforme"],
        }
    )

    out = agg_resultat_effectifs_par_type_usager(point)

    assert int(out["Conforme"].sum()) == 2
    assert int(out["Total"].sum()) == 2


def test_resultat_effectifs_par_type_usager_journalise_conflit_fc_id(caplog) -> None:
    point = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "type_usager": ["Collectivité 2", "Collectivité 2"],
            "resultat": ["Conforme", "Infraction"],
        }
    )

    with caplog.at_level("WARNING"):
        out = agg_resultat_effectifs_par_type_usager(point)

    assert "Conflit intra-fc_id sur resultat pour fc_id=FC-1" in caplog.text
    assert int(out["Conforme"].sum()) == 2
    assert int(out["Infraction"].sum()) == 0


def test_resultat_effectifs_par_type_usager_prefere_valeur_plus_recente_et_informative() -> None:
    point = pd.DataFrame(
        {
            "fc_id": ["FC-143615", "FC-143615"],
            "date_ctrl": [pd.Timestamp("2022-11-01"), pd.Timestamp("2023-03-31")],
            "type_usager": [
                "Particulier 2",
                "Particulier (usager de la nature + gestionnaire d'une propriété) 2",
            ],
            "resultat": ["Conforme", "Infraction"],
        }
    )

    out = agg_resultat_effectifs_par_type_usager(point)
    part = out.loc[
        out["type_usager"] == "Particulier (usager de la nature + gestionnaire d'une propriété)"
    ]

    assert int(part["Infraction"].sum()) == 2
    assert int(part["Total"].sum()) == 2
    assert int(out.loc[out["type_usager"] == "Autre", "Total"].sum()) == 0


def test_activite_par_type_usager_compte_ctrl_et_pej_hors() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1", "CTRL-2"],
            "theme": ["Thème A", "Thème B"],
            "type_usager": ["Particulier 1", "Collectivité 1"],
            "resultat": ["Conforme", "Conforme"],
        }
    )
    pej = pd.DataFrame(
        {
            "DC_ID": ["PEJ-1"],
            "ENTITE_ORIGINE_PROCEDURE": ["SD21"],
            "THEME": ["Thème C"],
            "type_usager": ["Pêcheur"],
        }
    )
    out = activite_par_type_usager(point, pej, "departement", "21")
    assert int(out["nb_effectifs"].sum()) == 2
    assert int(out["nb_pej_hors_controle"].sum()) == 1
    assert int(out["nb_total"].sum()) == 3


def test_procedures_par_theme_pa_uniquement_depuis_controles() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1", "CTRL-2"],
            "theme": ["Thème A", "Thème A"],
            "type_usager": ["Particulier 1", "Particulier 1"],
            "resultat": ["Manquement", "Manquement"],
            "code_pa": ["PA1", "PA2"],
        }
    )
    pa_ods = pd.DataFrame(
        {
            "DC_ID": ["CTRL-1"],
            "ENTITE_ORIGINE_PROCEDURE": ["SD21"],
            "THEME": ["Thème A"],
            "type_usager": ["Particulier 1"],
        }
    )
    proc = procedures_par_theme(
        pd.DataFrame(columns=["DC_ID", "ENTITE_ORIGINE_PROCEDURE", "THEME"]),
        pa_ods,
        point,
        "departement",
        "21",
    )
    assert "nb_pve" not in proc.columns
    assert int(proc.loc[proc["theme"] == "Thème A", "nb_pa"].sum()) == 2


def test_effectifs_usagers_par_theme() -> None:
    point = pd.DataFrame(
        {
            "theme": ["T1", "T1"],
            "type_usager": ["Particulier 2", "Particulier 1, Collectivité 4"],
        }
    )
    out = agg_effectifs_usagers_par_theme(point)
    # Particulier n'est pas toujours mappé dans types_usagers.csv → fallback « Autre »
    assert int(out.loc[out["type_usager"] == "Autre", "nb"].sum()) == 3
    assert int(out.loc[out["type_usager"] == "Collectivité", "nb"].sum()) == 4
    assert int(out["nb"].sum()) == 7


def test_effectifs_usagers_par_theme_dedupplique_par_fc_id() -> None:
    point = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "theme": ["T1", "T1"],
            "type_usager": ["Collectivité 4", "Collectivité 4"],
        }
    )

    out = agg_effectifs_usagers_par_theme(point)

    assert int(out["nb"].sum()) == 4
    assert int(out.loc[out["type_usager"] == "Collectivité", "nb"].sum()) == 4


def test_map_type_usager_libelle_referentiel_pej() -> None:
    lib = "Agriculteur et autres acteurs agricoles"
    assert map_type_usager("pej", "USAGER", lib) == lib
    assert map_type_usager("pej", "type_usager", lib) == lib
    assert format_type_usager_display("Autre") == "Autre usager"


def test_analyse_pve_synthese_exports(tmp_path) -> None:
    pve = pd.DataFrame(
        {
            "INF-DATE-INTG": pd.to_datetime(["2025-03-15", "2025-03-20", "2025-04-01"]),
            "INF-CLASSE": ["4", "4", "3"],
            "INF-INSEE": ["21001", "21001", "21002"],
            "INF-NATINF": ["100", "100", "200"],
        }
    )
    analyse_pve_synthese(pve, tmp_path)
    classe = pd.read_csv(tmp_path / "synthese_pve_par_classe.csv", sep=";")
    assert int(classe["nb"].sum()) == 3
    assert int(classe.loc[classe["classe"].astype(str) == "4", "nb"].sum()) == 2


def test_activite_usager_par_theme_pej_suite_controle() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1"],
            "theme": ["Thème A"],
            "type_usager": ["Collectivité 2"],
            "resultat": ["Conforme"],
        }
    )
    pej = pd.DataFrame(
        {
            "DC_ID": ["CTRL-1"],
            "ENTITE_ORIGINE_PROCEDURE": ["SD21"],
            "THEME": ["Thème A"],
            "type_usager": ["Autre"],
        }
    )
    out = activite_usager_par_theme(point, pej, "departement", "21")
    autre = out[(out["type_usager"] == "Autre") & (out["theme"] == "Thème A")].iloc[0]
    coll = out[(out["type_usager"] == "Collectivité") & (out["theme"] == "Thème A")].iloc[0]
    assert int(autre["nb_pej_suite_controle"]) == 1
    assert int(autre["nb_effectifs"]) == 0
    assert int(autre["nb_pej_hors_controle"]) == 0
    assert int(autre["nb_total"]) == 1
    assert int(coll["nb_effectifs"]) == 2
    assert int(coll["nb_pej_suite_controle"]) == 0


def test_activite_usager_par_theme_dedupplique_effectifs_par_fc_id() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-1", "CTRL-1"],
            "fc_id": ["FC-1", "FC-1"],
            "theme": ["Thème A", "Thème A"],
            "type_usager": ["Collectivité 2", "Collectivité 2"],
            "resultat": ["Conforme", "Conforme"],
        }
    )
    pej = pd.DataFrame(columns=["DC_ID", "ENTITE_ORIGINE_PROCEDURE", "THEME"])

    out = activite_usager_par_theme(point, pej, "departement", "21")
    coll = out[(out["type_usager"] == "Collectivité") & (out["theme"] == "Thème A")].iloc[0]

    assert int(coll["nb_effectifs"]) == 2
    assert int(coll["nb_total"]) == 2


def test_activite_usager_par_theme_prefere_theme_et_type_plus_recents() -> None:
    point = pd.DataFrame(
        {
            "dc_id": ["CTRL-143615", "CTRL-143615"],
            "fc_id": ["FC-143615", "FC-143615"],
            "date_ctrl": [pd.Timestamp("2022-11-01"), pd.Timestamp("2023-03-31")],
            "theme": ["Travaux en cours d'eau", "Travaux en cours d'eau [2023]"],
            "type_usager": [
                "Particulier 2",
                "Particulier (usager de la nature + gestionnaire d'une propriété) 2",
            ],
            "resultat": ["Conforme", "Infraction"],
        }
    )
    pej = pd.DataFrame(columns=["DC_ID", "ENTITE_ORIGINE_PROCEDURE", "THEME"])

    out = activite_usager_par_theme(point, pej, "departement", "21")
    part = out[
        (out["type_usager"] == "Particulier (usager de la nature + gestionnaire d'une propriété)")
        & (out["theme"] == "Travaux en cours d'eau [2023]")
    ].iloc[0]

    assert int(part["nb_effectifs"]) == 2
    assert int(part["nb_total"]) == 2
    assert int(out.loc[out["type_usager"] == "Autre", "nb_effectifs"].sum()) == 0


def test_activite_par_type_usager_pej_hors_ventile_par_categorie() -> None:
    point = pd.DataFrame(columns=["dc_id", "theme", "type_usager", "resultat"])
    pej = pd.DataFrame(
        {
            "DC_ID": ["PEJ-1", "PEJ-2"],
            "ENTITE_ORIGINE_PROCEDURE": ["SD21", "SD21"],
            "THEME": ["Thème X", "Thème Y"],
            "USAGER": [
                "Agriculteur et autres acteurs agricoles",
                "Particulier (usager de la nature + gestionnaire d'une propriété)",
            ],
            "type_usager": [
                "Agriculteur et autres acteurs agricoles",
                "Particulier (usager de la nature + gestionnaire d'une propriété)",
            ],
        }
    )
    out = activite_par_type_usager(point, pej, "departement", "21")
    agr = out.loc[
        out["type_usager"].astype(str).str.startswith("Agriculteur"), "nb_pej_hors_controle"
    ]
    part = out.loc[
        out["type_usager"].astype(str).str.startswith("Particulier"), "nb_pej_hors_controle"
    ]
    assert int(agr.sum()) == 1
    assert int(part.sum()) == 1
    assert int(out.loc[out["type_usager"] == "Autre", "nb_pej_hors_controle"].sum()) == 0
