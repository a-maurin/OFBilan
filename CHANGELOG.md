# Journal des modifications (Changelog)

Toutes les modifications notables apportées au projet **OFBilan** depuis la version **v0.9.1** sont documentées ci-dessous.

---

## [v1.0.1] - 2026-06-24 : Visualisation cartographique interactive (Explorer) & Autocomplétion des filtres

Cette version apporte des fonctionnalités de visualisation de données et améliore l'expérience utilisateur dans la saisie des filtres.

### Visualisation interactive (OFBilan Explorer)
* **Cartographie interactive (Leaflet.js)** : Intégration d'une carte dynamique affichant précisément les points de contrôle OSCEAN géolocalisés.
* **Tableaux de bord dynamiques (Chart.js)** : Visualisation directe de la répartition des résultats de contrôle et du Top 5 des domaines d'activité les plus contrôlés.
* **API de données unifiée** : Exposition d'un point de terminaison HTTP `POST /api/data` sécurisé pour interroger et filtrer à la volée les données OSCEAN chargées en mémoire.
* **Correction des statistiques (PA)** : Alignement du calcul des procédures administratives de l'Explorer avec la logique métier du moteur (`points_as_pa_lignes`).

### Ergonomie de l'interface (GUI)
* **Recherche et sélection intuitive** : Remplacement des champs texte bruts par des comboboxes de recherche dynamique avec autocomplétion pour les codes géographiques (départements, régions, BMI) et types d'usagers.
* **Menu de navigation partagé** : Insertion d'un onglet de navigation fluide entre la génération de bilans et l'exploration de données.

### Outils de distribution
* **Packaging automatisé** : Script utilitaire `tools/build_pack.py` pour assembler l'archive ZIP de distribution contenant la configuration et les référentiels géographiques.

### Correction de bug : 
* **Fiabilisation de la gestion des codes département à 3 chiffres** : 
Les services ultramarins correctement pris en compte.

---

## [v1.0.0] - 2026-06-23 : Interface graphique (GUI) & flexibilité cartographique

### Nouvelle interface graphique (GUI locale)
* **Serveur web local** : Implémentation d'un serveur HTTP léger (`serveur.py` sur le port `8000`) pilotant le moteur Python sous-jacent en arrière-plan de manière asynchrone et isolée.
* **Lanceur Windows** : Création du script d'aide au démarrage `scripts/windows/lancer_gui.bat` qui lance le serveur et ouvre automatiquement le navigateur.
* **Panneau de contrôle web** : Conception d'une interface web moderne et dynamique (charte graphique OFB) permettant de configurer l'ensemble des paramètres (dates, échelle géographique, types d'usagers, diffusion).
* **Recherche de profils** : Ajout d'une zone de saisie interactive avec autocomplétion pour filtrer et sélectionner les profils de bilans parmi les 35+ modèles disponibles.
* **Console temps réel** : Intégration d'un terminal en direct affichant les logs du moteur, couplé à une barre de progression dynamique.
* **Actions post-génération** : Ajout de boutons interactifs pour ouvrir directement le PDF généré ou explorer le dossier de sortie via l'explorateur du système d'exploitation.

### Améliorations de l'intégration cartographique
* **Sélection granulaire des cartes** : Ajout d'un panneau d'options dans la GUI permettant d'inclure uniquement certaines des cartes par défaut (*Domaines*, *Résultats*, *Usagers*, *Procédures*).
* **Cartes personnalisées** : Possibilité d'intégrer des fichiers PNG externes au catalogue en renseignant leur chemin absolu sur le disque.
* **Assouplissement des règles de validation** : Les cartes personnalisées externes contournent automatiquement le contrôle strict de correspondance de code département.

### Robustesse et non-interactivité du moteur
* **Désactivation de l'interactivité** : Lancement de la CLI avec `stdin=subprocess.DEVNULL` pour bypasser de manière transparente les menus de choix interactifs.
* **Contrôle d'ouverture** : Ajout de l'argument `--no-open` au point d'entrée principal CLI pour désactiver l'ouverture automatique du PDF à la fin du traitement.
* **Gestion des encodages Windows** : Forçage de `PYTHONIOENCODING=utf-8` et remplacement des caractères non décodables pour éliminer les plantages d'encodage système sur Windows.
* **Optimisation des logs** : Désactivation de l'animation textuelle de chargement (spinner) lorsque la sortie standard n'est pas connectée à un terminal physique (non-TTY).
