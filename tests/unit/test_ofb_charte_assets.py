"""Constantes et fichiers par défaut de la charte OFB."""

from __future__ import annotations

from core.common.ofb_charte import (
    CHARTE_ASSET_DEFAULT_FILES,
    IMG_BACKGROUND,
    IMG_BANNER,
    IMG_FILIGRANE,
    IMG_FILIGRANE_ALT,
    IMG_FOOTER_DECO,
    IMG_LOGO_BANNER,
    IMG_TITLE_DECO,
    IMG_TITLE_PAGE_DECO,
)


def test_charte_asset_default_files_match_yaml_keys() -> None:
    assert set(CHARTE_ASSET_DEFAULT_FILES) == {
        "banner",
        "title_page_deco",
        "watermark",
        "footer_deco",
    }
    assert CHARTE_ASSET_DEFAULT_FILES["banner"] == "image5.jpg"
    assert CHARTE_ASSET_DEFAULT_FILES["watermark"] == "image3.jpeg"


def test_charte_legacy_aliases_point_to_canonical_constants() -> None:
    assert IMG_LOGO_BANNER == IMG_BANNER
    assert IMG_TITLE_PAGE_DECO == IMG_TITLE_DECO
    assert IMG_FOOTER_DECO == IMG_FILIGRANE
    assert IMG_BACKGROUND == IMG_FILIGRANE_ALT
