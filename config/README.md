# Configuration applicative

Ce dossier contient la configuration versionnée du programme.

## Structure

- `config/profils_bilan/` : profils bilans (`*.yaml`), dont `global.yaml` pour le bilan global et les profils thématiques ;
- `config/presentation/` : règles de présentation PDF ;
- `config/charts/` : paramètres d’affichage des graphiques.

## Principe

Toute nouvelle clé de pilotage doit être ajoutée dans `config/`.

## Hors périmètre

- `ref/programme/` : référentiels lus par l’application ;
- `ref/hors_programme/` : archives (hors pipeline runtime) ;
- `data/sources/` : données d’entrée locales ;
- `data/out/` : sorties générées.