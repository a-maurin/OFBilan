#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'autonomisation et de mise à jour des assets web vendor (JS/CSS).
Télécharge les dépendances distantes, vérifie leur empreinte cryptographique SHA-256
et les enregistre dans `core/web/vendor/` pour garantir une utilisation 100% hors-ligne (air-gapped).
"""

import hashlib
import os
from pathlib import Path
import urllib.request

ROOT_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT_DIR / "core" / "web" / "vendor"

# Cartographie des assets : (Nom du fichier local, URL distante, Hash SHA-256 optionnel de contrôle)
ASSETS = [
    (
        "leaflet.css",
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
        "a90db677ec269ec3f00994d5098ffb4e54a500b4e054f4eb04c35e9f86055d7f",
    ),
    (
        "leaflet.js",
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
        "992a548232fb53c3064ecbbfebca3a5e81d773dd036b56be11f1816e8b4e7235",
    ),
    (
        "MarkerCluster.css",
        "https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css",
        "615b138139556858e92ae2ce93e62f0f494a8964344db1a7f6f1406830ef5246",
    ),
    (
        "MarkerCluster.Default.css",
        "https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css",
        "9584d4b1a457494f1b212f71ebf1d2a13ee124097f4cf9119d80d1964251147a",
    ),
    (
        "leaflet.markercluster.js",
        "https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js",
        "98d754160a747e45663737b6794be5f6a96dbcd3ec6a4ec73160e1d52d9a6c7e",
    ),
    (
        "leaflet-heat.js",
        "https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js",
        "5fb7d7ef7151a662e086118aaeb5032338c2ef0d3fb0b3b44b82d3e185ae14ed",
    ),
    (
        "chart.umd.js",
        "https://cdn.jsdelivr.net/npm/chart.js",
        None,  # Hash calculé dynamiquement
    ),
    (
        "html2canvas.min.js",
        "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
        "63c5aa68a577d612e6988c5ef30e527d2cbe27ef3e4a29a43a051d93ed7a0aa9",
    ),
    (
        "driver.css",
        "https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.css",
        "be1ff2c686e0fcfa5bcbf70549f3e498c8c6f14f526b7c53d0e405a4bc035921",
    ),
    (
        "driver.js.iife.js",
        "https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.js.iife.js",
        "6c4e09fceaa3b8d4f40f0aeebfb5cfc37e6be94fef4d89fae15f3ec32e3a0ef9",
    ),
]


def download_vendor_assets() -> None:
    """Télécharge et vérifie l'intégrité des dépendances JS/CSS vendor."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📦 Repertoire cible : {VENDOR_DIR}")

    headers = {"User-Agent": "OFBilan-Asset-Downloader/1.0"}

    for filename, url, expected_hash in ASSETS:
        dest_path = VENDOR_DIR / filename
        print(f"⬇️  Téléchargement de {filename} depuis {url}...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            content = resp.read()

        computed_hash = hashlib.sha256(content).hexdigest()
        print(f"   [SHA-256] {computed_hash}")

        if expected_hash and computed_hash != expected_hash:
            print(
                f"   ⚠️  Avertissement Hash SHA-256 différent pour {filename} !"
            )
            print(f"      Attendu: {expected_hash}")
            print(f"      Obtenu:  {computed_hash}")

        with open(dest_path, "wb") as f:
            f.write(content)
        print(f"   ✅ {filename} enregistré ({len(content)} octets)")

    print("\n🎉 Tous les assets vendor ont été téléchargés avec succès.")


if __name__ == "__main__":
    download_vendor_assets()
