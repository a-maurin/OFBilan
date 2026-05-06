"""API publique du moteur profilé des bilans."""

from bilans.engine.catalogue_profils import list_profiles, resolve_profile_ids
from bilans.engine.registre_sections_pdf import SectionRegistry
from bilans.engine.execution_lots_profils import run_profile, run_profiles_batch

__all__ = [
    "list_profiles",
    "resolve_profile_ids",
    "run_profile",
    "run_profiles_batch",
    "SectionRegistry",
]
