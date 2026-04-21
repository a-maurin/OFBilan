# Bilans de production 2025-2026

Projet de generation des bilans d'activite de controle (SD Cote-d'Or) a partir des donnees OSCEAN et PVe.

## A quoi sert ce depot

Le depot produit deux types de rapports PDF :

- **Bilan global** : vue complete de l'activite du service (controles, resultats, PEJ, PA, PVe).
- **Bilans thematiques** : rapports cibles par profil (ex. `agrainage`, `chasse`, `types_usager`, `procedures_pve`, `pnf`).

Tout passe par un point d'entree unique :

- `scripts/run_bilan.py`

## Utilisation rapide

### Interface Windows (recommande)

- `lancer_bilans.bat` : generation des bilans (global/thematique)
- `generer_cartes.bat` : generation des cartes PNG
- `parametrer_cartes.bat` : parametrage des profils cartographiques

### CLI (direct)

```bat
REM Lister les themes disponibles
python scripts/run_bilan.py --list-themes

REM Bilan global
python scripts/run_bilan.py --mode global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

REM Bilan thematique (un ou plusieurs profils)
python scripts/run_bilan.py --mode thematique --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

REM Bilan thematique avec preset de taille graphique
python scripts/run_bilan.py --mode thematique --profil pnf --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21 --preset standard
```

## Objectifs fonctionnels

### 1) Bilan global

- **But** : produire un bilan unique sur une periode et un departement.
- **Entree recommandee** : `scripts/run_bilan.py --mode global`
- **Sorties** : `out/bilan_global/` (PDF + CSV)

### 2) Bilan thematique

- **But** : produire un ou plusieurs bilans cibles via des profils.
- **Entree recommandee** : `scripts/run_bilan.py --mode thematique --profil <id>`
- **Combine** possible : `--combine`
- **Sorties** : `out/bilan_<profil>/` (ou bilan combine)

## Architecture (vue simple)

- `scripts/run_bilan.py` : orchestrateur principal
- `scripts/bilan_global/analyse_global.py` : moteur global
- `scripts/bilan_thematique/bilan_thematique_engine.py` : moteur thematique unifie
- `scripts/bilan_thematique/run_bilan_thematique.py` : lanceur thematique direct
- `config/profils_bilan/` et `ref/profils_bilan/` : profils YAML de pilotage
- `scripts/common/` : utilitaires partages (PDF, chartes, loaders, etc.)

## Profils et options

Chaque profil YAML definit :

- le filtre metier,
- les sources actives (`point_ctrl`, `pej`, `pa`, `pve`),
- les options activables (`pnf`, `tub`, `cartes`, `synthese_croisee`, etc.).

Surcharge possible en CLI :

```bat
python scripts/run_bilan.py --mode thematique --profil chasse --with-pnf --no-tub
python scripts/bilan_thematique/run_bilan_thematique.py --profil agrainage --option synthese_croisee=true
```

## Taille des graphiques PDF

Configuration centralisee via :

- `ref/charts_config.yaml`

Presets disponibles :

- `compact`
- `standard`
- `large`

Utilisation :

```bat
python scripts/run_bilan.py --mode thematique --profil pnf --preset large
```

## Cartographie

Ordre recommande :

1. Generer les cartes (`generer_cartes.bat` ou script associe)
2. Generer les bilans (qui integrent ensuite les cartes disponibles)

Les cartes attendues sont stockees dans `out/generateur_de_cartes/` sous forme `carte_<profil>.png`.

## Prerequis

- Python 3.10+
- dependances Python du projet
- QGIS (uniquement pour la generation de cartes)

## Licence et contact

- Licence : voir `LICENSE`
- Auteur : Aguirre Maurin
- Service : OFB, SD Cote-d'Or
