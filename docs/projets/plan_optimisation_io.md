# Optimisation des Chargements de Données (I/O)

## 1. Objectifs
Réduire drastiquement le temps total d'exécution en évitant les accès disques redondants lors des appels successifs aux fonctions `load_*`.

## 2. Stratégie Proposée (Patch Minimal & RAM Optimisée)
Approche : **Cache sur données brutes + Filtrage dynamique** (hybride Option B).

* **Séparation I/O / Filtrage** : Création de méthodes privées (ex: `_read_raw_point_ctrl(root)`) chargées de localiser et lire le fichier (I/O pur).
* **Mise en Cache** : Application de `@functools.lru_cache(maxsize=4)` sur ces sous-fonctions.
* **Filtrage (Business Logic)** : Les fonctions publiques actuelles (`load_point_ctrl`, etc.) feront appel à ces méthodes privées en cache, cloneront les données (`df = raw_df.copy()`) et appliqueront le filtrage (échelles, dates). Cela évite de saturer la RAM avec de multiples versions filtrées d'un même jeu de données.
* **Invalidation** : Création d'une fonction publique globale `vider_cache_chargeurs()` qui appellera `.cache_clear()` sur les fonctions de lecture, permettant de vider la RAM explicitement entre deux gros lots si nécessaire.

## 3. Plan de Découpage (Lots)
- [x] **Lot 1** : Diagnostic et proposition architecturale.
- [ ] **Lot 2** : Refactoring chirurgical dans `src/bilans/common/chargeurs_donnees.py` (création des `_read_raw_*`, application du `lru_cache`, adaptation des `load_*`).
- [ ] **Lot 3** : Ajout de la fonction `vider_cache_chargeurs()` et tests de cohérence locaux.

## 4. Point de Validation
Merci de valider ce plan d'action pour déclencher le Lot 2.
