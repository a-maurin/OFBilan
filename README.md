![OFBilan Banner](ref/programme/logos/bandeau_ofbilan.svg)

# OFBilan

Outil d'aide à la décision et de communication permettant de générer automatiquement des bilans d'activité cartographiés au format PDF à partir des données de contrôles (OSCEAN) et des procédures (PVe / PEJ) de l'Office Français de la Biodiversité (OFB).

---

## 🎯 Usages et Fonctionnalités Métier

### 1. Des Formats de Restitution Adaptés
* **Rapports PDF détaillés** : Documents complets avec indicateurs, graphiques de répartition et listes de procédures conformes à la charte graphique de l'OFB.
* **Mode Brochure A4 (Recto-Verso)** : Généré automatiquement pour le profil de synthèse PA/PJ. Il produit un document de 4 pages au format paysage, idéal pour l'impression et la distribution physique.
* **Double Périmètre de Diffusion** :
  * **Interne** : Contient le détail nominatif et précis des procédures (numéros de dossier, localisation précise des infractions).
  * **Externe** : Masque les données nominatives et localisations précises pour une transmission sécurisée aux partenaires institutionnels ou au grand public.

### 2. Catalogue de Profils de Bilans Prêts à l'Emploi
Plus de 35 profils configurables permettent de cibler précisément un sujet ou un territoire :
* **Bilan Global** : Une vision consolidée de toute l'activité du service.
* **Synthèse d'Activité PA / PJ** : Synthèse équilibrée entre Police Administrative et Police Judiciaire, avec édition automatique de la plaquette de communication (brochure).
* **Parc National de Forêts (PNF)** : Analyse territorialisée automatique sur les communes du parc (cœur et aire d'adhésion) avec cartographie dédiée intégrant le zonage réglementaire.
* **Zones TUB (Territoires sous Unique Bail)** : Suivi ciblé de l'agrainage et des contrôles/procédures associés dans ces périmètres à enjeu cynégétique.
* **Bilans Thématiques** : Chasse, Agrainage, Pêche, Sécheresse, Espèces Protégées, Continuité Écologique, Travaux, Zones Humides, Pollutions, etc.
* **Bilans par Usagers** : Possibilité de cibler un public spécifique (ex. Agriculteurs, Particuliers, Collectivités) pour analyser la répartition des contrôles et leur conformité.

### 3. Adaptation Spatiale et Cartographie Dynamique
* **Multi-Échelles** : Génération de bilans pour **n'importe quel département**, région administrative, ou à l'échelle nationale.
* **Intégration des Brigades Mobiles d'Intervention (BMI)** : Prise en charge native des secteurs géographiques des BMI (ex. `BMI-NEC`, `BMI-SO`, `BMI-SE`, `BMI-NO`).
* **Cartographie QGIS Automatisée** : 
  * Adaptation dynamique de l'emprise de la carte (zoom automatique sur le département, la région ou la BMI sélectionnée).
  * Application d'un pochoir de masquage pour mettre en valeur le territoire ciblé.
  * Ajout automatique de couches vectorielles selon le profil (ex. zonage cœur/adhésion pour le PNF, périmètre TUB pour l'agrainage).
  * *Mécanisme de repli (Fallback)* : Si QGIS n'est pas disponible sur le poste, le bilan PDF est tout de même généré (seules les cartes sont omises), garantissant la continuité du service.

---

## ⚙️ Mode d'Utilisation

### Guide de démarrage rapide (Mode Interactif)
Si vous lancez l'outil sans paramètres, un **assistant interactif en console** vous guide pas-à-pas :
1. Choix du ou des profils à générer.
2. Saisie de la période (dates de début et de fin).
3. Choix du périmètre géographique (Département, BMI, Région, etc.) et de son code (ex. `21`, `BMI-NEC`).
4. Activation/Désactivation des cartes et de la brochure.

Pour lancer l'assistant interactif, double-cliquez sur `lancer_bilans.bat` (Windows) ou lancez en console :
```bash
ofbilan
```

---

## 🛠️ Instructions Techniques & Commandes Avancées

### Prérequis et Installation
* Python 3.10+
* QGIS (facultatif, requis uniquement pour générer les cartes géographiques)

```bash
# Installation en mode éditable
pip install -e .

# Installation complète pour développement et tests
pip install -e .[dev]
```

### Exemples de Commandes CLI
Une fois installé, la commande `ofbilan` (ou `python -m ofbilan`) est disponible :

```bash
# 1. Générer le bilan global d'un département
ofbilan --profil global --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21

# 2. Générer une synthèse PA/PJ pour une BMI avec cartographie dynamique
ofbilan --profil synthese_activite_PA_PJ --date-deb 2025-01-01 --date-fin 2025-12-31 --echelle bmi --code BMI-NEC

# 3. Générer le bilan PNF en mode externe (anonymisé)
ofbilan --profil pnf --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21 --diffusion externe

# 4. Cibler les contrôles d'un type d'usager spécifique (sans cartes)
ofbilan --profil types_usager_cible --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21 --type-usager 2 --no-cartes

# 5. Lancer plusieurs bilans thématiques en une seule fois
ofbilan --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --code 21

# 6. Lister les thématiques et les types d'usagers disponibles
ofbilan --list-themes
ofbilan --list-type-usagers
```

### Automatisation et scripts rapides (Windows / Linux)
Des raccourcis sont disponibles dans le dossier `scripts/` :
* `lancer_bilans` / `lancer_bilans_qgis` : Lancement assisté avec ou sans cartographie.
* `generer_cartes` / `parametrer_cartes` : Outils dédiés à la mise au point des couches géographiques.

### Validation et Tests
Pour exécuter les tests unitaires et s'assurer du bon fonctionnement de l'application :
```bash
python -m pytest -q
```
*(Alternative sous Windows : exécuter `.\scripts\verify.ps1`)*

---

## 📂 Structure des Fichiers Clés

* `src/ofbilan/` : Code source applicatif (Calculs, PDF ReportLab, interface CLI, intégration QGIS).
* `config/` : Profils YAML de configuration des bilans (`config/profils_bilan/`), référentiel des régions et BMI.
* `data/` : Dossier d'entrée des données brutes (`sources/`) et de sortie des PDF générés (`out/`).
* `ref/` : Référentiels géographiques et tables de correspondances.
* `tests/` : Suite de tests automatisés.

---

## ✉️ Contact

* **Auteur** : Aguirre Maurin
* **Service** : OFB, Service Départemental de la Côte-d'Or
* **Courriel** : [aguirre.maurin@ofb.gouv.fr](mailto:aguirre.maurin@ofb.gouv.fr)
