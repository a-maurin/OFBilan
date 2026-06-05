import pandas as pd
from pathlib import Path
from reportlab.platypus import Paragraph, Spacer
from bilans.common.pdf_utils import ofb_table
from bilans.engine.pdf_context import PdfContext

def render_sec_region_detail(ctx: PdfContext) -> None:
    ctx.builder.add_section("secregion", ctx.section_title.get("secregion", "Détail par département"))
    
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
        
        # We will build a table for this domaine
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
        
        # To compute total region for each theme
        # We aggregate over departments
        agg_theme = group_dom.groupby("theme")[["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]].sum().reset_index()
        
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

