# Referentiels du projet

`ref/` contient des **referentiels versionnes** utilises par les moteurs de bilan.

## Contenu attendu

- referentiels SIG (perimetres, couches d'appui cartographique) ;
- tables de correspondance (themes, domaines, NATINF, usagers) ;
- assets de mise en forme (modele OFB) et documentation source.

## Regle d'usage

- `ref/` n'est pas un dossier de sorties de run ;
- les artefacts generes vont dans `out/` ;
- les donnees locales non partagees vont dans `sources/` ou `data/`.

## Note de transition

Les fichiers de pilotage ont ete deplaces dans `config/` (presentation/charts).
Le code garde un fallback de compatibilite si un environnement local contient
encore les anciens fichiers dans `ref/`.
