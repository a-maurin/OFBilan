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

from reportlab.platypus import Paragraph, Table
from core.engine.moteur_layout_widgets import (
    WidgetContext,
    _parse_column_width,
    compile_row_flowables,
    compile_page_layout,
)


def test_parse_column_width():
    usable_width = 800.0
    assert _parse_column_width("50%", usable_width) == 400.0
    assert _parse_column_width("100%", usable_width) == 800.0
    assert _parse_column_width("25%", usable_width) == 200.0
    assert _parse_column_width(350, usable_width) == 350.0


def test_compile_row_flowables_single_column():
    ctx = WidgetContext()
    row_config = {
        "columns": [
            {
                "width": "100%",
                "widget": {"type": "custom_text_box"},
            }
        ]
    }
    rendered = compile_row_flowables(row_config, 800.0, ctx)
    assert isinstance(rendered, Paragraph)


def test_compile_row_flowables_multi_column():
    def dummy_handler(w_cfg, ctx, target_width):
        return Paragraph(f"Dummy {w_cfg.get('type')}")

    ctx = WidgetContext(
        render_handlers={
            "map": dummy_handler,
            "section_group": dummy_handler,
        }
    )
    row_config = {
        "columns": [
            {"width": "50%", "widget": {"type": "map"}},
            {"width": "50%", "widget": {"type": "section_group"}},
        ]
    }
    rendered = compile_row_flowables(row_config, 800.0, ctx)
    assert isinstance(rendered, Table)


def test_compile_page_layout():
    ctx = WidgetContext()
    page_config = {
        "page_number": 1,
        "rows": [
            {
                "columns": [
                    {"width": "100%", "widget": {"type": "stat_kpi_grid"}}
                ]
            }
        ]
    }
    story = compile_page_layout(page_config, 800.0, 500.0, ctx)
    assert isinstance(story, list)
    assert len(story) > 0
