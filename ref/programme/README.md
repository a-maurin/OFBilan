# Référentiels actifs (`ref/programme/`)

Contenu lu par le code (`bilans.common.chargeurs_donnees`, moteur de bilans, cartographie, PDF).

## `tables_reference/`

| Fichier | Rôle |
|---------|------|
| `types_usagers.csv` | Mapping des types d’usagers |
| `ref_themes_ctrl.csv` | Thèmes des contrôles (bilans + cartes) |
| `tub_communes.csv` | Communes zone TUB |
| `communes_PNF.csv` | Communes PNF (repli tabulaire ; priorité au shapefile) |
| `liste_natinf.csv` | Libellés NATINF |

## `sig/`

| Élément | Rôle |
|---------|------|
| `bilans_carte.qgz` | Projet QGIS (cartographie) |
| `pochoir_sd21.gpkg`, `pve_agrainage_points_centroides.gpkg` | Couches référencées par le projet / la config cartes |
| `communes_pnf/` | Liste et centroïdes PNF |
| `PNF/` | Périmètres cœur et aire d’adhésion |
| `communes_21/` | `communes.shp` + `communes.csv` (INSEE / noms) |

## `modele_ofb/`

Images charte graphique : logo horizontal, bandeau (`image5`), fond et pied de page PDF (`image4`, `image3`).

Chemins résolus via `bilans.chemins_projet.get_ref_programme_dir()`.
