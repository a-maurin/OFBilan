import sys

with open('src/bilans/engine/sections_profil_extracted.py', 'r', encoding='utf-8') as f:
    extracted = f.read()

with open('src/bilans/engine/sections_profil.py', 'a', encoding='utf-8') as f:
    f.write('\n\n')
    f.write(extracted)

with open('src/bilans/engine/generation_pdf_profil.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('    def _render_sec22() -> None:')
end_idx = content.find('    sec56_registry = SectionRegistry()')

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + content[end_idx:]
    
    # We also need to update the registry bindings
    new_content = new_content.replace(
        'sec2_registry.register("sec22", lambda _ctx: _render_sec22())',
        'sec2_registry.register("sec22", render_sec22)'
    ).replace(
        'sec2_registry.register("sec22theme", lambda _ctx: _render_sec22theme())',
        'sec2_registry.register("sec22theme", render_sec22theme)'
    ).replace(
        'sec2_registry.register("sec22res", lambda _ctx: _render_sec22res())',
        'sec2_registry.register("sec22res", render_sec22res)'
    ).replace(
        'sec2_registry.render_many(sec2_order, {})',
        'sec2_registry.render_many(sec2_order, ctx)'
    )
    
    new_content = new_content.replace(
        'sec34_registry.register("sec3", lambda _ctx: _render_sec3_bundle())',
        'sec34_registry.register("sec3", render_sec3_bundle)'
    ).replace(
        'sec34_registry.register("sec4", lambda _ctx: _render_sec4())',
        'sec34_registry.register("sec4", render_sec4)'
    ).replace(
        'sec34_registry.render_many(sec34_order, {})',
        'sec34_registry.render_many(sec34_order, ctx)'
    )

    new_content = new_content.replace(
        'sec56_registry.register("sec5map", lambda _ctx: _render_sec5map())',
        'sec56_registry.register("sec5map", render_sec5map)'
    ).replace(
        'sec56_registry.register("sec6", lambda _ctx: _render_sec6())',
        'sec56_registry.register("sec6", render_sec6)'
    ).replace(
        'sec56_registry.render_many(["sec5map", "sec6"], {})',
        'sec56_registry.render_many(["sec5map", "sec6"], ctx)'
    )
    
    imports_to_add = ", render_sec22, render_sec22theme, render_sec22res, render_sec3_bundle, render_sec4, render_sec5map, render_sec6"
    new_content = new_content.replace(
        "from bilans.engine.sections_profil import render_sec1, render_sec2_chap, render_sec21",
        "from bilans.engine.sections_profil import render_sec1, render_sec2_chap, render_sec21" + imports_to_add
    )
    
    with open('src/bilans/engine/generation_pdf_profil.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Updated generation_pdf_profil.py successfully')
else:
    print('Could not find boundaries')
    sys.exit(1)
