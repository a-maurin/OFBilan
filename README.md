# Bilans Production

Application de génération de bilans PDF d’activité de contrôle à partir de sources OSCEAN et PVe.

## Finalité

Le programme produit :

- un **bilan global** (vision consolidée d’un département et d’une période) ;
- des **bilans thématiques** (profils métier paramétrables).

## Prérequis

- Python 3.10 ou supérieur ;
- dépendances Python du projet ;
- QGIS uniquement pour la production cartographique.

Installation :

```bash
pip install -e .
```

## Exécution

Entrée officielle :

```bash
python -m bilans
```

Exemples :

```bash
# Lister les profils thématiques
python -m bilans --list-themes

# Bilan global
python -m bilans --mode global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

# Bilans thématiques
python -m bilans --mode thematique --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21
```

Lanceurs :

- Windows : `scripts/windows/lancer_bilans.bat`, `scripts/windows/generer_cartes.bat`, `scripts/windows/parametrer_cartes.bat`
- Linux : `scripts/linux/lancer_bilans.sh`, `scripts/linux/generer_cartes.sh`, `scripts/linux/parametrer_cartes.sh`

## Données attendues

Le programme lit les entrées dans `data/sources/`.

Jeux principaux :

- points de contrôle OSCEAN : `data/sources/sig/points_de_ctrl_OSCEAN_*/`
- procédures judiciaires : `data/sources/suivi_procedure_enq_judiciaire_*.ods`
- procédures administratives : `data/sources/suivi_procedure_administrative_*.ods`
- PVe : `data/sources/Stats_PVe_OFB*`
- faits PJ géolocalisés : `data/sources/sig/points_infractions_pj/localisation_infrac_FAITS_*`

## Sorties

Les résultats sont écrits dans `data/out/` :

- `data/out/bilan_global/`
- `data/out/bilan_<profil>/`
- `data/out/generateur_de_cartes/`

## Organisation du dépôt

- `src/bilans/` : code applicatif ;
- `config/` : configuration de pilotage (profils, présentation PDF, charts) ;
- `ref/` : référentiels versionnés ;
- `data/` : entrées locales et sorties ;
- `docs/` : documentation d’architecture, d’usage et de migration ;
- `tests/` : tests unitaires et smoke.

## Références

- Description des sources : `docs/architecture/README_sources.md`
- Schéma des données : `docs/architecture/data_schema.md`
- Licence : `LICENSE`

