# Plan d'Architecture : Pilotage Hybride de la Cartographie (YAML + QGIS)

## 1. Contexte et Objectif
Actuellement, la mise en page des cartes QGIS est un mélange entre des positions codées en dur dans le fichier `.qgz` natif et des positions surchargées dynamiquement par Python.

**Objectif** : Passer à une architecture 100% "Hybride" où :
- **QGIS (`.qgz`)** agit uniquement comme une bibliothèque de styles (définition des polices, couleurs, formes SVG, étiquettes).
- **Le YAML (`layout_defaults.yaml`)** agit comme le "metteur en scène" qui dicte la position (X, Y) et la taille (Largeur, Hauteur) absolues de chaque élément.

## 2. Approche Technique : Le dictionnaire universel `extra_items`
Au lieu de modifier le code Python chaque fois qu'un nouvel élément graphique (logo, bandeau, flèche du nord) est ajouté à la carte, nous allons introduire un système de liaison dynamique basé sur l'**ID de l'élément QGIS**.

### 2.1 Modification du modèle de données (Python)
Dans `src/bilans/cartographie/config_cartes_model.py`, la classe `LayoutTemplateConfig` sera étendue :
```python
@dataclass
class LayoutTemplateConfig:
    # ... (existant)
    # NOUVEAU : Dictionnaire pour contrôler n'importe quel élément par son ID
    extra_items: Dict[str, LayoutItemRectConfig] = field(default_factory=dict)
```

### 2.2 Modification de la configuration (YAML)
Dans `src/bilans/cartographie/param/layout_defaults.yaml`, nous ajouterons la clé `extra_items` aux gabarits existants (ex: `ratio_141`).
Exemple :
```yaml
templates:
  ratio_141:
    # ... (existant)
    extra_items:
      "fleche_nord":
        x_mm: 5.0
        y_mm: 110.0
        width_mm: 15.0
        height_mm: 15.0
      "bandeau_bas":
        x_mm: 0.0
        y_mm: 140.0
        width_mm: 210.0
        height_mm: 9.0
```

### 2.3 Mise à jour du moteur de rendu (`layout_defaults.py`)
Dans la fonction principale `apply_layout_defaults`, un mécanisme itératif sera ajouté :
```python
    # Application des positions depuis extra_items
    for item_id, rect_cfg in template.extra_items.items():
        item = layout.itemById(item_id)
        if item is not None and rect_cfg.width_mm > 0:
            _layout_item_set_rect(item, rect_cfg)
        else:
            logger.debug(f"Élément extra_items ignoré ou introuvable : {item_id}")
```
*Note : Il faudra également nettoyer le code Python actuel (ex: la rustine de décalage automatique `delta_y` que nous avions mise en place) puisqu'il deviendra obsolète.*

## 3. Prérequis dans QGIS
Pour que cette architecture fonctionne, il y a une seule règle stricte à respecter côté QGIS :
**Chaque élément devant être piloté par le YAML (la flèche du nord, le rectangle du bandeau, la zone de texte) doit posséder un identifiant ("Item ID") unique et fixe dans QGIS.**

## 4. Étapes de validation du Lot
1. **Implémentation** : Mise à jour des 3 fichiers (`config_cartes_model.py`, `layout_defaults.py`, `layout_defaults.yaml`).
2. **Identification** : Ouvrir le projet `.qgz` pour relever les ID exacts de la flèche du nord et du bandeau.
3. **Vérification** : Génération d'une carte (ex: 21) pour valider que le placement répond strictement aux coordonnées du YAML.
