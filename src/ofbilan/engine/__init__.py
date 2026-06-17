"""API publique du moteur profilé des bilans."""

from ofbilan.engine.catalogue_profils import list_profiles, resolve_profile_ids
from ofbilan.engine.registre_sections_pdf import SectionRegistry
from ofbilan.engine.execution_lots_profils import run_profile, run_profiles_batch

__all__ = [
    "list_profiles",
    "resolve_profile_ids",
    "run_profile",
    "run_profiles_batch",
    "SectionRegistry",
]
