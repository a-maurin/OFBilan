# Référentiels SIG

Ce dossier contient les référentiels cartographiques stables du projet.

## Contenu

- projet QGIS principal : `ref/sig/sd21_tout.qgz` ;
- fonds et couches de référence (communes, périmètres, couches d’appui) ;
- données de support utilisées par la cartographie.

## Règles d’usage

- `ref/sig/` ne contient pas les données opérationnelles de production ;
- les entrées métier sont lues dans `data/sources/sig/` ;
- les sorties cartographiques sont écrites dans `data/out/generateur_de_cartes/`.

## Paramétrage

Le chemin du projet QGIS est défini dans la configuration cartographique et peut être surchargé par la variable d’environnement `CARTO_PROJECT_QGIS_PATH`.
