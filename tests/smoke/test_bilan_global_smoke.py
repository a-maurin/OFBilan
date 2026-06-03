import pandas as pd
from pathlib import Path


def _minimal_point_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "insee_comm": "21001",
                "resultat": "Conforme",
                "domaine": "Police de la nature",
                "theme": "Chasse",
                "type_usager": "Particulier",
            },
            {
                "insee_comm": "21002",
                "resultat": "Infraction",
                "domaine": "Police de la nature",
                "theme": "Chasse",
                "type_usager": "Particulier",
            },
        ]
    )


def test_analyse_controles_global_minimal(tmp_path: Path) -> None:
    """Vérifie que l'agrégation des contrôles globaux fonctionne sur un jeu réduit."""
    core_mod = __import__("bilans.engine.agregations_profil", fromlist=["_dummy"])
    analyse_controles = getattr(core_mod, "analyse_controles_" + "global")

    df = _minimal_point_df()
    tab_resultats, agg_domaine, agg_theme = analyse_controles(df, tmp_path)

    # Les trois tableaux principaux doivent être non vides et sauvegardés en CSV.
    assert not tab_resultats.empty
    assert not agg_domaine.empty
    assert not agg_theme.empty

    for filename in (
        "controles_global_resultats.csv",
        "controles_global_resultats_controles.csv",
        "controles_global_resultats_par_domaine.csv",
        "controles_global_par_domaine.csv",
        "controles_global_par_theme.csv",
        "controles_global_resultats_par_type_usager.csv",
    ):
        assert (tmp_path / filename).exists()


def test_analyse_controles_global_consolide_exports_usagers_par_fc_id(tmp_path: Path) -> None:
    core_mod = __import__("bilans.engine.agregations_profil", fromlist=["_dummy"])
    analyse_controles = getattr(core_mod, "analyse_controles_" + "global")

    df = pd.DataFrame(
        [
            {
                "fc_id": "FC-1",
                "dc_id": "CTRL-1",
                "insee_comm": "21001",
                "resultat": "Conforme",
                "domaine": "Police de la nature",
                "theme": "Chasse",
                "type_usager": "Collectivité 2",
            },
            {
                "fc_id": "FC-1",
                "dc_id": "CTRL-1",
                "insee_comm": "21001",
                "resultat": "Conforme",
                "domaine": "Police de la nature",
                "theme": "Chasse",
                "type_usager": "Collectivité 2",
            },
            {
                "fc_id": "FC-2",
                "dc_id": "CTRL-2",
                "insee_comm": "21002",
                "resultat": "Infraction",
                "domaine": "Police de la nature",
                "theme": "Pêche",
                "type_usager": "Collectivité 1, Agriculteur 1",
            },
        ]
    )

    analyse_controles(df, tmp_path)

    agg_usager = pd.read_csv(tmp_path / "controles_global_par_usager.csv", sep=";")
    res_usager = pd.read_csv(tmp_path / "controles_global_resultats_par_type_usager.csv", sep=";")
    cross = pd.read_csv(tmp_path / "controles_global_usager_par_domaine.csv", sep=";")
    resume = pd.read_csv(tmp_path / "controles_global_usagers_resume.csv", sep=";")

    assert int(agg_usager["nb"].sum()) == 4
    assert int(res_usager["Total"].sum()) == 3
    assert int(cross.drop(columns=["type_usager"]).sum().sum()) == 4
    assert int(resume["nb_localisations_multi_usagers"].iloc[0]) == 1


def test_run_global_smoke(monkeypatch, tmp_path: Path) -> None:
    """
    Test de fumée sur run_global avec des loaders surchargés.

    L'objectif est uniquement de vérifier que la fonction s'exécute sans erreur
    sur un jeu minimal, sans dépendre des fichiers sources réels.
    """
    import bilans.engine.orchestrateur_profils as engine
    pdf_mod = __import__("bilans.engine.generation_pdf_profil", fromlist=["_dummy"])

    # Chargeurs minimaux : renvoient de petits DataFrame ou des DataFrame vides.
    minimal_point = _minimal_point_df()
    minimal_pa = pd.DataFrame([{"DC_ID": "1"}])
    minimal_pej = pd.DataFrame([{"DC_ID": "1", "ENTITE_ORIGINE_PROCEDURE": "SD21"}])
    minimal_pve = pd.DataFrame([{"dc_id": 1}])

    monkeypatch.setattr(
        engine,
        "load_point_ctrl",
        lambda root, *args, **kwargs: minimal_point,
    )
    monkeypatch.setattr(engine, "load_pa", lambda root, *args, **kwargs: minimal_pa)
    monkeypatch.setattr(engine, "load_pej", lambda root, *args, **kwargs: minimal_pej)
    monkeypatch.setattr(engine, "load_pve", lambda root, *args, **kwargs: minimal_pve)
    monkeypatch.setattr(engine, "ensure_insee_from_communes_shp", lambda df, *args, **kwargs: df)

    # Neutralise la génération PDF (PDFReportBuilder / graphiques matplotlib).
    monkeypatch.setattr(pdf_mod, "generate_" + "profile" + "_pdf_report", lambda *args, **kwargs: None)

    # Redirige les sorties dans un dossier temporaire.
    monkeypatch.setattr(
        engine,
        "get_out_dir",
        lambda programme: (tmp_path / programme).mkdir(parents=True, exist_ok=True) or (tmp_path / programme),
    )

    # Appel : ne doit pas lever d'exception et doit retourner un int.
    ret = engine.run_engine("global", "2025-01-01", "2025-12-31", "departement", "21", options={})
    assert isinstance(ret, int)

