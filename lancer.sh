#!/usr/bin/env bash
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

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Détection de l'interpréteur Python
PYTHON_BIN=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
elif [ -x "$PROJECT_ROOT/.venv/bin/python3" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python &>/dev/null; then
    PYTHON_BIN="$(command -v python)"
else
    echo "[ERREUR] Aucun interpréteur Python (python3 ou python) n'a été trouvé sur ce système." >&2
    echo "         Veuillez installer Python 3 (ex: sudo apt install python3 python3-pip)." >&2
    exit 1
fi

# Export du PYTHONPATH pour accès direct aux modules core
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/core:${PYTHONPATH:-}"

# Vérification rapide des dépendances clés
if ! "$PYTHON_BIN" -c "import yaml, pandas, reportlab" &>/dev/null; then
    echo "[AVERTISSEMENT] Certaines dépendances Python recommandées semblent manquantes." >&2
    "$PYTHON_BIN" -c "
manquants = []
for mod in ['yaml', 'pandas', 'reportlab', 'openpyxl', 'matplotlib']:
    try:
        __import__(mod)
    except ImportError:
        manquants.append(mod)
if manquants:
    print('  Modules absents :', ', '.join(manquants))
    print('  Installation suggérée : pip install -r requirements.txt ou sudo apt install python3-yaml python3-pandas python3-reportlab python3-openpyxl python3-matplotlib')
" 2>/dev/null || true
fi

# Premier lancement : proposer d'installer le raccourci bureau si non encore installé
DESKTOP_ENTRY="$HOME/.local/share/applications/ofbilan.desktop"
FIRST_RUN_FLAG="$HOME/.ofbilan/.desktop_prompted"
if [ ! -f "$DESKTOP_ENTRY" ] && [ ! -f "$FIRST_RUN_FLAG" ] && [ -t 0 ] && [ $# -eq 0 ]; then
    mkdir -p "$HOME/.ofbilan"
    touch "$FIRST_RUN_FLAG"
    echo "Souhaitez-vous créer un raccourci OFBilan dans votre menu d'applications Linux ? (o/N)"
    read -r -t 10 reponse || reponse="n"
    if [[ "$reponse" =~ ^[oOyY]$ ]]; then
        bash "$PROJECT_ROOT/scripts/deploiement/installer_sur_ce_poste.sh" || true
    fi
fi

# Si des arguments CLI sont fournis, exécuter le point d'entrée CLI
if [ $# -gt 0 ]; then
    exec "$PYTHON_BIN" "$PROJECT_ROOT/core/point_entree_cli.py" "$@"
fi

# Sinon, démarrer le serveur web / GUI
echo "====================================="
echo "    Lancement d'OFBilan (Web / GUI)  "
echo "====================================="
echo "[OK] Interpréteur : $PYTHON_BIN"
echo "[OK] Racine       : $PROJECT_ROOT"
echo

exec "$PYTHON_BIN" "$PROJECT_ROOT/core/web/serveur.py"
