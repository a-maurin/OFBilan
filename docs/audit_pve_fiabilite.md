# Audit de fiabilité des totaux PVe

Ce document fixe les définitions de « total PVe » selon le livrable, un protocole de contrôle reproductible, et les écarts attendus avec des outils externes (QGIS, Excel).

## 1. Définition du total selon le livrable

| Livrable | Base de comptage | Filtres / géo inclus ? | Fichier / indicateur typique |
|----------|------------------|-------------------------|------------------------------|
| **Profil pipeline `global`** (ex. exécution via `_run_global_profile_via_yaml`) | Lignes après `load_pve` (département + période sur `INF-DATE-INTG`) puis `ensure_insee_from_communes_shp` si PVe non vide | **Pas** de `_filter_pve`, **pas** de `restrict_geo` sur PVe | Adapter d’agrégation du profil ; pour la synthèse : `pve_global_resume.csv` (`nb_pve_global`), `synthese_resume.csv` (`nb_pve`) |
| **Profil `synthese_activite_PA_PJ`** | Identique au global : `load_pve` + éventuel enrichissement INSEE | Même jeu que ci-dessus | `analyse_pve_global` → `nb_pve_global` = `len(pve)` |
| **Profil thématique** (`run_profile_engine` / moteur unifié) | Lignes du DataFrame **`pve_filtered`** au moment des agrégations | **`load_pve`** → **`_filter_pve`** (NATINF / mots-clés) → **`restrict_geo: pnf`** (`_apply_restrict_geo_pnf`) → enrichissements spatiaux **sans** ajout de lignes | `nb_pve` dans les résultats moteur = `len(pve_filtered)` ; export `pve_<prefix>.csv` (même nombre de lignes que le jeu filtré) |

**Règle importante** : comparer un PDF ou un CSV **thématique** au `nb_pve_global` de la synthèse (tous NATINF du département) conduira à un **écart normal** si le profil restreint les NATINF ou le périmètre PNF.

## 2. Chaîne technique (rappel)

1. **Fichier source** : le fichier `Stats_PVe_OFB*` le plus récent (par date de modification) sous `data/sources/`.
2. **`load_pve`** : filtre département (`INF-DEPART` / `INF-DEPARTEMENT`), période inclusive sur **`INF-DATE-INTG`**, enrichissement coordonnées (merge left sur centroïdes PNF — pas de duplication de lignes).
3. **`_filter_pve`** : `natinf_pve` du profil (regex `contient_natinf`) ou `filter.keywords` sur colonnes présentes.
4. **`restrict_geo: pnf`** : conservation des PVe dont l’INSEE PNF ou la position SIG tombe dans le périmètre.
5. **`nb_pve`** : `len(pve_filtered)` dans `_run_aggregations` ; le CSV détail `pve_<prefix>.csv` reflète ce jeu.

**Doublons** : le pipeline standard **ne déduplique pas** les PVe sur `INF-ID` (contrairement à certaines règles PEJ/PA). Des lignes dupliquées en source sont comptées plusieurs fois.

## 3. Protocole d’audit en six étapes

1. **Identifier le fichier** réellement lu (même règle que le code : `max(..., key=mtime)` sur `data/sources/Stats_PVe_OFB*`).
2. **Rejouer `load_pve`** avec les mêmes `dept_code`, `date_deb`, `date_fin` que la CLI ; vérifier le log INFO « PVe : X ligne(s) retenues… » et `len(df)`.
3. **Appliquer le filtre profil** : relire le YAML fusionné (`_defaults` + profil) ; rejouer `_filter_pve` (ou la logique équivalente documentée dans le code).
4. **Si `restrict_geo: pnf`** : le total affiché doit être **inférieur ou égal** au total après étape 3 ; lister les exclusions (hors liste INSEE PNF et hors union SIG).
5. **Cohérence des ventilations** : la somme d’un tableau (ex. par NATINF) n’égale `nb_pve` que si la ventilation est une **partition** (une ligne PVe → une seule ligne agrégée). Sinon, documenter les cas de ventilation multiple.
6. **Contrôle doublons source** : sur le fichier brut, compter les doublons sur la clé métier attendue (`INF-ID` ou équivalent) si l’exigence métier est l’unicité par dossier.

## 4. Outils du dépôt

- **Synthèse** : [`tools/audit_synthese_donnees.py`](../tools/audit_synthese_donnees.py) — contrôle `len(pve)` vs `pve_global_resume.csv` et `synthese_resume.csv`.
- **Profil thématique + dossier de sortie** : [`tools/audit_pve_totaux.py`](../tools/audit_pve_totaux.py) — rejoue `load_pve` + `_filter_pve` (+ restriction PNF si configurée) et compare au nombre de lignes des exports `pve_*.csv` (hors `*_par_zone.csv`).

### Exemples de commandes

```bash
pip install -e .
# Après un bilan synthèse (même dept / période que le script)
python tools/audit_synthese_donnees.py

# Après un bilan thématique : comparer rejoué vs CSV exporté
python tools/audit_pve_totaux.py --profil pnf --dept 21 --date-deb 2025-01-01 --date-fin 2025-12-31 --out-dir data/out/bilan_pnf
```

Sans `data/sources/` adapté, les scripts signalent l’absence de données ou des écarts attendus ; l’audit reste valable sur poste de production où les sources sont présentes.

## 5. Écart fréquent avec QGIS / Excel

Une jointure ou un filtre spatial **sans** la même fenêtre temporelle sur **`INF-DATE-INTG`** compte des intégrations hors période d’analyse. Le message INFO de `load_pve` rappelle ce point.

## 6. Vérification « run réel » (checklist)

Après exécution d’un bilan :

1. Noter `len(pve)` dans la console ou via `audit_synthese_donnees.py` / `audit_pve_totaux.py` (mode sans `--out-dir` : affichage seul du rejoué).
2. Ouvrir `pve_<prefix>.csv` (profil thématique) ou `pve_global_resume.csv` (synthèse) et comparer les comptages documentés en section 1.
3. Ouvrir le PDF : repérer l’indicateur « nombre de PVe » et vérifier qu’il correspond au **même** pipeline (global vs thématique).
4. **Tableau « Détail des PVe » (§ 3.1)** : avec `blocks.sec31.max_detail_rows: 0` dans [`config/presentation/pdf_presentation.yaml`](../config/presentation/pdf_presentation.yaml), le nombre de lignes du tableau doit égaler `nb_pve`. Si `max_detail_rows > 0`, la légende indique « N premiers sur T » et le total affiché en chiffre clé reste **T**.

Cette checklist valide le protocole sans imposer de données sensibles dans le dépôt.

### Exemple exécuté (poste avec `data/sources/`)

Sur le dépôt de développement (département 21, période 2025-01-01 au 2025-12-31, profil `procedures_pve`), `load_pve` puis `_filter_pve` ont produit **76** lignes ; un export factice `pve_*.csv` de 76 lignes de données a été validé **OK** par `tools/audit_pve_totaux.py --out-dir ...`.
