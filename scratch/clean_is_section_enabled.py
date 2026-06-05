import re

for filename in ['src/bilans/engine/sections_profil.py', 'src/bilans/engine/sections_synthese.py']:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove early returns:
    content = re.sub(r'    if not is_section_enabled\([^)]+\):\n        return\n', '', content)

    # Remove the `if is_section_enabled(ctx.presentation_cfg, "secX", True):` and unindent the next line.
    content = re.sub(
        r'    if is_section_enabled\(ctx\.presentation_cfg, \"([a-zA-Z0-9_]+)\", True\):\n        ctx\.builder\.add_section',
        r'    ctx.builder.add_section',
        content
    )

    # For sec2_chap, it's:
    content = re.sub(
        r'    if is_section_enabled\(ctx\.presentation_cfg, \"([a-zA-Z0-9_]+)\", True\):\n        ctx\.builder\.add_section\(',
        r'    ctx.builder.add_section(',
        content
    )
    
    # Just remove `if is_section_enabled(ctx.presentation_cfg, sid, True)` lines because they are in a loop in sec3_bundle!
    # Wait! In sec3_bundle:
    # for sid, title in section_defs:
    #     if is_section_enabled(ctx.presentation_cfg, sid, True)
    #         builder.add_section(...)
    # For this one, we actually *should* keep `is_section_enabled` or replace it with something else?
    # If the YAML handles sections, sec31/sec32/sec33 are INDIVIDUAL sections in YAML!
    # So why does `sec3_bundle` render them all in a loop?
    # Because `generation_pdf_profil.py` calls `render_sec3_bundle`. It should instead call `render_sec31`, `render_sec32`, etc. individually.
    # I already separated them in Synthese, but in Profil they are bundled?
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
