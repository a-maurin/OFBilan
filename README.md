# OFBilan 📊

Application de génération de bilans PDF d'activité à partir de données OSCEAN et PVe de l'Office Français de la Biodiversité (OFB).

## Fonctionnalités Clés

- **Bilan Global** : Vision départementale consolidée de l'activité sur une période donnée.
- **Bilans Thématiques** : Bilans spécialisés et modulables (ex. chasse, agrainage, types d'usagers, synthèse d'activité PA, PJ, etc).
- **Rendu PDF & Graphiques** : Mise en page dynamique respectant la charte graphique de l'OFB.
- **Cartographie QGIS Automatisée & Pilotée par YAML** : 
  - Génération automatique des cartes thématiques intégrées au PDF. Par défaut : contrôles par domaines, résultats des contrôles, contrôles par type d'usager, procédures (PA, PEJ, PVe).
  - Configuration complète de la cartographie (requêtes spatiales, couches géographiques, emprise, styles de légendes) centralisée dans les profils YAML (`profils_cartes.yaml` et `config/profils_bilan/`).
  - Résolution dynamique des couches cartographiques via `layer_resolver.py` et interface graphique de paramétrage.
  - **Mécanisme de repli (Fallback)** : L'absence de QGIS ou d'images PNG générées ne bloque jamais la production finale du bilan PDF.
- **Pilotage par YAML** : Paramétrage complet des pipelines de données, des filtres d'agrégation et de la structure des sections PDF via des profils YAML réutilisables, évitant tout code en dur.

## Prérequis et Installation

- Python 3.10+
- QGIS (facultatif, requis uniquement pour générer les cartes cartographiques)

```bash
# Installation en mode éditable
pip install -e .

# Installation avec dépendances de développement et tests
pip install -e .[dev]
```

Une fois installé, la commande `bilans` est disponible (raccourci pour `python -m ofbilan`).

## Exécution

L'exécution est pilotée par les profils de configuration. Si aucun profil n'est passé en paramètre, un menu interactif s'affiche.

```bash
# Lister les profils thématiques disponibles
ofbilan --list-themes

# Générer le bilan global
ofbilan --profil global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

# Générer des bilans thématiques spécifiques
ofbilan --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

# Bilan d'un type d'usager spécifique sans génération de cartes
ofbilan --profil types_usager_cible --date-deb 2025-01-01 --date-fin 2026-03-31 --dept-code 21 --type-usager 2 --no-cartes
```

### Scripts de Lancement rapides
Des scripts prêts à l'emploi sont disponibles dans le dossier `scripts/` pour Windows (`.bat`) et Linux (`.sh`) :
- `lancer_bilans` / `lancer_bilans_qgis` : Exécute la génération de bilans et cartes.
- `generer_cartes` / `parametrer_cartes` : Gestion de la cartographie.

## 🧪 Tests et Qualité

Pour lancer la suite de tests unitaires et de non-régression (smoke tests) :
```bash
python -m pytest -q
```
*Note : Sous Windows, vous pouvez également exécuter `.\scripts\verify.ps1` et sous Linux `./scripts/verify.sh`.*

## Structure du Projet

- `src/ofbilan/` : Code source de l'application (calculs, PDF, CLI, cartographie).
- `config/` : Profils YAML de configuration et charte graphique.
- `data/` : Dossiers des sources d'entrée (`sources/`) et des fichiers générés (`out/`).
- `docs/` : Documentations d'architecture, schémas de données et guides de migration.
- `ref/` : Référentiels géographiques et administratifs.
- `tests/` : Tests unitaires et smoke tests hermétiques.

## ✉️ Contact

- **Auteur** : Aguirre Maurin
- **Service** : OFB, Service Départemental de la Côte-d'Or
- **Courriel** : [aguirre.maurin@ofb.gouv.fr](mailto:aguirre.maurin@ofb.gouv.fr)
