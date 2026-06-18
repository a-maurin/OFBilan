## Règles de filtrage : bilans vs cartes

Objectif : lecture cohérente entre tableaux/PDF et cartes QGIS.

Sources de vérité :

- **Bilans** : `src/bilans/engine/orchestrateur_profils.py` (`_filter_point_ctrl`, `_filter_by_keywords`, filtres spécialisés).
- **Cartes** : `src/bilans/cartographie/production_cartographique.py` (expressions QGIS sur les couches).
- **Liaison profil bilan ↔ profil QGIS** : `src/bilans/common/cartographie_config.py`.

### Filtres côté bilans thématiques

| `filter.type` | Mécanisme bilan | Profils exemples |
|---------------|-----------------|------------------|
| `keywords` | `_filter_by_keywords` sur `columns` (theme, type_actio, nom_dossie…) | faune_sauvage, pollutions_urbaines |
| `agrainage` | `_filter_agrainage` + NATINF | agrainage |
| `chasse` | `est_chasse_point` + NATINF | chasse |
| `piegeage` | keywords piégeage (via filter keywords) | piegeage |
| `procedures` | PEJ/PA/PVe procédures | procedures_pve |
| `type_usager` | cibles usagers | types_usager, types_usager_cible |
| `all` | pas de filtre thème | global, synthese, pnf_foret (restriction geo) |

### Filtres côté cartes QGIS

| `filter_type` (symbologie couche) | Expression | Quand |
|-----------------------------------|------------|-------|
| `point_ctrl_global` | dept + période, tous contrôles | global, global_domaines |
| `point_ctrl_theme` | label thème (`ref_themes_ctrl`) LIKE sur theme/type_actio/nom | profils auto ref_themes |
| `point_ctrl_keywords` | mots-clés bilan LIKE (OR) sur colonnes YAML | surcharge depuis profil bilan |
| `point_ctrl_agrainage` | NATINF + zones agrainage | agrainage |
| `point_ctrl_chasse` | thème chasse | chasse |
| `point_ctrl_piegeage` | keywords piégeage | piegeage |
| `pj` / `pve` | procédures judiciaires / PVe | procedures_pve, synthèse carte 2 |

Période et département : toujours appliqués via `date_deb`, `date_fin`, `dept_code` CLI.

### Alignement automatique (Lot 2)

Lors d'un run `python -m ofbilan --cartes` :

1. `resolve_qgis_profile_ids` détermine les profils QGIS à générer.
2. `collect_bilan_carto_override` extrait `filter.keywords` et `filter.columns` du YAML bilan.
3. `run_export(..., qgis_overrides=...)` bascule la couche points en `point_ctrl_keywords` si des keywords sont présents.

Cas typiques :

- **faune_sauvage** : keywords `["faune sauvage"]` → même logique OR que le filtre pandas.
- **pollutions_urbaines** : keywords `["pollution", "urbaine"]` (plus fin que le label ref_themes seul).
- **Profils dedie** (agrainage, chasse) : filtres QGIS spécialisés dans `profils_cartes.yaml`, pas de keywords génériques.

### Profils sans génération QGIS

- `types_usager_cible` : mode `manuel` — dépôt PNG externe.
- `--no-cartes` : section PDF avec message « Cartographie désactivée ».

QGIS indisponible : pas d'erreur ; fallback PDF avec noms de fichiers attendus.

### Vérification manuelle (non-régression)

Pour un profil `<id>` et une période donnée :

1. Noter le nombre de contrôles agrégés (CSV ou PDF sec. 2).
2. Générer la carte : `python -m ofbilan --profil <id> --cartes ...`
3. Vérifier `data/out/generateur_de_cartes/carte_<id>.png` (ou fichiers catalogue global).
4. Contrôler visuellement que les points cartographiés correspondent au périmètre attendu.

En cas d'écart : ajuster `cartographie.keywords` / `profil_qgis` dans le YAML profil, ou l'entrée dans `profils_cartes.yaml`.

### Évolution d'un profil

1. Modifier le filtre bilan dans `config/profils_bilan/<id>.yaml`.
2. Si keywords changent : la surcharge QGIS suit automatiquement.
3. Si filtre spécialisé (agrainage, chasse…) : mettre à jour `profils_cartes.yaml` et symbologies associées.
4. Mettre à jour ce document si une nouvelle famille de filtres est introduite.
