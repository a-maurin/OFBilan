"""Règles de ventilation temporelle (mode ``auto``)."""

from __future__ import annotations

# Bornes inclusives : ≤ 1 an civil (366 j max) → hebdomadaire ; ≥ 2 ans → trimestrielle.
VENTILATION_JOURS_UN_AN = 366
VENTILATION_JOURS_DEUX_ANS = 730


def resolve_ventilation_auto(duree_jours: int, *, seuil_jours: int = 366) -> str:
    """Ventilation en mode ``auto`` selon la durée de la période d'analyse (en jours).

    - ≤ 1 an (366 j) : hebdomadaire (6 mois et 1 an exact inclus)
    - entre 1 an et 2 ans : mensuelle
    - ≥ 2 ans (730 j) : trimestrielle (2 ans exact inclus)
    - au-delà du ``seuil_jours`` du profil (si ≥ 2 ans) : annuelle
    """
    if duree_jours <= VENTILATION_JOURS_UN_AN:
        return "hebdomadaire"
    if duree_jours < VENTILATION_JOURS_DEUX_ANS:
        return "mensuelle"
    if seuil_jours >= VENTILATION_JOURS_DEUX_ANS and duree_jours > seuil_jours:
        return "annuelle"
    return "trimestrielle"
