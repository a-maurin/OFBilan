# Template de demande de changement PDF

Copier-coller ce template dans le chat, puis remplir les champs.

---

## 1) Contexte

- **Type de demande**: [ ] Ajustement visuel [ ] Structure sections [ ] Données affichées [ ] Logique métier [ ] Autre
- **Objectif métier**:
- **Priorité**: [ ] Haute [ ] Moyenne [ ] Basse

## 2) Périmètre exact

- **Moteur concerné**: [ ] Global [ ] Thématique [ ] Les deux
- **Profil(s) thématique(s)** (si applicable):
- **Département / période de test**:
- **Impact attendu**: [ ] Présentation uniquement [ ] Présentation + contenu [ ] Contenu métier/calcul

### Numérotation canonique (référence)

| Chapitre PDF | ID interne (historique) | Alias YAML acceptés |
|--------------|-------------------------|---------------------|
| 1. Chiffres clés | `sec1` | — |
| 2. Activité de contrôle | `sec2`, `sec21`, `sec22`, … | — |
| 3. Activité par type d'usager | `sec4` | `sec_usagers` (déprécié) |
| 4. Procédures (PEJ, PA, PVe) | `sec3`, `sec31`…`sec33` | `sec_procedures` (déprécié) |
| 5. Cartographie | `sec5` / `sec5map` (global) | — |
| 6. Annexes | `sec6` | — |

Pilotage : `config/presentation/pdf_presentation.yaml` (`sections.order`, `sections.titles`, `blocks.*`, `feature_registry`).  
Profils à zones (PNF, etc.) : exceptions documentées dans le handoff harmonisation.

Tests de non-régression TOC (ordre des titres) : `tests/fixtures/pdf_toc/README.md`.

## 3) Changement demandé

- **Ce qu'il faut changer** (description claire):
- **Section(s) concernée(s)** (ex: `sec21`, `sec22res`, `sec31` — ou alias `sec_usagers` / `sec_procedures`):
- **Bloc(s) concerné(s)** (ex: `blocks.sec22res.show_pie`):
- **Ordre des sections** (si concerné):
- **Comportement données manquantes**: [ ] `show_placeholder` [ ] `hide_silently` [ ] Sans changement

## 4) Résultat attendu dans le PDF

- **Avant** (ce que je vois aujourd'hui):
- **Après** (ce que je dois voir):
- **Critère d'acceptation visuelle** (vérifiable en 1 phrase):

## 5) Exemples / références (optionnel mais utile)

- **Capture, extrait PDF, exemple de profil**:
- **Fichier de référence** (si existant):
- **Contrainte de wording / style**:

## 6) Validation attendue

- **Cas minimum à tester**:
  - Global
  - Thématique profil principal:
  - Non-régression profil secondaire:
- **Mise à jour de la matrice visuelle**:
  - Oui
  - Non

## 7) Sortie souhaitée

- **Livrable**: [ ] Modif YAML seule [ ] Modif code + YAML [ ] + tests unitaires [ ] + smoke tests
- **Niveau de détail du retour**: [ ] Bref [ ] Standard [ ] Détaillé

---

## Mini version ultra-courte (si besoin)

```text
Objectif:
Moteur/profil:
Sections/blocs:
Résultat attendu:
Cas de test à rejouer:
```

