## Production des cartes bilans agrainage / chasse

**Référence de présentation :** la carte utilisée dans `old/bilan_agrainage_Cote_dOr.pdf` (section V. Cartographie) sert de modèle. Le layout QGIS « Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or » doit reproduire cette présentation (bandeau titre, carte, légende, échelle, pied de page sources/réalisation).

### 1. Pré-requis

- QGIS / OSGeo4W installé pour l'utilisateur (par ex. dans `%LOCALAPPDATA%\Programs\OSGeo4W`).
- Le projet QGIS `sd21_tout.qgz` placé dans `Bilans_production/ref/sig/`.
- Les données (PVe, PJ, points de contrôle, etc.) correctement branchées dans ce projet.
- **Bandeau logos** : pour afficher le bandeau République française + OFB en haut des cartes, placer l’image dans `Bilans_production/ref/modele_ofb/word/media/image5.jpg` (ou `image5.png`). Même fichier que pour les bilans PDF (référence OFB).

### 2. Lancer l'outil de production

À la racine de `Bilans_production`, **trois batch** sont disponibles :

- **parametrer_cartes.bat** — ouvre **directement** la fenêtre de configuration des couches et de la symbologie (équivalent `production_cartographique.py --gui`). Utiliser ce batch pour configurer les profils de cartes avant de générer.
- **generer_cartes.bat** — demande la période, le département et le type de carte, puis **lance la génération** en mode non interactif à partir des réglages enregistrés. Choix proposés : 1 = agrainage, 2 = chasse, 3 = piégeage, 4 = types usagers, 5 = procédures PVe, 6 = toutes.
- Les scripts du générateur restent dans `old/scripts/generateur_de_cartes/` ; ils sont invoqués par ces batch.

### 3. Configurer les couches et la symbologie

1. Lancer **parametrer_cartes.bat** pour ouvrir la fenêtre « Configuration des couches – Production cartographique ».
2. Dans cette fenêtre :
   - choisir le **profil** en haut à gauche (un profil par type de bilan : agrainage, chasse, piégeage, global, etc.) ;
   - dans la liste de gauche, **cocher les couches à afficher** sur la carte ;
   - sélectionner une couche pour afficher ses réglages à droite :
     - *Texte de légende* : texte affiché dans la légende. Ce libellé est appliqué automatiquement à la légende du layout à chaque génération — renseigner des libellés clairs (ex. « Infractions relevées par PVe », « Points de contrôle conformes ») pour une légende lisible.
     - *Type de données* : PVe, PJ, points de contrôle… ;
     - *Type de carte* : couleur par zone / points au centre des zones (pour les polygones) ;
     - *Type de représentation* : même symbole, couleurs graduées, couleurs par catégorie ;
     - *Couleur, taille, forme du symbole*.
3. Cliquer sur **« Enregistrer la configuration »** pour mettre à jour `config_cartes.py`.

Exemples de profils possibles (selon la configuration) :

- `agrainage` : carte bilans agrainage ;
- `chasse` : carte bilans chasse ;
- `piegeage` : carte bilans piégeage ;
- `global_usagers` : carte du bilan global montrant les contrôles par types d’usagers ;
- `procedures_pve` : carte dédiée aux procédures judiciaires et PVe.

### 4. Générer les cartes

1. Vérifier que la configuration a été enregistrée via **parametrer_cartes.bat**.
2. Lancer **generer_cartes.bat** : saisir la période, le département et le type de carte (1 = agrainage, 2 = chasse, 3 = piégeage, 4 = types usagers, 5 = procédures PVe, 6 = toutes). La génération s’exécute sans ouvrir la fenêtre de paramétrage.
3. Les cartes sont exportées dans `Bilans_production/out/generateur_de_cartes/` au format PNG ou JPEG selon le paramétrage.

### 5. Messages et diagnostics

- Si une couche mentionnée dans la configuration n'existe pas dans le projet QGIS,
  un message d'avertissement est affiché dans la console.
- Si les champs nécessaires aux filtres (PVe, PJ, points de contrôle) sont manquants,
  la couche est ignorée pour ce filtre et un message explicite est inscrit dans les logs.
- Si le bandeau logos n’apparaît pas, vérifier la présence de `ref/modele_ofb/word/media/image5.jpg` (ou `.png`).

