# Referentiels du projet

`ref/` contient des **referentiels versionnes** utilises par les moteurs de bilan.

## Contenu attendu

- referentiels SIG (perimetres, couches d'appui cartographique) ;
- tables de correspondance (themes, domaines, NATINF, usagers) ;
- assets de mise en forme (modele OFB, glossaires, documentation source).

## Regle d'usage

- `ref/` n'est pas un dossier de sorties de run ;
- les artefacts generes vont dans `out/` ;
- les donnees locales non partagees vont dans `sources/` ou `data/`.

## Note de transition

Certains fichiers de pilotage restent encore lus depuis `ref/` pour compatibilite :

- `pdf_presentation.yaml`
- `charts_config.yaml`
- `glossaire.yaml`

La cible est de regrouper progressivement ces reglages dans `config/`.
