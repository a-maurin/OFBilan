# Organisation du dossier `scripts/`

Ce dossier regroupe les scripts utilitaires du projet, classés par usage :

## 1. `lancement/`
Contient les lanceurs pour démarrer et utiliser OFBilan au quotidien :
- `demarrer_serveur_OFBilan.bat` / `.ps1` / `.sh` : lancement du serveur web et ouverture automatique du navigateur.
- `lancer_cli_OFBilan.bat` / `.sh` : lanceur de la ligne de commande avec l'interpréteur Python approprié.
- `lancer_gui.bat` : raccourci pour démarrer l'interface graphique.
- `lancer_bilans.bat` / `lancer_bilans_qgis.bat` : génération interactive des bilans (avec ou sans cartes adaptatives).
- `generer_cartes.bat` / `parametrer_cartes.bat` / `lancer_production_cartographique.bat` / `lancer_osgeo4w.bat` : production cartographique et paramétrage sous QGIS.

## 2. `deploiement/`
Contient les scripts d'installation, de distribution et de mise à jour :
- `installer_sur_ce_poste.bat` / `.ps1` : configuration du poste local (raccourci Bureau, relais QGIS).
- `installer_pack.bat` : extraction automatique du pack de données et référentiels.
- `preparer_package_deploiement.bat` / `.ps1` : création d'une archive allégée prête pour déploiement.
- `deployer_vers_serveur.bat` / `.ps1` : copie et synchronisation vers le serveur de partage.
- `nettoyer_poste_client.bat` / `.ps1` : purge complète des relais locaux pour simuler un poste vierge.
- `build_pack.py` / `pack_ref_distribution.py` : empaquetage des référentiels pour distribution.

## 3. `donnees/`
Contient les outils de gestion et préparation des données :
- `build_natinf_concordance.py` / `lancer_concordance.bat` : construction de la table de concordance Natinf/SNC.
- `match_snc_natinf.py` / `lancer_match_snc.bat` : appariement et vérification des règles SNC.
- `fetch_sources.py` : synchronisation des sources depuis les partages réseau.
- `download_vendor_assets.py` : téléchargement et contrôle d'intégrité des bibliothèques web locales.
- `restaurer_referentiel.py` : restauration des données de référence.

## 4. `maintenance/`
Contient les scripts d'assurance qualité, de diagnostic et d'outillage développeur :
- `verify.ps1` / `verify.sh` : exécution de la suite de tests automatisés.
- `verify_config_coherence.py` : vérification de la cohérence entre profils YAML et cartes.
- `verify_ref_layout.py` / `verify_ref_layout.ps1` : contrôle de conformité de l'arborescence `ref/`.
- `check_libs.py` : diagnostic de l'environnement Python et des dépendances.
- `run_diag_qgis.bat` / `test_qgis_zorder.py` : diagnostic de l'environnement PyQGIS.
- `test_commentaires_cli.py` : prévisualisation console des blocs de texte.
- `ajouter_entetes_copyright.py` / `ajouter_docstrings_tests.py` : harmonisation du code source.
- `nettoyer_fichiers_obsoletes.py` : nettoyage des artefacts obsolètes.
