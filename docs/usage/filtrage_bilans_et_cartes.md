## Règles de filtrage : bilans vs cartes

Ce document résume les grandes catégories de filtres appliquées :

- côté **moteur profils** (`src/bilans/engine/profile_engine.py`),
- côté **cartes** (`scripts/generateur_de_cartes/production_cartographique.py`).

L’objectif est de garantir une lecture cohérente entre les tableaux / PDF et les cartes.

### Filtres principaux côté bilans thématiques

- **Filtres par mots-clés** (`filter.type = "keywords"`)
  - Colonnes typiques : `theme`, `type_actio`, `nom_dossie`.
  - Utilisé dans les profils génériques (ex. filtrage des thèmes par liste de mots).
- **Filtres agrainage**
  - Fonctions autour de `_filter_agrainage` qui ciblent les contrôles et procédures liés à l’agrainage.
- **Filtres chasse**
  - Fonctions basées sur `est_chasse_point` pour restreindre les points de contrôle au domaine chasse.
- **Filtres procédures**
  - Profils avec `filter.type = "procedures"` qui exploitent `load_pej` / `load_pa` et filtrent sur `ENTITE_ORIGINE_PROCEDURE`, NATINF, etc.
- **Filtres types d’usagers**
  - Utilisation de `serie_type_usager` et de `type_usager_target` (profil `types_usager_cible`) pour ne retenir que certains types d’usagers.

### Filtres principaux côté cartes

Dans `scripts/generateur_de_cartes/production_cartographique.py` :

- **Expressions attributaires QGIS** pour les couches :
  - points de contrôle globaux (`_build_point_ctrl_global_expression`),
  - points agrainage, chasse, procédures, etc.
- Ces expressions filtrent généralement sur :
  - `domaine`, `theme`, `nature_controle`,
  - codes NATINF,
  - codes département, période.

### Alignement des règles

- Les mêmes familles de critères (thème, domaine, type d’usager, NATINF, département, période) sont utilisées :
  - dans les fonctions de filtrage pandas côté bilans,
  - dans les expressions SQL QGIS côté cartes.
- En cas d’évolution d’un profil ou d’un thème :
  - mettre à jour **à la fois** le profil YAML concerné et l’expression QGIS correspondante,
  - vérifier que les résultats agrégés (nombre de contrôles / procédures) restent cohérents entre bilans et cartes.

Ce document sert de base ; pour toute modification importante, compléter ici les règles spécifiques au thème ou au profil impacté.

