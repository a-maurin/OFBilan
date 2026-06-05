<RULE[cartes_generation]>

1. Socle Commun (Par Défaut)
4 Cartes Systématiques (Ordre strict) :
Domaines de contrôle : couleur par domaine.
Types d'usagers : couleur par type (jaune pour agriculteurs).
Résultats : rouge (infraction), violet (manquement), rouge/violet (mixte), vert (conforme), gris (autre).
Procédures/PVe : triangle bleu (PEJ), triangle violet (PA), triangle orange (PVe).
Fond & Emprise : IGN scan25. Pochoir dynamique et centrage sur le département.
Données : Filtrées sur la période temporelle sélectionnée.
Règle d'Or (Anti-Hardcoding) : Le moteur génère les 4 cartes par défaut. L'activation, le masquage ou l'ajout de couches spécifiques sont exclusivement pilotés par les fichiers YAML des profils. Aucune condition Python (ex: if profil == 'TUB') pour l'affichage.
2. Dérogations Pilotées par YAML
Agrainage : Ajout couches vecteurs zone TUB. Affiche uniquement cartes 3 (Résultats) et 4 (Procédures).
PNF : Pochoir et centrage sur polygone "AOA". Ajout couche vecteur "cœur de parc" (bordure verte).
TUB : Pochoir et centrage sur polygone "zone à risque". Ajout couches vecteurs zone TUB. Affiche uniquement cartes 1, 3 et 4.
3. Axes d'Amélioration Complémentaires
Délégation du Style (QML / YAML) : Externaliser la symbologie (couleurs, formes, tailles) dans des fichiers de style QGIS (.qml) ou un dictionnaire central (profils_cartes.yaml) pour éviter de surcharger le script Python de constantes visuelles.
Générateur de Rendu Unique : Créer une fonction de rendu générique (render_map(extent_layer, stencil_layer, data_layers, style)) où les paramètres sont directement injectés depuis la lecture du YAML.
Filtrage Spatial en Amont : Découper (clip) les géométries en amont du moteur de rendu QGIS pour alléger le traitement mémoire lors de la génération de l'image.
Parallélisation du Rendu : Si le thread QGIS local le permet, exécuter l'export PNG des 4 cartes en parallèle puisqu'elles partagent la même emprise. </RULE[cartes_generation]>