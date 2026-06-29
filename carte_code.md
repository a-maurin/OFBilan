# Carte d'Architecture du Projet Bilans

Ce fichier sert de point d'entrée pour l'agent. Il associe les grandes fonctionnalités métier aux fichiers correspondants afin de limiter les recherches globales.

## Intégration QGIS (Plugin)
- **Point d'entrée du plugin** : `ofbilan_plugin.py`

## Interface Web & Serveur Local
- **Serveur local Python** : `core/web/serveur.py`
- **Interface Édition PDF (Frontend)** : `core/web/index.html`, `core/web/app.js`
- **Interface Exploration Données (Frontend)** : `core/web/explorer.html`, `core/web/explorer.js`
- **Styles globaux** : `core/web/style.css`

## Génération PDF et Mise en page
- **Constructeur principal PDF** : `core/common/pdf_report_builder.py`
- **Génération par profil / synthèse** : `core/engine/generation_pdf_profil.py`, `core/engine/generation_pdf_synthese.py`
- **Charte graphique et styles** : `core/common/ofb_charte.py`
- **Configurations de présentation** : `core/common/pdf_presentation_config.py`
- **Rendus de graphiques (Matplotlib, etc.)** : `core/common/rendus_graphiques.py`
- **Sections spécifiques et logiques de rendu** : `core/engine/sections_profil.py`, `core/common/pdf_shared_sections.py`

## Données, Calculs et Agrégrations
- **Chargement des données (ETL)** : `core/common/chargeurs_donnees.py`
- **Agrégrations par profil / région** : `core/engine/agregations_profil.py`, `core/engine/agregations_region.py`
- **Utilitaires métier et traitements** : `core/common/utilitaires_metier.py`, `core/common/dataframe_rollup.py`
- **Configurations des profils (YAML)** : Dossier `config/profils_bilan/`

## Cartographie (QGIS)
- **Production principale QGIS** : `core/cartographie/production_cartographique.py`
- **Configuration des couches et cartes** : `core/cartographie/config_cartes.py`, `core/cartographie/layer_resolver.py`
- **Interface GUI pour les cartes** : `core/cartographie/gui_config_cartes.py`

## Orchestration et Point d'Entrée
- **Point d'entrée (CLI)** : `core/point_entree_cli.py`
- **Orchestration des profils** : `core/engine/orchestrateur_profils.py`

*Note : Si l'utilisateur signale un bug sans fichier cible, identifier la catégorie du bug et utilisez cette carte pour trouver le(s) fichier(s) pertinent(s).*
