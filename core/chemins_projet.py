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

#
"""Chemins du projet — partagés par tous les programmes."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def is_writable(path: Path) -> bool:
    """Vérifie si un chemin est inscriptible via un test de création de fichier temporaire."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / f".writable_test_{os.getpid()}.tmp"
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def is_network_path(path: Path) -> bool:
    """Détecte si un chemin est sur un partage réseau (UNC ou lecteur distant)."""
    try:
        resolved = str(path.resolve())
    except Exception:
        resolved = str(path)
    if resolved.startswith(("\\\\", "//")):
        return True
    if os.name == "nt":
        import ctypes
        drive = os.path.splitdrive(resolved)[0]
        if drive:
            drive_root = drive + "\\" if not drive.endswith("\\") else drive
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(drive_root) == 4:
                    return True
            except Exception:
                pass
    return False


def get_app_data_dir() -> Path:
    """Dossier local de travail (%LOCALAPPDATA%/OFBilan ou ~/.ofbilan)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "OFBilan"
    else:
        base = Path.home() / ".ofbilan"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_export_base_dir() -> Path:
    """Dossier de base pour les exports utilisateur (Documents/OFBilan_Exports ou personnalisé)."""
    env_dir = os.environ.get("OFBILAN_EXPORT_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    try:
        from core.parametres_utilisateur import lire_parametres
        settings = lire_parametres()
        export_str = settings.get("systeme", {}).get("dossier_export")
        if export_str:
            return Path(export_str).expanduser()
    except Exception:
        pass
    return Path.home() / "Documents" / "OFBilan_Exports"


def get_out_dir(programme: str) -> Path:
    """Dossier de sortie du programme.

    Les livrables sont systématiquement écrits sur le poste de l'utilisateur
    (dans ~/Documents/OFBilan_Exports/<programme> ou le dossier configuré par l'utilisateur).
    """
    base = get_export_base_dir()
    if not is_writable(base):
        base = get_app_data_dir() / "exports"
    d = base / programme
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_carto_temp_dir() -> Path:
    """Dossier local pour les couches SIG temporaires d'export automatique."""
    d = get_app_data_dir() / "cartes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_cartes_dir() -> Path:
    """Dossier des cartes générées (stockage local pour préserver le partage réseau)."""
    d = get_app_data_dir() / "cartes"
    d.mkdir(parents=True, exist_ok=True)
    return d


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