========================================================================
DOSSIER LIB/ — BIBLIOTHÈQUES PORTABLES OFBILAN
========================================================================

Ce dossier est destiné à accueillir d'éventuelles dépendances Python pures
(wheels décompressés ou modules .py) qui ne sont pas incluses nativement
dans l'interpréteur Python de QGIS (ex: odfpy).

RÈGLES D'UTILISATION :
1. Ce dossier est injecté en DERNIÈRE position dans sys.path (sys.path.append).
2. Ne JAMAIS y déposer des bibliothèques déjà fournies par QGIS
   (ex: numpy, pandas, shapely, pyogrio, gdal) afin d'éviter tout conflit binaire.
3. Seul l'administrateur / référent technique OFBilan dépose ou met à jour
   les modules dans ce dossier sur le partage réseau.
========================================================================
