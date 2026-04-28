# Schéma des données sources — Bilans_production

Ce document décrit les **sources de données**, les **champs** utilisés et les **règles de filtrage** appliquées dans les bilans. Les chargements sont centralisés dans `scripts/common/loaders.py`.

---

## 1. Vue d’ensemble des sources


| Source                           | Emplacement                                                                                 | Format        | Rôle                                                                                                                                                                            |
| -------------------------------- | ------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Points de contrôle**           | `sources/sig/point_ctrl_YYYYMMDD_wgs84.gpkg`                                                | GPKG          | Contrôles OSCEAN (un fichier par année, suffixe de date le plus récent)                                                                                                         |
| **PEJ**                          | `sources/suivi_procedure_judiciaire_YYYYMMDD.ods` ou `suivi_procedure_enq_judiciaire_*.ods` | ODS           | Procédures d’enquête judiciaire                                                                                                                                                 |
| **PA**                           | `sources/suivi_procedure_administrative_YYYYMMDD.ods`                                       | ODS           | Procédures administratives                                                                                                                                                      |
| **PVe**                          | `sources/Stats_PVe_OFB*.csv` ou `.ods`                                                      | CSV (;) / ODS | Procès-verbaux électroniques OFB (fichier le plus récent par date de modification)                                                                                              |
| **Points infractions PJ**        | `sources/sig/points_infractions_pj/localisation_infrac_FAITS_YYYYMMDD.gpkg`                 | GPKG / SHP    | Géolocalisation des faits PJ                                                                                                                                                    |
| **Communes PNF (périmètre)**     | `ref/sig/communes_pnf/communes_pnf.shp`                                                     | SHP           | Communes du parc (prioritaire pour `load_pnf`) ; repli : `communes_PNF.csv`                                                                                                     |
| **PNF — cœur de parc**           | `ref/sig/PNF/coeur_pnforets/Coeur_data_gouv_PNForets.shp`                                   | SHP           | Périmètre détaillé « cœur » (`load_pnf_coeur_gdf`)                                                                                                                              |
| **PNF — aire d'adhésion (2021)** | `ref/sig/PNF/aoa_2021_pnforets/AOA_2021_PNForets.shp`                                       | SHP           | Aire d'adhésion (`load_pnf_aoa_gdf`) ; source indicative : [Ternum BFC — périmètres PNF](https://trouver.ternum-bfc.fr/dataset/perimetres-detailles-du-parc-national-de-forets) |
| **Référentiels**                 | `ref/`                                                                                      | CSV, SIG      | PNF, TUB, centroïdes communes, NATINF                                                                                                                                           |


---

## 2. Champs par source

### 2.1 Points de contrôle (GPKG)


| Champ                        | Rôle / règle                                                             |
| ---------------------------- | ------------------------------------------------------------------------ |
| `dc_id`                      | Identifiant dossier de contrôle                                          |
| `fid`                        | Identifiant du point (localisation)                                      |
| `date_ctrl`                  | Date du contrôle (filtrage période)                                      |
| `num_depart`                 | Code département (filtrage département)                                  |
| `insee_comm`                 | Code INSEE commune (5 caractères)                                        |
| `nom_commun`                 | Nom de la commune                                                        |
| `nom_dossie` / `nom_dossier` | Nom du dossier (ex. « agrainage » pour filtre agrainage)                 |
| `type_actio` / `type_action` | Type d’action (ex. « chasse », « police sanitaire de la faune sauvage ») |
| `theme`                      | Thème du contrôle (ex. « Chasse », « Police de la chasse »)              |
| `domaine`                    | Domaine                                                                  |
| `entit_ctrl`                 | Entité de contrôle                                                       |
| `type_usage`                 | Type d’usage                                                             |
| `fc_type`                    | Type FC                                                                  |
| `resultat`                   | Résultat : Conforme, Infraction, Manquement                              |
| `code_pej`, `code_pa`        | Lien vers procédure judiciaire / administrative                          |
| `natinf_pej`                 | Code(s) NATINF associé(s) (PEJ)                                          |
| `x`, `y`                     | Coordonnées WGS84 (après suppression de la colonne geometry)             |


**Alias gérés dans le loader :** `nom_dossier` → `nom_dossie`, `type_action` → `type_actio`.

### 2.2 PEJ (ODS)


| Champ                             | Rôle / règle                                                                                                                                                           |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DC_ID`                           | Identifiant dossier de contrôle                                                                                                                                        |
| `DATE_CONSTATATION`               | Date de constatation                                                                                                                                                   |
| `DATE_OUVERTURE_PROCEDURE`        | Date d’ouverture de la procédure                                                                                                                                       |
| `RECAP_DATE_INIT_PJ`              | Date d’initialisation PJ                                                                                                                                               |
| `DATE_REF`                        | Colonne dérivée : DATE_CONSTATATION, puis DATE_OUVERTURE_PROCEDURE, puis RECAP_DATE_INIT_PJ (affichage / tri ; **filtrage période = `RECAP_DATE_INIT_PJ` uniquement**) |
| `NATINF_PEJ` / `NATINF`           | Code(s) NATINF (ex. 27742, 25001 pour agrainage)                                                                                                                       |
| `DOMAINE`, `THEME`, `TYPE_ACTION` | Classification (filtre « chasse » sur THEME / TYPE_ACTION)                                                                                                             |
| `DUREE_PEJ`                       | Durée de la procédure (en jours)                                                                                                                                       |
| `CLOTUR_PEJ`                      | Clôture de la procédure                                                                                                                                                |
| `SUITE`                           | Suite donnée à la procédure                                                                                                                                            |
| `ENTITE_ORIGINE_PROCEDURE`        | Entité d’origine (ex. SD21)                                                                                                                                            |


**Période et volume PEJ :** le décompte et le filtre de période s’appuient **uniquement** sur le classeur ODS (champ `**RECAP_DATE_INIT_PJ`**). Toutes les PEJ ne sont pas liées à un contrôle. Les coordonnées ne figurent pas dans l’ODS : elles sont récupérées par jointure `DC_ID` = `dossier` sur la couche `**sources/sig/points_infractions_pj/localisation_infrac_FAITS_*`** (entité `SD{dept}`), pour les analyses spatiales (ex. restriction PNF).

### 2.3 PA (ODS)


| Champ                           | Rôle / règle                                      |
| ------------------------------- | ------------------------------------------------- |
| `DC_ID`                         | Identifiant dossier de contrôle                   |
| `DATE_CONTROLE`, `DATE_DOSSIER` | Dates de référence                                |
| `DATE_REF`                      | Colonne dérivée : DATE_CONTROLE puis DATE_DOSSIER |
| `THEME`, `TYPE_ACTION`          | Classification (filtre « chasse » comme pour PEJ) |
| `ENTITE_ORIGINE_PROCEDURE`      | Entité d’origine                                  |


### 2.4 PVe (CSV / ODS)


| Champ                            | Rôle / règle                           |
| -------------------------------- | -------------------------------------- |
| `INF-ID`                         | Identifiant PVe                        |
| `INF-DATE-INTG`                  | Date d’intégration (filtrage période)  |
| `INF-NATINF`                     | Code NATINF (ex. 27742 pour agrainage) |
| `INF-TYP-INF-STAT-LIB`           | Libellé type d’infraction              |
| `INF-INSEE`                      | Code INSEE commune (5 chiffres, zfill) |
| `INF-DEPART` / `INF-DEPARTEMENT` | Code département                       |
| `INF-CP`                         | Code postal                            |
| `inf_gps_lat`, `inf_gps_long`    | Coordonnées GPS si disponibles         |


### 2.5 Points infractions PJ (GPKG)


| Champ                         | Rôle / règle                              |
| ----------------------------- | ----------------------------------------- |
| `dossier`                     | Identifiant dossier (lien avec DC_ID PEJ) |
| `natinf`                      | Code NATINF                               |
| `entite`                      | Entité (ex. SD21)                         |
| `x_infrac`, `y_infrac`        | Coordonnées du fait                       |
| `commune_fait` / `commune_fa` | Commune du fait                           |
| `geometry`                    | Géométrie point                           |


### 2.5bis Localisation PEJ / PA pour critères géographiques (ex. PNF) — cadrage Phase 0

Les classeurs ODS de suivi (`suivi_procedure_enq_judiciaire_*.ods`, `suivi_procedure_administrative_*.ods`) servent au **contenu métier** (dates, NATINF, thème, entité, etc.) mais **ne portent pas** une localisation exploitable pour répondre seuls à « dans le PNF ou non ». La suite distingue **PEJ** et **PA**.

#### PEJ — localisation du fait

**Source de référence** : `sources/sig/points_infractions_pj/` (`localisation_infrac_FAITS_*.gpkg` ou `.shp`, voir `get_points_infrac_pj_path` / `load_points_infrac_pj`).

**Règle** :

1. **INSEE direct** sur la couche (ou équivalent normalisé), puis appartenance au PNF via les codes issus de `**load_pnf`** (shapefile `ref/sig/communes_pnf/communes_pnf.shp` ou `communes_PNF.csv`).
2. **Sinon** : **jointure** `dossier` (GPKG) ↔ `DC_ID` (ODS PEJ), comme dans `load_pj_with_geometry` (extensions possibles selon le chantier en cours).

#### PA — localisation alignée sur les contrôles « Manquement »

**Ne pas** utiliser `points_infractions_pj` pour les PA. Il suffit de la source **points de contrôle OSCEAN** (`sources/sig/points_de_ctrl_OSCEAN_*` / chargement via `load_point_ctrl`).

**Règle métier** : le **nombre de PA** et leurs **localisations** à faire correspondre aux analyses spatiales sont ceux des **contrôles dont le résultat est « Manquement »** : une ligne de contrôle = une localisation (`insee_comm`, etc.), filtrée sur `resultat == "Manquement"` (libellé exact tel que dans les données). L’ODS PA reste utile pour le détail procédural ailleurs dans les bilans, mais pour le **périmètre géographique** des PA dans le PNF, la référence est ce sous-ensemble de points de contrôle.

### 2.6 Référentiels

- **Périmètre PNF (communes)** : en priorité le shapefile `**ref/sig/communes_pnf/communes_pnf.shp`** (polygones des communes du parc ; colonne INSEE attendue : `INSEE_COM`, `CODE_INSEE`, `insee_comm`, etc.). À défaut, fichier `**communes_PNF.csv`** dans `ref/` ou `sources/` (`NOM`, `CODE_INSEE`, `Adhesion`, `Coeur`, `RI`, …). Le chargeur `load_pnf` dans `scripts/common/loaders.py` unifie ces sources.
- **Périmètres détaillés PNF (cœur / aire d'adhésion)** : couches `**ref/sig/PNF/coeur_pnforets/`** et `**ref/sig/PNF/aoa_2021_pnforets/`** (noms de fichiers ci-dessus). Elles servent à classer les points (colonne `**pnf_zone_sig`** : `Coeur_PNF`, `Aire_adhesion_PNF`, `Hors_perimetres_sig`) via `**enrich_with_pnforet_sig_zones**` lorsque les coordonnées sont disponibles. Jeu de référence public : [Ternum BFC — Périmètres détaillés du parc national de forêts](https://trouver.ternum-bfc.fr/dataset/perimetres-detailles-du-parc-national-de-forets).
- **tub_communes.csv** : `INSEE_COM`, `NOM_COM`, … (séparateur `;`, encodage latin-1) — communes zone TUB.
- **ref/sig/communes-france-2025.csv** : `code_insee`, `latitude_centre`, `longitude_centre` — centroïdes pour jointure/localisation PVe.
- **liste_natinf.csv** : `Numéro NATINF`, `Nature de l'infraction`, … — nomenclature pour libellés dans les analyses par NATINF.
- **ref_themes_ctrl.csv** : `id`, `label`, `ordre` (séparateur `;`, UTF-8) — liste officielle des thèmes des bilans thématiques (agrainage, chasse, piégeage, types d'usagers, procédures PA/PEJ/PVe). Utilisé par les scripts de bilans et le générateur de cartes.

---

## 3. Règles des bilans existants

### 3.1 Bilan chasse

- **Périmètre :** département 21, période 01/09 – 01/03 (saison de chasse).
- **Contrôles :** `theme` ou `type_actio` contient « chasse » ou « police de la chasse » (voir `utils.est_chasse_thematique`).
- **PEJ / PA :** même filtre sur THEME / TYPE_ACTION ; périmètre département : DC_ID dans contrôles chasse ou ENTITE_ORIGINE_PROCEDURE = SD21 ; déduplication par DC_ID.
- **Sorties :** résultats par contrôle, indicateurs par commune, PNF / hors PNF, PEJ/PA par thème, cartographie.

### 3.2 Bilan agrainage

- **Périmètre :** département 21, période 01/01 – 05/02 (exemple).
- **Contrôles :** `nom_dossie` contient « agrain » OU `type_actio` contient « police sanitaire de la faune sauvage » avec exclusion « tuberculose », « grippe », « piégeage ».
- **PVe :** NATINF 27742.
- **PEJ :** NATINF 27742 ou 25001 ; périmètre SD21 + déduplication par DC_ID ; durée moyenne PEJ.
- **Zones :** Département, Zone TUB, PNF (synthèse croisée contrôles / PVe / PEJ).
- **Sorties :** CSV par zone, résumés, PDF, cartes.

---

## 4. Inventaire des données (phase 0)

Le script `scripts/inventaire/inventaire_donnees.py` produit les **valeurs distinctes et effectifs** des champs clés (theme, type_actio, domaine, nom_dossie, NATINF, etc.) sans modifier les bilans. Sortie : `out/inventaire/` (CSV + résumé texte). Utiliser ces résultats pour valider les thèmes et NATINF avant d’ajouter de nouveaux objets d’analyse.

---

## 6. Modules d’analyse (inventaire, NATINF, temporel, procédures)

### 6.1 Inventaire (phase 0)

- **Script :** `scripts/inventaire/inventaire_donnees.py`
- **Rôle :** Lecture seule des sources ; export des **valeurs distinctes et effectifs** des champs clés pour valider thèmes et NATINF avant de coder de nouveaux bilans.
- **Périmètre :** Points de contrôle (optionnel : `--dept`, `--date-deb`, `--date-fin`), PEJ, PA, PVe, points infractions PJ (tous sans filtre métier).
- **Champs inventoriés :**  
  - Points de contrôle : `theme`, `type_actio`, `domaine`, `nom_dossie`, `entit_ctrl`, `type_usage`, `fc_type`, `resultat`.  
  - PEJ : `THEME`, `TYPE_ACTION`, `DOMAINE`, `NATINF_PEJ`, `CLOTUR_PEJ`, `SUITE`.  
  - PA : `THEME`, `TYPE_ACTION`, `ENTITE_ORIGINE_PROCEDURE`.  
  - PVe : `INF-NATINF`, `INF-TYP-INF-STAT-LIB`.  
  - Points PJ : `natinf`, `entite`.
- **Sorties :** `out/inventaire/*.csv` (un CSV par source et champ) + `inventaire_resume.txt`. Jointure optionnelle avec `ref/liste_natinf.csv` pour libeller les NATINF.

### 6.2 Bilan par NATINF

- **Script :** `scripts/bilan_natinf/analyse_natinf.py`
- **Rôle :** Analyses **PVe et PEJ par code NATINF** avec libellés issus de `ref/liste_natinf.csv`.
- **Règles :**  
  - PVe : filtrage par `INF-NATINF` (chaîne peut contenir plusieurs codes séparés par `_` ou `,`). Effectifs par NATINF et par zone (Département, Zone TUB, PNF) via `INF-INSEE` et référentiels TUB/PNF.  
  - PEJ : filtrage par `NATINF_PEJ` (même logique multi-codes). Effectifs, **durée moyenne DUREE_PEJ**, répartition par **CLOTUR_PEJ**, par **SUITE**, par THEME/DOMAINE.
- **Périmètre optionnel :** `--dept` (PVe), `--date-deb`, `--date-fin`, `--natinf` (liste de codes ; si absent, tous les NATINF présents dans les données).
- **Sorties :** `out/bilan_natinf/` : `pve_par_natinf.csv`, `pve_par_natinf_zone.csv`, `pej_par_natinf.csv`, `pej_par_natinf_clotur.csv`, `pej_par_natinf_suite.csv`, `pej_par_natinf_theme.csv`.

### 6.3 Bilan temporel

- **Script :** `scripts/bilan_temporel/analyse_temporelle.py`
- **Rôle :** **Finesse temporelle** : évolution des effectifs par **mois** et par **trimestre** (colonnes dérivées à partir des dates).
- **Règles :**  
  - Points de contrôle : colonne `date_ctrl` → période au format `YYYY-MM`.  
  - PVe : `INF-DATE-INTG` → période.  
  - PEJ : `DATE_REF` → période.  
  Agrégation : effectifs par période (mois ou trimestre).
- **Périmètre optionnel :** `--dept`, `--date-deb`, `--date-fin`.
- **Sorties :** `out/bilan_temporel/` : `controles_par_mois.csv`, `controles_par_trimestre.csv`, `pve_par_mois.csv`, `pve_par_trimestre.csv`, `pej_par_mois.csv`, `pej_par_trimestre.csv`.

### 6.4 Bilan procédures PEJ

- **Script :** `scripts/bilan_procedures/analyse_procedures.py`
- **Rôle :** Indicateurs **globaux** sur les procédures PEJ : **DUREE_PEJ** (moyenne, médiane, quantiles P25/P75), répartition par **CLOTUR_PEJ** et **SUITE**, et par **THEME** / **DOMAINE**.
- **Règles :** Pas de filtre thématique ; tous les PEJ de la période. Durée en jours (colonne numérique `DUREE_PEJ`). Complète les sorties par NATINF (bilan_natinf) par une vue agrégée.
- **Périmètre optionnel :** `--date-deb`, `--date-fin`.
- **Sorties :** `out/bilan_procedures/` : `pej_duree_resume.csv`, `pej_clotur_global.csv`, `pej_suite_global.csv`, `pej_duree_par_theme.csv`, `pej_duree_par_domaine.csv`.

### 6.5 Parties communes réutilisables

- **Loaders :** `load_tub_pnf_codes(root)` dans `scripts/common/loaders.py` retourne `(tub_codes, pnf_codes)` pour les agrégations par zone (Département, TUB, PNF) sans dupliquer le chargement des référentiels.
- **Utils :** `_zone_summary` et `_zone_count` dans `scripts/common/utils.py` pour tableaux par zone (contrôles avec résultat, ou simple comptage PVe/PEJ).

---

## 7. Référence des loaders


| Fonction                                                                  | Fichier                     | Rôle                                                                                             |
| ------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------ |
| `load_point_ctrl`                                                         | `scripts/common/loaders.py` | Charge les points de contrôle (optionnel : dept, date_deb, date_fin)                             |
| `load_pej`                                                                | id.                         | Charge le dernier ODS PEJ (optionnel : date_deb, date_fin)                                       |
| `load_pa`                                                                 | id.                         | Charge le dernier ODS PA (optionnel : date_deb, date_fin)                                        |
| `load_pve`                                                                | id.                         | Charge le dernier Stats_PVe_OFB (optionnel : dept_code, date_deb, date_fin)                      |
| `load_pnf`, `load_tub`                                                    | id.                         | Référentiels PNF (communes / INSEE) et TUB                                                       |
| `load_pnf_coeur_gdf`, `load_pnf_aoa_gdf`, `enrich_with_pnforet_sig_zones` | id.                         | Périmètres SIG cœur et aire d'adhésion ; classification des points (`pnf_zone_sig`)              |
| `load_tub_pnf_codes`                                                      | id.                         | Retourne `(tub_codes, pnf_codes)` pour agrégations par zone                                      |
| `load_communes_centroides`                                                | id.                         | Centroïdes communes pour jointure PVe                                                            |
| `get_points_infrac_pj_path`, `load_points_infrac_pj`                      | id.                         | Chemin et chargement points PJ (filtre NATINF + entité)                                          |
| `load_pj_with_geometry`                                                   | id.                         | PEJ + géométrie des faits (jointure avec points PJ)                                              |
| `load_ref_themes_ctrl`                                                    | id.                         | Référentiel des thèmes des contrôles (ref/ref_themes_ctrl.csv) pour bilans thématiques et cartes |
