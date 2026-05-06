# Organisation du projet (Phases 1-3)

Ce document fixe les conventions de structure appliquees en phases 1-3
(hygiene + clarifications + stabilisation CLI/packaging)
sans refonte du moteur metier.

## Sources de verite

- `scripts/` : wrappers d'execution (Windows/Linux).
- `src/bilans/` : code applicatif principal (moteur profilé, cartographie, common).
- `config/` : configuration de pilotage versionnee (profils, options metier, presentation).
- `ref/` : referentiels versionnes (glossaires, assets OFB, tables de correspondance, donnees de reference).
- `data/sources/` : donnees locales d'entree non versionnees.
- `data/out/` : sorties generees (PDF/CSV/cartes) non versionnees.

## Lanceurs officiels

Wrappers maintenus :

- Windows : `scripts/windows/lancer_bilans.bat`, `scripts/windows/generer_cartes.bat`, `scripts/windows/parametrer_cartes.bat`
- Linux : `scripts/linux/lancer_bilans.sh`, `scripts/linux/generer_cartes.sh`, `scripts/linux/parametrer_cartes.sh`

## CLI et packaging (phase 2)

- Entree CLI officielle : `python -m bilans`
- Entree script console (apres installation) : `bilans`
- Fichier de packaging : `pyproject.toml`
- Pas de point d'entree legacy conserve : la CLI officielle est `python -m bilans`.

## Rationalisation config/ref (phase 3)

- Cible : `config/` porte le pilotage, `ref/` porte les referentiels.
- Etat actuel : les fichiers de pilotage sont places dans `config/`
  (`config/presentation/pdf_presentation.yaml`, `config/charts/charts_config.yaml`,
  `config/presentation/glossaire.yaml`).
- Compatibilite : fallback vers `ref/` uniquement si un environnement local
  conserve encore les anciens emplacements.
- Regle pratique : toute nouvelle cle de pilotage doit etre pensee pour `config/`
  et documenter explicitement le fallback si `ref/` est encore utilise.

## Regles hygiene repository

- Ne pas versionner les artefacts de run (`data/out/`, logs, caches Python, `__pycache__`, `.pytest_cache/`).
- Eviter tout chemin absolu machine dans les scripts (utiliser des chemins relatifs projet).
- Utiliser `pathlib` cote Python pour garder un comportement robuste sous Windows/Linux.

## Portee

Les phases 1-3 ne modifient pas le rendu metier des bilans PDF.
Elles clarifient l'usage, la navigation et la stabilite d'execution.
