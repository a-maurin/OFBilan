"""Façade moteur unique pour le backend global."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from bilans.common.loaders import (
    ensure_insee_from_communes_shp,
    load_pa,
    load_pej,
    load_point_ctrl,
    load_pve,
)
from bilans.common.ofb_charte import Spinner
from bilans.engine.global_core import (
    analyse_annuelle_global,
    analyse_controles_global as analyse_controles_global_impl,
    analyse_mensuelle_global,
    analyse_pej_pa_global,
    analyse_pve_global,
    analyse_trimestrielle_global,
)
from bilans.engine.global_pdf import generate_global_pdf_report
from bilans.paths import get_out_dir

_ROOT = Path(__file__).resolve().parents[3]
VENTILATION_TYPE_GLOBAL = "auto"
VENTILATION_SEUIL_JOURS_GLOBAL = 366


def resolve_ventilation_mode_global(date_deb: pd.Timestamp, date_fin: pd.Timestamp) -> str:
    """Détermine le mode global de ventilation temporelle."""
    vent_type = str(VENTILATION_TYPE_GLOBAL).strip().lower()
    duree_jours = int((date_fin - date_deb).days)
    if duree_jours < 183:
        return "mensuelle"
    if vent_type == "annuelle":
        return "annuelle"
    if vent_type == "globale":
        return "globale"
    if duree_jours > int(VENTILATION_SEUIL_JOURS_GLOBAL):
        return "annuelle"
    return "trimestrielle"


def run_global_backend(
    date_deb: str,
    date_fin: str,
    dept_code: str,
    *,
    chart_preset: str | None = None,
) -> int:
    """Exécute le backend global via l'API `engine` stable."""
    try:
        date_deb_ts = pd.to_datetime(date_deb)
        date_fin_ts = pd.to_datetime(date_fin)
    except Exception:
        print("Dates invalides : utiliser YYYY-MM-DD.", file=sys.stderr)
        return 1
    dept_code_norm = str(dept_code)

    out_dir = get_out_dir("bilan_global")
    root = _ROOT

    try:
        print(
            f"Période : {date_deb_ts.date():%d/%m/%Y} au {date_fin_ts.date():%d/%m/%Y} – Département {dept_code_norm}."
        )
        ventilation_mode = resolve_ventilation_mode_global(date_deb_ts, date_fin_ts)
        print(
            f"Ventilation temporelle : {ventilation_mode} "
            f"(type={VENTILATION_TYPE_GLOBAL}, seuil={VENTILATION_SEUIL_JOURS_GLOBAL} j)"
        )

        print("Étape 1/4 : chargement des données...")
        with Spinner():
            point = load_point_ctrl(root, dept_code=dept_code_norm, date_deb=date_deb_ts, date_fin=date_fin_ts)
            pa = load_pa(root, date_deb=date_deb_ts, date_fin=date_fin_ts)
            pej = load_pej(root, date_deb=date_deb_ts, date_fin=date_fin_ts)
            pve = load_pve(root, dept_code=dept_code_norm, date_deb=date_deb_ts, date_fin=date_fin_ts)

        spatial_log = logging.getLogger("bilans.spatial")
        if not point.empty:
            point = ensure_insee_from_communes_shp(
                point, root, context="bilan global — points de contrôle", log=spatial_log
            )
        if not pve.empty:
            pve = ensure_insee_from_communes_shp(
                pve, root, context="bilan global — PVe", log=spatial_log
            )

        print("Étape 2/4 : analyse des contrôles...")
        with Spinner():
            analyse_controles_global_impl(point, out_dir)

        print("Étape 3/4 : analyse PEJ / PA / PVe...")
        with Spinner():
            analyse_pej_pa_global(root, point, pa, pej, out_dir, dept_code=dept_code_norm)
            analyse_pve_global(pve, out_dir)
            if ventilation_mode == "annuelle":
                analyse_annuelle_global(point, pa, pej, pve, out_dir)
            elif ventilation_mode == "mensuelle":
                analyse_mensuelle_global(point, pa, pej, pve, out_dir)
            elif ventilation_mode == "trimestrielle":
                analyse_trimestrielle_global(point, pa, pej, pve, out_dir)
                if int((date_fin_ts - date_deb_ts).days) < 730:
                    analyse_mensuelle_global(point, pa, pej, pve, out_dir)
            else:
                pd.DataFrame(
                    columns=[
                        "periode",
                        "nb_controles",
                        "nb_controles_non_conformes",
                        "taux_non_conformite_controles",
                        "nb_pej",
                        "nb_pa",
                        "nb_pve",
                    ]
                ).to_csv(out_dir / "indicateurs_global_par_annee.csv", sep=";", index=False)

        try:
            from bilans.common.carte_helper import ensure_maps

            ensure_maps(
                "bilan_global",
                date_deb=str(date_deb_ts.date()),
                date_fin=str(date_fin_ts.date()),
                dept_code=dept_code_norm,
            )
        except Exception:
            pass

        print("Étape 4/4 : génération du PDF...")
        with Spinner():
            generate_global_pdf_report(
                out_dir,
                date_deb=date_deb_ts,
                date_fin=date_fin_ts,
                dept_code=dept_code_norm,
                ventilation_mode=ventilation_mode,
                chart_preset=chart_preset,
            )

        print("Bilan global généré dans data/out/bilan_global.")
        return 0
    except Exception as e:
        print(f"Erreur bilan global : {e}", file=sys.stderr)
        return 1


def analyse_controles_global(
    point: pd.DataFrame,
    out_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Expose l'agrégation globale des contrôles via `bilans.engine`."""
    return analyse_controles_global_impl(point, out_dir)
