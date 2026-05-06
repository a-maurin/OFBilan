"""Graphiques matplotlib pour les bilans (camemberts, barres, cartes)."""
from __future__ import annotations

import math
import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from bilans.common.ofb_charte import (
    COLOR_PRIMARY,
    CHART_PIE_COLORS,
    CHART_BAR_GROUPED_COLORS,
    COLOR_CHART_4,
)
from bilans.common.percent_format import int_percents_largest_remainder


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
# Camemberts : base harmonisée pour tous les camemberts PDF.
CHART_FIG_HEIGHT_PIE_COMPACT = 5.0
# Références typographiques : "Résultats des contrôles par type d'usager".
CHART_TITLE_FONT_SIZE_REF = 11
CHART_LEGEND_FONT_SIZE_REF = 8
# Ajustement demandé : réduire de moitié le disque des camemberts
# sans modifier la taille des légendes.
CHART_PIE_DISK_SCALE = 0.5
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


def _legend_below_axis(ax, *, ncol: int | None = None, fontsize: float = 8.0) -> None:
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
        fontsize=fontsize,
        frameon=False,
    )


def _tight_with_legend_space(fig, *, bottom: float = 0.20, top: float = 0.92) -> None:
    """Marges figure après placement de légende sous l'axe."""
    fig.tight_layout(rect=(0.04, bottom, 0.96, top))


def save_chart(fig, tmp_dir: Path, name: str, *, dpi: int = 150, tight: bool = True) -> str:
    path = str(tmp_dir / name)
    save_kw = {"dpi": dpi, "facecolor": "white"}
    if tight:
        save_kw["bbox_inches"] = "tight"
    fig.savefig(path, **save_kw)
    plt.close(fig)
    return path


def chart_pie(
    data: dict,
    title: str,
    tmp_dir: Path,
    name: str,
    *,
    figsize: tuple[float, float] | None = None,
    legend_fontsize: float | None = None,
    legend_ncol: int | None = None,
    figure_scale: float = 1.0,
) -> str:
    apply_mpl_style()
    labels = list(data.keys())
    values = list(data.values())
    fig_w = CHART_FIG_WIDTH * figure_scale if figsize is None else (figsize[0] * figure_scale)
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
    if legend_ncol is not None:
        ncol = max(1, int(legend_ncol))
    else:
        ncol = min(len(legend_labels), 4) if legend_labels else 1
    # On conserve la taille de police de référence ; on n'abaisse pas la police
    # quand la légende est dense (on augmente plutôt le nombre de lignes).
    leg_fs = CHART_LEGEND_FONT_SIZE_REF if legend_fontsize is None else float(legend_fontsize)
    # Wrap explicite des libellés de légende pour éviter toute troncature horizontale.
    wrap_width = max(42, int(fig_w * 10))
    legend_labels_wrapped = [textwrap.fill(lbl, width=wrap_width, break_long_words=False) for lbl in legend_labels]
    # Gabarit robuste : zone camembert fixe et zone légende variable.
    # Cela garantit un disque de taille identique, tandis que la hauteur
    # de l'image s'adapte au nombre de lignes de légende.
    total_legend_lines = sum((lbl.count("\n") + 1) for lbl in legend_labels_wrapped) or 1
    pie_h_in = CHART_FIG_HEIGHT_PIE_COMPACT * figure_scale * CHART_PIE_DISK_SCALE
    legend_row_h_in = 0.20 * (leg_fs / CHART_LEGEND_FONT_SIZE_REF)
    legend_h_in = 0.42 + total_legend_lines * legend_row_h_in
    top_pad_in = 0.28
    gap_in = 0.08
    bottom_pad_in = 0.14
    fig_h = pie_h_in + legend_h_in + top_pad_in + gap_in + bottom_pad_in

    fig = plt.figure(figsize=(fig_w, fig_h))
    ax = fig.add_axes(
        [
            0.12,
            (bottom_pad_in + legend_h_in + gap_in) / fig_h,
            0.76,
            pie_h_in / fig_h,
        ]
    )
    wedges, _ = ax.pie(values, startangle=90, colors=colors_pie)
    ax.set_aspect("equal")
    ax.set_title(
        title,
        fontsize=CHART_TITLE_FONT_SIZE_REF,
        fontweight="bold",
        color=COLOR_PRIMARY,
        pad=10,
    )

    ax_leg = fig.add_axes([0.06, bottom_pad_in / fig_h, 0.88, legend_h_in / fig_h])
    ax_leg.axis("off")
    ax_leg.legend(
        wedges,
        legend_labels_wrapped,
        loc="center",
        ncol=ncol,
        fontsize=leg_fs,
        frameon=False,
        handlelength=1.0,
        handletextpad=0.45,
        columnspacing=0.85,
        borderpad=0.2,
    )
    # DPI un peu plus élevé : le PDF insère le camembert plus étroit que les barres.
    # "tight bbox" inclut toute la légende dans le PNG final (pas de troncature).
    return save_chart(fig, tmp_dir, name, dpi=165, tight=True)


def chart_bar(
    categories: list,
    values: list,
    title: str,
    ylabel: str,
    tmp_dir: Path,
    name: str,
    color=COLOR_PRIMARY,
    *,
    figure_scale: float = 1.0,
) -> str:
    apply_mpl_style()
    fig, ax = plt.subplots(figsize=(CHART_FIG_WIDTH * figure_scale, CHART_FIG_HEIGHT_BAR * figure_scale))
    x = np.arange(len(categories))
    # Harmonisation demandée : largeur de colonnes réduite de moitié.
    bar_w = 0.17 if len(categories) == 1 else 0.25
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
    *,
    legend_fontsize: float = 8.0,
    legend_ncol_max: int = 4,
    figure_scale: float = 1.0,
) -> str:
    apply_mpl_style()
    fig, ax = plt.subplots(figsize=(CHART_FIG_WIDTH * figure_scale, CHART_FIG_HEIGHT_WITH_LEGEND * figure_scale))
    x = np.arange(len(group_labels))
    n = len(series)
    # Harmonisation demandée : largeur de colonnes réduite de moitié.
    w = 0.09 if len(group_labels) == 1 else 0.15
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
    _legend_below_axis(ax, ncol=min(max(1, legend_ncol_max), max(2, n)), fontsize=legend_fontsize)
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
    *,
    legend_fontsize: float = 8.0,
    legend_ncol_max: int = 4,
    figure_scale: float = 1.0,
) -> str:
    """Barres empilées : chaque série est empilée sur la précédente."""
    apply_mpl_style()
    n_groups = max(1, len(group_labels))
    fig_w = max(CHART_FIG_WIDTH, min(10.0, n_groups * 0.75)) * figure_scale
    fig, ax = plt.subplots(figsize=(fig_w, CHART_FIG_HEIGHT_WITH_LEGEND * figure_scale))
    x = np.arange(len(group_labels))
    bottom = np.zeros(len(group_labels))
    keywords_inf = ("infraction", "infractions", "non conforme", "non conformes", "non-conforme", "non-conformes")
    # Harmonisation demandée : largeur de colonnes réduite de moitié.
    bar_w = 0.17 if len(group_labels) == 1 else 0.275
    for i, (label, vals) in enumerate(series.items()):
        vals_arr = np.array(vals, dtype=float)
        lbl = str(label).lower()
        if "autre résultat" in lbl or "autre resultat" in lbl:
            color = "#555555"
        elif any(k in lbl for k in keywords_inf):
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
    _legend_below_axis(
        ax,
        ncol=min(max(1, legend_ncol_max), max(2, len(series))),
        fontsize=legend_fontsize,
    )
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
    *,
    legend_fontsize: float = 8.0,
    legend_ncol_max: int = 4,
    figure_scale: float = 1.0,
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
    fig_h = max(CHART_FIG_HEIGHT_WITH_LEGEND, min(14.0, 0.55 * n + 2.8)) * figure_scale
    fig, ax = plt.subplots(figsize=(CHART_FIG_WIDTH * figure_scale, fig_h))
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
    _legend_below_axis(
        ax,
        ncol=min(max(1, legend_ncol_max), max(2, len(series))),
        fontsize=legend_fontsize,
    )
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
    *,
    legend_fontsize: float = 8.0,
    legend_ncol_max: int = 4,
    figure_scale: float = 1.0,
) -> str:
    """Courbe d'évolution multi-séries (un trait par indicateur)."""
    apply_mpl_style()
    n_x = max(1, len(x_labels))
    fig_w = max(CHART_FIG_WIDTH, min(10.0, n_x * 0.75)) * figure_scale
    fig, ax = plt.subplots(figsize=(fig_w, CHART_FIG_HEIGHT_WITH_LEGEND * figure_scale))
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
    _legend_below_axis(
        ax,
        ncol=min(max(1, legend_ncol_max), max(2, len(series))),
        fontsize=legend_fontsize,
    )
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
