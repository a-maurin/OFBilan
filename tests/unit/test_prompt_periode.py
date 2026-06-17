"""Tests des défauts interactifs de période (ask_periode_perimetre)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from ofbilan.common import prompt_periode as pp


def test_default_date_deb_is_first_day_of_current_year() -> None:
    fixed = datetime(2026, 5, 28, 12, 0, 0)
    with patch("ofbilan.common.prompt_periode.dt.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.strptime = datetime.strptime
        assert pp._default_date_deb() == "2026-01-01"


def test_default_date_fin_is_today() -> None:
    fixed = datetime(2026, 5, 28, 12, 0, 0)
    with patch("ofbilan.common.prompt_periode.dt.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.strptime = datetime.strptime
        assert pp._default_date_fin() == "2026-05-28"


def test_ask_periode_perimetre_uses_dynamic_defaults_on_empty_input() -> None:
    fixed = datetime(2026, 5, 28, 12, 0, 0)
    inputs = iter(["", "", "", ""])
    with (
        patch("ofbilan.common.prompt_periode.dt.datetime") as mock_dt,
        patch.object(pp, "_is_interactive", return_value=True),
        patch("builtins.input", side_effect=lambda _prompt: next(inputs)),
    ):
        mock_dt.now.return_value = fixed
        mock_dt.strptime = datetime.strptime
        deb, fin, echelle, code = pp.ask_periode_perimetre()

    assert deb == "2026-01-01"
    assert fin == "2026-05-28"
    assert echelle == "departement"
    assert code == "21"


def test_ask_periode_perimetre_non_interactive_requires_dates() -> None:
    with patch.object(pp, "_is_interactive", return_value=False):
        with pytest.raises(ValueError, match="non interactif"):
            pp.ask_periode_perimetre()
