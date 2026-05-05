# Production cartographique

Ce document décrit la génération des cartes utilisées dans les bilans.

## Prérequis

- QGIS/OSGeo installé ;
- projet QGIS présent : `ref/sig/sd21_tout.qgz` ;
- données opérationnelles disponibles dans `data/sources/` et `data/sources/sig/`.

## Scripts Windows

- `scripts/windows/parametrer_cartes.bat` : paramétrage des couches ;
- `scripts/windows/generer_cartes.bat` : génération des cartes.

## Scripts Linux

- `scripts/linux/parametrer_cartes.sh` : paramétrage des couches ;
- `scripts/linux/generer_cartes.sh` : génération des cartes.

## Sortie

Les cartes sont écrites dans `data/out/generateur_de_cartes/`.

## Diagnostic

En cas d’erreur, vérifier en priorité :
- l’existence du projet QGIS ;
- la présence des couches attendues ;
- la cohérence des chemins de données.
