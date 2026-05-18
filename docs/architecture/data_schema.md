## Schémas de données attendus (chargement)

Ce document résume les **colonnes obligatoires** et **principales colonnes normalisées**
par les fonctions de chargement de `src/bilans/common/loaders.py`. Il sert de référence
en cas d'évolution des extractions OSCEAN / PVe / référentiels.

### Points de contrôle OSCEAN (`load_point_ctrl`)

- **Sources** : `data/sources/sig/points_de_ctrl_OSCEAN_YYYY/*.{gpkg,shp}` ou, en repli, `data/sources/sig/*.{gpkg,shp}` contenant `ctrl` dans le nom.
- **Colonnes obligatoires** :
  - `date_ctrl` : date de contrôle (convertie en `datetime64`),
  - `dc_id` : identifiant de dossier de contrôle,
  - `num_depart` : code département (filtre départemental),
- **Colonnes normalisées / alias courants** :
  - `nom_dossie` (alias possible de `nom_dossier`),
  - `type_actio` (alias possible de `type_action`),
  - `resultat` (alias possible de `Résultat` ou `RESULTAT`),
  - `nom_commun` (alias possible de `nom_commune`),
  - `type_usager` / `type_usage` (création d’alias réciproques),
  - `nature_con` / `nature_controle`,
  - `plan_contr` / `plan_controle`,
  - `avis_patbiodiv` / `avis_patbi` / `avis_pasbi`.

Les lignes sont filtrées par **département** (`num_depart`) et par **période**
(`date_ctrl`) si `dept_code`, `date_deb` et `date_fin` sont fournis.

### Procédures d’enquête judiciaire (`load_pej`)

- **Source** : `data/sources/suivi_procedure_enq_judiciaire_YYYYMMDD.ods`.
- **Colonnes obligatoires** :
  - `DATE_CONSTATATION`,
  - `DATE_OUVERTURE_PROCEDURE`,
  - `RECAP_DATE_INIT_PJ` (peut être absente, dans ce cas une série vide est utilisée),
- **Colonnes normalisées / alias courants** :
  - `NATINF_PEJ` (alias possible de `NATINF`),
  - `DATE_REF` : date de référence calculée comme premier non nul parmi
    `DATE_CONSTATATION`, `DATE_OUVERTURE_PROCEDURE`, `RECAP_DATE_INIT_PJ`.

Le filtrage temporel éventuel repose sur la colonne `DATE_REF`.

### Procédures administratives (`load_pa`)

- **Source** : `data/sources/suivi_procedure_administrative_YYYYMMDD.ods`.
- **Colonnes obligatoires** :
  - `DATE_CONTROLE`,
  - `DATE_DOSSIER`,
- **Colonnes normalisées** :
  - `DATE_REF` : date de référence calculée comme premier non nul parmi
    `DATE_CONTROLE` et `DATE_DOSSIER`.

Le filtrage temporel éventuel repose sur la colonne `DATE_REF`.

### Référentiel PNF (`load_pnf`)

- **Sources** : `ref/programme/sig/communes_pnf/communes_pnf.shp` (prioritaire), puis `ref/programme/tables_reference/communes_PNF.csv`, ou `data/sources/communes_PNF.csv`.
- **Colonnes obligatoires** :
  - `CODE_INSEE` (code INSEE sur 5 caractères, `zfill(5)` appliqué).

### Référentiel TUB (`load_tub`)

- **Source** : `ref/programme/tables_reference/tub_communes.csv` ou, en repli, `data/sources/tub_communes.csv`.
- **Colonnes obligatoires** :
  - `INSEE_COM` (code INSEE sur 5 caractères, `zfill(5)` appliqué).

### Table des centroïdes communes (`load_communes_centroides`)

- **Sources possibles** :
  - `ref/hors_programme/sig/communes-france-2025.csv` (hors pipeline principal ; fonction non branchée au runtime),
  - ou, en repli, shapefile/GeoPackage équivalent sous `ref/programme/sig/` ou `ref/hors_programme/sig/`.
- **Colonnes obligatoires (CSV)** :
  - code INSEE : `code_insee` ou `CODE_INSEE` ou `insee`,
  - coordonnées : `latitude_centre` / `longitude_centre` (ou variantes majuscules / `_centre`).

Les valeurs invalides ou sans coordonnées sont exclues du DataFrame retourné.

### Référentiel NATINF (`load_natinf_ref`)

- **Sources possibles** :
  - `ref/programme/tables_reference/liste_natinf.csv`,
  - ou `ref/programme/tables_reference/liste-natinf-avril2023.csv`,
  - ou équivalents présents dans `data/sources/`.
- **Colonnes obligatoires** :
  - numéro NATINF : `Numéro NATINF` ou `numero_natinf` ou `NATINF` ou `natinf`
    (renommée en `numero_natinf`),
- **Colonnes dérivées** :
  - `nature_infraction` (si colonne descriptive présente),
  - `qualification_infraction` (si présente),
  - `libelle_natinf` : libellé utilisé par les bilans (qualification ou nature).

La fonction retourne un DataFrame dédoublonné minimal avec au moins
`numero_natinf` et `libelle_natinf`.

