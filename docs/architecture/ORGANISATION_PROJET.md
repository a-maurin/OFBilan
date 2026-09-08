# Organisation du projet (Phases 1-3)

Ce document fixe les conventions de structure appliquees en phases 1-3
(hygiene + clarifications + stabilisation CLI/packaging)
sans refonte du moteur metier.

## Sources de verite

- `bin/` : raccourcis d'exécution locaux pour le développement.
- `scripts/` : scripts organisés par usage (`lancement/`, `deploiement/`, `donnees/`, `maintenance/`).
- `tools/` : scripts de maintenance internes, audits ponctuels et utilitaires de diagnostic.
- `src/bilans/` : code applicatif principal (moteur profilé, cartographie, common).
- `config/` : configuration de pilotage versionnee (profils, options metier, presentation).
- `ref/programme/` : referentiels lus par l'application (tables, SIG, charte OFB) ;
- `ref/hors_programme/` : archives et donnees hors pipeline runtime.
- `data/sources/` : donnees locales d'entree non versionnees.
- `data/out/` : sorties generees (PDF/CSV/cartes) non versionnees.

## Lanceurs officiels

Wrappers maintenus :

- Windows : `scripts/lancement/demarrer_serveur_OFBilan.bat`, `scripts/lancement/lancer_bilans.bat`, `scripts/lancement/lancer_bilans_qgis.bat`, `scripts/lancement/generer_cartes.bat`, `scripts/lancement/parametrer_cartes.bat`
- Linux : `scripts/lancement/demarrer_serveur_OFBilan.sh`, `scripts/lancement/lancer_cli_OFBilan.sh`

## CLI et packaging (phase 2)

- Entree CLI officielle : `python -m ofbilan`
- Entree script console (apres installation) : `bilans`
- Fichier de packaging : `pyproject.toml`
- Pas de point d'entree legacy conserve : la CLI officielle est `python -m ofbilan`.
- Tests : `pip install -e .[dev]` puis `python -m pytest -q` (ou `scripts/maintenance/verify.ps1` / `scripts/maintenance/verify.sh`) ; CI `.github/workflows/tests.yml`.

## Rationalisation config/ref (phase 3)

- Cible : `config/` porte le pilotage, `ref/programme/` porte les referentiels actifs.
- Etat actuel : pilotage dans `config/` ; donnees de reference dans `ref/programme/`.
- Verification locale : `scripts/maintenance/verify_ref_layout.ps1`.
- Regle pratique : toute nouvelle cle de pilotage dans `config/` ; tout nouveau referentiel
  metier dans `ref/programme/` (ou `data/sources/` si donnee operationnelle).

## Regles hygiene repository

- Ne pas versionner les artefacts de run (`data/out/`, logs, caches Python, `__pycache__`, `.pytest_cache/`).
- Eviter tout chemin absolu machine dans les scripts (utiliser des chemins relatifs projet).
- Utiliser `pathlib` cote Python pour garder un comportement robuste sous Windows/Linux.

## Portee

Les phases 1-3 ne modifient pas le rendu metier des bilans PDF.
Elles clarifient l'usage, la navigation et la stabilite d'execution.
