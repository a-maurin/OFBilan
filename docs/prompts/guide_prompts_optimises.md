# Guide des Prompts Optimisés pour l'Assistance au Code (Bilans Production)

Ce document centralise l'ensemble des modèles de prompts (requêtes) basés sur vos habitudes de travail, fusionnés avec le pack Cursor officiel du projet. 
L'ordre a été optimisé selon la fréquence de vos besoins en développement : du "Setup" quotidien aux tâches ponctuelles d'architecture.

Chaque prompt est pensé pour **restreindre l'IA**, limiter la génération de code non sollicité, et économiser les tokens.

---

## 1. ⚙️ Setup & "Chefs d'Orchestre" (À utiliser en début de tâche)

### 1.1. Préambule Système (À coller en début de chaque session)
```text
[RÈGLES DE TRAVAIL — À APPLIQUER SYSTÉMATIQUEMENT]
Profil : Je travaille sur un projet Python de génération de bilans PDF et de cartes QGIS (GeoPackage, CSV, YAML, ReportLab). Mon workspace est défini en début de session.
Comportement attendu :
- Analyse uniquement les fichiers explicitement utiles à ma demande]. Ne parcours pas tout le projet sans instruction.
- Ne génère jamais de code sans que je t'y aie explicitement autorisé. Si tu dois analyser avant d'agir, arrête-toi après le diagnostic et attends mon accord.
- Fournis uniquement les blocs de code modifiés (pas le fichier entier).
- Réponds en français, de façon concise. Pas de reformulation de ma demande, pas de résumé de ce que tu vas faire : fais-le directement.
- Si plusieurs corrections sont possibles, liste-les et demande-moi de prioriser avant d'agir.
- Signale-moi immédiatement si tu manques d'un élément nécessaire à ton analyse.
```

### 1.2. Mode Ultra-Token (Pour des corrections très rapides)
> **[CONTEXTE]** Fichiers ciblés : `@[fichiers]`
> **[OBJECTIFS]** [Objectif de la tâche rapide]
> **[CONTRAINTES]** Mode ultra-concis : réponses <= 12 lignes, pas de blabla. Fournis uniquement le plan court, le patch modifié, les commandes de test et les risques éventuels.

### 1.3. Sprint court en 3 lots (Pour une fonctionnalité complexe)
> **[CONTEXTE]** Fichiers ciblés : `@[fichiers]`
> **[OBJECTIFS]** Réaliser l'objectif `[objectif]` en 3 lots de développement maximum.
> **[CONTRAINTES]** Règles de lotissement : Lot 1 = Sécuriser (tests/guards), Lot 2 = Implémenter, Lot 3 = Nettoyer minimalement. **STOP** après chaque lot et attends ma validation avant de poursuivre.

---

## 2. 🐛 Débogage, Fiabilisation & Régressions (Très fréquent)

### 2.1. Incohérences QGIS vs Script
> **[CONTEXTE]** Écart de résultats identifié : Ma carte trouve `[X]` entités pour `[critère]`, le programme en trouve `[Y]`. Sources : `@[data/sources/sig/...]`.
> **[OBJECTIFS]** Analyse le fichier source pour déterminer la cause de l'écart (superpositions, champs vides). Donne les ID uniques concernés.
> **[CONTRAINTES]** Limite-toi à l'investigation. Ne modifie pas le programme. Livre ton diagnostic détaillé.

### 2.2. Régression après un changement
> **[CONTEXTE]** Fichiers ciblés : `@src/bilans/**`, `@tests/**`.
> **[OBJECTIFS]** Identifier la cause de la régression : `[symptôme exact, ex: tableau vide]`.
> **[CONTRAINTES]** Formule des hypothèses classées par probabilité. Propose une instrumentation minimale, un correctif ciblé et un test de verrouillage.

### 2.3. Audit de fiabilité d'un indicateur (Bug de calcul)
> **[CONTEXTE]** Fichiers stricts : `@src/bilans/engine/agregations_profil.py`, `@src/bilans/common/chargeurs_donnees.py`, `@tests/`.
> **[OBJECTIFS]** Auditer et fiabiliser le calcul de l'indicateur `[nom_indicateur]`. 
> **[CONTRAINTES]** Trace le flux de données (source -> agrégation -> PDF). Identifie les risques (doublons, nulls) et propose un correctif minimal + test de non-régression.

### 2.4. Validation d'interprétation des sources
> **[CONTEXTE]** Vérifier l'interprétation métier des sources PEJ/PA/PVe. Fichiers : `@src/bilans/common/chargeurs_donnees.py`, `@src/bilans/engine/orchestrateur_profils.py`.
> **[OBJECTIFS]** Produire une matrice "source -> usage -> risque -> correction".
> **[CONTRAINTES]** Ne propose un patch que pour les erreurs formellement avérées.

---

## 3. 📄 Bilans PDF : Mise en Page & Esthétique (Très fréquent)

### 3.1. Ajustement Visuel Cible (Mise en page, YAML)
> **[CONTEXTE]** Profil YAML : `@[config_tub.yaml]`, scripts : `@src/bilans/engine/generation_pdf_profil.py`.
> **[OBJECTIFS]** Améliorer la lisibilité / ajuster la mise en page de la section `[X]` (ex: répartition par type d'action, déplacement de graphique, réduction d'espaces).
> **[CONTRAINTES]** Ne modifie aucun calcul de données. Restreins l'usage de tokens : donne uniquement les blocs YAML ou Python modifiés. Joins un résumé avant/après attendu.

### 3.2. Harmonisation Charte Graphique
> **[CONTEXTE]** Fichiers : `@src/bilans/common/ofb_charte.py`, `@src/bilans/common/pdf_report_builder.py`.
> **[OBJECTIFS]** Harmoniser couleurs, polices et espacements PDF selon la charte.
> **[CONTRAINTES]** Liste d'abord les incohérences. Propose 2 options (conservative / modernisée). Implémente l'option conservative uniquement après validation.

### 3.3. Optimisation Pagination & Déplacement de Sections
> **[CONTEXTE]** Fichiers : `@src/bilans/engine/registre_sections_pdf.py`, `@src/bilans/engine/generation_pdf_profil.py`.
> **[OBJECTIFS]** Réduire les coupures de tableaux/graphiques OU réordonner les sections. 
> **[CONTRAINTES]** Pas de suppression de section ni de changement fonctionnel. Conserver les IDs existants. Patch + tests smoke.

---

## 4. 🎛️ Bilans PDF : Gestion des Profils YAML (Fréquent)

### 4.1. Activer/Désactiver des sections par profil
> **[CONTEXTE]** Fichiers : `@config/profils_bilan/_defaults.yaml`, `@config/profils_bilan/<profil>.yaml`, `@src/bilans/engine/registre_sections_pdf.py`.
> **[OBJECTIFS]** Permettre l'activation/désactivation de sections PDF via le YAML.
> **[CONTRAINTES]** Propose le schéma YAML, assure la rétrocompatibilité et fournis des tests unitaires.

### 4.2. Création complète d'un nouveau profil
> **[CONTEXTE]** Fichiers : `@config/profils_bilan/_defaults.yaml`, `@src/bilans/engine/catalogue_profils.py`.
> **[OBJECTIFS]** Créer le nouveau profil `[id_profil]`.
> **[CONTRAINTES]** Fournis le nouveau YAML, l'intégration CLI, et assure-toi qu'aucune régression n'impacte les profils existants (Test smoke requis).

### 4.3. Profil dérivé d'un existant (DRY)
> **[CONTEXTE]** Fichiers : `@config/profils_bilan/<profil_source>.yaml`.
> **[OBJECTIFS]** Créer `[nouveau_profil]` dérivé de `[profil_source]` avec des différences minimales.
> **[CONTRAINTES]** Principe DRY strict : ne dupliquer que le nécessaire et documenter les différences métier dans le YAML.

---

## 5. 🗺️ Cartographie & Symbologie QGIS (Fréquent)

### 5.1. Alignement Logique Script / QGIS (Symbologie)
> **[CONTEXTE]** Source : `@[symbology-style.db]`, `@[data/sources/sig/CARTO/pve_infractions.gpkg]`.
> **[OBJECTIFS]** Indique-moi une formule d'expression QGIS (symbologie/filtre) reproduisant la logique de notre script.
> **[CONTRAINTES]** Utilise les noms de champs exacts (ex: "PVe_INF-DATE-MIF"). Réponds brièvement avec la formule.

### 5.2. Chaîne complète : Profil → Cartes QGIS → PDF
> **[CONTEXTE]** Fichiers : `@config/profils_bilan/<profil_id>.yaml`, `@src/bilans/cartographie/param/profils_cartes.yaml`, `@src/bilans/cartographie/production_cartographique.py`, `@docs/usage/cartes_et_bilans.md`.
> **[OBJECTIFS]** Mettre en place ou compléter la chaîne d'export cartographique pour le profil `[profil_id]`.
> **[CONTRAINTES]** Étape 1 : Audit et flux (pas de code). Étape 2 : Design cible. Étape 3 : Implémentation par lots courts. QGIS doit rester optionnel (fallback si absent).

### 5.3. Defaults de mise en page cartes QGIS (réf. agrainage)
> **[CONTEXTE]** Fichiers : `@tools/prompt/handoff_cartographie_defaults_mise_en_page.md`, `@ref/programme/sig/bilans_carte.qgz`.
> **[OBJECTIFS]** Paramétrer par défaut les éléments généraux (format, DPI, structure) alignés sur le layout "agrainage" de référence.
> **[CONTRAINTES]** Ne pas écraser les symbologies (RuleRenderer QGIS). Migrer les constantes hardcodées vers YAML sans casser le rendu actuel.

---

## 6. 🏗️ Architecture, Audit & Optimisation (Ponctuel)

### 6.1. Audit Approfondi du Programme
> **[CONTEXTE]** Fichiers concernés : `Tous les scripts majeurs` (process_data.py, extract.py, tables_builder.py, config_tub.yaml).
> **[OBJECTIFS]** Auditer les logiques de calcul, la construction PDF et la génération de cartes pour détecter erreurs, valeurs nulles et incohérences.
> **[CONTRAINTES]** Livre uniquement le rapport d'audit et un plan de correction priorisé. Aucun code avant accord.

### 6.2. Revue critique sévère (Review PR/Diff)
> **[CONTEXTE]** Fichiers : `@[fichiers_modifies]`.
> **[OBJECTIFS]** Fais une review orientée risques sur ce changement. Priorités : 1) Bugs/Régressions, 2) Incohérences métier, 3) Dette technique.
> **[CONTRAINTES]** Classe les alertes (Sévère/Moyen/Faible). Propose un fix minimal par point remonté.

### 6.3. Audit Performance & I/O
> **[CONTEXTE]** Fichiers : `@src/bilans/engine/orchestrateur_profils.py`, `@src/bilans/common/chargeurs_donnees.py`.
> **[OBJECTIFS]** Auditer les goulots d'étranglement ou optimiser le chargement (I/O).
> **[CONTRAINTES]** Profilage logique, classification Quick wins / Lourds. Propose un cache local contrôlé si pertinent. N'implémente que les Quick wins validés.

---

## 7. 📝 Documentation & Communication (Ponctuel)

### 7.1. Rédaction de Communications (Vulgarisation pour la Hiérarchie)
> **[CONTEXTE]** Explication de correctifs (ex: couche des infractions `@[data/sources/sig/CARTO/pve_infractions.gpkg]`).
> **[OBJECTIFS]** Préparer un courriel pour le chef expliquant les bugs corrigés, les améliorations (avec un exemple), et ce qui n'a pas été touché (ex: saisie agent).
> **[CONTRAINTES]** Première personne, tutoiement, ton naturel. Aucun jargon de code.

### 7.2. Documentation d'un flux métier
> **[CONTEXTE]** Fichiers : `@src/bilans/common/chargeurs_donnees.py`, `@src/bilans/engine/agregations_profil.py`.
> **[OBJECTIFS]** Documenter le flux `[source -> calcul -> PDF]` en 1 page max.
> **[CONTRAINTES]** Étapes numérotées, identification des points de risque, points de contrôle testables.

---

## 8. 🛠️ Maintenance du Guide (Ajout de Modèles)

### 8.1. Nouveau Modèle (Mode Test / Sans sauvegarde)
> **[CONTEXTE]** Nouveau cas d'usage récurrent : `[Action]`.
> **[OBJECTIFS]** Génère un prompt adapté (Contexte / Objectifs / Contraintes).
> **[CONTRAINTES]** Propose-le directement dans le chat, **ne modifie pas** `guide_prompts_optimises.md`.

### 8.2. Nouveau Modèle (Ajout Définitif)
> **[CONTEXTE]** Cas d'usage : `[Action]`. Fichier cible : `@[guide_prompts_optimises.md]`.
> **[OBJECTIFS]** Ajoute le nouveau prompt à la liste du guide en respectant la structure.
> **[CONTRAINTES]** Insère-le dans la bonne section. Ne réécris pas le reste du document.
