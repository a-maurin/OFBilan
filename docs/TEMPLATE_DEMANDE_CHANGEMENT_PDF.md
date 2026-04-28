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

## 3) Changement demandé

- **Ce qu'il faut changer** (description claire):
- **Section(s) concernée(s)** (ex: `sec21`, `sec22res`, `sec31`):
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

