========================================================================
DOSSIER LIB/ — BIBLIOTHÈQUES PORTABLES OFBILAN
========================================================================

Ce dossier accueille les dépendances en Python pur non incluses
nativement dans l'interpréteur Python standard de QGIS :
- odfpy / defusedxml : lecture des classeurs ODS (ex. exports PEJ).
- pypdf : manipulation et contrôle des documents PDF.

Règles d'utilisation :
1. Ce dossier est injecté en dernière position dans sys.path (sys.path.append).
2. Ne jamais y déposer des bibliothèques déjà fournies par QGIS
   (ex. numpy, pandas, shapely, pyogrio, gdal) afin d'éviter tout conflit binaire.
3. Seul l'administrateur ou référent technique OFBilan met à jour ce dossier.
========================================================================

