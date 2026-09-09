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
Tests unitaires pour la vérification de l'autonomisation locale (vendoring)
et de l'absence totale de fuites de métadonnées / CDN distants dans l'Explorer GUI.
"""

import hashlib
from pathlib import Path
import urllib.request
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
VENDOR_DIR = ROOT_DIR / "core" / "web" / "vendor"
EXPLORER_HTML_PATH = ROOT_DIR / "core" / "web" / "explorer.html"

# Assets vendor requis avec leurs URLs de secours
VENDOR_ASSETS = [
    ("leaflet.css", "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
    ("leaflet.js", "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
    (
        "MarkerCluster.css",
        "https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css",
    ),
    (
        "MarkerCluster.Default.css",
        "https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css",
    ),
    (
        "leaflet.markercluster.js",
        "https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js",
    ),
    (
        "leaflet-heat.js",
        "https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js",
    ),
    ("chart.umd.js", "https://cdn.jsdelivr.net/npm/chart.js"),
    (
        "html2canvas.min.js",
        "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
    ),
    (
        "driver.css",
        "https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.css",
    ),
    (
        "driver.js.iife.js",
        "https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.js.iife.js",
    ),
]


def ensure_vendor_assets_exist():
    """S'assure que tous les assets vendor sont présents physiquement."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "OFBilan-Test-Setup/1.0"}

    for filename, url in VENDOR_ASSETS:
        dest_file = VENDOR_DIR / filename
        if not dest_file.exists() or dest_file.stat().st_size == 0:
            print(f"Téléchargement automatique de {filename} depuis {url}...")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                content = resp.read()
            with open(dest_file, "wb") as f:
                f.write(content)


def test_all_vendor_assets_present_and_non_empty():
    """Vérifie que les 10 fichiers d'assets vendor sont présents et non vides."""
    ensure_vendor_assets_exist()

    for filename, _ in VENDOR_ASSETS:
        asset_file = VENDOR_DIR / filename
        assert asset_file.exists(), (
            f"Fichier vendor manquant : {asset_file.name}"
        )
        assert asset_file.stat().st_size > 100, (
            f"Fichier vendor suspect (trop petit/vide) : {asset_file.name}"
        )


def test_explorer_html_has_no_external_cdn_references():
    """Vérifie l'absence totale de scripts et feuilles de style distants (CDN) dans explorer.html."""
    assert EXPLORER_HTML_PATH.exists(), "explorer.html est introuvable."

    content = EXPLORER_HTML_PATH.read_text(encoding="utf-8")

    forbidden_cdns = ["unpkg.com", "jsdelivr.net", "cdnjs.cloudflare.com"]

    for cdn in forbidden_cdns:
        assert cdn not in content, (
            f"Dépendance externe CDN interdite détectée dans explorer.html : {cdn}"
        )


def test_explorer_html_uses_local_vendor_paths():
    """Vérifie que explorer.html référence bien les fichiers vendor locaux."""
    content = EXPLORER_HTML_PATH.read_text(encoding="utf-8")

    expected_local_assets = [
        "vendor/leaflet.css",
        "vendor/MarkerCluster.css",
        "vendor/MarkerCluster.Default.css",
        "vendor/driver.css",
        "vendor/leaflet.js",
        "vendor/leaflet.markercluster.js",
        "vendor/leaflet-heat.js",
        "vendor/chart.umd.js",
        "vendor/html2canvas.min.js",
        "vendor/driver.js.iife.js",
    ]

    for asset in expected_local_assets:
        assert asset in content, (
            f"Asset local manquant dans explorer.html : {asset}"
        )
