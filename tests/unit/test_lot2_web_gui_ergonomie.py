# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL).

from pathlib import Path


def test_lot2_html_and_js_elements():
    """
    Vérifie la présence des nouveaux composants d'ergonomie et d'expérience utilisateur
    dans index.html, explorer.html, app.js et explorer.js.
    """
    web_dir = Path(__file__).resolve().parents[2] / "core" / "web"
    index_html = (web_dir / "index.html").read_text(encoding="utf-8")
    explorer_html = (web_dir / "explorer.html").read_text(encoding="utf-8")
    app_js = (web_dir / "app.js").read_text(encoding="utf-8")
    explorer_js = (web_dir / "explorer.js").read_text(encoding="utf-8")
    style_css = (web_dir / "style.css").read_text(encoding="utf-8")
    serveur_py = (web_dir / "serveur.py").read_text(encoding="utf-8")

    # 1. index.html : composants de volume, accordéon options avancées, étapes et annulation
    assert 'id="perimeter-volume-badge"' in index_html
    assert 'id="accordion-options-avancees"' in index_html
    assert 'id="accordion-options-avancees-body"' in index_html
    assert 'id="accordion-options-avancees-body" class="accordion-body hidden"' not in index_html
    assert 'id="generation-steps"' in index_html
    assert 'id="btn-cancel-generation"' in index_html

    # 2. explorer.html : boutons d'action unifiés et bandeau de puces
    assert 'id="btn-go-to-generator"' in explorer_html
    assert 'id="active-filters-chips-bar"' in explorer_html
    assert 'id="nav-link-generator"' in explorer_html
    assert 'Imprimer la vue' in explorer_html

    # 3. style.css : classes CSS de retour visuel
    assert '.btn-update-dirty' in style_css
    assert '.active-filters-bar' in style_css
    assert '.filter-chip' in style_css
    assert '.perimeter-volume-badge' in style_css
    assert '.generation-steps' in style_css

    # 4. explorer.js : passerelle, détection de modification et puces actives
    assert 'transferPerimeterToGenerator' in explorer_js
    assert 'checkFiltersDirty' in explorer_js
    assert 'renderActiveFiltersChips' in explorer_js
    assert 'ofbilan_shared_perimeter' in explorer_js
    assert 'btn-update-dirty' in explorer_js

    # 5. app.js : import du périmètre, harmonisation de profil, volume préalable et étapes
    assert 'applySharedPerimeterFromStorage' in app_js
    assert 'getSelectedProfileId' in app_js
    assert 'checkPerimeterVolume' in app_js
    assert 'setGenerationStep' in app_js
    assert 'ofbilan_shared_perimeter' in app_js
    assert '/api/generate/cancel' in app_js
    assert "accordOptionsAvanceesBody.classList.toggle('open'" in app_js

    # 6. serveur.py : endpoint d'annulation de génération
    assert '/api/generate/cancel' in serveur_py
    assert '_generate_lock' in serveur_py
