# 🗺️ Carte d'Architecture du Projet Bilans

Ce fichier sert de point d'entrée pour l'agent. Il associe les grandes fonctionnalités métier aux fichiers correspondants afin de limiter les recherches globales.

## 📄 Génération PDF et Mise en page
- **Constructeur principal PDF** : `src/ofbilan/common/pdf_report_builder.py`
- **Génération par profil / synthèse** : `src/ofbilan/engine/generation_pdf_profil.py`, `src/ofbilan/engine/generation_pdf_synthese.py`
- **Charte graphique et styles** : `src/ofbilan/common/ofb_charte.py`
- **Configurations de présentation** : `src/ofbilan/common/pdf_presentation_config.py`
- **Rendus de graphiques (Matplotlib, etc.)** : `src/ofbilan/common/rendus_graphiques.py`
- **Sections spécifiques et logiques de rendu** : `src/ofbilan/engine/sections_profil.py`, `src/ofbilan/common/pdf_shared_sections.py`

## 📊 Données, Calculs et Agrégrations
- **Chargement des données (ETL)** : `src/ofbilan/common/chargeurs_donnees.py`
- **Agrégrations par profil / région** : `src/ofbilan/engine/agregations_profil.py`, `src/ofbilan/engine/agregations_region.py`
- **Utilitaires métier et traitements** : `src/ofbilan/common/utilitaires_metier.py`, `src/ofbilan/common/dataframe_rollup.py`
- **Configurations des profils (YAML)** : Dossier `config/profils_bilan/`

## 🗺️ Cartographie (QGIS)
- **Production principale QGIS** : `src/ofbilan/cartographie/production_cartographique.py`
- **Configuration des couches et cartes** : `src/ofbilan/cartographie/config_cartes.py`, `src/ofbilan/cartographie/layer_resolver.py`
- **Interface GUI pour les cartes** : `src/ofbilan/cartographie/gui_config_cartes.py`

## ⚙️ Orchestration et Point d'Entrée
- **Point d'entrée (CLI)** : `src/ofbilan/point_entree_cli.py`
- **Orchestration des profils** : `src/ofbilan/engine/orchestrateur_profils.py`

*Note à l'Agent : Si l'utilisateur signale un bug sans fichier cible, identifiez la catégorie du bug et utilisez cette carte pour trouver le(s) fichier(s) pertinent(s).*
