# Migration CLI — moteur unique par profil

## Rupture (breaking change)

- **`--mode global` / `--mode thematique` sont supprimés.**  
  Toute exécution passe par **`--profil`** (y compris le bilan global).

## Nouvelles commandes

```bash
# Lister les profils (numérotation pour saisie interactive)
python -m bilans --list-themes

# Bilan global
python -m bilans --profil global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

# Un ou plusieurs bilans thématiques
python -m bilans --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

# Plusieurs profils avec récapitulatif combiné (si autorisé par leurs capacités)
python -m bilans --profil chasse --profil agrainage --combine --date-deb ... --date-fin ... --dept-code 21
```

Règles d'usage :

- Les restrictions batch/combine sont pilotées par `capabilities.combine` et `capabilities.mix_batch` dans les profils YAML.
- Sans `--profil`, la CLI affiche les profils disponibles et demande une sélection interactive.

## Points d’entrée historiques

- **`python -m bilans`** reste l’entrée officielle.
- **`bilans.bilan_global`** : package historique retiré ; utiliser `python -m bilans --profil global`.
- **`bilans.bilan_thematique.run_bilan_thematique`** : point d’entrée retiré ; utiliser `python -m bilans`.

## Fichiers de configuration

- Profil global : `config/profils_bilan/global.yaml` (`pipeline: global`).
- Profils thématiques : `config/profils_bilan/<id>.yaml` (comportement inchangé côté YAML métier).
- Chaque profil peut aussi déclarer ses adapters `aggregation.adapter` et `pdf.adapter`.
- Le socle partagé est déclaré dans `config/profils_bilan/_defaults.yaml` puis fusionné avec chaque profil.

## Recette de parité (manuelle / données réelles)

À valider avec les jeux de données du département cible :

1. **global** — sorties sous `data/out/bilan_global/` (CSV + PDF attendus).
2. **chasse** — `data/out/bilan_chasse/` (ou sous-dossier défini par le profil).
3. **agrainage** — idem.

Contrôles minimaux : présence des CSV pivots habituels, PDF sans section critique vide par erreur, graphiques et légendes lisibles.

## Évolutions prévues (hors scope immédiat)

- Registre central de sections PDF (`section_id → renderer`) partagé global / thématique pour réduire encore la duplication dans `_generate_pdf` / `_generate_pdf_content`.
