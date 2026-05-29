# Référentiels actifs (`ref/programme/`)

Contenu lu par le code (`bilans.common.chargeurs_donnees`, moteur de bilans, cartographie, PDF).

## `tables_reference/`

| Fichier | Rôle |
|---------|------|
| `types_usagers.csv` | Mapping des types d’usagers |
| `ref_themes_ctrl.csv` | Thèmes des contrôles (bilans + cartes) |
| `tub_communes.csv` | Communes zone TUB |
| `communes_PNF.csv` | Communes PNF (repli tabulaire) |
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

Images charte graphique (extraites du modèle Word `word/OFB_RAPPORT SIMPLE COM EXTERNE WORD 365.dotx`) :

| Fichier | Rôle PDF |
|---------|----------|
| `image5.jpg` | Bandeau Marianne + OFB (page de garde, haut) |
| `image6.jpeg` | Fond décoratif bleu (page de garde, bas) |
| `image3.jpeg` | Filigrane courbes (pages intérieures, bas-droite) |
| `image4.png` / `image4.jpeg` | Variante filigrane (option `footer_deco`, désactivée par défaut) |

Source de vérité visuelle : le `.dotx` dans `modele_ofb/word/`.

Constantes Python (`bilans.common.ofb_charte`) : `IMG_BANNER`, `IMG_TITLE_DECO`, `IMG_FILIGRANE`, `IMG_FILIGRANE_ALT` — pilotées par `config/presentation/pdf_presentation.yaml` → `defaults.charte`.

Chemins résolus via `bilans.chemins_projet.get_ref_programme_dir()`.
