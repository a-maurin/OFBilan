# Kit `ref/` — installation et rôle des fichiers

Ce document accompagne le dossier **`ref/`** transmis hors Git (données confidentielles non versionnées sur GitHub). Il permet de l’intégrer dans une copie locale du dépôt **Bilans_production** cloné depuis GitHub.

---

## 1. Installation

1. Cloner ou mettre à jour le dépôt applicatif :
   ```powershell
   git clone https://github.com/a-maurin/Bilans_production.git
   cd Bilans_production
   ```
2. **Copier-coller** le dossier `ref/` fourni **à la racine** du dépôt (au même niveau que `src/`, `config/`, `data/`).
   - Si un dossier `ref/` existe déjà : **fusionner** en conservant la structure `ref/programme/` décrite ci-dessous.
   - Ne pas recréer `ref/sig/` ou `ref/tables_reference/` à l’ancienne racine : le code attend `ref/programme/...`.
3. Vérifier l’installation :
   ```powershell
   python scripts/verify_ref_layout.py
   ```
   Le message attendu est : `OK — arborescence ref/ conforme.`
4. Les données opérationnelles (exports OSCEAN, PVe, etc.) restent dans **`data/sources/`** (non fournies dans ce kit).

---

## 2. Arborescence attendue

```
ref/
├── README.md
├── programme/                    ← lu par python -m bilans et la cartographie
│   ├── tables_reference/         ← tables CSV métier
│   ├── sig/                      ← fonds cartographiques et référentiels géo
│   └── modele_ofb/                ← images charte graphique OFB (PDF / cartes)
└── (optionnel) hors_programme/   ← non inclus dans le kit standard ; archives SIG / outils
```

Seul **`ref/programme/`** est indispensable pour exécuter les bilans et générer les PDF.

---

## 3. Catalogue des fichiers (`ref/programme/`)

### 3.1 `tables_reference/` — tables CSV

| Fichier | Rôle | Utilisé par |
|---------|------|-------------|
| **types_usagers.csv** | Correspondance entre valeurs sources OSCEAN et catégories de types d’usagers affichées dans les bilans. | Agrégations, PDF, sélection interactive des profils. |
| **ref_themes_ctrl.csv** | Liste officielle des thèmes de contrôle (`id`, libellé, ordre d’affichage). | Catalogue des profils, cartographie, filtres thématiques. |
| **tub_communes.csv** | Codes INSEE des communes en zone **TUB** (agrainage). | Filtres et tableaux « par zone » (Département / TUB / PNF). |
| **communes_PNF.csv** | Communes du périmètre **PNF** ; colonnes `CODE_INSEE`, `Coeur`, `perimetre_parc` pour distinguer cœur de parc et adhésion. | Repli si le shapefile PNF est indisponible ; recalage des zones PNF sur l’INSEE. |
| **liste_natinf.csv** | Référentiel **NATINF** (numéros et libellés d’infractions). | Exports et tableaux PVe / infractions libellés. |

**Format** : séparateur `;` pour la plupart des fichiers ; encodage UTF-8 recommandé (`tub_communes.csv` : souvent Latin-1 côté source métier).

---

### 3.2 `sig/` — données géographiques et projet QGIS

| Fichier / dossier | Rôle | Utilisé par |
|-------------------|------|-------------|
| **sd21_tout.qgz** | Projet **QGIS** principal (couches, styles, mise en page des cartes). | `production_cartographique.py`, génération des PNG intégrés aux bilans. |
| **pochoir_sd21.gpkg** | Couche « pochoir » du département (fond des cartes). | Projet QGIS / profils cartes (`layer_name: pochoir_sd21`). |
| **pve_agrainage_points_centroides.gpkg** | Points centroïdes liés au profil agrainage / chasse. | Projet QGIS / profil carte chasse. |
| **communes_21/communes.shp** (+ `.dbf`, `.shx`, `.prj`, `.cpg`) | Limites communales Côte-d’Or pour **jointure spatiale** (code INSEE, nom). | Enrichissement des contrôles / PVe sans INSEE complet. |
| **communes_21/communes.csv** | Table **INSEE → nom de commune** pour les libellés dans les PDF. | Affichage des noms de communes dans les rapports. |
| **communes_pnf/communes_pnf.shp** (+ sidecars) | Liste géographique des communes **PNF** (prioritaire sur le CSV). | `load_pnf`, filtres zone PNF. |
| **communes_pnf/communes_PNF_centroides.shp** (+ sidecars) | Centroïdes communaux PNF (`long_centr`, `lat_centro`). | Positionnement des PVe sur le centroïde communal PNF. |
| **communes_pnf/communes_pnf.qmd** | Métadonnées QGIS du shapefile (optionnel pour QGIS). | Édition SIG uniquement. |
| **PNF/coeur_pnforets/Coeur_data_gouv_PNForets.shp** (+ sidecars) | Polygone du **cœur** du Parc national de forêts. | Filtre géographique PNF, colonne `pnf_zone_sig`. |
| **PNF/aoa_2021_pnforets/AOA_2021_PNForets.shp** (+ sidecars) | Polygone de l’**aire d’adhésion** PNF (millésime 2021). | Idem. |

**Note shapefile** : chaque `.shp` doit être accompagné de ses fichiers `.dbf`, `.shx`, `.prj` (et `.cpg` si présent) dans le **même dossier**.

**Après copie** : ouvrir `sd21_tout.qgz` dans QGIS une fois et vérifier que les chemins des couches pointent vers `…/ref/programme/sig/…` (réparer si l’ancien poste utilisait un chemin absolu différent).

---

### 3.3 `modele_ofb/` — charte graphique PDF et cartes

| Fichier | Rôle | Utilisé par |
|---------|------|-------------|
| **bloc-marque-RF-OFB_horizontal.jpg** | Logo horizontal République française + OFB. | Légendes et cartes exportées. |
| **word/media/image5.jpg** | Bandeau logos en en-tête des PDF. | `ofb_charte.py`, cartographie. |
| **word/media/image4.png** | Filigrane / fond de page des PDF. | Mise en page PDF. |
| **word/media/image3.jpeg** | Élément décoratif pied de page PDF. | Mise en page PDF. |

---

## 4. Ce qui n’est pas dans le kit standard

- **`data/sources/`** : exports OSCEAN, PVe, procédures, etc. (données d’entrée de production).
- **`ref/hors_programme/`** : archives (autres couches SIG, concordances SNC, modèle Word complet) — utile pour la maintenance, pas requis pour lancer un bilan.
- **`config/`** : déjà versionné sur GitHub (profils YAML, présentation PDF).

---

## 5. Dépannage

| Symptôme | Piste |
|----------|--------|
| `Référentiel PNF introuvable` | Vérifier `communes_pnf.shp` ou `communes_PNF.csv` sous `ref/programme/`. |
| Cartes vides ou erreur QGIS | Réparer les sources de couches dans `sd21_tout.qgz` ; vérifier la présence des `.gpkg`. |
| PDF sans logos | Vérifier les 4 fichiers sous `ref/programme/modele_ofb/`. |
| Dossier `communes_pnf/communes_pnf/` imbriqué | Mauvaise copie : les `.shp` doivent être directement dans `communes_pnf/`, pas dans un sous-dossier du même nom. Relancer `python scripts/verify_ref_layout.py`. |

---

## 6. Contact / mise à jour

Ce kit correspond à la structure attendue par le dépôt **Bilans_production** (branche `main`, moteur unique `python -m bilans`). En cas de mise à jour des référentiels, remplacer l’intégralité de `ref/programme/` ou les fichiers concernés, puis relancer la vérification.

*Document généré pour la distribution hors Git du dossier `ref/` — ne pas publier sur un dépôt public.*
