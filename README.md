![OFBilan Banner](ref/programme/logos/bandeau_ofbilan.svg)

# OFBilan

Outil d'aide à la décision et de communication permettant de générer automatiquement des bilans d'activité cartographiés au format PDF à partir des données de contrôles (OSCEAN) et des procédures (PVe / PEJ / PA) de l'Office Français de la Biodiversité (OFB).

---

## Usages et fonctionnalités métier

### 1. Des formats de restitution adaptés
* **Rapports PDF détaillés** : Documents complets avec indicateurs, graphiques de répartition et listes de procédures conformes à la charte graphique de l'OFB.
* **Mode Brochure A4 (Recto-Verso)** : Généré automatiquement pour le profil de synthèse PA/PJ. Il produit un document de 4 pages au format paysage, pour l'impression et la distribution physique.
* **Double Périmètre de Diffusion** :
  * **Interne** : Contient les données sensibles liées aux procédures (numéros de dossier, localisation précise des infractions).
  * **Externe** : Masque les données sensibles pour une transmission sécurisée aux partenaires institutionnels ou au grand public.

### 2. Catalogue de profils de bilans prêts à l'emploi
Plus de 35 profils configurables permettent de cibler précisément un sujet ou un territoire :
* **Bilan Global** : Une vision consolidée de toute l'activité du service.
* **Synthèse d'Activité PA / PJ** : Synthèse des activités de Police Administrative et Police Judiciaire, avec édition automatique de la plaquette de communication (brochure).
* **Bilans Thématiques** : Chasse, Agrainage, Pêche, Sécheresse, Espèces Protégées, Continuité Écologique, Travaux, Zones Humides, Pollutions, etc.
* **Bilans par Usagers** : Possibilité de cibler un public spécifique (ex. Agriculteurs, Particuliers, Collectivités) pour analyser la répartition des contrôles et leur conformité.

### 3. Adaptation spatiale et cartographie dynamique
* **Multi-Échelles** : Génération de bilans pour n'importe quel département, région administrative, ou à l'échelle nationale (en cours d'implémentation)
* **Intégration des Brigades Mobiles d'Intervention (BMI)** : Prise en charge native des secteurs géographiques des BMI (ex. `BMI-NEC`, `BMI-SO`, `BMI-SE`, `BMI-NO`).
* **Cartographie QGIS Automatisée** : 
  * Adaptation dynamique de l'emprise de la carte (zoom automatique sur le département, la région ou la BMI sélectionnée).
  * Application d'un pochoir de masquage pour mettre en valeur le territoire ciblé.
  * Ajout automatique de couches vectorielles selon le profil (ex. zonage cœur/adhésion pour le PNF, périmètre TUB pour l'agrainage).
  * *Mécanisme de repli* : Si QGIS n'est pas disponible sur le poste, le bilan PDF est tout de même généré (seules les cartes sont omises), garantissant la continuité du service.

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

* **Fonctionnalités de l'interface** :
  * Sélection interactive des profils de bilans avec filtrage et recherche intelligente.
  * Saisie simplifiée de la période, de l'échelle géographique (département, région, BMI) et du type d'usager.
  * Choix précis des cartes QGIS à intégrer au PDF (Par défaut : Domaines, Résultats, Usagers, Procédures).
  * Possibilité d'intégrer des cartes personnalisées depuis votre disque en indiquant leur chemin absolu.
  * Suivi du traitement en temps réel dans une console intégrée et téléchargement immédiat du PDF généré.

### 2. Lancement en ligne de commande (CLI & mode interactif)
L'assistant interactif classique en mode console vous guide pas-à-pas :

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
