from reportlab.pdfbase import pdfmetrics

from bilans.common.ofb_charte import FONT_FAMILY
from bilans.common.pdf_utils import truncate_text_to_width


def test_truncate_text_to_width_fits_one_line() -> None:
    long_label = (
        "27745 – NON RESPECT DES PRESCRIPTIONS DU SCHEMA DEPARTEMENTAL DE GESTION "
        "DES POPULATIONS DE GRAND GIBIER"
    )
    width_pt = 320.0
    out = truncate_text_to_width(long_label, width_pt)
    assert "\n" not in out
    assert pdfmetrics.stringWidth(out, FONT_FAMILY, 9.0) <= width_pt - 8.0
    assert out.endswith("…")
