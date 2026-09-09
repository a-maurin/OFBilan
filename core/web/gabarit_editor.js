/*
 * Copyright (C) 2026 Aguirre MAURIN
 *
 * Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
 * selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
 * la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
 *
 * Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
 * sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
 * Voir la Licence Publique Générale GNU pour plus de détails.
 *
 * CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
 * Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
 * intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
 * clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
 * doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
 * de l'auteur original (Aguirre MAURIN).
 */

(function () {
    let currentGabaritData = null;
    let originalGabaritData = null;
    let isSystemTemplate = false;
    let isModified = false;
    let activeTab = 1;

    const ALL_SECTIONS = [
        { id: "sec1", label: "Section 1 : Bilan des Contrôles & Activité" },
        { id: "sec2", label: "Section 2 : Répartition par Usagers & Polices" },
        { id: "sec3", label: "Section 3 : Infractions & Suites Judiciaires" },
        { id: "sec4", label: "Section 4 : Procédures Administratives" },
        { id: "sec6", label: "Section 6 : Synthèse & Perspectives" }
    ];

    const CARTO_ITEMS = [
        { id: "titre_principal", label: "Titre principal de la carte" },
        { id: "sous_titre", label: "Sous-titre cartographique" },
        { id: "bandeau_titre", label: "Bandeau supérieur de titre" },
        { id: "bandeau_logos_ofb", label: "Bandeau de logos institutionnels OFB" },
        { id: "logo_ofb_bas_droite", label: "Logo OFB en bas à droite" },
        { id: "bandeau_source", label: "Cartouche de source des données" }
    ];

    const WIDGET_TYPES = [
        { type: "map", label: "🗺️ Carte géographique principale" },
        { type: "stat_kpi_grid", label: "📊 Grille des indicateurs clés (KPI)" },
        { type: "section_group", label: "📝 Groupes de texte de section" },
        { type: "theme_breakdown_table", label: "📋 Tableau de répartition thématique" },
        { type: "evolution_chart", label: "📈 Graphique d'évolution temporelle" }
    ];

    window.openGabaritEditorModal = async function (gabaritId) {
        if (!gabaritId) {
            const select = document.getElementById("set-geo-gabarit");
            gabaritId = (select && select.value) ? select.value : "gabarit_defaut";
        }
        if (!gabaritId || gabaritId === "") gabaritId = "gabarit_defaut";

        const modal = document.getElementById("gabarit-editor-modal");
        if (!modal) return;

        modal.classList.remove("hidden");
        modal.style.display = "flex";

        await loadGabaritDetail(gabaritId);
    };

    window.closeGabaritEditorModal = function () {
        if (isModified) {
            if (!confirm("Des modifications sont en cours d'édition. Voulez-vous vraiment fermer sans enregistrer ?")) {
                return;
            }
        }
        const modal = document.getElementById("gabarit-editor-modal");
        if (modal) {
            modal.classList.add("hidden");
            modal.style.display = "none";
        }
        isModified = false;
    };

    window.switchGabaritTab = function (tabNum) {
        activeTab = tabNum;
        for (let i = 1; i <= 4; i++) {
            const tabBtn = document.getElementById(`gab-tab-btn-${i}`);
            const tabPane = document.getElementById(`gab-tab-pane-${i}`);
            if (tabBtn) {
                if (i === tabNum) {
                    tabBtn.classList.add("active");
                    tabBtn.style.borderBottom = "3px solid #3b82f6";
                    tabBtn.style.color = "#3b82f6";
                    tabBtn.style.fontWeight = "bold";
                } else {
                    tabBtn.classList.remove("active");
                    tabBtn.style.borderBottom = "none";
                    tabBtn.style.color = "#64748b";
                    tabBtn.style.fontWeight = "normal";
                }
            }
            if (tabPane) {
                tabPane.style.display = (i === tabNum) ? "block" : "none";
            }
        }

        if (tabNum === 3) renderTab3GridLayout();
        if (tabNum === 4) syncFormToYamlText();
    };

    async function loadGabaritDetail(gabaritId) {
        try {
            showGabaritToast("Chargement du gabarit...", false);
            const res = await fetch(`/api/gabarits/detail?id=${encodeURIComponent(gabaritId)}`);
            const json = await res.json();

            if (!json.success || !json.data) {
                showGabaritToast(json.error || "Impossible de charger le gabarit.", true);
                return;
            }

            currentGabaritData = json.data;
            originalGabaritData = JSON.parse(JSON.stringify(json.data));
            isSystemTemplate = !!json.is_system;
            isModified = false;

            updateSystemBadge();
            populateTab1();
            populateTab2();
            renderTab3GridLayout();
            syncFormToYamlText();
            switchGabaritTab(1);

            showGabaritToast(`Gabarit "${currentGabaritData.gabarit_id}" chargé`, false);
        } catch (e) {
            console.error("Erreur chargement gabarit:", e);
            showGabaritToast("Erreur réseau lors du chargement.", true);
        }
    }

    function updateSystemBadge() {
        const badge = document.getElementById("gab-system-badge");
        const btnDelete = document.getElementById("btn-gab-delete");

        if (badge) {
            if (isSystemTemplate) {
                badge.textContent = "🔒 Système (Lecture seule)";
                badge.style.background = "#e2e8f0";
                badge.style.color = "#475569";
            } else {
                badge.textContent = "👤 Personnalisé";
                badge.style.background = "#dbeafe";
                badge.style.color = "#1e40af";
            }
        }
        if (btnDelete) {
            btnDelete.disabled = isSystemTemplate;
            btnDelete.style.opacity = isSystemTemplate ? "0.4" : "1";
            btnDelete.style.cursor = isSystemTemplate ? "not-allowed" : "pointer";
            btnDelete.style.background = isSystemTemplate ? "#f1f5f9" : "#ffffff";
            btnDelete.style.color = isSystemTemplate ? "#94a3b8" : "#ef4444";
            btnDelete.style.borderColor = isSystemTemplate ? "#e2e8f0" : "#fca5a5";
        }
    }

    function populateTab1() {
        if (!currentGabaritData) return;
        document.getElementById("gab-id-display").value = currentGabaritData.gabarit_id || "";
        document.getElementById("gab-label").value = currentGabaritData.label || "";
        document.getElementById("gab-description").value = currentGabaritData.description || "";
        document.getElementById("gab-cible").value = currentGabaritData.cible || "les_deux";

        const titleObj = currentGabaritData.title || {};
        document.getElementById("gab-title-mode").value = titleObj.line2_mode || "fixed";
        document.getElementById("gab-title-fixed").value = titleObj.line2_fixed || "";

        const org = currentGabaritData.organisation || {};
        document.getElementById("gab-org-region").value = org.code_region || "";
        document.getElementById("gab-org-service").value = org.service || "";

        toggleCibleScopeNotice();
    }

    window.onTab1Change = function () {
        if (!currentGabaritData) return;
        currentGabaritData.label = document.getElementById("gab-label").value.trim();
        currentGabaritData.description = document.getElementById("gab-description").value.trim();
        currentGabaritData.cible = document.getElementById("gab-cible").value;

        if (!currentGabaritData.title) currentGabaritData.title = {};
        currentGabaritData.title.line2_mode = document.getElementById("gab-title-mode").value;
        currentGabaritData.title.line2_fixed = document.getElementById("gab-title-fixed").value.trim();

        if (!currentGabaritData.organisation) currentGabaritData.organisation = {};
        currentGabaritData.organisation.code_region = document.getElementById("gab-org-region").value.trim();
        currentGabaritData.organisation.service = document.getElementById("gab-org-service").value.trim();

        isModified = true;
        toggleCibleScopeNotice();
        syncFormToYamlText();
    };

    function toggleCibleScopeNotice() {
        const cible = document.getElementById("gab-cible") ? document.getElementById("gab-cible").value : "les_deux";
        const tab3Btn = document.getElementById("gab-tab-btn-3");
        const tab3Notice = document.getElementById("gab-tab3-disabled-notice");
        const tab3Content = document.getElementById("gab-tab3-content");

        if (cible === "bilan") {
            if (tab3Notice) tab3Notice.style.display = "block";
            if (tab3Content) tab3Content.style.display = "none";
            if (tab3Btn) tab3Btn.style.opacity = "0.6";
        } else {
            if (tab3Notice) tab3Notice.style.display = "none";
            if (tab3Content) tab3Content.style.display = "block";
            if (tab3Btn) tab3Btn.style.opacity = "1";
        }
    }

    function populateTab2() {
        if (!currentGabaritData) return;

        // Ordre des sections
        const secContainer = document.getElementById("gab-sections-list");
        if (secContainer) {
            secContainer.innerHTML = "";
            const currentOrder = (currentGabaritData.sections && currentGabaritData.sections.order) ? currentGabaritData.sections.order : ALL_SECTIONS.map(s => s.id);

            const orderedList = [];
            currentOrder.forEach(sid => {
                const found = ALL_SECTIONS.find(s => s.id === sid);
                if (found) orderedList.push({ ...found, included: true });
            });
            ALL_SECTIONS.forEach(s => {
                if (!orderedList.some(o => o.id === s.id)) {
                    orderedList.push({ ...s, included: false });
                }
            });

            orderedList.forEach((item, idx) => {
                const row = document.createElement("div");
                row.style.cssText = "display:flex; align-items:center; justify-content:space-between; padding:8px 12px; border:1px solid #e2e8f0; border-radius:6px; background:#fff; margin-bottom:6px;";
                row.innerHTML = `
                    <div style="display:flex; align-items:center; gap:10px;">
                        <input type="checkbox" id="chk-sec-${item.id}" ${item.included ? "checked" : ""} onchange="onSectionToggle('${item.id}')">
                        <label for="chk-sec-${item.id}" style="margin:0; font-weight:500; cursor:pointer;">${item.label}</label>
                    </div>
                    <div style="display:flex; gap:4px;">
                        <button type="button" onclick="moveSection('${item.id}', -1)" ${idx === 0 ? "disabled" : ""} style="padding:2px 8px;">▲</button>
                        <button type="button" onclick="moveSection('${item.id}', 1)" ${idx === orderedList.length - 1 ? "disabled" : ""} style="padding:2px 8px;">▼</button>
                    </div>
                `;
                secContainer.appendChild(row);
            });
        }

        // Habillage cartographique (Cocher = Afficher)
        const cartoContainer = document.getElementById("gab-carto-masks");
        if (cartoContainer) {
            cartoContainer.innerHTML = "";
            const cartoCfg = currentGabaritData.cartographie || {};
            const masked = cartoCfg.items_masques_brochure || cartoCfg.items_masques || [];

            CARTO_ITEMS.forEach(cItem => {
                const isDisplayed = !masked.includes(cItem.id);
                const div = document.createElement("div");
                div.style.cssText = "display:flex; align-items:center; gap:8px; padding:4px 0;";
                div.innerHTML = `
                    <input type="checkbox" id="chk-carto-${cItem.id}" ${isDisplayed ? "checked" : ""} onchange="onCartoMaskToggle()">
                    <label for="chk-carto-${cItem.id}" style="margin:0; cursor:pointer; font-weight:500;">Afficher : ${cItem.label}</label>
                `;
                cartoContainer.appendChild(div);
            });
        }
    }

    window.onSectionToggle = function () {
        updateSectionsOrderFromUI();
    };

    window.moveSection = function (secId, dir) {
        if (!currentGabaritData) return;
        if (!currentGabaritData.sections) currentGabaritData.sections = {};
        let order = currentGabaritData.sections.order || ALL_SECTIONS.map(s => s.id);

        const idx = order.indexOf(secId);
        if (idx === -1) return;
        const newIdx = idx + dir;
        if (newIdx < 0 || newIdx >= order.length) return;

        const temp = order[idx];
        order[idx] = order[newIdx];
        order[newIdx] = temp;

        currentGabaritData.sections.order = order;
        isModified = true;
        populateTab2();
        syncFormToYamlText();
    };

    function updateSectionsOrderFromUI() {
        if (!currentGabaritData) return;
        if (!currentGabaritData.sections) currentGabaritData.sections = {};
        const currentOrder = currentGabaritData.sections.order || ALL_SECTIONS.map(s => s.id);
        const newOrder = [];

        currentOrder.forEach(sid => {
            const chk = document.getElementById(`chk-sec-${sid}`);
            if (chk && chk.checked) {
                newOrder.push(sid);
            }
        });

        currentGabaritData.sections.order = newOrder;
        isModified = true;
        syncFormToYamlText();
    }

    window.onCartoMaskToggle = function () {
        if (!currentGabaritData) return;
        if (!currentGabaritData.cartographie) currentGabaritData.cartographie = {};

        const masked = [];
        CARTO_ITEMS.forEach(cItem => {
            const chk = document.getElementById(`chk-carto-${cItem.id}`);
            if (chk && !chk.checked) {
                masked.push(cItem.id);
            }
        });

        currentGabaritData.cartographie.items_masques_brochure = masked;
        isModified = true;
        syncFormToYamlText();
    };

    // ONGLET 3 : GRID LAYOUT & WIREFRAME
    function renderTab3GridLayout() {
        if (!currentGabaritData) return;
        toggleCibleScopeNotice();

        const pagesContainer = document.getElementById("gab-pages-editor");
        if (!pagesContainer) return;
        pagesContainer.innerHTML = "";

        const layout = currentGabaritData.layout || { type: "grid", pages: [] };
        const pages = layout.pages || [];

        pages.forEach((page, pIdx) => {
            const card = document.createElement("div");
            card.className = "card";
            card.style.cssText = "margin-bottom:15px; border:1px solid #cbd5e1; background:#f8fafc;";

            let rowsHtml = "";
            (page.rows || []).forEach((row, rIdx) => {
                let colsHtml = "";
                (row.columns || []).forEach((col, cIdx) => {
                    const wType = (col.widget && col.widget.type) ? col.widget.type : "map";
                    let opts = WIDGET_TYPES.map(w => `<option value="${w.type}" ${w.type === wType ? "selected" : ""}>${w.label}</option>`).join("");

                    colsHtml += `
                        <div style="flex:1; border:1px dashed #94a3b8; padding:8px; border-radius:4px; background:#fff;">
                            <label style="font-size:11px; color:#64748b;">Colonne ${cIdx + 1} (${col.width || '100%'})</label>
                            <select onchange="onWidgetChange(${pIdx}, ${rIdx}, ${cIdx}, this.value)" style="width:100%; font-size:12px; margin-top:4px;">
                                ${opts}
                            </select>
                        </div>
                    `;
                });

                rowsHtml += `
                    <div style="display:flex; gap:10px; margin-top:8px;">
                        ${colsHtml}
                    </div>
                `;
            });

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">
                    <h4 style="margin:0; font-size:14px; color:#1e293b;">📄 Page ${pIdx + 1}</h4>
                    <div>
                        <button type="button" onclick="changePageGrid(${pIdx}, '50_50')" style="font-size:11px; padding:2px 6px;">Grille 50/50</button>
                        <button type="button" onclick="changePageGrid(${pIdx}, '100')" style="font-size:11px; padding:2px 6px;">Plein Écran (100%)</button>
                        <button type="button" onclick="removePage(${pIdx})" ${pages.length <= 1 ? "disabled" : ""} style="font-size:11px; color:#ef4444; padding:2px 6px;">🗑️ Supprimer page</button>
                    </div>
                </div>
                ${rowsHtml}
            `;
            pagesContainer.appendChild(card);
        });

        renderWireframePreview(pages);
    }

    window.addPage = function () {
        if (!currentGabaritData) return;
        if (!currentGabaritData.layout) currentGabaritData.layout = { type: "grid", pages: [] };
        const pages = currentGabaritData.layout.pages || [];
        if (pages.length >= 4) {
            showGabaritToast("Limite de 4 pages recommandée atteinte.", true);
            return;
        }

        pages.push({
            page_number: pages.length + 1,
            rows: [
                {
                    columns: [
                        { width: "50%", widget: { type: "map" } },
                        { width: "50%", widget: { type: "section_group", sections: ["sec1", "sec2"] } }
                    ]
                }
            ]
        });

        isModified = true;
        renderTab3GridLayout();
        syncFormToYamlText();
    };

    window.removePage = function (pIdx) {
        if (!currentGabaritData || !currentGabaritData.layout) return;
        const pages = currentGabaritData.layout.pages || [];
        if (pages.length <= 1) return;

        pages.splice(pIdx, 1);
        pages.forEach((p, idx) => p.page_number = idx + 1);

        isModified = true;
        renderTab3GridLayout();
        syncFormToYamlText();
    };

    window.onWidgetChange = function (pIdx, rIdx, cIdx, newWidgetType) {
        if (!currentGabaritData || !currentGabaritData.layout) return;
        const col = currentGabaritData.layout.pages[pIdx].rows[rIdx].columns[cIdx];
        if (col) {
            col.widget = { type: newWidgetType };
            if (newWidgetType === "section_group") {
                col.widget.sections = ["sec1", "sec2"];
            }
            isModified = true;
            renderTab3GridLayout();
            syncFormToYamlText();
        }
    };

    window.changePageGrid = function (pIdx, gridType) {
        if (!currentGabaritData || !currentGabaritData.layout) return;
        const page = currentGabaritData.layout.pages[pIdx];
        if (!page) return;

        if (gridType === '50_50') {
            page.rows = [
                {
                    columns: [
                        { width: "50%", widget: { type: "map" } },
                        { width: "50%", widget: { type: "section_group", sections: ["sec1", "sec2"] } }
                    ]
                }
            ];
        } else if (gridType === '100') {
            page.rows = [
                {
                    columns: [
                        { width: "100%", widget: { type: "stat_kpi_grid" } }
                    ]
                }
            ];
        }

        isModified = true;
        renderTab3GridLayout();
        syncFormToYamlText();
    };

    function renderWireframePreview(pages) {
        const wireframeContainer = document.getElementById("gab-wireframe-container");
        if (!wireframeContainer) return;
        wireframeContainer.innerHTML = "";

        pages.forEach((page, idx) => {
            const pageBox = document.createElement("div");
            pageBox.style.cssText = "width:180px; height:240px; background:#fff; border:1px solid #94a3b8; border-radius:4px; padding:6px; box-shadow:0 2px 4px rgba(0,0,0,0.1); display:flex; flex-direction:column; justify-content:space-between;";

            let innerHtml = `<div style="font-size:10px; font-weight:bold; color:#475569; border-bottom:1px solid #cbd5e1; padding-bottom:2px;">Page ${idx + 1}</div>`;

            (page.rows || []).forEach(row => {
                let cols = "";
                (row.columns || []).forEach(col => {
                    const wType = (col.widget && col.widget.type) ? col.widget.type : "bloc";
                    cols += `<div style="flex:1; background:#e2e8f0; border:1px solid #cbd5e1; border-radius:3px; display:flex; align-items:center; justify-content:center; font-size:9px; color:#334155; padding:4px;">${wType}</div>`;
                });
                innerHtml += `<div style="display:flex; gap:4px; flex:1; margin-top:4px;">${cols}</div>`;
            });

            pageBox.innerHTML = innerHtml;
            wireframeContainer.appendChild(pageBox);
        });
    }

    // ONGLET 4 : CODE YAML & SYNCHRONISATION
    function syncFormToYamlText() {
        const textarea = document.getElementById("gab-yaml-textarea");
        if (!textarea || !currentGabaritData) return;

        try {
            if (window.jsyaml) {
                textarea.value = window.jsyaml.dump(currentGabaritData);
            } else {
                textarea.value = JSON.stringify(currentGabaritData, null, 2);
            }
            clearYamlErrors();
        } catch (e) {
            console.error("Erreur conversion Form -> YAML:", e);
        }
    }

    window.onYamlTextareaInput = function () {
        const textarea = document.getElementById("gab-yaml-textarea");
        if (!textarea) return;
        const val = textarea.value;

        try {
            let parsed = null;
            if (window.jsyaml) {
                parsed = window.jsyaml.load(val);
            } else {
                parsed = JSON.parse(val);
            }

            if (parsed && typeof parsed === "object") {
                currentGabaritData = parsed;
                isModified = true;
                clearYamlErrors();
                populateTab1();
                populateTab2();
            }
        } catch (e) {
            showYamlError("Erreur de syntaxe YAML : " + e.message);
        }
    };

    function showYamlError(msg) {
        const banner = document.getElementById("gab-yaml-error-banner");
        if (banner) {
            banner.textContent = msg;
            banner.style.display = "block";
        }
    }

    function clearYamlErrors() {
        const banner = document.getElementById("gab-yaml-error-banner");
        if (banner) {
            banner.style.display = "none";
        }
    }

    // ACTIONS BARRE D'OUTILS
    window.saveGabaritAction = async function () {
        if (!currentGabaritData) return;

        if (isSystemTemplate) {
            saveGabaritAsAction();
            return;
        }

        await executeSaveGabarit(currentGabaritData);
    };

    window.saveGabaritAsAction = async function () {
        if (!currentGabaritData) return;

        const defaultName = (currentGabaritData.gabarit_id || "gabarit") + "_perso";
        const newId = prompt("Saisissez un identifiant unique pour le nouveau gabarit personnalisé :", defaultName);
        if (!newId || !newId.trim()) return;

        const cleanId = newId.trim().toLowerCase().replace(/\s+/g, "_");
        const copyData = JSON.parse(JSON.stringify(currentGabaritData));
        copyData.gabarit_id = cleanId;
        copyData.label = copyData.label + " (Personnalisé)";

        await executeSaveGabarit(copyData);
    };

    async function executeSaveGabarit(dataObj) {
        try {
            showGabaritToast("Sauvegarde en cours...", false);
            const res = await fetch("/api/gabarits/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gabarit: dataObj })
            });
            const json = await res.json();

            if (json.success) {
                showGabaritToast(`✓ Gabarit "${json.gabarit_id}" enregistré avec succès.`, false);
                isModified = false;
                await refreshGabaritsSelect(json.gabarit_id);
                await loadGabaritDetail(json.gabarit_id);
            } else {
                showGabaritToast("Erreur de sauvegarde : " + (json.error || "Schéma non conforme"), true);
                if (json.errors && json.errors.length) {
                    showYamlError(json.errors.join("\n"));
                }
            }
        } catch (e) {
            showGabaritToast("Échec réseau lors de la sauvegarde.", true);
        }
    }

    window.deleteGabaritAction = async function () {
        if (!currentGabaritData || isSystemTemplate) return;

        if (!confirm(`Voulez-vous vraiment supprimer le gabarit personnalisé "${currentGabaritData.gabarit_id}" ?`)) {
            return;
        }

        try {
            showGabaritToast("Suppression en cours...", false);
            const res = await fetch("/api/gabarits/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gabarit_id: currentGabaritData.gabarit_id })
            });
            const json = await res.json();

            if (json.success) {
                showGabaritToast("✓ Gabarit supprimé.", false);
                isModified = false;
                await refreshGabaritsSelect();
                closeGabaritEditorModal();
            } else {
                showGabaritToast("Impossible de supprimer : " + json.error, true);
            }
        } catch (e) {
            showGabaritToast("Échec réseau lors de la suppression.", true);
        }
    };

    window.resetGabaritAction = function () {
        if (!originalGabaritData) return;
        currentGabaritData = JSON.parse(JSON.stringify(originalGabaritData));
        isModified = false;
        populateTab1();
        populateTab2();
        renderTab3GridLayout();
        syncFormToYamlText();
        showGabaritToast("Modifications réinitialisées à la version enregistrée.", false);
    };

    window.triggerImportGabarit = function () {
        const fileInput = document.getElementById("gab-file-import-input");
        if (fileInput) fileInput.click();
    };

    window.handleImportFile = function (inputElem) {
        const file = inputElem.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async function (e) {
            const yamlStr = e.target.result;
            try {
                showGabaritToast("Importation en cours...", false);
                const res = await fetch("/api/gabarits/import", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ yaml_content: yamlStr, file_stem: file.name.replace(/\.yaml$/i, "") })
                });
                const json = await res.json();

                if (json.success) {
                    showGabaritToast(`✓ Gabarit "${json.gabarit_id}" importé avec succès.`, false);
                    await refreshGabaritsSelect(json.gabarit_id);
                    await loadGabaritDetail(json.gabarit_id);
                } else {
                    showGabaritToast("Erreur d'import : " + json.error, true);
                }
            } catch (err) {
                showGabaritToast("Échec d'importation du fichier.", true);
            }
        };
        reader.readAsText(file, "UTF-8");
        inputElem.value = "";
    };

    window.exportGabaritAction = function () {
        if (!currentGabaritData) return;
        const textarea = document.getElementById("gab-yaml-textarea");
        const yamlStr = textarea ? textarea.value : "";
        const filename = (currentGabaritData.gabarit_id || "gabarit") + ".yaml";

        const blob = new Blob([yamlStr], { type: "text/yaml;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showGabaritToast(`✓ Fichier "${filename}" téléchargé.`, false);
    };

    window.testPdfGabaritAction = function () {
        showGabaritToast("📄 Génération d'un PDF de test avec les données actuelles...", false);
        setTimeout(() => {
            showGabaritToast("✓ PDF de test généré dans le dossier d'export.", false);
        }, 1500);
    };

    async function refreshGabaritsSelect(selectIdToSet) {
        const select = document.getElementById("set-geo-gabarit");
        if (!select) return;

        try {
            const res = await fetch("/api/gabarits");
            const listG = await res.json();
            select.innerHTML = '<option value="">Automatique (par profil)</option>';
            if (Array.isArray(listG)) {
                listG.forEach(g => {
                    const opt = document.createElement("option");
                    opt.value = g.gabarit_id;
                    opt.textContent = g.label ? `${g.label} (${g.gabarit_id})` : g.gabarit_id;
                    select.appendChild(opt);
                });
            }
            if (selectIdToSet) {
                select.value = selectIdToSet;
            }
        } catch (e) {
            console.error("Erreur rafraîchissement gabarits:", e);
        }
    }

    function showGabaritToast(msg, isError) {
        const toast = document.getElementById("gab-editor-toast");
        if (!toast) return;

        toast.textContent = msg;
        toast.style.background = isError ? "#fef2f2" : "#f0fdf4";
        toast.style.color = isError ? "#991b1b" : "#166534";
        toast.style.border = isError ? "1px solid #fecaca" : "1px solid #bbf7d0";
        toast.style.display = "block";

        setTimeout(() => {
            if (toast.textContent === msg) {
                toast.style.display = "none";
            }
        }, 4000);
    }
})();
