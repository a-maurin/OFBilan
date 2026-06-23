# Journal des modifications (Changelog)

Toutes les modifications notables apportées au projet **OFBilan** depuis la version **v0.9.1** sont documentées ci-dessous.

---

## [v1.0.0] - 2026-06-23

### Nouvelle interface graphique (GUI locale)
* **Serveur web local** : Implémentation d'un serveur HTTP léger (`serveur.py` sur le port `8000`) pilotant le moteur Python sous-jacent en arrière-plan de manière asynchrone et isolée.
* **Lanceur Windows** : Création du script d'aide au démarrage `scripts/windows/lancer_gui.bat` qui lance le serveur et ouvre automatiquement le navigateur.
* **Panneau de contrôle web** : Conception d'une interface web moderne et responsive (charte graphique OFB) permettant de configurer l'ensemble des paramètres (dates, échelle géographique, types d'usagers, diffusion).
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
