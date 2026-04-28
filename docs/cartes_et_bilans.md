## Cartes et bilans : convention de nommage

Les bilans PDF intègrent des cartes pré-générées stockées dans `out/generateur_de_cartes`.

### Nom des fichiers de cartes

- **Format général** : `carte_<map_id>.png`
- Exemples usuels :
  - `carte_agrainage.png`
  - `carte_chasse.png`
  - `carte_global_usagers.png`
  - `carte_procedures_pve.png`

Pour le profil `types_usager_cible`, le `map_id` est construit à partir de la
sélection d’usagers (ex. `carte_Agriculteur_Collectivite.png`).

### Recherche des cartes côté code

- Dans `scripts/common/carte_helper.py` :
  - `find_map(profile_id)` cherche successivement :
    - `out/generateur_de_cartes/carte_<profile_id>.png`,
    - `out/generateur_de_cartes/<profile_id>.png`,
    - puis tout fichier `*<profile_id>*.png`.
  - `find_maps_for_bilan("bilan_global")` agrège les cartes standards du bilan
    global : `agrainage`, `chasse`, `global_usagers`, `procedures_pve`.

- Dans `python -m bilans` (CLI officielle) :
  - `ensure_maps("bilan_global", ...)` est appelé avant le bilan global,
  - `ensure_maps_for_profiles([...], ...)` est appelé pour les bilans thématiques.

### Bonnes pratiques

- Lors de l’ajout d’un nouveau profil de carte :
  - choisir un `map_id` explicite et stable (sans espaces),
  - générer les cartes sous la forme `carte_<map_id>.png`,
  - si nécessaire, mettre à jour le mapping dans `find_maps_for_bilan`.
- En cas de carte manquante :
  - le bilan continue à être généré ; un warning est simplement émis dans la
    console, sans bloquer l’exécution.

