## Organisation des données SIG pour la production des bilans

- **Audit des conventions de nommage (ref/, sources/, sources/sig)** :
  - **ref/** : référentiels stables — `communes_PNF.csv`, `tub_communes.csv`, `liste_natinf.csv`, `sig/communes-france-2025.csv`, `sig/communes_21/`, etc.
  - **sources/** : extractions opérationnelles — `Stats_PVe_OFB au DD.MM.YYYY.csv` ou `.ods` ; `suivi_procedure_judiciaire_YYYYMMDD.ods` ; `suivi_procedure_administrative_YYYYMMDD.ods`.
  - **sources/sig/** : couches SIG dérivées — `point_ctrl_YYYYMMDD_wgs84.gpkg` ; `points_infractions_pj/localisation_infrac_FAITS_YYYYMMDD.gpkg` ; `pve_agrainage_points_centroides.gpkg` (généré par le bilan agrainage). Les scripts prennent automatiquement le fichier le plus récent par préfixe/année.

- **Projet QGIS principal** :
  - Fichier de projet attendu : `Bilans_production/ref/sig/sd21_tout.qgz`.
  - Ce projet doit contenir toutes les couches nécessaires aux cartes et rapports
    (infractions PVe, PJ, points de contrôle agrainage/chasse, communes, etc.).

- **Sources des données opérationnelles (scripts et cartes)** :
  - **Contrôles** : GPKG `point_ctrl_YYYYMMDD_wgs84.gpkg` dans **`sources/sig`**. Les scripts sélectionnent automatiquement le fichier le plus récent par année.
  - **Points PJ** : GPKG `localisation_infrac_FAITS_YYYYMMDD.gpkg` dans **`sources/sig/points_infractions_pj`** (ou `sources/points_infractions_pj`). Le script charge le fichier avec la date la plus récente.
  - **PVe (points)** : généré par le bilan agrainage dans **`sources/sig/pve_agrainage_points_centroides.gpkg`** à partir de Stats_PVe_OFB + centroïdes.
  - **Référentiels** (PNF, TUB, communes, centroïdes) : fichiers dans **`ref/`** ou **`ref/sig`** (ex. `ref/communes_PNF.csv`, `ref/tub_communes.csv`, `ref/sig/communes-france-2025.csv`). Les loaders cherchent d’abord dans `ref/` puis dans `sources/` pour PNF et TUB.

- **Couches clés et champs utilisés par les filtres** :
  - PVe (agrainage illicite) :
    - Champs attendus : `INF-NATINF`, `INF-DEPART`, `INF-DATE-I`.
  - Procédures judiciaires (PJ) :
    - Champs attendus : `entite`, `natinf`, `date_saisine`.
  - Points de contrôle agrainage :
    - Champs attendus : `nom_dossier` (ou `nom_dossie`), `date_ctrl`, `num_depart`, `resultat`.
  - Points de contrôle chasse :
    - Champs attendus : `date_ctrl`, `num_depart`, `resultat` (+ `theme` si disponible).

- **Lien avec la configuration Python** :
  - Le chemin du projet QGIS est défini dans `config_cartes_model.GlobalConfig.project_qgis_path`.
  - Il peut être surchargé par la variable d’environnement `CARTO_PROJECT_QGIS_PATH`.
  - Les couches effectivement utilisées et leur symbologie sont décrites dans `scripts/generateur_de_cartes/config_cartes.py`.

