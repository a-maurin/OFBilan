import os
import shutil
import glob
import re
from datetime import datetime
from pathlib import Path
import stat

# Chemins
SERVER_ROOT = Path(r"\\ad.intra\dfs\COMMUNS\CENTRAL\ECHANGE\SSSC")
PVE_DIR = SERVER_ROOT / "PVe" / "Statistiques"
PEJ_PA_DIR = SERVER_ROOT / "OSCEAN" / "1-Données" / "suivi_procedures"
SIG_DIR = SERVER_ROOT / "OSCEAN" / "2-Carto"

LOCAL_ROOT = Path(os.getcwd())
LOCAL_SOURCES = LOCAL_ROOT / "data" / "sources"
LOCAL_SOURCES_SIG = LOCAL_SOURCES / "sig"
ARCHIVE_DIR = LOCAL_ROOT / "data" / "sources_archive"

def archive_existing_sources():
    if not LOCAL_SOURCES.exists():
        return
    
    # S'il est vide, on ne fait rien
    if not any(LOCAL_SOURCES.iterdir()):
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = ARCHIVE_DIR / timestamp
    
    print(f"Archivage des sources existantes vers : {archive_path}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Pour éviter de déplacer le dossier racine complet (ce qui pourrait gêner Git si des choses sont trackées),
    # on déplace le contenu de data/sources/ vers l'archive.
    archive_path.mkdir(exist_ok=True)
    for item in LOCAL_SOURCES.iterdir():
        if item.name == ".gitkeep":
            continue
        dest = archive_path / item.name
        try:
            shutil.move(str(item), str(dest))
        except PermissionError as e:
            print(f"\n[ERREUR] Impossible de déplacer '{item.name}'.")
            print(f"Détail de l'erreur : {e}")
            print("\n-> Le fichier est probablement ouvert dans QGIS ou un autre programme.")
            print("-> Veuillez fermer QGIS et relancer le script.")
            import sys
            sys.exit(1)
        except Exception as e:
            print(f"\n[ERREUR inattendue] Impossible de déplacer '{item.name}' : {e}")
            import sys
            sys.exit(1)
    
    print("Archivage terminé.")

def get_latest_file(directory: Path, pattern: str) -> Path:
    """Trouve le fichier le plus récent (basé sur la date de modification) qui correspond au motif."""
    files = list(directory.glob(pattern))
    if not files:
        return None
    
    # On trie par date de modification (mtime)
    # ou on peut essayer de parser la date dans le nom du fichier. 
    # Prenons la date de modification pour être sûr (ou le tri par nom si c'est formaté).
    # Le plus sûr pour "Stats_PVe_OFB au 02.03.2026.xlsx" ou "suivi_procedure_enq_judiciaire_20260423.ods"
    # est souvent le mtime ou la logique métier. On prend mtime.
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return latest

def fetch_pve():
    print(f"\n--- Récupération PVe ---")
    if not PVE_DIR.exists():
        print(f"Erreur : le dossier {PVE_DIR} est inaccessible.")
        return
    latest = get_latest_file(PVE_DIR, "Stats_PVe_OFB au *.xlsx")
    if latest:
        dest = LOCAL_SOURCES / latest.name
        print(f"Copie de : {latest.name}")
        LOCAL_SOURCES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(latest, dest)
    else:
        print("Aucun fichier PVe trouvé.")

def fetch_pej_pa():
    print(f"\n--- Récupération PEJ et PA ---")
    if not PEJ_PA_DIR.exists():
        print(f"Erreur : le dossier {PEJ_PA_DIR} est inaccessible.")
        return
    
    # PEJ
    latest_pej = get_latest_file(PEJ_PA_DIR, "suivi_procedure_enq_judiciaire_*.ods")
    if latest_pej:
        dest = LOCAL_SOURCES / latest_pej.name
        print(f"Copie de : {latest_pej.name}")
        LOCAL_SOURCES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(latest_pej, dest)
    else:
        print("Aucun fichier PEJ trouvé.")
        
    # PA
    latest_pa = get_latest_file(PEJ_PA_DIR, "suivi_procedure_administrative_*.ods")
    if latest_pa:
        dest = LOCAL_SOURCES / latest_pa.name
        print(f"Copie de : {latest_pa.name}")
        LOCAL_SOURCES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(latest_pa, dest)
    else:
        print("Aucun fichier PA trouvé.")

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def fetch_sig():
    print(f"\n--- Récupération données SIG (Points de contrôle) ---")
    if not SIG_DIR.exists():
        print(f"Erreur : le dossier {SIG_DIR} est inaccessible.")
        return
    
    # On cherche les dossiers points_de_ctrl_OSCEAN_*
    sig_folders = [d for d in SIG_DIR.glob("points_de_ctrl_OSCEAN_*") if d.is_dir()]
    if not sig_folders:
        print("Aucun dossier SIG trouvé.")
        return
    
    for folder in sig_folders:
        dest = LOCAL_SOURCES_SIG / folder.name
        print(f"Copie du dossier SIG : {folder.name}")
        if dest.exists():
            shutil.rmtree(dest, onerror=remove_readonly)
        shutil.copytree(folder, dest)
        
    # Copie du dossier point_infraction_PJ (GPKG localisés + CSV non localisés)
    pj_folder = SIG_DIR / "point_infraction_PJ"
    if pj_folder.exists() and pj_folder.is_dir():
        dest = LOCAL_SOURCES_SIG / pj_folder.name
        print(f"Copie du dossier SIG : {pj_folder.name}")
        if dest.exists():
            shutil.rmtree(dest, onerror=remove_readonly)
        shutil.copytree(pj_folder, dest)


def fetch_infrac_non_localises():
    """Copie le CSV des infractions PEJ non localisées (infrac_FAITS_non_localises_*.csv)
    depuis le serveur vers data/sources/sig/point_infraction_PJ/.

    Ce fichier recense les dossiers PEJ dont les faits n'ont pas pu être géolocalisés
    dans OSCEAN (geometry vide). Il est utilisé pour comptabiliser de façon fiable
    le nombre de PEJ sans commune dans le bilan.
    """
    print(f"\n--- Récupération des PEJ non localisées (CSV) ---")
    pj_server = SIG_DIR / "point_infraction_PJ"
    if not pj_server.exists():
        print(f"Dossier point_infraction_PJ inaccessible sur le serveur : {pj_server}")
        return

    latest = get_latest_file(pj_server, "infrac_FAITS_non_localises_*.csv")
    if not latest:
        print("Aucun fichier infrac_FAITS_non_localises_*.csv trouvé.")
        return

    dest_dir = LOCAL_SOURCES_SIG / "point_infraction_PJ"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / latest.name
    print(f"Copie de : {latest.name}")
    shutil.copy2(latest, dest)

def main():
    print("Démarrage de la récupération automatique des sources...")
    
    archive_existing_sources()
    fetch_pve()
    fetch_pej_pa()
    fetch_sig()
    fetch_infrac_non_localises()
    
    print("\nTerminé avec succès.")

if __name__ == "__main__":
    main()
