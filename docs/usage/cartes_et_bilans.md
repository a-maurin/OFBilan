## Cartes et bilans : chaîne d'intégration

Les bilans PDF intègrent des cartes PNG stockées dans `data/out/generateur_de_cartes/`.

Entrée officielle : `python -m ofbilan --profil <id> [--cartes] [--no-cartes]`.

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
python -m ofbilan --profil global --cartes --carte global --carte global_domaines
python -m ofbilan --profil global --cartes --carte all

# Désactiver les cartes
python -m ofbilan --profil chasse --no-cartes
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

### Génération adaptative (pochoir, emprise, titres par département)

La cartographie **dynamique** (pochoir depuis `ref/programme/sig/limites_admin_dep/DEPARTEMENT_ADMIN_Express_200207.shp`, zoom sur le département, titres adaptés) nécessite **PyQGIS** (`import qgis.core`). Le Python « classique » de `python -m ofbilan` ne le fournit en général pas → message du type *« QGIS non disponible »*.

#### Génération automatique depuis `python -m ofbilan` (sans PyQGIS in-process)

Si QGIS est installé mais que `python -m ofbilan` affiche encore un avertissement PyQGIS, le moteur tente un **export en sous-processus** via `lancer_production_cartographique.bat` (variable `BILANS_CARTO_HEADLESS=1`). Les 4 cartes du catalogue global sont générées en un seul appel si la sélection les inclut toutes.

Sinon, utiliser explicitement :

```bat
scripts\windows\lancer_bilans_qgis.bat --profil global --cartes --echelle departement --code 25 --date-deb 2025-01-01 --date-fin 2025-12-31
```

#### Windows — bilan + cartes en une commande (recommandé)

1. Installer **QGIS** (standalone ou OSGeo4W) depuis [qgis.org](https://qgis.org/).
2. Installer le package bilan dans l’interpréteur **QGIS** (une fois) :
   ```bat
   cd C:\chemin\vers\Bilans_production
   "C:\Program Files\QGIS 3.40.15\bin\python.exe" -m pip install -e .
   ```
   (Adapter le chemin : dans QGIS → *Extensions → Console Python* : `import sys; print(sys.executable)`.)
3. Lancer le bilan avec le script dédié :
   ```bat
   scripts\windows\lancer_bilans_qgis.bat --profil global --cartes --echelle departement --code 25 --date-deb 2025-01-01 --date-fin 2025-12-31
   ```
   Ce script utilise le Python QGIS/OSGeo4W (même logique que `lancer_production_cartographique.bat`).

   **Sans argument**, le script configure uniquement l'environnement QGIS puis délègue toute la saisie à `python -m ofbilan` (profils, période, échelle, cartes) — pas de double invite batch/CLI.

#### Windows — pré-générer les PNG puis bilan classique

1. Générer les cartes avec QGIS :
   ```bat
   scripts\windows\generer_cartes.bat --profil global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 25
   ```
   Répéter pour chaque vue du catalogue global si besoin (`global_usagers`, `procedures_pve`, `global_domaines`) via `src\bilans\cartographie\lancer_production_cartographique.bat <profil_qgis> --date-deb ... --date-fin ... --dept-code 25`.
2. Vérifier `data/out/generateur_de_cartes/` : PNG + marqueur `carte_<nom>.XX.dept` (ex. `carte_global.25.dept`).
3. Lancer le bilan avec le Python habituel :
   ```bat
   python -m ofbilan --profil global --cartes --echelle departement --code 25 --date-deb 2025-01-01 --date-fin 2025-12-31
   ```

#### Vérifier que PyQGIS est détecté

```bat
python -c "from qgis.core import Qgis; print('PyQGIS OK')"
```
→ doit échouer avec le Python système ; réussir avec le Python affiché par `lancer_bilans_qgis.bat` (ligne *Python QGIS : …*). Sans argument, le script délègue le menu interactif au CLI `bilans`.

Si QGIS est installé mais non détecté : créer `scripts\windows\qgis_python_path.txt` ou `src\bilans\cartographie\qgis_python_path.txt` contenant **une ligne** = chemin complet vers `python.exe` QGIS.

#### Marqueurs département et rétrocompatibilité

- Après export QGIS : fichier sidecar `carte_global.25.dept` (texte `25`) à côté de `carte_global.png`.
- Sans marqueur : seul le département **21** est accepté comme carte pré-générée legacy (Côte-d'Or).
- Département **≠ 21** sans QGIS ni marqueur : cartes ignorées dans le PDF + avertissement dans les logs.

Voir aussi : `docs/usage/README_Production_cartes.md`, `scripts/windows/lancer_bilans_qgis.bat`.
