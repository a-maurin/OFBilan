# Pack de Prompts Cursor — Bilans_production

## Bloc commun (a prefixer souvent)

```text
Contexte projet:
- Repo: Bilans_production
- Architecture cible: src/bilans/** + config/profils_bilan/** + tests/**
- CLI officielle: python -m bilans --profil ...
- Interdit: chemins legacy scripts/** sauf si je le demande explicitement

Regles d'execution:
- Lis uniquement les fichiers utiles
- N'ajoute pas de refactor non demande
- Propose un plan en 5-8 points max
- Puis implemente en lots courts
- Apres chaque lot: diff + tests cibles + risques (5 lignes max)
```

## 1) Ameliorations graphiques PDF

### Prompt 1 — Ajustement visuel cible

```text
Objectif: ameliorer la lisibilite des graphiques PDF (titres, legendes, densite visuelle) sans modifier la logique metier.
Contexte: @src/bilans/engine/generation_pdf_profil.py @config/presentation/pdf_presentation.yaml @config/charts/
Contraintes:
- ne pas modifier les calculs de donnees
- conserver le format de sortie actuel
Livrable:
1) patch minimal
2) avant/apres attendu (description)
3) tests/commandes de verification
```

### Prompt 2 — Harmonisation charte graphique

```text
Objectif: harmoniser couleurs, tailles de police et espacements PDF selon la charte OFB.
Contexte: @src/bilans/common/ofb_charte.py @src/bilans/common/pdf_report_builder.py @config/presentation/pdf_presentation.yaml
Demande:
- lister d'abord les incoherences
- proposer 2 options (conservative / modernisee legere)
- implementer seulement l'option conservative apres validation
```

### Prompt 3 — Optimisation pagination PDF

```text
Objectif: reduire les coupures de tableaux/graphiques sur pages PDF.
Contexte: @src/bilans/engine/generation_pdf_profil.py @src/bilans/engine/generation_pdf_synthese.py
Contraintes:
- pas de suppression de sections
- pas de changement de contenu
Sortie: patch + cas limites traites + tests smoke
```

### Prompt 3bis — Deplacement de sections PDF

```text
Objectif: deplacer des sections dans le PDF sans modifier le contenu fonctionnel.
Contexte: @src/bilans/engine/registre_sections_pdf.py @src/bilans/engine/generation_pdf_profil.py @src/bilans/engine/generation_pdf_synthese.py @config/profils_bilan/<profil>.yaml
Demande:
1) decrire l'ordre actuel des sections
2) proposer le nouvel ordre cible
3) implementer uniquement le repositionnement (pas de suppression/ajout de section)
Contraintes:
- conserver les ids de section existants
- conserver la logique de calcul et les donnees affichees
- garantir la retrocompatibilite pour les autres profils
Verification:
- lancer un test smoke sur le profil cible
- confirmer dans le compte-rendu l'ordre final des sections
```

### Prompt 3ter — Optimisation de l'organisation des sections (basee sur le dernier PDF)

```text
Objectif: optimiser l’organisation des sections du PDF pour le profil de bilan utilise lors du dernier run, sans changer le fond metier.

Etape 1 — Analyse obligatoire (pas de code):
1) Identifier le dernier PDF genere pertinent et decrire l’ordre actuel des sections.
2) Pour chaque section, resumer en 1-2 lignes les donnees presentees et son role (controles, procedures, PVe, synthese, etc.).
3) Determiner le profil de bilan utilise (id de profil) et les fichiers impactes dans le programme (YAML + Python).
4) Evaluer la coherence narrative (ex: sections “controles” avant “procedures”, regroupement thematique, continuite logique).

Etape 2 — Proposition:
5) Proposer une nouvelle organisation SEULEMENT si c’est utile, avec:
   - ordre actuel -> ordre propose,
   - justification section par section,
   - impact attendu en lisibilite/interpretation.
6) Ne rien modifier tant que je n’ai pas valide.

Etape 3 — Implementation apres confirmation explicite:
7) Si je confirme, implementer les changements dans les fichiers concernes (YAML / .py / registre de sections / autre composant pertinent).
8) Fournir:
   - patch minimal,
   - liste des fichiers modifies,
   - resume avant/apres de l’ordre final des sections,
   - verification smoke.

Contraintes strictes:
- Ne pas modifier les calculs de donnees.
- Ne pas modifier le contenu metier des sections (uniquement l’organisation/ordre).
- Preserver la retrocompatibilite des profils non concernes.
```

## 2) Parametrage PDF par profil

### Prompt 4 — Activer/desactiver sections par profil

```text
Objectif: permettre l’activation/desactivation de sections PDF via YAML de profil.
Contexte: @config/profils_bilan/_defaults.yaml @config/profils_bilan/<profil>.yaml @src/bilans/engine/registre_sections_pdf.py @src/bilans/engine/orchestrateur_profils.py
Attendu:
- proposition de schema YAML
- retrocompatibilite avec profils existants
- tests unitaires sur resolution des sections
```

### Prompt 5 — Variantes de rendu selon profil

```text
Objectif: appliquer des presets de rendu (compact/standard/large) specifiques a certains profils.
Contexte: @src/bilans/point_entree_cli.py @src/bilans/engine/orchestrateur_profils.py @config/profils_bilan/
Contraintes:
- priorite: option CLI > profil YAML > defaut global
- documenter la priorite dans un commentaire court
```

### Prompt 6 — Personnalisation titre/sous-titre/footer

```text
Objectif: personnaliser titre, sous-titre et footer PDF selon le profil.
Contexte: @config/profils_bilan/*.yaml @src/bilans/engine/generation_pdf_profil.py
Livrable: schema YAML + patch + exemple sur 2 profils reels
```

## 3) Fiabilisation des donnees

### Prompt 7 — Audit de fiabilite d’un indicateur

```text
Objectif: auditer et fiabiliser le calcul de l’indicateur <nom_indicateur>.
Contexte strict: @src/bilans/engine/agregations_profil.py @src/bilans/common/chargeurs_donnees.py @tests/
Demande:
1) tracer le flux de donnees source -> agregation -> PDF
2) identifier risques (doublons, filtres, nulls, mapping)
3) proposer correctif minimal
4) ajouter test de non-regression
```

### Prompt 8 — Validation d’interpretation des sources

```text
Objectif: verifier que l’interpretation metier des sources PEJ/PA/PVe est coherente avec les regles projet.
Contexte: @src/bilans/common/chargeurs_donnees.py @src/bilans/engine/orchestrateur_profils.py @docs/architecture/README_sources.md
Sortie attendue:
- matrice “source -> usage -> risque -> correction”
- patch uniquement sur les erreurs averees
```

### Prompt 9 — Controles qualite automatiques

```text
Objectif: ajouter des garde-fous qualite sur les donnees avant generation PDF.
Contexte: @src/bilans/engine/orchestrateur_profils.py @tests/unit/
Contraintes:
- guard clauses en entree
- logs structures et explicites
- echec propre avec message actionnable
```

## 4) Ajout d’un nouveau profil

### Prompt 10 — Creation complete profil

```text
Objectif: creer un nouveau profil "<id_profil>".
Contexte: @config/profils_bilan/_defaults.yaml @config/profils_bilan/ @src/bilans/engine/catalogue_profils.py
Attendu:
- nouveau YAML profil
- integration catalogue/listing CLI
- test smoke d’execution profil
- aucune regression profils existants
```

### Prompt 11 — Profil derive d’un existant

```text
Objectif: creer "<nouveau_profil>" derive de "<profil_source>" avec differences minimales.
Contexte: @config/profils_bilan/<profil_source>.yaml @config/profils_bilan/
Contraintes:
- DRY: ne dupliquer que le necessaire
- documenter les differences metier en commentaire YAML
```

### Prompt 12 — Profil geographique (type PNF/TUB)

```text
Objectif: creer un profil restreint geographiquement.
Contexte: @config/profils_bilan/ @src/bilans/engine/orchestrateur_profils.py @src/bilans/common/chargeurs_donnees.py
Contraintes:
- utiliser le mecanisme existant (restrict_geo / enrichissement INSEE)
- ne pas introduire de second mecanisme parallele
```

## 5) Audit de code / optimisation

### Prompt 13 — Audit perf cible

```text
Objectif: auditer les goulots d’etranglement du pipeline sur <zone>.
Contexte: @src/bilans/engine/orchestrateur_profils.py @src/bilans/engine/agregations_profil.py
Methode demandee:
- profiler logiquement (sans micro-optimisation prematuree)
- classer quick wins / medium / lourd
- implementer uniquement quick wins a faible risque
```

### Prompt 14 — Reduction duplication

```text
Objectif: reduire duplication dans <fichier(s)> sans changer le comportement.
Contexte: @src/bilans/engine/<fichier>.py
Contraintes:
- conserver API/CLI inchangees
- tests avant/apres obligatoires
- patch atomique lisible
```

### Prompt 15 — Optimisation I/O chargement donnees

```text
Objectif: optimiser le chargement des sources (I/O) pour reduire le temps total de run.
Contexte: @src/bilans/common/chargeurs_donnees.py
Attendu:
- identifier lectures redondantes
- proposer cache local controle
- invalider cache proprement
- test de coherence resultats
```

### Prompt 16 — Optimisation memoire

```text
Objectif: reduire l’empreinte memoire sur les gros runs multi-profils.
Contexte: @src/bilans/engine/execution_lots_profils.py @src/bilans/engine/orchestrateur_profils.py
Contraintes:
- pas de changement fonctionnel
- liberer explicitement intermediaires volumineux
```

## 6) Debug / regression

### Prompt 17 — Bug de calcul

```text
Objectif: corriger le bug <description>.
Contexte: @<fichier1> @<fichier2> @tests/
Methode:
1) ecrire test qui echoue
2) corriger minimalement
3) faire passer test
4) verifier non-regression liee
```

### Prompt 18 — Regression apres changement

```text
Objectif: identifier la cause de la regression <symptome>.
Contexte: @src/bilans/** @tests/**
Demande:
- hypotheses classees par probabilite
- instrumentation minimale
- correctif + test de verrouillage
```

## 7) Documentation technique utile (courte, econome)

### Prompt 19 — Doc d’un flux metier

```text
Objectif: documenter le flux <source -> calcul -> PDF> en 1 page max.
Contexte: @src/bilans/common/chargeurs_donnees.py @src/bilans/engine/agregations_profil.py @src/bilans/engine/generation_pdf_profil.py
Format:
- etapes numerotees
- points de risque
- points de controle testables
```

### Prompt 20 — Migration/clarification architecture

```text
Objectif: mettre a jour la doc pour refleter l’architecture actuelle (src/bilans, profils YAML, CLI).
Contexte: @README.md @docs/architecture/ORGANISATION_PROJET.md @docs/migration/cli_moteur_unique.md
Contraintes:
- supprimer ambiguites legacy
- garder exemples CLI executables
```

## 8) Prompts “chef d’orchestre” (efficaces)

### Prompt 21 — Sprint court en 3 lots

```text
Objectif: realiser <objectif> en 3 lots max.
Contexte: @<fichiers>
Regles:
- Lot 1: securiser (tests/guards)
- Lot 2: implementer
- Lot 3: nettoyer minimalement
Apres chaque lot: STOP et attendre ma validation.
```

### Prompt 22 — Mode ultra-token

```text
Mode ultra-concis:
- reponses <= 12 lignes
- pas de blabla
- uniquement: plan court, patch, commandes test, risques
Objectif: <objectif>
Contexte: @<fichiers>
```

### Prompt 23 — Revue critique severe

```text
Fais une review orientee risques sur ce diff/changement.
Priorite:
1) bugs/regressions
2) incoherences metier
3) dette technique critique
Sortie:
- findings classes severe/moyen/faible
- proposition de fix minimal par finding
Contexte: @<fichiers>
```

## 9) Macro-prompts specialises

### PDF + profil + fiabilite (combo)

```text
Objectif: ajuster le rendu PDF du profil <profil_id> et fiabiliser les chiffres affiches.
Contexte: @config/profils_bilan/<profil_id>.yaml @src/bilans/engine/agregations_profil.py @src/bilans/engine/generation_pdf_profil.py @tests/
Contraintes:
- pas de changement de perimetre metier
- patch minimal et tracable
Sortie:
1) plan
2) patch
3) test(s) ajoute(s)
4) mini note d’impact
```

### Nouveau profil + QA complete

```text
Objectif: ajouter profil <id> + valider sa robustesse.
Contexte: @config/profils_bilan/ @src/bilans/engine/catalogue_profils.py @tests/smoke/
Attendu:
- creation YAML profil
- integration listing CLI
- smoke test dedie
- verification compatibilite batch/combine
```

## 10) Cartes adaptees au profil de bilan

Prefixer avec le **bloc commun** en tete de session si besoin.

### Prompt 24 — Chaine complete profil → cartes → PDF

```text
Objectif:
Mettre en place (ou completer) une chaine coherente « profil de bilan choisi → cartes pertinentes → integration PDF », sans regression sur les profils existants.

Question obligatoire (repondre avant tout code):
Cette evolution doit-elle s'appliquer :
- uniquement au profil <profil_id> (ex. agrainage, chasse, global, synthese_activite_PA_PJ), ou
- a tous les profils de bilan ?
Si ambigu, demander aussi le profil pilote pour la premiere iteration.

Contexte technique (source de verite):
@config/profils_bilan/<profil_id>.yaml
@config/profils_bilan/_defaults.yaml
@config/profils_bilan/schema_ui.yaml
@src/bilans/cartographie/param/profils_cartes.yaml
@src/bilans/cartographie/production_cartographique.py
@src/bilans/cartographie/config_cartes_model.py
@src/bilans/common/carte_helper.py
@src/bilans/engine/orchestrateur_profils.py
@src/bilans/engine/execution_lots_profils.py
@src/bilans/engine/generation_pdf_profil.py
@src/bilans/engine/generation_pdf_synthese.py
@docs/usage/cartes_et_bilans.md
@docs/usage/filtrage_bilans_et_cartes.md
@docs/usage/README_Production_cartes.md
@tests/unit/test_carte_helper_maps.py
@tests/unit/test_maps_pdf_layout.py

Etat attendu aujourd'hui (a verifier, ne pas supposer):
1) Profil bilan : bloc optionnel cartographie (fichiers, disposition) + capabilities.map_profiles + option CLI cartes.
2) Resolution PNG : resolve_profile_map_id, resolve_profile_map_paths, expected_map_filenames dans carte_helper.
3) Generation QGIS : profils dans profils_cartes.yaml → carte_<map_id>.png dans generateur_de_cartes.
4) PDF : section 5 (global/thematique) ou brochure selon profil ; fallback si PNG absents.
5) Risque connu : mapping partiel / durci (find_maps_for_bilan, profils carto sans entree YAML, filtres bilan vs expressions QGIS).

Etape 1 — Audit (PAS DE CODE):
Pour le profil <profil_id> (et perimetre valide) :
A) Tracer le flux complet :
   CLI/options → orchestrateur (ensure_maps, prompt_cartography_integration) → export QGIS → recherche PNG → rendu PDF.
B) Produire un tableau :
   | profil bilan | map_id | fichiers PNG attendus | profil carto QGIS | filtres bilan | filtres carte | ecart |
C) Lister les ecarts bloquants vs cosmetiques (carte absente, mauvais map_id, filtres desalignes, layout brochure vs standard).
D) Proposer 2 options d'architecture (minimal YAML-only / socle commun + declarations par profil), avec avantages/inconvenients.
STOP — attendre ma validation du perimetre et de l'option choisie.

Etape 2 — Design cible (toujours sans code tant que non valide):
Definir pour chaque profil concerne :
- cartographie.fichiers (motifs {map_id} si besoin),
- capabilities.map_profiles (liste des profils QGIS a generer en batch),
- entree(s) dans profils_cartes.yaml (couches, symbologies, periode, output_filename),
- alignement des criteres de filtrage avec le profil bilan (cf. filtrage_bilans_et_cartes.md).
Regles projet :
- Pas de if profil_id == ... cote rendu : preferer YAML explicite.
- Changement global → cle visible dans chaque profil YAML concerne, pas seulement _defaults.
- Cartographie optionnelle : 0/1/N cartes, pas d'erreur bloquante si QGIS indisponible.

Etape 3 — Implementation (lots courts, apres validation):
Lot 1 — Declarations & resolution
- Completer YAML profil(s) + profils_cartes.yaml.
- Reduire/eviter mappings codes en dur dans carte_helper si une config YAML suffit.
- Tests unitaires carte_helper (multi-fichiers, profil sans carte, map_id derive types_usager_cible).

Lot 2 — Generation
- Brancher ensure_maps / run_export sur capabilities.map_profiles et periode/departement du run.
- Messages CLI actionnables (noms attendus, dossier, commande generer_cartes si pertinent).

Lot 3 — PDF
- Verifier section 5 / brochure : bons chemins, placeholder coherent, une carte par page (PDF standard).
- Mettre a jour test_maps_pdf_layout si layout touche.

Contraintes strictes:
- Ne pas modifier les calculs d'agregation (pandas) sauf bug avere de coherence carte/bilan.
- Ne pas versionner data/out/, PNG de debug a la racine, __pycache__.
- Patch minimal, tracable.
- QGIS optionnel : le bilan doit toujours se terminer sans carte.

Verification (obligatoire avant « termine »):
1) python -m pytest -q tests/unit/test_carte_helper_maps.py tests/unit/test_maps_pdf_layout.py
2) Smoke cible :
   python -m bilans --profil <profil_id> --date-deb YYYY-MM-DD --date-fin YYYY-MM-DD --dept-code XX
   avec et sans --cartes si pertinent.
3) Checklist manuelle :
   - PNG au bon nom dans data/out/generateur_de_cartes/
   - section carto du PDF remplie ou message fallback explicite
   - pour perimetre « tous les profils » : au moins 2 profils distincts (ex. global + agrainage) sans regression.

Livrables par lot:
1) plan (5–8 points)
2) patch
3) tests ajoutes/renforces
4) note d'impact (profils touches, commandes, risques regression)
```

### Prompt 24bis — Variante profil pilote unique

```text
Objectif: meme chaine que Prompt 24, scope reduit.

Perimetre fige: uniquement le profil <profil_id> (ex. agrainage).
Ne pas modifier les autres profils YAML sans mon accord explicite.

Reprendre les etapes 1–3 du Prompt 24 en limitant l'audit, le design et l'implementation a ce profil.
Verification: pytest cible + un smoke sur <profil_id> uniquement.
```

### Prompt 25 — Defaults mise en page cartes QGIS (réf. profil global)

```text
Objectif:
Extraire et paramétrer les éléments généraux des mises en page cartographiques (actuellement hardcodés en Python ou fixés dans le .qgz). Centraliser ces réglages dans une configuration YAML (ex: `layout_defaults.yaml`) et utiliser le layout du profil "global" comme modèle de référence. Tous les autres profils seront harmonisés comme des variations de ce profil global.
Ce prompt est un modèle : l'utilisateur a conservé ci-dessous UNIQUEMENT les éléments qu'il souhaite modifier.

[INSTRUCTIONS UTILISATEUR : SUPPRIMEZ LES LIGNES NON DÉSIRÉES ET PRÉCISEZ LES VALEURS CIBLES ENTRE CROCHETS]

### 1. Format d'export et page
- Fichiers concernés : `src/bilans/cartographie/config_cartes_model.py`, `src/bilans/cartographie/config_cartes.py`
- Format d'image (ex: png, jpeg) : [Préciser la valeur cible]
- Résolution DPI (ex: 300) : [Préciser la valeur cible]
- Taille de page (ex: A4) : [Préciser la valeur cible]
- Orientation (ex: landscape) : [Préciser la valeur cible]

### 2. Éléments fixes de la mise en page (Textes et Légende)
- Fichier concerné : `src/bilans/cartographie/production_cartographique.py`
- ID de l'item Titre (`layout_title_item_id` actuel : 'titre_principal') : [Modifier si besoin]
- ID de l'item Sous-titre (`layout_subtitle_item_id` actuel : 'sous_titre') : [Modifier si besoin]
- Légende : [Préciser si la légende doit être standardisée, repositionnée, etc.]

### 3. Bandeau et Logos (Actuellement hardcodés en Python)
- Fichier concerné : `src/bilans/cartographie/production_cartographique.py`
- Bandeau Haut (fonction `_ensure_logo_bandeau`, id `bandeau_logos_ofb`, hauteur `min(25mm, 15% page)`) : [Préciser la nouvelle règle, ex: extraire en YAML, forcer la hauteur à 20mm]
- Logo OFB Bas Droite (constantes `LOGO_OFB_BAS_DROITE_*`, marges, id `logo_ofb_bas_droite`) : [Préciser la nouvelle règle, ex: extraire en YAML, définir les marges]

### 4. Composants du Layout QGIS de référence (Fichier .qgz)
- Fichier concerné : `ref/programme/sig/bilans_carte.qgz`
- Layout de référence (Modèle) : [Préciser le nom exact du layout global dans le .qgz, ex: "Layout_Global"]
- Composants QGIS (Carte item 65639, Échelle, Flèche Nord) : [Préciser s'il faut ajuster leur taille ou position via script Python (apply_layout_defaults) ou manuellement]

---

Contexte & Contraintes techniques absolues (pour l'agent) :
1. Ne JAMAIS écraser les symbologies de couches (RuleRenderer QGIS).
2. L'absence de QGIS sur la machine ne doit générer aucune erreur bloquante.
3. Rétrocompatibilité : Tout profil ne spécifiant pas de `layout_defaults` doit conserver le comportement actuel.
4. Les migrations de variables hardcodées (logos, bandeau) vers le YAML ne doivent engendrer aucune modification visuelle sur le layout de référence (tolérance au pixel près).
5. Ne pas traiter les variations spécifiques induites par les règles de profil (couches métier, symbologies).

Fichiers sources prioritaires à lire AVANT toute modification :
@ref/programme/sig/bilans_carte.qgz
@src/bilans/cartographie/production_cartographique.py
@src/bilans/cartographie/config_cartes_model.py
@src/bilans/cartographie/param/profils_cartes.yaml

Étapes de travail exigées (Stop & Go à chaque étape) :
1) Audit (Lecture seule) : Analysez le code actuel et les fichiers .qgz/.py uniquement pour les éléments sélectionnés ci-dessus. Produisez un récapitulatif strict de ce qui va être modifié (ancien comportement vs nouveau comportement dicté par le YAML). **Attendez la validation de l'utilisateur (Stop & Go)**.
2) Création du Design : Créez le fichier de configuration YAML (ex: `layout_defaults.yaml`) et mettez à jour `config_cartes_model.py` (Pydantic). Modifiez `export_layout()` dans `production_cartographique.py` pour consommer ces valeurs AVANT l'export d'image. Gérer la rétrocompatibilité. **Attendez la validation (Stop & Go)**.
3) Implémentation par lots : 
   - Lot 1: Config + Modèles
   - Lot 2: Application dans l'export QGIS (`production_cartographique.py`)
   - Lot 3: Harmonisation des profils existants
   - Lot 4: Tests et non-régression

Vérification finale obligatoire :
1) Lancer `python -m pytest -q` ciblé sur les tests de configuration (ex: `test_cartographie_config.py`).
2) Lancer un smoke test QGIS : `python -m bilans --profil global --cartes --dept-code 21`
3) Analyser les logs pour s'assurer de l'absence d'erreurs QGIS.
4) Effectuer une comparaison visuelle stricte : les PDF et PNG générés doivent respecter la nouvelle configuration sans casser l'existant.
```

