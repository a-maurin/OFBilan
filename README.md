# Bilans de production 2025-2026

Projet de generation des bilans d'activite de controle (SD Cote-d'Or) a partir des donnees OSCEAN et PVe.

## A quoi sert ce depot

Le depot produit deux types de rapports PDF :

- **Bilan global** : vue complete de l'activite du service (controles, resultats, PEJ, PA, PVe).
- **Bilans thematiques** : rapports cibles par profil (ex. `agrainage`, `chasse`, `types_usager`, `procedures_pve`, `pnf`).

Tout passe par un point d'entree unique :

- `scripts/run_bilan.py`

## Utilisation rapide

### Interface Windows (recommande)

- `lancer_bilans.bat` : generation des bilans (global/thematique)
- `generer_cartes.bat` : generation des cartes PNG
- `parametrer_cartes.bat` : parametrage des profils cartographiques

### CLI (direct)

```bat
REM Lister les themes disponibles
python scripts/run_bilan.py --list-themes

REM Bilan global
python scripts/run_bilan.py --mode global --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

REM Bilan thematique (un ou plusieurs profils)
python scripts/run_bilan.py --mode thematique --profil chasse --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21

REM Bilan thematique avec preset de taille graphique
python scripts/run_bilan.py --mode thematique --profil pnf --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21 --preset standard
```

## Objectifs fonctionnels

### 1) Bilan global

- **But** : produire un bilan unique sur une periode et un departement.
- **Entree recommandee** : `scripts/run_bilan.py --mode global`
- **Sorties** : `out/bilan_global/` (PDF + CSV)

### 2) Bilan thematique

- **But** : produire un ou plusieurs bilans cibles via des profils.
- **Entree recommandee** : `scripts/run_bilan.py --mode thematique --profil <id>`
- **Combine** possible : `--combine`
- **Sorties** : `out/bilan_<profil>/` (ou bilan combine)

## Méthodologie des sources (vue non technique)

Le bilan ne constitue pas une base unique « toute mélangée » : il part de plusieurs jeux de données distincts, qui répondent chacun à une question différente, puis les met en cohérence sur un même cadre (département et période choisis).

Les **points de contrôle OSCEAN** sont la colonne vertébrale lorsqu’ils sont utilisés : ils décrivent l’activité de contrôle sur le terrain (où, quand, sur quel thème ou domaine, avec quel résultat, parfois avec un lien vers des suites administratives ou judiciaires lorsque l’information est présente dans le point). C’est la référence pour parler de **contrôles** et de **résultats de contrôle** au sens « point de contrôle ».

Les **procédures judiciaires (PEJ)** et les **procédures administratives (PA)** sont lues comme des **suites possibles** de l’activité, mais pas seulement comme la suite d’un contrôle : une **infraction peut faire suite à un contrôle** ou être **constatée en dehors d’un contrôle** (autre saisine, enquête, etc.). Pour le volet judiciaire, le bilan s’appuie en pratique sur **deux entrées complémentaires** : le **classeur de suivi des PEJ** (`sources/suivi_procedure_enq_judiciaire_YYYYMMDD.ods`, par exemple `sources/suivi_procedure_enq_judiciaire_20260206.ods`), qui porte le contenu procédural et le filtrage temporel, et la **couche de localisation des faits PJ** (`sources/sig/points_infractions_pj/localisation_infrac_FAITS_YYYYMMDD` en GeoPackage ou shapefile, par exemple les fichiers `localisation_infrac_FAITS_20260403.shp` / `.shx` / `.dbf`, etc.), qui apporte la **géolocalisation des faits** lorsque le classeur ne suffit pas seul. Ces sources **complètent** les points de contrôle sans les remplacer : elles décrivent ce qui existe côté dossiers PEJ/PA et côté faits localisés, avec des **recoupements possibles** lorsque les données le permettent (par exemple repères communs entre un point OSCEAN, un dossier PEJ et un fait géolocalisé).

Les **infractions relevées par procès-verbal électronique (PVe)** sont comprises comme une **autre voie de constat des infractions**, issue d’un circuit différent d’OSCEAN et distincte du couple PEJ / faits PJ ci-dessus. Elles sont donc traitées en **source parallèle** : utiles pour le volume et le profil des infractions « PVe », sans être confondues avec le seul décompte des contrôles OSCEAN ni avec le périmètre PEJ + localisation des faits. Le bilan peut les présenter à côté des contrôles pour donner une vision plus large de l’activité répressive ou de constat, en rappelant qu’il ne s’agit pas du même périmètre métier.

Les **référentiels et fonds cartographiques** (communes, zones d’intérêt, libellés d’infractions, etc.) ne sont pas des « sources d’événements » au même titre : ils servent à interpréter ou situer les lignes des sources ci-dessus (libellés lisibles, regroupements par commune ou par zone lorsque l’option est activée), sans créer de nouveaux faits.

Le **profil du bilan** (fichier de paramètres) précise quelles sources sont activées ou non pour ce rapport et comment le périmètre métier est restreint (par exemple un thème ou des mots-clés). Ainsi, pour un bilan thématique, on ne « réduit » pas arbitrairement la base : on filtre les points OSCEAN selon les règles du profil, puis on rapproche PEJ, PA et éventuellement PVe sur ce même cadre temporel et territorial, pour que les chiffres et graphiques du PDF restent comparables dans le temps et dans l’espace, tout en respectant la sémantique de chaque source (contrôle d’un côté, procédures et faits PJ d’un autre, PVe d’un troisième). Détail des jointures et des champs : `ref/README_sources.md`, `scripts/common/loaders.py`.

## Architecture (vue simple)

- `scripts/run_bilan.py` : orchestrateur principal
- `scripts/bilan_global/analyse_global.py` : moteur global
- `scripts/bilan_thematique/bilan_thematique_engine.py` : moteur thematique unifie
- `scripts/bilan_thematique/run_bilan_thematique.py` : lanceur thematique direct
- `config/profils_bilan/` et `ref/profils_bilan/` : profils YAML de pilotage
- `scripts/common/` : utilitaires partages (PDF, chartes, loaders, etc.)

## Profils et options

Chaque profil YAML definit :

- le filtre metier,
- les sources actives (`point_ctrl`, `pej`, `pa`, `pve`),
- les options activables (`pnf`, `tub`, `cartes`, `synthese_croisee`, etc.).

Surcharge possible en CLI :

```bat
python scripts/run_bilan.py --mode thematique --profil chasse --with-pnf --no-tub
python scripts/bilan_thematique/run_bilan_thematique.py --profil agrainage --option synthese_croisee=true
```

## Taille des graphiques PDF

Configuration centralisee via :

- `ref/charts_config.yaml`

Presets disponibles :

- `compact`
- `standard`
- `large`

Utilisation :

```bat
python scripts/run_bilan.py --mode thematique --profil pnf --preset large
```

## Cartographie

Ordre recommande :

1. Generer les cartes (`generer_cartes.bat` ou script associe)
2. Generer les bilans (qui integrent ensuite les cartes disponibles)

Les cartes attendues sont stockees dans `out/generateur_de_cartes/` sous forme `carte_<profil>.png`.

## Prerequis

- Python 3.10+
- dependances Python du projet
- QGIS (uniquement pour la generation de cartes)

## Licence et contact

- Licence : voir `LICENSE`
- Auteur : Aguirre Maurin
- Service : OFB, SD Cote-d'Or
