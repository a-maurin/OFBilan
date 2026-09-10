# -*- coding: utf-8 -*-
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

"""
Module d'assistance au diagnostic technique et à la préparation de la boîte noire.

Ce module regroupe les fonctions nécessaires pour :
1. Collecter l'environnement système, matériel et logiciel du poste client.
2. Gérer un historique tournant des 3 derniers journaux de génération.
3. Extraire un échantillon des 50 premières lignes des sources de données selon les filtres du run.
"""

from __future__ import annotations

import ctypes
import io
import json
import logging
import os
import platform
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from core.chemins_projet import PROJECT_ROOT, get_app_data_dir

logger = logging.getLogger(__name__)

NB_MAX_LOGS_RUN = 3
NB_LIGNES_ECHANTILLON_DEFAUT = 50


def get_generations_log_dir() -> Path:
    """Retourne le dossier dédié aux journaux d'exécution des bilans."""
    d = get_app_data_dir() / "logs" / "generations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def initialiser_journal_generation(max_runs: int = NB_MAX_LOGS_RUN) -> Path:
    """
    Crée un nouveau fichier journal horodaté pour une exécution de bilan.
    Effectue une rotation pour ne conserver au maximum que les `max_runs` plus récents.
    """
    log_dir = get_generations_log_dir()
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    nouveau_fichier = log_dir / f"generation_{now_str}.log"

    try:
        fichiers_existants = sorted(
            log_dir.glob("generation_*.log"),
            key=lambda p: p.stat().st_mtime,
        )
        surplus = len(fichiers_existants) - (max_runs - 1)
        if surplus > 0:
            for f in fichiers_existants[:surplus]:
                try:
                    f.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning("Impossible de purger l'ancien journal %s : %s", f.name, e)
    except Exception as e:
        logger.warning("Erreur lors de la rotation des journaux de génération : %s", e)

    try:
        nouveau_fichier.write_text(
            f"=== DÉBUT D'EXÉCUTION DU BILAN [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ===\n\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Impossible d'initialiser le fichier journal %s : %s", nouveau_fichier.name, e)

    return nouveau_fichier


def obtenir_chemins_journaux_recents(max_runs: int = NB_MAX_LOGS_RUN) -> list[Path]:
    """Retourne la liste des journaux de génération récents triés du plus récent au plus ancien."""
    log_dir = get_generations_log_dir()
    fichiers = sorted(
        log_dir.glob("generation_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return fichiers[:max_runs]


def enregistrer_derniers_parametres_run(params: dict[str, Any]) -> None:
    """Enregistre les paramètres du dernier run demandé dans un fichier json."""
    try:
        fichier_params = get_app_data_dir() / "logs" / "dernier_run_params.json"
        fichier_params.parent.mkdir(parents=True, exist_ok=True)
        fichier_params.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Impossible d'enregistrer les paramètres du run : %s", e)


def lire_derniers_parametres_run() -> dict[str, Any]:
    """Lit les paramètres du dernier run depuis le fichier json si présent."""
    try:
        fichier_params = get_app_data_dir() / "logs" / "dernier_run_params.json"
        if fichier_params.is_file():
            return json.loads(fichier_params.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Impossible de lire les paramètres du dernier run : %s", e)
    return {}


def _obtenir_memoire_disponible() -> str:
    """Retourne une estimation textuelle de la mémoire vive disponible."""
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_go = stat.ullTotalPhys / (1024**3)
                dispo_go = stat.ullAvailPhys / (1024**3)
                return f"{dispo_go:.1f} Go libres sur {total_go:.1f} Go totaux ({stat.dwMemoryLoad}% utilisés)"
    except Exception:
        pass
    return "Non disponible"


def _obtenir_espace_disque(chemin: Path) -> str:
    """Retourne l'espace disque disponible sur la partition du chemin donné."""
    try:
        usage = shutil.disk_usage(chemin)
        dispo_go = usage.free / (1024**3)
        total_go = usage.total / (1024**3)
        return f"{dispo_go:.1f} Go libres sur {total_go:.1f} Go totaux"
    except Exception:
        return "Non disponible"


def _detecter_version_qgis() -> str:
    """Tente de déterminer la version de QGIS présente dans l'environnement."""
    try:
        import qgis.core
        if hasattr(qgis.core, "Qgis") and hasattr(qgis.core.Qgis, "QGIS_VERSION"):
            return str(qgis.core.Qgis.QGIS_VERSION)
        return "Inconnue"
    except Exception:
        pass

    qgis_prefix = os.environ.get("QGIS_PREFIX_PATH")
    if qgis_prefix:
        return f"Environnement QGIS détecté ({qgis_prefix})"
    return "Hors QGIS (mode autonome ou serveur web)"


def collecter_diagnostic_systeme(run_params: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Rassemble les métadonnées techniques, logicielles et matérielles du poste utilisateur.
    """
    if run_params is None:
        run_params = lire_derniers_parametres_run()

    from core.parametres_utilisateur import get_settings_file_path

    # Vérification de l'accessibilité des données sources majeures
    sources_statut: dict[str, Any] = {}
    chemins_cles = {
        "dossier_projet": PROJECT_ROOT,
        "referentiels_sig": PROJECT_ROOT / "ref" / "programme" / "sig",
        "tables_reference": PROJECT_ROOT / "ref" / "programme" / "tables_reference",
        "donnees_pej": PROJECT_ROOT / "data" / "pej",
        "donnees_pve": PROJECT_ROOT / "data" / "pve",
        "donnees_pa": PROJECT_ROOT / "data" / "pa",
    }
    for label, p in chemins_cles.items():
        sources_statut[label] = {
            "chemin": str(p),
            "existe": p.exists(),
            "est_dossier": p.is_dir() if p.exists() else False,
        }

    return {
        "horodatage": datetime.now().isoformat(),
        "environnement": {
            "systeme_exploitation": f"{platform.system()} {platform.release()} ({platform.version()})",
            "architecture": platform.machine(),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "version_qgis": _detecter_version_qgis(),
            "encodage_systeme": sys.getdefaultencoding(),
            "encodage_fichiers": sys.getfilesystemencoding(),
        },
        "ressources": {
            "memoire_ram": _obtenir_memoire_disponible(),
            "espace_disque_projet": _obtenir_espace_disque(PROJECT_ROOT),
            "espace_disque_appdata": _obtenir_espace_disque(get_app_data_dir()),
        },
        "chemins": {
            "racine_projet": str(PROJECT_ROOT),
            "dossier_appdata": str(get_app_data_dir()),
            "fichier_parametres": str(get_settings_file_path()),
        },
        "sources_donnees": sources_statut,
        "parametres_dernier_calcul": run_params,
    }


def extraire_echantillons_donnees(
    params: dict[str, Any] | None = None,
    nb_lignes: int = NB_LIGNES_ECHANTILLON_DEFAUT,
) -> dict[str, str]:
    """
    Extrait un échantillon des premières lignes des jeux de données chargés,
    filtrés selon le périmètre et la période du dernier run pour aider à la reproduction.
    Retourne un dictionnaire {nom_fichier_csv: contenu_texte_csv}.
    """
    if params is None:
        params = lire_derniers_parametres_run()

    echelle = str(params.get("echelle", "national"))
    code = str(params.get("code", "FR"))
    date_deb = params.get("date-deb") or params.get("date_deb")
    date_fin = params.get("date-fin") or params.get("date_fin")

    echantillons: dict[str, str] = {}

    from core.common.chargeurs_donnees import load_point_ctrl, load_pej, load_pa, load_pve

    loaders = [
        ("point_ctrl_echantillon.csv", load_point_ctrl),
        ("pej_echantillon.csv", load_pej),
        ("pa_echantillon.csv", load_pa),
        ("pve_echantillon.csv", load_pve),
    ]

    for filename, loader_func in loaders:
        try:
            df = loader_func(
                PROJECT_ROOT,
                echelle=echelle,
                code=code,
                date_deb=date_deb,
                date_fin=date_fin,
            )
            if df is not None and hasattr(df, "head"):
                sample_df = df.head(nb_lignes)
                echantillons[filename] = sample_df.to_csv(index=False, sep=";", encoding="utf-8")
            else:
                echantillons[filename] = f"Données vides ou non chargées pour le filtre ({echelle}={code}).\n"
        except Exception as e:
            echantillons[f"erreur_{filename}.txt"] = f"Échec d'extraction de l'échantillon ({filename}) : {e}\n"

    return echantillons


def generer_archive_diagnostic(nb_lignes_echantillon: int = NB_LIGNES_ECHANTILLON_DEFAUT) -> bytes:
    """
    Assemble à la volée une archive zip en mémoire contenant :
    - Le rapport de diagnostic système au format JSON et texte lisible.
    - Le journal du serveur web (serveur_web.log).
    - Les journaux récents d'exécution de bilans (generation_*.log).
    - Les échantillons des données sources filtrées (CSV).
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Diagnostic système JSON et résumé texte
        try:
            diag_dict = collecter_diagnostic_systeme()
            zf.writestr("diagnostic_systeme.json", json.dumps(diag_dict, ensure_ascii=False, indent=2, default=str))

            env = diag_dict.get("environnement", {})
            res = diag_dict.get("ressources", {})
            params = diag_dict.get("parametres_dernier_calcul", {})
            resume = (
                f"Résumé du diagnostic OFBilan\n"
                f"Date : {diag_dict.get('horodatage', '')}\n"
                f"Système : {env.get('systeme_exploitation', '')} ({env.get('architecture', '')})\n"
                f"Python : {env.get('python_version', '').split()[0]} ({env.get('python_executable', '')})\n"
                f"QGIS : {env.get('version_qgis', '')}\n"
                f"Mémoire vive : {res.get('memoire_ram', '')}\n"
                f"Espace disque projet : {res.get('espace_disque_projet', '')}\n"
                f"Espace disque AppData : {res.get('espace_disque_appdata', '')}\n\n"
                f"Paramètres du dernier calcul :\n{json.dumps(params, ensure_ascii=False, indent=2, default=str)}\n"
            )
            zf.writestr("resume_diagnostic.txt", resume)
        except Exception as e:
            zf.writestr("erreur_diagnostic_systeme.txt", f"Échec collecte diagnostic : {e}\n")

        # 2. Journal du serveur web
        try:
            from core.chemins_projet import get_app_data_dir
            server_log = get_app_data_dir() / "logs" / "serveur_web.log"
            if server_log.is_file():
                zf.writestr("logs/serveur_web.log", server_log.read_bytes())
        except Exception as e:
            zf.writestr("logs/erreur_serveur_web.txt", f"Échec lecture serveur_web.log : {e}\n")

        # 3. Journaux de génération récents
        try:
            journaux_run = obtenir_chemins_journaux_recents(max_runs=NB_MAX_LOGS_RUN)
            for j in journaux_run:
                if j.is_file():
                    zf.writestr(f"logs/{j.name}", j.read_bytes())
        except Exception as e:
            zf.writestr("logs/erreur_journaux_generation.txt", f"Échec lecture journaux génération : {e}\n")

        # 4. Échantillons de données
        try:
            echantillons = extraire_echantillons_donnees(nb_lignes=nb_lignes_echantillon)
            for nom_fich, contenu in echantillons.items():
                zf.writestr(f"echantillons/{nom_fich}", contenu.encode("utf-8"))
        except Exception as e:
            zf.writestr("echantillons/erreur_echantillonnage.txt", f"Échec extraction échantillons : {e}\n")

    return buffer.getvalue()
