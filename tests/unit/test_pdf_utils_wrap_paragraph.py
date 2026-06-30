from core.common.pdf_utils import wrap_plain_text_for_pdf_paragraph


def test_wrap_plain_text_for_pdf_paragraph_inserts_breaks() -> None:
    s = "un deux trois quatre cinq six sept huit neuf dix onze douze"
    out = wrap_plain_text_for_pdf_paragraph(s, wrap_width=12, max_lines=20)
    assert "<br/>" in out
    assert "un" in out


def test_wrap_plain_text_for_pdf_paragraph_escapes_html() -> None:
    out = wrap_plain_text_for_pdf_paragraph("A < B et C > D", wrap_width=20, max_lines=10)
    assert "&lt;" in out
    assert "&gt;" in out


def test_wrap_plain_text_for_pdf_paragraph_caps_lines() -> None:
    long = "mot " * 80
    out = wrap_plain_text_for_pdf_paragraph(long, wrap_width=10, max_lines=5)
    assert out.endswith("…")
    assert out.count("<br/>") <= 4
