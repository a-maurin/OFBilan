"""Chemins du projet — partagés par tous les programmes."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_out_dir(programme: str) -> Path:
    """Dossier de sortie du programme (data/out/<programme>)."""
    d = PROJECT_ROOT / "data" / "out" / programme
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_cartes_dir() -> Path:
    """Dossier des cartes générées (pour les bilans qui les intègrent)."""
    return PROJECT_ROOT / "data" / "out" / "generateur_de_cartes"


def get_sources_dir() -> Path:
    """Dossier des sources (CSV OSCEAN, etc.)."""
    return PROJECT_ROOT / "data" / "sources"


def get_ref_programme_dir() -> Path:
    """Référentiels lus par l'application (bilans, PDF, cartographie)."""
    return PROJECT_ROOT / "ref" / "programme"


def get_ref_hors_programme_dir() -> Path:
    """Référentiels archivés : hors pipeline runtime (outils, QGIS manuel, doc)."""
    return PROJECT_ROOT / "ref" / "hors_programme"


def get_ref_dir() -> Path:
    """Alias de get_ref_programme_dir() (compatibilité)."""
    return get_ref_programme_dir()


def ref_programme(root: Path | None = None) -> Path:
    """Chemin ref/programme/ pour un jeu de tests (tmp_path) ou la racine projet."""
    base = root if root is not None else PROJECT_ROOT
    return base / "ref" / "programme"


def get_config_dir() -> Path:
    """Dossier des configurations versionnées (profils YAML, configs cartes, etc.)."""
    return PROJECT_ROOT / "config"


def get_sig_dir() -> Path:
    """Données SIG utilisées par les bilans et la cartographie."""
    return get_ref_programme_dir() / "sig"


def get_qgis_project_path() -> Path:
    """Projet QGIS principal pour la production de cartes."""
    return get_sig_dir() / "bilans_carte.qgz"


def get_sources_sig_dir() -> Path:
    """Dossier des données SIG construites à partir des sources (PVe, points de contrôle, etc.)."""
    return PROJECT_ROOT / "data" / "sources" / "sig"
