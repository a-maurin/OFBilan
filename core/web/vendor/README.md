# Dépendances Web GUI Autonomes (Vendor)

Ce répertoire contient les bibliothèques JavaScript et feuilles de style CSS autonomes requises pour le fonctionnement de l'interface graphique web (Explorer GUI - `explorer.html`).

Toutes les ressources ci-dessous sont hébergées et servies en local par le serveur web Python (`http://localhost:8000/vendor/...`) afin de garantir un fonctionnement 100% hors-ligne (*air-gapped*), résilient et sans aucune fuite de métadonnées vers des CDN distants.

---

## Registre des Bibliothèques Incluses

| Fichier | Bibliothèque | Version | URL Source d'origine | Licence |
| :--- | :--- | :--- | :--- | :--- |
| `leaflet.css` | Leaflet CSS | 1.9.4 | `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css` | BSD-2-Clause |
| `leaflet.js` | Leaflet JS | 1.9.4 | `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js` | BSD-2-Clause |
| `MarkerCluster.css` | Leaflet MarkerCluster CSS | 1.4.1 | `https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css` | MIT |
| `MarkerCluster.Default.css` | Leaflet MarkerCluster Default CSS | 1.4.1 | `https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css` | MIT |
| `leaflet.markercluster.js` | Leaflet MarkerCluster JS | 1.4.1 | `https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js` | MIT |
| `leaflet-heat.js` | Leaflet Heatmap JS | 0.2.0 | `https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js` | BSD-2-Clause |
| `chart.umd.js` | Chart.js | 4.4.1 | `https://cdn.jsdelivr.net/npm/chart.js` | MIT |
| `html2canvas.min.js` | html2canvas | 1.4.1 | `https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js` | MIT |
| `driver.css` | Driver.js CSS | 1.3.1 | `https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.css` | MIT |
| `driver.js.iife.js` | Driver.js | 1.3.1 | `https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.js.iife.js` | MIT |

---

## Procédure de Mise à Jour

Pour mettre à jour ou retélécharger ces dépendances en vérifiant leur intégrité SHA-256, exécuter le script :

```bash
python3 scripts/donnees/download_vendor_assets.py
```
