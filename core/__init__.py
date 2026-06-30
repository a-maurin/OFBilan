"""Package principal pour la génération des bilans."""

import warnings

# --- CONFIGURATION GLOBALE PANDAS ---
# Solution pérenne pour désactiver le backend PyArrow pour les chaînes de caractères.
# Dans l'environnement QGIS (Pandas 2.1+), PyArrow est souvent activé par défaut, mais la
# version de PyArrow fournie manque de certaines fonctionnalités regex (ex: replace_substring_regex).
# En forçant le mode "python", Pandas utilisera le moteur natif (module re) pour toutes les séries.
try:
    import pandas as pd
    
    # Pandas 2.0+
    if hasattr(pd.options.mode, "string_storage"):
        pd.options.mode.string_storage = "python"
        
    # Option future pour Pandas 2.1+
    if hasattr(pd.options.future, "infer_string"):
        pd.options.future.infer_string = False
except ImportError:
    pass
except Exception as e:
    warnings.warn(f"Impossible de configurer globalement le backend string de Pandas : {e}")
