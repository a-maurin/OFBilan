document.addEventListener('DOMContentLoaded', () => {
    let isUnloading = false;
    window.addEventListener('beforeunload', () => {
        isUnloading = true;
    });

    let chartResults = null;
    let chartDomains = null;
    let boundaryLayer = null;

    const btnUpdate = document.getElementById('btn-update');
    const selectEchelle = document.getElementById('echelle');
    const inputCode = document.getElementById('code');
    const codeHelper = document.getElementById('code-helper');

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

    // Stats Elements
    const valControles = document.getElementById('val-controles');
    const valPej = document.getElementById('val-pej');
    const valPa = document.getElementById('val-pa');
    const valPve = document.getElementById('val-pve');

    // Combobox Profils de bilan
    const inputProfil = document.getElementById('profil');
    const btnToggleProfils = document.getElementById('btn-toggle-profils');
    const profilsDropdown = document.getElementById('profils-dropdown');

    // Combobox Type Usager
    const inputUsager = document.getElementById('type-usager');
    const btnToggleUsagers = document.getElementById('btn-toggle-usagers');
    const usagersDropdown = document.getElementById('usagers-dropdown');

    const profilesList = [
        { value: "global", label: "Bilan Global d'Activité" },
        { value: "synthese_activite_PA_PJ", label: "Synthèse & Activité PA/PJ" },
        { value: "agrainage", label: "Police de l'Agrainage" },
        { value: "chasse", label: "Police de la Chasse" },
        { value: "autorisations_environnementales", label: "Autorisations Environnementales" },
        { value: "autres_gestion_qualitative", label: "Autres Gestions Qualitatives" },
        { value: "continuite_ecologique", label: "Continuité Écologique" },
        { value: "controles_aires_protegees", label: "Contrôles Aires Protégées" },
        { value: "controles_espaces_proteges", label: "Contrôles Espaces Protégés" },
        { value: "controles_secheresse", label: "Contrôles Sécheresse" },
        { value: "especes_exotiques_envahissantes", label: "Espèces Exotiques Envahissantes" },
        { value: "especes_protegees", label: "Espèces Protégées" },
        { value: "faune_protegee_reglementee", label: "Faune Protégée Réglementée" },
        { value: "faune_sauvage", label: "Faune Sauvage" },
        { value: "faune_sauvage_captive", label: "Faune Sauvage Captive" },
        { value: "gestion_eaux_pluviales", label: "Gestion des Eaux Pluviales" },
        { value: "gestion_quantitative_hors_snc", label: "Gestion Quantitative Hors SNC" },
        { value: "ouvrages_prelevement", label: "Ouvrages de Prélèvement" },
        { value: "peche", label: "Pêche" },
        { value: "piegeage", label: "Piégeage" },
        { value: "plans_eau", label: "Plans d'Eau" },
        { value: "pnf", label: "PNF (Parc National des Forêts)" },
        { value: "pollutions_diffuses", label: "Pollutions Diffuses" },
        { value: "pollutions_urbaines", label: "Pollutions Urbaines" },
        { value: "procedures_pve", label: "Procédures PVe" },
        { value: "reglementation_sanitaire", label: "Réglementation Sanitaire" },
        { value: "sites_inscrits_classes", label: "Sites Inscrits/Classés" },
        { value: "travaux", label: "Travaux" },
        { value: "tub", label: "TUB" },
        { value: "types_usager", label: "Types d'Usagers" },
        { value: "types_usager_cible", label: "Types d'Usagers – Ciblé" },
        { value: "zones_humides", label: "Zones Humides" },
        { value: "hors_theme", label: "Hors Thème" }
    ];

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
        { value: "r27", label: "r27 - Bourgogne-Franche-Comté" }
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

    function setupCombobox(inputEl, toggleBtn, dropdownEl, getListDataFn) {
        function render(filterText = '') {
            dropdownEl.innerHTML = '';
            const search = filterText.toLowerCase().trim();
            const listData = getListDataFn();
            const filtered = listData.filter(p => 
                p.label.toLowerCase().includes(search) || p.value.toLowerCase().includes(search)
            );

            if (filtered.length === 0) {
                const noRes = document.createElement('div');
                noRes.className = 'dropdown-option-empty';
                noRes.textContent = 'Aucun élément trouvé';
                dropdownEl.appendChild(noRes);
                return;
            }

            filtered.forEach(p => {
                const opt = document.createElement('div');
                opt.className = 'dropdown-option';
                opt.dataset.value = p.value;
                opt.textContent = p.label;
                opt.addEventListener('click', () => {
                    inputEl.value = p.value;
                    dropdownEl.classList.add('hidden');
                });
                dropdownEl.appendChild(opt);
            });
        }

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isHidden = dropdownEl.classList.contains('hidden');
            if (isHidden) {
                document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
                render();
                dropdownEl.classList.remove('hidden');
                inputEl.focus();
            } else {
                dropdownEl.classList.add('hidden');
            }
        });

        inputEl.addEventListener('input', () => {
            render(inputEl.value);
            dropdownEl.classList.remove('hidden');
        });

        inputEl.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
            render(inputEl.value);
            dropdownEl.classList.remove('hidden');
        });
    }

    // Initialisation des comboboxes
    setupCombobox(inputProfil, btnToggleProfils, profilsDropdown, () => profilesList);
    setupCombobox(inputCode, btnToggleCodes, codesDropdown, getActiveCodesList);
    setupCombobox(inputUsager, btnToggleUsagers, usagersDropdown, () => usagersList);

    // Hide dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-container')) {
            document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
        }
    });

    selectEchelle.addEventListener('change', () => {
        const val = selectEchelle.value;
        if (val === 'departement') {
            inputCode.value = '21';
            inputCode.placeholder = 'ex : 21';
            codeHelper.textContent = 'Exemples : 21, 27, 39';
        } else if (val === 'region') {
            inputCode.value = '27';
            inputCode.placeholder = 'ex : r27';
            codeHelper.textContent = 'Exemples : 27, 44 (ou r27, r44)';
        } else if (val === 'bmi') {
            inputCode.value = 'BMI-NEC';
            inputCode.placeholder = 'ex : BMI-NEC';
            codeHelper.textContent = 'Codes possibles : BMI-NEC, BMI-SO, BMI-SE, BMI-NO, BMI-IFE, BMI-IFO, BMI-TIP';
        } else if (val === 'national') {
            inputCode.value = 'FR';
            inputCode.placeholder = 'ex : FR';
            codeHelper.textContent = 'Code national : FR';
        }
    });

    // --- LEAFLET MAP INITIALIZATION ---
    // France Center
    const map = L.map('map').setView([46.2276, 2.2137], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);

    // Color definitions for status markers
    function getMarkerColor(resultat) {
        if (!resultat) return '#64748B'; // Grey (En attente / Autre)
        const res = resultat.toLowerCase();
        if (res.includes('conforme') && !res.includes('non')) {
            return '#10B981'; // Green
        } else if (res.includes('infraction') || res.includes('non') || res.includes('manquement')) {
            return '#EF4444'; // Red
        }
        return '#F59E0B'; // Orange (warning or pending)
    }

    function loadData() {
        btnUpdate.disabled = true;
        btnUpdate.textContent = 'Chargement...';

        const params = {
            profil: inputProfil.value,
            'date-deb': document.getElementById('date-deb').value,
            'date-fin': document.getElementById('date-fin').value,
            echelle: selectEchelle.value,
            code: inputCode.value,
            'type-usager': document.getElementById('type-usager').value
        };

        fetch('/api/data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erreur serveur lors de la récupération des données.');
            }
            return response.json();
        })
        .then(res => {
            // Update stats indicators
            valControles.textContent = res.stats.total_controles;
            valPej.textContent = res.stats.total_pej;
            valPa.textContent = res.stats.total_pa;
            valPve.textContent = res.stats.total_pve;

            // Update map markers
            markersGroup.clearLayers();
            if (boundaryLayer) {
                map.removeLayer(boundaryLayer);
                boundaryLayer = null;
            }
            const coordinates = [];

            if (res.points && res.points.length > 0) {
                res.points.forEach(pt => {
                    const lat = parseFloat(pt.y);
                    const lng = parseFloat(pt.x);

                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        coordinates.push([lat, lng]);

                        const color = getMarkerColor(pt.resultat);
                        const marker = L.circleMarker([lat, lng], {
                            radius: 6,
                            fillColor: color,
                            color: '#FFFFFF',
                            weight: 1.5,
                            opacity: 1,
                            fillOpacity: 0.8
                        });

                        const popupContent = `
                            <strong>Contrôle OSCEAN</strong><br>
                            ID: ${pt.dc_id || 'N/A'}<br>
                            Date: ${pt.date_ctrl || 'N/A'}<br>
                            Résultat: <span style="font-weight:bold;color:${color}">${pt.resultat || 'N/A'}</span><br>
                            Domaine: ${pt.domaine || 'N/A'}<br>
                            Thème: ${pt.theme || 'N/A'}<br>
                            Usager: ${pt.type_usager || 'N/A'}<br>
                            Commune: ${pt.nom_commun || 'N/A'}
                        `;
                        marker.bindPopup(popupContent);
                        markersGroup.addLayer(marker);
                    }
                });
            }

            // Render boundary if available
            if (res.geojson) {
                boundaryLayer = L.geoJSON(res.geojson, {
                    style: {
                        color: '#003A76',
                        weight: 2.5,
                        opacity: 0.85,
                        fillColor: '#003A76',
                        fillOpacity: 0.05
                    }
                }).addTo(map);
            }

            // Center/zoom map
            if (boundaryLayer) {
                map.fitBounds(boundaryLayer.getBounds(), { padding: [20, 20] });
            } else if (coordinates.length > 0) {
                const bounds = L.latLngBounds(coordinates);
                map.fitBounds(bounds, { padding: [30, 30] });
            } else {
                // If no points, reset view to France
                map.setView([46.2276, 2.2137], 6);
            }

            // --- CHARTS GENERATION ---
            // 1. Aggregate results
            const resultsCounts = { "Conforme": 0, "Non-conforme": 0, "En attente": 0 };
            const domainsCounts = {};

            if (res.points && res.points.length > 0) {
                res.points.forEach(pt => {
                    const resText = pt.resultat ? pt.resultat.toLowerCase() : '';
                    if (resText.includes('conforme') && !resText.includes('non')) {
                        resultsCounts["Conforme"]++;
                    } else if (resText.includes('infraction') || resText.includes('non') || resText.includes('manquement')) {
                        resultsCounts["Non-conforme"]++;
                    } else {
                        resultsCounts["En attente"]++;
                    }

                    const domain = pt.domaine || 'Hors domaine';
                    domainsCounts[domain] = (domainsCounts[domain] || 0) + 1;
                });
            }

            // Render Results Chart (Doughnut)
            if (chartResults) {
                chartResults.destroy();
            }
            const ctxResults = document.getElementById('chart-results').getContext('2d');
            chartResults = new Chart(ctxResults, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(resultsCounts),
                    datasets: [{
                        data: Object.values(resultsCounts),
                        backgroundColor: ['#10B981', '#EF4444', '#64748B'],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } }
                    }
                }
            });

            // Render Domains Chart (Bar)
            if (chartDomains) {
                chartDomains.destroy();
            }
            
            const sortedDomains = Object.entries(domainsCounts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5);
            
            const ctxDomains = document.getElementById('chart-domains').getContext('2d');
            chartDomains = new Chart(ctxDomains, {
                type: 'bar',
                data: {
                    labels: sortedDomains.map(d => splitLabel(d[0], 25)),
                    datasets: [{
                        label: 'Contrôles',
                        data: sortedDomains.map(d => d[1]),
                        backgroundColor: '#003A76',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { beginAtZero: true, ticks: { font: { size: 9 } } },
                        y: { ticks: { font: { size: 9 } } }
                    }
                }
            });
        })
        .catch(err => {
            if (isUnloading) return;
            console.error(err);
            alert('Impossible de charger les données : ' + err.message);
        })
        .finally(() => {
            btnUpdate.disabled = false;
            btnUpdate.textContent = 'Charger les données';
        });
    }

    btnUpdate.addEventListener('click', loadData);

    // Initial load
    loadData();
});
