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
    from scripts.bilan_global.analyse_global import analyse_controles_global

    df = _minimal_point_df()
    tab_resultats, agg_domaine, agg_theme = analyse_controles_global(df, tmp_path)

    # Les trois tableaux principaux doivent être non vides et sauvegardés en CSV.
    assert not tab_resultats.empty
    assert not agg_domaine.empty
    assert not agg_theme.empty

    for filename in (
        "controles_global_resultats.csv",
        "controles_global_par_domaine.csv",
        "controles_global_par_theme.csv",
    ):
        assert (tmp_path / filename).exists()


def test_run_global_smoke(monkeypatch, tmp_path: Path) -> None:
    """
    Test de fumée sur run_global avec des loaders surchargés.

    L'objectif est uniquement de vérifier que la fonction s'exécute sans erreur
    sur un jeu minimal, sans dépendre des fichiers sources réels.
    """
    import scripts.bilan_global.analyse_global as mod

    # Chargeurs minimaux : renvoient de petits DataFrame ou des DataFrame vides.
    minimal_point = _minimal_point_df()
    minimal_pa = pd.DataFrame([{"DC_ID": "1"}])
    minimal_pej = pd.DataFrame([{"DC_ID": "1", "ENTITE_ORIGINE_PROCEDURE": "SD21"}])
    minimal_pve = pd.DataFrame([{"dc_id": 1}])

    monkeypatch.setattr(mod, "load_point_ctrl", lambda root, dept_code, date_deb, date_fin: minimal_point)
    monkeypatch.setattr(mod, "load_pa", lambda root, date_deb, date_fin: minimal_pa)
    monkeypatch.setattr(mod, "load_pej", lambda root, date_deb, date_fin: minimal_pej)
    monkeypatch.setattr(mod, "load_pve", lambda root, dept_code, date_deb, date_fin: minimal_pve)
    monkeypatch.setattr(mod, "ensure_insee_from_communes_shp", lambda df, *args, **kwargs: df)
    monkeypatch.setattr(mod, "enrich_with_pnforet_sig_zones", lambda df, *args, **kwargs: df)
    monkeypatch.setattr(mod, "load_natinf_ref", lambda root: pd.DataFrame())

    # Neutralise les fonctions de rendu PDF/graphique pour ce test.
    monkeypatch.setattr(mod, "key_figures_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "ofb_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "chart_pie", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "chart_bar_grouped", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "chart_bar_stacked", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "chart_line_evolution", lambda *args, **kwargs: None)

    # Redirige les sorties dans un dossier temporaire.
    monkeypatch.setattr(mod, "get_out_dir", lambda programme: tmp_path / programme)

    # Appel : ne doit pas lever d'exception et doit retourner un int.
    ret = mod.run_global("2025-01-01", "2025-12-31", "21")
    assert isinstance(ret, int)

