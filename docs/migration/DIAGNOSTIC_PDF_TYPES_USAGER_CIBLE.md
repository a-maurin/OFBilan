# Diagnostic : analyses absentes du PDF pour le bilan types_usager_cible

## Contexte

Pour le profil **types_usager_cible**, les CSV exportés dans `data/out/bilan_types_usager_cible/` contiennent des analyses qui ne figurent pas dans le PDF (ex. `bilan_types_usager_cible_Côte-dOr.pdf`). Exemples manquants cités :

- Répartition pour l’usager ciblé des **résultats des contrôles** (Conforme / Manquement / Infraction)
- Répartition des **types de procédures** (PJ, PA, PVe par domaine/thème)
- **Répartition par communes** (top communes pour l’usager ciblé)

---

## 0. Vérification : le problème survient-il ailleurs ?

**À conserver en mémoire :** les propositions de correction détaillées ci‑après (sections 1 et 2) restent la référence pour l’implémentation.

### 0.1 Bilan global (module PDF du pipeline profil global)

- **Génération :** script dédié ; CSV et PDF sont produits dans le même flux. Le PDF est construit en **relisant les CSV** générés (`_generate_pdf_content` charge `controles_global_*.csv`, `pej_global_*.csv`, etc.).
- **Contenu :** Le PDF inclut toutes les sections correspondant aux CSV (chiffres clés, domaine, thème, **résultats des contrôles**, procédures PEJ/PA/PVe, types d’usagers). Aucune section n’est exclue selon un flag `type_usager`.
- **Par commune :** Le bilan global **ne produit pas** d’agrégat par commune (pas d’équivalent à `agg_commune`). Donc pas d’écart à constater sur ce point.
- **Conclusion :** **Aucun écart** entre CSV et PDF pour le bilan global.

### 0.2 Bilans thématiques sans analyse par type d’usager (chasse, agrainage, pêche, etc.)

- **Génération :** même moteur `bilan_thematique_engine.run_engine` → `_generate_pdf`. Pour ces profils, `profile.get("analyses", {}).get("type_usager")` est **faux** ou absent.
- **Effet :** La condition `if nb_ctrl > 0 and not is_type_usager and not is_procedures` est **vraie** : la section « Résultats des contrôles » et le tableau « Communes avec le plus de contrôles » sont bien affichés. Les CSV (resultats, par_commune) sont cohérents avec le PDF.
- **Conclusion :** **Aucun écart** pour les profils thématiques sans `type_usager`.

### 0.3 Bilans thématiques avec analyse par type d’usager

Les profils suivants ont `analyses.type_usager: true` dans leur YAML :

| Profil                  | Fichier YAML                     | `type_usager_target` |
|-------------------------|----------------------------------|----------------------|
| types_usager_cible      | types_usager_cible.yaml          | choisi à la volée    |
| types_usager            | types_usager.yaml                | non (tous)           |
| agriculteur             | agriculteur.yaml                 | Agriculteur…         |

Pour **tous** ces profils, le moteur :

- calcule et exporte en CSV : `tab_resultats`, `agg_commune`, `ctrl_par_usager_*`, `res_par_usager_*`, `proc_par_usager_*` ;
- mais dans `_generate_pdf`, la section « Résultats des contrôles » (et donc le tableau communes) n’est **jamais** créée (`not is_type_usager` est faux) ;
- et les tableaux **procédures** (`proc_par_usager_domaine` / `proc_par_usager_theme`) ne sont **jamais** insérés dans le PDF.

**Conclusion :** **Le même problème** (résultats des contrôles, répartition par communes, types de procédures absents du PDF alors que présents en CSV) survient pour **les quatre** profils à `type_usager: true`. Une seule correction dans `bilan_thematique_engine.py` (section « Contrôles par type d’usager ») corrigera les quatre en une fois.

---

### 1.1 Résultats des contrôles (usager ciblé)

**Fichier CSV concerné :** `controles_types_usager_cible_resultats.csv` (colonnes `resultat`, `nb`, `taux`).

**Cause :**  
Dans `bilan_thematique_engine.py`, la section PDF **« Résultats des contrôles »** n’est créée que si :

```python
if nb_ctrl > 0 and not is_type_usager and not is_procedures:
```

Pour le profil `types_usager_cible`, `is_type_usager` est `True`. Cette condition exclut donc **tous** les bilans avec analyse par type d’usager. Le tableau et le camembert des résultats (Conforme / Manquement / Infraction) ne sont jamais ajoutés au PDF, alors que les données existent dans `results["tab_resultats"]` (calculé sur `point_filtered`, déjà filtré par type usager ciblé) et sont bien exportées en CSV.

**Résumé :** La section « Résultats des contrôles » est volontairement désactivée dès que `type_usager` est activé, sans alternative dédiée pour l’usager ciblé.

---

### 1.2 Répartition par communes

**Fichier CSV concerné :** `indicateurs_types_usager_cible_par_commune.csv` (colonnes `insee_comm`, `nb_controles`, `nb_infractions`, `taux_infraction`).

**Cause :**  
Le tableau **« Communes avec le plus de contrôles »** est généré **uniquement à l’intérieur** du bloc « Résultats des contrôles » (vers les lignes 1049–1058). Comme ce bloc n’est pas exécuté lorsque `is_type_usager` est vrai, le top communes n’apparaît jamais dans le PDF pour les bilans types_usager_cible.  
Les données sont pourtant calculées : `agg_commune` est construit à partir de `point_filtered` (lignes 648–659), donc déjà restreint à l’usager ciblé quand un filtre `type_usager_target` est appliqué, et exporté dans `indicateurs_<profil_id>_par_commune.csv`.

**Résumé :** Le tableau par communes n’est pas affiché car il est couplé à une section (« Résultats des contrôles ») qui est exclue pour les profils type_usager.

---

### 1.3 Types de procédures (PJ, PA, PVe par domaine / thème)

**Fichiers CSV concernés :**  
`procedures_par_type_usager_domaine.csv`, `procedures_par_type_usager_theme.csv`.

**Cause :**  
Dans `_generate_pdf`, la section **« Contrôles par type d’usager »** utilise uniquement :

- `usager_effectifs`
- `usager_par_domaine`
- `ctrl_par_usager_domaine`
- `res_par_usager_domaine`

Les clés **`proc_par_usager_domaine`** et **`proc_par_usager_theme`** ne sont **jamais** utilisées pour construire un tableau ou un graphique. Les agrégats sont bien calculés (lignes 765–773), exportés en CSV, mais aucun bloc de code ne les insère dans le PDF.

**Résumé :** Données procédures présentes en `results` et en CSV, mais aucun rendu PDF prévu pour elles.

---

## 2. Plan de correction proposé

### 2.1 Objectif

Aligner le contenu du PDF sur les CSV pour le profil **types_usager_cible** en ajoutant dans le PDF :

1. La répartition des **résultats des contrôles** pour l’usager ciblé.
2. La **répartition par communes** (top N communes) pour l’usager ciblé.
3. La répartition des **procédures par domaine** (et éventuellement par thème) pour l’usager ciblé.

Sans casser le comportement actuel pour les autres profils (notamment sans type_usager).

---

### 2.2 Modifications dans `bilan_thematique_engine.py`

#### A. Résultats des contrôles pour l’usager ciblé

- **Où :** Dans la section « Contrôles par type d’usager » (`if is_type_usager and nb_ctrl > 0`), après les tableaux existants (usager_par_domaine, ctrl_par_usager_domaine, res_par_usager_domaine).
- **Quoi :**
  - Si `results.get("tab_resultats")` est non vide :
    - Ajouter un tableau « Résultats des contrôles » (colonnes Résultat, Nombre, Taux), alimenté par `tab_resultats`.
    - Optionnel : ajouter un camembert de répartition (comme pour la section standard « Résultats des contrôles »).
  - Adapter le libellé pour préciser qu’il s’agit de l’usager ciblé (ex. « Résultats des contrôles – usager ciblé » ou « Résultats des contrôles – [libellé du type] » en mono-usager).

#### B. Répartition par communes

- **Où :** Dans la même section « Contrôles par type d’usager », après le bloc « Résultats des contrôles » (ou à la suite des tableaux domaine).
- **Quoi :**
  - Si `options.get("par_commune", True)` et `results.get("agg_commune")` est non vide :
    - Construire le tableau « Communes avec le plus de contrôles » à partir de `results["agg_commune"]` (tri par `nb_controles` décroissant, head(10)).
    - Colonnes : Code INSEE (ou nom), Nb contrôles, Nb infractions, Taux infraction.
    - Légende adaptée, ex. « Communes avec le plus de contrôles (usager ciblé) ».

#### C. Procédures par domaine (et thème)

- **Où :** Toujours dans la section « Contrôles par type d’usager », après les tableaux résultats par domaine.
- **Quoi :**
  - Si `results.get("proc_par_usager_domaine")` est non vide :
    - Construire un tableau « Procédures par domaine » (ou « Répartition des procédures par domaine »).
    - En mode mono-usager : supprimer la colonne `type_usager` si une seule valeur, comme pour `ctrl_par_usager_domaine` / `res_par_usager_domaine`.
    - Colonnes utiles : domaine, puis nb_pj, nb_pa, nb_pve (selon le schéma réel des agrégats).
  - Si souhaité, faire de même pour `proc_par_usager_theme` avec un tableau « Procédures par thème » (et même logique de masquage de `type_usager` en mono-usager).

---

### 2.3 Ordre recommandé des blocs dans la section « Contrôles par type d’usager »

1. Effectifs par catégorie (multi-usager) ou rien (mono-usager).
2. Tableau Usagers × Domaine / Répartition par domaine.
3. Contrôles par type d’usager et par domaine (top 15).
4. Résultats des contrôles par type d’usager et par domaine (top 15).
5. **Nouveau :** Résultats des contrôles (tableau + éventuellement camembert) pour l’usager ciblé.
6. **Nouveau :** Communes avec le plus de contrôles (usager ciblé).
7. **Nouveau :** Procédures par domaine (et par thème si implémenté).
8. Saut de page.

Cela garde une logique : effectifs → contrôles/résultats par domaine → synthèse résultats → territorial (communes) → procédures.

---

### 2.4 Points d’attention

- **Cohérence mono-usager :** Pour tous les nouveaux tableaux, réutiliser la logique existante : si `is_single_usager` et colonne `type_usager` à une seule valeur, la supprimer et adapter les titres (ex. « Procédures par domaine » au lieu de « Procédures par type d’usager et par domaine »).
- **Sommaire :** Les nouvelles entrées sont déjà dans la section « Contrôles par type d’usager » ; pas besoin de nouvelle section au sommaire sauf si on souhaite une section dédiée « Répartition par communes » (peu nécessaire si un seul tableau).
- **Tests :** Après implémentation, régénérer un PDF pour un département (ex. Côte-d’Or) avec le profil `types_usager_cible` et vérifier la présence des trois blocs (résultats, communes, procédures) et la cohérence avec les CSV.

---

### 2.5 Résumé des tâches techniques

| Priorité | Tâche | Fichier / zone |
|----------|--------|-----------------|
| 1 | Ajouter tableau + (optionnel) camembert « Résultats des contrôles » dans la section types d’usager, à partir de `tab_resultats` | `_generate_pdf`, bloc `if is_type_usager and nb_ctrl > 0` |
| 2 | Ajouter tableau « Communes avec le plus de contrôles » à partir de `agg_commune`, si `par_commune` et données présentes | Idem |
| 3 | Ajouter tableau « Procédures par domaine » à partir de `proc_par_usager_domaine` (avec logique mono-usager) | Idem |
| 4 | (Optionnel) Ajouter tableau « Procédures par thème » à partir de `proc_par_usager_theme` | Idem |
| 5 | Vérifier les noms de colonnes des agrégats procédures (nb_pj, nb_pa, nb_pve, etc.) pour le rendu PDF | `agg_procedures_par_type_usager_domaine` / theme |

Ce document peut servir de référence pour l’implémentation et les relectures de code.
