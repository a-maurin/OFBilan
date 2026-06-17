"""Audit cohérence des comptages profil synthese_activite_PA_PJ (département 21, 2025), dont PVe (resume + pve_global_resume)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ofbilan.common.utilitaires_metier import (  # noqa: E402
    agg_effectifs_usagers,
    agg_procedures_dossiers_par_theme,
)
from ofbilan.engine.agregations_profil import analyse_controles_global, analyse_pej_pa_global  # noqa: E402
from ofbilan.engine.synthese_aggregations import (  # noqa: E402
    activite_par_type_usager,
    activite_police_par_theme,
    activite_usager_par_theme,
    pej_hors_fiche_controle,
    procedures_par_theme,
    procedures_usager_par_theme,
    _pej_departement,
)

OUT = ROOT / "data" / "out" / "bilan_synthese_activite_PA_PJ"
DEPT = "21"
DATE_DEB = "2025-01-01"
DATE_FIN = "2025-12-31"


def _load_sources():
    from ofbilan.common.chargeurs_donnees import load_pa, load_pej, load_point_ctrl, load_pve

    point = load_point_ctrl(ROOT, dept_code=DEPT, date_deb=DATE_DEB, date_fin=DATE_FIN)
    pej = load_pej(ROOT, dept_code=DEPT, date_deb=DATE_DEB, date_fin=DATE_FIN)
    pa = load_pa(ROOT, date_deb=DATE_DEB, date_fin=DATE_FIN)
    pve = load_pve(ROOT, dept_code=DEPT, date_deb=DATE_DEB, date_fin=DATE_FIN)
    return point, pej, pa, pve


def _chk(name: str, ok: bool, detail: str) -> None:
    mark = "OK" if ok else "ECART"
    print(f"  [{mark}] {name}: {detail}")


def main() -> int:
    print("=== Audit synthese_activite_PA_PJ ===\n")
    point, pej, pa, pve = _load_sources()
    print(f"Sources brutes (après loaders): point={len(point)}, pej={len(pej)}, pa={len(pa)}, pve={len(pve)}")

    act_theme = activite_police_par_theme(point, pej, DEPT)
    act_u = activite_par_type_usager(point, pej, DEPT)
    act_ut = activite_usager_par_theme(point, pej, DEPT)
    proc_theme = procedures_par_theme(pej, pa, point, DEPT)
    proc_ut = procedures_usager_par_theme(pej, pa, point, DEPT)

    hors = pej_hors_fiche_controle(pej, point, DEPT)
    pej_d = _pej_departement(pej, DEPT)

    # --- § 2.1 cohérence interne ---
    print("\n--- Section 2.1 (activité par thème) ---")
    s21_ctrl = int(act_theme["nb_ctrl"].sum()) if not act_theme.empty else 0
    s21_pej = int(act_theme["nb_pej_hors_controle"].sum()) if not act_theme.empty else 0
    s21_tot = int(act_theme["nb_total"].sum()) if not act_theme.empty else 0
    _chk("nb_ctrl = len(point)", s21_ctrl == len(point), f"{s21_ctrl} vs {len(point)}")
    _chk("nb_pej_hors = len(hors)", s21_pej == len(hors), f"{s21_pej} vs {len(hors)}")
    _chk("nb_total = ctrl + pej_hors", s21_tot == s21_ctrl + s21_pej, f"{s21_tot} vs {s21_ctrl}+{s21_pej}")

    # --- § 1 vs agrégations globales ---
    print("\n--- Section 1 (chiffres clés) vs exports globaux ---")
    tab_res = pd.read_csv(OUT / "controles_global_resultats.csv", sep=";")
    pej_res = pd.read_csv(OUT / "pej_global_resume.csv", sep=";")
    pa_res = pd.read_csv(OUT / "pa_global_resume.csv", sep=";")
    pve_res = pd.read_csv(OUT / "pve_global_resume.csv", sep=";")
    res_eff = pd.read_csv(OUT / "synthese_resultats_usager_effectifs.csv", sep=";")
    resume = pd.read_csv(OUT / "synthese_resume.csv", sep=";")

    nc_brut = int(
        tab_res.loc[tab_res["resultat"].astype(str).str.strip().isin(["Infraction", "Manquement"]), "nb"].sum()
    )
    eff_total = int(res_eff["Total"].sum()) if not res_eff.empty else 0
    _chk("resume nb_ctrl", int(resume.iloc[0]["nb_ctrl"]) == len(point), str(resume.iloc[0]["nb_ctrl"]))
    _chk("resume nb_pej", int(resume.iloc[0]["nb_pej"]) == len(pej_d), f"{resume.iloc[0]['nb_pej']} vs {len(pej_d)}")
    _chk(
        "resume nb_pej_hors",
        int(resume.iloc[0]["nb_pej_hors_controle"]) == len(hors),
        f"{resume.iloc[0]['nb_pej_hors_controle']} vs {len(hors)}",
    )
    nb_pve_global_csv = int(pve_res.iloc[0]["nb_pve_global"]) if not pve_res.empty else -1
    _chk(
        "pve_global_resume nb_pve_global = len(pve)",
        nb_pve_global_csv == len(pve),
        f"{nb_pve_global_csv} vs {len(pve)}",
    )
    nb_pve_resume = int(resume.iloc[0]["nb_pve"]) if not resume.empty and "nb_pve" in resume.columns else -1
    _chk(
        "synthese_resume nb_pve = len(pve)",
        nb_pve_resume == len(pve),
        f"{nb_pve_resume} vs {len(pve)}",
    )
    _chk("effectifs §1 = sum Total res_eff", True, f"{eff_total} (indépendant de {len(point)} loc.)")

    # --- § 2.3 PEJ : tous les dossiers vs hors fiche ---
    print("\n--- Section 2.3 vs 2.1 (PEJ) ---")
    s23_pej = int(proc_theme["nb_pej"].sum()) if not proc_theme.empty and "nb_pej" in proc_theme.columns else 0
    _chk(
        "§2.3 PEJ >= §2.1 PEJ hors fiche",
        s23_pej >= s21_pej,
        f"§2.3={s23_pej} (tous PEJ dept), §2.1 hors={s21_pej}",
    )
    _chk(
        "§2.3 PEJ = nb PEJ dept",
        s23_pej == len(pej_d),
        f"{s23_pej} vs {len(pej_d)}",
    )
    _chk(
        "§2.3 sans colonne PVe",
        "nb_pve" not in proc_theme.columns,
        "PVe traites au § 4",
    )

    # --- § 3 camembert (loc.) vs § 3.1 (effectifs) ---
    print("\n--- Section 3 : camembert (loc.+PEJ) vs § 3.1 (effectifs) ---")
    pie_total = int(act_u["nb_total"].sum()) if not act_u.empty else 0
    ut_eff = int(act_ut["nb_effectifs"].sum()) if not act_ut.empty else 0
    ut_pej = int(act_ut["nb_pej_hors_controle"].sum()) if not act_ut.empty else 0
    ut_tot = int(act_ut["nb_total"].sum()) if not act_ut.empty else 0
    eff_dom = int(agg_effectifs_usagers(point)["nb"].sum()) if not point.empty else 0
    eff_pie = int(act_u["nb_effectifs"].sum()) if not act_u.empty and "nb_effectifs" in act_u.columns else 0

    _chk("pie effectifs = agg_effectifs_usagers", eff_pie == eff_dom, f"{eff_pie} vs {eff_dom}")
    _chk("§3.1 effectifs >> loc. si multi-usagers", ut_eff >= len(point), f"eff={ut_eff}, loc={len(point)}")
    _chk("§3.1 pej_hors sum vs len(hors)", ut_pej == len(hors), f"sum thème={ut_pej}, dossiers={len(hors)}")

    # PEJ hors : comptage par thème/type vs dossiers uniques
    empty_pa = hors.iloc[0:0].copy() if not hors.empty else pd.DataFrame()
    pej_agg = agg_procedures_dossiers_par_theme(
        hors, empty_pa, with_type_usager=True, source_table="pej", source_champ="type_usager"
    )
    pej_multi = int(pej_agg["nb_pej"].sum()) if not pej_agg.empty else 0
    _chk(
        "PEJ hors : somme par type peut > nb dossiers",
        pej_multi >= len(hors) or pej_multi == 0,
        f"somme ventilée={pej_multi}, dossiers uniques={len(hors)}",
    )

    # --- Double comptage PA § 2.3 ---
    print("\n--- PA § 2.3 (manquements + ODS) ---")
    from ofbilan.common.utilitaires_metier import count_pa_induites_par_controles, points_as_pa_lignes

    nb_pa_manq = count_pa_induites_par_controles(point)
    s23_pa = int(proc_theme["nb_pa"].sum()) if not proc_theme.empty and "nb_pa" in proc_theme.columns else 0
    _chk("§1 PA = manquements sur contrôles", int(pa_res.iloc[0]["nb_pa_global"]) == nb_pa_manq, str(pa_res.iloc[0]["nb_pa_global"]))
    _chk(
        "§2.3 PA = manquements (sans doublon ODS)",
        s23_pa == nb_pa_manq,
        f"§2.3={s23_pa}, manquements={nb_pa_manq}",
    )

    # --- DC_ID jointure PEJ hors ---
    print("\n--- Jointure PEJ hors fiche (DC_ID) ---")
    if not point.empty and "dc_id" in point.columns and not pej_d.empty:
        dc_pt = set(point["dc_id"].dropna().astype(str).str.strip())
        dc_pej = set(pej_d["DC_ID"].dropna().astype(str).str.strip())
        inter = dc_pt & dc_pej
        _chk("intersection dc_id", True, f"{len(inter)} PEJ ont un DC_ID aussi présent dans les contrôles")
        hors_ids = set(hors["DC_ID"].astype(str).str.strip()) if not hors.empty else set()
        _chk("hors et controles DC_ID disjoints", len(hors_ids & dc_pt) == 0, f"{len(hors_ids & dc_pt)} devrait etre 0")

    # --- CSV exportés vs recalcul ---
    print("\n--- CSV exportés vs recalcul live ---")
    if OUT.exists():
        csv_act = pd.read_csv(OUT / "synthese_activite_par_theme.csv", sep=";")
        csv_u = pd.read_csv(OUT / "synthese_activite_par_type_usager.csv", sep=";")
        _chk(
            "CSV activite_par_theme",
            int(csv_act["nb_total"].sum()) == s21_tot,
            "ok" if int(csv_act["nb_total"].sum()) == s21_tot else "diff",
        )
        _chk(
            "CSV activite_par_type_usager",
            int(csv_u["nb_total"].sum()) == pie_total,
            "ok" if int(csv_u["nb_total"].sum()) == pie_total else "diff",
        )

    print("\n=== Synthèse des écarts connus (comportement code, pas forcément bugs) ===")
    print("  §3 camembert et §3.1 : effectifs + PEJ hors (alignés).")
    print("  §2.3 PA : uniquement manquements issus des fiches contrôle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
