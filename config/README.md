# Configurations du projet

Ce dossier contient les **configurations de pilotage versionnees**.

## Convention cible

- `config/profils_bilan/` : profils YAML des bilans thematiques ;
- `config/presentation/` : regles de presentation PDF (ordre/sections/blocs) ;
- `config/charts/` : reglages de charts.

## Situation actuelle (transition)

Le pilotage de presentation est desormais centralise ici :

- `config/presentation/pdf_presentation.yaml`
- `config/charts/charts_config.yaml`
- `config/presentation/glossaire.yaml`

Compatibilite conservee par le code : fallback vers `ref/` si ces fichiers y
existent encore localement.

## Hors du scope `config/`

- `ref/` : referentiels (SIG, tables de correspondance, assets OFB) ;
- `sources/` / `data/` : donnees d'entree locales non versionnees ;
- `out/` : sorties de run non versionnees.