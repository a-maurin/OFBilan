# 🗺️ Carte d'Architecture du Projet Bilans

Ce fichier sert de point d'entrée pour l'agent. Il associe les grandes fonctionnalités métier aux fichiers correspondants afin de limiter les recherches globales.

## 📄 Génération PDF et Mise en page
- **Constructeur principal PDF** : `src/bilans/common/pdf_report_builder.py`
- **Génération par profil / synthèse** : `src/bilans/engine/generation_pdf_profil.py`, `src/bilans/engine/generation_pdf_synthese.py`
- **Charte graphique et styles** : `src/bilans/common/ofb_charte.py`
- **Configurations de présentation** : `src/bilans/common/pdf_presentation_config.py`
- **Rendus de graphiques (Matplotlib, etc.)** : `src/bilans/common/rendus_graphiques.py`
- **Sections spécifiques et logiques de rendu** : `src/bilans/engine/sections_profil.py`, `src/bilans/common/pdf_shared_sections.py`

## 📊 Données, Calculs et Agrégrations
- **Chargement des données (ETL)** : `src/bilans/common/chargeurs_donnees.py`
- **Agrégrations par profil / région** : `src/bilans/engine/agregations_profil.py`, `src/bilans/engine/agregations_region.py`
- **Utilitaires métier et traitements** : `src/bilans/common/utilitaires_metier.py`, `src/bilans/common/dataframe_rollup.py`
- **Configurations des profils (YAML)** : Dossier `config/profils_bilan/`

## 🗺️ Cartographie (QGIS)
- **Production principale QGIS** : `src/bilans/cartographie/production_cartographique.py`
- **Configuration des couches et cartes** : `src/bilans/cartographie/config_cartes.py`, `src/bilans/cartographie/layer_resolver.py`
- **Interface GUI pour les cartes** : `src/bilans/cartographie/gui_config_cartes.py`

## ⚙️ Orchestration et Point d'Entrée
- **Point d'entrée (CLI)** : `src/bilans/point_entree_cli.py`
- **Orchestration des profils** : `src/bilans/engine/orchestrateur_profils.py`

*Note à l'Agent : Si l'utilisateur signale un bug sans fichier cible, identifiez la catégorie du bug et utilisez cette carte pour trouver le(s) fichier(s) pertinent(s).*
