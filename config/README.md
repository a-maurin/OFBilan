# Configurations du projet

Ce dossier contient les **configurations de pilotage versionnees**.

## Convention cible

- `config/profils_bilan/` : profils YAML des bilans thematiques ;
- `config/presentation/` : regles de presentation PDF (ordre/sections/blocs) ;
- `config/charts/` : reglages de charts.

## Situation actuelle (transition)

Une partie du pilotage est encore lue dans `ref/` pour compatibilite historique :

- `ref/pdf_presentation.yaml`
- `ref/charts_config.yaml`
- `ref/glossaire.yaml`

Ces fichiers restent supportes. La migration vers `config/` se fera progressivement.

## Hors du scope `config/`

- `ref/` : referentiels (SIG, tables de correspondance, assets OFB) ;
- `sources/` / `data/` : donnees d'entree locales non versionnees ;
- `out/` : sorties de run non versionnees.