# Référentiels (`ref/`)

Ce dossier est scindé en deux parties pour distinguer ce que lit **`python -m bilans`** (et la cartographie associée) du reste.

## `ref/programme/`

Fichiers **utilisés au runtime** : tables CSV, couches SIG indispensables, assets charte OFB (PDF et cartes).

Voir `ref/programme/README.md` pour le détail.

## `ref/hors_programme/`

Fichiers **non branchés** sur le pipeline principal : jeux SIG d’appui QGIS, concordances pour scripts `tools/`, modèle Word OFB complet, documentation.

Ne pas supprimer sans vérifier le projet QGIS (`sd21_tout.qgz`) et les outils de maintenance.

## Données opérationnelles

Les entrées de production restent dans `data/sources/` ; les sorties dans `data/out/`.

## Vérification

```powershell
.\scripts\verify_ref_layout.ps1
# ou : python scripts/verify_ref_layout.py
```

Contrôle la présence des fichiers sous `programme/`, l’absence des anciens dossiers à la racine de `ref/`, et les imbrications erronées (`communes_pnf/communes_pnf`, etc.).
