![OFBilan Banner](ref/programme/logos/bandeau_ofbilan.svg)

# OFBilan (Plugin QGIS)

**OFBilan** est un outil d'aide à la décision et de communication s'appuyant sur les données de contrôles (OSCEAN) et les procédures (PVe / PEJ / PA) de l'Office Français de la Biodiversité (OFB).

Initialement conçu comme un script autonome, **OFBilan est désormais intégré sous la forme d'une extension QGIS**.

---

## Avantages de l'intégration QGIS & Portabilité

L'intégration sous forme de plugin QGIS permet :
*   **Une portabilité totale** : Plus besoin d'installer et de configurer manuellement un environnement Python complexe, PyQt ou les liaisons PyQGIS sur chaque poste. L'outil utilise directement l'interpréteur Python et les bibliothèques embarqués de QGIS.
*   **Une simplicité de déploiement** : Tout agent disposant de QGIS installé sur son poste peut instantanément installer et exécuter le programme.
*   **L'automatisation cartographique native** : L'extension s'appuie directement sur le moteur de QGIS pour générer et mettre en page des cartes statistiques et territoriales de manière transparente.

---

## Installation et Configuration

La mise en place de l'outil s'effectue en deux étapes.

### Étape 1 : Installation

Deux méthodes de déploiement sont possibles :

*   **Méthode A : Installation par fichier ZIP (Recommandée)**
    1.  Téléchargez la version packagée au foramt .zip.
    2.  Ouvrez QGIS.
    3.  Allez dans le menu **Extensions > Installer/Gérer les extensions**.
    4.  Sélectionnez l'onglet **Installer depuis un ZIP**.
    5.  Choisissez votre fichier ZIP et cliquez sur **Installer l'extension**.

*   **Méthode B : Copie manuelle du répertoire**
    1.  Copiez l'intégralité du dossier `OFBilan-Plugin-QGIS` dans le dossier des extensions QGIS de votre profil utilisateur.
    2.  Sur **Windows**, le chemin standard est :
        `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\OFBilan-Plugin-QGIS`
    3.  Redémarrez QGIS.

### Étape 2 : Récupération des référentiels et données (Pack de configuration)

Pour des raisons de confidentialité, les données géographiques de référence (`ref/programme/`), les chartes graphiques de l'OFB et les dossiers de données sources (`data/sources/`) ne sont pas inclus dans ce dépôt de code.

1.  Contactez l'auteur du projet pour obtenir l'archive `pack_configuration_referentiels.zip`.
2.  Copiez ce fichier ZIP et le script `installer_pack.bat` à la racine de votre dossier de plugin (le répertoire d'installation décrit dans la Méthode B).
3.  Double-cliquez sur `installer_pack.bat` : le script extraira automatiquement les dossiers `ref`, `config` et `data` au bon endroit.

---

## Guide d'utilisation

### 1. Démarrage de l'interface graphique (OFBilan Explorer)

L'utilisation principale s'effectue directement depuis l'interface utilisateur de QGIS :

1.  Ouvrez **QGIS**.
2.  Activez l'extension **OFBilan** dans le gestionnaire d'extensions si son icône n'apparaît pas.
3.  Cliquez sur le bouton **OFBilan** dans votre barre d'outils, ou allez dans le menu **Extensions > OFBilan > Lancer OFBilan Explorer**.
4.  L'extension effectue alors les actions suivantes de manière transparente :
    *   Elle démarre un serveur web local léger en tâche de fond (sans ouvrir de console noire).
    *   Elle ouvre automatiquement votre navigateur internet par défaut sur l'interface interactive : `http://localhost:8000/explorer.html`.
5.  Lorsque vous fermez QGIS, le serveur web d'OFBilan s'arrête automatiquement.

### 2. Démarrage en mode autonome (Sans ouvrir QGIS)

Si vous ne souhaitez pas ouvrir QGIS, vous pouvez exécuter le serveur de manière autonome en utilisant le script dédié :

1.  Double-cliquez sur le fichier `demarrer_serveur_OFBilane.bat` situé à la racine du projet.
2.  Le script va automatiquement rechercher l'interpréteur Python de votre installation QGIS locale (ex: dans `C:\Program Files\QGIS 3.44.8`).
3.  Une fois trouvé, il lance le serveur web d'OFBilan et vous pouvez alors accéder à l'interface via votre navigateur à l'adresse : `http://localhost:8000/explorer.html`.
4.  Pour arrêter le serveur, il vous suffit de fermer la fenêtre de commande ouverte par le script `.bat`.

### 3. Fonctionnalités de l'interface web

L'application web s'articule autour de deux onglets :

*   **Analyse dynamique** :
    *   *Cartographie interactive (Leaflet.js)* : Visualisation géographique instantanée des points de contrôle OSCEAN.
    *   *Tableaux de bord (Chart.js)* : Visualisation des statistiques clés (Top 5 thématiques, résultats des contrôles, etc.).
    *   *Filtrage à la volée* : Filtrez instantanément par période, département, BMI, ou type d'usager avec une mise à jour immédiate des cartes et des graphiques.

*   **Edition de bilans PDF** :
    *   *Catalogue complet (profils activable par yaml)* : Bilans globaux, thématiques (eau, chasse, espèces, pollutions...) ou ciblés par type d'usager.
    *   *Mise en page professionnelle* : Rapports détaillés ou brochures A4 synthétiques (4 pages).
    *   *Double périmètre de diffusion* : Générez des versions *Internes* (détaillées) ou *Externes* (anonymisées/masquées pour les partenaires).
    *   *Intégration cartographique automatique* : Le serveur communique avec QGIS pour générer des cartes personnalisées à l'échelle du département, de la région ou de la BMI sélectionnée et les insérer dans le rapport PDF final.

---

## Utilisation en ligne de commande

Pour les automatisations ou les tâches de traitement par lots, vous pouvez exécuter le programme en ligne de commande (CLI) en exploitant l'interprète Python de QGIS.

### Commande de base
```bash
# Windows (adapter le chemin selon votre version de QGIS)
"C:\Program Files\QGIS 3.40.11\bin\python.exe" -m ofbilan --profil global --date-deb 2026-01-01 --date-fin 2026-12-31 --code 21
```

### Exemples d'options courantes
*   **Lister les thématiques et usagers disponibles** :
    ```bash
    python -m ofbilan --list-themes
    python -m ofbilan --list-type-usagers
    ```
*   **Générer un bilan PNF anonymisé pour l'externe** :
    ```bash
    python -m ofbilan --profil pnf --date-deb 2026-01-01 --date-fin 2026-12-31 --code 21 --diffusion externe
    ```
*   **Générer un bilan sans cartes** (mécanisme de repli rapide) :
    ```bash
    python -m ofbilan --profil global --code 21 --no-cartes
    ```

---

## Structure du projet

*   `ofbilan_plugin.py` : Point d'entrée et intégration dans l'interface de QGIS.
*   `metadata.txt` : Métadonnées d'identification du plugin pour QGIS.
*   `core/` : Cœur de l'application (calculs statistiques, génération PDF ReportLab, serveur FastAPI).
*   `config/` : Profils YAML de configuration des bilans et référentiel géographique.
*   `data/` : Dossiers d'entrées (`sources/`) et de sorties des PDF générés (`out/`).
*   `ref/` : Référentiels cartographiques, logos, polices et tables de correspondance.
*   `tests/` : Suite de tests automatisés.

---

## Contact & Support

*   **Auteur** : Aguirre Maurin
*   **Service** : Office Français de la Biodiversité (OFB), Service Départemental de la Côte-d'Or
*   **Courriel** : [aguirre.maurin@ofb.gouv.fr](mailto:aguirre.maurin@ofb.gouv.fr)
