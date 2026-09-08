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

/**
 * ========================================================================================
 * EXPLORATEUR CARTOGRAPHIQUE ET DASHBOARD INTERACTIF (`explorer.js`)
 * ========================================================================================
 * Ce fichier JavaScript orchestre l'interface dynamique de l'explorateur de données OFBilan.
 *
 * Fonctionnalités majeures :
 *   1. Initialisation et contrôle de la carte interactive Leaflet (fond de carte OpenStreetMap,
 *      couches de points de contrôle, géométries PNF / TUB, marqueurs personnalisés).
 *   2. Construction et mise à jour dynamique des graphiques d'analyse statistique (Chart.js) :
 *      résultats de contrôle, répartition par usagers, domaines et thématiques.
 *   3. Filtrage en temps réel des données par période, périmètre géographique et mots-clés.
 *   4. Gestion du tableau de données interactif (tri des colonnes, pagination, recherche).
 *   5. Export des données filtrées vers Excel et génération de rapports cartographiques.
 * ========================================================================================
 */
// Système de remontée automatique des journaux JS client vers le serveur web (/api/log)
function sendClientLog(level, message, source = 'explorer.js', line = '', context = null) {
    try {
        const payload = JSON.stringify({
            level: level || 'INFO',
            message: message || '',
            source: source,
            line: line,
            context: context
        });
        if (navigator.sendBeacon) {
            const blob = new Blob([payload], { type: 'application/json' });
            navigator.sendBeacon('/api/log', blob);
        } else {
            fetch('/api/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
                keepalive: true
            }).catch(() => {});
        }
    } catch (e) {}
}

window.onerror = function (msg, url, lineNo, columnNo, error) {
    const filename = url ? url.split('/').pop() : 'explorer.js';
    sendClientLog('ERROR', String(msg), filename, lineNo ? `${lineNo}:${columnNo || 0}` : '', {
        stack: error ? error.stack : null
    });
    return false;
};

window.addEventListener('unhandledrejection', function (event) {
    const reason = event.reason;
    sendClientLog('ERROR', `Promesse rejetée non gérée: ${reason ? (reason.message || reason) : 'Inconnue'}`, 'async', '', {
        stack: reason ? reason.stack : null
    });
});

document.addEventListener('DOMContentLoaded', () => {
    let isUnloading = false;
    window.addEventListener('beforeunload', () => {
        isUnloading = true;
    });

    let chartResults = null;
    let chartDomains = null;
    let chartUsagers = null;
    let chartThemes = null;
    let chartSeasonality = null;
    let boundaryLayer = null;

    // Fix chart pixelation globally (supports Chart.js v2 and v3+)
    if (typeof Chart !== 'undefined') {
        Chart.defaults.devicePixelRatio = 4;
        if (Chart.defaults.global) Chart.defaults.global.devicePixelRatio = 20;
    }

    // État pour le tableau détaillé des contrôles
    let activePoints = [];
    let activeProcedures = [];
    let currentTablePage = 1;
    const tableRowsPerPage = 25;
    let tableSortColumn = '';
    let tableSortAsc = true;
    let isTableExpanded = false;

    // Fonction utilitaire de normalisation (insensibilité à la casse et aux accents)
    function normalizeStr(str) {
        if (!str) return '';
        return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    // État pour le filtrage dynamique à la volée (Masquage visuel carte/chaleur/stats)
    const dynamicExclusions = {
        types: new Set(),
        domaines: new Set(),
        themes: new Set(),
        actions: new Set()
    };
    let lastFetchedDataPayload = null;

    // Mode d'affichage et filtre interactif des KPI / Donuts
    let currentMapMode = 'results'; // 'results' | 'usagers'
    let activeKpiFilter = null; // null | 'controles' | 'pej' | 'pa' | 'pve' | 'usagers' | 'chart-results' | 'chart-usagers' | 'usager:Label'
    window.usagerLegendFilters = {
        'Particulier': true,
        'Agriculteur': true,
        'Collectivité': true,
        'Entreprise': true,
        'Acteurs sylvicoles': true,
        'Autre': true
    };

    function getUsagerCategory(typeUsager) {
        if (!typeUsager) return 'Autre';
        const l = typeUsager.toLowerCase();
        if (l.includes('agriculteur')) return 'Agriculteur';
        if (l.includes('particulier')) return 'Particulier';
        if (l.includes('collectiv')) return 'Collectivité';
        if (l.includes('entreprise')) return 'Entreprise';
        if (l.includes('sylvic')) return 'Acteurs sylvicoles';
        return 'Autre';
    }

    function getUsagerColor(typeUsager) {
        const cat = getUsagerCategory(typeUsager);
        switch (cat) {
            case 'Agriculteur': return '#F1C40F';
            case 'Particulier': return '#2980B9';
            case 'Collectivité': return '#27AE60';
            case 'Entreprise': return '#E74C3C';
            case 'Acteurs sylvicoles': return '#16A085';
            default: return '#95A5A6';
        }
    }

    function setActiveKpiVisual(filterName) {
        document.querySelectorAll('.stat-card').forEach(el => el.classList.remove('active-kpi-button'));
        document.querySelectorAll('.interactive-chart-card').forEach(el => el.classList.remove('active-chart-button'));

        if (!filterName) return;

        if (['controles', 'pej', 'pa', 'pve', 'usagers'].includes(filterName)) {
            const kpiEl = document.getElementById(`stat-card-${filterName}`);
            if (kpiEl) kpiEl.classList.add('active-kpi-button');
        }

        if (filterName === 'chart-results' || filterName === 'controles' || filterName.startsWith('resultat:')) {
            const cardRes = document.getElementById('card-chart-results');
            if (cardRes) cardRes.classList.add('active-chart-button');
            const kpiCtrl = document.getElementById('stat-card-controles');
            if (kpiCtrl) kpiCtrl.classList.add('active-kpi-button');
        } else if (filterName === 'chart-usagers' || filterName === 'usagers' || filterName.startsWith('usager:')) {
            const cardUsa = document.getElementById('card-chart-usagers');
            if (cardUsa) cardUsa.classList.add('active-chart-button');
            const kpiUsa = document.getElementById('stat-card-usagers');
            if (kpiUsa) kpiUsa.classList.add('active-kpi-button');
        } else if (filterName === 'chart-domains' || filterName.startsWith('domaine:')) {
            const cardDom = document.getElementById('card-chart-domains');
            if (cardDom) cardDom.classList.add('active-chart-button');
        } else if (filterName === 'chart-themes' || filterName.startsWith('theme:')) {
            const cardTh = document.getElementById('card-chart-themes');
            if (cardTh) cardTh.classList.add('active-chart-button');
        }
    }

    function findUsagerValue(targetLabel) {
        if (!targetLabel) return null;
        const norm = normalizeStr(targetLabel);
        const item = usagersList.find(u => u.value && (normalizeStr(u.value).includes(norm) || norm.includes(normalizeStr(u.value)) || normalizeStr(u.label).includes(norm)));
        return item ? item.value : null;
    }

    window.handleKpiClick = function(filterName) {
        if (filterName === 'chart-usagers') filterName = 'usagers';
        if (filterName === 'chart-results') filterName = 'controles';

        if (activeKpiFilter === filterName) {
            resetKpiFilter();
            return;
        }

        activeKpiFilter = filterName;
        setActiveKpiVisual(filterName);

        let shouldLoadData = false;

        if (filterName === 'controles') {
            currentMapMode = 'results';
            const choroplethSelect = document.getElementById('choropleth-metric');
            if (choroplethSelect) choroplethSelect.value = 'controles';
            legendFilters.ctrl_conforme = true;
            legendFilters.ctrl_infraction = true;
            legendFilters.ctrl_attente = true;
            legendFilters.pej = true;
            legendFilters.pa = true;
            legendFilters.pve = true;
        } else if (filterName === 'pej') {
            currentMapMode = 'results';
            const choroplethSelect = document.getElementById('choropleth-metric');
            if (choroplethSelect) choroplethSelect.value = 'pej';
            legendFilters.ctrl_conforme = false;
            legendFilters.ctrl_infraction = false;
            legendFilters.ctrl_attente = false;
            legendFilters.pej = true;
            legendFilters.pa = false;
            legendFilters.pve = false;
        } else if (filterName === 'pa') {
            currentMapMode = 'results';
            legendFilters.ctrl_conforme = false;
            legendFilters.ctrl_infraction = false;
            legendFilters.ctrl_attente = false;
            legendFilters.pej = false;
            legendFilters.pa = true;
            legendFilters.pve = false;
        } else if (filterName === 'pve') {
            currentMapMode = 'results';
            const choroplethSelect = document.getElementById('choropleth-metric');
            if (choroplethSelect) choroplethSelect.value = 'pve';
            legendFilters.ctrl_conforme = false;
            legendFilters.ctrl_infraction = false;
            legendFilters.ctrl_attente = false;
            legendFilters.pej = false;
            legendFilters.pa = false;
            legendFilters.pve = true;
        } else if (filterName === 'usagers') {
            currentMapMode = 'usagers';
            Object.keys(usagerLegendFilters).forEach(k => usagerLegendFilters[k] = true);
        } else if (filterName.startsWith('usager:')) {
            currentMapMode = 'usagers';
            const targetLabel = filterName.substring(7);
            const usagerVal = findUsagerValue(targetLabel);
            if (usagerVal && typeof inputUsager !== 'undefined') {
                const currentVals = inputUsager.getSelectedValues ? inputUsager.getSelectedValues() : [];
                if (currentVals.includes(usagerVal)) {
                    if (inputUsager.setSelectedValues) inputUsager.setSelectedValues([]);
                    else inputUsager.value = '';
                    activeKpiFilter = null;
                    setActiveKpiVisual(null);
                } else {
                    if (inputUsager.setSelectedValues) inputUsager.setSelectedValues([usagerVal]);
                    else inputUsager.value = usagerVal;
                }
                shouldLoadData = true;
            }
            const normTarget = normalizeStr(targetLabel);
            Object.keys(usagerLegendFilters).forEach(k => {
                usagerLegendFilters[k] = normalizeStr(k).includes(normTarget) || normTarget.includes(normalizeStr(k));
            });
        } else if (filterName.startsWith('resultat:')) {
            currentMapMode = 'results';
            const rawLabel = filterName.substring(9);
            const label = rawLabel.toLowerCase();
            let resVal = 'Conforme';
            if (label.includes('conforme') && !label.includes('non')) {
                resVal = 'Conforme';
                legendFilters.ctrl_conforme = true;
                legendFilters.ctrl_infraction = false;
                legendFilters.ctrl_attente = false;
            } else if (label.includes('non') || label.includes('infraction') || label.includes('manquement')) {
                resVal = 'Non-conforme';
                legendFilters.ctrl_conforme = false;
                legendFilters.ctrl_infraction = true;
                legendFilters.ctrl_attente = false;
            } else {
                resVal = 'En attente';
                legendFilters.ctrl_conforme = false;
                legendFilters.ctrl_infraction = false;
                legendFilters.ctrl_attente = true;
            }
            legendFilters.pej = false;
            legendFilters.pa = false;
            legendFilters.pve = false;

            if (typeof inputResultat !== 'undefined' && inputResultat) {
                const currentVals = inputResultat.getSelectedValues ? inputResultat.getSelectedValues() : [];
                if (currentVals.includes(resVal)) {
                    if (inputResultat.setSelectedValues) inputResultat.setSelectedValues([]);
                    else inputResultat.value = '';
                    activeKpiFilter = null;
                    setActiveKpiVisual(null);
                } else {
                    if (inputResultat.setSelectedValues) inputResultat.setSelectedValues([resVal]);
                    else inputResultat.value = resVal;
                }
                shouldLoadData = true;
            }
        }

        triggerMapReRender();
        if (shouldLoadData) {
            loadData();
        }
    };

    window.resetKpiFilter = function() {
        activeKpiFilter = null;
        currentMapMode = 'results';
        setActiveKpiVisual(null);
        legendFilters.ctrl_conforme = true;
        legendFilters.ctrl_infraction = true;
        legendFilters.ctrl_attente = true;
        legendFilters.pej = true;
        legendFilters.pa = true;
        legendFilters.pve = true;
        Object.keys(usagerLegendFilters).forEach(k => usagerLegendFilters[k] = true);

        if (typeof inputUsager !== 'undefined' && inputUsager.setSelectedValues) inputUsager.setSelectedValues([]);
        if (typeof inputDomaineSNC !== 'undefined' && inputDomaineSNC.setSelectedValues) inputDomaineSNC.setSelectedValues([]);
        if (typeof inputThemeSNC !== 'undefined' && inputThemeSNC.setSelectedValues) inputThemeSNC.setSelectedValues([]);
        if (typeof inputResultat !== 'undefined' && inputResultat.setSelectedValues) inputResultat.setSelectedValues([]);

        triggerMapReRender();
        loadData();
    };

    window.toggleUsagerLegendFilter = function(categoryKey, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        usagerLegendFilters[categoryKey] = usagerLegendFilters[categoryKey] === false ? true : false;
        triggerMapReRender();
    };

    function getFilteredHeatmapData() {
        const heatData = [];
        if (!lastFetchedDataPayload) return heatData;

        const { rawResN, rawResN1 } = lastFetchedDataPayload;

        // Points Contrôles N
        if (rawResN && rawResN.points) {
            rawResN.points.forEach(pt => {
                if (isItemDynamicallyExcluded(pt, false)) return;
                if (['pej', 'pa', 'pve'].includes(activeKpiFilter)) return;
                if (activeKpiFilter && activeKpiFilter.startsWith('usager:')) {
                    const target = normalizeStr(activeKpiFilter.substring(7));
                    const cat = normalizeStr(getUsagerCategory(pt.type_usager));
                    if (!cat.includes(target) && !target.includes(cat)) return;
                }

                const usagerCat = getUsagerCategory(pt.type_usager);
                if (currentMapMode === 'usagers') {
                    if (usagerLegendFilters[usagerCat] === false) return;
                } else {
                    const res = (pt.resultat || '').toLowerCase();
                    if (res.includes('conforme') && !res.includes('non')) {
                        if (legendFilters.ctrl_conforme === false) return;
                    } else if (res.includes('infraction') || res.includes('non') || res.includes('manquement')) {
                        if (legendFilters.ctrl_infraction === false) return;
                    } else {
                        if (legendFilters.ctrl_attente === false) return;
                    }
                }

                const lat = parseFloat(pt.y);
                const lng = parseFloat(pt.x);
                if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                    heatData.push([lat, lng, 1.0]);
                }
            });
        }

        // Procédures N
        if (currentMapMode !== 'usagers' && rawResN && rawResN.procedures) {
            rawResN.procedures.forEach(p => {
                if (isItemDynamicallyExcluded(p, true)) return;
                if (activeKpiFilter === 'controles') return;
                const ptype = (p.type || '').toUpperCase();
                if (activeKpiFilter === 'pej' && !ptype.includes('PEJ')) return;
                if (activeKpiFilter === 'pa' && !ptype.includes('PA')) return;
                if (activeKpiFilter === 'pve' && !ptype.includes('PVE')) return;

                if (ptype.includes('PEJ') && legendFilters.pej === false) return;
                if (ptype.includes('PA') && legendFilters.pa === false) return;
                if (ptype.includes('PVE') && legendFilters.pve === false) return;

                const lat = parseFloat(p.y);
                const lng = parseFloat(p.x);
                if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                    heatData.push([lat, lng, 1.0]);
                }
            });
        }

        // Complément N-1 si comparaison active
        if (rawResN1) {
            if (rawResN1.points) {
                rawResN1.points.forEach(pt => {
                    if (isItemDynamicallyExcluded(pt, false)) return;
                    if (['pej', 'pa', 'pve'].includes(activeKpiFilter)) return;
                    if (activeKpiFilter && activeKpiFilter.startsWith('usager:')) {
                        const target = normalizeStr(activeKpiFilter.substring(7));
                        const cat = normalizeStr(getUsagerCategory(pt.type_usager));
                        if (!cat.includes(target) && !target.includes(cat)) return;
                    }

                    const usagerCat = getUsagerCategory(pt.type_usager);
                    if (currentMapMode === 'usagers') {
                        if (usagerLegendFilters[usagerCat] === false) return;
                    } else {
                        const res = (pt.resultat || '').toLowerCase();
                        if (res.includes('conforme') && !res.includes('non')) {
                            if (legendFilters.ctrl_conforme === false) return;
                        } else if (res.includes('infraction') || res.includes('non') || res.includes('manquement')) {
                            if (legendFilters.ctrl_infraction === false) return;
                        } else {
                            if (legendFilters.ctrl_attente === false) return;
                        }
                    }

                    const lat = parseFloat(pt.y);
                    const lng = parseFloat(pt.x);
                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        heatData.push([lat, lng, 1.0]);
                    }
                });
            }
            if (currentMapMode !== 'usagers' && rawResN1.procedures) {
                rawResN1.procedures.forEach(p => {
                    if (isItemDynamicallyExcluded(p, true)) return;
                    if (activeKpiFilter === 'controles') return;
                    const ptype = (p.type || '').toUpperCase();
                    if (activeKpiFilter === 'pej' && !ptype.includes('PEJ')) return;
                    if (activeKpiFilter === 'pa' && !ptype.includes('PA')) return;
                    if (activeKpiFilter === 'pve' && !ptype.includes('PVE')) return;

                    if (ptype.includes('PEJ') && legendFilters.pej === false) return;
                    if (ptype.includes('PA') && legendFilters.pa === false) return;
                    if (ptype.includes('PVE') && legendFilters.pve === false) return;

                    const lat = parseFloat(p.y);
                    const lng = parseFloat(p.x);
                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        heatData.push([lat, lng, 1.0]);
                    }
                });
            }
        }

        return heatData;
    }

    function triggerMapReRender() {
        if (lastFetchedDataPayload) {
            const mapContainer = map.getContainer();
            if (mapContainer) {
                mapContainer.classList.add('map-fade-transition');
                mapContainer.style.opacity = '0.4';
            }
            setTimeout(() => {
                try {
                    renderLoadedData(lastFetchedDataPayload);
                    renderTable();
                } catch (e) {
                    console.error("Erreur lors de la mise à jour de la carte :", e);
                } finally {
                    if (mapContainer) mapContainer.style.opacity = '1';
                }
            }, 120);
        }
    }

    // Cache mémoire LRU pour les requêtes /api/data (filtres à la volée / années)
    const DATA_CACHE_MAX_SIZE = 50;
    const dataResponseCache = new Map();

    function clearDataResponseCache() {
        dataResponseCache.clear();
    }
    window.clearDataResponseCache = clearDataResponseCache;

    function cloneData(data) {
        if (!data) return data;
        return typeof structuredClone === 'function' ? structuredClone(data) : JSON.parse(JSON.stringify(data));
    }

    function getOrSetCache(cacheKey, fetchFn) {
        if (dataResponseCache.has(cacheKey)) {
            const cachedData = dataResponseCache.get(cacheKey);
            dataResponseCache.delete(cacheKey);
            dataResponseCache.set(cacheKey, cachedData);
            return Promise.resolve(cloneData(cachedData));
        }
        return fetchFn().then(data => {
            if (dataResponseCache.size >= DATA_CACHE_MAX_SIZE) {
                const oldestKey = dataResponseCache.keys().next().value;
                dataResponseCache.delete(oldestKey);
            }
            dataResponseCache.set(cacheKey, data);
            return cloneData(data);
        });
    }

    function triggerDataFadeIn(selector = '.explorer-panel, .stat-card, #results-count') {
        document.querySelectorAll(selector).forEach(el => {
            el.classList.remove('data-fade-in');
            void el.offsetWidth;
            el.classList.add('data-fade-in');
        });
    }

    function isItemDynamicallyExcluded(item, isProcedure = false) {
        if (!item) return false;

        if (isProcedure) {
            const ptype = (item.type || '').toUpperCase();
            if (ptype.includes('PEJ') && dynamicExclusions.types.has('PEJ')) return true;
            if (ptype.includes('PA') && dynamicExclusions.types.has('PA')) return true;
            if (ptype.includes('PVE') && dynamicExclusions.types.has('PVE')) return true;
        } else {
            if (dynamicExclusions.types.has('CONTROLES')) return true;
        }

        const dom = item.domaine?.trim();
        const thm = item.theme?.trim();
        const act = item.type_action?.trim();
        return (dom && dynamicExclusions.domaines.has(dom)) ||
               (thm && dynamicExclusions.themes.has(thm)) ||
               (act && dynamicExclusions.actions.has(act));
    }

    function populateDynamicFilterOptions(points = [], procedures = []) {
        const sets = { domaines: new Set(), themes: new Set(), actions: new Set() };
        const keys = [
            { field: 'domaine', set: sets.domaines },
            { field: 'theme', set: sets.themes },
            { field: 'type_action', set: sets.actions }
        ];

        points.concat(procedures).forEach(item => {
            if (!item) return;
            keys.forEach(({ field, set }) => {
                const val = item[field]?.trim();
                if (val) set.add(val);
            });
        });

        const procTypes = [
            { label: 'Contrôles (points)', key: 'CONTROLES' },
            { label: 'PEJ (Procédures Judiciaires)', key: 'PEJ' },
            { label: 'PA (Procédures Admin.)', key: 'PA' },
            { label: 'PVe (Procès-Verbaux)', key: 'PVE' }
        ];

        const renderTypesGroup = (searchTerm = '') => {
            const container = document.getElementById('dynamic-filter-types');
            const groupWrapper = document.getElementById('dynamic-filter-types-group');
            if (!container) return;
            container.innerHTML = '';

            const searchNorm = normalizeStr(searchTerm);
            const filteredTypes = procTypes.filter(t => !searchTerm || normalizeStr(t.label).includes(searchNorm) || normalizeStr(t.key).includes(searchNorm));

            if (groupWrapper) groupWrapper.style.display = filteredTypes.length === 0 ? 'none' : 'block';
            if (filteredTypes.length === 0) return;

            const sortedTypes = [...filteredTypes].sort((a, b) => {
                const aChecked = dynamicExclusions.types.has(a.key);
                const bChecked = dynamicExclusions.types.has(b.key);
                if (aChecked !== bChecked) return aChecked ? -1 : 1;
                return a.label.localeCompare(b.label, 'fr');
            });

            sortedTypes.forEach(t => {
                const label = document.createElement('label');
                label.style.cssText = 'display: flex; align-items: center; gap: 4px; font-weight: normal; margin: 0; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px;';
                label.title = t.label;
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = t.key;
                cb.checked = dynamicExclusions.types.has(t.key);
                cb.addEventListener('change', () => {
                    if (cb.checked) {
                        dynamicExclusions.types.add(t.key);
                    } else {
                        dynamicExclusions.types.delete(t.key);
                    }
                    updateDynamicFilterBadge();
                    renderTypesGroup(document.getElementById('dynamic-filter-search')?.value || '');
                    if (lastFetchedDataPayload && typeof renderLoadedData === 'function') {
                        renderLoadedData(lastFetchedDataPayload);
                    }
                });
                label.appendChild(cb);
                label.appendChild(document.createTextNode(t.label));
                container.appendChild(label);
            });
        };

        const renderItemsGroup = (containerId, set, typeKey, groupWrapperId, searchTerm = '') => {
            const container = document.getElementById(containerId);
            const groupWrapper = document.getElementById(groupWrapperId);
            if (!container) return;
            container.innerHTML = '';

            const searchNorm = normalizeStr(searchTerm);
            const allItems = Array.from(set).filter(val => !searchTerm || normalizeStr(val).includes(searchNorm));

            if (groupWrapper) {
                groupWrapper.style.display = allItems.length === 0 ? 'none' : 'block';
            }
            if (allItems.length === 0) return;

            const sorted = allItems.sort((a, b) => {
                const aChecked = dynamicExclusions[typeKey].has(a);
                const bChecked = dynamicExclusions[typeKey].has(b);
                if (aChecked !== bChecked) return aChecked ? -1 : 1;
                return a.localeCompare(b, 'fr');
            });

            sorted.forEach(val => {
                const label = document.createElement('label');
                label.style.cssText = 'display: flex; align-items: center; gap: 4px; font-weight: normal; margin: 0; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px;';
                label.title = val;
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = val;
                cb.checked = dynamicExclusions[typeKey].has(val);
                cb.addEventListener('change', () => {
                    if (cb.checked) {
                        dynamicExclusions[typeKey].add(val);
                    } else {
                        dynamicExclusions[typeKey].delete(val);
                    }
                    updateDynamicFilterBadge();
                    renderItemsGroup(containerId, set, typeKey, groupWrapperId, document.getElementById('dynamic-filter-search')?.value || '');
                    if (lastFetchedDataPayload && typeof renderLoadedData === 'function') {
                        renderLoadedData(lastFetchedDataPayload);
                    }
                });
                label.appendChild(cb);
                label.appendChild(document.createTextNode(val));
                container.appendChild(label);
            });
        };

        const renderAllGroups = (searchTerm = '') => {
            renderTypesGroup(searchTerm);
            renderItemsGroup('dynamic-filter-domaines', sets.domaines, 'domaines', 'dynamic-filter-domaines-group', searchTerm);
            renderItemsGroup('dynamic-filter-themes', sets.themes, 'themes', 'dynamic-filter-themes-group', searchTerm);
            renderItemsGroup('dynamic-filter-actions', sets.actions, 'actions', 'dynamic-filter-actions-group', searchTerm);
        };

        const searchInput = document.getElementById('dynamic-filter-search');
        if (searchInput) {
            searchInput.oninput = (e) => {
                renderAllGroups(e.target.value.trim());
            };
        }

        renderAllGroups(searchInput ? searchInput.value.trim() : '');
        updateDynamicFilterBadge();
    }

    function updateDynamicFilterBadge() {
        const badge = document.getElementById('dynamic-filter-badge');
        const count = dynamicExclusions.types.size + dynamicExclusions.domaines.size + dynamicExclusions.themes.size + dynamicExclusions.actions.size;
        if (badge) {
            if (count > 0) {
                badge.textContent = `${count} masqué${count > 1 ? 's' : ''}`;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    }

    const btnToggleDynFilter = document.getElementById('btn-toggle-dynamic-filter');
    const dynFilterPanel = document.getElementById('dynamic-filter-panel');
    const btnResetDynFilter = document.getElementById('btn-reset-dynamic-filter');

    if (btnToggleDynFilter && dynFilterPanel) {
        btnToggleDynFilter.addEventListener('click', (e) => {
            e.stopPropagation();
            dynFilterPanel.classList.toggle('hidden');
        });
        document.addEventListener('click', (e) => {
            if (!dynFilterPanel.contains(e.target) && e.target !== btnToggleDynFilter && !btnToggleDynFilter.contains(e.target)) {
                dynFilterPanel.classList.add('hidden');
            }
        });
    }

    if (btnResetDynFilter) {
        btnResetDynFilter.addEventListener('click', () => {
            dynamicExclusions.types.clear();
            dynamicExclusions.domaines.clear();
            dynamicExclusions.themes.clear();
            dynamicExclusions.actions.clear();
            const searchInput = document.getElementById('dynamic-filter-search');
            if (searchInput) searchInput.value = '';
            updateDynamicFilterBadge();
            if (lastFetchedDataPayload) {
                populateDynamicFilterOptions(lastFetchedDataPayload.rawResN.points, lastFetchedDataPayload.rawResN.procedures);
                if (typeof renderLoadedData === 'function') {
                    renderLoadedData(lastFetchedDataPayload);
                }
            }
        });
    }

    const btnUpdate = document.getElementById('btn-update');
    const selectEchelle = document.getElementById('echelle');
    const inputCode = document.getElementById('code');
    const codeHelper = document.getElementById('code-helper');

    // --- Accordéon : Filtres optionnels ---
    const accordHeader = document.getElementById('accordion-filtres-header');
    const accordBody = document.getElementById('accordion-filtres-body');
    const filtresBadge = document.getElementById('filtres-badge');
    const filtresInputs = [
        document.getElementById('type-usager'),
        document.getElementById('domaine-snc'),
        document.getElementById('theme-snc'),
        document.getElementById('type-action-snc'),
        document.getElementById('resultat-select')
    ];

    function updateFiltresBadge() {
        if (!filtresBadge) return;
        const count = filtresInputs.filter(el => el && el.value.trim() !== '').length;
        if (count > 0) {
            filtresBadge.textContent = count;
            filtresBadge.classList.remove('hidden');
        } else {
            filtresBadge.classList.add('hidden');
        }
    }

    filtresInputs.forEach(el => {
        if (el) el.addEventListener('input', updateFiltresBadge);
    });

    if (accordHeader && accordBody) {
        accordHeader.addEventListener('click', () => {
            const isOpen = accordBody.classList.contains('open');
            accordBody.classList.toggle('open', !isOpen);
            accordHeader.classList.toggle('open', !isOpen);
        });
    }

    // --- GESTION VOLET COULISSANT DES FILTRES (DRAWER IN-FLOW) ---
    const controlPanelEl = document.querySelector('.control-panel');
    const explorerContainerEl = document.querySelector('.explorer-container');
    const btnCloseFiltresPanel = document.getElementById('btn-close-filtres-panel');
    const btnOpenFiltresPanel = document.getElementById('btn-open-filtres-panel');
    const btnMapFullscreenFiltres = document.getElementById('btn-map-fullscreen-filtres');

    function toggleFiltresDrawer(show) {
        if (!controlPanelEl || !explorerContainerEl) return;
        const isCurrentlyCollapsed = controlPanelEl.classList.contains('collapsed');
        const shouldShow = typeof show === 'boolean' ? show : isCurrentlyCollapsed;

        if (shouldShow) {
            controlPanelEl.classList.remove('collapsed');
            explorerContainerEl.classList.remove('filtres-collapsed');
            try { localStorage.setItem('ofbilan_explorer_filtres_collapsed', 'false'); } catch (e) {}
        } else {
            controlPanelEl.classList.add('collapsed');
            explorerContainerEl.classList.add('filtres-collapsed');
            try { localStorage.setItem('ofbilan_explorer_filtres_collapsed', 'true'); } catch (e) {}
        }

        // Recalcul du rendu visuel des cartes et graphiques après animation
        setTimeout(() => {
            if (typeof map !== 'undefined' && map && typeof map.invalidateSize === 'function') {
                map.invalidateSize();
            }
            window.dispatchEvent(new Event('resize'));
        }, 310);
    }

    if (btnCloseFiltresPanel) {
        btnCloseFiltresPanel.addEventListener('click', () => toggleFiltresDrawer(false));
    }
    if (btnOpenFiltresPanel) {
        btnOpenFiltresPanel.addEventListener('click', () => toggleFiltresDrawer(true));
    }
    if (btnMapFullscreenFiltres) {
        btnMapFullscreenFiltres.addEventListener('click', () => toggleFiltresDrawer(true));
    }

    // Restauration de la préférence utilisateur sauvegardée dans localStorage
    try {
        const savedFiltresCollapsed = localStorage.getItem('ofbilan_explorer_filtres_collapsed');
        if (savedFiltresCollapsed === 'true') {
            toggleFiltresDrawer(false);
        }
    } catch (e) {}

    const btnToggleCodes = document.getElementById('btn-toggle-codes');
    const codesDropdown = document.getElementById('codes-dropdown');

    // Set default dates dynamically: Jan 1st of current year to today
    const now = new Date();
    const currentYear = now.getFullYear();
    const dateDebEl = document.getElementById('date-deb');
    const dateFinEl = document.getElementById('date-fin');
    if (dateDebEl) dateDebEl.value = `${currentYear}-01-01`;
    if (dateFinEl) {
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        dateFinEl.value = `${currentYear}-${month}-${day}`;
    }

    // Comparaison temporelle N-1
    const compareActiveCheck = document.getElementById('compare-active');
    const compareDatesContainer = document.getElementById('compare-dates-container');
    const compareDateDebEl = document.getElementById('compare-date-deb');
    const compareDateFinEl = document.getElementById('compare-date-fin');
    if (compareDateDebEl && compareDateFinEl) {
        const lastYear = currentYear - 1;
        compareDateDebEl.value = `${lastYear}-01-01`;

        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        compareDateFinEl.value = `${lastYear}-${month}-${day}`;
    }

    if (compareActiveCheck && compareDatesContainer) {
        compareActiveCheck.addEventListener('change', () => {
            if (compareActiveCheck.checked) {
                compareDatesContainer.classList.remove('hidden');
                
                // Synchronisation dynamique avec la période principale sélectionnée
                if (dateDebEl && dateFinEl && compareDateDebEl && compareDateFinEl) {
                    const debVal = dateDebEl.value;
                    const finVal = dateFinEl.value;
                    if (debVal && debVal.includes('-')) {
                        const [y, m, d] = debVal.split('-');
                        compareDateDebEl.value = `${parseInt(y) - 1}-${m}-${d}`;
                    }
                    if (finVal && finVal.includes('-')) {
                        const [y, m, d] = finVal.split('-');
                        compareDateFinEl.value = `${parseInt(y) - 1}-${m}-${d}`;
                    }
                }
            } else {
                compareDatesContainer.classList.add('hidden');
            }
        });
    }

    // --- Génération de la liste déroulante "Années Rapides" (Quick Years) au survol ---
    const quickYearContainer = document.getElementById('quick-year-container');
    if (quickYearContainer) {
        quickYearContainer.innerHTML = '';

        const dropdownWrapper = document.createElement('div');
        dropdownWrapper.className = 'quick-year-dropdown';

        const triggerBtn = document.createElement('button');
        triggerBtn.type = 'button';
        triggerBtn.id = 'quick-year-trigger';
        triggerBtn.className = 'btn-map-action btn-quick-year active';
        triggerBtn.title = "Sélectionner l'année de l'analyse";
        triggerBtn.innerHTML = `Année : <span id="quick-year-label">${currentYear}</span> ▾`;

        const menuPanel = document.createElement('div');
        menuPanel.className = 'quick-year-menu';

        // Générer pour l'année en cours + 5 années précédentes (6 années au total)
        for (let i = 0; i < 6; i++) {
            const y = currentYear - i;
            const itemBtn = document.createElement('button');
            itemBtn.type = 'button';
            itemBtn.className = `quick-year-item ${i === 0 ? 'active' : ''}`;
            itemBtn.dataset.year = y;
            itemBtn.innerHTML = `<span>${y}</span> <span class="check-mark">${i === 0 ? '✓' : ''}</span>`;

            itemBtn.addEventListener('click', (e) => {
                e.stopPropagation();

                // Mettre à jour l'étiquette du bouton déclencheur
                const labelEl = document.getElementById('quick-year-label');
                if (labelEl) labelEl.textContent = y;

                // Gestion de la classe active sur les items
                menuPanel.querySelectorAll('.quick-year-item').forEach(btn => {
                    btn.classList.remove('active');
                    const check = btn.querySelector('.check-mark');
                    if (check) check.textContent = '';
                });
                itemBtn.classList.add('active');
                const activeCheck = itemBtn.querySelector('.check-mark');
                if (activeCheck) activeCheck.textContent = '✓';

                // Refermer le menu si ouvert par clic
                dropdownWrapper.classList.remove('open');

                // Mise à jour des dates
                if (dateDebEl) dateDebEl.value = `${y}-01-01`;
                if (dateFinEl) {
                    if (y === currentYear) {
                        const m = String(now.getMonth() + 1).padStart(2, '0');
                        const d = String(now.getDate()).padStart(2, '0');
                        dateFinEl.value = `${y}-${m}-${d}`;
                    } else {
                        dateFinEl.value = `${y}-12-31`;
                    }
                }

                // Mise à jour du mode Comparaison N-1
                if (compareActiveCheck && compareActiveCheck.checked && compareDateDebEl && compareDateFinEl) {
                    const prevYear = y - 1;
                    compareDateDebEl.value = `${prevYear}-01-01`;
                    compareDateFinEl.value = `${prevYear}-12-31`;
                }

                // Empêcher le recentrage de la carte
                window.preventMapFitBounds = true;

                // Lancer le chargement
                if (btnUpdate) btnUpdate.click();
            });

            menuPanel.appendChild(itemBtn);
        }

        dropdownWrapper.appendChild(triggerBtn);
        dropdownWrapper.appendChild(menuPanel);
        quickYearContainer.appendChild(dropdownWrapper);

        // Support du clic pour ouvrir/fermer le menu déroulant
        triggerBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdownWrapper.classList.toggle('open');
        });

        document.addEventListener('click', () => {
            dropdownWrapper.classList.remove('open');
        });
    }

    // Gestion de la saisie manuelle pour adapter l'affichage
    const removeActiveChips = () => {
        const activeLabel = document.getElementById('quick-year-label');
        const activeItem = document.querySelector('.quick-year-item.active');
        if (activeItem) {
            activeItem.classList.remove('active');
            const check = activeItem.querySelector('.check-mark');
            if (check) check.textContent = '';
        }
        if (activeLabel) activeLabel.textContent = 'Personnalisée';
    };
    if (dateDebEl) dateDebEl.addEventListener('change', removeActiveChips);
    if (dateFinEl) dateFinEl.addEventListener('change', removeActiveChips);

    // Comportement du bouton Effacer (Reset) pour la réinitialisation
    const btnResetQuickYears = document.getElementById('btn-reset');
    if (btnResetQuickYears) {
        btnResetQuickYears.addEventListener('click', () => {
            setTimeout(() => {
                const labelEl = document.getElementById('quick-year-label');
                if (labelEl) labelEl.textContent = currentYear;
                const menuItems = document.querySelectorAll('.quick-year-item');
                menuItems.forEach(b => {
                    const isCurrent = (b.dataset.year == currentYear);
                    b.classList.toggle('active', isCurrent);
                    const check = b.querySelector('.check-mark');
                    if (check) check.textContent = isCurrent ? '✓' : '';
                });
            }, 50);
        });
    }
    // --- Fin de la logique Quick Years ---


    fetch('/api/profils?target=explorer')
        .then(res => res.json())
        .then(data => {
            const selectProfil = document.getElementById('profil-select');
            if (selectProfil && Array.isArray(data)) {
                selectProfil.innerHTML = '';
                window.profilsMetadata = {};
                data.forEach(p => {
                    if (p.value === 'types_usager_cible' || p.value === 'pnf_v2' || p.value === 'procedures_pve') return; // Désactivé dans l'explorer
                    window.profilsMetadata[p.value] = p;
                    const opt = document.createElement('option');
                    opt.value = p.value;
                    opt.textContent = p.label;
                    selectProfil.appendChild(opt);
                });

                selectProfil.addEventListener('change', updateUIForProfile);
                updateUIForProfile();
            }
        })
        .catch(err => console.error('Erreur chargement profils:', err));

    fetch('/api/version')
        .then(res => res.json())
        .then(data => {
            const versionSpan = document.getElementById('app-version');
            if (versionSpan && data.version) {
                versionSpan.textContent = data.version;
            }
        })
        .catch(err => console.error('Erreur chargement version:', err));

    function updateUIForProfile() {
        clearDataResponseCache();
        const selectProfil = document.getElementById('profil-select');
        if (!selectProfil) return;
        const val = selectProfil.value;
        const meta = window.profilsMetadata[val];
        if (!meta) return;

        // Griser les filtres thématiques
        const filterControls = [
            document.getElementById('domaine-snc'),
            document.getElementById('btn-toggle-domaines-snc'),
            document.getElementById('theme-snc'),
            document.getElementById('btn-toggle-themes-snc'),
            document.getElementById('type-action-snc'),
            document.getElementById('btn-toggle-types-action')
        ];

        filterControls.forEach(el => {
            if (el) {
                el.disabled = meta.has_action_filter;
                if (meta.has_action_filter) {
                    el.style.opacity = '0.5';
                    el.style.cursor = 'not-allowed';
                } else {
                    el.style.opacity = '1';
                    el.style.cursor = '';
                }
            }
        });

        const activeSources = meta.sources || { point_ctrl: true, pej: true, pa: true, pve: true };
        const hasPointCtrl = activeSources.point_ctrl !== false;

        // Griser les résultats de contrôles
        const resFilter = document.getElementById('resultats-filter');
        if (resFilter) {
            resFilter.disabled = !hasPointCtrl;
            resFilter.style.opacity = hasPointCtrl ? '1' : '0.5';
            resFilter.style.cursor = hasPointCtrl ? '' : 'not-allowed';
        }

        const conformiteCard = document.getElementById('chart-conformite')?.closest('.card');
        if (conformiteCard) {
            conformiteCard.style.opacity = hasPointCtrl ? '1' : '0.3';
        }

        const statCards = {
            'point_ctrl': document.getElementById('val-controles')?.closest('.stat-card'),
            'pej': document.getElementById('val-pej')?.closest('.stat-card'),
            'pa': document.getElementById('val-pa')?.closest('.stat-card'),
            'pve': document.getElementById('val-pve')?.closest('.stat-card')
        };

        for (const [sourceKey, cardEl] of Object.entries(statCards)) {
            if (cardEl) {
                const isEnabled = activeSources[sourceKey] !== false;
                cardEl.style.opacity = isEnabled ? '1' : '0.3';
            }
        }

        // Bannière
        const banner = document.getElementById('profile-warning-banner');
        if (banner) {
            let warnings = [];
            if (meta.has_natinf_filter) {
                warnings.push("Ce profil cible un nombre restreint de procédures et verrouille la sélection des thèmes et actions.");
            }
            if (meta.has_custom_stats) warnings.push("Attention : l'affichage Web est simplifié. Reportez-vous au PDF pour les statistiques consolidées de ce profil.");

            // Logique PNF : Forcer l'échelle et bloquer le code géographique
            const pnfDeptContainer = document.getElementById('pnf-dept-container');
            const pnfAgentContainer = document.getElementById('pnf-agent-container');
            if (val === 'pnf') {
                if (selectEchelle) {
                    selectEchelle.value = 'pnf';
                    selectEchelle.disabled = true;
                }
                if (inputCode) {
                    inputCode.value = '';
                    inputCode.disabled = true;
                    inputCode.placeholder = 'Dép. 21 et 52';
                }
                if (btnToggleCodes) btnToggleCodes.disabled = true;
                if (pnfDeptContainer) pnfDeptContainer.classList.remove('hidden');
                if (pnfAgentContainer) pnfAgentContainer.classList.remove('hidden');
                warnings.push("Le périmètre géographique est verrouillé sur le Parc National de Forêts (Départements 21 et 52).");
            } else if (val === 'tub') {
                if (selectEchelle) {
                    // Optionnel : on peut garder "departement" affiché ou ajouter une option "tub" invisible
                    selectEchelle.value = 'departement'; // Laissons 'departement' en visuel, de toute façon c'est forcé côté serveur
                    selectEchelle.disabled = true;
                }
                if (inputCode) {
                    inputCode.value = '';
                    inputCode.disabled = true;
                    inputCode.placeholder = 'Zone TUB';
                }
                if (btnToggleCodes) btnToggleCodes.disabled = true;
                if (pnfDeptContainer) pnfDeptContainer.classList.add('hidden');
                if (pnfAgentContainer) pnfAgentContainer.classList.add('hidden');
                warnings.push("Le périmètre géographique est verrouillé sur la zone TUB (Risque, Infectée, Interdiction).");
            } else {
                if (selectEchelle) {
                    selectEchelle.disabled = false;
                    // Reset to default if it was pnf
                    if (selectEchelle.value === 'pnf') selectEchelle.value = 'departement';
                }
                if (inputCode) {
                    inputCode.disabled = selectEchelle.value === 'national';
                    inputCode.placeholder = selectEchelle.value === 'national' ? 'France entière' : 'Rechercher ou sélectionner...';
                }
                if (btnToggleCodes) btnToggleCodes.disabled = selectEchelle.value === 'national';
                if (pnfDeptContainer) pnfDeptContainer.classList.add('hidden');
                if (pnfAgentContainer) pnfAgentContainer.classList.add('hidden');
            }

            if (warnings.length > 0) {
                banner.innerHTML = warnings.join('<br>');
                banner.style.display = 'block';
            } else {
                banner.style.display = 'none';
            }
        }
    }

    // Stats Elements
    const valControles = document.getElementById('val-controles');
    const valPej = document.getElementById('val-pej');
    const valPa = document.getElementById('val-pa');
    const valPve = document.getElementById('val-pve');



    // Combobox Type Usager
    const inputUsager = document.getElementById('type-usager');
    const btnToggleUsagers = document.getElementById('btn-toggle-usagers');
    const usagersDropdown = document.getElementById('usagers-dropdown');

    // Combobox Domaines SNC
    const inputDomaineSNC = document.getElementById('domaine-snc');
    const btnToggleDomainesSNC = document.getElementById('btn-toggle-domaines-snc');
    const domainesSNCDropdown = document.getElementById('domaines-snc-dropdown');

    // Combobox Thèmes SNC
    const inputThemeSNC = document.getElementById('theme-snc');
    const btnToggleThemesSNC = document.getElementById('btn-toggle-themes-snc');
    const themesSNCDropdown = document.getElementById('themes-snc-dropdown');

    // Combobox Types d'action
    const inputTypeAction = document.getElementById('type-action-snc');
    const btnToggleTypesAction = document.getElementById('btn-toggle-types-action');
    const typesActionDropdown = document.getElementById('types-action-dropdown');


    const deptsList = [
        { value: "01", label: "01 - Ain" },
        { value: "02", label: "02 - Aisne" },
        { value: "03", label: "03 - Allier" },
        { value: "04", label: "04 - Alpes-de-Haute-Provence" },
        { value: "05", label: "05 - Hautes-Alpes" },
        { value: "06", label: "06 - Alpes-Maritimes" },
        { value: "07", label: "07 - Ardèche" },
        { value: "08", label: "08 - Ardennes" },
        { value: "09", label: "09 - Ariège" },
        { value: "10", label: "10 - Aube" },
        { value: "11", label: "11 - Aude" },
        { value: "12", label: "12 - Aveyron" },
        { value: "13", label: "13 - Bouches-du-Rhône" },
        { value: "14", label: "14 - Calvados" },
        { value: "15", label: "15 - Cantal" },
        { value: "16", label: "16 - Charente" },
        { value: "17", label: "17 - Charente-Maritime" },
        { value: "18", label: "18 - Cher" },
        { value: "19", label: "19 - Corrèze" },
        { value: "2A", label: "2A - Corse-du-Sud" },
        { value: "2B", label: "2B - Haute-Corse" },
        { value: "21", label: "21 - Côte-d'Or" },
        { value: "22", label: "22 - Côtes-d'Armor" },
        { value: "23", label: "23 - Creuse" },
        { value: "24", label: "24 - Dordogne" },
        { value: "25", label: "25 - Doubs" },
        { value: "26", label: "26 - Drôme" },
        { value: "27", label: "27 - Eure" },
        { value: "28", label: "28 - Eure-et-Loir" },
        { value: "29", label: "29 - Finistère" },
        { value: "30", label: "30 - Gard" },
        { value: "31", label: "31 - Haute-Garonne" },
        { value: "32", label: "32 - Gers" },
        { value: "33", label: "33 - Gironde" },
        { value: "34", label: "34 - Hérault" },
        { value: "35", label: "35 - Ille-et-Vilaine" },
        { value: "36", label: "36 - Indre" },
        { value: "37", label: "37 - Indre-et-Loire" },
        { value: "38", label: "38 - Isère" },
        { value: "39", label: "39 - Jura" },
        { value: "40", label: "40 - Landes" },
        { value: "41", label: "41 - Loir-et-Cher" },
        { value: "42", label: "42 - Loire" },
        { value: "43", label: "43 - Haute-Loire" },
        { value: "44", label: "44 - Loire-Atlantique" },
        { value: "45", label: "45 - Loiret" },
        { value: "46", label: "46 - Lot" },
        { value: "47", label: "47 - Lot-et-Garonne" },
        { value: "48", label: "48 - Lozère" },
        { value: "49", label: "49 - Maine-et-Loire" },
        { value: "50", label: "50 - Manche" },
        { value: "51", label: "51 - Marne" },
        { value: "52", label: "52 - Haute-Marne" },
        { value: "53", label: "53 - Mayenne" },
        { value: "54", label: "54 - Meurthe-et-Moselle" },
        { value: "55", label: "55 - Meuse" },
        { value: "56", label: "56 - Morbihan" },
        { value: "57", label: "57 - Moselle" },
        { value: "58", label: "58 - Nièvre" },
        { value: "59", label: "59 - Nord" },
        { value: "60", label: "60 - Oise" },
        { value: "61", label: "61 - Orne" },
        { value: "62", label: "62 - Pas-de-Calais" },
        { value: "63", label: "63 - Puy-de-Dôme" },
        { value: "64", label: "64 - Pyrénées-Atlantiques" },
        { value: "65", label: "65 - Hautes-Pyrénées" },
        { value: "66", label: "66 - Pyrénées-Orientales" },
        { value: "67", label: "67 - Bas-Rhin" },
        { value: "68", label: "68 - Haut-Rhin" },
        { value: "69", label: "69 - Rhône" },
        { value: "70", label: "70 - Haute-Saône" },
        { value: "71", label: "71 - Saône-et-Loire" },
        { value: "72", label: "72 - Sarthe" },
        { value: "73", label: "73 - Savoie" },
        { value: "74", label: "74 - Haute-Savoie" },
        { value: "75", label: "75 - Paris" },
        { value: "76", label: "76 - Seine-Maritime" },
        { value: "77", label: "77 - Seine-et-Marne" },
        { value: "78", label: "78 - Yvelines" },
        { value: "79", label: "79 - Deux-Sèvres" },
        { value: "80", label: "80 - Somme" },
        { value: "81", label: "81 - Tarn" },
        { value: "82", label: "82 - Tarn-et-Garonne" },
        { value: "83", label: "83 - Var" },
        { value: "84", label: "84 - Vaucluse" },
        { value: "85", label: "85 - Vendée" },
        { value: "86", label: "86 - Vienne" },
        { value: "87", label: "87 - Haute-Vienne" },
        { value: "88", label: "88 - Vosges" },
        { value: "89", label: "89 - Yonne" },
        { value: "90", label: "90 - Territoire de Belfort" },
        { value: "91", label: "91 - Essonne" },
        { value: "92", label: "92 - Hauts-de-Seine" },
        { value: "93", label: "93 - Seine-Saint-Denis" },
        { value: "94", label: "94 - Val-de-Marne" },
        { value: "95", label: "95 - Val-d'Oise" },
        { value: "971", label: "971 - Guadeloupe" },
        { value: "972", label: "972 - Martinique" },
        { value: "973", label: "973 - Guyane" },
        { value: "974", label: "974 - La Réunion" },
        { value: "976", label: "976 - Mayotte" }
    ];

    const regionsList = [
        { value: "r01", label: "r01 - Guadeloupe" },
        { value: "r02", label: "r02 - Martinique" },
        { value: "r03", label: "r03 - Guyane" },
        { value: "r04", label: "r04 - La Réunion" },
        { value: "r06", label: "r06 - Mayotte" },
        { value: "r11", label: "r11 - Île-de-France" },
        { value: "r24", label: "r24 - Centre-Val de Loire" },
        { value: "r27", label: "r27 - Bourgogne-Franche-Comté" },
        { value: "r28", label: "r28 - Normandie" },
        { value: "r32", label: "r32 - Hauts-de-France" },
        { value: "r44", label: "r44 - Grand Est" },
        { value: "r52", label: "r52 - Pays de la Loire" },
        { value: "r53", label: "r53 - Bretagne" },
        { value: "r75", label: "r75 - Nouvelle-Aquitaine" },
        { value: "r76", label: "r76 - Occitanie" },
        { value: "r84", label: "r84 - Auvergne-Rhône-Alpes" },
        { value: "r93", label: "r93 - Provence-Alpes-Côte d'Azur" },
        { value: "r94", label: "r94 - Corse" }
    ];

    const bmisList = [
        { value: "BMI-NEC", label: "BMI-NEC - BMI Pôle Nord Est Centre" },
        { value: "BMI-SO", label: "BMI-SO - BMI Pôle Sud Ouest" },
        { value: "BMI-SE", label: "BMI-SE - BMI Pôle Sud-Est" },
        { value: "BMI-NO", label: "BMI-NO - BMI Pôle Nord Ouest" },
        { value: "BMI-IFE", label: "BMI-IFE - BMI-IFE" },
        { value: "BMI-IFO", label: "BMI-IFO - BMI-IFO" },
        { value: "BMI-TIP", label: "BMI-TIP - BMI-TIP" }
    ];

    const nationalList = [
        { value: "FR", label: "FR - France (National)" }
    ];

    const usagersList = [
        { value: "", label: "Tous les types d'usagers" },
        { value: "Particulier (usager de la nature + gestionnaire d'une propriété)", label: "Particulier (usager de la nature + gestionnaire d'une propriété)" },
        { value: "Agriculteur et autres acteurs agricoles", label: "Agriculteur et autres acteurs agricoles" },
        { value: "Collectivité", label: "Collectivité" },
        { value: "Entreprise", label: "Entreprise" },
        { value: "Acteurs sylvicoles", label: "Acteurs sylvicoles" },
        { value: "Autre", label: "Autre" }
    ];

    const domainesSNCList = [
        { value: "", label: "Tous les domaines" },
        { value: "Sujets transversaux", label: "Sujets transversaux" },
        { value: "Gestion qualitative de la ressource en eau", label: "Gestion qualitative de la ressource en eau" },
        { value: "Gestion quantitative de l'eau", label: "Gestion quantitative de l'eau" },
        { value: "Assurer la protection des espèces animales et végétales", label: "Assurer la protection des espèces animales et végétales" },
        { value: "Préservation des milieux aquatiques", label: "Préservation des milieux aquatiques" },
        { value: "Espaces protégés et protection des milieux et du cadre de vie", label: "Espaces protégés et protection des milieux et du cadre de vie" },
        { value: "Sécurité publique et Prévention des inondations", label: "Sécurité publique et Prévention des inondations" }
    ];

    const themesSNCList = [
        { value: "", label: "Tous les thèmes" },
        { value: "Autorisations environnementales", label: "Autorisations environnementales" },
        { value: "Lutter contre les pollutions urbaines", label: "Lutter contre les pollutions urbaines" },
        { value: "Pollutions diffuses", label: "Pollutions diffuses" },
        { value: "Gestion des eaux pluviales", label: "Gestion des eaux pluviales" },
        { value: "Autres actions liées à la gestion qualitative", label: "Autres actions liées à la gestion qualitative" },
        { value: "Ouvrages et autorisations de prélèvement (SNC 3.1)", label: "Ouvrages et autorisations de prélèvement (SNC 3.1)" },
        { value: "Contrôles sécheresse (SNC 3.2)", label: "Contrôles sécheresse (SNC 3.2)" },
        { value: "Autres contrôles gestion quantitative hors SNC", label: "Autres contrôles gestion quantitative hors SNC" },
        { value: "Faune sauvage captive", label: "Faune sauvage captive" },
        { value: "Espèces protégées", label: "Espèces protégées" },
        { value: "Espèces exotiques envahissantes", label: "Espèces exotiques envahissantes" },
        { value: "Chasse", label: "Chasse" },
        { value: "Pêche", label: "Pêche" },
        { value: "Continuité écologique des cours d'eau (SNC 5.2)", label: "Continuité écologique des cours d'eau (SNC 5.2)" },
        { value: "Plans d'eau", label: "Plans d'eau" },
        { value: "Travaux", label: "Travaux" },
        { value: "Contrôles aires protégées (SNC 5.1)", label: "Contrôles aires protégées (SNC 5.1)" },
        { value: "Sites inscrits ou classés (SNC 5.3)", label: "Sites inscrits ou classés (SNC 5.3)" },
        { value: "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", label: "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)" },
        { value: "Sécurité des ouvrages hydrauliques (SNC 6.1)", label: "Sécurité des ouvrages hydrauliques (SNC 6.1)" }
    ];

    const typesActionList = [
        { value: "", label: "Tous les types d'action" },
        { value: "Contrôle des autorisations environnementales délivrées (déroulement des travaux, prescriptions de fonctionnement, compensations... (SNC 1.1))", label: "Contrôle des autorisations environnementales (SNC 1.1)" },
        { value: "Préserver la qualité des milieux aquatiques et la santé grâce à des systèmes d'assainissement conformes (SNC 2.1)", label: "Systèmes d'assainissement conformes (SNC 2.1)" },
        { value: "Éviter la pollution des milieux par des épandages de boues d'épuration mal maîtrisés ou sauvages (SNC 2.2)", label: "Épandages de boues d'épuration (SNC 2.2)" },
        { value: "Préserver la qualité des milieux aquatiques et la santé grâce à une gestion durable des eaux pluviales (SNC 2.3)", label: "Eaux pluviales (SNC 2.3)" },
        { value: "Limiter la présence de nitrates d'origine agricole dans les milieux aquatiques afin de lutter contre l'eutrophisation des milieux et protéger la ressource en eau destinée à la consommation humaine (SNC 2.4)", label: "Nitrates agricoles (SNC 2.4)" },
        { value: "Assurer le respect des conditions d'emplois des produits phytopharmaceutiques afin de préserver la qualité de l'eau et des milieux aquatiques (SNC 2.5)", label: "Produits phytopharmaceutiques (SNC 2.5)" },
        { value: "ICPE avec rejets aqueux (hors SNC)", label: "ICPE avec rejets aqueux (hors SNC)" },
        { value: "Autres actions liées à la gestion qualitative", label: "Autres actions liées à la gestion qualitative" },
        { value: "Contrôles gestion quantitative sur IOTA (hors AUP) (SNC 3.1)", label: "IOTA hors AUP (SNC 3.1)" },
        { value: "Contrôles bureau des prélèvements dans le cadre d'une AUP (SNC 3.1)", label: "Prélèvements AUP (SNC 3.1)" },
        { value: "Contrôles sur ICPE (SNC 3.1)", label: "ICPE (SNC 3.1)" },
        { value: "Faire respecter les contraintes de prélèvements en période de sécheresse pour assurer les usages prioritaires de l'eau (SNC 3.2)", label: "Sécheresse – prélèvements (SNC 3.2)" },
        { value: "Autres contrôles gestion quantitative hors SNC", label: "Autres contrôles gestion quantitative hors SNC" },
        { value: "Assurer le respect de la réglementation par les établissements détenant de la faune sauvage captive (SNC 4.1)", label: "Faune sauvage captive (SNC 4.1)" },
        { value: "Assurer le respect de la bonne mise en œuvre des mesures ERC des projets d'aménagement soumis à autorisation dans les milieux naturels à enjeux et ceux relatifs à une dérogation espèces protégées (SNC 4.2)", label: "Mesures ERC espèces protégées (SNC 4.2)" },
        { value: "Espèces protégées : destructions ou perturbations d'espèces protégées, altération, dégradation et destruction d'habitat (SNC 4.3)", label: "Destructions/perturbations espèces protégées (SNC 4.3)" },
        { value: "Contrôles liés à la détention et commerce illégaux d'espèces protégées ou réglementées CITES (SNC 4.3)", label: "Détention/commerce illégal CITES (SNC 4.3)" },
        { value: "Dérogations espèces protégées délivrées à des fins de recherche, à but scientifique, à des fins d'inventaire ou portant autorisations de prélèvements (SNC 4.3)", label: "Dérogations espèces protégées – recherche (SNC 4.3)" },
        { value: "Autres actions relevant de la protection des espèces animales et végétales (hors SNC et hors chasse)", label: "Autres actions protection espèces (hors SNC)" },
        { value: "Prévenir la propagation sur les territoires métropolitains et ultramarins des espèces exotiques envahissantes (SNC 4.4)", label: "Espèces exotiques envahissantes (SNC 4.4)" },
        { value: "Sécurité à la chasse (SNC 4.5)", label: "Sécurité à la chasse (SNC 4.5)" },
        { value: "Contrôle du respect des quotas collectifs et des obligations de déclaration de prélèvement de certaines espèces (SNC 4.5)", label: "Quotas collectifs chasse (SNC 4.5)" },
        { value: "Contrôle des conditions d'exercice ou d'interdiction des chasses traditionnelles (SNC 4.5)", label: "Chasses traditionnelles (SNC 4.5)" },
        { value: "Contrôle de l'emploi et du port de grenaille de plomb en zone humide (SNC 4.5)", label: "Grenaille de plomb zone humide (SNC 4.5)" },
        { value: "Actions contrôles chasse hors priorités SNC", label: "Actions chasse hors priorités SNC" },
        { value: "Actions de contrôle de la pêche (hors SNC)", label: "Contrôle pêche (hors SNC)" },
        { value: "Assurer la continuité écologique des cours d'eau (SNC 5.2)", label: "Continuité écologique cours d'eau (SNC 5.2)" },
        { value: "Contrôle de la création de nouveaux plans d'eau et des plans d'eaux existants (hors contrôles d'une autorisation environnementale et hors présence d'une espèce protégée)", label: "Plans d'eau (hors AE et hors EP)" },
        { value: "Travaux en cours d'eau et remblais (hors contrôles d'une autorisation environnementale et hors présence d'une espèce portégée)", label: "Travaux en cours d'eau et remblais" },
        { value: "Travaux en zones humides (hors contrôles d'une autorisation environnementale et hors présence d'une espèce protégée )", label: "Travaux en zones humides" },
        { value: "Réglementations parc national (SNC 5.1)", label: "Réglementations parc national (SNC 5.1)" },
        { value: "Réglementation réserves naturelles (SNC 5.1)", label: "Réglementation réserves naturelles (SNC 5.1)" },
        { value: "Contrôles APB (SNC 5.1)", label: "Contrôles APB (SNC 5.1)" },
        { value: "Contrôles APG (SNC 5.1)", label: "Contrôles APG (SNC 5.1)" },
        { value: "Terrains conservatoire du littoral (SNC 5.1)", label: "Terrains conservatoire du littoral (SNC 5.1)" },
        { value: "N 2000 Contrôle de l'existence préalable d'une évaluation d'incidence et contrôle des mesures et prescriptions (SNC 5.1)", label: "Natura 2000 – évaluation d'incidence (SNC 5.1)" },
        { value: "Autres aires protégées (SNC 5.1)", label: "Autres aires protégées (SNC 5.1)" },
        { value: "Assurer la protection des sites inscrits et classés en exerçant la police des sites (SNC 5.3)", label: "Sites inscrits et classés (SNC 5.3)" },
        { value: "Contrôles espaces protégés et protection des milieux et cadre de vie (hors SNC)", label: "Contrôles espaces protégés (hors SNC)" },
        { value: "Neutralisation des digues (SNC 6.1)", label: "Neutralisation des digues (SNC 6.1)" }
    ];

    function getActiveCodesList() {
        const scale = selectEchelle.value;
        if (scale === 'departement') return deptsList;
        if (scale === 'region') return regionsList;
        if (scale === 'bmi') return bmisList;
        if (scale === 'national') return nationalList;
        return [];
    }

    function splitLabel(str, maxLen = 25) {
        if (!str) return [];
        if (str.length <= maxLen) return [str];
        const words = str.split(' ');
        const lines = [];
        let currentLine = '';
        words.forEach(word => {
            if ((currentLine + ' ' + word).trim().length <= maxLen) {
                currentLine = (currentLine + ' ' + word).trim();
            } else {
                if (currentLine) lines.push(currentLine);
                currentLine = word;
            }
        });
        if (currentLine) lines.push(currentLine);
        return lines;
    }

    function setupCombobox(inputEl, toggleBtn, dropdownEl, getListDataFn, isMultiSelect = false) {
        let selectedValues = [];

        inputEl.getSelectedValues = () => selectedValues;
        inputEl.setSelectedValues = (vals) => {
            selectedValues = vals || [];
            updateInputDisplay();
        };

        function updateInputDisplay() {
            const listData = getListDataFn();
            const selectedLabels = selectedValues
                .map(val => {
                    const found = listData.find(d => d.value === val);
                    return found ? found.label : val;
                })
                .filter(Boolean);

            if (isMultiSelect) {
                if (selectedValues.length === 0) {
                    inputEl.value = '';
                    inputEl.placeholder = inputEl.dataset.placeholder || inputEl.placeholder;
                } else if (selectedValues.length === 1) {
                    inputEl.value = selectedLabels[0];
                } else {
                    inputEl.value = `${selectedValues.length} sélectionnés`;
                }
            } else {
                inputEl.value = selectedValues[0] || '';
            }
        }

        function render(filterText = '') {
            dropdownEl.innerHTML = '';
            const search = normalizeStr(filterText.trim());
            const listData = getListDataFn();
            const filtered = listData.filter(p =>
                normalizeStr(p.label).includes(search) || normalizeStr(p.value).includes(search)
            );

            if (filtered.length === 0) {
                const noRes = document.createElement('div');
                noRes.className = 'dropdown-option-empty';
                // Multi-codes : virgule dans la saisie → mode comparaison spatiale, pas d'erreur
                noRes.textContent = filterText.includes(',') ? '✦ Mode comparaison spatiale' : 'Aucun élément trouvé';
                dropdownEl.appendChild(noRes);
                return;
            }

            filtered.forEach(p => {
                const opt = document.createElement('div');
                opt.className = 'dropdown-option';
                opt.style.display = 'flex';
                opt.style.alignItems = 'center';
                opt.style.gap = '8px';
                opt.dataset.value = p.value;

                if (isMultiSelect && p.value !== "") {
                    const chk = document.createElement('input');
                    chk.type = 'checkbox';
                    chk.checked = selectedValues.includes(p.value);
                    chk.style.margin = '0';
                    chk.addEventListener('click', (e) => {
                        e.stopPropagation();
                        toggleValue(p.value, chk.checked);
                    });
                    opt.appendChild(chk);

                    const labelSpan = document.createElement('span');
                    labelSpan.textContent = p.label;
                    opt.appendChild(labelSpan);

                    opt.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const nextState = !chk.checked;
                        chk.checked = nextState;
                        toggleValue(p.value, nextState);
                    });
                } else {
                    opt.textContent = p.label;
                    opt.addEventListener('click', () => {
                        if (isMultiSelect) {
                            // C'est l'option "Tous" (vide)
                            selectedValues = [];
                            updateInputDisplay();
                            dropdownEl.classList.add('hidden');
                        } else {
                            selectedValues = [p.value];
                            inputEl.value = p.value;
                            dropdownEl.classList.add('hidden');
                        }
                    });
                }
                dropdownEl.appendChild(opt);
            });
        }

        function toggleValue(val, isChecked) {
            if (isChecked) {
                if (!selectedValues.includes(val)) {
                    selectedValues.push(val);
                }
            } else {
                selectedValues = selectedValues.filter(v => v !== val);
            }
            updateInputDisplay();
        }

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isHidden = dropdownEl.classList.contains('hidden');
            if (isHidden) {
                document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
                render();
                dropdownEl.classList.remove('hidden');
                if (!isMultiSelect) inputEl.focus();
            } else {
                dropdownEl.classList.add('hidden');
                updateInputDisplay();
            }
        });

        inputEl.addEventListener('input', () => {
            render(inputEl.value);
            dropdownEl.classList.remove('hidden');
        });

        inputEl.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
            render(isMultiSelect ? '' : inputEl.value);
            dropdownEl.classList.remove('hidden');
        });

        inputEl.dataset.placeholder = inputEl.placeholder;
    }

    const resultatsList = [
        { value: "", label: "Tous les résultats" },
        { value: "Conforme", label: "Conforme" },
        { value: "Non-conforme", label: "Non-conforme" },
        { value: "En attente", label: "En attente" }
    ];

    const inputResultat = document.getElementById('resultat-select');
    const btnToggleResultats = document.getElementById('btn-toggle-resultats');
    const resultatsDropdown = document.getElementById('resultats-dropdown');
    const inputCommune = document.getElementById('filter-commune');

    // Initialisation des comboboxes
    setupCombobox(inputCode, btnToggleCodes, codesDropdown, getActiveCodesList, false);

    /**
     * Retourne un tableau des codes géographiques saisis (séparés par virgule).
     * Ex: "21, 25" → ["21", "25"] | "r27" → ["r27"]
     */
    function getParsedCodes() {
        const raw = (inputCode.value || '').trim();
        if (!raw) return [];
        return raw.split(',').map(c => c.trim()).filter(c => c.length > 0);
    }

    setupCombobox(inputUsager, btnToggleUsagers, usagersDropdown, () => usagersList, true);
    setupCombobox(inputDomaineSNC, btnToggleDomainesSNC, domainesSNCDropdown, () => domainesSNCList, true);
    setupCombobox(inputThemeSNC, btnToggleThemesSNC, themesSNCDropdown, () => themesSNCList, true);
    setupCombobox(inputTypeAction, btnToggleTypesAction, typesActionDropdown, () => typesActionList, true);
    setupCombobox(inputResultat, btnToggleResultats, resultatsDropdown, () => resultatsList, true);

    // Hide dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-container')) {
            document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
        }
    });

    selectEchelle.addEventListener('change', () => {
        const val = selectEchelle.value;

        inputCode.disabled = false;
        if (btnToggleCodes) btnToggleCodes.disabled = false;

        if (val === 'departement') {
            inputCode.value = '21';
            inputCode.placeholder = 'ex : 21';
            codeHelper.textContent = 'Exemples : 21, 27, 39';
        } else if (val === 'region') {
            inputCode.value = 'r27';
            inputCode.placeholder = 'ex : r27';
            codeHelper.textContent = 'Exemples : r27, r44';
        } else if (val === 'bmi') {
            inputCode.value = 'BMI-NEC';
            inputCode.placeholder = 'ex : BMI-NEC';
            codeHelper.textContent = 'Codes possibles : BMI-NEC, BMI-SO, BMI-SE, BMI-NO, BMI-IFE, BMI-IFO, BMI-TIP';
        } else if (val === 'national') {
            inputCode.value = '';
            inputCode.placeholder = 'France entière';
            codeHelper.textContent = 'Échelle nationale sélectionnée';
            inputCode.disabled = true;
            if (btnToggleCodes) btnToggleCodes.disabled = true;
        }
    });

    // --- LEAFLET MAP INITIALIZATION ---
    // France Center
    const map = L.map('map', {
        preferCanvas: true,
        zoomSnap: 0.25,
        zoomDelta: 0.25,
        wheelPxPerZoomLevel: 120
    }).setView([46.2276, 2.2137], 6);

    // Panes d'empilement z-index pour garantir que le masque laiteux est au-dessus des tuiles IGN (410) et les entités au-dessus du masque (650)
    const maskPane = map.createPane('maskPane');
    maskPane.style.zIndex = '410';
    maskPane.style.pointerEvents = 'none';

    const choroplethPane = map.createPane('choroplethPane');
    choroplethPane.style.zIndex = '420';

    const entityMarkersPane = map.createPane('entityMarkersPane');
    entityMarkersPane.style.zIndex = '650';

    const maskRenderer = L.canvas({ pane: 'maskPane' });
    const choroplethRenderer = L.svg({ pane: 'choroplethPane' });
    const entityRenderer = L.canvas({ pane: 'entityMarkersPane' });

    L.tileLayer('https://data.geopf.fr/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.ign.fr/">IGN</a>'
    }).addTo(map);

    // Helper to calculate dynamic heatmap Max based on current viewport visible points
    const HEATMAP_GRADIENT = {
        0.2: 'blue',
        0.45: 'lime',
        0.7: 'yellow',
        0.88: 'orange',
        0.95: 'red'
    };

    function getDynamicMaxForZoom(mapInstance, heatPoints, radiusPx) {
        if (!heatPoints || heatPoints.length === 0) return 1.0;
        const currentZoom = mapInstance.getZoom();
        const bounds = mapInstance.getBounds();
        
        // Uniquement les points visibles dans le champ de vision actuel
        const visiblePoints = heatPoints.filter(pt => bounds.contains([pt[0], pt[1]]));
        const pointsToProcess = visiblePoints.length > 0 ? visiblePoints : heatPoints;

        const grid = {};
        let maxCount = 1;
        const cellSize = radiusPx / 2;
        pointsToProcess.forEach(pt => {
            const p = mapInstance.project([pt[0], pt[1]], currentZoom);
            const gx = Math.floor(p.x / cellSize);
            const gy = Math.floor(p.y / cellSize);
            const key = gx + ',' + gy;
            grid[key] = (grid[key] || 0) + 1;
            if (grid[key] > maxCount) maxCount = grid[key];
        });
        return Math.max(1.0, maxCount);
    }

    window.updateClusterOffset = function(zoom) {
        if (typeof zoom === 'undefined') {
            zoom = map.getZoom();
        }
        const useOffset = localStorage.getItem('ui_cluster_offset') !== 'false';
        const zoomThreshold = parseInt(localStorage.getItem('ui_cluster_zoom')) || 10;
        const container = map.getContainer();
        if (useOffset && zoom >= zoomThreshold) {
            container.classList.add('cluster-offset-active');
        } else {
            container.classList.remove('cluster-offset-active');
        }
    };

    map.on('zoomend moveend', function () {
        const currentZoom = map.getZoom();
        window.updateClusterOffset(currentZoom);

        if (typeof heatmapLayer !== 'undefined' && heatmapLayer && document.querySelector('input[name="map-mode"]:checked')?.value === 'heatmap') {
            const hData = [...activePoints, ...activeProcedures]
                .map(pt => [parseFloat(pt.y), parseFloat(pt.x), 1.0])
                .filter(coords => !isNaN(coords[0]) && !isNaN(coords[1]) && coords[0] !== 0 && coords[1] !== 0);
            const newMax = getDynamicMaxForZoom(map, hData, 25);
            heatmapLayer.setOptions({
                max: newMax,
                maxZoom: currentZoom,
                gradient: HEATMAP_GRADIENT
            });
        }
    });

    // Application des paramètres (Code Géo, Thème, Zoom...) après init de la map
    fetch('/api/settings').then(res => res.json()).then(settings => {
        if (settings.geo && settings.geo.code_geo_defaut) {
            const code = settings.geo.code_geo_defaut.toLowerCase();
            if (code === 'fr') selectEchelle.value = 'national';
            else if (code.startsWith('r')) selectEchelle.value = 'region';
            else if (code.startsWith('bmi')) selectEchelle.value = 'bmi';
            else selectEchelle.value = 'departement';

            selectEchelle.dispatchEvent(new Event('change'));
            if (selectEchelle.value !== 'national') {
                inputCode.value = settings.geo.code_geo_defaut;
            }
        }

        if (settings.geo && settings.geo.annee_reference) {
            const refYear = settings.geo.annee_reference;
            const mo = String(now.getMonth() + 1).padStart(2, '0');
            const da = String(now.getDate()).padStart(2, '0');
            if (dateDebEl) dateDebEl.value = `${refYear}-01-01`;
            if (dateFinEl) dateFinEl.value = `${refYear}-${mo}-${da}`;

            if (compareDateDebEl && compareDateFinEl) {
                const lastYear = refYear - 1;
                compareDateDebEl.value = `${lastYear}-01-01`;
                compareDateFinEl.value = `${lastYear}-${mo}-${da}`;
            }
        }

        if (settings.ui && settings.ui.zoom_defaut) {
            map.setZoom(settings.ui.zoom_defaut);
        }

        if (settings.ui && settings.ui.theme === "sombre") {
            document.body.classList.add("theme-sombre");
        }
    }).catch(e => console.warn("Paramètres non appliqués:", e)).finally(() => {
        // Chargement initial
        const stateFromURL = loadStateFromURL();
        const stateFromLS = loadStateFromLocalStorage();

        if (stateFromURL) {
            applyFiltersState(stateFromURL);
        } else if (stateFromLS) {
            applyFiltersState(stateFromLS);
        }

        if (typeof window.updateClusterOffset === 'function') {
            window.updateClusterOffset(map.getZoom());
        }

        loadData();
    });

    const markersGroup = L.layerGroup();

    /**
     * Clustering cloisonné par territoire administratif.
     * clusterParent : FeatureGroup parent ajouté à la carte (visible dans le contrôle des couches).
     * clustersByTerritory : Map JS { clé_territoire -> L.markerClusterGroup }
     * Idem pour PEJ, PA, PVe.
     */
    const clusterParent = L.featureGroup().addTo(map);
    const pejParent = L.featureGroup().addTo(map);
    const paParent = L.featureGroup().addTo(map);
    const pveParent = L.featureGroup().addTo(map);

    let clustersByTerritory = new Map();
    let pejByTerritory = new Map();
    let paByTerritory = new Map();
    let pveByTerritory = new Map();

    // FeatureGroups et Maps pour la période N-1 (séparés pour ne jamais fusionner avec N)
    const clusterParentN1 = L.featureGroup().addTo(map);
    const pejParentN1 = L.featureGroup().addTo(map);
    const paParentN1 = L.featureGroup().addTo(map);
    const pveParentN1 = L.featureGroup().addTo(map);

    let clustersByTerritoryN1 = new Map();
    let pejByTerritoryN1 = new Map();
    let paByTerritoryN1 = new Map();
    let pveByTerritoryN1 = new Map();

    // Options réutilisées pour chaque sous-groupe de clusters
    const baseClusterOpts = {
        chunkedLoading: true,
        disableClusteringAtZoom: 14,
        maxClusterRadius: function (zoom) { return (zoom < 8) ? 80 : (zoom < 11) ? 50 : 30; }
    };

    const clusterShades = {
        '#10B981': ['#10B981', '#059669', '#047857'], // Green (Conforme)
        '#EF4444': ['#EF4444', '#DC2626', '#B91C1C'], // Red (Infraction)
        '#64748B': ['#64748B', '#475569', '#334155'], // Grey (Attente)
        '#3B82F6': ['#3B82F6', '#2563EB', '#1D4ED8'], // Blue (PEJ)
        '#8B5CF6': ['#8B5CF6', '#7C3AED', '#6D28D9'], // Purple (PA)
        '#F97316': ['#F97316', '#EA580C', '#C2410C']  // Orange (PVe)
    };

    function getDynamicClusterOpts(baseHex, isN1, customClass = '') {
        return {
            ...baseClusterOpts,
            iconCreateFunction: function (cluster) {
                const count = cluster.getChildCount();
                let shades = clusterShades[baseHex.toUpperCase()] || [baseHex, baseHex, baseHex];
                let shade = shades[0];
                if (count >= 50) shade = shades[2];
                else if (count >= 10) shade = shades[1];

                if (isN1) {
                    return L.divIcon({
                        html: `<div class="${customClass}" style="background-color:${shade};opacity:0.75;border:2px dashed rgba(255,255,255,0.8);border-radius:50%;text-align:center;color:white;font-weight:bold;line-height:26px;width:28px;height:28px;box-shadow:none;">${count}</div>`,
                        className: '',
                        iconSize: [28, 28]
                    });
                } else {
                    return L.divIcon({
                        html: `<div class="${customClass}" style="background-color:${shade};border:2px solid white;border-radius:50%;text-align:center;color:white;font-weight:bold;line-height:26px;width:30px;height:30px;box-shadow: 0 1px 3px rgba(0,0,0,0.3);">${count}</div>`,
                        className: '',
                        iconSize: [30, 30]
                    });
                }
            }
        };
    }

    /**
     * Normalise un code département brut en chaîne 2 chars (ou 3 pour DOM/TOM, 2A/2B).
     * Retourne null si la valeur est absente, vide ou non exploitable.
     */
    function normalizeDeptCode(raw) {
        if (raw === null || raw === undefined) return null;
        let s = String(raw).trim();
        // Nettoyer suffixe float (ex: "25.0")
        if (/^\d+\.0*$/.test(s)) s = s.split('.')[0];
        if (!s || s === 'nan' || s === 'None' || s === '') return null;
        // DOM/TOM (3 chiffres) ou alphanumérique (2A, 2B)
        if (/^\d{3}$/.test(s)) return s;
        if (/^2[AB]$/i.test(s)) return s.toUpperCase();
        // Cas standard : forcer 2 chiffres
        if (/^\d{1,2}$/.test(s)) return s.padStart(2, '0');
        return null; // format inconnu
    }

    /**
     * Retourne la clé de territoire stricte pour le cloisonnement.
     * - échelle 'region' ou 'national' : code région INSEE (depuis DEPT_TO_REG)
     * - toute autre échelle (département, pnf, bmi) : code département normalisé
     * - absence de territoire valide : bucket '_fallback' unique (jamais de crash Leaflet)
     */
    function getTerritoryKey(codeDeptRaw) {
        const normalized = normalizeDeptCode(codeDeptRaw);
        if (!normalized) return '_fallback';
        return 'dept_' + normalized;
    }

    /**
     * Récupère ou crée le L.markerClusterGroup pour une clé territoire et un parent donnés.
     */
    function getOrCreateCluster(key, parentFG, byTerritoryMap, extraOpts = {}) {
        if (!byTerritoryMap.has(key)) {
            const grp = L.markerClusterGroup({ clusterPane: 'entityMarkersPane', ...baseClusterOpts, ...extraOpts });
            parentFG.addLayer(grp);
            byTerritoryMap.set(key, grp);
        }
        return byTerritoryMap.get(key);
    }

    /**
     * Vide et supprime de la carte tous les sous-groupes d'une Map de clusters.
     */
    function clearTerritoryMap(parentFG, byTerritoryMap) {
        byTerritoryMap.forEach(grp => {
            grp.clearLayers();
            parentFG.removeLayer(grp);
        });
        byTerritoryMap.clear();
    }

    let heatmapLayer = null;
    let choroplethLayer = null;
    let currentBoundaryGeojson = null;
    window.isChoroplethLegendCollapsed = false;

    window.toggleChoroplethLegend = function(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        window.isChoroplethLegendCollapsed = !window.isChoroplethLegendCollapsed;
        const body = document.getElementById('choropleth-legend-body');
        const btn = document.getElementById('choropleth-legend-toggle');
        if (body) body.style.display = window.isChoroplethLegendCollapsed ? 'none' : 'block';
        if (btn) {
            btn.textContent = window.isChoroplethLegendCollapsed ? '▲' : '▼';
            btn.title = window.isChoroplethLegendCollapsed ? 'Déplier la légende' : 'Réduire la légende';
        }
    };

    function renderChoroplethLayer() {
        const isChoroplethMode = document.querySelector('input[name="map-mode"]:checked')?.value === 'choropleth';
        const choroplethOptions = document.getElementById('choropleth-options');
        const legendContainer = document.getElementById('choropleth-legend');

        if (typeof updateLegend === 'function') updateLegend();

        if (choroplethOptions) {
            choroplethOptions.classList.toggle('hidden', !isChoroplethMode);
        }

        if (!isChoroplethMode) {
            if (choroplethLayer) {
                map.removeLayer(choroplethLayer);
                choroplethLayer = null;
            }
            if (legendContainer) legendContainer.classList.add('hidden');
            return;
        }

        if (legendContainer) legendContainer.classList.remove('hidden');

        const metric = document.getElementById('choropleth-metric')?.value || 'controles';
        const isControles = (metric === 'controles');

        if (choroplethLayer) {
            map.removeLayer(choroplethLayer);
            choroplethLayer = null;
        }

        if (!currentBoundaryGeojson || !currentBoundaryGeojson.features || currentBoundaryGeojson.features.length === 0) {
            sendClientLog('WARN', 'Carte choroplèthe non affichée: Aucune entité GeoJSON reçue du serveur pour la zone actuelle', 'explorer.js', 'renderChoroplethLayer');
            if (legendContainer) legendContainer.classList.add('hidden');
            return;
        }

        sendClientLog('INFO', `Diagnostic Carte Choroplèthe: ${currentBoundaryGeojson.features.length} entité(s) GeoJSON chargées (Métrique: ${metric})`, 'explorer.js', 'renderChoroplethLayer');

        function fixUtf8Encoding(str) {
            if (!str || typeof str !== 'string') return str || '';
            if (str.includes('Ã') || str.includes('Â')) {
                try {
                    return decodeURIComponent(escape(str));
                } catch (e) {
                    return str;
                }
            }
            return str;
        }

        function normCode(str) {
            if (str === null || str === undefined) return '';
            let s = str.toString().trim().toUpperCase();
            if (s.length === 1 && !isNaN(s)) s = '0' + s;
            if (s.length === 4 && !isNaN(s)) s = '0' + s;
            return s;
        }

        const entityCounts = new Map();
        const entityDetails = new Map();
        let unmappedProceduresCount = 0;

        currentBoundaryGeojson.features.forEach((feature, idx) => {
            const props = feature.properties || {};
            const codeDept = normCode(props.code_dept || props.insee_dep || props.INSEE_DEP || props.code_dep || props.dep);
            const codeInsee = normCode(props.code_insee || props.CODE_INSEE || props.insee_comm || props.insee_com || props.INSEE_COM || props.INSEE_COMM || props.com || props.insee || props.INSEE || props.insee_com_m);
            const rawNom = props.nom_comm || props.nom_dept || props.NOM_DEP || props.NOM_COM || props.nom || props.insee_dep || `Zone ${idx + 1}`;
            const nom = fixUtf8Encoding(rawNom);

            const featureKey = codeInsee || codeDept || `feat_${idx}`;
            entityCounts.set(featureKey, 0);
            entityDetails.set(featureKey, {
                nom: nom,
                codeDept: codeDept,
                codeInsee: codeInsee,
                total: 0,
                pej: 0,
                pve: 0,
                controles: 0
            });
        });

        function pointInPolyRing(pt, ring) {
            const x = pt[0], y = pt[1];
            let inside = false;
            for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
                const xi = ring[i][0], yi = ring[i][1];
                const xj = ring[j][0], yj = ring[j][1];
                const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
                if (intersect) inside = !inside;
            }
            return inside;
        }

        function pointInFeatureGeom(pt, feature) {
            if (!feature || !feature.geometry) return false;
            const geom = feature.geometry;
            if (geom.type === 'Polygon') {
                return pointInPolyRing(pt, geom.coordinates[0]);
            } else if (geom.type === 'MultiPolygon') {
                return geom.coordinates.some(poly => pointInPolyRing(pt, poly[0]));
            }
            return false;
        }

        if (isControles) {
            (activePoints || []).forEach(pt => {
                if (isItemDynamicallyExcluded(pt, false)) return;
                if (['pej', 'pa', 'pve'].includes(activeKpiFilter)) return;
                if (activeKpiFilter && activeKpiFilter.startsWith('usager:')) {
                    const target = normalizeStr(activeKpiFilter.substring(7));
                    const cat = normalizeStr(getUsagerCategory(pt.type_usager));
                    if (!cat.includes(target) && !target.includes(cat)) return;
                }
                if (activeKpiFilter && activeKpiFilter.startsWith('resultat:')) {
                    const label = activeKpiFilter.substring(9).toLowerCase();
                    const res = (pt.resultat || '').toLowerCase();
                    if (label.includes('conforme') && !label.includes('non')) {
                        if (!res.includes('conforme') || res.includes('non')) return;
                    } else if (label.includes('non') || label.includes('infraction') || label.includes('manquement')) {
                        if (!res.includes('infraction') && !res.includes('non') && !res.includes('manquement')) return;
                    } else {
                        if (res.includes('conforme') || res.includes('infraction') || res.includes('non') || res.includes('manquement')) return;
                    }
                }

                const usagerCat = getUsagerCategory(pt.type_usager);
                if (currentMapMode === 'usagers') {
                    if (usagerLegendFilters[usagerCat] === false) return;
                } else {
                    const res = (pt.resultat || '').toLowerCase();
                    if (res.includes('conforme') && !res.includes('non')) {
                        if (legendFilters.ctrl_conforme === false) return;
                    } else if (res.includes('infraction') || res.includes('non') || res.includes('manquement')) {
                        if (legendFilters.ctrl_infraction === false) return;
                    } else {
                        if (legendFilters.ctrl_attente === false) return;
                    }
                }
                const rawDept = pt.code_dept || pt.insee_dep || (pt.code_insee ? pt.code_insee.toString().trim().substring(0, 2) : '');
                const ptDept = normCode(rawDept);
                const ptInsee = normCode(pt.code_insee || pt.insee_comm || pt.insee_com);

                let matched = false;
                for (const [key, details] of entityDetails.entries()) {
                    const matchInsee = details.codeInsee && ptInsee && details.codeInsee === ptInsee;
                    const matchDept = !details.codeInsee && details.codeDept && ptDept && details.codeDept === ptDept;
                    if (matchInsee || matchDept) {
                        details.controles++;
                        details.total++;
                        entityCounts.set(key, details.total);
                        matched = true;
                        break;
                    }
                }
                if (!matched) {
                    const px = parseFloat(pt.x), py = parseFloat(pt.y);
                    if (!isNaN(px) && !isNaN(py) && px !== 0 && py !== 0) {
                        for (let i = 0; i < currentBoundaryGeojson.features.length; i++) {
                            const feat = currentBoundaryGeojson.features[i];
                            if (pointInFeatureGeom([px, py], feat)) {
                                const props = feat.properties || {};
                                const codeDept = normCode(props.code_dept || props.insee_dep || props.INSEE_DEP || props.code_dep || props.dep);
                                const codeInsee = normCode(props.code_insee || props.CODE_INSEE || props.insee_comm || props.insee_com || props.INSEE_COM || props.INSEE_COMM || props.com || props.insee || props.INSEE || props.insee_com_m);
                                const key = codeInsee || codeDept || `feat_${i}`;
                                const details = entityDetails.get(key);
                                if (details) {
                                    details.controles++;
                                    details.total++;
                                    entityCounts.set(key, details.total);
                                    matched = true;
                                    break;
                                }
                            }
                        }
                    }
                }
            });
        } else {
            (activeProcedures || []).forEach(p => {
                if (isItemDynamicallyExcluded(p, true)) return;
                if (activeKpiFilter === 'controles') return;
                const ptype = (p.type || '').toUpperCase();
                if (!ptype.includes('PEJ') && !ptype.includes('PVE')) return;
                if (metric === 'pej' && !ptype.includes('PEJ')) return;
                if (metric === 'pve' && !ptype.includes('PVE')) return;
                if (activeKpiFilter === 'pej' && !ptype.includes('PEJ')) return;
                if (activeKpiFilter === 'pa' && !ptype.includes('PA')) return;
                if (activeKpiFilter === 'pve' && !ptype.includes('PVE')) return;
                if (activeKpiFilter && activeKpiFilter.startsWith('usager:')) {
                    const target = normalizeStr(activeKpiFilter.substring(7));
                    const cat = normalizeStr(getUsagerCategory(p.type_usager));
                    if (!cat.includes(target) && !target.includes(cat)) return;
                }
                if (currentMapMode === 'usagers') {
                    const cat = getUsagerCategory(p.type_usager);
                    if (usagerLegendFilters[cat] === false) return;
                }

                if (ptype.includes('PEJ') && legendFilters.pej === false) return;
                if (ptype.includes('PA') && legendFilters.pa === false) return;
                if (ptype.includes('PVE') && legendFilters.pve === false) return;

                const rawDept = p.code_dept || p.insee_dep || (p.code_insee ? p.code_insee.toString().trim().substring(0, 2) : '');
                const pDept = normCode(rawDept);
                const pInsee = normCode(p.code_insee || p.insee_comm || p.insee_com);

                let matched = false;
                for (const [key, details] of entityDetails.entries()) {
                    const matchInsee = details.codeInsee && pInsee && details.codeInsee === pInsee;
                    const matchDept = !details.codeInsee && details.codeDept && pDept && details.codeDept === pDept;
                    if (matchInsee || matchDept) {
                        details.total++;
                        if (ptype.includes('PEJ')) details.pej++;
                        if (ptype.includes('PVE')) details.pve++;
                        const valToSet = (metric === 'pej') ? details.pej : ((metric === 'pve') ? details.pve : (details.pej + details.pve));
                        entityCounts.set(key, valToSet);
                        matched = true;
                        break;
                    }
                }

                if (!matched) {
                    const px = parseFloat(p.x), py = parseFloat(p.y);
                    if (!isNaN(px) && !isNaN(py) && px !== 0 && py !== 0) {
                        for (let i = 0; i < currentBoundaryGeojson.features.length; i++) {
                            const feat = currentBoundaryGeojson.features[i];
                            if (pointInFeatureGeom([px, py], feat)) {
                                const props = feat.properties || {};
                                const codeDept = normCode(props.code_dept || props.insee_dep || props.INSEE_DEP || props.code_dep || props.dep);
                                const codeInsee = normCode(props.code_insee || props.CODE_INSEE || props.insee_comm || props.insee_com || props.INSEE_COM || props.INSEE_COMM || props.com || props.insee || props.INSEE || props.insee_com_m);
                                const key = codeInsee || codeDept || `feat_${i}`;
                                const details = entityDetails.get(key);
                                if (details) {
                                    details.total++;
                                    if (ptype.includes('PEJ')) details.pej++;
                                    if (ptype.includes('PVE')) details.pve++;
                                    const valToSet = (metric === 'pej') ? details.pej : ((metric === 'pve') ? details.pve : (details.pej + details.pve));
                                    entityCounts.set(key, valToSet);
                                    matched = true;
                                    break;
                                }
                            }
                        }
                    }
                }

                if (!matched) {
                    unmappedProceduresCount++;
                }
            });
        }

        const counts = Array.from(entityCounts.values());
        const nonZeroCounts = counts.filter(c => c > 0).sort((a, b) => a - b);
        const maxVal = nonZeroCounts.length > 0 ? nonZeroCounts[nonZeroCounts.length - 1] : 0;
        const minVal = nonZeroCounts.length > 0 ? nonZeroCounts[0] : 0;

        const paletteControles = ['#e6f4ea', '#6ee7b7', '#10b981', '#047857', '#064e3b'];
        const palettePej = ['#f3e8ff', '#d8b4fe', '#a855f7', '#7e22ce', '#581c87'];
        const palettePve = ['#e0e7ff', '#c7d2fe', '#818cf8', '#4f46e5', '#312e81'];
        const paletteInfractions = ['#fce7f3', '#fbcfe8', '#f472b6', '#db2777', '#831843'];

        let activePalette = paletteControles;
        if (metric === 'pej') activePalette = palettePej;
        else if (metric === 'pve') activePalette = palettePve;
        else if (metric === 'infractions') activePalette = paletteInfractions;

        // Algorithme de classification dynamique hybride (Quantiles / Intervalles stricts entiers)
        const classes = [];
        if (maxVal > 0) {
            if (minVal === maxVal) {
                classes.push({
                    min: minVal,
                    max: maxVal,
                    color: activePalette[4],
                    label: minVal === 1 ? '1' : `1 - ${maxVal}`
                });
            } else {
                const numClasses = Math.min(5, maxVal - minVal + 1);

                // Tentative de quantiles si effectifs suffisants
                let percentileBreaks = [];
                if (nonZeroCounts.length >= numClasses) {
                    const getQ = (pct) => nonZeroCounts[Math.min(nonZeroCounts.length - 1, Math.floor(nonZeroCounts.length * pct))];
                    const p20 = getQ(0.20);
                    const p40 = getQ(0.40);
                    const p60 = getQ(0.60);
                    const p80 = getQ(0.80);
                    percentileBreaks = [minVal, p20, p40, p60, p80, maxVal];
                }

                let usePercentiles = percentileBreaks.length === 6;
                if (usePercentiles) {
                    for (let i = 0; i < percentileBreaks.length - 1; i++) {
                        if (percentileBreaks[i] >= percentileBreaks[i + 1]) {
                            usePercentiles = false;
                            break;
                        }
                    }
                }

                if (usePercentiles) {
                    for (let i = 0; i < 5; i++) {
                        const low = i === 0 ? minVal : percentileBreaks[i] + 1;
                        const high = percentileBreaks[i + 1];
                        if (low <= high) {
                            classes.push({
                                min: low,
                                max: high,
                                color: activePalette[i],
                                label: low === high ? `${low}` : (i === 4 ? `> ${percentileBreaks[4]}` : `${low} - ${high}`)
                            });
                        }
                    }
                }

                // Repli sur intervalles linéaires stricts réguliers si quantiles non valides
                if (classes.length === 0) {
                    let lastEnd = minVal - 1;
                    for (let i = 0; i < numClasses; i++) {
                        const low = lastEnd + 1;
                        let high;
                        if (i === numClasses - 1) {
                            high = maxVal;
                        } else {
                            high = Math.floor(minVal + (i + 1) * (maxVal - minVal) / numClasses);
                        }
                        if (high < low) high = low;
                        lastEnd = high;

                        const colorIdx = numClasses === 1 ? 4 : Math.min(4, Math.floor(i * 5 / numClasses));
                        const label = (low === high) ? `${low}` : `${low} - ${high}`;
                        classes.push({
                            min: low,
                            max: high,
                            color: activePalette[colorIdx],
                            label: label
                        });
                    }
                }
            }
        }

        function getColor(val) {
            if (!val || val <= 0) return 'transparent';
            for (let c of classes) {
                if (val >= c.min && val <= c.max) return c.color;
            }
            if (classes.length > 0) {
                if (val < classes[0].min) return classes[0].color;
                if (val > classes[classes.length - 1].max) return classes[classes.length - 1].color;
            }
            return activePalette[0];
        }

        choroplethLayer = L.geoJSON(currentBoundaryGeojson, {
            pane: 'choroplethPane',
            renderer: choroplethRenderer,
            interactive: true,
            style: function(feature) {
                const props = feature.properties || {};
                const codeDept = normCode(props.code_dept || props.insee_dep || props.INSEE_DEP || props.code_dep || props.dep);
                const codeInsee = normCode(props.code_insee || props.CODE_INSEE || props.insee_comm || props.insee_com || props.INSEE_COM || props.INSEE_COMM || props.com || props.insee || props.INSEE || props.insee_com_m);
                const featureKey = codeInsee || codeDept || `feat_${currentBoundaryGeojson.features.indexOf(feature)}`;

                const count = entityCounts.get(featureKey) || 0;
                const isZero = (count === 0);

                return {
                    fillColor: isZero ? '#f1f5f9' : getColor(count),
                    fillOpacity: 1.0,
                    stroke: true,
                    color: '#cbd5e1',
                    weight: 0.5
                };
            },
            onEachFeature: function(feature, layer) {
                const props = feature.properties || {};
                const codeDept = normCode(props.code_dept || props.insee_dep || props.INSEE_DEP || props.code_dep || props.dep);
                const codeInsee = normCode(props.code_insee || props.CODE_INSEE || props.insee_comm || props.insee_com || props.INSEE_COM || props.INSEE_COMM || props.com || props.insee || props.INSEE || props.insee_com_m);
                const featureKey = codeInsee || codeDept || `feat_${currentBoundaryGeojson.features.indexOf(feature)}`;
                const info = entityDetails.get(featureKey) || { nom: 'Zone', total: 0, pej: 0, pve: 0, controles: 0 };

                let tooltipText = `<strong>${fixUtf8Encoding(info.nom)}</strong>`;
                if (codeDept) tooltipText += ` (${codeDept})`;
                tooltipText += `<br>`;

                if (metric === 'controles') {
                    tooltipText += `📊 Contrôles : <strong>${info.controles}</strong>`;
                } else if (metric === 'pej') {
                    tooltipText += `📝 PEJ : <strong>${info.pej}</strong>`;
                } else if (metric === 'pve') {
                    tooltipText += `📱 PVe : <strong>${info.pve}</strong>`;
                } else {
                    tooltipText += `⚖️ Infractions : <strong>${info.pej + info.pve}</strong><br>`;
                    tooltipText += `<span style="font-size:10px; color:#475569;">• PEJ : ${info.pej} | PVe : ${info.pve}</span>`;
                }

                layer.bindTooltip(tooltipText, { sticky: true });

                layer.on({
                    mouseover: function(e) {
                        const l = e.target;
                        l.setStyle({ weight: 2.5, color: '#0f172a', fillOpacity: 1.0 });
                        l.bringToFront();
                    },
                    mouseout: function(e) {
                        if (choroplethLayer) choroplethLayer.resetStyle(e.target);
                    },
                    click: function(e) {
                        const currentScale = typeof selectEchelle !== 'undefined' && selectEchelle ? selectEchelle.value : '';
                        if (currentScale === 'pnf') {
                            // Désactivé pour le PNF : infobulle seule sans altération des filtres
                            return;
                        }
                        if (codeInsee) {
                            const inputCommune = document.getElementById('commune');
                            if (inputCommune) {
                                inputCommune.value = info.nom;
                                triggerDataUpdate();
                            }
                        } else if (codeDept) {
                            const inputDept = document.getElementById('echelle-code');
                            if (inputDept) {
                                inputDept.value = codeDept;
                                triggerDataUpdate();
                            }
                        }
                    }
                });
            }
        }).addTo(map);

        if (typeof boundaryLayer !== 'undefined' && boundaryLayer && typeof boundaryLayer.bringToFront === 'function') {
            try { boundaryLayer.bringToFront(); } catch (e) { }
        }

        const legendTitle = document.getElementById('choropleth-legend-title');
        const legendItems = document.getElementById('choropleth-legend-items');

        let usagerSubTitle = '';
        if (activeKpiFilter && activeKpiFilter.startsWith('usager:')) {
            usagerSubTitle = ` (${activeKpiFilter.substring(7)})`;
        }

        if (legendTitle) {
            if (metric === 'controles') legendTitle.textContent = `Légende - Contrôles${usagerSubTitle}`;
            else if (metric === 'pej') legendTitle.textContent = `Légende - PEJ${usagerSubTitle}`;
            else if (metric === 'pve') legendTitle.textContent = `Légende - PVe${usagerSubTitle}`;
            else legendTitle.textContent = `Légende - Infractions${usagerSubTitle}`;
        }

        let zeroLabel = '0 contrôle';
        if (metric === 'pej') zeroLabel = '0 PEJ';
        else if (metric === 'pve') zeroLabel = '0 PVe';
        else if (metric === 'infractions') zeroLabel = '0 infraction';

        if (legendItems) {
            legendItems.innerHTML = '';
            legendItems.innerHTML += `
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="width: 14px; height: 14px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 2px;"></span>
                    <span>${zeroLabel}</span>
                </div>
            `;

            if (classes.length > 0) {
                classes.forEach(s => {
                    legendItems.innerHTML += `
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span style="width: 14px; height: 14px; background: ${s.color}; border: 1px solid rgba(0,0,0,0.1); border-radius: 2px;"></span>
                            <span>${s.label}</span>
                        </div>
                    `;
                });
            }

            if (!isControles && unmappedProceduresCount > 0) {
                legendItems.innerHTML += `
                    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px dashed #cbd5e1; font-size: 11px; color: #64748b;">
                        Infractions non localisées à la commune : <strong>${unmappedProceduresCount}</strong>
                    </div>
                `;
            }
        }
    }

    // État des filtres de la légende (Activé par défaut)
    window.legendFilters = {
        ctrl_conforme: true,
        ctrl_infraction: true,
        ctrl_attente: true,
        pej: true,
        pa: true,
        pve: true
    };

    // Légende de la carte (Dynamique, Interactive & Rétractable)
    const mapLegend = L.control({ position: 'bottomright' });
    let mapLegendDiv = null;
    let isLegendCollapsed = false;

    window.toggleMapLegend = function(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        isLegendCollapsed = !isLegendCollapsed;
        updateLegend();
    };

    window.toggleLegendFilter = function(filterKey, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        legendFilters[filterKey] = !legendFilters[filterKey];
        applyLegendFilters();
        updateLegend();
    };

    window.toggleLegendGroup = function(groupKey, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        if (groupKey === 'controles') {
            const allActive = legendFilters.ctrl_conforme && legendFilters.ctrl_infraction && legendFilters.ctrl_attente;
            const targetState = !allActive;
            legendFilters.ctrl_conforme = targetState;
            legendFilters.ctrl_infraction = targetState;
            legendFilters.ctrl_attente = targetState;
        } else if (groupKey === 'procedures') {
            const allActive = legendFilters.pej && legendFilters.pa && legendFilters.pve;
            const targetState = !allActive;
            legendFilters.pej = targetState;
            legendFilters.pa = targetState;
            legendFilters.pve = targetState;
        }
        applyLegendFilters();
        updateLegend();
    };

    function applyLegendFilters() {
        if (currentMapMode === 'usagers') {
            clustersByTerritory.forEach((grp, key) => {
                let active = true;
                if (key.includes('_usager_')) {
                    const parts = key.split('_usager_');
                    if (parts.length > 1) {
                        const category = parts[1].split('_')[0];
                        if (usagerLegendFilters[category] === false) active = false;
                    }
                }
                if (active) {
                    if (!clusterParent.hasLayer(grp)) clusterParent.addLayer(grp);
                } else {
                    if (clusterParent.hasLayer(grp)) clusterParent.removeLayer(grp);
                }
            });

            if (typeof clustersByTerritoryN1 !== 'undefined') {
                clustersByTerritoryN1.forEach((grp, key) => {
                    let active = true;
                    if (key.includes('_usager_')) {
                        const parts = key.split('_usager_');
                        if (parts.length > 1) {
                            const category = parts[1].split('_')[0];
                            if (usagerLegendFilters[category] === false) active = false;
                        }
                    }
                    if (active) {
                        if (!clusterParentN1.hasLayer(grp)) clusterParentN1.addLayer(grp);
                    } else {
                        if (clusterParentN1.hasLayer(grp)) clusterParentN1.removeLayer(grp);
                    }
                });
            }

            pejByTerritory.forEach(grp => { if (pejParent.hasLayer(grp)) pejParent.removeLayer(grp); });
            paByTerritory.forEach(grp => { if (paParent.hasLayer(grp)) paParent.removeLayer(grp); });
            pveByTerritory.forEach(grp => { if (pveParent.hasLayer(grp)) pveParent.removeLayer(grp); });
            if (typeof pejByTerritoryN1 !== 'undefined') pejByTerritoryN1.forEach(grp => { if (pejParentN1.hasLayer(grp)) pejParentN1.removeLayer(grp); });
            if (typeof paByTerritoryN1 !== 'undefined') paByTerritoryN1.forEach(grp => { if (paParentN1.hasLayer(grp)) paParentN1.removeLayer(grp); });
            if (typeof pveByTerritoryN1 !== 'undefined') pveByTerritoryN1.forEach(grp => { if (pveParentN1.hasLayer(grp)) pveParentN1.removeLayer(grp); });

            updateMapLayerClasses();
            return;
        }

        // 1. Contrôles (N et N-1)
        clustersByTerritory.forEach((grp, key) => {
            let active = true;
            if (key.endsWith('#10B981')) active = legendFilters.ctrl_conforme;
            else if (key.endsWith('#EF4444')) active = legendFilters.ctrl_infraction;
            else if (key.endsWith('#64748B')) active = legendFilters.ctrl_attente;

            if (active) {
                if (!clusterParent.hasLayer(grp)) clusterParent.addLayer(grp);
            } else {
                if (clusterParent.hasLayer(grp)) clusterParent.removeLayer(grp);
            }
        });

        if (typeof clustersByTerritoryN1 !== 'undefined') {
            clustersByTerritoryN1.forEach((grp, key) => {
                let active = true;
                if (key.endsWith('#10B981')) active = legendFilters.ctrl_conforme;
                else if (key.endsWith('#EF4444')) active = legendFilters.ctrl_infraction;
                else if (key.endsWith('#64748B')) active = legendFilters.ctrl_attente;

                if (active) {
                    if (!clusterParentN1.hasLayer(grp)) clusterParentN1.addLayer(grp);
                } else {
                    if (clusterParentN1.hasLayer(grp)) clusterParentN1.removeLayer(grp);
                }
            });
        }

        // 2. PEJ (N et N-1)
        pejByTerritory.forEach((grp) => {
            if (legendFilters.pej) {
                if (!pejParent.hasLayer(grp)) pejParent.addLayer(grp);
            } else {
                if (pejParent.hasLayer(grp)) pejParent.removeLayer(grp);
            }
        });
        if (typeof pejByTerritoryN1 !== 'undefined') {
            pejByTerritoryN1.forEach((grp) => {
                if (legendFilters.pej) {
                    if (!pejParentN1.hasLayer(grp)) pejParentN1.addLayer(grp);
                } else {
                    if (pejParentN1.hasLayer(grp)) pejParentN1.removeLayer(grp);
                }
            });
        }

        // 3. PA (N et N-1)
        paByTerritory.forEach((grp) => {
            if (legendFilters.pa) {
                if (!paParent.hasLayer(grp)) paParent.addLayer(grp);
            } else {
                if (paParent.hasLayer(grp)) paParent.removeLayer(grp);
            }
        });
        if (typeof paByTerritoryN1 !== 'undefined') {
            paByTerritoryN1.forEach((grp) => {
                if (legendFilters.pa) {
                    if (!paParentN1.hasLayer(grp)) paParentN1.addLayer(grp);
                } else {
                    if (paParentN1.hasLayer(grp)) paParentN1.removeLayer(grp);
                }
            });
        }

        // 4. PVe (N et N-1)
        pveByTerritory.forEach((grp) => {
            if (legendFilters.pve) {
                if (!pveParent.hasLayer(grp)) pveParent.addLayer(grp);
            } else {
                if (pveParent.hasLayer(grp)) pveParent.removeLayer(grp);
            }
        });
        if (typeof pveByTerritoryN1 !== 'undefined') {
            pveByTerritoryN1.forEach((grp) => {
                if (legendFilters.pve) {
                    if (!pveParentN1.hasLayer(grp)) pveParentN1.addLayer(grp);
                } else {
                    if (pveParentN1.hasLayer(grp)) pveParentN1.removeLayer(grp);
                }
            });
        }

        updateMapLayerClasses();
    }

    function updateLegend() {
        if (!mapLegendDiv) return;

        const activeMapMode = document.querySelector('input[name="map-mode"]:checked')?.value || 'markers';
        if (activeMapMode === 'choropleth' || activeMapMode === 'heatmap') {
            mapLegendDiv.style.display = 'none';
            return;
        }

        if (currentMapMode === 'usagers') {
            mapLegendDiv.style.display = 'block';
            let bodyHtml = `
                <div style="font-weight:bold; font-size:10px; margin-bottom:4px; color:#1e293b;">
                    <span>Par Type d'Usager</span>
                </div>
            `;
            const categories = [
                { key: 'Particulier', color: '#2980B9', label: 'Particulier' },
                { key: 'Agriculteur', color: '#F1C40F', label: 'Agriculteur' },
                { key: 'Collectivité', color: '#27AE60', label: 'Collectivité' },
                { key: 'Entreprise', color: '#E74C3C', label: 'Entreprise' },
                { key: 'Acteurs sylvicoles', color: '#16A085', label: 'Acteurs sylvicoles' },
                { key: 'Autre', color: '#95A5A6', label: 'Autre' }
            ];
            categories.forEach(cat => {
                const isActive = usagerLegendFilters[cat.key] !== false;
                const opacityStyle = isActive ? 'opacity: 1;' : 'opacity: 0.4; text-decoration: line-through;';
                bodyHtml += `
                    <div onclick="toggleUsagerLegendFilter('${cat.key}', event)" title="${isActive ? 'Masquer' : 'Afficher'} ${cat.label}" style="display:flex; align-items:center; margin-bottom:3px; cursor:pointer; user-select:none; transition:opacity 0.2s; ${opacityStyle}">
                        <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background-color:${cat.color}; margin-right:6px; flex-shrink:0; border:1px solid rgba(0,0,0,0.15);"></span>
                        <span style="font-size:9.5px; line-height:1.2; color:#334155;">${cat.label}</span>
                    </div>
                `;
            });

            const icon = isLegendCollapsed ? '▲' : '▼';
            const toggleBtn = `<button class="legend-toggle-btn" onclick="toggleMapLegend(event)" title="${isLegendCollapsed ? 'Déplier la légende' : 'Réduire la légende'}" style="background:none; border:none; padding:0 0 0 6px; cursor:pointer; font-size:9px; color:#64748b; font-weight:bold;">${icon}</button>`;

            mapLegendDiv.innerHTML = `
                <div style="display:flex; align-items:center; justify-content:space-between; ${isLegendCollapsed ? '' : 'margin-bottom:4px; border-bottom:1px solid #f1f5f9; padding-bottom:3px;'}" class="legend-header">
                    <span style="font-weight:bold; font-size:9.5px; color:#475569;">Légende Usagers</span>
                    ${toggleBtn}
                </div>
                <div class="legend-body" style="${isLegendCollapsed ? 'display:none;' : 'display:block;'}">
                    ${bodyHtml}
                </div>
            `;
            return;
        }

        const renderItem = (filterKey, color, label) => {
            const isActive = legendFilters[filterKey] !== false;
            const opacityStyle = isActive ? 'opacity: 1;' : 'opacity: 0.4; text-decoration: line-through;';
            const cleanTitle = label.replace(/<br\s*\/?>/gi, ' ');
            return `
                <div onclick="toggleLegendFilter('${filterKey}', event)" title="${isActive ? 'Masquer' : 'Afficher'} ${cleanTitle}" style="display:flex; align-items:center; margin-bottom:3px; cursor:pointer; user-select:none; transition:opacity 0.2s; ${opacityStyle}">
                    <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background-color:${color}; margin-right:6px; flex-shrink:0; border:1px solid rgba(0,0,0,0.15);"></span>
                    <span style="font-size:9.5px; line-height:1.2; color:#334155;">${label}</span>
                </div>
            `;
        };

        const renderGroupHeader = (groupKey, title) => {
            let isAllActive = true;
            if (groupKey === 'controles') {
                isAllActive = legendFilters.ctrl_conforme && legendFilters.ctrl_infraction && legendFilters.ctrl_attente;
            } else if (groupKey === 'procedures') {
                isAllActive = legendFilters.pej && legendFilters.pa && legendFilters.pve;
            }
            const opacityStyle = isAllActive ? 'opacity: 1;' : 'opacity: 0.55;';
            return `
                <div onclick="toggleLegendGroup('${groupKey}', event)" title="Tout masquer / Tout afficher (${title})" style="font-weight:bold; font-size:10px; margin-bottom:4px; color:#1e293b; cursor:pointer; user-select:none; display:flex; align-items:center; justify-content:space-between; ${opacityStyle}">
                    <span>${title}</span>
                </div>
            `;
        };

        const hasConforme = Array.from(clustersByTerritory.keys()).some(k => k.endsWith('#10B981')) ||
                            (typeof clustersByTerritoryN1 !== 'undefined' && Array.from(clustersByTerritoryN1.keys()).some(k => k.endsWith('#10B981')));
        const hasInfraction = Array.from(clustersByTerritory.keys()).some(k => k.endsWith('#EF4444')) ||
                              (typeof clustersByTerritoryN1 !== 'undefined' && Array.from(clustersByTerritoryN1.keys()).some(k => k.endsWith('#EF4444')));
        const hasAttente = Array.from(clustersByTerritory.keys()).some(k => k.endsWith('#64748B')) ||
                           (typeof clustersByTerritoryN1 !== 'undefined' && Array.from(clustersByTerritoryN1.keys()).some(k => k.endsWith('#64748B')));

        const hasControles = hasConforme || hasInfraction || hasAttente;

        const hasPej = pejByTerritory.size > 0 || (typeof pejByTerritoryN1 !== 'undefined' && pejByTerritoryN1.size > 0);
        const hasPa = paByTerritory.size > 0 || (typeof paByTerritoryN1 !== 'undefined' && paByTerritoryN1.size > 0);
        const hasPve = pveByTerritory.size > 0 || (typeof pveByTerritoryN1 !== 'undefined' && pveByTerritoryN1.size > 0);

        const hasAnyData = hasControles || hasPej || hasPa || hasPve;

        if (!hasAnyData) {
            mapLegendDiv.style.display = 'none';
            return;
        }

        mapLegendDiv.style.display = 'block';

        let bodyHtml = '';

        if (hasControles) {
            bodyHtml += renderGroupHeader('controles', 'Contrôles');
            if (hasConforme) bodyHtml += renderItem('ctrl_conforme', '#10B981', 'Conforme');
            if (hasInfraction) bodyHtml += renderItem('ctrl_infraction', '#EF4444', 'Infraction / <br> Manquement');
            if (hasAttente) bodyHtml += renderItem('ctrl_attente', '#64748B', 'En attente / <br> Autre');
        }

        if (hasPej || hasPa || hasPve) {
            if (bodyHtml.length > 0) bodyHtml += `<div style="margin-top:6px;"></div>`;
            bodyHtml += renderGroupHeader('procedures', 'Procédures');
            if (hasPej) bodyHtml += renderItem('pej', '#3B82F6', 'PEJ');
            if (hasPa) bodyHtml += renderItem('pa', '#8B5CF6', 'PA');
            if (hasPve) bodyHtml += renderItem('pve', '#F97316', 'PVe');
        }

        const icon = isLegendCollapsed ? '▲' : '▼';
        const toggleBtn = `<button class="legend-toggle-btn" onclick="toggleMapLegend(event)" title="${isLegendCollapsed ? 'Déplier la légende' : 'Réduire la légende'}" style="background:none; border:none; padding:0 0 0 6px; cursor:pointer; font-size:9px; color:#64748b; font-weight:bold;">${icon}</button>`;

        mapLegendDiv.innerHTML = `
            <div style="display:flex; align-items:center; justify-content:space-between; ${isLegendCollapsed ? '' : 'margin-bottom:4px; border-bottom:1px solid #f1f5f9; padding-bottom:3px;'}" class="legend-header">
                <span style="font-weight:bold; font-size:9.5px; color:#475569;">Légende</span>
                ${toggleBtn}
            </div>
            <div class="legend-body" style="${isLegendCollapsed ? 'display:none;' : 'display:block;'}">
                ${bodyHtml}
            </div>
        `;
    }

    mapLegend.onAdd = function (map) {
        mapLegendDiv = L.DomUtil.create('div', 'info legend');
        mapLegendDiv.style.backgroundColor = 'rgba(255, 255, 255, 0.92)';
        mapLegendDiv.style.padding = '5px 8px';
        mapLegendDiv.style.borderRadius = '5px';
        mapLegendDiv.style.boxShadow = '0 1px 4px rgba(0,0,0,0.2)';
        mapLegendDiv.style.fontSize = '10px';
        mapLegendDiv.style.lineHeight = '1.3';
        mapLegendDiv.style.color = '#334155';
        mapLegendDiv.style.display = 'none';
        
        L.DomEvent.disableClickPropagation(mapLegendDiv);
        
        return mapLegendDiv;
    };
    mapLegend.addTo(map);

    function updateMapLayerClasses() {
        const container = map.getContainer();
        const hasCtrl = map.hasLayer(clusterParent) && clusterParent.getLayers().length > 0;
        const hasPej = map.hasLayer(pejParent) && pejParent.getLayers().length > 0;
        const hasPa = map.hasLayer(paParent) && paParent.getLayers().length > 0;
        const hasPve = map.hasLayer(pveParent) && pveParent.getLayers().length > 0;

        container.classList.toggle('has-ctrl', hasCtrl);
        container.classList.toggle('has-pej', hasPej);
        container.classList.toggle('has-pa', hasPa);
        container.classList.toggle('has-pve', hasPve);
    }

    // Color definitions for status markers
    function getMarkerColor(resultat) {
        if (!resultat) return '#64748B';
        const res = resultat.toLowerCase();
        if (res.includes('en attente')) return '#64748B';
        if (res.includes('conforme') && !res.includes('non')) {
            return '#10B981';
        } else if (res.includes('infraction') || res.includes('non') || res.includes('manquement')) {
            return '#EF4444';
        }
        return '#64748B';
    }

    function toggleElementClass(element, className, add) {
        if (element) element.classList.toggle(className, add);
    }

    function setGlobalLoadingState(isLoading, isError = false, errorMessage = '', territoryLabel = '') {
        const mapOverlay = document.getElementById('map-loading-overlay');
        const mapErrorBanner = document.getElementById('map-error-banner');
        const mapErrorMessage = document.getElementById('map-error-message');
        const loadingBanner = document.getElementById('data-loading-banner');
        const loadingBannerText = document.getElementById('data-loading-banner-text');
        const controlPanel = document.querySelector('.control-panel');
        const quickYearContainer = document.getElementById('quick-year-container');
        const activeQuickYearBtn = document.querySelector('.btn-quick-year.active');

        // Activation / Désactivation des voiles et des filtres
        toggleElementClass(mapOverlay, 'hidden', !isLoading);
        toggleElementClass(controlPanel, 'filters-loading-disabled', isLoading);
        toggleElementClass(quickYearContainer, 'filters-loading-disabled', isLoading);

        if (loadingBanner) {
            if (isLoading) {
                let terrText = territoryLabel;
                if (!terrText) {
                    const echelleVal = typeof selectEchelle !== 'undefined' && selectEchelle ? selectEchelle.value : '';
                    const parsed = typeof getParsedCodes === 'function' ? getParsedCodes() : [];
                    if (echelleVal === 'national') {
                        terrText = 'la France entière';
                    } else if (parsed && parsed.length > 0) {
                        const typeLabel = echelleVal === 'departement' ? 'le département' : echelleVal === 'region' ? 'la région' : 'le périmètre';
                        terrText = `${typeLabel} ${parsed.join(', ')}`;
                    } else {
                        terrText = 'le périmètre sélectionné';
                    }
                }
                if (loadingBannerText) {
                    loadingBannerText.textContent = `Chargement des données pour ${terrText} en cours...`;
                }
                loadingBanner.classList.remove('hidden');
                loadingBanner.style.display = 'flex';
            } else {
                loadingBanner.classList.add('hidden');
                loadingBanner.style.display = 'none';
            }
        }

        if (isLoading) {
            toggleElementClass(mapErrorBanner, 'hidden', true);
            if (activeQuickYearBtn) {
                activeQuickYearBtn.classList.remove('has-error');
                activeQuickYearBtn.classList.add('is-loading');
                let spinner = activeQuickYearBtn.querySelector('.btn-quick-year-spinner');
                if (!spinner) {
                    spinner = document.createElement('span');
                    spinner.className = 'btn-quick-year-spinner';
                    activeQuickYearBtn.appendChild(spinner);
                }
                spinner.style.display = 'inline-block';
            }
        } else {
            document.querySelectorAll('.btn-quick-year').forEach(b => {
                b.classList.remove('is-loading');
                const spinner = b.querySelector('.btn-quick-year-spinner');
                if (spinner) spinner.style.display = 'none';
            });

            if (isError) {
                if (activeQuickYearBtn) activeQuickYearBtn.classList.add('has-error');
                if (mapErrorBanner) {
                    if (mapErrorMessage) {
                        mapErrorMessage.textContent = `⚠️ Erreur lors du chargement des données${errorMessage ? ' : ' + errorMessage : '.'}`;
                    }
                    mapErrorBanner.classList.remove('hidden');
                }
            } else {
                document.querySelectorAll('.btn-quick-year').forEach(b => b.classList.remove('has-error'));
                toggleElementClass(mapErrorBanner, 'hidden', true);
            }
        }
    }

    function loadData() {
        btnUpdate.disabled = true;
        btnUpdate.innerHTML = `
            <style>@keyframes btnspin { 100% { transform: rotate(360deg); } }</style>
            <svg viewBox="0 0 24 24" style="width:18px;height:18px;margin-right:8px;vertical-align:-4px;animation: btnspin 1s linear infinite; stroke: white; fill: none; stroke-width: 3; stroke-linecap: round;">
                <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" />
                <path d="M12 2 A10 10 0 0 1 22 12" stroke="white" />
            </svg>
            Chargement...`;
        setGlobalLoadingState(true);

        // Point C : validation dates avant tout appel réseau
        if (dateDebEl && dateFinEl && dateDebEl.value && dateFinEl.value && dateDebEl.value > dateFinEl.value) {
            const banner = document.getElementById('profile-warning-banner');
            if (banner) {
                banner.innerHTML = '⚠️ La date de début doit être antérieure ou égale à la date de fin.';
                banner.style.display = 'block';
                banner.style.color = '#EF4444';
            }
            btnUpdate.disabled = false;
            btnUpdate.innerHTML = 'Charger les données';
            setGlobalLoadingState(false, false);
            return;
        }

        // Point A : reset de la bannière avant chaque chargement
        const _errBanner = document.getElementById('profile-warning-banner');
        if (_errBanner) { _errBanner.style.display = 'none'; _errBanner.style.color = ''; }

        const isCompare = compareActiveCheck && compareActiveCheck.checked;

        const parsedCodes = getParsedCodes();
        // Mode comparaison spatiale : plusieurs codes, sans comparaison temporelle
        const isSpatial = parsedCodes.length > 1 && !isCompare;

        const getParams = (isComparePeriod = false, overrideCode = null) => {
            const debEl = isComparePeriod ? compareDateDebEl : dateDebEl;
            const finEl = isComparePeriod ? compareDateFinEl : dateFinEl;
            const selectProfil = document.getElementById('profil-select');
            const pnfDeptEl = document.getElementById('pnf-dept-select');
            const pnfAgentEl = document.getElementById('pnf-agent-select');
            return {
                profil: selectProfil ? selectProfil.value : 'global',
                pnf_dept: pnfDeptEl ? pnfDeptEl.value : '',
                agent_service: pnfAgentEl ? pnfAgentEl.value : 'tous',
                'date-deb': debEl ? debEl.value : '',
                'date-fin': finEl ? finEl.value : '',
                echelle: selectEchelle.value,
                // overrideCode : utilisé en mode spatial pour isoler chaque unité
                code: overrideCode !== null ? overrideCode : (parsedCodes[0] || inputCode.value),
                'type-usager': inputUsager.getSelectedValues ? inputUsager.getSelectedValues() : (inputUsager.value ? [inputUsager.value] : []),
                'domaines': inputDomaineSNC.getSelectedValues ? inputDomaineSNC.getSelectedValues() : (inputDomaineSNC.value ? [inputDomaineSNC.value] : []),
                'themes': inputThemeSNC.getSelectedValues ? inputThemeSNC.getSelectedValues() : (inputThemeSNC.value ? [inputThemeSNC.value] : []),
                'types_action': inputTypeAction.getSelectedValues ? inputTypeAction.getSelectedValues() : (inputTypeAction.value ? [inputTypeAction.value] : []),
                'resultats': inputResultat.getSelectedValues ? inputResultat.getSelectedValues() : [],
                'commune': inputCommune ? inputCommune.value.trim() : ''
            };
        };

        // Cache client pour les requêtes /api/data
        if (!window.apiDataCache) window.apiDataCache = new Map();

        // Helper fetch unique avec journalisation systématique et cache client
        const fetchOne = (params) => {
            const cacheKey = JSON.stringify(params);
            if (window.apiDataCache.has(cacheKey)) {
                sendClientLog('INFO', `Données /api/data restituées depuis le cache client pour code ${params.code}`, 'explorer.js', 'fetchOne');
                return Promise.resolve(JSON.parse(JSON.stringify(window.apiDataCache.get(cacheKey))));
            }

            sendClientLog('INFO', `Demande de données /api/data (Échelle: ${params.echelle}, Code: ${params.code}, Période: ${params['date-deb']} -> ${params['date-fin']})`, 'explorer.js', 'fetchOne');
            return fetch('/api/data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: cacheKey
            }).then(async response => {
                if (!response.ok) {
                    let errMsg = 'Erreur API';
                    try { const d = await response.json(); if (d.error) errMsg += ' : ' + d.error; } catch (e) { }
                    sendClientLog('ERROR', `Échec HTTP ${response.status} sur /api/data : ${errMsg}`, 'explorer.js', 'fetchOne');
                    throw new Error(errMsg);
                }
                const data = await response.json();
                const ptsCount = (data.points || []).length;
                const procCount = (data.procedures || []).length;
                sendClientLog('INFO', `Réponse /api/data reçue pour code ${params.code}: ${ptsCount} point(s) de contrôle, ${procCount} procédure(s)`, 'explorer.js', 'fetchOne');

                if (window.apiDataCache.size > 30) {
                    const firstKey = window.apiDataCache.keys().next().value;
                    window.apiDataCache.delete(firstKey);
                }
                window.apiDataCache.set(cacheKey, data);

                return data;
            }).catch(err => {
                sendClientLog('ERROR', `Erreur réseau /api/data : ${err.message}`, 'explorer.js', 'fetchOne');
                throw err;
            });
        };

        // Résolution des promises selon le mode actif
        let allPromises;
        if (isSpatial) {
            // Un fetch par code géographique (ex: "21", "25")
            allPromises = parsedCodes.map(code => fetchOne(getParams(false, code)));
        } else {
            // Mode normal ou comparaison temporelle N vs N-1
            const reqN = fetchOne(getParams(false));
            const reqN1 = isCompare ? fetchOne(getParams(true)) : Promise.resolve(null);
            allPromises = [reqN, reqN1];
        }

        Promise.all(allPromises)
            .then(results => {
                // Normalisation : en mode spatial resGeoUnits = tableau des résultats par unité
                // En mode normal/temporel : resN = results[0], resN1 = results[1]
                const resGeoUnits = isSpatial ? results : null;
                const resN = isSpatial ? Object.assign({}, results[0]) : results[0];
                const resN1 = isSpatial ? null : results[1];

                if (isSpatial) {
                    resN.points = [];
                    resN.procedures = [];
                    resGeoUnits.forEach(res => {
                        if (res.points) resN.points.push(...res.points);
                        if (res.procedures) resN.procedures.push(...res.procedures);
                    });
                }

                saveStateToLocalStorage();
                updateURLWithState();

                lastFetchedDataPayload = {
                    resGeoUnits,
                    rawResN: Object.assign({}, resN),
                    rawResN1: resN1 ? Object.assign({}, resN1) : null,
                    isSpatial,
                    isCompare,
                    parsedCodes
                };

                populateDynamicFilterOptions(resN.points || [], resN.procedures || []);
                renderLoadedData(lastFetchedDataPayload);
            })
            .then(() => {
                const banner = document.getElementById('profile-warning-banner');
                if (banner && banner.style.color === 'rgb(239, 68, 68)') {
                    banner.style.display = 'none';
                    banner.style.color = '';
                }
            })
            .catch(err => {
                if (isUnloading) return;
                console.error('[OFBilan] Erreur chargement données:', err);
                const banner = document.getElementById('profile-warning-banner');
                if (banner) {
                    banner.innerHTML = `⚠️ Impossible de charger les données : ${err.message}`;
                    banner.style.display = 'block';
                    banner.style.color = '#EF4444';
                }
                setGlobalLoadingState(false, true, err.message);
            })
            .finally(() => {
                updateLegend();
                btnUpdate.disabled = false;
                btnUpdate.innerHTML = 'Charger les données';

                const mapErrorBanner = document.getElementById('map-error-banner');
                const hasError = mapErrorBanner && !mapErrorBanner.classList.contains('hidden');
                setGlobalLoadingState(false, hasError);
            });
    }

    function renderLoadedData(payload) {
        if (!payload) return;
        const { resGeoUnits, rawResN, rawResN1, isSpatial, isCompare, parsedCodes } = payload;

        // Déclenchement de la transition visuelle par fondu sur les panneaux de résultats
        triggerDataFadeIn();

        // Application du filtrage dynamique en mémoire à la volée (masquage visuel)
        const resN = Object.assign({}, rawResN, {
            points: (rawResN.points || []).filter(pt => !isItemDynamicallyExcluded(pt, false)),
            procedures: (rawResN.procedures || []).filter(p => !isItemDynamicallyExcluded(p, true))
        });
        const resN1 = rawResN1 ? Object.assign({}, rawResN1, {
            points: (rawResN1.points || []).filter(pt => !isItemDynamicallyExcluded(pt, false)),
            procedures: (rawResN1.procedures || []).filter(p => !isItemDynamicallyExcluded(p, true))
        }) : null;

        // Rendu des valeurs d'indicateurs clés
        function updateStatElement(elementId, statKey) {
            const el = document.getElementById(elementId);
            if (!el) return;

            const hasDynamicExclusion = dynamicExclusions.types.size > 0 || dynamicExclusions.domaines.size > 0 || dynamicExclusions.themes.size > 0 || dynamicExclusions.actions.size > 0;

            if (isSpatial) {
                let htmlLines = resGeoUnits.map((unit, idx) => {
                    let val = (unit.stats && unit.stats[statKey] !== undefined) ? unit.stats[statKey] : 0;
                    if (hasDynamicExclusion && statKey === 'total_controles') {
                        val = resN.points ? resN.points.length : 0;
                    }
                    const label = parsedCodes[idx];
                    return `<div style="display: flex; align-items: baseline; margin-bottom: 4px;">
                        <span style="flex: 1; text-align: right; padding-right: 8px; font-size: 12px !important; color: var(--color-text-muted, #64748B) !important; font-weight: 600 !important; text-transform: uppercase;">${label}</span>
                        <strong style="flex: 1; text-align: left; padding-left: 8px; font-size: 19px !important; color: var(--color-primary) !important; line-height: 1 !important;">${val}</strong>
                    </div>`;
                });
                el.innerHTML = htmlLines.join('');
            } else {
                let valN = (resN.stats && resN.stats[statKey] !== undefined) ? resN.stats[statKey] : 0;
                if (hasDynamicExclusion) {
                    if (statKey === 'total_controles') valN = resN.points ? resN.points.length : 0;
                    if (statKey === 'total_pej') valN = resN.procedures ? resN.procedures.filter(p => (p.type || '').toUpperCase().includes('PEJ')).length : 0;
                    if (statKey === 'total_pa') valN = resN.procedures ? resN.procedures.filter(p => (p.type || '').toUpperCase().includes('PA')).length : 0;
                    if (statKey === 'total_pve') valN = resN.procedures ? resN.procedures.filter(p => (p.type || '').toUpperCase().includes('PVE')).length : 0;
                }
                const valN1 = isCompare && resN1 && resN1.stats ? resN1.stats[statKey] : null;

                if (valN1 === undefined || valN1 === null) {
                    el.innerHTML = valN;
                } else {
                    const pct = valN1 > 0 ? ((valN - valN1) / valN1 * 100).toFixed(1) : 0;
                    const arrow = valN > valN1 ? '▲' : (valN < valN1 ? '▼' : '■');
                    const color = valN > valN1 ? '#10B981' : (valN < valN1 ? '#EF4444' : '#64748B');
                    el.innerHTML = `<span style="font-size: 16px;">${valN}</span> <div style="font-size: 9px; font-weight: 600; color: ${color}; margin-top: 2px;">vs ${valN1} (${pct >= 0 ? '+' : ''}${pct}% ${arrow})</div>`;
                }
            }
        }

                updateStatElement('val-controles', 'total_controles');
                updateStatElement('val-pej', 'total_pej');
                updateStatElement('val-pa', 'total_pa');
                updateStatElement('val-usagers-controles', 'total_usagers_controles');
                updateStatElement('val-pve', 'total_pve');

                if (isCompare && resN && resN1 && resN.stats && resN1.stats) {
                    const ctrlN = resN.stats.total_controles || 0;
                    const ctrlN1 = resN1.stats.total_controles || 0;
                    const dropPct = ctrlN1 > 0 ? ((ctrlN - ctrlN1) / ctrlN1 * 100) : 0;
                    const warnEl = document.getElementById('volume-anomaly-warning');
                    if (warnEl) {
                        if (ctrlN1 > 0 && dropPct < -30) {
                            warnEl.style.display = 'block';
                            warnEl.innerHTML = `⚠️ <b>Alerte volume N-1 :</b> Baisse de ${Math.abs(dropPct.toFixed(1))}% des contrôles vs l'année précédente. Vérifiez la complétude de l'export source.`;
                        } else {
                            warnEl.style.display = 'none';
                        }
                    }
                } else {
                    const warnEl = document.getElementById('volume-anomaly-warning');
                    if (warnEl) warnEl.style.display = 'none';
                }

                const inputDom = document.getElementById('domaine-snc');
                const inputTh = document.getElementById('theme-snc');
                const inputAct = document.getElementById('type-action-snc');
                const hidePve = (inputDom && inputDom.value.trim()) || (inputTh && inputTh.value.trim()) || (inputAct && inputAct.value.trim());
                const pveCard = document.getElementById('stat-card-pve');
                if (pveCard) {
                    pveCard.style.display = hidePve ? 'none' : 'block';
                }

                // Mise à jour des points actifs et du compteur (uniquement basés sur la période principale N)
                activePoints = resN.points || [];
                activeProcedures = resN.procedures || [];
                currentTablePage = 1;

                const resultsCountEl = document.getElementById('results-count');
                if (resultsCountEl) {
                    const count = activePoints.length;
                    resultsCountEl.textContent = `${count} contrôle${count > 1 ? 's' : ''} chargé${count > 1 ? 's' : ''}`;
                    resultsCountEl.classList.remove('hidden');
                }

                if (isTableExpanded) {
                    renderTable();
                }

                markersGroup.clearLayers();
                // Nettoyage des clusters cloisonnés N et N-1
                clearTerritoryMap(clusterParent, clustersByTerritory);
                clearTerritoryMap(pejParent, pejByTerritory);
                clearTerritoryMap(paParent, paByTerritory);
                clearTerritoryMap(pveParent, pveByTerritory);
                clearTerritoryMap(clusterParentN1, clustersByTerritoryN1);
                clearTerritoryMap(pejParentN1, pejByTerritoryN1);
                clearTerritoryMap(paParentN1, paByTerritoryN1);
                clearTerritoryMap(pveParentN1, pveByTerritoryN1);
                if (heatmapLayer) {
                    map.removeLayer(heatmapLayer);
                    heatmapLayer = null;
                }
                if (boundaryLayer) {
                    if (boundaryLayer.maskLayer) map.removeLayer(boundaryLayer.maskLayer);
                    if (boundaryLayer.outerLayer) map.removeLayer(boundaryLayer.outerLayer);
                    map.removeLayer(boundaryLayer);
                    boundaryLayer = null;
                }
                const coordinates = [];
                const heatData = [];
                const isHeatmapMode = document.querySelector('input[name="map-mode"]:checked')?.value === 'heatmap';



                if (resN.points && resN.points.length > 0) {
                    // Map temporaire pour batching : clé -> tableau de markers
                    const markersByKey = new Map();

                    resN.points.forEach(pt => {
                        const lat = parseFloat(pt.y);
                        const lng = parseFloat(pt.x);

                        if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                            if (['pej', 'pa', 'pve'].includes(activeKpiFilter)) return;
                            if (activeKpiFilter && activeKpiFilter.startsWith('resultat:')) {
                                const label = activeKpiFilter.substring(9).toLowerCase();
                                const res = (pt.resultat || '').toLowerCase();
                                if (label.includes('conforme') && !label.includes('non')) {
                                    if (!res.includes('conforme') || res.includes('non')) return;
                                } else if (label.includes('non') || label.includes('infraction') || label.includes('manquement')) {
                                    if (!res.includes('infraction') && !res.includes('non') && !res.includes('manquement')) return;
                                } else {
                                    if (res.includes('conforme') || res.includes('infraction') || res.includes('non') || res.includes('manquement')) return;
                                }
                            }

                            const isUsagersMode = (currentMapMode === 'usagers');
                            const usagerCat = getUsagerCategory(pt.type_usager);
                            if (isUsagersMode && usagerLegendFilters[usagerCat] === false) return;

                            coordinates.push([lat, lng]);
                            heatData.push([lat, lng, 1.0]);

                            const color = isUsagersMode ? getUsagerColor(pt.type_usager) : getMarkerColor(pt.resultat);

                            const marker = L.circleMarker([lat, lng], {
                                radius: 6,
                                fillColor: color,
                                color: '#FFFFFF',
                                weight: 1.5,
                                opacity: 1,
                                fillOpacity: 1,
                                pane: 'entityMarkersPane',
                                renderer: entityRenderer
                            });

                            const resColor = getMarkerColor(pt.resultat);
                            const usaColor = getUsagerColor(pt.type_usager);
                            const popupContent = `
                            <strong>Contrôle OSCEAN</strong><br>
                            ID: ${pt.dc_id || 'N/A'}<br>
                            Date: ${pt.date_ctrl || 'N/A'}<br>
                            Résultat: <span style="font-weight:bold;color:${resColor}">${pt.resultat || 'N/A'}</span><br>
                            Domaine: ${pt.domaine || 'N/A'}<br>
                            Thème: ${pt.theme || 'N/A'}<br>
                            Action: ${pt.type_action || 'N/A'}<br>
                            Usager: <span style="font-weight:bold;color:${usaColor}">${pt.type_usager || 'N/A'}</span><br>
                            Commune: ${pt.nom_commun || 'N/A'}
                        `;
                            marker.bindPopup(popupContent);
                            markersGroup.addLayer(marker);

                            // Cloisonnement : on groupe par clé territoire ET COULEUR avant d'injecter
                            const tKey = isUsagersMode
                                ? getTerritoryKey(pt.code_dept) + '_usager_' + usagerCat + '_' + color
                                : getTerritoryKey(pt.code_dept) + '_' + color;

                            if (!markersByKey.has(tKey)) markersByKey.set(tKey, { markers: [], color: color });
                            markersByKey.get(tKey).markers.push(marker);
                        }
                    });

                    markersByKey.forEach((data, tKey) => {
                        const grp = getOrCreateCluster(tKey, clusterParent, clustersByTerritory, getDynamicClusterOpts(data.color, false, 'cluster-ctrl'));
                        grp.addLayers(data.markers);
                    });
                }

                // Render procedure markers (if any)
                if (resN.procedures && resN.procedures.length > 0) {
                    const pejByKey = new Map(), paByKey = new Map(), pveByKey = new Map();

                    resN.procedures.forEach(p => {
                        let lat = parseFloat(p.y);
                        let lng = parseFloat(p.x);
                        if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                            heatData.push([lat, lng, 1.0]);
                            let procColor = '#3B82F6';
                            const ptype = (p.type || '').toUpperCase();
                            let targetMap = pejByKey;
                            if (ptype.includes('PEJ')) {
                                procColor = '#3B82F6'; targetMap = pejByKey;
                            } else if (ptype.includes('PA')) {
                                procColor = '#8B5CF6'; targetMap = paByKey;
                            } else if (ptype.includes('PVE')) {
                                procColor = '#F97316'; targetMap = pveByKey;
                            }

                            const marker = L.circleMarker([lat, lng], {
                                radius: 6,
                                color: procColor,
                                fillColor: procColor,
                                fillOpacity: 1,
                                weight: 1.5,
                                interactive: true,
                                pane: 'entityMarkersPane',
                                renderer: entityRenderer
                            });
                            const precColor = p.precision_loc && p.precision_loc.includes('Approximatif') ? '#D97706' : '#2563EB';
                            const popup = `
                            <strong>${p.type}</strong><br>
                            N° Oscean : ${p.dc_id || 'N/A'}<br>
                            Date: ${p.date_ctrl || 'N/A'}<br>
                            Type d'action de la ${p.type} : ${p.type_action || 'Non renseigné'}<br>
                            Usager visé : ${p.type_usager || 'Non renseigné'}<br>
                            Précision localisation : <span style="font-weight:bold;color:${precColor}">${p.precision_loc || 'GPS Fait (Exacte)'}</span>
                        `;
                            marker.bindPopup(popup);

                            const tKey = getTerritoryKey(p.code_dept);
                            if (!targetMap.has(tKey)) targetMap.set(tKey, []);
                            targetMap.get(tKey).push(marker);
                        }
                    });

                    pejByKey.forEach((markers, tKey) => getOrCreateCluster(tKey, pejParent, pejByTerritory, getDynamicClusterOpts('#3B82F6', false, 'cluster-pej')).addLayers(markers));
                    paByKey.forEach((markers, tKey) => getOrCreateCluster(tKey, paParent, paByTerritory, getDynamicClusterOpts('#8B5CF6', false, 'cluster-pa')).addLayers(markers));
                    pveByKey.forEach((markers, tKey) => getOrCreateCluster(tKey, pveParent, pveByTerritory, getDynamicClusterOpts('#F97316', false, 'cluster-pve')).addLayers(markers));
                }

                // --- Gestion du bandeau discret des PEJ non localisées & Modale Explicative ---
                const bannerEl = document.getElementById('map-pej-unmapped-banner');
                const unmappedCountEl = document.getElementById('pej-unmapped-count');
                const totalCountEl = document.getElementById('pej-total-count');
                const modalEl = document.getElementById('modal-pej-unmapped-info');
                const btnCloseModal = document.getElementById('btn-close-pej-unmapped-modal');
                const btnOkModal = document.getElementById('btn-ok-pej-unmapped-modal');

                if (bannerEl && unmappedCountEl) {
                    const stats = resN.stats || {};
                    const totalPej = stats.total_pej || 0;
                    const mappedPej = resN.procedures ? resN.procedures.filter(p => (p.type || '').toUpperCase() === 'PEJ' && p.x !== null && p.x !== undefined && p.y !== null && p.y !== undefined).length : 0;
                    const unmappedPej = (stats.unmapped_pej !== undefined) ? stats.unmapped_pej : Math.max(0, totalPej - mappedPej);
                    
                    if (totalPej > 0 && unmappedPej > 0) {
                        unmappedCountEl.textContent = unmappedPej;
                        if (totalCountEl) totalCountEl.textContent = totalPej;
                        bannerEl.classList.remove('hidden');
                    } else {
                        bannerEl.classList.add('hidden');
                    }

                    if (!bannerEl.dataset.hasListener) {
                        bannerEl.dataset.hasListener = "true";
                        const openModal = () => {
                            if (modalEl) modalEl.classList.remove('hidden');
                        };
                        const closeModal = () => {
                            if (modalEl) modalEl.classList.add('hidden');
                        };
                        bannerEl.addEventListener('click', openModal);
                        if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);
                        if (btnOkModal) btnOkModal.addEventListener('click', closeModal);
                        if (modalEl) {
                            modalEl.addEventListener('click', (e) => {
                                if (e.target === modalEl) closeModal();
                            });
                        }
                    }
                }

                applyLegendFilters();
                updateLegend();

                if (isHeatmapMode) {
                    clusterParent.eachLayer(l => map.removeLayer(l));

                    const filteredHeat = getFilteredHeatmapData();
                    const dynamicMax = getDynamicMaxForZoom(map, filteredHeat, 25);

                    heatmapLayer = L.heatLayer(filteredHeat, {
                        radius: 25,
                        blur: 18,
                        maxZoom: map.getZoom(), // Dynamic zoom recalibration
                        max: dynamicMax,
                        gradient: HEATMAP_GRADIENT
                    }).addTo(map);
                } else {
                    if (heatmapLayer) {
                        map.removeLayer(heatmapLayer);
                        heatmapLayer = null;
                    }
                    const selectedMapMode = document.querySelector('input[name="map-mode"]:checked')?.value || 'markers';
                    const isHeatmapOrChoropleth = (selectedMapMode === 'heatmap' || selectedMapMode === 'choropleth');
                    if (isHeatmapOrChoropleth) {
                        if (map.hasLayer(clusterParent)) map.removeLayer(clusterParent);
                    } else if (!map.hasLayer(clusterParent)) {
                        clusterParent.addTo(map);
                    }
                }

                // Render points N-1 (heatmap/cluster group global, style semi-transparent)
                if (isCompare && resN1 && resN1.points && resN1.points.length > 0) {
                    const markersByKeyN1 = new Map();
                    resN1.points.forEach(pt => {
                        const lat = parseFloat(pt.y);
                        const lng = parseFloat(pt.x);

                        if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                            if (['pej', 'pa', 'pve'].includes(activeKpiFilter)) return;
                            if (activeKpiFilter && activeKpiFilter.startsWith('resultat:')) {
                                const label = activeKpiFilter.substring(9).toLowerCase();
                                const res = (pt.resultat || '').toLowerCase();
                                if (label.includes('conforme') && !label.includes('non')) {
                                    if (!res.includes('conforme') || res.includes('non')) return;
                                } else if (label.includes('non') || label.includes('infraction') || label.includes('manquement')) {
                                    if (!res.includes('infraction') && !res.includes('non') && !res.includes('manquement')) return;
                                } else {
                                    if (res.includes('conforme') || res.includes('infraction') || res.includes('non') || res.includes('manquement')) return;
                                }
                            }

                            const isUsagersMode = (currentMapMode === 'usagers');
                            const usagerCat = getUsagerCategory(pt.type_usager);
                            if (isUsagersMode && usagerLegendFilters[usagerCat] === false) return;

                            const color = isUsagersMode ? getUsagerColor(pt.type_usager) : getMarkerColor(pt.resultat);

                            const marker = L.circleMarker([lat, lng], {
                                radius: 6,
                                fillColor: color,
                                color: '#FFFFFF',
                                weight: 1.5,
                                opacity: 0.5,
                                fillOpacity: 0.4,
                                pane: 'entityMarkersPane',
                                renderer: entityRenderer
                            });

                            const resColor = getMarkerColor(pt.resultat);
                            const usaColor = getUsagerColor(pt.type_usager);
                            const popupContent = `
                            <strong>Contrôle OSCEAN (N-1)</strong><br>
                            ID: ${pt.dc_id || 'N/A'}<br>
                            Date: ${pt.date_ctrl || 'N/A'}<br>
                            Résultat: <span style="font-weight:bold;color:${resColor}">${pt.resultat || 'N/A'}</span><br>
                            Domaine: ${pt.domaine || 'N/A'}<br>
                            Thème: ${pt.theme || 'N/A'}<br>
                            Usager: <span style="font-weight:bold;color:${usaColor}">${pt.type_usager || 'N/A'}</span><br>
                            Commune: ${pt.nom_commun || 'N/A'}
                        `;
                            marker.bindPopup(popupContent);
                            markersGroup.addLayer(marker);

                            const tKey = isUsagersMode
                                ? getTerritoryKey(pt.code_dept) + '_usager_' + usagerCat + '_' + color
                                : getTerritoryKey(pt.code_dept) + '_' + color;

                            if (!markersByKeyN1.has(tKey)) markersByKeyN1.set(tKey, { markers: [], color: color });
                            markersByKeyN1.get(tKey).markers.push(marker);
                        }
                    });

                    // N-1 : sous-groupes séparés (jamais mélangés avec N)
                    markersByKeyN1.forEach((data, tKey) => {
                        const grp = getOrCreateCluster(tKey, clusterParentN1, clustersByTerritoryN1, getDynamicClusterOpts(data.color, true, 'cluster-ctrl-n1'));
                        grp.addLayers(data.markers);
                    });
                }

                // Render procedure markers N-1 (cloisonnés)
                if (isCompare && resN1 && resN1.procedures && resN1.procedures.length > 0) {
                    const pejByKeyN1 = new Map(), paByKeyN1 = new Map(), pveByKeyN1 = new Map();

                    resN1.procedures.forEach(p => {
                        let lat = parseFloat(p.y);
                        let lng = parseFloat(p.x);
                        if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                            let procColor = '#3B82F6';
                            const ptype = (p.type || '').toUpperCase();
                            let targetMap = pejByKeyN1;
                            if (ptype.includes('PEJ')) {
                                procColor = '#3B82F6'; targetMap = pejByKeyN1;
                            } else if (ptype.includes('PA')) {
                                procColor = '#8B5CF6'; targetMap = paByKeyN1;
                            } else if (ptype.includes('PVE')) {
                                procColor = '#F97316'; targetMap = pveByKeyN1;
                            }

                            const marker = L.circleMarker([lat, lng], {
                                radius: 6,
                                color: procColor,
                                fillColor: procColor,
                                opacity: 0.5,
                                fillOpacity: 0.35,
                                weight: 1.5,
                                interactive: true,
                                pane: 'entityMarkersPane',
                                renderer: entityRenderer
                            });
                            const popup = `
                            <strong>${p.type} (N-1)</strong><br>
                            N° Oscean : ${p.dc_id || 'N/A'}<br>
                            Date: ${p.date_ctrl || 'N/A'}<br>
                            Type d'action de la ${p.type} : ${p.type_action || 'Non renseigné'}<br>
                            Usager visé : ${p.type_usager || 'Non renseigné'}
                        `;
                            marker.bindPopup(popup);

                            const tKey = getTerritoryKey(p.code_dept);
                            if (!targetMap.has(tKey)) targetMap.set(tKey, []);
                            targetMap.get(tKey).push(marker);
                        }
                    });

                    pejByKeyN1.forEach((markers, tKey) => getOrCreateCluster(tKey, pejParentN1, pejByTerritoryN1, getDynamicClusterOpts('#3B82F6', true, 'cluster-pej-n1')).addLayers(markers));
                    paByKeyN1.forEach((markers, tKey) => getOrCreateCluster(tKey, paParentN1, paByTerritoryN1, getDynamicClusterOpts('#8B5CF6', true, 'cluster-pa-n1')).addLayers(markers));
                    pveByKeyN1.forEach((markers, tKey) => getOrCreateCluster(tKey, pveParentN1, pveByTerritoryN1, getDynamicClusterOpts('#F97316', true, 'cluster-pve-n1')).addLayers(markers));
                }

                applyLegendFilters();
                updateLegend();

                // Plus de addLayers global — déjà injecté dans les sous-groupes cloisonnés ci-dessus

                // Render boundary if available
                currentBoundaryGeojson = { type: "FeatureCollection", features: [] };
                let currentPerimeterGeojson = { type: "FeatureCollection", features: [] };
                let hasGeojson = false;

                if (isSpatial && resGeoUnits) {
                    resGeoUnits.forEach(res => {
                        if (res && res.geojson) {
                            if (res.geojson.type === "FeatureCollection") {
                                currentBoundaryGeojson.features.push(...res.geojson.features);
                            } else {
                                currentBoundaryGeojson.features.push(res.geojson);
                            }
                            hasGeojson = true;
                        }
                        if (res && res.perimeter_geojson) {
                            if (res.perimeter_geojson.type === "FeatureCollection") {
                                currentPerimeterGeojson.features.push(...res.perimeter_geojson.features);
                            } else {
                                currentPerimeterGeojson.features.push(res.perimeter_geojson);
                            }
                        }
                    });
                } else if (resN && resN.geojson) {
                    currentBoundaryGeojson = resN.geojson;
                    currentPerimeterGeojson = resN.perimeter_geojson || { type: "FeatureCollection", features: [] };
                    hasGeojson = true;
                }

                const currentEchelle = document.getElementById('echelle-select')?.value || '';
                if ((!currentPerimeterGeojson.features || currentPerimeterGeojson.features.length === 0) && !['pnf', 'departement'].includes(currentEchelle)) {
                    currentPerimeterGeojson = currentBoundaryGeojson;
                }

                if (hasGeojson) {
                    // 1. boundaryLayer : Affiche les limites administratives officielles prescrites par l'échelle (perimeter_geojson)
                    // Discret, élégant et parfaitement intégré à la charte de l'explorateur (1.8px, #003A76, opacité 0.8)
                    boundaryLayer = L.geoJSON(currentPerimeterGeojson, {
                        interactive: false,
                        style: function(feature) {
                            let color = '#003A76';
                            let weight = 1.8;
                            let opacity = 0.8;
                            let fillColor = 'transparent';
                            let fillOpacity = 0;
                            let dashArray = null;

                            if (feature && feature.properties && feature.properties.zone_type) {
                                if (feature.properties.zone_type === 'risque') {
                                    color = '#EAB308';
                                    fillColor = '#EAB308';
                                    weight = 2;
                                    fillOpacity = 0.2;
                                } else if (feature.properties.zone_type === 'infectee') {
                                    color = '#F97316';
                                    fillColor = '#F97316';
                                    weight = 2;
                                    fillOpacity = 0.3;
                                    dashArray = '5, 5';
                                } else if (feature.properties.zone_type === 'interdiction') {
                                    color = '#EF4444';
                                    fillColor = '#EF4444';
                                    weight = 2;
                                    fillOpacity = 0.4;
                                    dashArray = '10, 5';
                                }
                            }

                            return {
                                color: color,
                                weight: weight,
                                opacity: opacity,
                                fillColor: fillColor,
                                fillOpacity: fillOpacity,
                                dashArray: dashArray,
                                interactive: false
                            };
                        }
                    }).addTo(map);

                    // 2. Masque laiteux d'estompage du fond de carte autour du périmètre
                    const worldCoords = [
                        [85, -360], [85, 360], [-85, 360], [-85, -360]
                    ];
                    let maskRings = [worldCoords];

                    boundaryLayer.eachLayer(layer => {
                        if (layer instanceof L.Polygon) {
                            let latlngs = layer.getLatLngs();
                            if (!latlngs || latlngs.length === 0) return;

                            if (Array.isArray(latlngs[0]) && latlngs[0].length > 0) {
                                if (latlngs[0][0] instanceof L.LatLng) {
                                    maskRings.push(latlngs[0]);
                                } else if (Array.isArray(latlngs[0][0])) {
                                    latlngs.forEach(poly => {
                                        if (poly.length > 0) {
                                            maskRings.push(poly[0]);
                                        }
                                    });
                                }
                            }
                        }
                    });

                    boundaryLayer.maskLayer = L.polygon(maskRings, {
                        color: 'transparent',
                        fillColor: '#ffffff',
                        fillOpacity: 0.60,
                        interactive: false,
                        pane: 'maskPane',
                        renderer: maskRenderer
                    }).addTo(map);

                    if (boundaryLayer && typeof boundaryLayer.bringToFront === 'function') {
                        try { boundaryLayer.bringToFront(); } catch (e) {}
                    }
                    [clusterParent, pejParent, paParent, pveParent, clusterParentN1, pejParentN1, paParentN1, pveParentN1].forEach(grp => {
                        if (grp && typeof grp.bringToFront === 'function') {
                            try { grp.bringToFront(); } catch (e) {}
                        }
                    });
                }

                // Center/zoom map
                if (window.preventMapFitBounds) {
                    // Conserver la vue actuelle (zoom et pan) pour permettre la comparaison interannuelle
                    // Réinitialisation du drapeau pour les futurs chargements
                    window.preventMapFitBounds = false;
                } else {
                    if (selectEchelle.value === 'national') {
                        map.setView([46.2276, 2.2137], 6);
                    } else if (boundaryLayer) {
                        map.fitBounds(boundaryLayer.getBounds(), { padding: [20, 20] });
                    } else if (coordinates.length > 0) {
                        const bounds = L.latLngBounds(coordinates);
                        map.fitBounds(bounds, { padding: [30, 30] });
                    } else {
                        // If no points, reset view to France
                        map.setView([46.2276, 2.2137], 6);
                    }
                }

                renderChoroplethLayer();

                // --- CHARTS GENERATION ---
                const chartData = resN.charts || {};

                const tooltipPercentageCallback = {
                    label: function (context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ' : ';
                        } else {
                            label = context.label ? context.label + ' : ' : '';
                        }
                        const val = context.raw;
                        let total = 0;
                        if (context.chart.config.type === 'bar' && context.dataset.stack) {
                            const currentStack = context.dataset.stack;
                            context.chart.data.datasets.forEach(ds => {
                                if (ds.stack === currentStack) {
                                    total += (ds.data[context.dataIndex] || 0);
                                }
                            });
                        } else {
                            total = context.dataset.data.reduce((sum, v) => sum + (v || 0), 0);
                        }

                        if (total > 0) {
                            const percentage = ((val / total) * 100).toFixed(1);
                            return `${label}${val} (${percentage}%)`;
                        }
                        return `${label}${val}`;
                    }
                };

                // --- CHARTS GENERATION ---

                // 1. Résultats des Contrôles (Doughnut concentrique)
                if (chartResults) {
                    chartResults.destroy();
                }
                const resultsN = chartData.results || {};
                const resultsN1 = isCompare ? (resN1.charts.results || {}) : null;

                // Palette pour les anneaux spatiaux (opacités décroissantes)
                const spatialRingsAlpha = ['ff', 'aa', '66', '44'];
                const spatialResultsColors = [
                    ['#53AB60', '#EF4444', '#64748B'],
                    ['#53AB60aa', '#EF4444aa', '#64748Baa'],
                    ['#53AB6066', '#EF444466', '#64748B66'],
                    ['#53AB6044', '#EF444444', '#64748B44']
                ];

                const resultsDatasets = [];
                if (isSpatial) {
                    // Un dataset (anneau) par unité géo — extérieur = unité 0
                    resGeoUnits.forEach((unit, idx) => {
                        const unitResults = unit.charts.results || {};
                        const colors = spatialResultsColors[idx] || spatialResultsColors[spatialResultsColors.length - 1];
                        resultsDatasets.push({
                            data: Object.values(unitResults),
                            backgroundColor: colors,
                            borderWidth: 1,
                            label: parsedCodes[idx]
                        });
                    });
                } else {
                    resultsDatasets.push({
                        data: Object.values(resultsN),
                        backgroundColor: ['#53AB60', '#EF4444', '#64748B'],
                        borderWidth: 1,
                        label: isCompare ? 'Période N' : 'Période'
                    });
                    if (isCompare && resultsN1) {
                        resultsDatasets.push({
                            data: Object.values(resultsN1),
                            backgroundColor: ['rgba(83, 171, 96, 0.5)', 'rgba(239, 68, 68, 0.5)', 'rgba(100, 116, 139, 0.5)'],
                            borderWidth: 1,
                            label: 'Période N-1'
                        });
                    }
                }

                const ctxResults = document.getElementById('chart-results').getContext('2d');
                chartResults = new Chart(ctxResults, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(isSpatial ? (resGeoUnits[0].charts.results || {}) : resultsN),
                        datasets: resultsDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        onClick: (event, elements) => {
                            if (elements && elements.length > 0) {
                                const index = elements[0].index;
                                const label = chartResults.data.labels[index];
                                window.handleKpiClick('resultat:' + label);
                            } else {
                                window.handleKpiClick('controles');
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: tooltipPercentageCallback }
                        }
                    }
                });

                // Légende résultats
                const legendResults = document.getElementById('legend-results');
                if (legendResults) {
                    legendResults.innerHTML = '';
                    const resultsLabels = Object.keys(isSpatial ? (resGeoUnits[0].charts.results || {}) : resultsN);
                    const resultsColors = ['#53AB60', '#EF4444', '#64748B'];
                    resultsLabels.forEach((label, idx) => {
                        const color = resultsColors[idx] || '#64748B';
                        const itemDiv = document.createElement('div');
                        itemDiv.style.cssText = "display: flex; align-items: center; gap: 5px; font-size: 9px; font-weight: 500; color: var(--color-text-dark); cursor: pointer;";
                        itemDiv.title = `Filtrer la carte sur : ${label}`;
                        itemDiv.innerHTML = `
                            <span style="display: inline-block; width: 8px; height: 8px; background-color: ${color}; border-radius: 50%; flex-shrink: 0;"></span>
                            <span>${label}</span>
                        `;
                        itemDiv.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            window.handleKpiClick('resultat:' + label);
                        });
                        legendResults.appendChild(itemDiv);
                    });
                    if (isSpatial) {
                        const spatialDiv = document.createElement('div');
                        spatialDiv.style.cssText = "font-size:8px;color:#888;margin-top:3px;";
                        spatialDiv.textContent = `Anneau ext. = ${parsedCodes[0]}, int. = ${parsedCodes.slice(1).join(', ')}`;
                        legendResults.appendChild(spatialDiv);
                    }
                }

                // 2. Usagers (Doughnut concentrique)
                if (chartUsagers) {
                    chartUsagers.destroy();
                }
                const usagersN = chartData.usagers || {};
                const usagersN1 = isCompare ? (resN1.charts.usagers || {}) : null;
                const rawLabels = Object.keys(usagersN);
                const usagersLabels = rawLabels.map(label => {
                    if (label.toLowerCase().includes('agriculteur')) return 'Agriculteur';
                    if (label.toLowerCase().includes('particulier')) return 'Particulier';
                    return label;
                });
                const usagersColors = rawLabels.map(label => {
                    const l = label.toLowerCase();
                    if (l.includes('agriculteur')) return '#F1C40F';
                    if (l.includes('particulier')) return '#2980B9';
                    if (l.includes('collectiv')) return '#27AE60';
                    if (l.includes('entreprise')) return '#E74C3C';
                    if (l.includes('sylvic')) return '#16A085';
                    return '#95A5A6';
                });

                const usagersDatasets = [];
                if (isSpatial) {
                    // Un anneau par unité géo
                    resGeoUnits.forEach((unit, idx) => {
                        const unitUsagers = unit.charts.usagers || {};
                        const opacity = idx === 0 ? 'ff' : idx === 1 ? 'aa' : idx === 2 ? '66' : '44';
                        const colors = rawLabels.map(lbl => {
                            const base = usagersColors[rawLabels.indexOf(lbl)];
                            return idx === 0 ? base : base + opacity;
                        });
                        usagersDatasets.push({
                            data: rawLabels.map(lbl => unitUsagers[lbl] || 0),
                            backgroundColor: colors,
                            borderWidth: 1,
                            label: parsedCodes[idx]
                        });
                    });
                } else {
                    usagersDatasets.push({
                        data: Object.values(usagersN),
                        backgroundColor: usagersColors,
                        borderWidth: 1,
                        label: isCompare ? 'Période N' : 'Période'
                    });
                    if (isCompare && usagersN1) {
                        const alignedN1Data = rawLabels.map(lbl => usagersN1[lbl] || 0);
                        usagersDatasets.push({
                            data: alignedN1Data,
                            backgroundColor: usagersColors.map(c => c + '80'),
                            borderWidth: 1,
                            label: 'Période N-1'
                        });
                    }
                }

                const ctxUsagers = document.getElementById('chart-usagers').getContext('2d');
                chartUsagers = new Chart(ctxUsagers, {
                    type: 'doughnut',
                    data: {
                        labels: usagersLabels,
                        datasets: usagersDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        onClick: (event, elements) => {
                            if (elements && elements.length > 0) {
                                const index = elements[0].index;
                                const shortLabel = chartUsagers.data.labels[index];
                                window.handleKpiClick('usager:' + shortLabel);
                            } else {
                                window.handleKpiClick('chart-usagers');
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: tooltipPercentageCallback }
                        }
                    }
                });

                // Légende usagers
                const legendUsagers = document.getElementById('legend-usagers');
                if (legendUsagers) {
                    legendUsagers.innerHTML = '';
                    usagersLabels.forEach((label, idx) => {
                        const color = usagersColors[idx];
                        const itemDiv = document.createElement('div');
                        itemDiv.style.cssText = "display: flex; align-items: center; gap: 5px; font-size: 9px; font-weight: 500; color: var(--color-text-dark); cursor: pointer;";
                        itemDiv.title = `Filtrer la carte sur : ${label}`;
                        itemDiv.innerHTML = `
                            <span style="display: inline-block; width: 8px; height: 8px; background-color: ${color}; border-radius: 50%; flex-shrink: 0;"></span>
                            <span>${label}</span>
                        `;
                        itemDiv.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            window.handleKpiClick('usager:' + label);
                        });
                        legendUsagers.appendChild(itemDiv);
                    });
                    if (isSpatial) {
                        const spatialDiv = document.createElement('div');
                        spatialDiv.style.cssText = "font-size:8px;color:#888;margin-top:3px;";
                        spatialDiv.textContent = `Anneau ext. = ${parsedCodes[0]}, int. = ${parsedCodes.slice(1).join(', ')}`;
                        legendUsagers.appendChild(spatialDiv);
                    }
                }

                // 3. Domaines d'Activité (Barres groupées ou empilées)
                if (chartDomains) {
                    chartDomains.destroy();
                }

                const pnfDeptElChart = document.getElementById('pnf-dept-select');
                const isRegion = selectEchelle.value === 'region' || (selectEchelle.value === 'pnf' && (!pnfDeptElChart || pnfDeptElChart.value === ''));
                const getDomainTotal = (val) => typeof val === 'number' ? val : Object.values(val).reduce((sum, v) => sum + v, 0);

                const sortedDomainsN = Object.entries(chartData.domains || {})
                    .sort((a, b) => getDomainTotal(b[1]) - getDomainTotal(a[1]))
                    .slice(0, 5);

                const domainsN1 = isCompare ? (resN1.charts.domains || {}) : null;
                const domainLabels = sortedDomainsN.map(d => splitLabel(d[0], 40));

                const deptNames = {
                    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence", "05": "Hautes-Alpes",
                    "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes", "09": "Ariège", "10": "Aube",
                    "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal",
                    "16": "Charente", "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud",
                    "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne",
                    "25": "Doubs", "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère",
                    "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde", "34": "Hérault",
                    "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura",
                    "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique",
                    "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère", "49": "Maine-et-Loire",
                    "50": "Manche", "51": "Marne", "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle",
                    "55": "Meuse", "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise",
                    "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques", "65": "Hautes-Pyrénées",
                    "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône",
                    "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie", "75": "Paris",
                    "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines", "79": "Deux-Sèvres", "80": "Somme",
                    "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse", "85": "Vendée",
                    "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
                    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise",
                    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "976": "Mayotte"
                };
                const getDeptName = (code) => {
                    const c = String(code).trim().padStart(2, '0');
                    return deptNames[c] || code;
                };

                // Palette : unités spatiales (D3 Category10), N-1 pastel
                const deptColorsDom = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
                const deptColorsDomN1 = ['#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'];

                let domainsDatasets = [];

                if (isSpatial) {
                    // Mode comparaison spatiale : une barre groupée par unité géo
                    resGeoUnits.forEach((unit, idx) => {
                        const unitDomains = unit.charts.domains || {};
                        domainsDatasets.push({
                            label: parsedCodes[idx],
                            data: sortedDomainsN.map(([domain]) => getDomainTotal(unitDomains[domain] || 0)),
                            backgroundColor: deptColorsDom[idx % deptColorsDom.length],
                            borderRadius: 4,
                            barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                        });
                    });
                } else if (isRegion) {
                    const allDepts = new Set();
                    sortedDomainsN.forEach(([_, counts]) => {
                        if (typeof counts === 'object') Object.keys(counts).forEach(d => allDepts.add(d));
                    });
                    const depts = Array.from(allDepts).sort();
                    depts.forEach((dept, idx) => {
                        domainsDatasets.push({
                            label: isCompare ? `${getDeptName(dept)} N` : getDeptName(dept),
                            data: sortedDomainsN.map(([_, counts]) => (counts[dept] || 0)),
                            backgroundColor: deptColorsDom[idx % deptColorsDom.length],
                            borderColor: '#ffffff',
                            borderWidth: 1,
                            stack: 'Stack N',
                            borderRadius: 4,
                            barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                        });
                    });
                    if (isCompare && domainsN1) {
                        const deptsN1 = new Set();
                        sortedDomainsN.forEach(([domain]) => {
                            const counts = domainsN1[domain] || {};
                            if (typeof counts === 'object') Object.keys(counts).forEach(d => deptsN1.add(d));
                        });
                        Array.from(deptsN1).sort().forEach((dept, idx) => {
                            domainsDatasets.push({
                                label: `${getDeptName(dept)} N-1`,
                                data: sortedDomainsN.map(([domain]) => ((domainsN1[domain] || {})[dept] || 0)),
                                backgroundColor: deptColorsDomN1[idx % deptColorsDomN1.length],
                                borderColor: '#ffffff',
                                borderWidth: 1,
                                stack: 'Stack N-1',
                                borderRadius: 4,
                                barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                            });
                        });
                    }
                } else {
                    domainsDatasets.push({
                        label: isCompare ? 'Période N' : 'Période',
                        data: sortedDomainsN.map(d => getDomainTotal(d[1])),
                        backgroundColor: '#003A76',
                        borderRadius: 4,
                        barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                    });
                    if (isCompare && domainsN1) {
                        const alignedN1 = sortedDomainsN.map(d => getDomainTotal(domainsN1[d[0]] || 0));
                        domainsDatasets.push({
                            label: 'Période N-1',
                            data: alignedN1,
                            backgroundColor: '#93C5FD',
                            borderRadius: 4,
                            barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                        });
                    }
                }

                const showDomainsLegend = isCompare || isRegion || isSpatial;
                const domainTotalLines = domainLabels.reduce((sum, lines) => sum + lines.length, 0);
                // Augmentation de la hauteur de base et de l'espace par barre pour aérer l'affichage
                const domainHeight = Math.max(150, 65 + (domainLabels.length * (showDomainsLegend ? 38 : 28)) + (domainTotalLines - domainLabels.length) * 14);
                const wrapperDomains = document.getElementById('wrapper-domains');
                if (wrapperDomains) {
                    wrapperDomains.style.minHeight = `${domainHeight}px`;
                    wrapperDomains.style.height = '100%';
                }

                const ctxDomains = document.getElementById('chart-domains').getContext('2d');
                chartDomains = new Chart(ctxDomains, {
                    type: 'bar',
                    data: {
                        labels: domainLabels,
                        datasets: domainsDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        indexAxis: 'y',
                        onClick: (event, elements) => {
                            if (elements && elements.length > 0) {
                                const index = elements[0].index;
                                const domainName = sortedDomainsN[index][0];
                                const currentVals = inputDomaineSNC.getSelectedValues ? inputDomaineSNC.getSelectedValues() : (inputDomaineSNC.value ? [inputDomaineSNC.value] : []);
                                if (currentVals.includes(domainName)) {
                                    if (inputDomaineSNC.setSelectedValues) inputDomaineSNC.setSelectedValues([]);
                                    else inputDomaineSNC.value = '';
                                    activeKpiFilter = null;
                                    setActiveKpiVisual(null);
                                } else {
                                    if (inputDomaineSNC.setSelectedValues) inputDomaineSNC.setSelectedValues([domainName]);
                                    else inputDomaineSNC.value = domainName;
                                    activeKpiFilter = 'domaine:' + domainName;
                                    setActiveKpiVisual('domaine:' + domainName);
                                }
                                loadData();
                            }
                        },
                        plugins: {
                            legend: {
                                display: showDomainsLegend,
                                position: 'top',
                                labels: {
                                    boxWidth: 10,
                                    font: { size: 9 },
                                    filter: function (item, chart) {
                                        return !(isCompare && item.text && item.text.endsWith('N-1'));
                                    }
                                }
                            },
                            subtitle: {
                                display: isCompare,
                                text: 'Les couleurs estompées désignent les données N-1',
                                font: { size: 10, style: 'italic' },
                                padding: { bottom: 10 }
                            },
                            tooltip: { callbacks: tooltipPercentageCallback }
                        },
                        scales: {
                            x: { stacked: isRegion && !isSpatial, beginAtZero: true, ticks: { font: { size: 9 } } },
                            y: {
                                stacked: isRegion && !isSpatial,
                                grid: { display: false },
                                ticks: { autoSkip: false, font: { size: 9 } }
                            }
                        }
                    }
                });

                // 4. Thématiques (Barres groupées ou empilées)
                if (chartThemes) {
                    chartThemes.destroy();
                }
                const sortedThemesN = Object.entries(chartData.themes || {})
                    .sort((a, b) => getDomainTotal(b[1]) - getDomainTotal(a[1]))
                    .slice(0, 5);

                const themesN1 = isCompare ? (resN1.charts.themes || {}) : null;
                const themeLabels = sortedThemesN.map(d => splitLabel(d[0], 40));

                const deptColorsTh = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
                const deptColorsThN1 = ['#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'];

                let themesDatasets = [];

                if (isSpatial) {
                    // Mode comparaison spatiale : une barre groupée par unité géo
                    resGeoUnits.forEach((unit, idx) => {
                        const unitThemes = unit.charts.themes || {};
                        themesDatasets.push({
                            label: parsedCodes[idx],
                            data: sortedThemesN.map(([theme]) => getDomainTotal(unitThemes[theme] || 0)),
                            backgroundColor: deptColorsTh[idx % deptColorsTh.length],
                            borderRadius: 4,
                            barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                        });
                    });
                } else if (isRegion) {
                    const allDepts = new Set();
                    sortedThemesN.forEach(([_, counts]) => {
                        if (typeof counts === 'object') Object.keys(counts).forEach(d => allDepts.add(d));
                    });
                    const depts = Array.from(allDepts).sort();
                    depts.forEach((dept, idx) => {
                        themesDatasets.push({
                            label: isCompare ? `${getDeptName(dept)} N` : getDeptName(dept),
                            data: sortedThemesN.map(([_, counts]) => (counts[dept] || 0)),
                            backgroundColor: deptColorsTh[idx % deptColorsTh.length],
                            borderColor: '#ffffff',
                            borderWidth: 1,
                            stack: 'Stack N',
                            borderRadius: 4,
                            barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                        });
                    });
                    if (isCompare && themesN1) {
                        const deptsN1 = new Set();
                        sortedThemesN.forEach(([theme]) => {
                            const counts = themesN1[theme] || {};
                            if (typeof counts === 'object') Object.keys(counts).forEach(d => deptsN1.add(d));
                        });
                        Array.from(deptsN1).sort().forEach((dept, idx) => {
                            themesDatasets.push({
                                label: `${getDeptName(dept)} N-1`,
                                data: sortedThemesN.map(([theme]) => ((themesN1[theme] || {})[dept] || 0)),
                                backgroundColor: deptColorsThN1[idx % deptColorsThN1.length],
                                borderColor: '#ffffff',
                                borderWidth: 1,
                                stack: 'Stack N-1',
                                borderRadius: 4,
                                barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                            });
                        });
                    }
                } else {
                    themesDatasets.push({
                        label: isCompare ? 'Période N' : 'Période',
                        data: sortedThemesN.map(d => getDomainTotal(d[1])),
                        backgroundColor: '#4296CE',
                        borderRadius: 4,
                        barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                    });
                    if (isCompare && themesN1) {
                        const alignedN1 = sortedThemesN.map(d => getDomainTotal(themesN1[d[0]] || 0));
                        themesDatasets.push({
                            label: 'Période N-1',
                            data: alignedN1,
                            backgroundColor: '#FCA5A5',
                            borderRadius: 4,
                            barPercentage: 0.85, categoryPercentage: 0.9, maxBarThickness: 40
                        });
                    }
                }

                const showThemesLegend = isCompare || isRegion || isSpatial;
                const themeTotalLines = themeLabels.reduce((sum, lines) => sum + lines.length, 0);
                // Augmentation de la hauteur de base et de l'espace par barre pour aérer l'affichage
                const themeHeight = Math.max(150, 65 + (themeLabels.length * (showThemesLegend ? 38 : 28)) + (themeTotalLines - themeLabels.length) * 14);
                const wrapperThemes = document.getElementById('wrapper-themes');
                if (wrapperThemes) {
                    wrapperThemes.style.minHeight = `${themeHeight}px`;
                    wrapperThemes.style.height = '100%';
                }

                const ctxThemes = document.getElementById('chart-themes').getContext('2d');
                chartThemes = new Chart(ctxThemes, {
                    type: 'bar',
                    data: {
                        labels: themeLabels,
                        datasets: themesDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        indexAxis: 'y',
                        onClick: (event, elements) => {
                            if (elements && elements.length > 0) {
                                const index = elements[0].index;
                                const themeName = sortedThemesN[index][0];
                                const currentVals = inputThemeSNC.getSelectedValues ? inputThemeSNC.getSelectedValues() : (inputThemeSNC.value ? [inputThemeSNC.value] : []);
                                if (currentVals.includes(themeName)) {
                                    if (inputThemeSNC.setSelectedValues) inputThemeSNC.setSelectedValues([]);
                                    else inputThemeSNC.value = '';
                                    activeKpiFilter = null;
                                    setActiveKpiVisual(null);
                                } else {
                                    if (inputThemeSNC.setSelectedValues) inputThemeSNC.setSelectedValues([themeName]);
                                    else inputThemeSNC.value = themeName;
                                    activeKpiFilter = 'theme:' + themeName;
                                    setActiveKpiVisual('theme:' + themeName);
                                }
                                loadData();
                            }
                        },
                        plugins: {
                            legend: {
                                display: showThemesLegend,
                                position: 'top',
                                labels: {
                                    boxWidth: 10,
                                    font: { size: 9 },
                                    filter: function (item, chart) {
                                        return !(isCompare && item.text && item.text.endsWith('N-1'));
                                    }
                                }
                            },
                            subtitle: {
                                display: isCompare,
                                text: 'Les couleurs estompées désignent les données N-1',
                                font: { size: 10, style: 'italic' },
                                padding: { bottom: 10 }
                            },
                            tooltip: { callbacks: tooltipPercentageCallback }
                        },
                        scales: {
                            x: { stacked: isRegion && !isSpatial, beginAtZero: true, ticks: { font: { size: 9 } } },
                            y: {
                                stacked: isRegion && !isSpatial,
                                grid: { display: false },
                                ticks: { autoSkip: false, font: { size: 9 } }
                            }
                        }
                    }
                });

                // 5. Saisonnalité de l'activité
                if (chartSeasonality) {
                    chartSeasonality.destroy();
                }
                const monthsLabels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sept', 'Oct', 'Nov', 'Déc'];
                const seasonalityN = chartData.seasonality || { controls: Array(12).fill(0), infractions: Array(12).fill(0) };
                const seasonalityN1 = isCompare ? (resN1.charts.seasonality || { controls: Array(12).fill(0), infractions: Array(12).fill(0) }) : null;

                // Palettes pour les courbes spatiales (contrôles + infractions par unité)
                const seasonalColorsBorder = ['#003A76', '#1f77b4', '#2ca02c', '#9467bd', '#8c564b'];
                const seasonalColorsBorderInf = ['#EF4444', '#ff7f0e', '#d62728', '#e377c2', '#bcbd22'];

                const seasonalityDatasets = [];

                if (isSpatial) {
                    // Une paire de courbes (contrôles + infractions) par unité géo
                    resGeoUnits.forEach((unit, idx) => {
                        const unitSeas = unit.charts.seasonality || { controls: Array(12).fill(0), infractions: Array(12).fill(0) };
                        const bColor = seasonalColorsBorder[idx % seasonalColorsBorder.length];
                        const iColor = seasonalColorsBorderInf[idx % seasonalColorsBorderInf.length];
                        seasonalityDatasets.push({
                            label: `Contrôles (${parsedCodes[idx]})`,
                            data: unitSeas.controls,
                            borderColor: bColor,
                            backgroundColor: 'transparent',
                            borderDash: idx > 0 ? [5, 3] : [],
                            fill: false,
                            tension: 0.3
                        });
                        seasonalityDatasets.push({
                            label: `Infractions (${parsedCodes[idx]})`,
                            data: unitSeas.infractions,
                            borderColor: iColor,
                            backgroundColor: 'transparent',
                            borderDash: idx > 0 ? [5, 3] : [],
                            fill: false,
                            tension: 0.3
                        });
                    });
                } else {
                    seasonalityDatasets.push(
                        {
                            label: isCompare ? 'Contrôles (N)' : 'Contrôles',
                            data: seasonalityN.controls,
                            borderColor: '#003A76', backgroundColor: 'rgba(0, 58, 118, 0.05)',
                            fill: true, tension: 0.3
                        },
                        {
                            label: isCompare ? 'Infractions (N)' : 'Infractions',
                            data: seasonalityN.infractions,
                            borderColor: '#EF4444', backgroundColor: 'rgba(239, 68, 68, 0.05)',
                            fill: true, tension: 0.3
                        }
                    );
                    if (isCompare && seasonalityN1) {
                        seasonalityDatasets.push(
                            {
                                label: 'Contrôles (N-1)',
                                data: seasonalityN1.controls,
                                borderColor: '#93C5FD', backgroundColor: 'transparent',
                                borderDash: [5, 5], fill: false, tension: 0.3
                            },
                            {
                                label: 'Infractions (N-1)',
                                data: seasonalityN1.infractions,
                                borderColor: '#FCA5A5', backgroundColor: 'transparent',
                                borderDash: [5, 5], fill: false, tension: 0.3
                            }
                        );
                    }
                }

                const ctxSeasonality = document.getElementById('chart-seasonality').getContext('2d');
                chartSeasonality = new Chart(ctxSeasonality, {
                    type: 'line',
                    data: {
                        labels: monthsLabels,
                        datasets: seasonalityDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'top', labels: { boxWidth: 12, font: { size: 10 } } },
                            tooltip: {
                                callbacks: tooltipPercentageCallback
                            }
                        },
                        scales: {
                            x: { ticks: { font: { size: 9 } } },
                            y: { beginAtZero: true, ticks: { font: { size: 9 } } }
                        }
                    }
                });
    }

    // --- GESTION DU TABLEAU DÉTAILLÉ DES CONTRÔLES (LOT 1) ---
    const toggleTableHeader = document.getElementById('toggle-table-header');
    const tableContainer = document.getElementById('table-container');
    const tableToggleIcon = document.getElementById('table-toggle-icon');

    if (toggleTableHeader && tableContainer && tableToggleIcon) {
        toggleTableHeader.addEventListener('click', (e) => {
            if (e.target.id === 'btn-export-csv' || e.target.closest('#btn-export-csv')) return;

            isTableExpanded = !isTableExpanded;
            if (isTableExpanded) {
                tableContainer.classList.remove('hidden');
                tableToggleIcon.textContent = '▼';
                renderTable();
            } else {
                tableContainer.classList.add('hidden');
                tableToggleIcon.textContent = '▶';
            }
        });
    }

    function isOnlyPejView(data) {
        return activeKpiFilter === 'pej'
            || (data.length > 0 && data.every(row =>
                row.type === 'PEJ'
                || (row.resultat && row.resultat.includes('PEJ'))
            ));
    }

    function getFilteredTableData() {
        let data = [];
        if (activeKpiFilter === 'pej') {
            data = activeProcedures.filter(p => (p.type || '').toUpperCase().includes('PEJ'));
        } else if (activeKpiFilter === 'pa') {
            data = activeProcedures.filter(p => (p.type || '').toUpperCase().includes('PA'));
        } else if (activeKpiFilter === 'pve') {
            data = activeProcedures.filter(p => (p.type || '').toUpperCase().includes('PVE'));
        } else if (activeKpiFilter === 'usagers' || currentMapMode === 'usagers') {
            data = [...activePoints, ...activeProcedures].filter(item => {
                const cat = getUsagerCategory(item.type_usager);
                return usagerLegendFilters[cat] !== false;
            });
        } else if (activeKpiFilter && activeKpiFilter.startsWith('resultat:')) {
            const label = activeKpiFilter.substring(9).toLowerCase();
            data = activePoints.filter(pt => {
                const res = (pt.resultat || '').toLowerCase();
                if (label.includes('conforme') && !label.includes('non')) {
                    return res.includes('conforme') && !res.includes('non');
                } else if (label.includes('non') || label.includes('infraction') || label.includes('manquement')) {
                    return res.includes('infraction') || res.includes('non') || res.includes('manquement');
                } else {
                    return !res.includes('conforme') && !res.includes('infraction') && !res.includes('non') && !res.includes('manquement');
                }
            });
        } else {
            data = [...activePoints, ...activeProcedures];
        }

        return data.filter(item => {
            const isProc = Boolean(item.type && !item.resultat);
            return !isItemDynamicallyExcluded(item, isProc);
        });
    }

    function renderTable() {
        const tableBody = document.getElementById('table-body');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        let data = getFilteredTableData();
        const showDirecteur = isOnlyPejView(data);

        const thDirecteur = document.getElementById('th-directeur-enquete');
        if (thDirecteur) {
            thDirecteur.style.display = showDirecteur ? '' : 'none';
        }

        if (!showDirecteur && tableSortColumn === 'directeur_enquete') {
            tableSortColumn = '';
            document.querySelectorAll('.data-table th[data-sort]').forEach(header => {
                const baseText = header.textContent.replace(/[⇅▲▼]/g, '').trim();
                header.textContent = `${baseText} ⇅`;
            });
        }

        // Tri
        if (tableSortColumn) {
            data.sort((a, b) => {
                let valA = a[tableSortColumn] || '';
                let valB = b[tableSortColumn] || '';

                if (typeof valA === 'string') {
                    return tableSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                } else {
                    return tableSortAsc ? (valA - valB) : (valB - valA);
                }
            });
        }

        // Pagination
        const totalRows = data.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / tableRowsPerPage));
        if (currentTablePage > totalPages) currentTablePage = totalPages;

        const startIndex = (currentTablePage - 1) * tableRowsPerPage;
        const endIndex = Math.min(startIndex + tableRowsPerPage, totalRows);
        const pageData = data.slice(startIndex, endIndex);

        const emptyColspan = showDirecteur ? 9 : 8;
        if (pageData.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="${emptyColspan}" style="text-align: center; color: var(--color-text-muted); padding: 20px;">Aucun contrôle à afficher.</td></tr>`;
        } else {
            pageData.forEach(row => {
                const tr = document.createElement('tr');
                const resText = row.resultat || (row.type ? `Infraction (${row.type})` : '');
                const color = getMarkerColor(resText);
                const communeText = row.nom_commun || ((row.x === null || row.x === undefined || row.x === 0) ? 'Non géolocalisée' : '');
                tr.innerHTML = `
                    <td style="padding: 6px 8px;">${row.dc_id || ''}</td>
                    <td style="padding: 6px 8px;">${row.date_ctrl || ''}</td>
                    <td style="padding: 6px 8px; font-weight: 600; color: ${color};">${resText}</td>
                    <td style="padding: 6px 8px;">${row.domaine || ''}</td>
                    <td style="padding: 6px 8px;">${row.theme || ''}</td>
                    <td style="padding: 6px 8px;">${row.type_action || 'Non renseigné'}</td>
                    <td style="padding: 6px 8px;">${row.type_usager || ''}</td>
                    <td style="padding: 6px 8px;">${communeText}</td>
                    ${showDirecteur ? `<td style="padding: 6px 8px;">${row.directeur_enquete || 'Non renseigné'}</td>` : ''}
                `;
                tableBody.appendChild(tr);
            });
        }

        // Mise à jour de l'UI pagination
        const infoEl = document.getElementById('table-pagination-info');
        if (infoEl) {
            infoEl.textContent = `Affichage de ${totalRows ? startIndex + 1 : 0} à ${endIndex} sur ${totalRows} ligne${totalRows > 1 ? 's' : ''} (Page ${currentTablePage}/${totalPages})`;
        }

        const btnPrev = document.getElementById('btn-page-prev');
        const btnNext = document.getElementById('btn-page-next');
        if (btnPrev) btnPrev.disabled = (currentTablePage === 1);
        if (btnNext) btnNext.disabled = (currentTablePage === totalPages);
    }

    const btnPrev = document.getElementById('btn-page-prev');
    const btnNext = document.getElementById('btn-page-next');
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentTablePage > 1) {
                currentTablePage--;
                renderTable();
            }
        });
    }
    if (btnNext) {
        btnNext.addEventListener('click', () => {
            const data = getFilteredTableData();
            const totalPages = Math.max(1, Math.ceil(data.length / tableRowsPerPage));
            if (currentTablePage < totalPages) {
                currentTablePage++;
                renderTable();
            }
        });
    }

    // Événements de tri sur les en-têtes
    document.querySelectorAll('.data-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            if (tableSortColumn === col) {
                tableSortAsc = !tableSortAsc;
            } else {
                tableSortColumn = col;
                tableSortAsc = true;
            }

            document.querySelectorAll('.data-table th[data-sort]').forEach(header => {
                const baseText = header.textContent.replace(/[⇅▲▼]/g, '').trim();
                if (header.dataset.sort === tableSortColumn) {
                    header.textContent = `${baseText} ${tableSortAsc ? '▲' : '▼'}`;
                } else {
                    header.textContent = `${baseText} ⇅`;
                }
            });
            renderTable();
        });
    });

    // Export CSV
    const btnExportCsv = document.getElementById('btn-export-csv');
    if (btnExportCsv) {
        btnExportCsv.addEventListener('click', (e) => {
            e.stopPropagation();
            const dataToExport = getFilteredTableData();
            if (dataToExport.length === 0) {
                alert('Aucune donnée à exporter.');
                return;
            }

            const exportPejOnly = isOnlyPejView(dataToExport);
            const headers = ['ID', 'Date', 'Resultat', 'Domaine', 'Theme', 'Type Action', 'Type Usager', 'Commune'];
            if (exportPejOnly) {
                headers.push('Directeur d\'enquête');
            }
            headers.push('X', 'Y');
            const rows = dataToExport.map(row => {
                const rowData = [
                    row.dc_id || '',
                    row.date_ctrl || '',
                    row.resultat || (row.type ? `Infraction (${row.type})` : ''),
                    row.domaine || '',
                    row.theme || '',
                    row.type_action || 'Non renseigné',
                    row.type_usager || '',
                    row.nom_commun || ((row.x === null || row.x === undefined || row.x === 0) ? 'Non géolocalisée' : ''),
                ];
                if (exportPejOnly) {
                    rowData.push(row.directeur_enquete || 'Non renseigné');
                }
                rowData.push(
                    row.x !== null && row.x !== undefined ? row.x : 0.0,
                    row.y !== null && row.y !== undefined ? row.y : 0.0
                );
                return rowData;
            });

            const csvContent = "\uFEFF" + [
                headers.join(';'),
                ...rows.map(r => r.map(val => `"${String(val).replace(/"/g, '""')}"`).join(';'))
            ].join('\n');

            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', `export_controles_${new Date().toISOString().slice(0, 10)}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // Réinitialisation des filtres (bouton Effacer)
    const btnReset = document.getElementById('btn-reset');
    if (btnReset) {
        btnReset.addEventListener('click', () => {
            if (typeof resetKpiFilter === 'function') resetKpiFilter();
            const now = new Date();
            const currentYear = now.getFullYear();
            const selectProfil = document.getElementById('profil-select');
            if (selectProfil) selectProfil.value = 'global';

            if (dateDebEl) dateDebEl.value = `${currentYear}-01-01`;
            if (dateFinEl) {
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const day = String(now.getDate()).padStart(2, '0');
                dateFinEl.value = `${currentYear}-${month}-${day}`;
            }

            selectEchelle.value = 'departement';
            inputCode.value = '21';
            codeHelper.textContent = 'Exemples : 21, 27, 39';

            // Réinitialisation des filtres multi-sélections
            if (inputUsager.setSelectedValues) inputUsager.setSelectedValues([]);
            else inputUsager.value = '';

            if (inputDomaineSNC.setSelectedValues) inputDomaineSNC.setSelectedValues([]);
            else inputDomaineSNC.value = '';

            if (inputThemeSNC.setSelectedValues) inputThemeSNC.setSelectedValues([]);
            else inputThemeSNC.value = '';

            if (inputTypeAction.setSelectedValues) inputTypeAction.setSelectedValues([]);
            else inputTypeAction.value = '';

            if (inputResultat.setSelectedValues) inputResultat.setSelectedValues([]);
            else inputResultat.value = '';

            const pnfDeptEl = document.getElementById('pnf-dept-select');
            if (pnfDeptEl) pnfDeptEl.value = '';
            const pnfAgentEl = document.getElementById('pnf-agent-select');
            if (pnfAgentEl) pnfAgentEl.value = 'tous';

            // Rechargement automatique des données réinitialisées
            loadData();
        });
    }

    // Écouteurs de changement pour les options spécifiques PNF
    const pnfDeptSelect = document.getElementById('pnf-dept-select');
    if (pnfDeptSelect) {
        pnfDeptSelect.addEventListener('change', () => loadData());
    }
    const pnfAgentSelect = document.getElementById('pnf-agent-select');
    if (pnfAgentSelect) {
        pnfAgentSelect.addEventListener('change', () => loadData());
    }

    // Écouteurs d'événements cliquables pour Chiffres Clés (KPI) et Graphiques Donuts
    const kpiBindings = [
        { id: 'stat-card-controles', filter: 'controles' },
        { id: 'stat-card-pej', filter: 'pej' },
        { id: 'stat-card-pa', filter: 'pa' },
        { id: 'stat-card-usagers', filter: 'usagers' },
        { id: 'stat-card-pve', filter: 'pve' },
        { id: 'card-chart-results', filter: 'chart-results' },
        { id: 'card-chart-usagers', filter: 'chart-usagers' }
    ];

    kpiBindings.forEach(b => {
        const el = document.getElementById(b.id);
        if (el) {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.btn-export-chart-png')) return;
                window.handleKpiClick(b.filter);
            });
        }
    });

    // Synchronisation du contrôle segmenté avec les boutons radios de mode cartographique
    const segmentedButtons = document.querySelectorAll('.map-segmented-btn');
    segmentedButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const val = btn.getAttribute('data-value');
            const targetRadio = document.querySelector(`input[name="map-mode"][value="${val}"]`);
            if (targetRadio) {
                targetRadio.checked = true;
                targetRadio.dispatchEvent(new Event('change'));
            }
        });
    });

    // Gestion du basculement du mode carte (Points / Chaleur / Choroplèthe)
    document.querySelectorAll('input[name="map-mode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            const selectedMode = radio.value;

            // Synchroniser la classe active sur les boutons segmentés visuels
            segmentedButtons.forEach(btn => {
                if (btn.getAttribute('data-value') === selectedMode) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            const isHeatmapMode = (selectedMode === 'heatmap');
            const isChoroplethMode = (selectedMode === 'choropleth');

            const allParents = [
                clusterParent, pejParent, paParent, pveParent,
                clusterParentN1, pejParentN1, paParentN1, pveParentN1
            ];

            if (isHeatmapMode || isChoroplethMode) {
                allParents.forEach(p => { if (map.hasLayer(p)) map.removeLayer(p); });
                try { if (typeof markersClusterGroup !== 'undefined' && map.hasLayer(markersClusterGroup)) map.removeLayer(markersClusterGroup); } catch (e) { }
            } else {
                allParents.forEach(p => { if (!map.hasLayer(p)) p.addTo(map); });
                try { if (typeof markersClusterGroup !== 'undefined' && !map.hasLayer(markersClusterGroup)) markersClusterGroup.addTo(map); } catch (e) { }
            }

            if (isHeatmapMode) {
                const heatData = getFilteredHeatmapData();
                if (heatmapLayer) map.removeLayer(heatmapLayer);

                const dynamicMax = getDynamicMaxForZoom(map, heatData, 25);
                heatmapLayer = L.heatLayer(heatData, {
                    radius: 25,
                    blur: 18,
                    maxZoom: map.getZoom(),
                    max: dynamicMax,
                    gradient: HEATMAP_GRADIENT
                }).addTo(map);
            } else {
                if (heatmapLayer) {
                    map.removeLayer(heatmapLayer);
                    heatmapLayer = null;
                }
            }

            if (typeof boundaryLayer !== 'undefined' && boundaryLayer && typeof window.getBoundaryStyle === 'function') {
                boundaryLayer.setStyle(window.getBoundaryStyle);
            }

            renderChoroplethLayer();
            saveStateToLocalStorage();
            updateURLWithState();
        });
    });

    const choroplethMetricSelect = document.getElementById('choropleth-metric');
    if (choroplethMetricSelect) {
        choroplethMetricSelect.addEventListener('change', () => {
            renderChoroplethLayer();
            saveStateToLocalStorage();
            updateURLWithState();
        });
    }

    // --- GESTION DU LOCAL STORAGE & DU PERMALIEN (LOT 3) ---
    function getFiltersState() {
        return {
            'date-deb': document.getElementById('date-deb').value,
            'date-fin': document.getElementById('date-fin').value,
            echelle: selectEchelle.value,
            code: inputCode.value,
            'type-usager': inputUsager.getSelectedValues ? inputUsager.getSelectedValues() : (inputUsager.value ? [inputUsager.value] : []),
            'domaines': inputDomaineSNC.getSelectedValues ? inputDomaineSNC.getSelectedValues() : (inputDomaineSNC.value ? [inputDomaineSNC.value] : []),
            'themes': inputThemeSNC.getSelectedValues ? inputThemeSNC.getSelectedValues() : (inputThemeSNC.value ? [inputThemeSNC.value] : []),
            'types_action': inputTypeAction.getSelectedValues ? inputTypeAction.getSelectedValues() : (inputTypeAction.value ? [inputTypeAction.value] : []),
            'resultats': inputResultat.getSelectedValues ? inputResultat.getSelectedValues() : [],
            'commune': inputCommune ? inputCommune.value.trim() : '',
            'compare-active': compareActiveCheck ? compareActiveCheck.checked : false,
            'compare-date-deb': compareDateDebEl ? compareDateDebEl.value : '',
            'compare-date-fin': compareDateFinEl ? compareDateFinEl.value : '',
            'map-mode': document.querySelector('input[name="map-mode"]:checked')?.value || 'markers',
            'choropleth-metric': document.getElementById('choropleth-metric')?.value || 'controles'
        };
    }

    function applyFiltersState(state) {
        if (!state) return;

        if (state['date-deb']) document.getElementById('date-deb').value = state['date-deb'];
        if (state['date-fin']) document.getElementById('date-fin').value = state['date-fin'];

        if (state.echelle) {
            selectEchelle.value = state.echelle;
            selectEchelle.dispatchEvent(new Event('change'));
        }
        if (state.code) inputCode.value = state.code;

        if (state['type-usager'] && inputUsager.setSelectedValues) inputUsager.setSelectedValues(state['type-usager']);
        if (state['domaines'] && inputDomaineSNC.setSelectedValues) inputDomaineSNC.setSelectedValues(state['domaines']);
        if (state['themes'] && inputThemeSNC.setSelectedValues) inputThemeSNC.setSelectedValues(state['themes']);
        if (state['types_action'] && inputTypeAction.setSelectedValues) inputTypeAction.setSelectedValues(state['types_action']);
        if (state['resultats'] && inputResultat.setSelectedValues) inputResultat.setSelectedValues(state['resultats']);
        if (state['commune'] && inputCommune) inputCommune.value = state['commune'];

        if (compareActiveCheck && state['compare-active'] !== undefined) {
            compareActiveCheck.checked = state['compare-active'];
            compareActiveCheck.dispatchEvent(new Event('change'));
        }
        if (state['compare-date-deb'] && compareDateDebEl) {
            compareDateDebEl.value = state['compare-date-deb'];
        }
        if (state['compare-date-fin'] && compareDateFinEl) {
            compareDateFinEl.value = state['compare-date-fin'];
        }

        if (state['map-mode']) {
            const radio = document.querySelector(`input[name="map-mode"][value="${state['map-mode']}"]`);
            if (radio) {
                radio.checked = true;
                radio.dispatchEvent(new Event('change'));
            }
        }
        if (state['choropleth-metric'] && document.getElementById('choropleth-metric')) {
            document.getElementById('choropleth-metric').value = state['choropleth-metric'];
            renderChoroplethLayer();
        }
    }

    function saveStateToLocalStorage() {
        try {
            const state = getFiltersState();
            localStorage.setItem('ofbilan_explorer_filters', JSON.stringify(state));
        } catch (e) {
            console.error('Impossible de sauvegarder dans localStorage', e);
        }
    }

    function loadStateFromLocalStorage() {
        // Désactivé à la demande de l'utilisateur : l'interface doit s'ouvrir "à blanc" par défaut.
        return null;
    }

    function updateURLWithState() {
        const state = getFiltersState();
        const searchParams = new URLSearchParams();

        Object.entries(state).forEach(([key, val]) => {
            if (Array.isArray(val)) {
                if (val.length > 0) searchParams.set(key, val.join(','));
            } else if (val !== '' && val !== false && val !== undefined) {
                searchParams.set(key, val);
            }
        });

        const newRelativePathQuery = window.location.pathname + '?' + searchParams.toString();
        window.history.replaceState(null, '', newRelativePathQuery);
    }

    function loadStateFromURL() {
        const searchParams = new URLSearchParams(window.location.search);
        if (searchParams.toString() === '') return null;

        const state = {};
        searchParams.forEach((value, key) => {
            if (['type-usager', 'domaines', 'themes', 'types_action', 'resultats'].includes(key)) {
                state[key] = value.split(',');
            } else if (key === 'compare-active') {
                state[key] = value === 'true';
            } else {
                state[key] = value;
            }
        });
        return state;
    }


    // --- GESTION DU PLEIN ÉCRAN CARTE (LOT 3) ---
    const btnFullscreenMap = document.getElementById('btn-fullscreen-map');
    if (btnFullscreenMap) {
        btnFullscreenMap.addEventListener('click', () => {
            const mapCard = document.getElementById('map')?.closest('.card');
            if (mapCard) {
                const isFullscreen = mapCard.classList.toggle('map-fullscreen');
                document.body.classList.toggle('has-map-fullscreen', isFullscreen);
                document.body.style.overflow = isFullscreen ? 'hidden' : '';

                if (isFullscreen) {
                    btnFullscreenMap.textContent = '🗗 Quitter';
                    btnFullscreenMap.title = 'Quitter le mode plein écran';
                    if (typeof toggleFiltresDrawer === 'function') {
                        toggleFiltresDrawer(false);
                    }
                } else {
                    btnFullscreenMap.textContent = '⛶ Plein écran';
                    btnFullscreenMap.title = 'Plein écran';
                }

                // Invalidation progressive de la taille pour s'adapter au rendu DOM
                const invalidate = () => { if (typeof map !== 'undefined' && map && map.invalidateSize) map.invalidateSize(); };
                invalidate();
                setTimeout(invalidate, 50);
                setTimeout(invalidate, 250);
            }
        });
    }

    const btnExportMapPng = document.getElementById('btn-export-map-png');
    if (btnExportMapPng) {
        btnExportMapPng.addEventListener('click', () => {
            const mapContainer = document.getElementById('map');
            if (!mapContainer) return;

            const originalText = btnExportMapPng.innerHTML;
            btnExportMapPng.innerHTML = '⏳...';
            btnExportMapPng.disabled = true;

            setTimeout(() => {
                html2canvas(mapContainer, {
                    useCORS: true,
                    allowTaint: false,
                    backgroundColor: '#e5e7eb', // Map background color
                    scale: 2 // Higher resolution
                }).then(canvas => {
                    // Create a composite canvas like charts to add a title
                    const headerHeight = 60;
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = canvas.width;
                    tempCanvas.height = canvas.height + headerHeight;
                    const tempCtx = tempCanvas.getContext('2d');

                    tempCtx.fillStyle = '#FFFFFF';
                    tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);

                    tempCtx.fillStyle = '#003A76';
                    tempCtx.font = 'bold 24px sans-serif'; // Scaled up font
                    tempCtx.textAlign = 'center';
                    tempCtx.fillText('Localisation des contrôles', tempCanvas.width / 2, 40);

                    tempCtx.drawImage(canvas, 0, headerHeight);

                    const link = document.createElement('a');
                    link.download = `OFBilan_Carte_${new Date().toISOString().split('T')[0]}.png`;
                    link.href = tempCanvas.toDataURL('image/png', 1.0);
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    btnExportMapPng.innerHTML = originalText;
                    btnExportMapPng.disabled = false;
                }).catch(err => {
                    console.error("Erreur lors de l'export de la carte:", err);
                    alert("Une erreur est survenue lors de l'export de la carte.");
                    btnExportMapPng.innerHTML = originalText;
                    btnExportMapPng.disabled = false;
                });
            }, 100);
        });
    }

    // --- EXPORT PNG DES GRAPHIPHES (LOT 3) ---
    document.querySelectorAll('.btn-export-chart-png').forEach(btn => {
        btn.addEventListener('click', () => {
            const chartId = btn.getAttribute('data-chart');
            const canvas = document.getElementById(chartId);
            if (!canvas) return;

            let chartInstance = null;
            let chartTitleText = "";
            if (chartId === 'chart-seasonality') { chartInstance = chartSeasonality; chartTitleText = "Saisonnalité de l'activité"; }
            else if (chartId === 'chart-results') { chartInstance = chartResults; chartTitleText = "Résultats des Contrôles"; }
            else if (chartId === 'chart-usagers') { chartInstance = chartUsagers; chartTitleText = "Répartition par Type d'Usager"; }
            else if (chartId === 'chart-domains') { chartInstance = chartDomains; chartTitleText = "Répartition par Domaine d'Activité"; }
            else if (chartId === 'chart-themes') { chartInstance = chartThemes; chartTitleText = "Répartition par Thématique (Top 5)"; }

            // Dimensions de l'image finale (hauteur dynamique de pied de page pour affichage vertical sans chevauchement)
            const headerHeight = 60;
            const labels = (chartInstance && chartInstance.data && chartInstance.data.labels) ? chartInstance.data.labels : [];
            const footerHeight = (chartId === 'chart-results' || chartId === 'chart-usagers') ? (labels.length * 20) + 15 : 60;

            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height + headerHeight + footerHeight;
            const tempCtx = tempCanvas.getContext('2d');

            // Fond blanc
            tempCtx.fillStyle = '#FFFFFF';
            tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);

            // 1. Dessiner le titre
            tempCtx.fillStyle = '#003A76';
            tempCtx.font = 'bold 16px sans-serif';
            tempCtx.textAlign = 'center';
            tempCtx.fillText(chartTitleText, tempCanvas.width / 2, 35);

            // 2. Dessiner le graphique au centre
            tempCtx.drawImage(canvas, 0, headerHeight);

            // 3. Dessiner la légende en bas
            if (chartInstance && chartInstance.data) {
                tempCtx.textAlign = 'left';
                tempCtx.font = '11px sans-serif';

                const datasets = chartInstance.data.datasets || [];

                if (chartId === 'chart-results' || chartId === 'chart-usagers') {
                    // Pour les Donuts : on a une couleur par élément
                    const ds = datasets[0] || {};
                    const data = ds.data || [];
                    const bgColors = ds.backgroundColor || [];

                    // Calcul du total de la période principale N
                    const total = data.reduce((a, b) => a + (b || 0), 0);

                    let startX = 25;
                    let startY = canvas.height + headerHeight + 20;

                    labels.forEach((lbl, idx) => {
                        const val = data[idx] || 0;
                        const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                        const color = bgColors[idx] || '#64748B';

                        // Carré de couleur
                        tempCtx.fillStyle = color;
                        tempCtx.fillRect(startX, startY - 10, 12, 12);

                        // Texte de la légende avec les valeurs
                        tempCtx.fillStyle = '#1E293B';
                        const displayLabel = Array.isArray(lbl) ? lbl.join(' ') : lbl;

                        // Si une comparaison est active, on ajoute la valeur N-1 dans la légende
                        let valText = `${displayLabel}: ${val} (${pct}%)`;
                        if (datasets.length > 1) {
                            const dataN1 = datasets[1].data || [];
                            const valN1 = dataN1[idx] || 0;
                            const totalN1 = dataN1.reduce((a, b) => a + (b || 0), 0);
                            const pctN1 = totalN1 > 0 ? ((valN1 / totalN1) * 100).toFixed(1) : 0;
                            valText += ` (vs période comp. : ${valN1} [${pctN1}%])`;
                        }

                        tempCtx.fillText(valText, startX + 20, startY);
                        startY += 20; // Saut de ligne
                    });
                } else if (chartId === 'chart-domains' || chartId === 'chart-themes') {
                    // Pour les barres horizontales
                    let startY = canvas.height + headerHeight + 30;
                    tempCtx.fillStyle = '#64748B';
                    tempCtx.font = 'italic 11px sans-serif';

                    let text = "Données issues de la recherche active de l'explorateur OFBilan.";
                    if (datasets.length > 1) {
                        text += ` Comparaison : ${datasets[0].label || 'Période N'} vs ${datasets[1].label || 'Période N-1'}`;
                    }
                    tempCtx.fillText(text, 20, startY);
                } else if (chartId === 'chart-seasonality') {
                    // Pour la saisonnalité
                    let startX = 20;
                    let startY = canvas.height + headerHeight + 30;

                    datasets.forEach((ds) => {
                        tempCtx.fillStyle = ds.borderColor || '#64748B';
                        tempCtx.fillRect(startX, startY - 8, 20, 4);

                        tempCtx.fillStyle = '#1E293B';
                        tempCtx.fillText(ds.label, startX + 25, startY);
                        startX += 130;
                    });
                }
            }

            const imageURI = tempCanvas.toDataURL('image/png');
            const link = document.createElement('a');
            link.download = `${chartId}_export.png`;
            link.href = imageURI;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    });

    btnUpdate.addEventListener('click', loadData);

    const btnRetryLoad = document.getElementById('btn-retry-load');
    if (btnRetryLoad) {
        btnRetryLoad.addEventListener('click', loadData);
    }

    const btnPdf = document.getElementById('btn-pdf');
    if (btnPdf) {
        btnPdf.addEventListener('click', () => {
            // Construction dynamique du titre pour le PDF
            const scale = selectEchelle.options[selectEchelle.selectedIndex].text;
            const codes = getParsedCodes();
            let territoryStr = '';

            if (selectEchelle.value === 'national') {
                territoryStr = 'National';
            } else if (codes.length > 0) {
                const activeList = getActiveCodesList();
                const labels = codes.map(c => {
                    const found = activeList.find(i => i.value === c);
                    return found ? found.label.replace(/^[^-]+-\s*/, '') : c; // Enlève le préfixe ex: "21 -"
                });
                territoryStr = labels.join(', ');
            } else {
                territoryStr = 'Non spécifié';
            }

            // Récupérer les filtres
            let filtres = [];
            if (inputUsager && inputUsager.getSelectedValues) {
                const vals = inputUsager.getSelectedValues().filter(v => v);
                if (vals.length > 0) filtres.push(...vals);
            }
            if (inputDomaineSNC && inputDomaineSNC.getSelectedValues) {
                const vals = inputDomaineSNC.getSelectedValues().filter(v => v);
                if (vals.length > 0) filtres.push(...vals);
            }
            if (inputThemeSNC && inputThemeSNC.getSelectedValues) {
                const vals = inputThemeSNC.getSelectedValues().filter(v => v);
                if (vals.length > 0) filtres.push(...vals);
            }
            if (inputTypeAction && inputTypeAction.getSelectedValues) {
                const vals = inputTypeAction.getSelectedValues().filter(v => v);
                if (vals.length > 0) filtres.push(...vals);
            }

            const profilSelect = document.getElementById('profil-select');
            let activiteStr = 'Bilan global';

            if (profilSelect && profilSelect.selectedIndex >= 0 && profilSelect.value !== 'global') {
                activiteStr = profilSelect.options[profilSelect.selectedIndex].text;
                if (filtres.length > 0) {
                    activiteStr += ' — ' + filtres.join(', ');
                }
            } else if (filtres.length > 0) {
                activiteStr = 'Activité sur ' + filtres.join(', ');
            }

            // Dates
            const dateDeb = dateDebEl ? dateDebEl.value.split('-').reverse().join('/') : '';
            const dateFin = dateFinEl ? dateFinEl.value.split('-').reverse().join('/') : '';
            const periodeStr = `période du ${dateDeb} au ${dateFin}`;

            const fullTitle = `${activiteStr} — ${scale} : ${territoryStr} — ${periodeStr}`;

            // Mention de comparaison N / N-1 uniquement pour le titre visuel d'impression (#print-title)
            const compareActiveEl = document.getElementById('compare-active');
            let displayTitle = fullTitle;
            if (compareActiveEl && compareActiveEl.checked) {
                displayTitle += ' (Comparaison années N / N-1)';
            }

            const titleEl = document.getElementById('print-title');
            if (titleEl) {
                titleEl.textContent = displayTitle;
            }

            // Changer le titre du document pour nommer le PDF généré
            const originalDocumentTitle = document.title;
            // Remplacer les caractères problématiques pour un nom de fichier par des tirets
            const safeTitle = fullTitle.replace(/[/\\?%*:|"<>]/g, '-').replace(/\s+/g, ' ').trim();
            document.title = `Bilan_OFB_${safeTitle}`;

            // ── Restauration après impression (Validée via /grill-me) ─────────
            // Logique de restauration fluide :
            // 1. Idempotence (hasRestored) et annulation du fallback timer (5s).
            // 2. Restauration immédiate du document.title.
            // 3. Réinitialisation des conteneurs HTML.
            // 4. Attente du reflow DOM (~100ms) pour recadrer la carte (center & zoom d'origine),
            //    réactiver la couche vectorielle et supprimer l'image temporaire sans clignotement blanc.
            // 5. Redimensionnement et mise à jour complète de tous les graphiques ChartJS.
            const prePrintCenter = (typeof map !== 'undefined' && map) ? map.getCenter() : null;
            const prePrintZoom = (typeof map !== 'undefined' && map) ? map.getZoom() : null;

            let hasRestored = false;
            let fallbackTimer = null;

            const restore = () => {
                if (hasRestored) return;
                hasRestored = true;
                if (fallbackTimer) clearTimeout(fallbackTimer);
                window.removeEventListener('afterprint', restore);

                // Restauration immédiate du titre du document
                document.title = originalDocumentTitle;

                // Restaurer la hauteur des wrappers ChartJS
                const wDom = document.getElementById('wrapper-domains');
                const wThe = document.getElementById('wrapper-themes');
                if (wDom) {
                    if (wDom.dataset.tmpH !== undefined) wDom.style.height = wDom.dataset.tmpH;
                    if (wDom.dataset.tmpMinH !== undefined) wDom.style.minHeight = wDom.dataset.tmpMinH;
                }
                if (wThe) {
                    if (wThe.dataset.tmpH !== undefined) wThe.style.height = wThe.dataset.tmpH;
                    if (wThe.dataset.tmpMinH !== undefined) wThe.style.minHeight = wThe.dataset.tmpMinH;
                }

                const wRes = typeof chartResults !== 'undefined' && chartResults ? chartResults.canvas.parentNode : null;
                const wUsa = typeof chartUsagers !== 'undefined' && chartUsagers ? chartUsagers.canvas.parentNode : null;
                if (wRes) {
                    if (wRes.dataset.tmpW !== undefined) wRes.style.width = wRes.dataset.tmpW;
                    if (wRes.dataset.tmpH !== undefined) wRes.style.height = wRes.dataset.tmpH;
                    wRes.style.margin = '';
                }
                if (wUsa) {
                    if (wUsa.dataset.tmpW !== undefined) wUsa.style.width = wUsa.dataset.tmpW;
                    if (wUsa.dataset.tmpH !== undefined) wUsa.style.height = wUsa.dataset.tmpH;
                    wUsa.style.margin = '';
                }


                // Attendre le reflow CSS avant de restaurer Leaflet et les graphiques
                setTimeout(() => {
                    // Supprimer les snapshots canvas d'impression
                    document.querySelectorAll('.print-canvas-snapshot').forEach(el => el.remove());

                    if (typeof map !== 'undefined' && map) {
                        const mapEl2 = document.getElementById('map');
                        if (mapEl2) { mapEl2.style.width = ''; mapEl2.style.height = ''; }
                        map.invalidateSize({ animate: false });
                        if (prePrintCenter && prePrintZoom !== null) {
                            map.setView(prePrintCenter, prePrintZoom, { animate: false });
                        }
                    }

                    // Redimensionner et mettre à jour tous les graphiques ChartJS
                    [chartDomains, chartThemes, chartResults, chartUsagers, typeof chartSeasonality !== 'undefined' ? chartSeasonality : null].forEach(c => {
                        if (c) { try { c.resize(); c.update('none'); } catch (e) {} }
                    });
                }, 100);
            };

            window.addEventListener('afterprint', restore);
            fallbackTimer = setTimeout(restore, 5000);

            setTimeout(() => {

                // ─ Redimensionnement ChartJS pour le format A4 ─
                const wDom = document.getElementById('wrapper-domains');
                const wThe = document.getElementById('wrapper-themes');
                if (wDom) { wDom.dataset.tmpH = wDom.style.height; wDom.style.height = '160px'; wDom.dataset.tmpMinH = wDom.style.minHeight; wDom.style.minHeight = '160px'; }
                if (wThe) { wThe.dataset.tmpH = wThe.style.height; wThe.style.height = '160px'; wThe.dataset.tmpMinH = wThe.style.minHeight; wThe.style.minHeight = '160px'; }

                const wRes = typeof chartResults !== 'undefined' && chartResults ? chartResults.canvas.parentNode : null;
                const wUsa = typeof chartUsagers !== 'undefined' && chartUsagers ? chartUsagers.canvas.parentNode : null;
                if (wRes) { wRes.dataset.tmpW = wRes.style.width; wRes.dataset.tmpH = wRes.style.height; wRes.style.width = '110px'; wRes.style.height = '110px'; wRes.style.margin = '0 auto'; chartResults.resize(); }
                if (wUsa) { wUsa.dataset.tmpW = wUsa.style.width; wUsa.dataset.tmpH = wUsa.style.height; wUsa.style.width = '110px'; wUsa.style.height = '110px'; wUsa.style.margin = '0 auto'; chartUsagers.resize(); }
                if (typeof chartDomains !== 'undefined' && chartDomains && wDom) chartDomains.resize(wDom.clientWidth, 160);
                if (typeof chartThemes !== 'undefined' && chartThemes && wThe) chartThemes.resize(wThe.clientWidth, 160);

                // ─ Étape 1 : calibrer le conteneur carte aux dimensions PDF (étape JS obligatoire) ─
                // Indispensable : invalidateSize() récalibre le canvas Leaflet sur ces dimensions.
                // Sans cette étape, le canvas reste calibré sur les dims écran et le CSS print le clipse.
                const mapEl = document.getElementById('map');
                if (mapEl) { mapEl.style.width = '610px'; mapEl.style.height = '350px'; }
                if (typeof map !== 'undefined' && map) {
                    map.invalidateSize({ animate: false }); // canvas vidé + _redraw programmé sur prochain RAF
                    if (typeof boundaryLayer !== 'undefined' && boundaryLayer) {
                        try { map.fitBounds(boundaryLayer.getBounds(), { padding: [10, 10], animate: false }); } catch (e) {}
                        // fitBounds(animate:false) déclenche moveend de façon synchrone
                        // le renderer canvas programme un nouveau _redraw via requestAnimationFrame
                    }
                }

                // ─ Étape 2 : attendre les tuiles IGN (max 5s) puis 2 RAF pour le canvas ─
                // Principe : on capture le canvas EN PNG après son redessin complet.
                // L'image statique contourne le bug Chromium qui rate les <canvas> récemment modifiés lors de window.print().
                const MAX_MS = 5000;
                const t0 = Date.now();

                const snapshotAndPrint = () => {
                    // Supprimer anciens snapshots résiduels
                    document.querySelectorAll('.print-canvas-snapshot').forEach(el => el.remove());

                    // Capturer chaque canvas Leaflet (vecteurs + heatmap) en PNG transparent
                    // et l'afficher comme overlay dans #map (z-index 450 : au-dessus du canvas vectoriel
                    // z=400, en-dessous des marqueurs HTML z=600)
                    if (mapEl) {
                        document.querySelectorAll('#map canvas').forEach(canvas => {
                            try {
                                const dataUrl = canvas.toDataURL('image/png');
                                if (!dataUrl || dataUrl.length < 200) return;
                                const img = document.createElement('img');
                                img.src = dataUrl;
                                img.className = 'print-canvas-snapshot';
                                const parentPane = canvas.closest('.leaflet-pane');
                                let zIdx = 450;
                                if (parentPane && parentPane.style && parentPane.style.zIndex) {
                                    zIdx = parseInt(parentPane.style.zIndex, 10) || 450;
                                }
                                img.style.cssText = [
                                    'position:absolute', 'left:0', 'top:0',
                                    'width:100%', 'height:100%',
                                    'pointer-events:none',
                                    `z-index:${zIdx}`,
                                    '-webkit-print-color-adjust:exact',
                                    'print-color-adjust:exact'
                                ].join(';');
                                mapEl.appendChild(img);
                            } catch (e) {}
                        });
                    }
                    window.print();
                };

                const waitForTiles = () => {
                    const pending = document.querySelectorAll(
                        '.leaflet-tile-pane img.leaflet-tile:not(.leaflet-tile-loaded)'
                    );
                    if (pending.length === 0 || Date.now() - t0 > MAX_MS) {
                        // 2 RAF : laisser le renderer canvas Leaflet achever son cycle de rendu
                        // avant la capture toDataURL()
                        requestAnimationFrame(() => requestAnimationFrame(snapshotAndPrint));
                    } else {
                        setTimeout(waitForTiles, 100);
                    }
                };
                // Délai initial pour laisser Leaflet lancer les requêtes tiles
                setTimeout(waitForTiles, 500);

            }, 350);
        });
    }
});



