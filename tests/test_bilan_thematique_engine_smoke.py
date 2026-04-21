import pandas as pd
from pathlib import Path


def _minimal_point_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date_ctrl": pd.Timestamp("2025-01-15"),
                "dc_id": 1,
                "num_depart": "21",
                "theme": "Chasse",
                "type_actio": "Contrôle",
                "type_usager": "Particulier",
            }
        ]
    )


def _minimal_empty_df() -> pd.DataFrame:
    return pd.DataFrame()


def test_run_engine_smoke(monkeypatch, tmp_path: Path) -> None:
    """
    Test de fumée sur run_engine avec des loaders et la génération de PDF surchargés.

    Ce test ne vérifie pas le contenu des résultats, seulement que le moteur
    peut s'exécuter sur un profil simple sans dépendre des sources réelles.
    """
    import scripts.bilan_thematique.bilan_thematique_engine as engine

    # Profils : on force un profil minimal en surchargeant load_profile_config.
    def _dummy_profile(root: Path, profil_id: str) -> dict:
        return {
            "id": profil_id,
            "label": profil_id,
            "out_subdir": f"bilan_{profil_id}",
            "analyse_PVe": False,
            "filter": {"type": "keywords", "keywords": [], "columns": ["theme"], "exclude_patterns": []},
            "sources": {"point_ctrl": True, "pej": False, "pa": False, "pve": False},
            "periode_analyse": {"ventilation": {"type": "globale", "seuil_jours": 366}},
            "options": {},
        }

    monkeypatch.setattr(engine, "load_profile_config", _dummy_profile)

    # Chargeurs minimaux.
    minimal_point = _minimal_point_df()
    monkeypatch.setattr(
        engine,
        "load_point_ctrl",
        lambda root, dept_code, date_deb, date_fin: minimal_point,
    )
    monkeypatch.setattr(engine, "load_pej", lambda *args, **kwargs: _minimal_empty_df())
    monkeypatch.setattr(engine, "load_pa", lambda *args, **kwargs: _minimal_empty_df())
    monkeypatch.setattr(engine, "load_pve", lambda *args, **kwargs: _minimal_empty_df())
    monkeypatch.setattr(engine, "load_pnf", lambda *args, **kwargs: _minimal_empty_df())
    monkeypatch.setattr(engine, "load_tub", lambda *args, **kwargs: _minimal_empty_df())
    monkeypatch.setattr(engine, "load_natinf_ref", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(engine, "load_tub_pnf_codes", lambda *args, **kwargs: (set(), set()))
    monkeypatch.setattr(engine, "load_communes_noms", lambda *args, **kwargs: {})

    # PDF : neutralise la génération pour garder un test de fumée focalisé moteur.
    monkeypatch.setattr(engine, "_generate_pdf", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "chart_pie", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "chart_bar", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "chart_bar_grouped", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "chart_bar_stacked", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "chart_line_evolution", lambda *args, **kwargs: None)

    # Cartes : on neutralise la recherche de cartes.
    monkeypatch.setattr(engine, "find_map", lambda *args, **kwargs: None)

    # Dossier de sortie : utilise un répertoire temporaire dédié.
    def _dummy_get_out(subdir: str) -> Path:
        d = tmp_path / subdir
        d.mkdir(parents=True, exist_ok=True)
        return d

    class DummyBilanConfig:
        def __init__(self, root: Path) -> None:
            self.root = root
            self.out_root = tmp_path
            self.date_deb = pd.Timestamp("2025-01-01")
            self.date_fin = pd.Timestamp("2025-12-31")
            self.dept_code = "21"
            self.dept_name = "Côte-d'Or"

        @classmethod
        def from_strings(cls, *args, **kwargs) -> "DummyBilanConfig":
            return cls(root=tmp_path)

        def get_out(self, subdir: str) -> Path:
            return _dummy_get_out(subdir)

    monkeypatch.setattr(engine, "BilanConfig", DummyBilanConfig)

    # Exécution : ne doit pas lever d'exception et retourne un int.
    ret = engine.run_engine("chasse", "2025-01-01", "2025-12-31", "21", options={})
    assert isinstance(ret, int)


def test_restrict_geo_pnf_pa_uses_manquement_controls(monkeypatch) -> None:
    """
    Vérifie la règle métier PA : sous restriction PNF, seuls les DC_ID des
    contrôles en Manquement sont conservés pour les PA.
    """
    import scripts.bilan_thematique.bilan_thematique_engine as engine

    point = pd.DataFrame(
        [
            {"dc_id": "A", "insee_comm": "21001", "resultat": "Manquement"},
            {"dc_id": "B", "insee_comm": "21001", "resultat": "Infraction"},
            {"dc_id": "C", "insee_comm": "99999", "resultat": "Manquement"},
        ]
    )
    pej = pd.DataFrame([{"DC_ID": "A"}, {"DC_ID": "B"}, {"DC_ID": "C"}])
    pa = pd.DataFrame([{"DC_ID": "A"}, {"DC_ID": "B"}, {"DC_ID": "C"}])
    pve = pd.DataFrame([{"INF-INSEE": "21001"}, {"INF-INSEE": "99999"}])

    monkeypatch.setattr(engine, "load_tub_pnf_codes", lambda root: (set(), {"21001"}))
    monkeypatch.setattr(engine, "ensure_insee_from_communes_shp", lambda df, *args, **kwargs: df)

    pt2, pej2, pa2, pve2 = engine._apply_restrict_geo_pnf(
        point, pej, pa, pve, root=Path("."), log=engine.logging.getLogger("test")
    )

    assert set(pt2["dc_id"].astype(str)) == {"A", "B"}
    assert set(pej2["DC_ID"].astype(str)) == {"A", "B"}
    assert set(pa2["DC_ID"].astype(str)) == {"A"}
    assert set(pve2["INF-INSEE"].astype(str)) == {"21001"}


def test_restrict_geo_pnf_sig_mask_or_insee(monkeypatch) -> None:
    """
    Si l'INSEE n'est pas dans le référentiel tabulaire PNF mais que le masque
    SIG indique une localisation dans le parc, les lignes doivent être conservées.
    """
    import scripts.bilan_thematique.bilan_thematique_engine as engine

    point = pd.DataFrame(
        [
            {
                "dc_id": "X",
                "insee_comm": "99999",
                "resultat": "Manquement",
                "x": 4.0,
                "y": 47.0,
            },
        ]
    )
    pej = pd.DataFrame([{"DC_ID": "X"}])
    pa = pd.DataFrame([{"DC_ID": "X"}])
    pve = pd.DataFrame([{"INF-INSEE": "99999", "inf_gps_long": 4.0, "inf_gps_lat": 47.0}])

    monkeypatch.setattr(engine, "load_tub_pnf_codes", lambda root: (set(), {"21001"}))
    monkeypatch.setattr(engine, "ensure_insee_from_communes_shp", lambda df, *args, **kwargs: df)
    monkeypatch.setattr(
        engine,
        "pnf_sig_union_membership_mask",
        lambda df, root, log=None: pd.Series(True, index=df.index),
    )

    pt2, pej2, pa2, pve2 = engine._apply_restrict_geo_pnf(
        point, pej, pa, pve, root=Path("."), log=engine.logging.getLogger("test")
    )

    assert list(pt2["dc_id"].astype(str)) == ["X"]
    assert list(pej2["DC_ID"].astype(str)) == ["X"]
    assert list(pa2["DC_ID"].astype(str)) == ["X"]
    assert len(pve2) == 1

