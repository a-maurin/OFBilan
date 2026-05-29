## Cartes et bilans : chaîne d'intégration

Les bilans PDF intègrent des cartes PNG stockées dans `data/out/generateur_de_cartes/`.

Entrée officielle : `python -m bilans --profil <id> [--cartes] [--no-cartes]`.

### Nom des fichiers

- **Format général** : `carte_<map_id>.png`
- **Profil global (catalogue)** : fichiers déclarés dans `config/profils_bilan/global.yaml` → `cartographie.catalog`
  - `carte_global.png`, `carte_global_usagers.png`, `carte_procedures_pve.png`, `carte_global_domaines.png`
- **Synthèse PA/PJ** : `carte_synthese_activite_PA_PJ.png`, `carte_synthese_activite_PA_PJ_2.png`
- **Types d'usagers ciblé** : `carte_{map_id}.png` (map_id = codes usagers sélectionnés, ex. `AGR`)

### Modes cartographiques (profil YAML)

Résolus par `src/bilans/common/cartographie_config.py` :

| Mode | Profils | Génération QGIS | PDF |
|------|---------|-----------------|-----|
| `catalog` | `global` | Sélection utilisateur (4 vues) | Toutes les cartes choisies, une par page |
| `synthese` | `synthese_activite_PA_PJ` | 2 profils QGIS dédiés | 2 PNG déclarés dans `cartographie.fichiers` |
| `dedie` | agrainage, chasse, piegeage, procedures_pve, types_usager, pnf_foret… | Entrée dans `profils_cartes.yaml` | `carte_<profil_id>.png` ou alias (`global_usagers`) |
| `thematique_ref` | Thématiques keywords (défaut) | Auto depuis `ref_themes_ctrl.csv` + surcharge keywords | `carte_<profil_id>.png` |
| `manuel` | `types_usager_cible` | Aucune (dépôt manuel) | Motifs `carte_{map_id}.png` |
| `none` | — | Aucune | Section carto désactivée ou fallback |

Mode explicite via `cartographie.mode` dans le YAML profil ; sinon inféré depuis `filter.type` et `pipeline`.

### Flux CLI

1. `run_profiles_batch` agrège les profils QGIS via `resolve_map_profiles_for_batch`.
2. `ensure_maps_for_profiles` cherche les PNG existants, tente QGIS pour les manquants (non bloquant).
3. Le moteur résout les chemins PDF via `resolve_profile_map_paths` / catalogue global.
4. Carte absente → message fallback dans le PDF, bilan terminé normalement.

### Options CLI utiles

```bash
# Global : sous-ensemble de cartes
python -m bilans --profil global --cartes --carte global --carte global_domaines
python -m bilans --profil global --cartes --carte all

# Désactiver les cartes
python -m bilans --profil chasse --no-cartes
```

### Fichiers de référence

- Profils bilan : `config/profils_bilan/<id>.yaml`
- Profils QGIS : `src/bilans/cartographie/param/profil_cartes.yaml`
- Symbologies : `src/bilans/cartographie/param/symbologies.yaml`
- Alignement filtres : `docs/usage/filtrage_bilans_et_cartes.md`

### Bonnes pratiques

- Nouveau profil thématique : id YAML = id dans `ref/programme/tables_reference/ref_themes_ctrl.csv` → profil QGIS auto.
- Keywords atypiques (ex. pollutions_urbaines) : alignés automatiquement via `filter.keywords` → filtre QGIS `point_ctrl_keywords`.
- Override ponctuel : `cartographie.profil_qgis` ou `cartographie.keywords` dans le YAML profil.
