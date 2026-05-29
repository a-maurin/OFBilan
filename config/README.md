# Configuration applicative

Ce dossier contient la configuration versionnée du programme.

## Structure

- `config/profils_bilan/` : profils bilans (`*.yaml`), dont `global.yaml` pour le bilan global et les profils thématiques ;
- `config/profils_bilan/_defaults.yaml` : socle commun fusionné avec chaque profil (pipeline, adapters agrégation/PDF, capacités par défaut) ;
- `config/presentation/` : règles de présentation PDF (sections, blocs, tables, diffusion) ;
- `config/charts/` : paramètres d’affichage des graphiques.

## Principe

Toute nouvelle clé de pilotage doit être ajoutée dans `config/` (profil dédié ou `_defaults.yaml` si partagé par plusieurs profils).

## Hors périmètre

- `ref/programme/` : référentiels lus par l’application ;
- `ref/hors_programme/` : archives (hors pipeline runtime) ;
- `data/sources/` : données d’entrée locales ;
- `data/out/` : sorties générées.