# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

"""
========================================================================================
MODULE : GENERATEUR DES SECTIONS REGIONALES PDF (`sections_region.py`)
========================================================================================
Ce module est dédié à la génération des tableaux et graphiques d'analyse interdépartementale
pour les bilans à l'échelle régionale (DR) ou des Brigades de Mission Interdépartementale (BMI).

Rôles :
  1. Génération des histogrammes comparatifs entre départements (localisations, opérations).
  2. Construction des tableaux d'agrégation interdépartementale par domaine et thématique.
  3. Rendu des graphiques camembert de répartition des procédures (PA, PEJ, PVe) entre départements.
  4. Création des annexes régionales détaillées.
========================================================================================
"""
import logging
import re
from pathlib import Path
from typing import Any
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from core.common.pdf_utils import ofb_table
from core.engine.pdf_context import PdfContext
from core.common.utilitaires_metier import get_dept_name
from core.common.pdf_report_builder import PDFReportBuilder
from core.common.rendus_graphiques import chart_interdept_stacked_bar, chart_pie, chart_pie_legend_right

logger = logging.getLogger(__name__)

try:
    import geopandas as gpd
except ImportError:
    gpd = None


def _create_proportional_rl_image(img_path: Path, target_w: float, fallback_text: str, styles: dict, max_h: float | None = 450.0) -> RLImage | Paragraph:
    """Instancie une RLImage ReportLab en conservant mathématiquement le ratio largeur/hauteur réel."""
    body_style = styles.get("BodyText", styles.get("Normal"))
    if not img_path.exists():
        return Paragraph(f"<i>{fallback_text}</i>", body_style)
    try:
        with PILImage.open(img_path) as im:
            w_px, h_px = im.size
        aspect = (h_px / float(w_px)) if w_px > 0 else 0.7
        target_h = target_w * aspect
        if max_h is not None and target_h > max_h:
            target_h = max_h
            target_w = target_h / aspect
        return RLImage(str(img_path), width=target_w, height=target_h)
    except Exception:
        return Paragraph(f"<i>{fallback_text}</i>", body_style)


def _shapely_to_pathpatch(geom, transform):
    """Convertit un Polygon ou MultiPolygon Shapely en PathPatch Matplotlib pour le clipping."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    import numpy as np

    codes = []
    verts = []

    def _add_poly(poly):
        ext = np.asarray(poly.exterior.coords)
        verts.extend(ext)
        codes.extend([Path.MOVETO] + [Path.LINETO] * (len(ext) - 2) + [Path.CLOSEPOLY])
        for interior in poly.interiors:
            int_coords = np.asarray(interior.coords)
            verts.extend(int_coords)
            codes.extend([Path.MOVETO] + [Path.LINETO] * (len(int_coords) - 2) + [Path.CLOSEPOLY])

    if geom.geom_type == 'Polygon':
        _add_poly(geom)
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            _add_poly(poly)

    path = Path(verts, codes)
    return PathPatch(path, transform=transform, facecolor='none', edgecolor='none')


def _generate_dept_vignette(
    dept_code: str,
    out_dir: Path,
    tmp_dir: Path,
    img_name: str,
    figure_scale: float = 1.0,
    profile_id: str = "global",
) -> Path:
    """
    Génère la vignette cartographique épurée du département avec conservation STRICTE du ratio d'aspect
    (1:1 carré, sans aucune déformation) et carte de chaleur de la pression de contrôle (Hexbin / Heatmap).
    """
    out_path = tmp_dir / img_name
    fig, ax = plt.subplots(figsize=(2.5 * figure_scale, 2.5 * figure_scale), dpi=150)
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#ffffff')
    
    ax.set_aspect('equal')
    
    try:
        from core.cartographie.pochoir_helper import load_department_gdf
        from core.common.chargeurs_donnees import load_pnf_aoa_gdf, load_pnf_coeur_gdf
        from core.chemins_projet import PROJECT_ROOT
        
        is_pnf = str(profile_id).strip().lower() in ("pnf_v2", "pnf") or "pnf" in str(out_dir.name).lower() or str(dept_code).strip() in ("21", "52") and "pnf" in str(out_dir).lower()
        if is_pnf:
            gdf_aoa = load_pnf_aoa_gdf(PROJECT_ROOT)
            gdf_coeur = load_pnf_coeur_gdf(PROJECT_ROOT)
            gdf_dept = gdf_aoa if gdf_aoa is not None and not gdf_aoa.empty else load_department_gdf(dept_code, project_root=PROJECT_ROOT)
        else:
            gdf_coeur = None
            gdf_dept = load_department_gdf(dept_code, project_root=PROJECT_ROOT)
        
        if gdf_dept is not None and not gdf_dept.empty:
            if is_pnf and gdf_aoa is not None and not gdf_aoa.empty:
                target_dept = str(dept_code).strip().zfill(2)
                col_dep = next((c for c in gdf_aoa.columns if c.lower() in ("insee_dep", "num_depart", "code_dept", "insee_com")), None)
                if col_dep:
                    mask_dept = gdf_aoa[col_dep].astype(str).str.strip().str[:2] == target_dept
                    gdf_aoa[~mask_dept].plot(ax=ax, color='#f1f5f9', edgecolor='#003366', linewidth=0.7)
                    gdf_aoa[mask_dept].plot(ax=ax, color='#bfdbfe', edgecolor='#003366', linewidth=1.1)
                else:
                    gdf_aoa.plot(ax=ax, color='#f1f5f9', edgecolor='#003366', linewidth=0.8)
                
                if gdf_coeur is not None and not gdf_coeur.empty:
                    gdf_coeur.plot(ax=ax, facecolor='none', edgecolor='#16a34a', linewidth=1.8, label='Cœur de parc')
            else:
                gdf_dept.plot(ax=ax, color='#f1f5f9', edgecolor='#003366', linewidth=1.2, aspect='equal')
            
            from core.chemins_projet import get_carto_temp_dir
            carto_dir_default = PROJECT_ROOT / "data" / "sources" / "sig" / "CARTO"
            gpkg_files = list(out_dir.rglob("controles_*.gpkg")) + list(out_dir.glob("controles_*.gpkg"))
            gpkg_files += list(get_carto_temp_dir().glob("controles_*.gpkg"))
            gpkg_files += list(carto_dir_default.glob("controles_*.gpkg"))
            
            pts_dept = None
            if gpd is not None and gpkg_files:
                try:
                    import re
                    code_clean = str(dept_code).strip().lower()
                    out_dir_name = str(out_dir.name).strip().lower()
                    reg_match = re.search(r"r\d+", out_dir_name)
                    reg_tag = reg_match.group(0) if reg_match else ""

                    matching = []
                    for f in gpkg_files:
                        fname = f.name.lower()
                        if reg_tag and reg_tag in fname:
                            matching.append(f)
                        elif code_clean in fname:
                            matching.append(f)

                    if matching:
                        matching.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        target_gpkg = matching[0]
                    else:
                        gpkg_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        target_gpkg = gpkg_files[0]
                    
                    gdf_pts = gpd.read_file(target_gpkg)
                    if gdf_pts.crs is None or gdf_pts.crs.to_epsg() != 2154:
                        if gdf_pts.crs is not None:
                            gdf_pts = gdf_pts.to_crs("EPSG:2154")
                    
                    target_dept = str(dept_code).strip().split('.')[0].zfill(2)
                    if "num_depart" in gdf_pts.columns:
                        dept_clean = gdf_pts["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)
                        pts_dept = gdf_pts[dept_clean == target_dept]
                    
                    if pts_dept is None or pts_dept.empty:
                        try:
                            pts_dept = gpd.sjoin(gdf_pts, gdf_dept, predicate="within")
                        except Exception:
                            pts_dept = None
                except Exception:
                    pts_dept = None
            
            if pts_dept is not None and not pts_dept.empty:
                x_coords = pts_dept.geometry.x
                y_coords = pts_dept.geometry.y
                hb = ax.hexbin(
                    x_coords, y_coords,
                    gridsize=18,
                    cmap='YlOrRd',
                    mincnt=1,
                    alpha=0.85,
                    edgecolors='none'
                )

                try:
                    poly_geom = gdf_dept.geometry.union_all() if hasattr(gdf_dept.geometry, "union_all") else gdf_dept.geometry.unary_union
                    patch = _shapely_to_pathpatch(poly_geom, ax.transData)
                    ax.add_patch(patch)
                    hb.set_clip_path(patch)
                except Exception:
                    pass

                cbar = fig.colorbar(hb, ax=ax, orientation='horizontal', pad=0.02, shrink=0.25, aspect=12)
                cbar.set_label('Pression de contrôle (Faible -> Forte)', fontsize=6.5, color='#003366')
                cbar.ax.tick_params(labelsize=5.5)

            minx, miny, maxx, maxy = gdf_dept.total_bounds
            cx = (minx + maxx) / 2.0
            cy = (miny + maxy) / 2.0
            max_span = max(maxx - minx, maxy - miny) * 0.56
            ax.set_xlim(cx - max_span, cx + max_span)
            ax.set_ylim(cy - max_span, cy + max_span)
        else:
            ax.text(0.5, 0.5, f"Département {dept_code}", ha='center', va='center', fontsize=9, color='#003366')
    except Exception:
        ax.text(0.5, 0.5, f"Département {dept_code}", ha='center', va='center', fontsize=9, color='#003366')
        
    ax.axis('off')
    fig.tight_layout(pad=0.05)
    fig.savefig(out_path, dpi=150, facecolor='white')
    plt.close(fig)
    return out_path


def _generate_region_choropleth(
    dept_counts: dict[str, int],
    dept_code: str,
    tmp_dir: Path,
    img_name: str,
    figure_scale: float = 1.0,
    out_dir: Path | None = None,
    profile_id: str = "global",
    total_unique_ops: int | None = None,
    cbar_shrink: float = 0.35,
    cbar_title_fontsize: float = 7.0,
    cbar_labelsize: float = 6.0,
    max_span_factor: float = 0.51,
    commune_counts: dict[str, int] | None = None,
    carto_cfg: dict[str, Any] | None = None,
) -> Path:
    """Génère la carte choroplèthe de la pression de contrôle (aplat par commune ou département)."""
    out_path = tmp_dir / img_name
    fig, ax = plt.subplots(figsize=(5.8 * figure_scale, 3.6 * figure_scale), dpi=150)
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#ffffff')
    ax.set_aspect('equal')
    
    cfg = carto_cfg or {}
    titre_carte = cfg.get("titre", "Carte de la pression de contrôle par commune")
    cbar_title_text = cfg.get("cbar_title", "Pression de contrôle (localisations/commune)")
    zero_color = cfg.get("zero_color", "#f1f5f9")
    commune_ec = cfg.get("commune_edgecolor", "#cbd5e1")
    dept_ec = cfg.get("dept_edgecolor", "#003366")
    show_labels = cfg.get("afficher_etiquettes_communes", False)

    try:
        from core.cartographie.pochoir_helper import load_department_gdf, load_communes_gdf
        from core.common.chargeurs_donnees import load_pnf_aoa_gdf, load_pnf_coeur_gdf
        from core.chemins_projet import PROJECT_ROOT
        
        is_pnf = (
            "pnf" in str(profile_id).strip().lower()
            or (out_dir and ("pnf" in str(out_dir.name).lower() or "21_52" in str(out_dir.name).lower()))
            or "pnf" in str(dept_code).lower()
        )
        if is_pnf:
            gdf_region = load_pnf_aoa_gdf(PROJECT_ROOT)
            gdf_coeur = load_pnf_coeur_gdf(PROJECT_ROOT)
            total_ops = total_unique_ops if total_unique_ops is not None else (int(round(sum(dept_counts.values()))) if dept_counts else 0)
            
            if gdf_region is not None and not gdf_region.empty:
                if gdf_region.crs is None or gdf_region.crs.to_epsg() != 2154:
                    gdf_region = gdf_region.set_crs("EPSG:2154") if gdf_region.crs is None else gdf_region.to_crs("EPSG:2154")
                    
                if gdf_coeur is not None and not gdf_coeur.empty:
                    if gdf_coeur.crs is None or gdf_coeur.crs.to_epsg() != 2154:
                        gdf_coeur = gdf_coeur.set_crs("EPSG:2154") if gdf_coeur.crs is None else gdf_coeur.to_crs("EPSG:2154")

                gdf_region.plot(ax=ax, color='#f1f5f9', edgecolor='#003366', linewidth=1.0)
                
                # Chargement des points de contrôle pour l'affichage de la grille de densité (hexbin)
                from core.chemins_projet import get_carto_temp_dir
                carto_dir_default = PROJECT_ROOT / "data" / "sources" / "sig" / "CARTO"
                gpkg_files = list(out_dir.rglob("controles_*.gpkg")) + list(out_dir.glob("controles_*.gpkg")) if out_dir else []
                gpkg_files += list(get_carto_temp_dir().glob("controles_*.gpkg"))
                gpkg_files += list(carto_dir_default.glob("controles_*.gpkg"))
                
                pts_pnf = None
                from core.cartographie.pochoir_helper import gpd
                if gpd is not None and gpkg_files:
                    try:
                        gdf_pts = gpd.read_file(gpkg_files[0])
                        if gdf_pts.crs is None or gdf_pts.crs.to_epsg() != 2154:
                            gdf_pts = gdf_pts.set_crs("EPSG:2154") if gdf_pts.crs is None else gdf_pts.to_crs("EPSG:2154")
                        try:
                            pts_pnf = gpd.sjoin(gdf_pts, gdf_region, predicate="within")
                        except Exception:
                            pts_pnf = gdf_pts
                    except Exception:
                        pts_pnf = None

                if pts_pnf is not None and not pts_pnf.empty:
                    x_coords = pts_pnf.geometry.x
                    y_coords = pts_pnf.geometry.y
                    hb = ax.hexbin(
                        x_coords, y_coords,
                        gridsize=18,
                        cmap='YlGnBu',
                        mincnt=1,
                        bins='log',
                        alpha=0.85,
                        edgecolors='none'
                    )

                    try:
                        poly_geom = gdf_region.geometry.union_all() if hasattr(gdf_region.geometry, "union_all") else gdf_region.geometry.unary_union
                        patch = _shapely_to_pathpatch(poly_geom, ax.transData)
                        ax.add_patch(patch)
                        hb.set_clip_path(patch)
                    except Exception:
                        pass

                    cbar = fig.colorbar(hb, ax=ax, orientation='horizontal', pad=0.02, shrink=cbar_shrink, aspect=20)
                    cbar.ax.set_title(cbar_title_text, fontsize=cbar_title_fontsize, color='#003366', pad=2)
                    import matplotlib.ticker as ticker
                    cbar.ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{int(round(x))}"))
                    cbar.ax.tick_params(labelsize=cbar_labelsize)

                if gdf_coeur is not None and not gdf_coeur.empty:
                    gdf_coeur.plot(ax=ax, facecolor='none', edgecolor='#16a34a', linewidth=1.0, linestyle='--', label='Cœur de parc')

                minx, miny, maxx, maxy = gdf_region.total_bounds
                cx = (minx + maxx) / 2.0
                cy = (miny + maxy) / 2.0
                max_span = max(maxx - minx, maxy - miny) * max_span_factor
                ax.set_xlim(cx - max_span, cx + max_span)
                ax.set_ylim(cy - max_span, cy + max_span)

                if titre_carte:
                    ax.set_title(titre_carte, fontsize=8.5, color='#003366', fontweight='bold', pad=4)

                ax.set_axis_off()
                fig.tight_layout(pad=0.05)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor="white")
                plt.close(fig)
                return out_path
        else:
            gdf_communes = load_communes_gdf(dept_code, project_root=PROJECT_ROOT)
            gdf_region = load_department_gdf(dept_code, project_root=PROJECT_ROOT, dissolve=False)

            if gdf_communes is not None and not gdf_communes.empty:
                counts_dict = commune_counts or {}
                gdf_communes["insee_clean"] = gdf_communes["insee_comm"].astype(str).str.strip().str.zfill(5)
                gdf_communes["nb_ops"] = gdf_communes["insee_clean"].map(lambda c: counts_dict.get(c, 0)).fillna(0)

                # Communes sans contrôles (0) en gris très clair
                gdf_zero = gdf_communes[gdf_communes["nb_ops"] == 0]
                gdf_active = gdf_communes[gdf_communes["nb_ops"] > 0]

                if not gdf_zero.empty:
                    gdf_zero.plot(ax=ax, facecolor=zero_color, edgecolor=commune_ec, linewidth=0.3)

                if not gdf_active.empty:
                    p_active = gdf_active.plot(
                        column="nb_ops",
                        ax=ax,
                        cmap="YlGnBu",
                        edgecolor=commune_ec,
                        linewidth=0.3,
                        legend=False
                    )
                    # Barre de légende continue pour la pression de contrôle
                    import matplotlib.cm as cm
                    import matplotlib.colors as mcolors
                    min_val = max(1, gdf_active["nb_ops"].min())
                    max_val = max(min_val + 1, gdf_active["nb_ops"].max())
                    norm = mcolors.Normalize(vmin=min_val, vmax=max_val)
                    sm = cm.ScalarMappable(cmap=cm.get_cmap("YlGnBu"), norm=norm)
                    sm._A = []
                    cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', pad=0.02, shrink=cbar_shrink, aspect=20)
                    cbar.ax.set_title(cbar_title_text, fontsize=cbar_title_fontsize, color='#003366', pad=2)
                    import matplotlib.ticker as ticker
                    cbar.ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{int(round(x))}"))
                    cbar.ax.tick_params(labelsize=cbar_labelsize)
                else:
                    gdf_communes.plot(ax=ax, facecolor=zero_color, edgecolor=commune_ec, linewidth=0.3)

                # Surbrillance des contours départementaux
                if gdf_region is not None and not gdf_region.empty:
                    gdf_region.plot(ax=ax, facecolor="none", edgecolor=dept_ec, linewidth=1.2)

                if titre_carte:
                    ax.set_title(titre_carte, fontsize=8.5, color='#003366', fontweight='bold', pad=4)

                # Traitement note des contrôles hors-communes si total_unique_ops > sum(mapped)
                total_mapped = int(gdf_communes["nb_ops"].sum())
                total_reg = int(total_unique_ops or sum(dept_counts.values()) or 0)
                if cfg.get("afficher_note_hors_communes", True) and total_reg > total_mapped:
                    diff_cnt = total_reg - total_mapped
                    ax.text(
                        0.5, -0.05,
                        f"* {diff_cnt} localisation(s) non rattachée(s) à une commune du périmètre",
                        transform=ax.transAxes, ha="center", va="top",
                        fontsize=5.5, color="#64748b", fontstyle="italic"
                    )

                ax.set_axis_off()
                fig.tight_layout(pad=0.05)
                fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor="white")
                plt.close(fig)
                return out_path

        if gdf_region is not None and not gdf_region.empty:
            col_dep = next((c for c in gdf_region.columns if c.lower() in ("insee_dep", "num_depart", "code_dept", "insee_com")), gdf_region.columns[0])
            gdf_region["dep_code_clean"] = gdf_region[col_dep].astype(str).str.strip().str.upper().str[:2]
            gdf_region["nb_ops"] = gdf_region["dep_code_clean"].map(
                lambda d: dept_counts.get(d, dept_counts.get(d.zfill(2), dept_counts.get(str(int(d)) if d.isdigit() else d, 0)))
            ).fillna(0)
            
            gdf_region.plot(
                column="nb_ops",
                ax=ax,
                cmap="YlGnBu",
                edgecolor=dept_ec,
                linewidth=0.8,
                legend=False
            )

            if titre_carte:
                ax.set_title(titre_carte, fontsize=8.5, color='#003366', fontweight='bold', pad=4)

            ax.set_axis_off()
            fig.tight_layout(pad=0.05)
            fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            return out_path
    except Exception:
        pass
    return out_path



def render_sec_region_dashboard(ctx: Any) -> None:
    """Rendu structuré et aéré du tableau de bord régional / PNF v2 (Page 1 à 3)."""
    title = ctx.section_title.get("sec_region_dashboard", "1. Synthèse régionale")
    ctx.builder.add_section("sec_region_dashboard", title)

    # 1. Pavés KPI Cards Régionaux / PNF Grand Angle
    prof_id = str(getattr(ctx, "profile_id", "")) or str((ctx.profile or {}).get("id", ""))
    out_dir_str = str(getattr(ctx, "out_dir", "")).lower()
    dept_code_str = str(getattr(ctx, "dept_code", "")).lower()
    is_pnf = "pnf" in prof_id.lower() or "pnf" in out_dir_str or "pnf" in dept_code_str or "21, 52" in dept_code_str or "21_52" in out_dir_str
    
    kf: list[tuple[str, str]] = []
    csv_coeur_path = ctx.out_dir / "pnf_coeur_vs_aoa.csv"
    if is_pnf:
        if not csv_coeur_path.exists():
            try:
                from core.chemins_projet import PROJECT_ROOT
                from core.engine.agregations_region import agregation_region_coeur_vs_aoa
                agregation_region_coeur_vs_aoa(ctx.point, ctx.pej, ctx.pve, ctx.dept_code, ctx.out_dir, ctx.echelle, ctx.code, project_root=PROJECT_ROOT)
            except Exception:
                pass

        if csv_coeur_path.exists():
            try:
                df_coeur = pd.read_csv(csv_coeur_path, sep=";", encoding="utf-8")
                if not df_coeur.empty:
                    ops_coeur = int(df_coeur[df_coeur["zonage"] == "Cœur de parc"]["nb_operations"].sum())
                    ops_total = int(df_coeur["nb_operations"].sum()) or int(ctx.nb_ops or 0)
                    
                    pej_tot = int(df_coeur["nb_pej"].sum()) or int(ctx.nb_pej or 0)
                    pa_tot = int(df_coeur["nb_pa"].sum()) or int(ctx.nb_pa or 0)
                    pve_tot = int(df_coeur["nb_pve"].sum()) or int(ctx.nb_pve or 0)
                    
                    kf.append((f"{ops_total}", "Opérations AOA (Total PNF)"))
                    kf.append((f"{ops_coeur}", "Opérations en Cœur de parc"))
                    kf.append((f"{pve_tot} PVe | {pej_tot} PEJ | {pa_tot} PA", "Procédures sur le périmètre PNF"))
            except Exception:
                pass

    if not kf:
        if ctx.nb_ops:
            kf.append((str(ctx.nb_ops), "Opérations de contrôle"))
        if ctx.nb_localisations:
            kf.append((str(ctx.nb_localisations), "Localisations de contrôle"))
        if ctx.nb_pej or ctx.nb_pa or ctx.nb_pve:
            kf.append((f"{ctx.nb_pej or 0} | {ctx.nb_pa or 0} | {ctx.nb_pve or 0}", "Procédures PEJ / PA / PVe"))
            
    ctx.builder.add_key_figures(kf)
    ctx.builder.add_spacer(6)

    csv_path = ctx.out_dir / "region_detail_par_dept.csv"
    df = pd.DataFrame()
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, sep=";", encoding="utf-8")
        except Exception:
            df = pd.DataFrame()

    # --- PAGE 1 VISUELS SUPERPOSÉS VERTICALEMENT : CARTE CHOROPLÈTHE (HAUT) & DONUT DOMAINES (BAS) ---
    dept_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    if not df.empty:
        df["departement"] = df["departement"].astype(str)
        if "nb_operations" in df.columns:
            dept_counts = df.groupby("departement")["nb_operations"].sum().to_dict()
            domain_counts = df.groupby("domaine")["nb_operations"].sum().to_dict()

    # Calcul des localisations de contrôle par commune (commune_counts)
    commune_counts: dict[str, int] = {}
    for df_src in (getattr(ctx, "point", None), getattr(ctx, "pej", None), getattr(ctx, "pve", None)):
        if df_src is not None and not df_src.empty:
            col = next((c for c in ("insee_comm", "insee_com", "code_insee", "INSEE_COM", "insee", "INF-INSEE") if c in df_src.columns), None)
            if col:
                s_counts = df_src[col].astype(str).str.strip().str.zfill(5).value_counts()
                for code_insee, val in s_counts.items():
                    if code_insee and len(code_insee) == 5 and code_insee.isdigit():
                        commune_counts[code_insee] = commune_counts.get(code_insee, 0) + int(val)

    body_style = ctx.builder.styles.get("BodyText", ctx.builder.styles.get("Normal"))

    # Extraire les options visuelles configurées dans le gabarit YAML
    sec_enr = (getattr(ctx, "presentation_cfg", {}) or {}).get("sections_enrichies", {}).get("synthese_regionale", {})
    carto_cfg = sec_enr.get("carte_choroplethe", {})
    cbar_shrink = float(carto_cfg.get("cbar_shrink", 0.35))
    cbar_title_fs = float(carto_cfg.get("cbar_title_fontsize", 7.0))
    cbar_lbl_fs = float(carto_cfg.get("cbar_labelsize", 6.0))
    max_span_factor = float(carto_cfg.get("max_span_factor", 0.51))
    w_ratio = float(carto_cfg.get("width_ratio", 0.95))
    max_h_carto = float(carto_cfg.get("max_h", 290.0))
    legend_fs_donut = float(sec_enr.get("legend_fontsize_donut", 9.0))
    show_reg_usg = sec_enr.get("afficher_donut_usagers", False)

    # Visuel 1 : Carte choroplèthe régionale centrée en haut
    total_unique = int(ctx.nb_ops) if ctx.nb_ops else None
    carto_path = _generate_region_choropleth(
        dept_counts,
        ctx.dept_code,
        ctx.tmp_dir,
        "region_choropleth.png",
        figure_scale=ctx.figure_scale,
        out_dir=ctx.out_dir,
        profile_id=prof_id,
        total_unique_ops=total_unique,
        cbar_shrink=cbar_shrink,
        cbar_title_fontsize=cbar_title_fs,
        cbar_labelsize=cbar_lbl_fs,
        max_span_factor=max_span_factor,
        commune_counts=commune_counts,
        carto_cfg=carto_cfg,
    )

    if carto_path.exists():
        img_carto = _create_proportional_rl_image(carto_path, ctx.avail_w * w_ratio, "Carte régionale indisponible", ctx.builder.styles, max_h=max_h_carto)
    else:

        img_carto = Paragraph("<para align='center'><i>Carte régionale non disponible</i></para>", body_style)

    tbl_carto = Table([[img_carto]], colWidths=[ctx.avail_w])
    tbl_carto.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    ctx.builder.story.append(tbl_carto)

    # Note explicative sous la carte si nécessaire
    somme_dept = int(round(sum(dept_counts.values()))) if dept_counts else 0
    total_reg = int(ctx.nb_ops) if ctx.nb_ops else 0
    if somme_dept > 0 and total_reg > 0 and somme_dept != total_reg:
        diff = int(abs(somme_dept - total_reg))
        str_somme = f"{somme_dept:,}".replace(",", "\u00a0")
        str_total = f"{total_reg:,}".replace(",", "\u00a0")
        if somme_dept > total_reg:
            note_txt = (
                f"<i>* La somme par département ({str_somme} ops) excède le total régional ({str_total} ops) "
                f"car {diff} opération(s) inter-départementale(s) sont comptabilisées dans chaque territoire concerné.</i>"
            )
        else:
            note_txt = (
                f"<i>* La somme par département ({str_somme} ops) est inférieure au total régional ({str_total} ops) "
                f"car {diff} opération(s) ne sont pas rattachées à un département de la région.</i>"
            )
        style_note = ParagraphStyle(
            "RegMapDynamicNote",
            parent=ctx.builder.styles.get("BodySmall", ctx.builder.styles["BodyText"]),
            fontSize=7,
            leading=8.5,
            textColor=colors.HexColor("#555555"),
            alignment=TA_CENTER,
        )
        ctx.builder.story.append(Spacer(1, 2))
        ctx.builder.story.append(Paragraph(note_txt, style_note))

    ctx.builder.add_spacer(2)

    # Visuel 2 : Diagrammes Donut par Domaine et/ou Type d'Usager
    domain_counts_filtered = {k: int(v) for k, v in domain_counts.items() if int(v) > 0}
    if domain_counts_filtered and sum(domain_counts_filtered.values()) > 0:
        legend_ncol_dom = 1
        ref_pie_fs = getattr(ctx, "ref_pie_fs", 1.22)
        ref_pie_w = getattr(ctx, "ref_pie_w", 0.78)
        donut_path = chart_pie(
            domain_counts_filtered,
            "Répartition par Domaine de contrôle",
            ctx.tmp_dir,
            "region_domaines_donut.png",
            figure_scale=ref_pie_fs,
            donut=True,
            legend_ncol=legend_ncol_dom,
            legend_fontsize=legend_fs_donut
        )
        dom_w = ctx.avail_w * 0.46 if show_reg_usg else ctx.avail_w * ref_pie_w
        img_donut_dom = _create_proportional_rl_image(Path(donut_path), dom_w, "Graphique domaines indisponible", ctx.builder.styles, max_h=220.0 if show_reg_usg else 250.0)
    else:
        img_donut_dom = Paragraph("<para align='center'><i>Répartition par domaine non disponible</i></para>", body_style)

    if show_reg_usg:
        # Donut récapitulatif usagers régional
        csv_usg = ctx.out_dir / "usagers_par_dept.csv"
        usg_counts = {}
        if csv_usg.exists():
            try:
                df_usg = pd.read_csv(csv_usg, sep=";", encoding="utf-8")
                if not df_usg.empty and "type_usager" in df_usg.columns and "nb_operations" in df_usg.columns:
                    import re
                    df_usg["type_usager_clean"] = df_usg["type_usager"].apply(lambda u: re.sub(r'[\s_]+\d+$', '', str(u)).strip() if pd.notna(u) else "Non renseigné")
                    usg_grp = df_usg.groupby("type_usager_clean")["nb_operations"].sum().reset_index()
                    usg_counts = {str(r["type_usager_clean"]): int(r["nb_operations"]) for _, r in usg_grp.iterrows() if int(r["nb_operations"]) > 0}
            except Exception:
                usg_counts = {}

        if usg_counts:
            donut_usg_path = chart_pie(
                usg_counts,
                "Répartition par Type d'usager",
                ctx.tmp_dir,
                "region_usagers_donut.png",
                figure_scale=getattr(ctx, "ref_pie_fs", 1.22),
                donut=True,
                legend_ncol=1,
                legend_fontsize=legend_fs_donut
            )

            img_donut_usg = _create_proportional_rl_image(Path(donut_usg_path), ctx.avail_w * 0.46, "Graphique usagers indisponible", ctx.builder.styles, max_h=220.0)
        else:
            img_donut_usg = Paragraph("<para align='center'><i>Répartition par type d'usager non disponible</i></para>", body_style)

        tbl_donut = Table([[img_donut_dom, img_donut_usg]], colWidths=[ctx.avail_w * 0.48, ctx.avail_w * 0.48])
    else:
        tbl_donut = Table([[img_donut_dom]], colWidths=[ctx.avail_w])

    tbl_donut.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    ctx.builder.story.append(tbl_donut)


    # --- SAUT DE PAGE VERS LA PAGE 2 DE LA SYNTHÈSE RÉGIONALE / PNF ---
    ctx.builder.story.append(PageBreak())

    # --- PAGE 2 PNF V2 : FOCUS CŒUR VS AOA & TYPOLOGIE DES USAGERS ---
    if is_pnf:
        ctx.builder.add_paragraph("<b>1.2 Répartition spatiale (Cœur de parc vs AOA) et Typologie des Usagers</b>", style="Heading2")
        ctx.builder.add_spacer(4)

        # 1. Tableau Cœur vs AOA vs Non géolocalisé (agrégé globalement sans décomposition 21/52)
        csv_coeur = ctx.out_dir / "pnf_coeur_vs_aoa.csv"
        if csv_coeur.exists():
            try:
                df_c = pd.read_csv(csv_coeur, sep=";", encoding="utf-8")
                if not df_c.empty:
                    df_c_grouped = df_c.groupby("zonage")[["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]].sum().reset_index()
                    
                    order_map = {"AOA (Hors cœur)": 1, "Cœur de parc": 2, "Non géolocalisé (AOA)": 3}
                    df_c_grouped["order"] = df_c_grouped["zonage"].map(lambda z: order_map.get(z, 99))
                    df_c_grouped = df_c_grouped.sort_values("order")

                    c_data = [["Zonage / Territoire", "Opérations", "Localisations", "PEJ", "PA", "PVe"]]
                    tot_ops_c, tot_locs_c, tot_pej_c, tot_pa_c, tot_pve_c = 0, 0, 0, 0, 0
                    
                    for _, r in df_c_grouped.iterrows():
                        zon = str(r["zonage"])
                        ops = int(r["nb_operations"])
                        locs = int(r["nb_localisations"])
                        pej = int(r["nb_pej"])
                        pa = int(r["nb_pa"])
                        pve = int(r["nb_pve"])

                        tot_ops_c += ops
                        tot_locs_c += locs
                        tot_pej_c += pej
                        tot_pa_c += pa
                        tot_pve_c += pve

                        c_data.append([
                            zon,
                            f"{ops:,}".replace(",", "\u202f"),
                            f"{locs:,}".replace(",", "\u202f"),
                            f"{pej:,}".replace(",", "\u202f"),
                            f"{pa:,}".replace(",", "\u202f"),
                            f"{pve:,}".replace(",", "\u202f")
                        ])

                    c_data.append([
                        "Total PNF",
                        f"{tot_ops_c:,}".replace(",", "\u202f"),
                        f"{tot_locs_c:,}".replace(",", "\u202f"),
                        f"{tot_pej_c:,}".replace(",", "\u202f"),
                        f"{tot_pa_c:,}".replace(",", "\u202f"),
                        f"{tot_pve_c:,}".replace(",", "\u202f")
                    ])

                    c_widths = [0.38 * ctx.avail_w, 0.15 * ctx.avail_w, 0.17 * ctx.avail_w, 0.10 * ctx.avail_w, 0.10 * ctx.avail_w, 0.10 * ctx.avail_w]
                    c_aligns = ["L", "R", "R", "R", "R", "R"]
                    tbl_c = ofb_table(c_data, col_widths=c_widths, col_aligns=c_aligns)
                    ctx.builder.story.append(tbl_c)
                    
                    note_coeur_txt = (
                        "<i>* Note : Les PA et PEJ sont géolocalisés à partir des coordonnées précises de l'opération ou de l'infraction. "
                        "Les PVe sont affectés selon le centroïde de leur commune d'infraction.</i>"
                    )
                    style_note_coeur = ParagraphStyle(
                        "CoeurVsAoaNote",
                        parent=ctx.builder.styles.get("BodySmall", ctx.builder.styles["BodyText"]),
                        fontSize=7,
                        leading=8.5,
                        textColor=colors.HexColor("#555555"),
                        alignment=TA_CENTER,
                    )
                    ctx.builder.story.append(Spacer(1, 2))
                    ctx.builder.story.append(Paragraph(note_coeur_txt, style_note_coeur))
                    ctx.builder.add_spacer(6)
            except Exception:
                pass

        # 2. Infographie Typologie des Usagers
        csv_usag = ctx.out_dir / "controles_global_par_usager.csv"
        if csv_usag.exists():
            try:
                df_u = pd.read_csv(csv_usag, sep=";", encoding="utf-8")
                if not df_u.empty:
                    u_data = [["Catégorie d'usager contrôlé", "Opérations", "Localisations", "Part (%)"]]
                    u_chart_dict = {}
                    tot_ops_u = sum(df_u["nb_operations"].astype(int)) if "nb_operations" in df_u.columns else 1
                    
                    for _, r in df_u.iterrows():
                        u_name = str(r["type_usager"]).split(' (')[0]
                        u_ops = int(r["nb_operations"]) if "nb_operations" in r else int(r["nb"])
                        u_locs = int(r["nb"]) if "nb" in r else u_ops
                        pct = round((u_ops / tot_ops_u * 100), 1) if tot_ops_u > 0 else 0
                        
                        u_chart_dict[u_name] = u_ops
                        u_data.append([
                            u_name,
                            f"{u_ops:,}".replace(",", "\u202f"),
                            f"{u_locs:,}".replace(",", "\u202f"),
                            f"{pct} %"
                        ])

                    u_widths = [0.46 * ctx.avail_w, 0.18 * ctx.avail_w, 0.20 * ctx.avail_w, 0.16 * ctx.avail_w]
                    u_aligns = ["L", "R", "R", "R"]
                    tbl_u = ofb_table(u_data, col_widths=u_widths, col_aligns=u_aligns)
                    
                    # Chart donut usagers à côté du tableau
                    if u_chart_dict:
                        u_chart_path = chart_pie_legend_right(
                            u_chart_dict,
                            "Répartition des contrôles par Type d'usager",
                            ctx.tmp_dir,
                            "pnf_usagers_donut.png",
                            figure_scale=ctx.figure_scale,
                            donut=True,
                            legend_fontsize=8.0
                        )
                        img_u_chart = _create_proportional_rl_image(Path(u_chart_path), ctx.avail_w * 0.85, "Graphique usagers indisponible", ctx.builder.styles)
                        
                        grid_table = Table([[tbl_u], [Spacer(1, 4)], [img_u_chart]], colWidths=[ctx.avail_w])
                        grid_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 0),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                            ('TOPPADDING', (0, 0), (-1, -1), 0),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                        ]))
                        ctx.builder.story.append(grid_table)
                    else:
                        ctx.builder.story.append(tbl_u)
            except Exception:
                pass

        ctx.builder.story.append(PageBreak())

    # --- PAGE 3 : TABLEAU COMPARATIF INTERDÉPARTEMENTAL & GRAPHIQUE DES PROCÉDURES ---
    if not df.empty:
        df["departement"] = df["departement"].astype(str)
        depts = sorted(df["departement"].unique().tolist())

        # 1. Construction du tableau comparatif interdépartemental
        table_data = [["Dépt", "Libellé département", "Opérations", "Localisations", "PEJ", "PA", "PVe"]]
        tot_ops, tot_locs, tot_pej, tot_pa, tot_pve = 0, 0, 0, 0, 0

        for d in depts:
            sub = df[df["departement"] == d]
            ops = int(sub["nb_operations"].sum()) if "nb_operations" in sub.columns else 0
            locs = int(sub["nb_localisations"].sum()) if "nb_localisations" in sub.columns else 0
            pej = int(sub["nb_pej"].sum()) if "nb_pej" in sub.columns else 0
            pa = int(sub["nb_pa"].sum()) if "nb_pa" in sub.columns else 0
            pve = int(sub["nb_pve"].sum()) if "nb_pve" in sub.columns else 0

            tot_ops += ops
            tot_locs += locs
            tot_pej += pej
            tot_pa += pa
            tot_pve += pve

            table_data.append([
                d,
                get_dept_name(d),
                f"{ops:,}".replace(",", "\u202f"),
                f"{locs:,}".replace(",", "\u202f"),
                f"{pej:,}".replace(",", "\u202f"),
                f"{pa:,}".replace(",", "\u202f"),
                f"{pve:,}".replace(",", "\u202f")
            ])

        # Ligne de totalisation régionale
        table_data.append([
            "Total",
            "Périmètre PNF" if is_pnf else "Périmètre régional",
            f"{tot_ops:,}".replace(",", "\u202f"),
            f"{tot_locs:,}".replace(",", "\u202f"),
            f"{tot_pej:,}".replace(",", "\u202f"),
            f"{tot_pa:,}".replace(",", "\u202f"),
            f"{tot_pve:,}".replace(",", "\u202f")
        ])

        col_widths = [
            0.08 * ctx.avail_w,
            0.34 * ctx.avail_w,
            0.12 * ctx.avail_w,
            0.14 * ctx.avail_w,
            0.10 * ctx.avail_w,
            0.10 * ctx.avail_w,
            0.12 * ctx.avail_w
        ]
        col_aligns = ["C", "L", "R", "R", "R", "R", "R"]

        tbl_interdept = ofb_table(table_data, col_widths=col_widths, col_aligns=col_aligns)
        ctx.builder.story.append(tbl_interdept)
        ctx.builder.add_spacer(12)

        # 2. Graphique comparatif des procédures en barres empilées
        try:
            depts_labels = [f"{d} - {get_dept_name(d)}" for d in depts]
            categories = ["PEJ", "PA", "PVe"]
            data_by_cat = {
                "PEJ": [int(df[df["departement"] == d]["nb_pej"].sum()) if "nb_pej" in df.columns else 0 for d in depts],
                "PA": [int(df[df["departement"] == d]["nb_pa"].sum()) if "nb_pa" in df.columns else 0 for d in depts],
                "PVe": [int(df[df["departement"] == d]["nb_pve"].sum()) if "nb_pve" in df.columns else 0 for d in depts]
            }
            
            chart_path = chart_interdept_stacked_bar(
                depts_labels,
                categories,
                data_by_cat,
                ctx.tmp_dir,
                "interdept_procedures.png",
                title="Comparaison de l'activité procédurale par département",
                figure_scale=ctx.figure_scale
            )
            img_chart = _create_proportional_rl_image(Path(chart_path), ctx.avail_w * ctx.chart_bar_w, "Graphique comparatif indisponible", ctx.builder.styles)
            ctx.builder.story.append(img_chart)
            ctx.builder.add_spacer(5)
        except Exception as e:
            ctx.builder.add_paragraph(f"<i>Impossible d'afficher le graphique comparatif : {e}</i>")

        # 3. Saisonnalité de l'activité (Courbes mensuelles)
        sec_enr = (getattr(ctx, "presentation_cfg", {}) or {}).get("sections_enrichies", {})
        sais_cfg = sec_enr.get("saisonnalite", {})
        sais_enabled = sais_cfg.get("enabled", False)

        csv_sais = ctx.out_dir / "saisonnalite_mensuelle.csv"
        if sais_enabled and csv_sais.exists():
            try:
                df_sais = pd.read_csv(csv_sais, sep=";", encoding="utf-8")
                if not df_sais.empty:
                    from core.common.rendus_graphiques import chart_line_evolution
                    x_labs = df_sais["mois_lib"].tolist()
                    s_series = {
                        "Opérations de contrôle": df_sais["nb_operations"].tolist(),
                        "Infractions relevées (PEJ/PVe/PA)": df_sais["nb_infractions"].tolist()
                    }
                    sais_title = sais_cfg.get("title", "1.3 Saisonnalité mensuelle de l'activité")
                    path_sais = chart_line_evolution(
                        x_labs,
                        s_series,
                        "Saisonnalité mensuelle de l'activité et des infractions",
                        "Nombre",
                        ctx.tmp_dir,
                        "saisonnalite_courbes.png",
                        figure_scale=ctx.figure_scale
                    )
                    img_sais = _create_proportional_rl_image(Path(path_sais), ctx.avail_w * 0.85, "Graphique saisonnalité indisponible", ctx.builder.styles)
                    ctx.builder.story.append(PageBreak())
                    ctx.builder.add_paragraph(f"<b>{sais_title}</b>", style="Heading2")
                    ctx.builder.add_spacer(4)
                    ctx.builder.story.append(img_sais)
                    ctx.builder.add_spacer(6)
            except Exception as e_sais:
                logger.warning(f"Rendu saisonnalité : {e_sais}")

        # 4. Top Infractions fusionné (Top PEJ + Top PVe)
        top_cfg = sec_enr.get("top_infractions", {})
        top_enabled = top_cfg.get("enabled", False)


        csv_top = ctx.out_dir / "top_infractions_pej_pve.csv"
        if top_enabled and csv_top.exists():
            try:
                df_top = pd.read_csv(csv_top, sep=";", encoding="utf-8")
                if not df_top.empty:
                    top_data = [["Procédure", "Thème SNC", "N° NATINF", "Libellé de l'infraction", "Nature juridique", "Total"]]
                    for _, r in df_top.iterrows():
                        top_data.append([
                            str(r.get("procedure", "")),
                            str(r.get("theme_snc", "")),
                            str(r.get("numero_natinf", "")),
                            str(r.get("libelle_infraction", "")),
                            str(r.get("nature_juridique", "")),
                            f"{int(r.get('nb_infractions', 0)):,}".replace(",", "\u202f")
                        ])

                    t_widths = [0.12 * ctx.avail_w, 0.22 * ctx.avail_w, 0.12 * ctx.avail_w, 0.34 * ctx.avail_w, 0.12 * ctx.avail_w, 0.08 * ctx.avail_w]

                    t_aligns = ["C", "L", "C", "L", "C", "R"]
                    tbl_top_natinf = ofb_table(top_data, col_widths=t_widths, col_aligns=t_aligns)
                    top_title = top_cfg.get("title", "1.4 Principales infractions relevées (Top 5 PEJ & Top 5 PVe)")
                    ctx.builder.add_paragraph(f"<b>{top_title}</b>", style="Heading2")
                    ctx.builder.add_spacer(4)
                    ctx.builder.story.append(tbl_top_natinf)
                    ctx.builder.add_spacer(6)
            except Exception as e_top:
                logger.warning(f"Rendu top infractions : {e_top}")

    else:
        ctx.builder.add_paragraph("<i>Aucune donnée régionale détaillée disponible pour la synthèse interdépartementale.</i>")


def render_sec_region_fiches(ctx: PdfContext) -> None:
    """Rendu de la Partie 2 : Fiches Départementales (1 Page A4 portrait stricte dans le rapport consolidé)."""
    csv_path = ctx.out_dir / "region_detail_par_dept.csv"
    if not csv_path.exists():
        ctx.builder.add_paragraph("Aucune donnée régionale détaillée disponible.")
        return

    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    if df.empty:
        ctx.builder.add_paragraph("Aucune donnée régionale détaillée disponible.")
        return

    df["departement"] = df["departement"].astype(str)
    depts = sorted(df["departement"].unique().tolist())

    # Chargement des indicateurs complémentaires départementaux
    df_nc = pd.DataFrame()
    csv_nc = ctx.out_dir / "non_conformite_global_et_dept.csv"
    if csv_nc.exists():
        try:
            df_nc = pd.read_csv(csv_nc, sep=";", encoding="utf-8")
            if not df_nc.empty and "departement" in df_nc.columns:
                df_nc["departement"] = df_nc["departement"].astype(str)
        except Exception:
            pass

    df_mail = pd.DataFrame()
    csv_mail = ctx.out_dir / "maillage_communes_dept.csv"
    if csv_mail.exists():
        try:
            df_mail = pd.read_csv(csv_mail, sep=";", encoding="utf-8")
            if not df_mail.empty and "departement" in df_mail.columns:
                df_mail["departement"] = df_mail["departement"].astype(str)
        except Exception:
            pass

    df_usg_dept = pd.DataFrame()
    csv_usg_dept = ctx.out_dir / "usagers_par_dept.csv"
    if csv_usg_dept.exists():
        try:
            df_usg_dept = pd.read_csv(csv_usg_dept, sep=";", encoding="utf-8")
            if not df_usg_dept.empty and "departement" in df_usg_dept.columns:
                df_usg_dept["departement"] = df_usg_dept["departement"].astype(str)
        except Exception:
            pass

    dept_dir = ctx.out_dir / "departements"
    if dept_dir.exists():
        for old_f in dept_dir.glob("Fiche_Dept_*.pdf"):
            try:
                old_f.unlink()
            except Exception:
                pass
    dept_dir.mkdir(parents=True, exist_ok=True)

    title_sec2 = ctx.section_title.get("sec_region_fiches", "2. Fiches départementales")

    for idx, d in enumerate(depts):
        dept_str = str(d)
        dept_name = get_dept_name(dept_str)
        df_dept = df[df["departement"] == dept_str]

        # Élimination du titre orphelin : le titre du chapitre 2 est posé en haut de la page 1 de chaque fiche
        ctx.builder.add_page_break()
        if idx == 0:
            ctx.builder.add_section("sec_region_fiches", title_sec2, level=1)

        sec_id = f"sec_dept_{dept_str}"
        sec_label = f"Département {dept_str} - {dept_name}"
        ctx.builder.add_section(sec_id, sec_label, level=2, toc_level=1)

        total_ops = int(df_dept["nb_operations"].sum()) if not df_dept.empty else 0
        total_locs = int(df_dept["nb_localisations"].sum()) if not df_dept.empty else 0
        total_pej = int(df_dept["nb_pej"].sum()) if not df_dept.empty else 0
        total_pa = int(df_dept["nb_pa"].sum()) if not df_dept.empty else 0
        total_pve = int(df_dept["nb_pve"].sum()) if not df_dept.empty else 0

        prof_id = str((ctx.profile or {}).get("id", "")) if hasattr(ctx, "profile") else "global"
        is_pnf = str(prof_id).strip().lower() in ("pnf_v2", "pnf")
        csv_coeur_path = ctx.out_dir / "pnf_coeur_vs_aoa.csv"
        
        ops_coeur_dept = 0
        if is_pnf and csv_coeur_path.exists():
            try:
                df_coeur = pd.read_csv(csv_coeur_path, sep=";", encoding="utf-8")
                if not df_coeur.empty:
                    df_coeur["departement"] = df_coeur["departement"].astype(str)
                    sub_c = df_coeur[(df_coeur["departement"] == dept_str) & (df_coeur["zonage"] == "Cœur de parc")]
                    ops_coeur_dept = int(sub_c["nb_operations"].sum()) if not sub_c.empty else 0
            except Exception:
                pass

        # Récupération Taux de non-conformité et Maillage communal
        pct_nc_str = "0 %"
        if not df_nc.empty:
            sub_nc = df_nc[df_nc["departement"] == dept_str]
            if not sub_nc.empty:
                pct_nc_str = f"{float(sub_nc['pct_non_conformite'].iloc[0])} %"

        maillage_str = "0 %"
        if not df_mail.empty:
            sub_m = df_mail[df_mail["departement"] == dept_str]
            if not sub_m.empty:
                c_ctrl = int(sub_m["communes_controlees"].iloc[0])
                c_tot = int(sub_m["total_communes"].iloc[0])
                p_m = float(sub_m["pct_maillage"].iloc[0])
                maillage_str = f"{p_m} % ({c_ctrl}/{c_tot} com)"

        sec_enr = (getattr(ctx, "presentation_cfg", {}) or {}).get("sections_enrichies", {})
        fiches_cfg = sec_enr.get("fiches_departementales", {})
        show_nc = fiches_cfg.get("afficher_taux_non_conformite", False)
        show_mail = fiches_cfg.get("afficher_maillage_communes", False)
        visuel_droite = fiches_cfg.get("visuel_droite", "domaines")
        tab_synth = fiches_cfg.get("tableau_synthese", "domaine")
        limit_themes = int(fiches_cfg.get("limit_themes_snc", 10))

        if is_pnf and ops_coeur_dept > 0:
            dept_kfis = [
                (str(total_ops), "Opérations AOA"),
                (f"{ops_coeur_dept}", "dont Cœur de parc"),
                (f"{total_pve} / {total_pej} / {total_pa}", "PVe / PEJ / PA")
            ]
        else:
            dept_kfis = [
                (str(total_ops), "Opérations"),
                (str(total_locs), "Localisations"),
                (f"{total_pej} / {total_pa} / {total_pve}", "PEJ / PA / PVe")
            ]

        if show_nc:
            dept_kfis.append((pct_nc_str, "Non-conformité"))
        if show_mail:
            dept_kfis.append((maillage_str, "Maillage territorial"))

        # 1. Traitement pour le Rapport Consolidé Régional (1 Page A4 portrait)
        if df_dept.empty or (total_ops == 0 and total_locs == 0 and total_pej == 0):
            ctx.builder.add_callout_box(
                f"Aucun contrôle ou donnée répertorié pour le département {dept_str} - {dept_name} sur le périmètre sélectionné.",
                title="Département sans activité ciblée"
            )
        else:
            spacer_h = 3 if (show_nc or show_mail or visuel_droite == "usagers" or tab_synth == "theme_snc") else 4
            ctx.builder.add_key_figures(dept_kfis)
            ctx.builder.add_spacer(spacer_h)

            prof_id = str((ctx.profile or {}).get("id", "")) if hasattr(ctx, "profile") else "global"
            vignette_path = _generate_dept_vignette(dept_str, ctx.out_dir, ctx.tmp_dir, f"vignette_dept_{dept_str}.png", figure_scale=ctx.figure_scale, profile_id=prof_id)
            vignette_w = ctx.avail_w * 0.44 if (show_nc or show_mail or visuel_droite == "usagers") else ctx.avail_w * 0.46
            img_vignette = _create_proportional_rl_image(vignette_path, vignette_w, "Vignette cartographique", ctx.builder.styles, max_h=200.0)

            # Visuel de droite : Donut Usagers ou Donut Domaines selon la config
            pie_dict = {}
            pie_title = ""
            if visuel_droite == "usagers" and not df_usg_dept.empty:
                sub_usg = df_usg_dept[df_usg_dept["departement"] == dept_str]
                if not sub_usg.empty:
                    pie_dict = {str(r["type_usager"]): int(r["nb_operations"]) for _, r in sub_usg.iterrows() if int(r["nb_operations"]) > 0}
                    pie_title = f"Types d'usagers ({dept_name})"
            else:
                cols_dom = [c for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"] if c in df_dept.columns]
                df_dom = df_dept.groupby("domaine")[cols_dom].sum().reset_index()
                pie_dict = {str(r["domaine"]): int(r["nb_localisations"]) for _, r in df_dom.iterrows() if r["nb_localisations"] > 0}
                pie_title = f"Domaines ({dept_name})"

            if pie_dict:
                img_name = f"pie_dept_{dept_str}.png"
                pie_path = chart_pie_legend_right(
                    pie_dict,
                    pie_title,
                    ctx.tmp_dir,
                    img_name,
                    figure_scale=ctx.figure_scale,
                    legend_fontsize=6.5 if visuel_droite == "usagers" else 7.0
                )
                pie_w = ctx.avail_w * 0.46 if (show_nc or show_mail or visuel_droite == "usagers") else ctx.avail_w * 0.48
                img_pie = _create_proportional_rl_image(Path(pie_path), pie_w, "Graphique indisponible", ctx.builder.styles, max_h=200.0)
            else:
                body_s = ctx.builder.styles.get("BodyText", ctx.builder.styles.get("Normal"))
                img_pie = Paragraph("<i>Aucune donnée visuelle</i>", body_s)

            double_visuel_tbl = Table(
                [[img_vignette, img_pie]],
                colWidths=[ctx.avail_w * 0.48, ctx.avail_w * 0.48]
            )
            double_visuel_tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            ctx.builder.story.append(double_visuel_tbl)
            ctx.builder.add_spacer(spacer_h)

            # Tableau de Synthèse : Thème SNC ou Domaine selon la config
            if tab_synth == "theme_snc":
                csv_td = ctx.out_dir / "theme_snc_par_dept.csv"
                df_ts = pd.DataFrame()
                if csv_td.exists():
                    try:
                        df_ts = pd.read_csv(csv_td, sep=";", encoding="utf-8")
                        if not df_ts.empty and "departement" in df_ts.columns:
                            df_ts["departement"] = df_ts["departement"].astype(str)
                            df_ts = df_ts[df_ts["departement"] == dept_str]
                    except Exception:
                        df_ts = pd.DataFrame()

                if df_ts.empty or "nb_pej" not in df_ts.columns or df_ts["nb_pej"].sum() == 0:
                    # Regroupement direct sur df_dept (contient les effectifs réels nb_pej, nb_pa, nb_pve)
                    df_ts = df_dept.copy()
                    df_ts["theme_snc"] = df_ts["theme"].fillna(df_ts["domaine"]).astype(str) if "theme" in df_ts.columns else df_ts["domaine"].astype(str)

                cols_sum = [c for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"] if c in df_ts.columns]
                for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]:
                    if c not in cols_sum:
                        df_ts[c] = 0

                df_ts_sorted = df_ts.groupby("theme_snc")[["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]].sum().reset_index()
                df_ts_sorted = df_ts_sorted.sort_values(by="nb_localisations", ascending=False)
                top_df = df_ts_sorted.head(limit_themes)
                other_df = df_ts_sorted.iloc[limit_themes:]


                tbl_dept = [["Thème SNC", "Opérations", "Localisations", "PEJ / PA / PVe"]]
                for _, r in top_df.iterrows():
                    th_label = re.sub(r"^\[\d+\]\s*", "", str(r["theme_snc"])).strip()
                    tbl_dept.append([
                        th_label,
                        str(int(r["nb_operations"])),
                        str(int(r["nb_localisations"])),
                        f"{int(r.get('nb_pej', 0))} / {int(r.get('nb_pa', 0))} / {int(r.get('nb_pve', 0))}"
                    ])
                if not other_df.empty:
                    tbl_dept.append([
                        f"Autres thèmes ({len(other_df)})",
                        str(int(other_df["nb_operations"].sum())),
                        str(int(other_df["nb_localisations"].sum())),
                        f"{int(other_df['nb_pej'].sum())} / {int(other_df['nb_pa'].sum())} / {int(other_df['nb_pve'].sum())}"
                    ])

                caption_txt = f"Synthèse par Thème SNC - {dept_name}"
            else:
                cols_dom = [c for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"] if c in df_dept.columns]
                df_dom = df_dept.groupby("domaine")[cols_dom].sum().reset_index()
                df_dom_sorted = df_dom.sort_values(by="nb_localisations", ascending=False)
                top5_df = df_dom_sorted.head(5)
                other_df = df_dom_sorted.iloc[5:]

                tbl_dept = [["Domaine Métier", "Opérations", "Localisations", "PEJ / PA / PVe"]]
                for _, r in top5_df.iterrows():
                    dom_label = re.sub(r"^\[\d+\]\s*", "", str(r["domaine"])).strip()
                    tbl_dept.append([
                        dom_label,
                        str(int(r["nb_operations"])),
                        str(int(r["nb_localisations"])),
                        f"{int(r.get('nb_pej', 0))} / {int(r.get('nb_pa', 0))} / {int(r.get('nb_pve', 0))}"
                    ])
                if not other_df.empty:
                    tbl_dept.append([
                        f"Autres domaines ({len(other_df)})",
                        str(int(other_df["nb_operations"].sum())),
                        str(int(other_df["nb_localisations"].sum())),
                        f"{int(other_df['nb_pej'].sum())} / {int(other_df['nb_pa'].sum())} / {int(other_df['nb_pve'].sum())}"
                    ])
                caption_txt = f"Synthèse par domaine principal - {dept_name}"

            ctx.builder.add_table(
                tbl_dept,
                caption=caption_txt,
                col_widths=[ctx.avail_w * 0.40, ctx.avail_w * 0.20, ctx.avail_w * 0.20, ctx.avail_w * 0.20],
                col_aligns=["LEFT", "CENTER", "CENTER", "CENTER"],
                keep_together=True
            )

            ctx.builder.add_spacer(3)




        # 2. Export du PDF autonome individuel 2-PAGES (departements/Fiche_Dept_<Code>.pdf)
        try:
            dept_pdf_path = dept_dir / f"Fiche_Dept_{dept_str}.pdf"
            b_dept = PDFReportBuilder(
                dept_pdf_path,
                f"Bilan Départemental {dept_str} - {dept_name}",
                title=f"Bilan Départemental {dept_str} - {dept_name}",
                content_only=True
            )
            b_dept.begin_content_pages()
            
            # --- PAGE 1 DU PDF AUTONOME ---
            b_dept.add_section("sec_dept_solo", f"Département {dept_str} - {dept_name}", level=1)
            if df_dept.empty or (total_ops == 0 and total_locs == 0 and total_pej == 0):
                b_dept.add_callout_box(
                    f"Aucun contrôle ou donnée répertorié pour le département {dept_str} - {dept_name} sur le périmètre sélectionné.",
                    title="Département sans activité ciblée"
                )
            else:
                b_dept.add_key_figures(dept_kfis)
                b_dept.add_spacer(4)
                b_dept.story.append(double_visuel_tbl)
                b_dept.add_spacer(4)
                b_dept.add_table(
                    tbl_dept,
                    caption=f"Synthèse par domaine (Top 5) - {dept_name}",
                    col_widths=[b_dept.avail_w * 0.40, b_dept.avail_w * 0.20, b_dept.avail_w * 0.20, b_dept.avail_w * 0.20],
                    col_aligns=["LEFT", "CENTER", "CENTER", "CENTER"],
                    keep_together=True
                )
                
                # --- PAGE 2 DU PDF AUTONOME : DÉTAIL MATRICIEL EXHAUSTIF ---
                b_dept.add_page_break()
                b_dept.add_section("sec_dept_solo_detail", f"Détail par domaine et thème - {dept_name}", level=2)
                
                headers_full = ["Domaine Métier", "Thème", "Opérations", "Localisations", "PEJ / PA / PVe"]
                tbl_full = [headers_full]
                
                for _, r_full in df_dept.iterrows():
                    tbl_full.append([
                        str(r_full.get("domaine", "")),
                        str(r_full.get("theme", "")),
                        str(int(r_full.get("nb_operations", 0))),
                        str(int(r_full.get("nb_localisations", 0))),
                        f"{int(r_full.get('nb_pej', 0))} / {int(r_full.get('nb_pa', 0))} / {int(r_full.get('nb_pve', 0))}"
                    ])
                
                b_dept.add_table(
                    tbl_full,
                    caption=f"Détail exhaustif des contrôles et procédures - {dept_name}",
                    col_widths=[b_dept.avail_w * 0.30, b_dept.avail_w * 0.30, b_dept.avail_w * 0.13, b_dept.avail_w * 0.13, b_dept.avail_w * 0.14],
                    col_aligns=["LEFT", "LEFT", "CENTER", "CENTER", "CENTER"],
                    keep_together=False
                )
                
            b_dept.build()
        except Exception as e_dept_pdf:
            pass


def render_sec_region_detail(ctx: PdfContext) -> None:
    """Rendu de l'Annexe Technique Détaillée (Détail matriciel par domaine et par thème)."""
    title = ctx.section_title.get("secregion", "Détail par département")
    ctx.builder.add_section("secregion", title)

    csv_path = ctx.out_dir / "region_detail_par_dept.csv"
    if not csv_path.exists():
        ctx.builder.add_paragraph("Aucune donnée régionale détaillée disponible.")
        return

    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    if df.empty:
        ctx.builder.add_paragraph("Aucune donnée régionale détaillée disponible.")
        return

    df["departement"] = df["departement"].astype(str)
    for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]:
        if c not in df.columns:
            df[c] = 0

    depts = sorted(df["departement"].unique().tolist())

    for domaine, group_dom in df.groupby("domaine"):
        if domaine == "Hors domaine":
            continue

        ctx.builder.add_section(f"secregion_{domaine}", f"Domaine : {domaine}", level=3)
        agg_theme = group_dom.groupby("theme")[["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]].sum().reset_index()

        headers = ["Thème", "Département", "Opérations", "Localisations", "PEJ / PA / PVe"]
        col_widths = [ctx.avail_w * 0.25, ctx.avail_w * 0.25, ctx.avail_w * 0.15, ctx.avail_w * 0.15, ctx.avail_w * 0.20]
        col_aligns = ["LEFT", "LEFT", "CENTER", "CENTER", "CENTER"]
        tbl = [headers]

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

                tbl.append([
                    theme_label,
                    dept_label,
                    str(int(v_ops)),
                    str(int(v_locs)),
                    f"{int(v_pej)} / {int(v_pa)} / {int(v_pve)}"
                ])

            tot_suites = f"{int(row_theme['nb_pej'])} / {int(row_theme['nb_pa'])} / {int(row_theme['nb_pve'])}"
            tbl.append([
                "",
                "Total Région",
                str(int(row_theme["nb_operations"])),
                str(int(row_theme["nb_localisations"])),
                tot_suites
            ])

        ctx.builder.add_table(
            tbl,
            caption=f"Détail par département pour le domaine {domaine}",
            col_widths=col_widths,
            col_aligns=col_aligns,
            keep_together=True
        )
        ctx.builder.add_spacer(5)