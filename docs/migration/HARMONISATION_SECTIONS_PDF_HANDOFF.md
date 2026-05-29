# Harmonisation des sections PDF — passation agent

**Date** : 2026-05-28 (mise à jour suite : registry, tests TOC multi-profils, YAML titles)  
**Statut** : implémenté ; validation visuelle initiale par le demandeur ; non-régression automatisée TOC  
**Périmètre** : organisation / ordre / présence des sections PDF uniquement (pas de changement métier des calculs ni du contenu des tableaux existants).

---

## 1. Objectif métier

Uniformiser la structure des bilans PDF entre profils (global, thématiques, cas particuliers type agrainage/PNF) avec :

1. **Chiffres clés**
2. **Activité de contrôle** (police administrative uniquement : période, domaines/thèmes/zones, résultats)
3. **Activité par type d’usager** (chapitre dédié, entre contrôles et procédures)
4. **Procédures** (PEJ / PA / PVe — détail procédural **sans** ventilation par type d’usager)
5. **Cartographie**
6. **Annexes**

### Règles validées par le demandeur

- La section **type d’usager** n’est plus un chapitre 4 autonome placé après les procédures : c’est le **chapitre 3**.
- Dans le chapitre 3 : ventilation des **résultats de contrôle** par type (Conforme, Manquement, Infraction, En attente / « Autre résultat » OSCEAN) **+ PEJ + PA** par type d’usager.
- Dans le chapitre 4 (procédures) : **pas** de tableaux « procédures par type d’usager et par domaine/thème » (éviter doublon avec le ch. 3).
- Exceptions : profils à zones (ex. `agrainage`, `pnf`) conservent des sous-sections 2.x spécifiques (analyse par zone, synthèse croisée).
- Pilotage via YAML (`config/presentation/pdf_presentation.yaml`), pas de `if profil == ...` dispersés pour l’ordre.

---

## 2. Identifiants de sections (rétrocompatibilité)

Les **IDs internes** historiques sont conservés ; seuls **ordre**, **titres** et **rendu** changent :

| ID interne | Rôle sémantique | Numérotation PDF cible |
|------------|-----------------|-------------------------|
| `sec1` | Chiffres clés | 1 |
| `sec2` / `sec2_chap` | Chapitre contrôles | 2 |
| `sec21`, `sec22`, `sec22dom`, `sec22theme`, `sec22res` | Sous-parties contrôles | 2.x |
| `sec4` | **Chapitre usagers** (nom historique trompeur) | **3** |
| `sec3`, `sec31`, `sec32`, `sec33` | **Chapitre procédures** | **4**, 4.1, 4.2, 4.3 |
| `sec5` / `sec5map` | Cartographie | 5 |
| `sec6` | Annexes | 6 |

Sous-sections ajoutées pour PEJ/PA usager (TOC niveau 2, IDs locaux) :

- `sec4_pej_usager`
- `sec4_pa_usager`

---

## 3. Ordre canonique (YAML)

Fichier source de vérité : `config/presentation/pdf_presentation.yaml`

### Scope `thematique` (défaut)

```yaml
order: ["sec1", "sec2", "sec21", "sec22", "sec4", "sec3", "sec31", "sec32", "sec33", "sec5", "sec6"]
titles:
  sec2: "2. Activité de contrôle"
  sec4: "3. Activité par type d’usager"
  sec3: "4. Procédures (PEJ, PA, PVe)"
  sec31–sec33: "4.1 …", "4.2 …", "4.3 …"
  sec5: "5. Localisation cartographique des contrôles"
```

### Scope `global`

```yaml
order: ["sec1", "sec2_chap", "sec21", "sec22dom", "sec22theme", "sec22res", "sec4", "sec3", "sec31", "sec32", "sec33", "sec5map", "sec6"]
# + titles alignés sur la numérotation 3 / 4
```

### Profil `agrainage` (override)

```yaml
order: ["sec1", "sec2", "sec21", "sec22", "sec22theme", "sec22res", "sec4", "sec3", "sec31", "sec32", "sec33", "sec5", "sec6"]
titles:
  sec22: "2.2. Résultats des contrôles"
  sec22theme: "2.3. Analyse par zone"
  sec22res: "2.4. Synthèse croisée par zone"
  sec4: "3. Activité par type d’usager"
  sec3: "4. Procédures (PEJ, PA, PVe)"
```

### Profil `types_usager_cible`

- Section usagers = pression de contrôle départementale, renumérotée **« 3. … »** dans le YAML profil.

---

## 4. Pilotage affichage / absence

Résolution : `src/bilans/common/pdf_presentation_config.py`

```
defaults → scopes.<global|thematique> → profiles.<id> → profiles._diffusion_externe (si --diffusion externe)
```

| Mécanisme | Fonction | Usage |
|-----------|----------|--------|
| Ordre + activation sections | `resolve_sections_for_toc`, `is_section_enabled` | `sections.order`, `sections.enabled` |
| Titres | `resolve_section_titles` | `sections.titles` |
| Sous-blocs (tableaux, graphiques) | `is_block_enabled` | `blocks.sec4.show_*`, etc. |
| Placeholders | `should_show_placeholder` | `behavior.missing_data_policy` |

### Nouveaux blocs YAML (chapitre usagers / ID `sec4`)

```yaml
sec4:
  show_table_pej_par_type_usager: true
  show_table_pa_par_type_usager: true
```

---

## 5. Implémentation code

### 5.1 Moteur thématique

**Fichier** : `src/bilans/engine/orchestrateur_profils.py`

- `section_defs` par défaut et variante `agrainage` : titres 3/4 et ordre dans la liste de définition.
- Texte d’intro ch. 2 : renvoie à la **partie 4. Procédures** (plus « partie 3 »).
- `_pdf_section_activite_par_types_usagers` : inchangé sur le fond ; en fin de fonction appel à :
  - `summarize_procedures_par_type_usager(results["proc_par_usager_domaine"])`
  - `add_procedures_par_type_usager_subsection(...)`
- `_render_sec4` : chapitre usagers sans `toc_level` 2.5 (toujours chapitre de niveau I).
- `sec34_registry.render_many` : ordre lu depuis `sections_toc` → **`sec4` avant `sec3`**.
- **Supprimé** dans `_render_sec32` / `_render_sec33` : appels à `_render_proc_par_domaine_theme` pour les tableaux avec colonne `type_usager` (doublon ch. 3).

**Données** (déjà produites en agrégation thématique, inchangées) :

- `proc_par_usager_domaine`, `proc_par_usager_theme`
- `res_bilan_par_type_usager`, `ctrl_par_usager_theme`, etc.

### 5.2 Moteur global

**Fichier** : `src/bilans/engine/generation_pdf_profil.py`

- `section_defs` : ordre `sec4` puis `sec3`, titres 3 / 4 / 4.x.
- Fin de `_render_sec4` : chargement CSV + sous-sections PEJ/PA usager.
- `sec34_order` par défaut : `["sec4", "sec3"]`.

**Fichier** : `src/bilans/engine/agregations_profil.py`

- Export additionnel (même fonction d’agrégation que le thématique, pas de nouvelle formule) :
  - `procedures_global_par_type_usager.csv`  
  - Colonnes : `type_usager`, `nb_pej`, `nb_pa`  
  - Écrit si `type_usager` présent dans les points de contrôle.

### 5.3 Fonctions partagées

**Fichier** : `src/bilans/common/pdf_shared_sections.py`

| Fonction | Rôle |
|----------|------|
| `summarize_procedures_par_type_usager(df)` | `groupby type_usager` sur `proc_par_usager_domaine` |
| `add_procedures_par_type_usager_subsection(builder, summary, …)` | Tableaux PEJ et PA par type d’usager |

### 5.4 Registre sections (squelette)

**Fichier** : `src/bilans/engine/registre_sections_pdf.py` — inchangé (squelette `SectionRegistry` déjà utilisé dans global/thématique). Factorisation complète multi-moteurs **non** faite dans ce lot.

### 5.5 Profil hors périmètre harmonisation stricte

- `synthese_activite_PA_PJ` : moteur dédié `generation_pdf_synthese.py` — structure propre (sec2_1, sec3_1, etc.) **non** migrée.
- `types_usager` (profil dédié `analyses.type_usager: true`) : logique sec22 spécifique conservée.

---

## 6. Tests automatisés

**Fichier** : `tests/unit/test_pdf_presentation_config.py`

- `test_agrainage_pdf_sections_order_and_titles` — ordre sec4 avant sec3, titres 3/4.
- `test_thematique_default_sections_usagers_before_procedures` — `sec4` index < `sec3` index.
- `test_summarize_procedures_par_type_usager` — agrégation PEJ/PA par type.

Commande :

```bash
python -m pytest tests/unit/test_pdf_presentation_config.py tests/unit/test_pdf_report_builder_heading_binding.py -q
```

Résultat au moment de la passation : **28 passed**.

---

## 7. Vérification manuelle effectuée

Validée visuellement par le demandeur sur bilans régénérés (profils non précisés dans le fil ; commandes typiques) :

```bash
python -m bilans --profil global --dept-code 21
python -m bilans --profil agrainage --dept-code 21
```

---

## 8. Limites connues / dette technique

1. **IDs historiques** : `sec3` = procédures, `sec4` = usagers — peut prêter à confusion pour les mainteneurs ; une migration d’IDs (`sec_usagers`, `sec_procedures`) serait un chantier séparé.
2. **Ordre de rendu agrainage** : blocs TUB / zone (`sec22theme`, `sec22res`) sont encore injectés **dans le flux Python** après `sec2_registry`, pas entièrement pilotés par `sections.order` (TOC YAML vs ordre physique peut diverger sur cas limites).
3. **Profil `synthese_activite_PA_PJ`** : structure 6 parties non alignée sur le canon 1–6.
4. **Global sans colonne `type_usager`** : ch. 3 PEJ/PA usager absent (CSV vide) ; comportement attendu.
5. **`feature_registry`** : branché sur `sections.enabled` à la résolution config (hors scope moteur → désactivé sauf surcharge YAML).

---

## 9. Pistes pour la suite

- [x] Étendre l’ordre YAML-driven au chapitre 2 agrainage (`sec22theme`, `sec22res`, registry).
- [x] Tests d’intégration TOC (extraction titres) : agrainage, chasse, global — fixtures `tests/fixtures/pdf_toc_*` (CSV `;`).
- [x] Alias YAML `sec_usagers` / `sec_procedures` + hoist legacy `titles` → `sections.titles`.
- [x] Scopes `global` / `thematique` : `sections.titles` corrigés dans le YAML.
- [x] `feature_registry` → `apply_feature_registry_to_effective` / `is_section_enabled`.
- [x] Documenter dans `docs/TEMPLATE_DEMANDE_CHANGEMENT_PDF.md` la numérotation 3/4.
- [ ] Harmoniser `generation_pdf_synthese.py` sur le canon 1–6 (**hors périmètre** — validé par le demandeur).
- [ ] Renommage complet des IDs internes dans le code Python (**reporté** : alias YAML suffisants pour l’instant).

---

## 10. Fichiers touchés (commit de référence)

| Fichier | Nature du changement |
|---------|----------------------|
| `config/presentation/pdf_presentation.yaml` | Ordre, titres, blocs sec4 PEJ/PA, profils agrainage / thematique / global |
| `src/bilans/common/pdf_presentation_config.py` | Ordre par défaut `sec4` avant `sec3` |
| `src/bilans/common/pdf_shared_sections.py` | PEJ/PA par type d’usager |
| `src/bilans/engine/orchestrateur_profils.py` | Structure, ordre rendu, suppression doublons procédures |
| `src/bilans/engine/generation_pdf_profil.py` | Structure global, ordre, PEJ/PA usager |
| `src/bilans/engine/agregations_profil.py` | Export `procedures_global_par_type_usager.csv` |
| `tests/unit/test_pdf_presentation_config.py` | Non-régression ordre / agrégation / feature_registry |
| `tests/unit/test_pdf_toc_agrainage_integration.py` | TOC agrainage + chasse |
| `tests/unit/test_pdf_toc_global_integration.py` | TOC global |
| `tests/fixtures/pdf_toc/README.md` | Jeux CSV tests (`;`) |
| `src/bilans/common/pdf_toc_inspection.py` | Extraction titres PDF (pypdf) |

**Hors périmètre volontaire** : `scripts/**`, calculs métier des agrégations existantes, contenu des cellules de tableaux.

---

## 11. Contraintes à respecter pour toute évolution suivante

- Ne pas modifier les **formules de calcul** sans validation métier explicite.
- Préserver la **rétrocompatibilité** des profils non concernés (`sections.enabled` / défauts).
- Entrée CLI : `python -m bilans --profil <id>` (pas `scripts/**`).
- Preuve de non-régression : tests unitaires ci-dessus + régénération multi-profils (`global`, `agrainage`, 1 thématique standard).

---

## 12. Références code (points d’entrée)

```text
config/presentation/pdf_presentation.yaml
src/bilans/common/pdf_presentation_config.py    # resolve_*, is_section_enabled, is_block_enabled
src/bilans/common/pdf_shared_sections.py        # add_procedures_par_type_usager_subsection
src/bilans/engine/orchestrateur_profils.py      # _generate_pdf (thématique)
src/bilans/engine/generation_pdf_profil.py      # _generate_pdf_content (global)
src/bilans/engine/agregations_profil.py         # analyse_pej_pa_global
config/profils_bilan/_defaults.yaml             # pdf.adapter: generate_profile_pdf_report
config/profils_bilan/global.yaml
config/profils_bilan/agrainage.yaml
```
