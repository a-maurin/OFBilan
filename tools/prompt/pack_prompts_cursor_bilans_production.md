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

