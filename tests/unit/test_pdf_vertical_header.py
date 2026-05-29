"""En-têtes PDF (VerticalText, tableau Usagers × Domaine)."""

from reportlab.platypus import Paragraph

from bilans.common.pdf_usagers_domaine_table import (
    resolve_usagers_x_domaine_header_layout,
    usagers_x_domaine_col_widths,
)
from bilans.common.pdf_utils import VerticalText, _CELL_HEADER, ofb_table_wide


def test_vertical_text_wrap_height_not_capped_by_small_avail_height() -> None:
    label = (
        "Assurer la protection des espèces animales et végétales "
        "dans le cadre de la police de l'environnement"
    )
    flow = VerticalText(label, _CELL_HEADER, max_lines=6)
    w, h = flow.wrap(48.0, 12.0)
    assert w == 48.0
    assert h > 12.0
    assert len(flow._lines) >= 2


def test_vertical_text_splits_long_domain_label() -> None:
    label = "Espaces proteges, protection des milieux et du cadre de vie"
    flow = VerticalText(label, _CELL_HEADER, max_lines=6)
    flow.wrap(52.0, 200.0)
    assert len(flow._lines) >= 2
    assert flow._lines[0].startswith("Espaces")


def test_resolve_usagers_x_domaine_header_layout_default_horizontal() -> None:
    assert resolve_usagers_x_domaine_header_layout({}) == "horizontal_wrap"
    assert (
        resolve_usagers_x_domaine_header_layout(
            {"usagers_x_domaine": {"header_layout": "vertical"}}
        )
        == "vertical"
    )


def test_ofb_table_wide_horizontal_wrap_uses_paragraph_headers() -> None:
    label = "Assurer la protection des especes animales et vegetales"
    rows = [["type_usager", label], ["A", "1"]]
    widths = [120.0, 55.0]
    tbl = ofb_table_wide(
        rows,
        col_widths=widths,
        header_layout="horizontal_wrap",
        vertical_header_font_size=7.0,
        vertical_header_max_lines=5,
    )
    header_cells = tbl._cellvalues[0]
    assert isinstance(header_cells[1], Paragraph)
    assert "<br/>" in header_cells[1].text or len(label) < 40


def test_usagers_x_domaine_col_widths_uses_yaml_ratio() -> None:
    avail = 500.0
    layout = {"usagers_x_domaine": {"first_column_width_ratio": 0.20}}
    widths = usagers_x_domaine_col_widths(avail, 4, layout)
    assert len(widths) == 5
    assert abs(widths[0] - 100.0) < 0.01
    assert abs(sum(widths) - avail) < 0.02
