# Production cartographique

Ce document décrit la génération des cartes utilisées dans les bilans.

## Prérequis

- QGIS/OSGeo installé ;
- Python ≥ 3.10 et package installé (`pip install -e .`) ;
- projet QGIS présent : `ref/programme/sig/bilans_carte.qgz` ;
- données opérationnelles disponibles dans `data/sources/` et `data/sources/sig/`.

## Scripts Windows

- `scripts/windows/parametrer_cartes.bat` : paramétrage des couches ;
- `scripts/windows/generer_cartes.bat` : génération des cartes.

## Scripts Linux

- `scripts/linux/parametrer_cartes.sh` : paramétrage des couches ;
- `scripts/linux/generer_cartes.sh` : génération des cartes.

## Sortie

Les cartes sont écrites dans `data/out/generateur_de_cartes/`.

## Mise en page (layout_defaults)

À l'export, le moteur applique `src/bilans/cartographie/param/layout_defaults.yaml` :

- gabarit **`carre_210`** : page 210×210 mm (réf. agrainage), carte pleine largeur, **une seule légende** à droite (154–210 mm) ;
- gabarit **`a4_paysage`** : page 297×210 mm (layouts SD21), légende unique colonne droite ;
- sélection du template : `layout_defaults_ref` sur le profil, sinon détection automatique selon la taille de page du layout QGIS ;
- logos : bandeau haut (`bandeau_logos_ofb`) injecté par Python ; logo RF-OFB bas droite repositionné depuis le YAML (pas de doublon si déjà présent dans le `.qgz`) ;
- ids titre : mapping `layout_title_ids` (ex. layout agrainage → id label QGIS long).

Surcharge par profil dans `profils_cartes.yaml` : `layout_defaults_ref: carre_210` ou `a4_paysage`.

## Diagnostic

En cas d’erreur, vérifier en priorité :
- l’existence du projet QGIS ;
- la présence des couches attendues ;
- la cohérence des chemins de données.
