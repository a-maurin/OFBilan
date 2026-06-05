import re
import sys

with open('src/bilans/engine/generation_pdf_synthese.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('    # ── 1. Chiffres clés + § 2 + § 2.1 (même page) ──')
end_idx = content.find('    builder.build()')

if start_idx == -1 or end_idx == -1:
    print('Failed to find start/end')
    sys.exit(1)

block = content[start_idx:end_idx]

# Unindent
block = '\n'.join([line[4:] if line.startswith('    ') else line for line in block.split('\n')])

# We split the block into sections manually using regex on `builder.add_section`
# But wait, sec1, sec2, sec2_1 are all together and share variables like `act_theme_display`.
# It's better to group them by the headers that are enabled/disabled.
# Since synthese has no `is_section_enabled` checks currently, they are always generated.
# Let's wrap the whole thing in one `def render_all_synthese(ctx: PdfContext):` for now?
# NO, Etape 3 requires them to be separable by SectionRegistry.

# Let's add markers
block = block.replace('builder.add_section("sec1"', 'MARKER_SEC1\nbuilder.add_section("sec1"')
block = block.replace('builder.add_section(\n        "sec2_2",', 'MARKER_SEC22\nbuilder.add_section(\n        "sec2_2",')
block = block.replace('builder.add_section(\n        "sec2_3",', 'MARKER_SEC23\nbuilder.add_section(\n        "sec2_3",')
block = block.replace('builder.add_section("sec3"', 'MARKER_SEC3\nbuilder.add_section("sec3"')
block = block.replace('builder.add_section(\n        "sec3_1",', 'MARKER_SEC31\nbuilder.add_section(\n        "sec3_1",')
block = block.replace('builder.add_section(\n        "sec3_2",', 'MARKER_SEC32\nbuilder.add_section(\n        "sec3_2",')
block = block.replace('builder.add_section("sec3_3"', 'MARKER_SEC33\nbuilder.add_section("sec3_3"')
block = block.replace('builder.add_section("sec4"', 'MARKER_SEC4\nbuilder.add_section("sec4"')
block = block.replace('builder.add_section("sec5"', 'MARKER_SEC5\nbuilder.add_section("sec5"')
block = block.replace('builder.add_section("sec6"', 'MARKER_SEC6\nbuilder.add_section("sec6"')

parts = block.split('MARKER_')
if len(parts) < 2:
    print('Failed to split')
    sys.exit(1)

# parts[0] is just comments before sec1
sections_code = ""

for part in parts[1:]:
    sec_id = part[:part.find('\n')]
    code = part[part.find('\n')+1:]
    
    func_name = f"render_{sec_id.lower()}"
    
    # Indent code
    indented_code = '\n'.join(['    ' + line if line else '' for line in code.split('\n')])
    sections_code += f"def {func_name}(ctx: PdfContext) -> None:\n{indented_code}\n\n"


variables = [
    'presentation_cfg', 'builder', 'section_title', 'out_dir', 'agg_domaine', 'tmp_dir',
    'legend_fontsize', 'legend_ncol_max', 'figure_scale', 'chart_bar_w', 'avail_w',
    'split_by_row', 'ref_pie_fs', 'ref_pie_legend_fs', 'ref_pie_w', 'tab_resultats',
    'nb_pej', 'nb_pa', 'nb_pve', 'cartes', 'global_map_paths', 'global_map_layout',
    'map_captions', 'map_id', 'show_placeholder', 'profile', 'date_deb', 'date_fin',
    'dept_name_typo', 'dept_code', 'profile_id', 'diffusion', 'nb_localisations',
    'ventilation_mode', 'pej_dom', 'tab_resultats_controles', 'nb_effectifs',
    'nb_operations_controle', 'nb_nc', 'act_theme', 'act_theme_total', 'act_proc',
    'pve_natinf', 'pej_top', 'usagers_resume', 'res_usager', 'cross_usager_dom'
]

for var in variables:
    sections_code = re.sub(r'\b' + var + r'\b', f'ctx.{var}', sections_code)

# Fix kwargs
for var in variables:
    sections_code = re.sub(r'ctx\.' + var + r'\s*=', var + '=', sections_code)

sections_code = sections_code.replace('ctx.ctx.', 'ctx.')
sections_code = sections_code.replace('ctx.builder.add_section("sec', 'ctx.builder.add_section("sec')

header = """\"\"\"Fonctions de rendu des sections pour le profil synthèse globale.\"\"\"

from pathlib import Path
import pandas as pd
from reportlab.platypus import Spacer, Paragraph

from bilans.engine.pdf_context import PdfContext
from bilans.common.pdf_presentation_config import is_section_enabled, is_block_enabled
from bilans.common.pdf_table_sort import (
    PDF_LABEL_CTRL_LOCATIONS,
    PDF_LABEL_CTRL_LOCATIONS_SHORT,
    PDF_LABEL_NON_CONFORME_LOCATIONS,
    PDF_LABEL_PEJ_COUNT,
)
from bilans.common.percent_format import format_pct_int_from_rate
from bilans.engine.pdf_utils import nb_non_conformes_brut, truncate_with_dash
from bilans.common.rendus_graphiques import (
    chart_bar_stacked, chart_line_evolution, chart_pie, chart_stackplot_resultats_domaine,
    chart_bar_horizontal_stacked
)
from bilans.common.utilitaires_metier import _load_csv_opt
from bilans.engine.generation_pdf_synthese import (
    _nb_non_conformes_brut, _build_synthese_key_figure_rows, _rollup_small_categories,
    _wrap_table_label, _resultats_controles_pie_data, _pie_data_controles_par_type_usager,
    _display_type_usager, _chart_pie_compact_legend_kw, _format_pve_natinf_label,
    _build_pve_natinf_table_rows, _KEY_FIGURES_GRAIN_NOTE, _SEC3_1_TABLE_NOTE
)
from bilans.common.pdf_blocks import _mk_centered_image, pdf_metric_caption, ofb_table
from xml.sax.saxutils import escape

"""

with open('src/bilans/engine/sections_synthese.py', 'w', encoding='utf-8') as f:
    f.write(header + sections_code)

# Now modify generation_pdf_synthese.py to inject PdfContext
ctx_instantiation = """
    from bilans.engine.pdf_context import PdfContext
    from bilans.engine.sections_synthese import (
        render_sec1, render_sec22, render_sec23, render_sec3, render_sec31,
        render_sec32, render_sec33, render_sec4, render_sec5, render_sec6
    )
    from bilans.engine.registre_sections_pdf import SectionRegistry
    
    ctx = PdfContext(
        builder=builder,
        profile={},
        presentation_cfg={},
        behavior_cfg={},
        show_placeholder=show_placeholder,
        date_deb=date_deb,
        date_fin=date_fin,
        dept_code=dept_code,
        dept_name_typo=dept_name_typo,
        diffusion=diffusion,
        ventilation_mode="",
        out_dir=out_dir,
        avail_w=avail_w,
        tmp_dir=tmp_dir,
        chart_bar_w=chart_bar_w,
        legend_fontsize=legend_fontsize,
        legend_ncol_max=legend_ncol_max,
        figure_scale=figure_scale,
        ref_pie_w=ref_pie_w,
        ref_pie_fs=ref_pie_fs,
        ref_pie_legend_fs=ref_pie_legend_fs,
        split_by_row=bool(tables_layout.get("split_by_row")),
        tables_layout=tables_layout,
        section_title={},
        nb_localisations=nb_localisations,
        nb_ops=nb_ops,
        nb_effectifs=nb_effectifs,
        nb_operations_controle=nb_operations_controle,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
        tab_resultats=tab_resultats,
        tab_resultats_controles=tab_resultats_controles,
        agg_domaine=agg_domaine,
        act_theme=act_theme,
        act_proc=act_proc,
        pve_natinf=pve_natinf,
        pej_top=None,
        agg_usager=None,
        res_usager=res_usager,
        cross_usager_dom=cross_usager_dom,
        usagers_resume=usagers_resume,
        cartes=cartes,
        global_map_paths=global_map_paths,
        global_map_layout=global_map_layout,
        map_captions=map_captions,
        map_id="global",
    )

    registry = SectionRegistry()
    registry.register("sec1", render_sec1)
    registry.register("sec2_2", render_sec22)
    registry.register("sec2_3", render_sec23)
    registry.register("sec3", render_sec3)
    registry.register("sec3_1", render_sec31)
    registry.register("sec3_2", render_sec32)
    registry.register("sec3_3", render_sec33)
    registry.register("sec4", render_sec4)
    registry.register("sec5", render_sec5)
    registry.register("sec6", render_sec6)
    
    registry.render_many([
        "sec1", "sec2_2", "sec2_3", "sec3", "sec3_1", "sec3_2", "sec3_3", "sec4", "sec5", "sec6"
    ], ctx)
"""

new_content = content[:start_idx] + ctx_instantiation + content[end_idx:]

with open('src/bilans/engine/generation_pdf_synthese.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Updated synthese successfully')
