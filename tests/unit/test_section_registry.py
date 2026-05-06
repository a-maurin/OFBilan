from __future__ import annotations


def test_section_registry_register_and_render() -> None:
    from bilans.engine.registre_sections_pdf import SectionRegistry

    seen: list[str] = []

    def _render(ctx: dict) -> None:
        seen.append(str(ctx.get("x", "")))

    reg = SectionRegistry()
    reg.register("sec_test", _render)
    reg.render("sec_test", {"x": "ok"})
    assert seen == ["ok"]


def test_section_registry_missing_raises() -> None:
    from bilans.engine.registre_sections_pdf import SectionRegistry

    reg = SectionRegistry()
    try:
        reg.render("missing", {})
    except KeyError as e:
        assert "missing" in str(e).lower() or "aucun" in str(e).lower()
    else:
        raise AssertionError("expected KeyError")


def test_section_registry_render_many_skips_unknown_by_default() -> None:
    from bilans.engine.registre_sections_pdf import SectionRegistry

    seen: list[str] = []

    def _render_a(ctx: dict) -> None:
        seen.append(f"a:{ctx.get('v', '')}")

    reg = SectionRegistry()
    reg.register("a", _render_a)
    reg.render_many(["a", "missing"], {"v": "ok"})
    assert seen == ["a:ok"]


def test_section_registry_render_many_raises_when_requested() -> None:
    from bilans.engine.registre_sections_pdf import SectionRegistry

    reg = SectionRegistry()
    try:
        reg.render_many(["missing"], {}, skip_unknown=False)
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")
