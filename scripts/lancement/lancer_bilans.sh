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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/core:${PYTHONPATH:-}"

PYTHON_BIN=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
elif [ -x "$ROOT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python &>/dev/null; then
    PYTHON_BIN="$(command -v python)"
else
    echo "[ERREUR] Impossible de trouver l'interpréteur Python." >&2
    exit 1
fi

# Si des arguments sont fournis, passage direct en mode non interactif
if [ $# -gt 0 ]; then
    exec "$PYTHON_BIN" "$ROOT_DIR/core/point_entree_cli.py" "$@"
fi

echo "  OOOOOOO   FFFFFFF   BBBBBBB "
echo "  OOOOOOO   FFFFFFF   BBBBBBB "
echo "  OO   OO   FF        BB   BB"
echo "  OO   OO   FFFFFF    BBBBBBB"
echo "  OO   OO   FFFFFF    BBBBBBB"
echo "  OO   OO   FF        BB   BB"
echo "  OOOOOOO   FF        BBBBBBB"
echo "  OOOOOOO   FF        BBBBBBB"
echo
echo "     OFFICE FRANCAIS"
echo "   DE LA BIODIVERSITE"
echo
echo "==============================================="
echo "  Bilans - Par profil (global ou thématiques)  "
echo "==============================================="
echo

CURRENT_YEAR="$(date +%Y)"
DATE_FIN_DEFAULT="$(date +%Y-%m-%d)"
DATE_DEB_DEFAULT="${CURRENT_YEAR}-01-01"

read -r -p "Date de début (YYYY-MM-DD ou YYYY) [$DATE_DEB_DEFAULT] > " DATE_DEB
DATE_DEB="${DATE_DEB:-$DATE_DEB_DEFAULT}"

read -r -p "Date de fin   (YYYY-MM-DD ou YYYY) [$DATE_FIN_DEFAULT] > " DATE_FIN
DATE_FIN="${DATE_FIN:-$DATE_FIN_DEFAULT}"

read -r -p "Code département (Côte-d'Or) [21] > " DEPT
DEPT="${DEPT:-21}"

# Normalisation si seule l'année est saisie
if [[ "$DATE_DEB" =~ ^[0-9]{4}$ ]]; then
    DATE_DEB="${DATE_DEB}-01-01"
fi
if [[ "$DATE_FIN" =~ ^[0-9]{4}$ ]]; then
    DATE_FIN="${DATE_FIN}-12-31"
fi

echo
echo "Période : $DATE_DEB au $DATE_FIN - Département $DEPT"
echo
echo "1. Bilan global uniquement"
echo "2. Bilan(s) thématique(s) - agrainage, chasse, piégeage, etc."
echo

CHOIX=""
while [[ "$CHOIX" != "1" && "$CHOIX" != "2" ]]; do
    read -r -p "Choix (1 ou 2) > " CHOIX
    if [[ "$CHOIX" != "1" && "$CHOIX" != "2" ]]; then
        echo "Choix invalide. Veuillez saisir 1 ou 2."
    fi
done

if [ "$CHOIX" = "1" ]; then
    echo "=== Bilan global ==="
    exec "$PYTHON_BIN" "$ROOT_DIR/core/point_entree_cli.py" --profil global --date-deb "$DATE_DEB" --date-fin "$DATE_FIN" --dept-code "$DEPT"
else
    echo
    echo "Profils disponibles :"
    "$PYTHON_BIN" "$ROOT_DIR/core/point_entree_cli.py" --list-themes
    echo
    read -r -p "Profil(s) à lancer (numéro(s) ou id, séparés par des espaces) [2 3] > " PROFILS
    PROFILS="${PROFILS:-2 3}"

    CLI_ARGS=()
    for p in $PROFILS; do
        CLI_ARGS+=(--profil "$p")
    done

    echo "=== Génération des bilans thématiques ==="
    exec "$PYTHON_BIN" "$ROOT_DIR/core/point_entree_cli.py" "${CLI_ARGS[@]}" --date-deb "$DATE_DEB" --date-fin "$DATE_FIN" --dept-code "$DEPT"
fi
