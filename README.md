![OFBilan Banner](ref/programme/logos/bandeau_ofbilan.svg)

# OFBilan

Outil d'aide à la décision et de communication qui s'articule autour de deux piliers à partir des données de contrôles (OSCEAN) et des procédures (PVe / PEJ / PA) de l'Office Français de la Biodiversité (OFB) :
1. **L'exploration dynamique des données** via une interface web interactive.
2. **La génération automatisée de bilans cartographiés** au format PDF.

---

## Usages et fonctionnalités métier

### 1. Exploration dynamique des données (OFBilan Explorer)
L'interface graphique intègre un explorateur web interactif permettant d'analyser la base de données à la volée :
* **Cartographie interactive (Leaflet.js)** : Visualisation géographique précise des points de contrôle OSCEAN.
* **Tableaux de bord (Chart.js)** : Graphiques dynamiques affichant la répartition par résultat de contrôle et les domaines d'activité les plus contrôlés.
* **Filtrage multicritères** : Exploration instantanée par période, échelle spatiale (département, région, BMI), profil thématique et type d'usager.
* **Indicateurs de synthèse** : Comptage immédiat des contrôles réels, procédures pénales et administratives adaptées.

### 2. Génération de bilans PDF cartographiés
Le programme produit automatiquement des rapports complets et formatés (graphiques, indicateurs, procédures) :
* **Catalogue de +35 profils prêts à l'emploi** : Bilans globaux, Synthèses d'activité PA/PJ, Bilans Thématiques (Chasse, Eau, Espèces, Pollutions...), et Bilans ciblés par Usagers.
* **Des formats de restitution adaptés** : 
  * *Rapports détaillés* conformes à la charte graphique OFB.
  * *Mode Brochure A4 (Recto-Verso)* pour la communication physique (dépliant de 4 pages).
* **Double Périmètre de Diffusion** : Génération de versions *Internes* (données complètes et sensibles) et *Externes* (masquage des informations confidentielles pour les partenaires).

### 3. Production cartographique QGIS intégrée
* **Multi-Échelles** : Analyse et rendu de cartes pour n'importe quel département, région administrative, ou BMI.
* **Cartographie Automatisée** : Adaptation dynamique de l'emprise, application d'un pochoir de mise en valeur territoriale, et ajout ciblé de couches métier selon le profil choisi.
* **Mécanisme de repli** : Si QGIS n'est pas disponible, les bilans textuels/graphiques PDF restent entièrement générés sans bloquer le processus.

---

## Mode d'utilisation

### 1. Interface graphique (GUI locale web) — *Recommandé*
Une interface utilisateur est disponible pour configurer et générer vos bilans sans saisir de lignes de commande.

* **Démarrage de l'interface** :
  Double-cliquez sur `lancer_gui.bat` (Windows) ou lancez dans votre console :
  ```bash
  scripts/windows/lancer_gui.bat
  ```
  *(Le script ouvre automatiquement votre navigateur internet à l'adresse [http://localhost:8000](http://localhost:8000)).*

* **Fonctionnalités de génération** :
  * Sélection interactive des profils de bilans avec filtrage et recherche intelligente par autocomplétion.
  * Saisie simplifiée de la période, de l'échelle géographique (département, région, BMI) et du type d'usager via des comboboxes dynamiques.
  * Choix précis des cartes QGIS à intégrer au PDF (Par défaut : Domaines, Résultats, Usagers, Procédures).
  * Possibilité d'intégrer des cartes personnalisées depuis votre disque en indiquant leur chemin absolu.
  * Suivi du traitement en temps réel dans une console intégrée et téléchargement immédiat du PDF généré.

* **Explorateur de données interactif** :
  * Accessible directement depuis l'interface via l'onglet de navigation dédié.
  * **Cartographie interactive (Leaflet.js)** : Visualisation géographique des points de contrôle OSCEAN sur le territoire sélectionné.
  * **Tableaux de bord (Chart.js)** : Graphiques dynamiques affichant la répartition par résultat de contrôle et le Top 5 des domaines d'activité les plus contrôlés.
  * **Indicateurs de synthèse** : Synthèse chiffrée immédiate (localisations, contrôles réels, procédures pénales, procédures administratives adaptées).
  * **Filtrage à la volée** : Exploration rapide de la base de données OSCEAN par période, échelle spatiale et type d'usager avec rafraîchissement instantané sans génération de PDF.

### 2. Lancement en ligne de commande (CLI & mode interactif)
L'assistant interactif  en mode console vous guide pas-à-pas :

* **Avec génération automatique des cartes (QGIS requis)** :
  Double-cliquez sur `lancer_bilans_qgis.bat` (Windows) ou lancez dans votre console :
  ```bash
  scripts/windows/lancer_bilans_qgis.bat
  ```
* **Sans génération automatique des cartes (ou si QGIS n'est pas installé)** :
  Double-cliquez sur `lancer_bilans.bat` (Windows) ou lancez dans votre console :
  ```bash
  python -m ofbilan
  ```

---

## Instructions techniques & configuration

### 0. Récupération des référentiels et données (Pack de configuration)
Pour des raisons de confidentialité, les référentiels géographiques (`ref/programme/`), les modèles de chartes graphiques et les dossiers de données d'entrée (`data/sources/`) ne sont pas inclus dans ce dépôt Git.

Si vous souhaitez utiliser l'outil, vous pouvez contacter l'auteur du projet pour obtenir le pack de configuration et données. Un script d'installation automatique (`installer_pack.bat`) est fourni avec ce pack pour configurer votre environnement local facilement.

### 1. Installation de QGIS & environnement cartographique
La génération automatique des cartes du rapport nécessite l'accès à **PyQGIS** (les bibliothèques Python de QGIS).
1. Installez **QGIS** (version LTR recommandée, ex: 3.40+) sur votre poste de travail.
2. Installez le package `ofbilan` dans l'interprète Python de QGIS (requis une seule fois) :
   ```bash
   "C:\Program Files\QGIS 3.40.11\bin\python.exe" -m pip install -e .
   ```
   *(Ajustez le chemin de l'exécutable Python selon votre version de QGIS. Dans QGIS, allez dans Extensions > Console Python et lancez `import sys; print(sys.executable)` pour le connaître).*
3. Si QGIS est installé dans un répertoire personnalisé et n'est pas détecté automatiquement, créez un fichier texte nommé `qgis_python_path.txt` dans le dossier `scripts/windows/` contenant uniquement le chemin absolu vers `python.exe` de QGIS.

### 2. Paramétrage pour un autre département (hors Côte-d'Or 21)
Bien que configuré par défaut pour la Côte-d'Or (21), l'outil peut générer des bilans pour **n'importe quel département français** en suivant ces étapes :
* **Données Sources** : Déposez les exports de données (OSCEAN, PVe, PEJ) correspondant au département ciblé dans le répertoire `data/sources/`.
* **Génération du Pochoir** : Le pochoir de découpe spécifique à votre département est **généré automatiquement** par l'outil à partir des limites administratives officielles de l'IGN (`ref/programme/sig/limites_admin_dep/DEPARTEMENT_ADMIN_Express_200207.shp`). Le projet QGIS de référence (`ref/programme/sig/bilans_carte.qgz`) n'a pas besoin de le contenir d'avance, il doit seulement intégrer le pochoir modèle (`pochoir_sd21`) qui sert de gabarit graphique pour cloner la symbologie du masque inversé (le blanc opaque masquant les zones hors département).
* **Exécution** : Indiquez le code du département via l'option `--code` (ou `--dept-code`). Par exemple pour le Doubs (25) :
  ```bash
  scripts/windows/lancer_bilans_qgis.bat --profil global --code 25 --date-deb 2025-01-01 --date-fin 2025-12-31
  ```
* **Compilation sans QGIS (Marqueurs)** : Si les cartes sont générées sur un poste équipé de QGIS puis copiées sur un poste sans QGIS pour la génération finale du PDF, elles doivent être accompagnées d'un fichier marqueur sidecar nommé `carte_<nom_carte>.<code_dept>.dept` (ex: `carte_global.25.dept`) dans `data/out/generateur_de_cartes/`.

### 3. Exemples de commandes CLI
Une fois installé, la commande de base `ofbilan` (ou `python -m ofbilan`) propose ces options :

```bash
# Générer le bilan global d'un département
ofbilan --profil global --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21

# Générer une synthèse PA/PJ pour une BMI avec cartographie dynamique
ofbilan --profil synthese_activite_PA_PJ --date-deb 2025-01-01 --date-fin 2025-12-31 --echelle bmi --code BMI-NEC

# Générer le bilan PNF en mode externe (anonymisé pour partenaires)
ofbilan --profil pnf --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21 --diffusion externe

# Cibler les contrôles d'un type d'usager spécifique (sans cartes)
ofbilan --profil types_usager_cible --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21 --type-usager 2 --no-cartes

# Lister les thématiques et les types d'usagers disponibles
ofbilan --list-themes
ofbilan --list-type-usagers
```

### 4. Automatisation et tests
* **Scripts de raccourci** : Des batchs d'automatisation sont disponibles dans `scripts/windows/` (`lancer_bilans`, `lancer_bilans_qgis`, `generer_cartes`, `parametrer_cartes`).
* **Tests unitaires** :
  ```bash
  python -m pytest -q
  ```

---

## Structure des fichiers clés

* `src/ofbilan/` : Code source applicatif (Calculs, PDF ReportLab, interface CLI, intégration QGIS).
* `config/` : Profils YAML de configuration des bilans (`config/profils_bilan/`), référentiel des régions et BMI.
* `data/` : Dossier d'entrée des données brutes (`sources/`) et de sortie des PDF générés (`out/`).
* `ref/` : Référentiels géographiques et tables de correspondances.
* `tests/` : Suite de tests automatisés.

---

## Contact

* **Auteur** : Aguirre Maurin
* **Service** : OFB, Service Départemental de la Côte-d'Or
* **Courriel** : [aguirre.maurin@ofb.gouv.fr](mailto:aguirre.maurin@ofb.gouv.fr)
