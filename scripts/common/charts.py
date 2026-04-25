"""Graphiques matplotlib pour les bilans (camemberts, barres, cartes)."""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from scripts.common.ofb_charte import (
    COLOR_PRIMARY,
    CHART_PIE_COLORS,
    CHART_BAR_GROUPED_COLORS,
    COLOR_CHART_4,
)
from scripts.common.percent_format import int_percents_largest_remainder


def _pick_mpl_font() -> str:
    """Pick the best matplotlib-compatible font from the OFB chain."""
    from matplotlib.font_manager import fontManager
    available = {f.name for f in fontManager.ttflist}
    for name in ("Marianne", "Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"):
        if name in available:
            return name
    return "sans-serif"


# Dimensions harmonisées (pouces) pour export PNG puis intégration PDF homogène.
CHART_FIG_WIDTH = 7.2
# Camemberts avec peu de parts (ex. résultats Conforme / Infraction / Manquement) : même base que PDF.
CHART_FIG_HEIGHT_PIE_COMPACT = 4.0
# Hauteur des barres / barres groupées-empilées : +50 % vs ancienne base pour lisibilité PDF.
CHART_FIG_HEIGHT_BAR = 3.5 * 1.5
CHART_FIG_HEIGHT_WITH_LEGEND = 4.15 * 1.5


def apply_mpl_style() -> None:
    """Style matplotlib pour les graphiques exportés en PNG."""
    plt.rcParams["font.family"] = _pick_mpl_font()
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 10
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["legend.frameon"] = False


def _legend_below_axis(ax, *, ncol: int | None = None) -> None:
    """Légende centrée sous le graphique (repère axes, y négatif)."""
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    n = len(handles)
    if ncol is None:
        ncol = min(4, max(2, n))
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=ncol,
        fontsize=8,
        frameon=False,
    )


def _tight_with_legend_space(fig, *, bottom: float = 0.20, top: float = 0.92) -> None:
    """Marges figure après placement de légende sous l'axe."""
    fig.tight_layout(rect=(0.04, bottom, 0.96, top))


def save_chart(fig, tmp_dir: Path, name: str, *, dpi: int = 150) -> str:
    path = str(tmp_dir / name)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def chart_pie(
    data: dict,
    title: str,
    tmp_dir: Path,
    name: str,
    *,
    figsize: tuple[float, float] | None = None,
) -> str:
    apply_mpl_style()
    labels = list(data.keys())
    values = list(data.values())
    if figsize is not None:
        fig_w, fig_h = figsize
    else:
        fig_w = CHART_FIG_WIDTH
        fig_h = (
            CHART_FIG_HEIGHT_WITH_LEGEND
            if len(labels) > 4
            else CHART_FIG_HEIGHT_PIE_COMPACT
        )
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    # Palette : on force une couleur rouge douce (COLOR_CHART_4) pour les parts
    # correspondant aux infractions / non-conformes, les autres utilisent la
    # palette standard CHART_PIE_COLORS.
    colors_pie = []
    keywords_inf = ("infraction", "infractions", "non conforme", "non conformes", "non-conforme", "non-conformes")
    for i, lb in enumerate(labels):
        base = CHART_PIE_COLORS[i % len(CHART_PIE_COLORS)]
        lbl = str(lb).lower()
        if any(k in lbl for k in keywords_inf):
            colors_pie.append(COLOR_CHART_4)
        else:
            colors_pie.append(base)
    total = sum(values)
    if total:
        pcts = int_percents_largest_remainder([int(v) for v in values])
        legend_labels = [
            f"{lb} : {v} ({pcts[i]} %)"
            for i, (lb, v) in enumerate(zip(labels, values))
        ]
    else:
        legend_labels = [f"{lb} : {v} (0 %)" for lb, v in zip(labels, values)]
    wedges, _ = ax.pie(
        values, startangle=90, colors=colors_pie
    )
    ax.set_aspect("equal")
    ncol = min(3, max(1, (len(legend_labels) + 2) // 3))
    ax.legend(
        wedges,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=ncol,
        fontsize=9,
        frameon=False,
    )
    ax.set_title(title, fontsize=12, fontweight="bold", color=COLOR_PRIMARY, pad=10)
    bottom = 0.26 if len(legend_labels) > 6 else 0.20
    _tight_with_legend_space(fig, bottom=bottom, top=0.90)
    # DPI un peu plus élevé : le PDF insère le camembert plus étroit que les barres.
    return save_chart(fig, tmp_dir, name, dpi=165)


def chart_bar(
    categories: list,
    values: list,
    title: str,
    ylabel: str,
    tmp_dir: Path,
    name: str,
    color=COLOR_PRIMARY,
) -> str:
    apply_mpl_style()
    fig, ax = plt.subplots(figsize=(CHART_FIG_WIDTH, CHART_FIG_HEIGHT_BAR))
    x = np.arange(len(categories))
    bar_w = 0.34 if len(categories) == 1 else 0.5
    bars = ax.bar(x, values, color=color, width=bar_w)
    if len(categories) == 1:
        ax.set_xlim(-0.9, 0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_PRIMARY, pad=10)
    ax.bar_label(bars, fmt="%g", fontsize=9, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(rect=(0.05, 0.10, 0.95, 0.92))
    return save_chart(fig, tmp_dir, name)


def chart_bar_grouped(
    group_labels,
    series: dict,
    title: str,
    ylabel: str,
    tmp_dir: Path,
    name: str,
) -> str:
    apply_mpl_style()
    fig, ax = plt.subplots(figsize=(CHART_FIG_WIDTH, CHART_FIG_HEIGHT_WITH_LEGEND))
    x = np.arange(len(group_labels))
    n = len(series)
    w = 0.18 if len(group_labels) == 1 else 0.30
    keywords_inf = ("infraction", "infractions", "non conforme", "non conformes", "non-conforme", "non-conformes")
    for i, (label, vals) in enumerate(series.items()):
        offset = (i - n / 2 + 0.5) * w
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        else:
            color = CHART_BAR_GROUPED_COLORS[i % len(CHART_BAR_GROUPED_COLORS)]
        bars = ax.bar(
            x + offset, vals, w, label=label,
            color=color,
        )
        ax.bar_label(bars, fmt="%g", fontsize=8, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels, fontsize=9)
    if len(group_labels) == 1:
        ax.set_xlim(-0.9, 0.9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_PRIMARY, pad=10)
    _legend_below_axis(ax, ncol=min(4, max(2, n)))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _tight_with_legend_space(fig, bottom=0.22, top=0.90)
    return save_chart(fig, tmp_dir, name)


def chart_bar_stacked(
    group_labels: list,
    series: dict,
    title: str,
    ylabel: str,
    tmp_dir: Path,
    name: str,
) -> str:
    """Barres empilées : chaque série est empilée sur la précédente."""
    apply_mpl_style()
    n_groups = max(1, len(group_labels))
    fig_w = max(CHART_FIG_WIDTH, min(10.0, n_groups * 0.75))
    fig, ax = plt.subplots(figsize=(fig_w, CHART_FIG_HEIGHT_WITH_LEGEND))
    x = np.arange(len(group_labels))
    bottom = np.zeros(len(group_labels))
    keywords_inf = ("infraction", "infractions", "non conforme", "non conformes", "non-conforme", "non-conformes")
    bar_w = 0.34 if len(group_labels) == 1 else 0.55
    for i, (label, vals) in enumerate(series.items()):
        vals_arr = np.array(vals, dtype=float)
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        else:
            color = CHART_BAR_GROUPED_COLORS[i % len(CHART_BAR_GROUPED_COLORS)]
        bars = ax.bar(x, vals_arr, bar_w, label=label, bottom=bottom, color=color)
        for bar, val in zip(bars, vals_arr):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(val)}",
                    ha="center", va="center", fontsize=7, fontweight="bold",
                    color="white",
                )
        bottom += vals_arr
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels, fontsize=9)
    if len(group_labels) == 1:
        ax.set_xlim(-0.9, 0.9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_PRIMARY, pad=10)
    _legend_below_axis(ax, ncol=min(4, max(2, len(series))))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _tight_with_legend_space(fig, bottom=0.22, top=0.90)
    return save_chart(fig, tmp_dir, name)


def chart_bar_horizontal_stacked(
    row_labels: list,
    series: dict,
    title: str,
    xlabel: str,
    tmp_dir: Path,
    name: str,
) -> str:
    """Barres horizontales empilées : une ligne par catégorie, segments empilés selon les séries."""
    apply_mpl_style()
    n = max(1, len(row_labels))
    y = np.arange(n)
    height = 0.62
    left = np.zeros(n)
    keywords_inf = (
        "infraction",
        "infractions",
        "non conforme",
        "non conformes",
        "non-conforme",
        "non-conformes",
    )
    # Hauteur figure : assez d'espace pour les libellés Y (types d'usager souvent longs).
    fig_h = max(CHART_FIG_HEIGHT_WITH_LEGEND, min(14.0, 0.55 * n + 2.8))
    fig, ax = plt.subplots(figsize=(CHART_FIG_WIDTH, fig_h))
    for i, (label, vals) in enumerate(series.items()):
        vals_arr = np.array(vals, dtype=float)
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        else:
            color = CHART_BAR_GROUPED_COLORS[i % len(CHART_BAR_GROUPED_COLORS)]
        bars = ax.barh(y, vals_arr, height, left=left, label=label, color=color)
        for bar, val in zip(bars, vals_arr):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(val)}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color="white",
                )
        left += vals_arr
    ax.set_yticks(y)
    ax.set_yticklabels(row_labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_PRIMARY, pad=10)
    _legend_below_axis(ax, ncol=min(4, max(2, len(series))))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _tight_with_legend_space(fig, bottom=0.18, top=0.92)
    return save_chart(fig, tmp_dir, name)


def chart_line_evolution(
    x_labels: list,
    series: dict,
    title: str,
    ylabel: str,
    tmp_dir: Path,
    name: str,
) -> str:
    """Courbe d'évolution multi-séries (un trait par indicateur)."""
    apply_mpl_style()
    n_x = max(1, len(x_labels))
    fig_w = max(CHART_FIG_WIDTH, min(10.0, n_x * 0.75))
    fig, ax = plt.subplots(figsize=(fig_w, CHART_FIG_HEIGHT_WITH_LEGEND))
    x = np.arange(len(x_labels))
    keywords_inf = ("infraction", "infractions", "non conforme", "non conformes", "non-conforme", "non-conformes")
    for i, (label, vals) in enumerate(series.items()):
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        else:
            color = CHART_BAR_GROUPED_COLORS[i % len(CHART_BAR_GROUPED_COLORS)]
        ax.plot(x, vals, marker="o", label=label, color=color, linewidth=2, markersize=6)
        for xi, v in zip(x, vals):
            ax.annotate(
                str(int(v)), (xi, v),
                textcoords="offset points", xytext=(0, 8),
                ha="center", fontsize=8, fontweight="bold", color=color,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color=COLOR_PRIMARY, pad=10)
    _legend_below_axis(ax, ncol=min(4, max(2, len(series))))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _tight_with_legend_space(fig, bottom=0.22, top=0.90)
    return save_chart(fig, tmp_dir, name)


def _make_map(
    communes_gdf: gpd.GeoDataFrame,
    agg_data,
    insee_col: str,
    column: str,
    cmap: str,
    legend_label: str,
    title: str,
    tmp_dir: Path,
    name: str,
    points_gdf=None,
    points_label=None,
) -> str:
    """Génère une carte choroplèthe PNG pour intégration dans le PDF."""
    apply_mpl_style()
    communes_simple = communes_gdf.copy()
    communes_simple["geometry"] = communes_simple.geometry.simplify(
        tolerance=0.0005, preserve_topology=True
    )

    if agg_data is not None and not agg_data.empty:
        merge_col = (
            "insee_comm" if "insee_comm" in agg_data.columns else agg_data.columns[0]
        )
        geo = communes_simple.merge(
            agg_data, left_on=insee_col, right_on=merge_col, how="left"
        )
    else:
        geo = communes_simple.copy()
        geo[column] = 0

    xmin, ymin, xmax, ymax = communes_gdf.total_bounds
    marge = 0.02 * max(xmax - xmin, ymax - ymin)

    fig, ax = plt.subplots(figsize=(7, 7))
    geo[column] = geo[column].fillna(0)
    geo.plot(
        column=column,
        cmap=cmap,
        linewidth=0.3,
        edgecolor="white",
        legend=True,
        ax=ax,
        legend_kwds={"label": legend_label, "shrink": 0.6, "aspect": 25},
        missing_kwds={"color": "lightgrey", "label": "Aucune donnée"},
        rasterized=True,
    )

    if points_gdf is not None and not points_gdf.empty:
        if (
            communes_gdf.crs is not None
            and points_gdf.crs != communes_gdf.crs
        ):
            points_gdf = points_gdf.to_crs(communes_gdf.crs)
        points_gdf.plot(
            ax=ax,
            color="#E76F51",
            markersize=18,
            alpha=0.8,
            label=points_label or "Points",
            edgecolor="white",
            linewidth=0.3,
            rasterized=True,
        )
        ax.legend(fontsize=8, loc="lower left")

    ax.set_xlim(xmin - marge, xmax + marge)
    ax.set_ylim(ymin - marge, ymax + marge)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=13, fontweight="bold", color=COLOR_PRIMARY, pad=12)
    ax.axis("off")

    scale_len_m = 20000
    if communes_gdf.crs and communes_gdf.crs.is_geographic:
        scale_len_deg = scale_len_m / 111320
    else:
        scale_len_deg = scale_len_m
    sx = xmin + marge
    sy = ymin + marge * 0.5
    ax.plot([sx, sx + scale_len_deg], [sy, sy], color="black", linewidth=2)
    ax.text(
        sx + scale_len_deg / 2,
        sy + marge * 0.3,
        "20 km",
        ha="center",
        fontsize=8,
        fontweight="bold",
    )

    nx = xmax - marge * 0.5
    ny = ymax - marge * 1.5
    ax.annotate(
        "N",
        xy=(nx, ny),
        xytext=(nx, ny - marge * 2),
        arrowprops=dict(arrowstyle="->", lw=1.5, color="black"),
        fontsize=10,
        fontweight="bold",
        ha="center",
        va="bottom",
    )

    fig.tight_layout()
    return save_chart(fig, tmp_dir, name)
