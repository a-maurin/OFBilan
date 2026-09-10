![OFBilan banner](ref/programme/logos/bandeau_ofbilan.svg)

# OFBilan

[![QGIS](https://img.shields.io/badge/QGIS-3.22%2B%20LTR-green.svg)](https://qgis.org)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)
[![Licence](https://img.shields.io/badge/Licence-GPLv3-orange.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Plateforme](https://img.shields.io/badge/Plateforme-Windows%2010%20%2F%2011-lightgrey.svg)]()

**OFBilan** est une application autonome d'aide à la décision, d'exploration de données et de communication, dotée d'une intégration optionnelle sous forme d'extension relais pour QGIS. Elle s'appuie sur les données de contrôles (OSCEAN) et les procédures judiciaires et administratives (PVe, PEJ, PA) de l'Office français de la biodiversité (OFB).

---

## Fonctionnalités principales

Le programme s'articule autour de deux modules majeurs :

### 1. OFBilan Explorer (analyse interactive)
Une interface web locale pour l'exploration fluide des données de contrôle :
* **Cartographie interactive (Leaflet)** : visualisation géographique instantanée des points de contrôle, regroupements dynamiques (clusters) et génération de cartes de chaleur (heatmaps) filtrables par année.
* **Tableaux de bord (Chart.js)** : indicateurs clés actualisés selon l'emprise spatiale et les filtres actifs (répartition par thématique, suites données, profils d'usagers).
* **Filtrage multicritère à la volée** : affinage instantané des données par période temporelle, département, brigade (BMI), catégorie d'usager ou nature d'infraction.
* **Ergonomie réactive** : légende dynamique, console d'information intégrée et export d'extraits cartographiques.

### 2. Éditeur de bilans PDF (génération de rapports)
Un moteur d'édition automatisé piloté par des gabarits déclaratifs en YAML :
* **Gabarits modulaires et catalogue sur mesure** : bilans d'activité globaux, thématiques ciblées (eau, chasse, espèces protégées, pollutions) ou synthèses territoriales, avec mise en page verrouillée sur des formats stricts (ex. fiches A4 autonomes).
* **Mise en page et infographies avancées** : restitution soignée intégrant diagrammes de saisonnalité mensuelle, répartition des usagers et tableaux consolidés des infractions.
* **Gestion de la confidentialité** : double périmètre de diffusion paramétrable (versions internes détaillées ou versions externes anonymisées pour les partenaires institutionnels).
* **Cartographie native intégrée** : communication directe avec le moteur de rendu de QGIS pour générer et intégrer automatiquement des cartes d'activité dans les rapports PDF.

---

## Atouts et architecture technique

* **Zéro configuration Python** : l'application exploite directement l'interpréteur Python et les bibliothèques géospatiales embarqués dans votre installation QGIS locale (`gdal`, `geopandas`, `fiona`, `reportlab`).
* **Miroir SSD local transparent** : en cas d'exécution depuis un partage réseau d'entreprise, un miroir local est synchronisé automatiquement dans le profil utilisateur pour garantir un démarrage instantané et une résilience hors-ligne.
* **Sécurité et confidentialité totales** : traitement 100% local (`http://localhost:8000`), sans dépendance à des CDN externes (assets web locaux autonomes) et sans aucune fuite de données nominatives ou sensibles vers l'extérieur.

---

## Prérequis système

* **Système d'exploitation** : Windows 10 ou 11 (64 bits).
* **QGIS** : **QGIS 3.22 LTR ou supérieur** installé sur le poste (versions recommandées : 3.28 LTR, 3.34 LTR ou 3.40+).
* **Environnement Python** : Python $\ge$ 3.8 (fourni nativement avec QGIS).
> ⚠️ **Incompatibilité** : les versions antérieures de QGIS (ex. QGIS 3.10 et 3.16) reposant sur Python 3.7 ne sont pas supportées.

---

## Installation et configuration

### Méthode 1 : Déploiement en réseau partagé (recommandé pour les services)
Si OFBilan est hébergé sur un lecteur réseau ou serveur partagé de votre service :
1. Ouvrez le dossier réseau partagé d'OFBilan.
2. Double-cliquez sur le script [`installer_sur_ce_poste.bat`](file:///scripts/deploiement/installer_sur_ce_poste.ps1) (situé dans `scripts/deploiement/`).
3. L'installation s'effectue en quelques secondes sans aucun droit administrateur :
   * Un raccourci de lancement **OFBilan** est créé sur votre Bureau.
   * L'extension relais est automatiquement branchée dans vos profils QGIS.

### Méthode 2 : Installation autonome ou poste développeur
Pour une installation isolée (clone Git ou copie locale sans partage réseau) :
1. Clonez le dépôt ou décompressez l'archive du code source sur votre poste.
2. **Référentiels et données sources** : les données métier (`data/sources/`) et fonds géographiques (`ref/programme/`) étant confidentiels, déposez l'archive `pack_configuration_referentiels.zip` et exécutez le script `scripts/deploiement/installer_pack.bat`.
3. Lancez l'application via `scripts/lancement/demarrer_serveur_OFBilan.bat`.

### Désinstallation et réinitialisation
Pour remettre un poste client à l'état vierge, exécutez le script :
`scripts/deploiement/nettoyer_poste_client.bat`
Ce script supprime les raccourcis Bureau, le cache local (`%LOCALAPPDATA%\OFBilan`), les relais QGIS et les dossiers temporaires sans affecter les données du serveur partagé.

---

## Guide d'utilisation

### Mode 1 : Application de bureau (recommandé)
1. Double-cliquez sur le raccourci **OFBilan** sur votre Bureau (ou lancez `scripts/lancement/demarrer_serveur_OFBilan.bat`).
2. Le serveur local démarre automatiquement en arrière-plan et l'interface s'ouvre dans votre navigateur par défaut.
3. Pour quitter, fermez simplement la fenêtre de commande ou la page web.

### Mode 2 : Depuis QGIS
1. Ouvrez QGIS : l'extension relais **OFBilan** est disponible dans votre barre d'outils et dans le menu **Extensions > OFBilan**.
2. Cliquez sur l'icône OFBilan pour lancer l'application et accéder aux outils d'édition.
3. À la fermeture de QGIS, le serveur s'arrête automatiquement.

### Mode 3 : Ligne de commande (CLI et automatisation)
Pour générer des bilans par lots ou intégrer des scripts planifiés, utilisez l'exécutable Python de QGIS :
```bash
# Génération d'un bilan global pour l'année 2026 sur le département 21
"C:\Program Files\QGIS 3.40.11\bin\python.exe" -m ofbilan --profil global --date-deb 2026-01-01 --date-fin 2026-12-31 --code 21

# Bilan anonymisé pour diffusion externe sans cartes
python -m ofbilan --profil pnf --code 21 --diffusion externe --no-cartes

# Consultation de la liste des profils et options
python -m ofbilan --list-themes
python -m ofbilan --list-type-usagers
```

---

## Espace développeurs et tests

Pour exécuter la suite de tests automatisés avec l'environnement Python de QGIS :
```bash
# Exécution de l'ensemble des tests unitaires
pytest tests/unit

# Exécution d'un test spécifique
pytest tests/unit/test_pdf_context.py
```

---

## Structure du projet

* `core/` : moteur applicatif (serveur FastAPI, calculs statistiques, génération PDF ReportLab et interface web).
* `config/` : profils d'analyse métier, gabarits YAML de présentation et configurations cartographiques.
* `scripts/` : scripts d'automatisation pour le lancement (`scripts/lancement/`) et le déploiement client/serveur (`scripts/deploiement/`).
* `data/` : répertoire des données d'entrée (`sources/`) et des bilans générés (`out/`).
* `ref/` : référentiels cartographiques, chartes graphiques et logos institutionnels.
* `ofbilan_plugin.py` : point d'entrée du relais pour l'intégration QGIS.
* `tests/` : suite de tests automatisés (tests unitaires et d'intégration).

---

## Licence et droits d'auteur

Ce projet est développé par **Aguirre Maurin** (service départemental de la Côte-d'Or, OFB).

Le code source est distribué sous licence **GNU General Public License v3.0 (GPLv3)**.

**Clause stricte d'attribution (article 7(b) de la GPLv3) :**
Conformément à la section 7(b) de la licence GNU GPLv3, il est **strictement interdit** de supprimer, altérer ou masquer les mentions de droits d'auteur, les notices de licence ou les informations d'identification de l'auteur d'origine présentes dans les fichiers sources, les interfaces utilisateurs (logos, mentions légales, console) et les documents générés. Toute modification ou redistribution du code doit clairement conserver l'attribution à l'auteur initial.

**Contact :** [aguirre.maurin@ofb.gouv.fr](mailto:aguirre.maurin@ofb.gouv.fr)
