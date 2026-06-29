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

    // État pour le tableau détaillé des contrôles
    let activePoints = [];
    let currentTablePage = 1;
    const tableRowsPerPage = 25;
    let tableSortColumn = '';
    let tableSortAsc = true;
    let isTableExpanded = false;

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
            } else {
                compareDatesContainer.classList.add('hidden');
            }
        });
    }

    fetch('/api/profils')
        .then(res => res.json())
        .then(data => {
            const selectProfil = document.getElementById('profil-select');
            if (selectProfil && Array.isArray(data)) {
                selectProfil.innerHTML = '';
                window.profilsMetadata = {};
                data.forEach(p => {
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
                warnings.push("Le périmètre géographique est verrouillé sur le Parc National de Forêts (Départements 21 et 52).");
            } else {
                if (selectEchelle) {
                    selectEchelle.disabled = false;
                    // Reset to default if it was pnf
                    if (selectEchelle.value === 'pnf') selectEchelle.value = 'departement';
                }
                if (inputCode) {
                    inputCode.disabled = false;
                    inputCode.placeholder = 'Rechercher ou sélectionner...';
                }
                if (btnToggleCodes) btnToggleCodes.disabled = false;
                if (pnfDeptContainer) pnfDeptContainer.classList.add('hidden');
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
        { value: "07", label: "07 - Ordèche" },
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
            inputCode.value = 'FR';
            inputCode.placeholder = 'ex : FR';
            codeHelper.textContent = 'Code national : FR';
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

    L.tileLayer('https://data.geopf.fr/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.ign.fr/">IGN</a>'
    }).addTo(map);

    const markersGroup = L.layerGroup(); // Les points individuels sans cluster (si besoin de bascule)
    const markersClusterGroup = L.markerClusterGroup({ 
        chunkedLoading: true,
        disableClusteringAtZoom: 14,
        maxClusterRadius: function (zoom) { return (zoom < 8) ? 80 : (zoom < 11) ? 50 : 30; }
    }).addTo(map);
    const pejGroup = L.markerClusterGroup({
        chunkedLoading: true,
        disableClusteringAtZoom: 14,
        maxClusterRadius: function (zoom) { return (zoom < 8) ? 80 : (zoom < 11) ? 50 : 30; },
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            return L.divIcon({
                html: `<div style="background-color:rgba(59, 130, 246, 0.85);border:2px solid white;border-radius:50%;text-align:center;color:white;font-weight:bold;line-height:26px;width:30px;height:30px;box-shadow: 0 1px 3px rgba(0,0,0,0.3);">${count}</div>`,
                className: '',
                iconSize: [30, 30]
            });
        }
    }).addTo(map);

    const paGroup = L.markerClusterGroup({
        chunkedLoading: true,
        disableClusteringAtZoom: 14,
        maxClusterRadius: function (zoom) { return (zoom < 8) ? 80 : (zoom < 11) ? 50 : 30; },
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            return L.divIcon({
                html: `<div style="background-color:rgba(139, 92, 246, 0.85);border:2px solid white;border-radius:50%;text-align:center;color:white;font-weight:bold;line-height:26px;width:30px;height:30px;box-shadow: 0 1px 3px rgba(0,0,0,0.3);">${count}</div>`,
                className: '',
                iconSize: [30, 30]
            });
        }
    }).addTo(map);

    const pveGroup = L.markerClusterGroup({
        chunkedLoading: true,
        disableClusteringAtZoom: 14,
        maxClusterRadius: function (zoom) { return (zoom < 8) ? 80 : (zoom < 11) ? 50 : 30; },
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            return L.divIcon({
                html: `<div style="background-color:rgba(249, 115, 22, 0.85);border:2px solid white;border-radius:50%;text-align:center;color:white;font-weight:bold;line-height:26px;width:30px;height:30px;box-shadow: 0 1px 3px rgba(0,0,0,0.3);">${count}</div>`,
                className: '',
                iconSize: [30, 30]
            });
        }
    }).addTo(map);
    let heatmapLayer = null;

    // Contrôle des couches
    const baseMaps = {};
    const overlayMaps = {
        "Contrôles (Clusters/Points)": markersClusterGroup,
        "PEJ": pejGroup,
        "PA": paGroup,
        "PVe": pveGroup
    };
    L.control.layers(baseMaps, overlayMaps, { collapsed: false, position: 'topright' }).addTo(map);

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

    function loadData() {
        btnUpdate.disabled = true;
        btnUpdate.innerHTML = `
            <style>@keyframes btnspin { 100% { transform: rotate(360deg); } }</style>
            <svg viewBox="0 0 24 24" style="width:18px;height:18px;margin-right:8px;vertical-align:-4px;animation: btnspin 1s linear infinite; stroke: white; fill: none; stroke-width: 3; stroke-linecap: round;">
                <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" />
                <path d="M12 2 A10 10 0 0 1 22 12" stroke="white" />
            </svg>
            Chargement...`;

        const isCompare = compareActiveCheck && compareActiveCheck.checked;

        const getParams = (isComparePeriod = false) => {
            const debEl = isComparePeriod ? compareDateDebEl : dateDebEl;
            const finEl = isComparePeriod ? compareDateFinEl : dateFinEl;
            const selectProfil = document.getElementById('profil-select');
            const pnfDeptEl = document.getElementById('pnf-dept-select');
            return {
                profil: selectProfil ? selectProfil.value : 'global',
                pnf_dept: pnfDeptEl ? pnfDeptEl.value : '',
                'date-deb': debEl ? debEl.value : '',
                'date-fin': finEl ? finEl.value : '',
                echelle: selectEchelle.value,
                code: inputCode.value,
                'type-usager': inputUsager.getSelectedValues ? inputUsager.getSelectedValues() : (inputUsager.value ? [inputUsager.value] : []),
                'domaines': inputDomaineSNC.getSelectedValues ? inputDomaineSNC.getSelectedValues() : (inputDomaineSNC.value ? [inputDomaineSNC.value] : []),
                'themes': inputThemeSNC.getSelectedValues ? inputThemeSNC.getSelectedValues() : (inputThemeSNC.value ? [inputThemeSNC.value] : []),
                'types_action': inputTypeAction.getSelectedValues ? inputTypeAction.getSelectedValues() : (inputTypeAction.value ? [inputTypeAction.value] : []),
                'resultats': inputResultat.getSelectedValues ? inputResultat.getSelectedValues() : [],
                'commune': inputCommune ? inputCommune.value.trim() : ''
            };
        };

        const reqN = fetch('/api/data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getParams(false))
        }).then(async response => {
            if (!response.ok) {
                let errMsg = 'Erreur lors du chargement de la période principale';
                try {
                    const data = await response.json();
                    if (data.error) errMsg += ' : ' + data.error;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return response.json();
        });

        const reqN1 = isCompare ? fetch('/api/data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getParams(true))
        }).then(async response => {
            if (!response.ok) {
                let errMsg = 'Erreur lors du chargement de la période de comparaison';
                try {
                    const data = await response.json();
                    if (data.error) errMsg += ' : ' + data.error;
                } catch (e) {}
                throw new Error(errMsg);
            }
            return response.json();
        }) : Promise.resolve(null);

        Promise.all([reqN, reqN1])
        .then(([resN, resN1]) => {
            // Mémorisation de l'état (localStorage et URL)
            saveStateToLocalStorage();
            updateURLWithState();

            // Rendu des valeurs d'indicateurs clés
            function updateStatElement(elementId, valN, valN1) {
                const el = document.getElementById(elementId);
                if (!el) return;
                if (valN1 === undefined || valN1 === null) {
                    el.innerHTML = valN;
                } else {
                    const pct = valN1 > 0 ? ((valN - valN1) / valN1 * 100).toFixed(1) : 0;
                    const arrow = valN > valN1 ? '▲' : (valN < valN1 ? '▼' : '■');
                    const color = valN > valN1 ? '#10B981' : (valN < valN1 ? '#EF4444' : '#64748B');
                    el.innerHTML = `<span style="font-size: 16px;">${valN}</span> <div style="font-size: 9px; font-weight: 600; color: ${color}; margin-top: 2px;">vs ${valN1} (${pct >= 0 ? '+' : ''}${pct}% ${arrow})</div>`;
                }
            }

            updateStatElement('val-controles', resN.stats.total_controles, isCompare ? resN1.stats.total_controles : null);
            updateStatElement('val-pej', resN.stats.total_pej, isCompare ? resN1.stats.total_pej : null);
            updateStatElement('val-pa', resN.stats.total_pa, isCompare ? resN1.stats.total_pa : null);
            updateStatElement('val-pve', resN.stats.total_pve, isCompare ? resN1.stats.total_pve : null);

            // Mise à jour des points actifs et du compteur (uniquement basés sur la période principale N)
            activePoints = resN.points || [];
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
            markersClusterGroup.clearLayers();
            pejGroup.clearLayers();
            paGroup.clearLayers();
            pveGroup.clearLayers();
            if (heatmapLayer) {
                map.removeLayer(heatmapLayer);
                heatmapLayer = null;
            }
            if (boundaryLayer) {
                map.removeLayer(boundaryLayer);
                boundaryLayer = null;
            }
            const coordinates = [];
            const heatData = [];
            const isHeatmapMode = document.querySelector('input[name="map-mode"]:checked')?.value === 'heatmap';
            
            const newMarkers = [];
            const newPejMarkers = [];
            const newPaMarkers = [];
            const newPveMarkers = [];

            if (resN.points && resN.points.length > 0) {
                resN.points.forEach(pt => {
                    const lat = parseFloat(pt.y);
                    const lng = parseFloat(pt.x);

                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        coordinates.push([lat, lng]);
                        heatData.push([lat, lng, 1.0]);

                        const color = getMarkerColor(pt.resultat);
                        const marker = L.circleMarker([lat, lng], {
                            radius: 6,
                            fillColor: color,
                            color: '#FFFFFF',
                            weight: 1.5,
                            opacity: 1,
                            fillOpacity: 1
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
                        newMarkers.push(marker);
                    }
                });
            }

            if (isHeatmapMode) {
                map.removeLayer(markersClusterGroup);
                heatmapLayer = L.heatLayer(heatData, {
                    radius: 20,
                    blur: 15,
                    maxZoom: 12
                }).addTo(map);
            } else {
                if (!map.hasLayer(markersClusterGroup)) {
                    markersClusterGroup.addTo(map);
                }
            }
            // Render procedure markers (if any)
            if (resN.procedures && resN.procedures.length > 0) {
                resN.procedures.forEach(p => {
                    let lat = parseFloat(p.y);
                    let lng = parseFloat(p.x);
                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        let procColor = '#3B82F6';
                        const ptype = (p.type || '').toUpperCase();
                        let targetGroup = pejGroup;
                        if (ptype.includes('PEJ')) {
                            procColor = '#3B82F6';
                            targetGroup = pejGroup;
                        } else if (ptype.includes('PA')) {
                            procColor = '#8B5CF6';
                            targetGroup = paGroup;
                        } else if (ptype.includes('PVE')) {
                            procColor = '#F97316';
                            targetGroup = pveGroup;
                        }

                        const marker = L.circleMarker([lat, lng], {
                            radius: 6,
                            color: procColor,
                            fillColor: procColor,
                            fillOpacity: 1,
                            weight: 1.5,
                            interactive: true
                        });
                        const popup = `
                            <strong>${p.type}</strong><br>
                            N° Oscean : ${p.dc_id || 'N/A'}<br>
                            Date: ${p.date_ctrl || 'N/A'}<br>
                            Type d'action de la ${p.type} : ${p.type_action || 'Non renseigné'}<br>
                            Usager visé : ${p.type_usager || 'Non renseigné'}
                        `;
                        marker.bindPopup(popup);
                        if (targetGroup === pejGroup) newPejMarkers.push(marker);
                        else if (targetGroup === paGroup) newPaMarkers.push(marker);
                        else if (targetGroup === pveGroup) newPveMarkers.push(marker);
                    }
                });
            }

            // Render points N-1
            if (isCompare && resN1 && resN1.points && resN1.points.length > 0) {
                resN1.points.forEach(pt => {
                    const lat = parseFloat(pt.y);
                    const lng = parseFloat(pt.x);

                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        const color = getMarkerColor(pt.resultat);
                        const marker = L.circleMarker([lat, lng], {
                            radius: 6,
                            fillColor: color,
                            color: '#FFFFFF',
                            weight: 1.5,
                            opacity: 0.5,
                            fillOpacity: 0.4
                        });

                        const popupContent = `
                            <strong>Contrôle OSCEAN (N-1)</strong><br>
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
                        newMarkers.push(marker);
                    }
                });
            }

            // Render procedure markers N-1
            if (isCompare && resN1 && resN1.procedures && resN1.procedures.length > 0) {
                resN1.procedures.forEach(p => {
                    let lat = parseFloat(p.y);
                    let lng = parseFloat(p.x);
                    if (!isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0) {
                        let procColor = '#3B82F6';
                        const ptype = (p.type || '').toUpperCase();
                        let targetGroup = pejGroup;
                        if (ptype.includes('PEJ')) {
                            procColor = '#3B82F6';
                            targetGroup = pejGroup;
                        } else if (ptype.includes('PA')) {
                            procColor = '#8B5CF6';
                            targetGroup = paGroup;
                        } else if (ptype.includes('PVE')) {
                            procColor = '#F97316';
                            targetGroup = pveGroup;
                        }

                        const marker = L.circleMarker([lat, lng], {
                            radius: 6,
                            color: procColor,
                            fillColor: procColor,
                            opacity: 0.5,
                            fillOpacity: 0.35,
                            weight: 1.5,
                            interactive: true
                        });
                        const popup = `
                            <strong>${p.type} (N-1)</strong><br>
                            N° Oscean : ${p.dc_id || 'N/A'}<br>
                            Date: ${p.date_ctrl || 'N/A'}<br>
                            Type d'action de la ${p.type} : ${p.type_action || 'Non renseigné'}<br>
                            Usager visé : ${p.type_usager || 'Non renseigné'}
                        `;
                        marker.bindPopup(popup);
                        if (targetGroup === pejGroup) newPejMarkers.push(marker);
                        else if (targetGroup === paGroup) newPaMarkers.push(marker);
                        else if (targetGroup === pveGroup) newPveMarkers.push(marker);
                    }
                });
            }
            
            // Ajout en masse aux clusters
            markersClusterGroup.addLayers(newMarkers);
            pejGroup.addLayers(newPejMarkers);
            paGroup.addLayers(newPaMarkers);
            pveGroup.addLayers(newPveMarkers);

            // Render boundary if available
            if (resN.geojson) {
                boundaryLayer = L.geoJSON(resN.geojson, {
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
            const chartData = resN.charts || {};

            const tooltipPercentageCallback = {
                label: function(context) {
                    let label = context.dataset.label || '';
                    if (label) {
                        label += ' : ';
                    } else {
                        label = context.label ? context.label + ' : ' : '';
                    }
                    const val = context.raw;
                    const total = context.dataset.data.reduce((sum, v) => sum + (v || 0), 0);
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

            const resultsDatasets = [{
                data: Object.values(resultsN),
                backgroundColor: ['#53AB60', '#EF4444', '#64748B'],
                borderWidth: 1,
                label: 'Période N'
            }];

            if (isCompare && resultsN1) {
                resultsDatasets.push({
                    data: Object.values(resultsN1),
                    backgroundColor: ['rgba(83, 171, 96, 0.5)', 'rgba(239, 68, 68, 0.5)', 'rgba(100, 116, 139, 0.5)'],
                    borderWidth: 1,
                    label: 'Période N-1'
                });
            }

            const ctxResults = document.getElementById('chart-results').getContext('2d');
            chartResults = new Chart(ctxResults, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(resultsN),
                    datasets: resultsDatasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: tooltipPercentageCallback
                        }
                    }
                }
            });

            // Populate custom results legend
            const legendResults = document.getElementById('legend-results');
            if (legendResults) {
                legendResults.innerHTML = '';
                const resultsLabels = Object.keys(resultsN);
                const resultsColors = ['#53AB60', '#EF4444', '#64748B'];
                resultsLabels.forEach((label, idx) => {
                    const color = resultsColors[idx] || '#64748B';
                    legendResults.innerHTML += `
                        <div style="display: flex; align-items: center; gap: 5px; font-size: 9px; font-weight: 500; color: var(--color-text-dark);">
                            <span style="display: inline-block; width: 8px; height: 8px; background-color: ${color}; border-radius: 50%; flex-shrink: 0;"></span>
                            <span>${label}</span>
                        </div>
                    `;
                });
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

            const usagersDatasets = [{
                data: Object.values(usagersN),
                backgroundColor: usagersColors,
                borderWidth: 1,
                label: 'Période N'
            }];

            if (isCompare && usagersN1) {
                const alignedN1Data = rawLabels.map(lbl => usagersN1[lbl] || 0);
                usagersDatasets.push({
                    data: alignedN1Data,
                    backgroundColor: usagersColors.map(c => c + '80'),
                    borderWidth: 1,
                    label: 'Période N-1'
                });
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
                            const matched = usagersList.find(u => u.label.toLowerCase().includes(shortLabel.toLowerCase()) || u.value.toLowerCase().includes(shortLabel.toLowerCase()));
                            if (matched && matched.value) {
                                if (inputUsager.setSelectedValues) {
                                    inputUsager.setSelectedValues([matched.value]);
                                } else {
                                    inputUsager.value = matched.value;
                                }
                                loadData();
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: tooltipPercentageCallback
                        }
                    }
                }
            });

            // Populate custom usagers legend
            const legendUsagers = document.getElementById('legend-usagers');
            if (legendUsagers) {
                legendUsagers.innerHTML = '';
                usagersLabels.forEach((label, idx) => {
                    const color = usagersColors[idx];
                    legendUsagers.innerHTML += `
                        <div style="display: flex; align-items: center; gap: 5px; font-size: 9px; font-weight: 500; color: var(--color-text-dark);">
                            <span style="display: inline-block; width: 8px; height: 8px; background-color: ${color}; border-radius: 50%; flex-shrink: 0;"></span>
                            <span>${label}</span>
                        </div>
                    `;
                });
            }

            // 3. Domaines d'Activité (Barres groupées ou empilées par département)
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
            const domainLabels = sortedDomainsN.map(d => splitLabel(d[0], 25));

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

            let domainsDatasets = [];
            // Palette colorée distincte (Type D3 Category10) pour bien différencier les départements
            const deptColorsDom = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
            const deptColorsDomN1 = ['#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'];
            
            if (isRegion) {
                const allDepts = new Set();
                sortedDomainsN.forEach(([_, counts]) => {
                    if (typeof counts === 'object') Object.keys(counts).forEach(d => allDepts.add(d));
                });
                const depts = Array.from(allDepts).sort();
                
                depts.forEach((dept, idx) => {
                    domainsDatasets.push({
                        label: `${getDeptName(dept)} N`,
                        data: sortedDomainsN.map(([_, counts]) => (counts[dept] || 0)),
                        backgroundColor: deptColorsDom[idx % deptColorsDom.length],
                        borderColor: '#ffffff',
                        borderWidth: 1,
                        stack: 'Stack N',
                        borderRadius: 4,
                        barThickness: isCompare ? 16 : 24
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
                            barThickness: 16
                        });
                    });
                }
            } else {
                domainsDatasets.push({
                    label: 'Période N',
                    data: sortedDomainsN.map(d => getDomainTotal(d[1])),
                    backgroundColor: '#003A76',
                    borderRadius: 4,
                    barThickness: isCompare ? 8 : 12
                });

                if (isCompare && domainsN1) {
                    const alignedN1 = sortedDomainsN.map(d => getDomainTotal(domainsN1[d[0]] || 0));
                    domainsDatasets.push({
                        label: 'Période N-1',
                        data: alignedN1,
                        backgroundColor: '#93C5FD',
                        borderRadius: 4,
                        barThickness: 8
                    });
                }
            }

            const domainTotalLines = domainLabels.reduce((sum, lines) => sum + lines.length, 0);
            const domainHeight = Math.max(100, 45 + (domainLabels.length * (isCompare ? 36 : 24)) + (domainTotalLines - domainLabels.length) * 11);
            const wrapperDomains = document.getElementById('wrapper-domains');
            if (wrapperDomains) {
                wrapperDomains.style.height = `${domainHeight}px`;
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
                            if (inputDomaineSNC.setSelectedValues) {
                                inputDomaineSNC.setSelectedValues([domainName]);
                            } else {
                                inputDomaineSNC.value = domainName;
                            }
                            loadData();
                        }
                    },
                    plugins: {
                        legend: { display: isCompare || isRegion, position: 'top', labels: { boxWidth: 10, font: { size: 9 } } },
                        tooltip: {
                            callbacks: tooltipPercentageCallback
                        }
                    },
                    scales: {
                        x: { stacked: isRegion, beginAtZero: true, ticks: { font: { size: 9 } } },
                        y: { 
                            stacked: isRegion,
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
            const themeLabels = sortedThemesN.map(d => splitLabel(d[0], 25));

            let themesDatasets = [];
            // Palette colorée distincte (Type D3 Category10) pour bien différencier les départements
            const deptColorsTh = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
            const deptColorsThN1 = ['#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'];
            
            if (isRegion) {
                const allDepts = new Set();
                sortedThemesN.forEach(([_, counts]) => {
                    if (typeof counts === 'object') Object.keys(counts).forEach(d => allDepts.add(d));
                });
                const depts = Array.from(allDepts).sort();
                
                depts.forEach((dept, idx) => {
                    themesDatasets.push({
                        label: `${getDeptName(dept)} N`,
                        data: sortedThemesN.map(([_, counts]) => (counts[dept] || 0)),
                        backgroundColor: deptColorsTh[idx % deptColorsTh.length],
                        borderColor: '#ffffff',
                        borderWidth: 1,
                        stack: 'Stack N',
                        borderRadius: 4,
                        barThickness: isCompare ? 16 : 24
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
                            barThickness: 16
                        });
                    });
                }
            } else {
                themesDatasets.push({
                    label: 'Période N',
                    data: sortedThemesN.map(d => getDomainTotal(d[1])),
                    backgroundColor: '#4296CE',
                    borderRadius: 4,
                    barThickness: isCompare ? 8 : 12
                });

                if (isCompare && themesN1) {
                    const alignedN1 = sortedThemesN.map(d => getDomainTotal(themesN1[d[0]] || 0));
                    themesDatasets.push({
                        label: 'Période N-1',
                        data: alignedN1,
                        backgroundColor: '#FCA5A5',
                        borderRadius: 4,
                        barThickness: 8
                    });
                }
            }

            const themeTotalLines = themeLabels.reduce((sum, lines) => sum + lines.length, 0);
            const themeHeight = Math.max(100, 45 + (themeLabels.length * (isCompare ? 36 : 24)) + (themeTotalLines - themeLabels.length) * 11);
            const wrapperThemes = document.getElementById('wrapper-themes');
            if (wrapperThemes) {
                wrapperThemes.style.height = `${themeHeight}px`;
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
                            if (inputThemeSNC.setSelectedValues) {
                                inputThemeSNC.setSelectedValues([themeName]);
                            } else {
                                inputThemeSNC.value = themeName;
                            }
                            loadData();
                        }
                    },
                    plugins: {
                        legend: { display: isCompare || isRegion, position: 'top', labels: { boxWidth: 10, font: { size: 9 } } },
                        tooltip: {
                            callbacks: tooltipPercentageCallback
                        }
                    },
                    scales: {
                        x: { stacked: isRegion, beginAtZero: true, ticks: { font: { size: 9 } } },
                        y: { 
                            stacked: isRegion,
                            grid: { display: false },
                            ticks: { autoSkip: false, font: { size: 9 } } 
                        }
                    }
                }
            });

            // 5. Saisonnalité de l'activité (Double Courbe Line)
            if (chartSeasonality) {
                chartSeasonality.destroy();
            }
            const monthsLabels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sept', 'Oct', 'Nov', 'Déc'];
            const seasonalityN = chartData.seasonality || { controls: Array(12).fill(0), infractions: Array(12).fill(0) };
            const seasonalityN1 = isCompare ? (resN1.charts.seasonality || { controls: Array(12).fill(0), infractions: Array(12).fill(0) }) : null;

            const seasonalityDatasets = [
                {
                    label: 'Contrôles (N)',
                    data: seasonalityN.controls,
                    borderColor: '#003A76',
                    backgroundColor: 'rgba(0, 58, 118, 0.05)',
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'Infractions (N)',
                    data: seasonalityN.infractions,
                    borderColor: '#EF4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.05)',
                    fill: true,
                    tension: 0.3
                }
            ];

            if (isCompare && seasonalityN1) {
                seasonalityDatasets.push({
                    label: 'Contrôles (N-1)',
                    data: seasonalityN1.controls,
                    borderColor: '#93C5FD',
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3
                });
                seasonalityDatasets.push({
                    label: 'Infractions (N-1)',
                    data: seasonalityN1.infractions,
                    borderColor: '#FCA5A5',
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3
                });
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
        })
        .catch(err => {
            if (isUnloading) return;
            console.error(err);
            alert('Impossible de charger les données : ' + err.message);
        })
        .finally(() => {
            btnUpdate.disabled = false;
            btnUpdate.innerHTML = 'Charger les données';
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

    function renderTable() {
        const tableBody = document.getElementById('table-body');
        if (!tableBody) return;
        
        tableBody.innerHTML = '';
        
        let data = [...activePoints];
        
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
        
        if (pageData.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--color-text-muted); padding: 20px;">Aucun contrôle à afficher.</td></tr>`;
        } else {
            pageData.forEach(row => {
                const tr = document.createElement('tr');
                const color = getMarkerColor(row.resultat);
                tr.innerHTML = `
                    <td style="padding: 6px 8px;">${row.dc_id || ''}</td>
                    <td style="padding: 6px 8px;">${row.date_ctrl || ''}</td>
                    <td style="padding: 6px 8px; font-weight: 600; color: ${color};">${row.resultat || ''}</td>
                    <td style="padding: 6px 8px;">${row.domaine || ''}</td>
                    <td style="padding: 6px 8px;">${row.theme || ''}</td>
                    <td style="padding: 6px 8px;">${row.type_usager || ''}</td>
                    <td style="padding: 6px 8px;">${row.nom_commun || ''}</td>
                `;
                tableBody.appendChild(tr);
            });
        }
        
        // Mise à jour de l'UI pagination
        const infoEl = document.getElementById('table-pagination-info');
        if (infoEl) {
            infoEl.textContent = `Affichage de ${totalRows ? startIndex + 1 : 0} à ${endIndex} sur ${totalRows} contrôle${totalRows > 1 ? 's' : ''} (Page ${currentTablePage}/${totalPages})`;
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
            const totalPages = Math.max(1, Math.ceil(activePoints.length / tableRowsPerPage));
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
            if (activePoints.length === 0) {
                alert('Aucun contrôle à exporter.');
                return;
            }
            
            const headers = ['ID', 'Date', 'Resultat', 'Domaine', 'Theme', 'Type Usager', 'Commune', 'X', 'Y'];
            const rows = activePoints.map(row => [
                row.dc_id || '',
                row.date_ctrl || '',
                row.resultat || '',
                row.domaine || '',
                row.theme || '',
                row.type_usager || '',
                row.nom_commun || '',
                row.x || 0.0,
                row.y || 0.0
            ]);
            
            const csvContent = "\uFEFF" + [
                headers.join(';'),
                ...rows.map(r => r.map(val => `"${String(val).replace(/"/g, '""')}"`).join(';'))
            ].join('\n');
            
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', `export_controles_${new Date().toISOString().slice(0,10)}.csv`);
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

            if (inputCommune) inputCommune.value = '';
            
            loadData();
        });
    }

    // Gestion du basculement du mode carte (Points / Chaleur)
    document.querySelectorAll('input[name="map-mode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            const isHeatmapMode = radio.value === 'heatmap';
            if (isHeatmapMode) {
                if (map.hasLayer(markersClusterGroup)) {
                    map.removeLayer(markersClusterGroup);
                }
                const heatData = activePoints
                    .map(pt => [parseFloat(pt.y), parseFloat(pt.x), 1.0])
                    .filter(coords => !isNaN(coords[0]) && !isNaN(coords[1]) && coords[0] !== 0 && coords[1] !== 0);
                
                if (heatmapLayer) {
                    map.removeLayer(heatmapLayer);
                }
                heatmapLayer = L.heatLayer(heatData, {
                    radius: 20,
                    blur: 15,
                    maxZoom: 12
                }).addTo(map);
            } else {
                if (heatmapLayer) {
                    map.removeLayer(heatmapLayer);
                    heatmapLayer = null;
                }
                if (!map.hasLayer(markersClusterGroup)) {
                    markersClusterGroup.addTo(map);
                }
            }
        });
    });

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
            'compare-date-fin': compareDateFinEl ? compareDateFinEl.value : ''
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
            const mapCard = document.getElementById('map').closest('.card');
            if (mapCard) {
                mapCard.classList.toggle('map-fullscreen');
                if (mapCard.classList.contains('map-fullscreen')) {
                    btnFullscreenMap.textContent = '🗗 Quitter';
                    btnFullscreenMap.title = 'Quitter le mode plein écran';
                } else {
                    btnFullscreenMap.textContent = '⛶ Plein écran';
                    btnFullscreenMap.title = 'Plein écran';
                }
                // Attendre la transition de rendu et redimensionner la carte Leaflet
                setTimeout(() => {
                    map.invalidateSize();
                }, 200);
            }
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

    const btnPdf = document.getElementById('btn-pdf');
    if (btnPdf) {
        btnPdf.addEventListener('click', () => {
            alert('La génération PDF à partir des données de l\'explorateur sera implémentée ultérieurement.');
        });
    }

    // Chargement initial
    const stateFromURL = loadStateFromURL();
    const stateFromLS = loadStateFromLocalStorage();
    
    if (stateFromURL) {
        applyFiltersState(stateFromURL);
    } else if (stateFromLS) {
        applyFiltersState(stateFromLS);
    }

    loadData();
});
