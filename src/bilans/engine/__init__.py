"""Moteur unique bilans : dispatch profils global / thématiques."""

from bilans.engine.profiles import list_profiles, resolve_profile_ids
from bilans.engine.global_backend import run_global_backend, analyse_controles_global
from bilans.engine.global_core import analyse_pej_pa_global, analyse_pve_global
from bilans.engine.global_pdf import generate_global_pdf_report
from bilans.engine.section_registry import SectionRegistry
from bilans.engine.unified_engine import run_profiles_batch, run_thematic, run_unified

__all__ = [
    "list_profiles",
    "resolve_profile_ids",
    "run_profiles_batch",
    "run_thematic",
    "run_unified",
    "SectionRegistry",
    "run_global_backend",
    "analyse_controles_global",
    "analyse_pej_pa_global",
    "analyse_pve_global",
    "generate_global_pdf_report",
]
