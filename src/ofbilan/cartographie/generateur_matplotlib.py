import logging
from pathlib import Path
import matplotlib.pyplot as plt
import geopandas as gpd

logger = logging.getLogger(__name__)

COLOR_PRIMARY = "#003A76"
FONT_FAMILY = "sans-serif" # Fallback generique

def charger_couche_pochoir(dept_code: str, project_root: Path) -> gpd.GeoDataFrame:
    from ofbilan.cartographie.pochoir_helper import load_department_gdf
    try:
        return load_department_gdf(dept_code, project_root=project_root)
    except Exception as e:
        logger.warning(f"Impossible de charger le pochoir departement {dept_code}: {e}")
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry")

def tracer_carte(ax, pochoir_gdf: gpd.GeoDataFrame, layers_to_render: list):
    """Dessine le fond et les donnees sur l'axe principal."""
    # Fond general clair
    ax.set_facecolor("#f0f4f8")
    
    # Dessin du pochoir (departement)
    if not pochoir_gdf.empty:
        pochoir_gdf.plot(ax=ax, color="white", edgecolor="#CCCCCC", linewidth=1.5)
        # Ajuster emprise (extent)
        minx, miny, maxx, maxy = pochoir_gdf.total_bounds
        pad_x, pad_y = (maxx - minx)*0.05, (maxy - miny)*0.05
        ax.set_xlim(minx - pad_x, maxx + pad_x)
        ax.set_ylim(miny - pad_y, maxy + pad_y)

    # Note: On tracerait ici les `layers_to_render` avec matplotlib (geopandas plot)
    # Pour le lot 1 (Securiser le socle), on place l'infrastructure.
    ax.axis("off")

def tracer_cartouche(ax, titre: str, dept_name: str, date_deb: str, date_fin: str):
    """Dessine le panneau lateral."""
    ax.set_facecolor("white")
    ax.axis("off")
    
    # Ligne de separation
    ax.axvline(0, color=COLOR_PRIMARY, linewidth=2)
    
    # Textes
    ax.text(0.1, 0.9, "Office Français\nde la Biodiversité", fontsize=12, fontweight='bold', color=COLOR_PRIMARY, transform=ax.transAxes)
    ax.text(0.1, 0.8, titre, fontsize=16, fontweight='bold', color=COLOR_PRIMARY, transform=ax.transAxes)
    ax.text(0.1, 0.75, dept_name, fontsize=12, color="#333333", transform=ax.transAxes)
    ax.text(0.1, 0.70, f"Du {date_deb}\nau {date_fin}", fontsize=10, color="#666666", transform=ax.transAxes)
    
    # Footer
    ax.text(0.1, 0.05, "Sources: OFB, IGN\nProjection: RGF93", fontsize=8, color="#999999", transform=ax.transAxes)

def exporter_carte_matplotlib(prof, output_path: Path, dept_code: str, layers_to_render: list, project_root: Path):
    """Point d'entree principal du generateur."""
    logger.info(f"Génération Matplotlib (Fallback) pour le profil {prof.id}")
    
    fig = plt.figure(figsize=(11.69, 8.27), dpi=300) # A4 Landscape
    gs = fig.add_gridspec(1, 2, width_ratios=[4, 1], wspace=0)
    
    ax_map = fig.add_subplot(gs[0])
    ax_side = fig.add_subplot(gs[1])
    
    pochoir = charger_couche_pochoir(dept_code, project_root)
    tracer_carte(ax_map, pochoir, layers_to_render)
    
    titre = getattr(prof, "title_main", "") or getattr(prof, "title", "Bilan")
    tracer_cartouche(ax_side, titre, f"Département {dept_code}", prof.date_deb, prof.date_fin)
    
    fig.savefig(output_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return True
