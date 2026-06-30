import pandas as pd
from pathlib import Path
from reportlab.platypus import Paragraph, Spacer
from core.common.pdf_utils import ofb_table
from core.engine.pdf_context import PdfContext

def render_sec_region_detail(ctx: PdfContext) -> None:
    ctx.builder.add_section("secregion", ctx.section_title.get("secregion", "Détail par département"))
    
    # Intégration du graphique comparatif interdépartemental
    profil_id = ctx.profile.get("id") if ctx.profile else "global"
    ratio_csv = ctx.out_dir / f"{profil_id}_ratio_pej_departement.csv"
    if ratio_csv.exists():
        try:
            df_ratio = pd.read_csv(ratio_csv, sep=";", encoding="utf-8")
            if not df_ratio.empty:
                from core.common.rendus_graphiques import chart_ppp_ratio_pej
                from core.common.utilitaires_metier import get_dept_name
                
                depts_labels = []
                totals = []
                ppps = []
                for _, r in df_ratio.iterrows():
                    d = str(r["departement"])
                    depts_labels.append(f"{d} - {get_dept_name(d)}")
                    totals.append(int(r["total_pej"]))
                    ppps.append(int(r["ppp_pej"]))
                    
                img_name = f"ratio_pej_depts_{profil_id}.png"
                chart_path = chart_ppp_ratio_pej(
                    depts_labels, totals, ppps, ctx.tmp_dir, img_name, figure_scale=ctx.figure_scale
                )
                
                ctx.builder.add_section("secregion_ratio", "Part de l'activité thématique par département", level=2, toc_level=1)
                ctx.builder.add_image(Path(chart_path), width_ratio=ctx.chart_bar_w)
                ctx.builder.add_spacer(10)
                
                tbl_syn = [["Département", "Nombre total de PEJ", "Procédures PPP ciblées", "Part relative"]]
                for _, r in df_ratio.iterrows():
                    d = str(r["departement"])
                    tbl_syn.append([
                        f"{d} - {get_dept_name(d)}",
                        str(int(r["total_pej"])),
                        str(int(r["ppp_pej"])),
                        f"{r['ratio_pourcent']:.1f} %"
                    ])
                ctx.builder.add_table(
                    tbl_syn,
                    caption="Synthèse comparative de l'activité judiciaire par département",
                    col_widths=[ctx.avail_w * 0.40, ctx.avail_w * 0.20, ctx.avail_w * 0.20, ctx.avail_w * 0.20],
                    col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
                    keep_together=True
                )
                ctx.builder.add_page_break()
        except Exception as e:
            ctx.builder.add_paragraph(f"<i>Impossible de tracer le graphique comparatif des départements : {e}</i>")

    csv_path = ctx.out_dir / "region_detail_par_dept.csv"
    if not csv_path.exists():
        ctx.builder.add_paragraph("Aucune donnée régionale détaillée disponible.")
        return
        
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    if df.empty:
        ctx.builder.add_paragraph("Aucune donnée régionale détaillée disponible.")
        return
        
    df["departement"] = df["departement"].astype(str)
    
    # Ensure columns
    for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]:
        if c not in df.columns:
            df[c] = 0
            
    # List of departments (sorted)
    depts = sorted(df["departement"].unique().tolist())
    
    # Group by Domaine
    for domaine, group_dom in df.groupby("domaine"):
        if domaine == "Hors domaine":
            continue
            
        ctx.builder.add_section(f"secregion_{domaine}", f"Domaine : {domaine}", level=3)
        
        # To compute total region for each theme
        # We aggregate over departments
        agg_theme = group_dom.groupby("theme")[["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]].sum().reset_index()
        
        if len(depts) > 5:
            # Transposed layout for many departments
            # Columns: Thème | Département | Opérations | Localisations | PEJ / PA / PVe
            headers = ["Thème", "Département", "Opérations", "Localisations", "PEJ / PA / PVe"]
            w_theme = ctx.avail_w * 0.25
            w_dep = ctx.avail_w * 0.25
            w_ops = ctx.avail_w * 0.15
            w_loc = ctx.avail_w * 0.15
            w_pej = ctx.avail_w * 0.20
            col_widths = [w_theme, w_dep, w_ops, w_loc, w_pej]
            col_aligns = ["LEFT", "LEFT", "CENTER", "CENTER", "CENTER"]
            
            tbl = [headers]
            from core.common.utilitaires_metier import get_dept_name
            
            for _, row_theme in agg_theme.iterrows():
                theme = str(row_theme["theme"])
                df_theme = group_dom[group_dom["theme"] == theme]
                
                first = True
                for d in depts:
                    sub = df_theme[df_theme["departement"] == d]
                    if sub.empty:
                        v_ops, v_locs, v_pej, v_pa, v_pve = 0, 0, 0, 0, 0
                    else:
                        v_ops = sub["nb_operations"].sum()
                        v_locs = sub["nb_localisations"].sum()
                        v_pej = sub["nb_pej"].sum()
                        v_pa = sub["nb_pa"].sum()
                        v_pve = sub["nb_pve"].sum()
                        
                    dept_label = f"{d} - {get_dept_name(d)}"
                    theme_label = theme if first else ""
                    first = False
                    
                    row = [
                        theme_label,
                        dept_label,
                        str(int(v_ops)),
                        str(int(v_locs)),
                        f"{int(v_pej)} / {int(v_pa)} / {int(v_pve)}"
                    ]
                    tbl.append(row)
                
                # Add total row for this theme
                tot_suites = f"{int(row_theme['nb_pej'])} / {int(row_theme['nb_pa'])} / {int(row_theme['nb_pve'])}"
                tbl.append([
                    "",
                    "Total Région",
                    str(int(row_theme["nb_operations"])),
                    str(int(row_theme["nb_localisations"])),
                    tot_suites
                ])
        else:
            # Standard layout (departments in columns)
            # Columns: Thème | Métrique | Total | Dép 1 | Dép 2 | ...
            headers = ["Thème", "Métrique", "Total Région"] + depts
            
            # Calculate col widths based on landscape A4. 
            # A4 landscape is 297mm x 210mm. Avail_w is about 297 - margins ~ 260mm = ~730 points.
            # "Thème" -> 20%, "Métrique" -> 15%, "Total" -> 10%, depts -> rest divided by len(depts)
            w_theme = ctx.avail_w * 0.25
            w_met = ctx.avail_w * 0.15
            w_tot = ctx.avail_w * 0.10
            w_dep = (ctx.avail_w - w_theme - w_met - w_tot) / max(1, len(depts))
            col_widths = [w_theme, w_met, w_tot] + [w_dep] * len(depts)
            col_aligns = ["LEFT", "LEFT", "CENTER"] + ["CENTER"] * len(depts)
            
            tbl = [headers]
            
            for _, row_theme in agg_theme.iterrows():
                theme = str(row_theme["theme"])
                # Filter original df for this theme
                df_theme = group_dom[group_dom["theme"] == theme]
                
                # Row 1: Operations
                row_ops = [theme, "Opérations", str(int(row_theme["nb_operations"]))]
                for d in depts:
                    v = df_theme[df_theme["departement"] == d]["nb_operations"].sum()
                    row_ops.append(str(int(v)) if v > 0 else "0")
                tbl.append(row_ops)
                
                # Row 2: Localisations
                row_locs = ["", "Localisations", str(int(row_theme["nb_localisations"]))]
                for d in depts:
                    v = df_theme[df_theme["departement"] == d]["nb_localisations"].sum()
                    row_locs.append(str(int(v)) if v > 0 else "0")
                tbl.append(row_locs)
                
                # Row 3: PEJ / PA / PVe
                tot_suites = f"{int(row_theme['nb_pej'])} / {int(row_theme['nb_pa'])} / {int(row_theme['nb_pve'])}"
                row_suites = ["", "PEJ / PA / PVe", tot_suites]
                for d in depts:
                    sub = df_theme[df_theme["departement"] == d]
                    if sub.empty:
                        row_suites.append("0 / 0 / 0")
                    else:
                        v_pej = int(sub["nb_pej"].sum())
                        v_pa = int(sub["nb_pa"].sum())
                        v_pve = int(sub["nb_pve"].sum())
                        if v_pej == 0 and v_pa == 0 and v_pve == 0:
                            row_suites.append("0 / 0 / 0")
                        else:
                            row_suites.append(f"{v_pej} / {v_pa} / {v_pve}")
                tbl.append(row_suites)
                
        ctx.builder.add_table(
            tbl,
            caption=f"Détail par département pour le domaine {domaine}",
            col_widths=col_widths,
            col_aligns=col_aligns,
            keep_together=True
        )
        ctx.builder.add_spacer(5)
