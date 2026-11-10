# Journal des modifications (Changelog)

Toutes les modifications notables apportées au projet **OFBilan** depuis la version **v0.9.1** sont documentées ci-dessous.

---

## [v1.0.7] - 2026-08-08 : Bilan PNF v2, Pochoirs départementaux & Explorer dynamique

### Découplage des référentiels et résilience cartographique
* **Découplage strict PNF et TUB** : Séparation complète du chargement des communes du Parc national de forêts et du zonage sanitaire TUB dans le moteur de calcul. L'activation de l'option PNF n'exige plus la présence du fichier tub_communes.csv.
* **Tolérance aux fichiers absents (fail-soft)** : Remplacement des erreurs bloquantes par un repli propre (ensemble vide et journalisation d'un avertissement) pour les zonages secondaires.
* **Distribution des tables administratives** : Intégration directe des tables de référence tub_communes.csv et communes_PNF.csv au suivi Git du projet.
* **Fiabilisation du pont QGIS et résilience PDF** : Correction du chemin vers le lanceur batch cartographique, support des environnements récents sous Qt6 et isolation complète de la chaîne d'édition PDF pour garantir la production du rapport même en cas d'absence ou d'échec de la cartographie.

### Explorer Web et Cartographie Dynamique
* **Calibrage dynamique du choroplèthe** : Calcul dynamique de l'échelle et de la légende (min/max) des cartes choroplèthes et heatmaps selon les entités visibles dans le viewport.
* **Cascade de géolocalisation des PEJ (4 niveaux)** : Intégration d'une cascade de géolocalisation à 4 niveaux pour les Procédures d'Enquête Judiciaire, affichage de l'avis de précision dans les infobulles et bandeau d'information dédié aux PEJ non géolocalisées.
* **Bandeau cartographique & Pilule d'information** : Refonte ergonomique du bandeau cartographique avec pilule d'information flottante en mode plein écran.
* **Rendu Web & Impression** : Optimisation de l'affichage des cartes choroplèthes, de l'impression PDF web et de l'encodage UTF-8 des infobulles.
* **Filtrage des profils** : Masquage dynamique et filtrage backend des profils PDF dans l'Explorer Web.

### Édition PDF et Rapports
* **Restructuration Régionale PNF v2** : Bilan complet PNF v2 (partie consolidée PNF et fiches synthétiques départementales Côte-d'Or 21 / Haute-Marne 52).
* **Modernisation des Titres & En-têtes** : Dynamisation des titres de rapports et modernisation visuelle de l'en-tête de brochure PDF.
* **Harmonisation Cartographique & Symboles** : Calibrage des symboles cartographiques à 1.2 mm, fiabilisation du chargement des cartes fraîches et correction du bug `layout` dict (brochure forcée).
* **Gabarit SRP R27 & Diffusion Externe** : Bascule de la diffusion externe par défaut et ajustements visuels du gabarit SRP R27.
* **Performance CRS** : Optimisation des reprojections spatiales lors de l'édition des bilans PDF.

### Référentiel & Données
* **Shapefile 127 Communes PNF** : Prise en compte du référentiel `127_communes_AOA_et_statuts_adhesion.shp` pour l'attribution des communes aux zones PNF (Cœur PNF vs Aire d'adhésion avec fallback `null`).
* **Pochoirs départementaux dynamiques** : Découpage et masquage spatial par département (`pochoir_sdXX`), marquage des cartes par tag département et adaptation dynamique des libellés.
* **Consolidation PNF & Restrict Geo** : Unification de la détection `restrict_geo` et consolidation globale du profil PNF.

### Architecture, Qualité du Code & Sécurité
* **Autonomisation locale des assets Web GUI (Zero CDN / Zero Data Leak)** : Isolation complète des dépendances front-end (`Leaflet`, `Chart.js`, `Driver.js`, `MarkerCluster`, `html2canvas`) désormais hébergées en local (`core/web/vendor/`) avec contrôle d'intégrité SHA-256 (`scripts/download_vendor_assets.py`), garantissant un fonctionnement 100% autonome en réseau restreint/hors-ligne (*air-gapped*) sans fuite de métadonnées.
* **Gouvernance YAML-First** : Fiabilisation et alignement YAML-first du moteur d'édition.
* **Liaison des En-têtes PDF** : Liaison automatique d'en-têtes pour supprimer les titres orphelins.
* **Suite de Tests Unitaires** : Correction des régressions (gabarits, SQL Corse 2A/2B, CLI entry point) et support PyArrow.

---

## [v1.0.6] - 2026-07-31 : Explorer Web interactif, Commentaires auto PDF & Correctifs

### Explorer Web et Cartographie Dynamique
* **Indicateurs KPI & Donuts interactifs** : Transformation des cartes d'indicateurs clés (Contrôles, PEJ, PA, PVe, Usagers) et des graphiques donuts (Résultats, Types d'usager) en boutons de filtrage dynamique cliquables sur la carte Leaflet, la légende et le tableau de données.
* **Filtrage par tranche de graphique** : Filtrage ciblé au clic sur une tranche spécifique des donuts (ex: usager *Agriculteur* ou résultat *Conforme* / *Infraction* / *En attente*).
* **Refonte & Réactivation Légende** : Gestion dynamique et réactivation à la volée des entités/usagers masqués depuis les libellés de la légende interactive de la carte.
* **Procédures PEJ dans le profil PNF** : Vérification et prise en compte complète des Procédures d'Enquête Judiciaire (PEJ) dans l'explorateur et la cartographie PNF.
* **Correctif Infobulles / Popups** : Résolution du dysfonctionnement qui empêchait l'affichage des popups interactifs au clic sur les entités de la carte.

### Édition PDF et Rapports
* **Profil PNF v2 (Structure Régionale à 2 Parties)** : Restructuration du bilan complet multi-pages `pnf_v2` suivant l'organisation régionale à 2 parties (Partie 1 : Bilan consolidé PNF avec Carte N°1 des volumes par commune et tracé vert du Cœur de parc ; Partie 2 : Fiches synthétiques 1 page pour la Côte-d'Or 21 et la Haute-Marne 52 filtrées sur le périmètre PNF).
* **Compatibilité Gabarits & Surcharges** : Déclaration de `pnf_v2` dans `profils_compatibles` du gabarit `pnf_v2.yaml` et correction du `DeprecationWarning` GeoPandas (`union_all`).
* **Commentaires automatiques** : Système de commentaires introductifs auto-générés s'intercalant avant les tableaux et graphiques (`commentaires_auto.py`).
* **Gabarits YAML configurables** : Fichier `config/presentation/commentaires_auto.yaml` permettant d'éditer facilement les conditions et templates de texte sans coder (support des balises HTML `<b>`).
* **Accords & Formatage FR** : Formatage numérique selon les normes françaises (`1 250`, `31 %`) et gestion automatique des accords singulier/pluriel.
* **Pilotage & Surcharges** : Interrupteur global dans `pdf_presentation.yaml`, drapeaux CLI (`--commentaires-auto` / `--no-commentaires-auto`) et support des surcharges manuelles (`custom_text`).
* **Mise en page anti-orphelins** : Insertion souple avec `keepWithNext=True` et espacement compact (1.5 mm) pour éviter les grands espaces vides et préserver les contraintes du format Brochure.

### Données & Core
* **Correctif GeoPandas CRS** : Gestion propre du recalcul des centroïdes en coordonnées géographiques (`EPSG:4326`) pour éliminer les avertissements de précision spatiale.

### Outils & Tests
* **Prévisualisation console** : Script `scripts/test_commentaires_cli.py` pour tester instantanément le rendu des textes sans générer de PDF.
* **Tests unitaires** : Ajout et mise à jour des suites de tests (`tests/test_commentaires.py`).

---

## [v1.0.5] - 2026-07-24 : Bilans régionaux, Moteur PDF mutualisé & Purge Legacy

### Édition PDF et Bilans Régionaux
* **Refonte des bilans régionaux** : Intégration du dashboard macro synthétique, des cartes de chaleur (heatmaps) et des fiches départementales (1-page & double visuel).
* **Gabarits de présentation** : Introduction du système de gabarits de présentation PDF déclinables et configurables par service/organisation (`chargeur_gabarits.py`).
* **Mutualisation PDF & LayerResolver** : Unification du moteur d'exportation PDF et résolution dynamique des couches QGIS en fonction des rôles métiers (`LayerResolver`).
* **Feuilles de style & Impression** : Optimisation des rendus et ajustement de `print.css` pour l'export dashboard.

### Explorer Web et Interface
* **Cartographie & Explorer** : Améliorations de l'affichage (légende, clustering des points), support de la multi-sélection et ajout du bouton de copie.
* **Filtres & Données** : Correctifs sur les filtres thématiques (zones PNF/TUB, détection PVe hors couches) et corrections des géométries/CRS.
* **UI & Paramètres** : Correction du blocage d'enregistrement des paramètres (erreur de zoom).

### Core, Robustesse et Tests
* **Purge Legacy SD21** : Suppression intégrale du code obsolète SD21 et modularisation complète de l'orchestrateur.
* **Dépendances & Fallbacks** : Résolution des conflits d'importation (GeoPandas/Pandas), gestion robuste des fallbacks OGR (`osgeo.gdal`) et ajout à l'auto-installeur.
* **Tests unitaires** : Alignement et mise à jour globale de la suite de tests unitaires et d'intégration.

---

## [v1.0.4] - 2026-07-16 : Export PDF dynamique & Améliorations Explorer

### Édition PDF et Rapports
* **Export dynamique** : Nouveau moteur d'export PDF intégré directement à l'Explorer Web.
* **Mise en page** : Correction des feuilles de style (`print.css`) pour supprimer les pages vides superflues en fin de document.

### Explorer et Graphiques
* **Analyse multi-échelles** : Support de l'analyse sur des codes géographiques multiples (échelle nationale).
* **Cartographie** : Clustering des points respectant désormais strictement les limites administratives.
* **Graphiques** : Masquage conditionnel des légendes N-1 et ajustement de l'espacement des barres.
* **UI** : Restauration des boutons dynamiques de l'interface.

### Serveur et Données
* **Stabilité** : Correction d'incohérences entre la CLI et la GUI, optimisation de la gestion des données en arrière-plan.

---

## [v1.0.3] - 2026-06-29 : Migration vers QGIS et architecture de plugin

Cette version marque une transition majeure : le projet passe d'un outil autonome à un véritable plugin QGIS, exploitant l'environnement Python de QGIS.

### Architecture et intégration QGIS
* **Plugin QGIS** : Structuration du projet en tant que plugin QGIS pour une intégration native.
* **Environnement Python QGIS** : Utilisation de l'interpréteur Python fourni par QGIS pour s'affranchir des conflits de dépendances externes.
* **Script de lancement** : Amélioration de `lancer_serveur_autonome.bat` pour détecter et utiliser correctement Python QGIS.

### Interface et Serveur
* **Explorer par défaut** : L'interface web s'ouvre désormais directement sur la vue "Explorer".
* **Gestion du navigateur** : Prévention des ouvertures multiples d'onglets lors du démarrage.
* **Arrêt du serveur** : Arrêt immédiat et propre du serveur local sans demande de confirmation.

### Documentation et Distribution
* **Documentation à jour** : Le `README.md` et `carte_code.md` reflètent la nouvelle architecture plugin.
* **Packaging** : Scripts de déploiement (`installer_pack.bat`) et `.gitignore` ajustés pour le format plugin.


## [v1.0.2] - 2026-06-28 : Optimisations de l'Explorer et de la génération PDF

Cette version se concentre sur l'amélioration des performances de l'interface "Explorer", la correction de bugs serveur, et l'enrichissement des fonctionnalités cartographiques.

### Explorer et Visualisation
* **Séparation des couches cartographiques** : Division des cartes en trois couches distinctes ("Contrôles", "PA/PEJ", et "PVe").
* **Optimisation des performances** : Amélioration significative du temps de chargement initial.
* **Correction des filtres** : 
  * Résolution des problèmes de détection des PEJ pour le profil "Produits phytopharmaceutiques".
  * Correction de l'outil de filtrage "type d'action".
* **Ajustements UI** : Renommage de "Localisation des contrôles" en "Localisation des données" et correction du rognage CSS du bouton "Édition PDF".

### Serveur web et Démarrage
* **Lancement intelligent du navigateur** : Le script `lancer_gui.bat` attend désormais la fin du préchargement en mémoire avant d'ouvrir le navigateur.
* **Stabilité du serveur** : Gestion de la requête `favicon.ico` pour éviter les erreurs de logs et de threads.

### Génération PDF, Cartographie et Profils
* **Cartes N-1** : Prise en charge des cartes de l'année précédente dans le moteur d'export.
* **Profils thématiques** : Implémentation du profil d'analyse PPP et de la structure de rapport régionale associée.
* **Fiabilisation des tests (CI)** : Correction des assertions de casse et résolution de l'erreur du profil "sécheresse" désactivé.

### Documentation
* **Mise à jour du README** : Description exhaustive des fonctionnalités actuelles d'exploration dynamique et de génération de rapports PDF.

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
