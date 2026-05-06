# Sources de données

Ce document résume les sources exploitées par le programme.

## Emplacements officiels

- contrôles OSCEAN : `data/sources/sig/points_de_ctrl_OSCEAN_*/`
- PEJ : `data/sources/suivi_procedure_enq_judiciaire_*.ods`
- PA : `data/sources/suivi_procedure_administrative_*.ods`
- PVe : `data/sources/Stats_PVe_OFB*`
- faits PJ géolocalisés : `data/sources/sig/points_infractions_pj/localisation_infrac_FAITS_*`
- référentiels : `ref/` et `ref/sig/`

## Principes de traitement

- les bilans appliquent un filtrage par période et département ;
- les sources sont croisées par identifiants métier lorsque nécessaire ;
- les référentiels servent à la normalisation, à la qualification et à la cartographie.

## Références techniques

- chargement des données : `src/bilans/common/chargeurs_donnees.py`
- utilitaires de transformation : `src/bilans/common/utilitaires_metier.py`
- schéma synthétique : `docs/architecture/data_schema.md`
