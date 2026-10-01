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
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "================================================="
echo "     Installation d'OFBilan sur ce poste Linux   "
echo "================================================="
echo "Dossier source détecté : $PROJECT_ROOT"
echo

# 1. Droits d'exécution sur les scripts
chmod +x "$PROJECT_ROOT/lancer.sh" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/scripts/lancement/"*.sh 2>/dev/null || true
chmod +x "$PROJECT_ROOT/scripts/maintenance/"*.sh 2>/dev/null || true

# 2. Création de l'entrée de bureau (.desktop)
echo "[1/2] Création du raccourci applicatif..."
APPLICATIONS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPLICATIONS_DIR"

ICON_PATH="$PROJECT_ROOT/icon.png"
if [ ! -f "$ICON_PATH" ]; then
    ICON_PATH="$PROJECT_ROOT/icon.svg"
fi

DESKTOP_FILE="$APPLICATIONS_DIR/ofbilan.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=OFBilan
GenericName=Générateur et explorateur de bilans
Comment=Exploration des contrôles et édition automatisée des bilans d'activité OFB
Exec=/bin/bash "$PROJECT_ROOT/lancer.sh"
Icon=$ICON_PATH
Terminal=false
Categories=Office;Development;Geography;
StartupWMClass=OFBilan
EOF
chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APPLICATIONS_DIR" &>/dev/null || true
fi
echo "  [OK] Lanceur installé dans le menu d'applications : $DESKTOP_FILE"

# Raccourci sur le Bureau si le dossier existe
DESKTOP_DIR=""
if [ -d "$HOME/Bureau" ]; then
    DESKTOP_DIR="$HOME/Bureau"
elif [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
fi

if [ -n "$DESKTOP_DIR" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_DIR/ofbilan.desktop"
    chmod +x "$DESKTOP_DIR/ofbilan.desktop"
    if command -v gio &>/dev/null; then
        gio set "$DESKTOP_DIR/ofbilan.desktop" metadata::trusted true 2>/dev/null || true
    fi
    echo "  [OK] Raccourci créé sur le Bureau : $DESKTOP_DIR/ofbilan.desktop"
fi

# 3. Configuration de l'extension relais pour QGIS (si QGIS3 est installé)
echo
echo "[2/2] Détection des profils QGIS..."
QGIS_PROFILES_DIR="$HOME/.local/share/QGIS/QGIS3/profiles"
if [ -d "$QGIS_PROFILES_DIR" ]; then
    for prof in "$QGIS_PROFILES_DIR"/*; do
        if [ -d "$prof" ]; then
            PLUGINS_DIR="$prof/python/plugins"
            mkdir -p "$PLUGINS_DIR"
            ln -sfn "$PROJECT_ROOT" "$PLUGINS_DIR/OFBilan"
            echo "  [OK] Extension relais branchée dans le profil : $(basename "$prof")"
        fi
    done
else
    echo "  [INFO] Aucun profil QGIS local détecté dans $QGIS_PROFILES_DIR (non bloquant)."
fi

echo
echo "================================================="
echo "Installation terminée avec succès !"
echo "Vous pouvez désormais lancer OFBilan via :"
echo "  - Le raccourci Bureau ou le menu des applications"
echo "  - La commande ./lancer.sh depuis la racine du projet"
echo "================================================="
