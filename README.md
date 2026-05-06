# Bilans Production

Application de génération de bilans PDF d’activité à partir de données OSCEAN et PVe.

## Finalité

Le programme produit deux types de livrables :

- un **bilan global** : une vision consolidée d’un département sur une période donnée ;
- des **bilans thématiques** : des bilans spécialisés, selon des profils métier paramétrables.

## Prérequis

- Python 3.10 ou supérieur ;
- les dépendances Python du projet ;
- QGIS uniquement si vous générez les cartes.

Installation :

```bash
pip install -e .
```

## Exécution

**Rupture CLI :** l’option `--mode` n’est plus utilisée ; utilisez `--profil` (dont `global`). Voir `docs/migration/cli_moteur_unique.md`.
La compatibilité multi-profils (batch/combine), l’adapter d’agrégation et l’adapter de rendu PDF sont pilotés par les profils YAML.
Si aucun `--profil` n’est fourni, la CLI propose une sélection interactive.

Point d’entrée principal :

```bash
python -m bilans
```

Exemples de commandes :

```bash
# Lister les profils disponibles
python -m bilans --list-themes

# Bilan global
python -m bilans --profil global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

# Un ou plusieurs bilans thématiques
python -m bilans --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21
```

Scripts de lancement :

- Windows : `scripts/windows/lancer_bilans.bat`, `scripts/windows/generer_cartes.bat`, `scripts/windows/parametrer_cartes.bat`
- Linux : `scripts/linux/lancer_bilans.sh`, `scripts/linux/generer_cartes.sh`, `scripts/linux/parametrer_cartes.sh`

## Données attendues

Le programme lit les fichiers d’entrée dans `data/sources/`.

Jeux de données principaux :

- points de contrôle OSCEAN : `data/sources/sig/points_de_ctrl_OSCEAN_*/`
- procédures judiciaires : `data/sources/suivi_procedure_enq_judiciaire_*.ods`
- procédures administratives : `data/sources/suivi_procedure_administrative_*.ods`
- PVe : `data/sources/Stats_PVe_OFB*`
- faits PJ géolocalisés : `data/sources/sig/points_infractions_pj/localisation_infrac_FAITS_*`

## Sorties

Les résultats sont écrits dans `data/out/` :

- `data/out/bilan_global/` : PDF et exports du bilan global ;
- `data/out/bilan_<profil>/` : PDF et exports associés à chaque profil thématique ;
- `data/out/generateur_de_cartes/` : sorties intermédiaires de la génération cartographique.

## Organisation du dépôt

- `src/bilans/` : code applicatif principal ;
- `config/` : configuration de pilotage (profils, présentation PDF, graphiques) ;
- `config/profils_bilan/_defaults.yaml` : socle YAML commun (pipeline, adapters agrégation/PDF, capacités par défaut) fusionné avec chaque profil ;
- `ref/` : référentiels versionnés utilisés par l’application ;
- `data/` : données d’entrée locales et sorties générées ;
- `docs/` : documentation d’architecture, d’usage et de migration ;
- `tests/` : tests unitaires et tests smoke.

## Références

- Description des sources : `docs/architecture/README_sources.md`
- Schéma des données : `docs/architecture/data_schema.md`
- Licence : Apache License 2.0 (`LICENSE`)

## Contact

- Auteur : Aguirre Maurin
- Service : OFB, SD Côte-d'Or
- Courriel : [aguirre.maurin@ofb.gouv.fr](mailto:aguirre.maurin@ofb.gouv.fr)

