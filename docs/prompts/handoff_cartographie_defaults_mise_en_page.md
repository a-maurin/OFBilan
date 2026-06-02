# Handoff agent — Cartographie QGIS : defaults mise en page (réf. agrainage)

Copier-coller le bloc **Prompt agent** ci-dessous dans une nouvelle session Cursor.

---

## Prompt agent

```text
Contexte projet — Bilans_production
===================================

Repo : Bilans_production
Langue réponses : français, concis, technique.
CLI officielle : python -m bilans --profil <id> [--cartes] [--no-cartes] [--carte <map_id>|all]
Prérequis : Python ≥ 3.10, pip install -e .
Ne pas versionner : data/out/, __pycache__/, .pytest_cache/, PNG debug à la racine.

Règles projet obligatoires (.cursor/rules/) :
- Avant toute évolution comportementale carto/PDF : demander si périmètre **profil unique** ou **tous les profils**.
- Non-régression : tests automatisés ou protocole multi-profils reproductible.
- QGIS optionnel : le bilan doit toujours se terminer même si export carto échoue.
- Patch minimal, pas de refactor hors scope.


Objectif de cette session
=========================

Paramétrer **par défaut** les éléments généraux des cartes QGIS exportées :
- format page (ratio 1:1, DPI, PNG/JPEG),
- structure de mise en page alignée sur le **layout agrainage de référence**,
- tailles/positions des composants (carte, légende, titre, sous-titre, échelle, logos OFB),
- harmonisation des autres layouts du projet QGIS sur ce gabarit.

Référence visuelle métier : section cartographie du PDF agrainage
(data/out/bilan_agrainage/bilan_agrainage_Cote_dOr.pdf — section V, si disponible localement).

Référence technique layout QGIS :
- Projet : ref/programme/sig/bilans_carte.qgz
- Layout pilote : "Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or"


État du chantier carto (déjà livré — NE PAS refaire)
====================================================

Architecture validée (Option 2 : socle commun + YAML, déploiement incrémental, **tous les profils**) :

1) **Symbologie QGIS source de vérité**
   - symbology_source: qgis (défaut global dans profils_cartes.yaml)
   - apply_layer_symbology() n'est appelé que si override explicite symbology_source: yaml
   - Fichiers : src/bilans/cartographie/layer_resolver.py, production_cartographique.py

2) **Résolution dynamique des couches**
   - layer_role (point_controles, pej, pochoir, zone_*, …)
   - Renommage couche datée (ex. point_ctrl_20260205 → point_ctrl_20260505) géré automatiquement
   - Tests : tests/unit/test_layer_resolver.py

3) **Mode layout-driven**
   - layers_from_layout: true (défaut global)
   - Découverte couches : LayerSet carte → légende layout → layout_layer_group → visibles métier
   - YAML layers = surcharges filtres/légende uniquement
   - Fichiers : src/bilans/cartographie/layout_layers.py, tests/unit/test_layout_layers.py

4) **Chaîne bilan → cartes → PDF**
   - cartographie_config.py : modes catalog | synthese | dedie | thematique_ref | manuel | none
   - carte_helper.py : ensure_maps_for_profiles, resolve_map_profiles_for_batch
   - global.yaml : catalogue 4 vues (Contrôles / Types usagers / Procédures / Domaines)
   - Docs : docs/usage/cartes_et_bilans.md, docs/usage/filtrage_bilans_et_cartes.md

5) **Tests**
   - Suite complète : python -m pytest -q → 253 passed (dernier run connu)
   - Tests carto : test_cartographie_config.py, test_layer_resolver.py, test_layout_layers.py, test_carte_helper_maps.py


Fichiers source de vérité (lire en priorité)
============================================

Cartographie QGIS :
@ref/programme/sig/bilans_carte.qgz
@src/bilans/cartographie/production_cartographique.py
@src/bilans/cartographie/config_cartes_model.py
@src/bilans/cartographie/config_cartes.py
@src/bilans/cartographie/param/profils_cartes.yaml
@src/bilans/cartographie/param/symbologies.yaml
@src/bilans/cartographie/layer_resolver.py
@src/bilans/cartographie/layout_layers.py

Liaison bilan ↔ cartes :
@src/bilans/common/cartographie_config.py
@src/bilans/common/carte_helper.py
@src/bilans/engine/execution_lots_profils.py
@src/bilans/engine/generation_pdf_profil.py

Profils bilan (capabilities, catalogue cartes) :
@config/profils_bilan/global.yaml
@config/profils_bilan/agrainage.yaml

Assets logos :
@ref/programme/modele_ofb/bloc-marque-RF-OFB_horizontal.jpg
@ref/modele_ofb/word/media/image5.jpg (bandeau haut — chemin utilisé par _get_logo_bandeau_path)


État actuel de la mise en page (à auditer en début de session)
===============================================================

OutputConfig (config_cartes_model.py / config_cartes.py) :
- format: png, dpi: 300, page_size: A4, orientation: landscape

Constantes **hardcodées** dans production_cartographique.py (candidats à externaliser YAML) :
- LOGO_OFB_BAS_DROITE_* (taille, fractions page, marges, id layout logo_ofb_bas_droite)
- Bandeau haut _ensure_logo_bandeau : id bandeau_logos_ofb, hauteur min(25mm, 15% page)
- layout_title_item_id / layout_subtitle_item_id : défaut titre_principal / sous_titre

Comportement export_layout() aujourd'hui :
1. Charge layout par prof.layout_name
2. Met à jour titre/sous-titre (QgsLayoutItemLabel)
3. Applique legend_labels_map si fourni
4. Injecte bandeau logos haut + logo OFB bas droite (PyQGIS, pas dans .qgz)
5. exportToImage(dpi depuis CONFIG.output.dpi)

Layouts présents dans bilans_carte.qgz (9) :
- "Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or"  ← RÉFÉRENCE
- "Bilan – Agrainage – SD21"
- "Bilan – Chasse – SD21"
- "Bilan – Contrôles sécheresse – SD21"
- "Bilan – Professions agricoles – SD21"
- "Professions agricoles - bilan 2025"
- "Synthese_activité"
- "Activité PNF - Bilan"
- "carte_brochure"

Profils carto YAML — alignement layout partiel (dettes connues) :
- agrainage → layout référence + layout_layer_group: agrainage
- chasse → "Bilan – Chasse – SD21" + layout_layer_group: Contrôles
- synthese_activite_PA_PJ* → "Synthese_activité"
- global, piegeage, procedures_pve, global_* → encore sur layout agrainage (à harmoniser)

Limitation QGIS actuelle :
- LayerSet des cartes souvent **vide** dans le .qgz → découverte via groupe/légende/visibilité.
- Recommandation utilisateur : configurer LayerSet par layout dans QGIS pour fiabiliser layout-driven.


Question obligatoire (AVANT code)
=================================

Cette évolution de mise en page doit-elle s'appliquer :
A) uniquement au layout/profil agrainage (pilote), puis extension,
B) à **tous les layouts** du .qgz d'un coup,
C) à tous les profils carto via defaults YAML (application programmatic à l'export, sans modifier le .qgz) ?

Proposer l'option recommandée avec justification, puis attendre validation si ambigu.


Étape 1 — Audit (PAS DE CODE)
===============================

1) Extraire du layout agrainage de référence (XML .qgs ou PyQGIS si dispo) :
   - taille page (mm), orientation
   - items : carte (65639), légende (65642), labels, échelle, flèche nord, images
   - pour chaque item : id, position (mm), taille (mm), zValue
2) Comparer avec 2–3 autres layouts (chasse, Synthese_activité, carte_brochure).
3) Lister les écarts structurels (pas seulement titres différents).
4) Inventorier ce qui est déjà injecté par Python à l'export vs stocké dans le .qgz.
5) Produire un tableau :
   | composant | réf. agrainage | autre layout | source (qgz/python) | action proposée |

STOP — présenter le tableau + plan en 5–8 points, attendre validation.


Étape 2 — Design cible (après validation)
==========================================

Objectif design :
- Un fichier de config central (proposition) :
  config/cartographie/layout_defaults.yaml
  ou src/bilans/cartographie/param/layout_defaults.yaml
  avec sections : page, map_item, legend, title, subtitle, scalebar, logos, export

- Modèle Python étendu (config_cartes_model.py) :
  LayoutDefaultsConfig / LayoutPresentationConfig
  chargé par production_cartographique.py

- Fonction apply_layout_defaults(layout, prof, defaults) appelée dans export_layout()
  AVANT export image :
  - repositionner/redimensionner items par id ou type
  - ne pas écraser symbologies de couches
  - conserver injection logos si absents du .qgz

- Stratégie multi-layouts (selon périmètre validé) :
  - either : template layout agrainage cloné / synchronisé
  - or : apply programmatic defaults sur chaque layout à l'export
  - or : script one-shot QGIS pour normaliser le .qgz (documenter, hors pipeline runtime)

Rétrocompatibilité :
- Profils sans section layout_defaults → comportement actuel
- Overrides par profil dans profils_cartes.yaml (layout_defaults_ref ou bloc inline)


Étape 3 — Implémentation (lots courts)
======================================

Lot 1 — Config + modèle
- layout_defaults.yaml calibré sur agrainage
- chargement + tests unitaires parsing (sans PyQGIS)

Lot 2 — Application export
- apply_layout_defaults() dans production_cartographique.py
- brancher export_layout()
- logs explicites si item layout introuvable (non bloquant)

Lot 3 — Harmonisation profils / layouts
- aligner layout_name des profils carto restants
- option layout_template: agrainage pour nouveaux layouts
- doc courte docs/usage/README_Production_cartes.md

Lot 4 — Non-régression
- tests unitaires layout defaults
- smoke : python -m bilans --profil agrainage --cartes --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21
- comparaison visuelle PNG vs export manuel QGIS layout agrainage


Contraintes strictes
====================

- Ne pas modifier symbologies de couches (RuleRenderer QGIS) — hors scope.
- Ne pas modifier calculs agrégation bilan / filtres métier pandas.
- Ne pas casser layers_from_layout ni symbology_source: qgis.
- Constantes logos : migrer vers YAML sans changer le rendu agrainage (tolerance pixel près).
- QGIS absent → pas d'exception bloquante sur le pipeline bilan.
- Pas de chemins absolus machine.


Vérification obligatoire avant « terminé »
==========================================

1) python -m pytest -q
2) tests ciblés :
   pytest tests/unit/test_layout_layers.py tests/unit/test_layer_resolver.py tests/unit/test_cartographie_config.py -q
3) Si QGIS dispo :
   python -m bilans --profil agrainage --cartes --dept-code 21
   python -m bilans --profil chasse --cartes --dept-code 21
4) Checklist :
   - PNG dans data/out/generateur_de_cartes/
   - structure visuelle alignée agrainage (titres, légende, logos, échelle)
   - PDF section carto inchangée fonctionnellement (chemins PNG OK)


Hors scope (ne pas faire sauf demande explicite)
================================================

- Commit / push git
- Remplir LayerSet dans QGIS manuellement (documenter seulement)
- Refonte complète profils_cartes.yaml
- Migration symbologies.yaml vers RuleRenderer
- Graphiques PDF (config/presentation/pdf_presentation.yaml)


Livrables attendus
==================

1) Fichier(s) config layout defaults
2) Patch production_cartographique.py + config_cartes_model.py (+ loader)
3) Tests unitaires
4) Mise à jour doc usage cartes (section « mise en page »)
5) Tableau avant/après des layouts harmonisés
6) Risques résiduels (5 lignes max)
```
