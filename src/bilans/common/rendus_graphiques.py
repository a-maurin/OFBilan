"""Graphiques matplotlib pour les bilans (camemberts, barres, cartes)."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator

from bilans.common.ofb_charte import (
    COLOR_PRIMARY,
    CHART_PIE_COLORS,
    CHART_BAR_GROUPED_COLORS,
    COLOR_CHART_4,
    COLOR_GREY,
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
# Résolution raster par défaut pour tous les éléments exportés puis intégrés aux PDF.
DEFAULT_RASTER_EXPORT_DPI = 300
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

_KEYWORDS_INFRACTION = (
    "infraction",
    "infractions",
    "non conforme",
    "non conformes",
    "non-conforme",
    "non-conformes",
)
_KEYWORDS_ATTENTE = ("en attente", "attente")


def apply_mpl_style() -> None:
    """Style matplotlib pour les graphiques exportés en PNG."""
    plt.rcParams["font.family"] = _pick_mpl_font()
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 10
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["legend.frameon"] = False


def _legend_below_axis(
    ax,
    *,
    ncol: int | None = None,
    fontsize: float = 8.0,
    anchor_y: float = -0.14,
) -> None:
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
        bbox_to_anchor=(0.5, anchor_y),
        ncol=ncol,
        fontsize=fontsize,
        frameon=False,
    )


def _legend_right_of_axis(ax, *, fontsize: float = 8.0) -> None:
    """Légende à droite du tracé (évite la superposition avec les libellés d'axe X longs / tournés)."""
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    ax.legend(
        handles,
        labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0.0,
        fontsize=fontsize,
        frameon=False,
    )


def _tight_with_legend_space(
    fig,
    *,
    bottom: float = 0.20,
    top: float = 0.92,
    left: float = 0.04,
    right: float = 0.96,
) -> None:
    """Marges figure (légende sous l'axe ou à droite selon le graphique)."""
    fig.tight_layout(rect=(left, bottom, right, top))


def save_chart(
    fig,
    tmp_dir: Path,
    name: str,
    *,
    dpi: int = DEFAULT_RASTER_EXPORT_DPI,
    tight: bool = True,
    pad_inches: float = 0.1,
) -> str:
    path = str(tmp_dir / name)
    save_kw = {"dpi": dpi, "facecolor": "white"}
    if tight:
        save_kw["bbox_inches"] = "tight"
        save_kw["pad_inches"] = pad_inches
    fig.savefig(path, **save_kw)
    plt.close(fig)
    return path


_RE_PERIODE_SEMAINE_W_VERS_S = re.compile(r"(\d{4})-W(\d{2})\b")


def _sanitize_chart_period_tick_labels(labels: list) -> list[str]:
    """
    Libellés d'axe (périodes) : retire toute mention « ISO » et affiche les semaines en YYYY-Sww
    (même si le CSV contient encore YYYY-Www ou un suffixe « (ISO) »).
    """
    out: list[str] = []
    for raw in labels:
        s = str(raw).strip()
        for frag in (" (ISO)", "(ISO)", " (Iso)", "(Iso)"):
            s = s.replace(frag, "")
        s = _RE_PERIODE_SEMAINE_W_VERS_S.sub(r"\1-S\2", s)
        out.append(s.strip())
    return out


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
    legend_percent_only: bool = False,
    apply_mpl: bool = True,
    palette: list[str] | None = None,
) -> str:
    if apply_mpl:
        apply_mpl_style()
    labels = list(data.keys())
    values = list(data.values())
    fig_w = CHART_FIG_WIDTH * figure_scale if figsize is None else (figsize[0] * figure_scale)
    # Palette : on force une couleur rouge douce (COLOR_CHART_4) pour les parts
    # correspondant aux infractions / non-conformes, les autres utilisent la
    # palette standard CHART_PIE_COLORS.
    colors_pie = []
    keywords_inf = _KEYWORDS_INFRACTION
    pie_palette = palette if palette else CHART_PIE_COLORS
    for i, lb in enumerate(labels):
        base = pie_palette[i % len(pie_palette)]
        lbl = str(lb).lower()
        if any(k in lbl for k in keywords_inf):
            colors_pie.append(COLOR_CHART_4)
        else:
            colors_pie.append(base)
    total = sum(values)
    if total:
        pcts = int_percents_largest_remainder([int(v) for v in values])
        if legend_percent_only:
            legend_labels = [f"{lb} : {pcts[i]} %" for i, lb in enumerate(labels)]
        else:
            legend_labels = [
                f"{lb} : {v} ({pcts[i]} %)"
                for i, (lb, v) in enumerate(zip(labels, values))
            ]
    else:
        legend_labels = (
            [f"{lb} : 0 %" for lb in labels]
            if legend_percent_only
            else [f"{lb} : {v} (0 %)" for lb, v in zip(labels, values)]
        )
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
    if str(title).strip():
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
    # "tight bbox" inclut toute la légende dans le PNG final (pas de troncature).
    return save_chart(fig, tmp_dir, name, dpi=DEFAULT_RASTER_EXPORT_DPI, tight=True)


def chart_pie_legend_right(
    data: dict,
    title: str,
    tmp_dir: Path,
    name: str,
    *,
    figure_scale: float = 1.0,
    legend_percent_only: bool = False,
    legend_fontsize: float = 7.5,
    apply_mpl: bool = True,
    palette: list[str] | None = None,
) -> str:
    """Camembert compact avec légende à droite (brochure, colonne étroite)."""
    if apply_mpl:
        apply_mpl_style()
    labels = list(data.keys())
    values = list(data.values())
    colors_pie = []
    pie_palette = palette if palette else CHART_PIE_COLORS
    for i, lb in enumerate(labels):
        base = pie_palette[i % len(pie_palette)]
        lbl = str(lb).lower()
        if any(k in lbl for k in _KEYWORDS_INFRACTION):
            colors_pie.append(COLOR_CHART_4)
        else:
            colors_pie.append(base)
    total = sum(values)
    if total:
        pcts = int_percents_largest_remainder([int(v) for v in values])
        if legend_percent_only:
            legend_labels = [f"{lb}\n{pcts[i]} %" for i, lb in enumerate(labels)]
        else:
            legend_labels = [
                f"{lb}\n{v} ({pcts[i]} %)" for i, (lb, v) in enumerate(zip(labels, values))
            ]
    else:
        legend_labels = (
            [f"{lb}\n0 %" for lb in labels]
            if legend_percent_only
            else [f"{lb}\n0 (0 %)" for lb in labels]
        )
    fig_w = 5.2 * figure_scale
    fig_h = max(2.8, 0.35 * len(labels) + 1.8) * figure_scale
    fig, (ax_pie, ax_leg) = plt.subplots(
        1,
        2,
        figsize=(fig_w, fig_h),
        gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.08},
    )
    wedges, _ = ax_pie.pie(values, startangle=90, colors=colors_pie)
    ax_pie.set_aspect("equal")
    if str(title).strip():
        ax_pie.set_title(
            title,
            fontsize=CHART_TITLE_FONT_SIZE_REF - 1,
            fontweight="bold",
            color=COLOR_PRIMARY,
            pad=4,
        )
    ax_leg.axis("off")
    ax_leg.legend(
        wedges,
        legend_labels,
        loc="center left",
        fontsize=legend_fontsize,
        frameon=False,
        handlelength=0.9,
        handletextpad=0.35,
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.06)
    return save_chart(fig, tmp_dir, name, dpi=DEFAULT_RASTER_EXPORT_DPI, tight=True)


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
    keywords_inf = _KEYWORDS_INFRACTION
    for i, (label, vals) in enumerate(series.items()):
        offset = (i - n / 2 + 0.5) * w
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        elif any(k in lbl for k in _KEYWORDS_ATTENTE):
            color = COLOR_GREY
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
    group_labels = _sanitize_chart_period_tick_labels(list(group_labels))
    n_groups = max(1, len(group_labels))
    fig_w = max(CHART_FIG_WIDTH, min(10.0, n_groups * 0.75)) * figure_scale
    fig, ax = plt.subplots(figsize=(fig_w, CHART_FIG_HEIGHT_WITH_LEGEND * figure_scale))
    x = np.arange(len(group_labels))
    bottom = np.zeros(len(group_labels))
    keywords_inf = _KEYWORDS_INFRACTION
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


def chart_stackplot_resultats_domaine(
    domain_labels: list[str],
    series_conforme: list[float],
    series_non_conforme: list[float],
    series_en_attente: list[float],
    title: str,
    ylabel: str,
    tmp_dir: Path,
    name: str,
    *,
    legend_fontsize: float = 7.5,
    legend_ncol_max: int = 3,
    figure_scale: float = 0.68,
) -> str:
    """
    Aires empilées (stackplot) par domaine : Conforme, Non-conforme, En attente.

    Gabarit compact pour tenir sur une même page PDF avec tableau + camembert.
    """
    apply_mpl_style()
    n = max(1, len(domain_labels))
    # Marge droite réservée à la légende (hors zone des libellés X tournés).
    fig_w = max(6.4, min(7.4, 0.55 * n + 4.2)) * figure_scale
    fig_h = 2.45 * figure_scale
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    x = np.arange(n)
    y1 = np.array(series_conforme, dtype=float)
    y2 = np.array(series_non_conforme, dtype=float)
    y3 = np.array(series_en_attente, dtype=float)
    colors = [CHART_PIE_COLORS[1], COLOR_CHART_4, CHART_PIE_COLORS[2]]
    ax.stackplot(
        x,
        y1,
        y2,
        y3,
        labels=["Conforme", "Non-conforme", "En attente"],
        colors=colors,
        alpha=0.92,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(domain_labels, rotation=38, ha="right", fontsize=7)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold", color=COLOR_PRIMARY, pad=6)
    if n > 1:
        ax.set_xlim(x[0] - 0.45, x[-1] + 0.45)
    else:
        ax.set_xlim(-0.55, 0.55)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _legend_right_of_axis(ax, fontsize=legend_fontsize)
    # bottom : libellés X inclinés ; right : bande réservée à la légende (sans chevauchement).
    _tight_with_legend_space(fig, bottom=0.30, top=0.90, left=0.07, right=0.72)
    return save_chart(fig, tmp_dir, name, dpi=DEFAULT_RASTER_EXPORT_DPI, tight=True)


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
    show_title: bool = True,
    legend_below: bool = False,
    brochure_compact: bool = False,
    brochure_narrow: bool = False,
    figure_width_in: float | None = None,
    figure_height_in: float | None = None,
    plot_area_scale: float = 1.0,
    legend_right: bool = False,
    x_tick_fontsize: float | None = None,
    y_tick_fontsize: float | None = None,
    bar_value_fontsize: float | None = None,
    chart_dpi: int = DEFAULT_RASTER_EXPORT_DPI,
    apply_mpl: bool = True,
    grouped_colors: list[str] | None = None,
    title_color: str | None = None,
) -> str:
    """Barres horizontales empilées : une ligne par catégorie, segments empilés selon les séries."""
    if apply_mpl:
        apply_mpl_style()
    bar_palette = grouped_colors if grouped_colors else CHART_BAR_GROUPED_COLORS
    n = max(1, len(row_labels))
    y = np.arange(n)
    height = 0.62
    keywords_inf = _KEYWORDS_INFRACTION
    label_wrap = 18 if brochure_narrow else 40
    display_labels = [
        textwrap.fill(str(lb).strip(), width=label_wrap, break_long_words=False, break_on_hyphens=False)
        for lb in row_labels
    ]
    longest_line = 1
    for lbl in display_labels:
        for line in str(lbl).split("\n"):
            longest_line = max(longest_line, len(line.strip()))

    scale_eff = max(0.45, float(figure_scale))
    y_tick_fs = 9
    bar_value_fs = 8
    if brochure_narrow:
        fig_w = float(figure_width_in) if figure_width_in else 5.0
        fig_h = float(figure_height_in) if figure_height_in else max(2.6, 0.52 * n + 1.0)
        y_tick_fs = float(y_tick_fontsize) if y_tick_fontsize is not None else 8.0
        bar_value_fs = float(bar_value_fontsize) if bar_value_fontsize is not None else 7.5
    elif brochure_compact:
        scale_eff = max(0.26, min(0.48, float(figure_scale)))
        fig_w = max(
            CHART_FIG_WIDTH * scale_eff,
            7.8 + min(3.8, max(0, longest_line - 22) * 0.065),
        )
        fig_w = min(fig_w, 11.5)
        fig_h = max(3.0, 0.48 * n + 1.9) * scale_eff
        y_tick_fs = float(y_tick_fontsize) if y_tick_fontsize is not None else 8.5
        bar_value_fs = float(bar_value_fontsize) if bar_value_fontsize is not None else 7.5
    else:
        fig_w = max(
            CHART_FIG_WIDTH * scale_eff * 1.12,
            9.2 + min(5.4, max(0, longest_line - 22) * 0.085),
        )
        fig_w = min(fig_w, 15.0)
        fig_h = max(CHART_FIG_HEIGHT_WITH_LEGEND, min(14.0, 0.55 * n + 2.8)) * scale_eff
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    series_items = list(series.items())
    mat = np.column_stack([np.array(vals, dtype=float) for _, vals in series_items])
    if mat.ndim == 1:
        mat = mat.reshape(n, 1)
    row_totals = np.maximum(np.sum(mat, axis=1), 1.0)

    left = np.zeros(n)
    for i, (label, vals) in enumerate(series_items):
        vals_arr = np.array(vals, dtype=float)
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        elif any(k in lbl for k in _KEYWORDS_ATTENTE):
            color = COLOR_GREY
        else:
            color = bar_palette[i % len(bar_palette)]
        bars = ax.barh(y, vals_arr, height, left=left, label=label, color=color)
        for bar, val, rt in zip(bars, vals_arr, row_totals):
            if val > 0 and bar.get_width() >= max(3.5, 0.042 * float(rt)):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(val)}",
                    ha="center",
                    va="center",
                    fontsize=bar_value_fs,
                    fontweight="bold",
                    color="white",
                )
        left += vals_arr

    ax.set_yticks(y)
    ax.set_yticklabels(display_labels, fontsize=y_tick_fs)
    ax.invert_yaxis()
    show_xlabel = bool(str(xlabel).strip())
    if not (len(series_items) > 1 and legend_below) and show_xlabel:
        ax.set_xlabel(xlabel, fontsize=9)
    xmax = float(np.max(left)) if n else 0.0
    xmax = max(xmax, 1.0)
    ax.set_xlim(0, xmax * 1.08)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=8, integer=True, min_n_ticks=4))
    x_tick_fs = float(x_tick_fontsize) if x_tick_fontsize is not None else (6.5 if brochure_compact else 8.0)
    ax.tick_params(axis="x", labelsize=x_tick_fs)
    if show_title and str(title).strip():
        ax.set_title(title, fontsize=11, fontweight="bold", color=title_color or COLOR_PRIMARY, pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if len(series_items) > 1:
        use_legend_right = legend_right or (brochure_narrow and not legend_below)
        if use_legend_right:
            _legend_right_of_axis(ax, fontsize=legend_fontsize)
            if brochure_narrow:
                base_left, base_right = 0.30, 0.78
                span = (base_right - base_left) * max(1.0, float(plot_area_scale))
                span = min(0.70, span)
                left = max(0.14, base_right - span)
                fig.subplots_adjust(bottom=0.10, top=0.96, left=left, right=0.86)
            else:
                _tight_with_legend_space(fig, bottom=0.10, top=0.96, left=0.07, right=0.70)
        elif legend_below:
            x_fs = 8 if brochure_compact else 9
            x_pad = 12 if brochure_compact else 14
            leg_y = -0.24 if brochure_compact else -0.28
            leg_bottom = 0.28 if brochure_compact else 0.34
            leg_left = 0.20 if brochure_compact else 0.22
            if show_xlabel:
                ax.set_xlabel(xlabel, fontsize=x_fs, labelpad=x_pad)
            _legend_below_axis(
                ax,
                ncol=min(legend_ncol_max, len(series_items)),
                fontsize=legend_fontsize,
                anchor_y=leg_y,
            )
            _tight_with_legend_space(fig, bottom=leg_bottom, top=0.94, left=leg_left, right=0.98)
        else:
            _legend_right_of_axis(ax, fontsize=legend_fontsize)
            _tight_with_legend_space(fig, bottom=0.12, top=0.90, left=0.07, right=0.74)
    else:
        left_margin = 0.38 if brochure_narrow else 0.24
        _tight_with_legend_space(fig, bottom=0.10, top=0.96, left=left_margin, right=0.98)
    pad = 0.03 if brochure_narrow else 0.1
    return save_chart(fig, tmp_dir, name, dpi=chart_dpi, pad_inches=pad)


def chart_bar_horizontal_simple(
    labels: list,
    values: list,
    tmp_dir: Path,
    name: str,
    *,
    figure_scale: float = 0.38,
    dpi: int = DEFAULT_RASTER_EXPORT_DPI,
    apply_mpl: bool = True,
    bar_color: str | None = None,
) -> str:
    """Barres horizontales simples (brochure PDF, sans titre ni légende matplotlib)."""
    if apply_mpl:
        apply_mpl_style()
    n = max(1, len(labels))
    display_labels = [
        textwrap.fill(str(lb).strip(), width=34, break_long_words=False, break_on_hyphens=False)
        for lb in labels
    ]
    scale_eff = max(0.35, float(figure_scale))
    fig_h = max(2.4, 0.42 * n + 0.8) * scale_eff * 2.2
    fig_w = 6.8 * scale_eff
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    y = np.arange(n)
    bars = ax.barh(y, values, height=0.58, color=bar_color or COLOR_PRIMARY)
    ax.bar_label(bars, fmt="%g", fontsize=8, fontweight="bold", padding=2)
    ax.set_yticks(y)
    ax.set_yticklabels(display_labels, fontsize=8)
    ax.invert_yaxis()
    xmax = max(float(max(values)) if values else 1.0, 1.0)
    ax.set_xlim(0, xmax * 1.12)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True, min_n_ticks=3))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.subplots_adjust(left=0.34, right=0.99, top=0.96, bottom=0.06)
    return save_chart(fig, tmp_dir, name, dpi=dpi)


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
    x_labels = _sanitize_chart_period_tick_labels(list(x_labels))
    n_x = max(1, len(x_labels))
    fig_w = max(CHART_FIG_WIDTH, min(10.0, n_x * 0.75)) * figure_scale
    fig, ax = plt.subplots(figsize=(fig_w, CHART_FIG_HEIGHT_WITH_LEGEND * figure_scale))
    x = np.arange(len(x_labels))
    keywords_inf = _KEYWORDS_INFRACTION
    for i, (label, vals) in enumerate(series.items()):
        lbl = str(label).lower()
        if any(k in lbl for k in keywords_inf):
            color = COLOR_CHART_4
        elif any(k in lbl for k in _KEYWORDS_ATTENTE):
            color = COLOR_GREY
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
