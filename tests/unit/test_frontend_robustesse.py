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

#
"""
Tests de non-régression : Mission 4 (validation inputs) et Mission 5 (cohérence profils).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ── Mission 5 : Typo département 07 ──────────────────────────────────────────

def test_no_typo_dept_07_explorer_js():
    """
    Vérifie que 'Ordèche' (typo) est absent d'explorer.js et que 'Ardèche' est présent.
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    assert "Ordèche" not in source, "Typo 'Ordèche' encore présente dans explorer.js"
    assert "Ardèche" in source, "Département 07 manquant dans explorer.js"


def test_region_default_code_consistent_app_js():
    """
    Vérifie que app.js utilise 'r27' (format CLI) et non '27' pour le code région par défaut.
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    # Le code '27' sans préfixe 'r' ne doit pas apparaître comme valeur par défaut pour region
    assert "inputCode.value = '27'" not in source, (
        "app.js utilise '27' sans préfixe 'r' pour le code région — divergence avec explorer.js et le CLI"
    )


# ── Mission 4 : Validation form présente dans app.js ─────────────────────────

def test_validate_form_function_exists():
    """validateForm() doit exister dans app.js pour bloquer les soumissions invalides."""
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    assert "function validateForm()" in source, "validateForm() absente de app.js"


def test_validate_form_checks_dates():
    """validateForm() doit vérifier la cohérence des dates."""
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    assert "dateDeb > dateFin" in source, "Validation date-deb ≤ date-fin absente de validateForm()"


def test_validate_form_checks_profil():
    """validateForm() doit vérifier que le profil est dans la liste API."""
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    assert "profilesList.some" in source, "Validation profil contre liste API absente de validateForm()"


def test_validate_form_checks_code():
    """validateForm() doit exiger un code géographique pour les échelles non-nationales."""
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    assert "echelle !== 'national'" in source, "Validation code géo absente de validateForm()"


def test_validate_form_called_before_generate():
    """validateForm() doit être appelée dans le listener du bouton Générer."""
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    # Le pattern doit apparaître dans le listener click
    assert "if (!validateForm()) return;" in source, (
        "validateForm() n'est pas appelée dans le listener du bouton Générer"
    )


# ── Mission 5 : Cohérence source profils ─────────────────────────────────────

def test_both_js_use_same_profils_api_endpoint():
    """explorer.js et app.js consomment tous deux /api/profils avec leur cible respective."""
    explorer = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    app = (Path(__file__).resolve().parents[2] / "core" / "web" / "app.js").read_text(encoding="utf-8")
    assert "fetch('/api/profils?target=explorer')" in explorer, "/api/profils?target=explorer absent de explorer.js"
    assert "fetch('/api/profils?target=editor')" in app, "/api/profils?target=editor absent de app.js"


def test_no_debug_pve_in_serveur():
    """Régression A : debug_pve.txt ne doit plus être référencé dans serveur.py."""
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "serveur.py").read_text(encoding="utf-8")
    assert "debug_pve.txt" not in source


# ── Points restants A, B, C ──────────────────────────────────────────────────

def test_point_B_form_error_msg_in_index_html():
    """
    Point B : L'élément #form-error-msg doit exister dans index.html.
    Sans lui, validateForm() dans app.js tombait en fallback silencieux.
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="form-error-msg"' in source, "#form-error-msg absent de index.html"


def test_point_C_date_validation_in_explorer_js():
    """
    Point C : explorer.js doit valider date-deb ≤ date-fin avant l'appel /api/data.
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    assert "dateDebEl.value > dateFinEl.value" in source, (
        "Validation date-deb ≤ date-fin absente de explorer.js"
    )


def test_point_A_banner_reset_on_load_start():
    """
    Point A : La bannière d'erreur est réinitialisée au début de chaque loadData().
    Vérifie la présence du reset dans le code avant le fetch.
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    assert "_errBanner.style.display = 'none'" in source, (
        "Reset bannière au début de loadData() absent de explorer.js"
    )


def test_point_A_banner_reset_on_success():
    """
    Point A : La bannière d'erreur est réinitialisée après un succès (chainé dans .then()).
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    assert "reset bannière sur succès" in source.lower() or "Point A : reset" in source, (
        "Reset bannière post-succès absent de explorer.js"
    )


def test_compare_active_title_mention_in_explorer_js():
    """
    Vérifie la présence de la mention (Comparaison années N / N-1) selon l'état de compare-active.
    """
    source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    assert "compare-active" in source, "Élément compare-active absent de explorer.js"
    assert "(Comparaison années N / N-1)" in source, "Mention de comparaison (Comparaison années N / N-1) absente de explorer.js"


def test_cache_lru_and_fade_transition():
    """
    Vérifie l'implémentation du cache LRU et du fondu visuel dans explorer.js et explorer.html.
    """
    js_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    html_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.html").read_text(encoding="utf-8")

    assert "dataResponseCache = new Map()" in js_source, "dataResponseCache absent de explorer.js"
    assert "DATA_CACHE_MAX_SIZE = 50" in js_source, "DATA_CACHE_MAX_SIZE absent de explorer.js"
    assert "clearDataResponseCache()" in js_source, "clearDataResponseCache absent de explorer.js"
    assert "data-fade-in" in js_source, "Classe data-fade-in absente de explorer.js"
    assert ".data-fade-in" in html_source, "Classe CSS .data-fade-in absente de explorer.html"


def test_map_fullscreen_layout_fix():
    """
    Vérifie la présence des règles CSS et JS prévenant les bugs de mise en page en mode plein écran.
    """
    js_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    html_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.html").read_text(encoding="utf-8")

    assert "transform: none !important;" in html_source, "transform: none absente de .map-fullscreen dans explorer.html"
    assert "document.body.style.overflow = isFullscreen ? 'hidden' : ''" in js_source, "Gestion de l'overflow du body absente dans explorer.js"
    assert "map.invalidateSize" in js_source, "Invalidation de taille de carte absente dans explorer.js"
    assert "flex-wrap: nowrap;" in html_source, "flex-wrap: nowrap absent de la barre d'outils carte dans explorer.html"
    assert "transform: translateY" not in html_source, "transform: translateY ne doit pas être présent dans dataFadeIn"


def test_api_profils_target_filtering_in_serveur():
    """
    Vérifie que la route /api/profils dans serveur.py gère le paramètre target
    et filtre pnf_v2, types_usager_cible et procedures_pve pour target=explorer.
    """
    serveur_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "serveur.py").read_text(encoding="utf-8")
    assert 'target = (qs.get("target") or [None])[0]' in serveur_source
    assert 'if target == "explorer":' in serveur_source
    assert '"pnf_v2"' in serveur_source
    assert '"procedures_pve"' in serveur_source


def test_filtres_drawer_collapse():
    """
    Vérifie la présence des éléments HTML, des règles CSS et des handlers JS
    pour le volet coulissant réductible des filtres (drawer) et le positionnement in-flow zéro chevauchement.
    """
    js_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    html_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.html").read_text(encoding="utf-8")

    assert 'id="btn-open-filtres-panel"' in html_source, "Bouton btn-open-filtres-panel absent dans explorer.html"
    assert 'id="btn-close-filtres-panel"' in html_source, "Bouton btn-close-filtres-panel absent dans explorer.html"
    assert 'id="btn-map-fullscreen-filtres"' in html_source, "Bouton btn-map-fullscreen-filtres absent dans explorer.html"
    assert '.explorer-container.filtres-collapsed' in html_source, "Style filtres-collapsed absent dans explorer.html"
    assert 'body.has-map-fullscreen .control-panel' in html_source, "Règle body.has-map-fullscreen .control-panel absente dans explorer.html"
    assert 'body.has-map-fullscreen #btn-map-fullscreen-filtres' in html_source, "Règle body.has-map-fullscreen #btn-map-fullscreen-filtres absente dans explorer.html"
    assert 'toggleFiltresDrawer' in js_source, "Fonction toggleFiltresDrawer absente dans explorer.js"
    assert 'ofbilan_explorer_filtres_collapsed' in js_source, "Stockage localStorage absent dans explorer.js"
    assert 'document.body.classList.toggle(\'has-map-fullscreen\'' in js_source, "Classe has-map-fullscreen absente dans explorer.js"


def test_pej_table_export_alignment_and_type_action():
    """
    Vérifie l'intégration de getFilteredTableData(), de la colonne Type d'Action
    et l'alignement de l'export CSV et de la pagination dans explorer.js et explorer.html.
    """
    js_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    html_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.html").read_text(encoding="utf-8")
    serveur_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "serveur.py").read_text(encoding="utf-8")

    assert 'function getFilteredTableData()' in js_source, "Fonction getFilteredTableData absente dans explorer.js"
    assert 'data-sort="type_action"' in html_source, "En-tête type_action absent dans explorer.html"
    assert "Type d'Action" in html_source, "Libellé Type d'Action absent dans explorer.html"
    assert "dataToExport = getFilteredTableData()" in js_source, "Export CSV non raccordé à getFilteredTableData dans explorer.js"
    assert "Fallback 2: CENTROIDES COMMUNAUX POUR PEJ" in serveur_source or "load_communes_centroides" in serveur_source, "Fallback centroïde communal PEJ absent dans serveur.py"


def test_directeur_enquete_extraction_in_serveur():
    """Vérifie la présence de l'extraction directeur_enquete dans serveur.py."""
    serveur_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "serveur.py").read_text(encoding="utf-8")
    assert "_extract_directeur_enquete" in serveur_source, "_extract_directeur_enquete absent de serveur.py"
    assert "_DIRECTEUR_ENQUETE_COLS" in serveur_source, "_DIRECTEUR_ENQUETE_COLS absent de serveur.py"
    assert '"directeur_enquete": _extract_directeur_enquete(r)' in serveur_source, "Injection directeur_enquete absente du bloc PEJ"


def test_directeur_enquete_extraction_logic():
    """Vérifie la logique fail-soft de _extract_directeur_enquete."""
    from core.web.serveur import _extract_directeur_enquete

    assert _extract_directeur_enquete({"DIRECTEUR_ENQUETE": "Dupont Jean"}) == "Dupont Jean"
    assert _extract_directeur_enquete({"DIRECTEUR ENQUETE": "Martin Paul"}) == "Martin Paul"
    assert _extract_directeur_enquete({"DIRECTEUR_ENQUETE": "N/A"}) == ""
    assert _extract_directeur_enquete({"DIRECTEUR_ENQUETE": ""}) == ""
    assert _extract_directeur_enquete({}) == ""
    assert _extract_directeur_enquete({"RESPONSABLE_ENQUETE": "Durand"}) == "Durand"


def test_pej_directeur_column_conditional_ui():
    """Vérifie la colonne conditionnelle Directeur d'enquête dans explorer.js/html."""
    js_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js").read_text(encoding="utf-8")
    html_source = (Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.html").read_text(encoding="utf-8")

    assert 'function isOnlyPejView(data)' in js_source, "isOnlyPejView absent de explorer.js"
    assert 'th-directeur-enquete' in html_source, "En-tête th-directeur-enquete absent de explorer.html"
    assert 'data-sort="directeur_enquete"' in html_source, "data-sort directeur_enquete absent de explorer.html"
    assert "Directeur d'enquête" in html_source, "Libellé Directeur d'enquête absent de explorer.html"
    assert "row.directeur_enquete || 'Non renseigné'" in js_source, "Affichage directeur_enquete absent de renderTable"
    assert "exportPejOnly = isOnlyPejView(dataToExport)" in js_source, "Export CSV conditionnel PEJ absent de explorer.js"
    assert "Directeur d\\'enquête" in js_source, "En-tête CSV Directeur d'enquête absent de explorer.js"


def test_icones_et_manifeste_pwa_coherence():
    """Vérifie que favicon.ico, manifest.json et les balises d'icônes sont présents et cohérents."""
    import json
    web_dir = Path(__file__).resolve().parents[2] / "core" / "web"
    
    # 1. Présence des assets
    assert (web_dir / "favicon.ico").exists(), "favicon.ico absent du dossier core/web"
    assert (web_dir / "manifest.json").exists(), "manifest.json absent du dossier core/web"
    assert (web_dir / "icon.png").exists(), "icon.png absent du dossier core/web"
    assert (web_dir / "icon.svg").exists(), "icon.svg absent du dossier core/web"

    # 2. Structure du manifest.json
    manifest_data = json.loads((web_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "name" in manifest_data
    assert "icons" in manifest_data
    assert len(manifest_data["icons"]) >= 2

    # 3. Présence des balises d'icônes dans toutes les pages
    for page_name in ("loading.html", "explorer.html", "index.html"):
        page_source = (web_dir / page_name).read_text(encoding="utf-8")
        assert 'href="favicon.ico"' in page_source, f"Lien favicon.ico manquant dans {page_name}"
        assert 'href="icon.png"' in page_source, f"Lien icon.png manquant dans {page_name}"
        assert 'href="icon.svg"' in page_source, f"Lien icon.svg manquant dans {page_name}"
        assert 'href="manifest.json"' in page_source, f"Lien manifest.json manquant dans {page_name}"


def test_serveur_favicon_ico_reponse_200():
    """Vérifie que la requête /favicon.ico renvoie un code 200 avec type image/x-icon."""
    import socketserver
    import threading
    import urllib.request
    from core.web.serveur import Handler

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/favicon.ico", timeout=2) as resp:
            assert resp.status == 200
            assert resp.headers.get_content_type() == "image/x-icon"
            assert len(resp.read()) > 0
        thread.join()


def test_perimetre_initial_neutre_frontend():
    """Vérifie qu'aucun périmètre (21) n'est pré-sélectionné au premier démarrage."""
    web_dir = Path(__file__).resolve().parents[2] / "core" / "web"
    explorer_html = (web_dir / "explorer.html").read_text(encoding="utf-8")
    index_html = (web_dir / "index.html").read_text(encoding="utf-8")
    explorer_js = (web_dir / "explorer.js").read_text(encoding="utf-8")
    app_js = (web_dir / "app.js").read_text(encoding="utf-8")

    # 1. Vérifier que code n'a pas 21 par défaut dans le HTML
    assert 'name="code" value="21"' not in explorer_html
    assert 'name="code" value="21"' not in index_html
    assert 'name="code" value=""' in explorer_html
    assert 'name="code" value=""' in index_html

    # 2. Vérifier que l'option neutre d'échelle existe et est sélectionnée
    assert '<option value="" selected disabled>Choisir une échelle...</option>' in explorer_html
    assert '<option value="" selected disabled>Choisir une échelle...</option>' in index_html

    # 3. Vérifier que le chargement est suspendu au démarrage si aucun périmètre n'est sélectionné
    assert "Suspension du chargement tant qu'aucun périmètre géographique n'est sélectionné" in explorer_js
    assert "inputCode.value = '21'" not in explorer_js
    assert "inputCode.value = '21'" not in app_js


def test_no_duplicate_variable_declarations_frontend():
    """Vérifie l'absence de redéclaration de variables const/let dans le même bloc de code."""
    import re
    web_dir = Path(__file__).resolve().parents[2] / "core" / "web"
    for js_filename in ("explorer.js", "app.js"):
        content = (web_dir / js_filename).read_text(encoding="utf-8")
        scopes = [set()]
        duplicates = []
        for line_idx, line in enumerate(content.splitlines(), start=1):
            clean_line = re.sub(r"//.*$", "", line)
            for char in clean_line:
                if char == "{":
                    scopes.append(set())
                elif char == "}":
                    if len(scopes) > 1:
                        scopes.pop()
            matches = re.findall(r"\b(?:const|let)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\b", clean_line)
            for var_name in matches:
                if var_name in scopes[-1]:
                    duplicates.append((js_filename, line_idx, var_name))
                else:
                    scopes[-1].add(var_name)

        assert not duplicates, f"Déclarations dupliquées détectées dans {js_filename} : {duplicates}"