document.addEventListener('DOMContentLoaded', () => {
    const btnGenerate = document.getElementById('btn-generate');
    const btnClear = document.getElementById('btn-clear');
    const progressBar = document.getElementById('progress-bar');
    const percentText = document.getElementById('percent-text');
    const statusText = document.getElementById('status-text');
    const consoleOutput = document.getElementById('console-output');
    const resultCard = document.getElementById('result-card');

    const selectEchelle = document.getElementById('echelle');
    const inputCode = document.getElementById('code');
    const codeHelper = document.getElementById('code-helper');

    const btnToggleCodes = document.getElementById('btn-toggle-codes');
    const codesDropdown = document.getElementById('codes-dropdown');

    // Combobox Profils de bilan
    const inputProfil = document.getElementById('profil');
    const btnToggleProfils = document.getElementById('btn-toggle-profils');
    const profilsDropdown = document.getElementById('profils-dropdown');

    let profilesList = [];
    
    fetch('/api/profils')
        .then(res => res.json())
        .then(data => {
            if (Array.isArray(data)) {
                profilesList = data;
            }
        })
        .catch(err => console.error('Erreur chargement profils:', err));

    function renderDropdown(filterText = '') {
        profilsDropdown.innerHTML = '';
        const search = filterText.toLowerCase().trim();
        const filtered = profilesList.filter(p =>
            p.label.toLowerCase().includes(search) || p.value.toLowerCase().includes(search)
        );

        if (filtered.length === 0) {
            const noRes = document.createElement('div');
            noRes.className = 'dropdown-option-empty';
            noRes.textContent = 'Aucun profil trouvé';
            profilsDropdown.appendChild(noRes);
            return;
        }

        filtered.forEach(p => {
            const opt = document.createElement('div');
            opt.className = 'dropdown-option';
            opt.dataset.value = p.value;
            opt.textContent = p.label;
            opt.addEventListener('click', () => {
                inputProfil.value = p.value;
                profilsDropdown.classList.add('hidden');
            });
            profilsDropdown.appendChild(opt);
        });
    }

    // Toggle dropdown on arrow button click
    btnToggleProfils.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = profilsDropdown.classList.contains('hidden');
        if (isHidden) {
            renderDropdown();
            profilsDropdown.classList.remove('hidden');
            inputProfil.focus();
        } else {
            profilsDropdown.classList.add('hidden');
        }
    });

    // Show dropdown and filter on input typing
    inputProfil.addEventListener('input', () => {
        renderDropdown(inputProfil.value);
        profilsDropdown.classList.remove('hidden');
    });

    // Show all when input is focused/clicked
    inputProfil.addEventListener('click', (e) => {
        e.stopPropagation();
        renderDropdown(inputProfil.value);
        profilsDropdown.classList.remove('hidden');
    });

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

    function getActiveCodesList() {
        const scale = selectEchelle.value;
        if (scale === 'departement') return deptsList;
        if (scale === 'region') return regionsList;
        if (scale === 'bmi') return bmisList;
        if (scale === 'national') return nationalList;
        return [];
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
        { value: "Assurer le respect des conditions d'emplois des produits phytopharmaceutiques afin de préserver la qualité de l'eau et des milieux aquatiques (SNC 2.5)", label: "Produits phytosanitaires (SNC 2.5)" },
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

    // Initialisation de la combobox Code géographique et filtres
    setupCombobox(inputCode, btnToggleCodes, codesDropdown, getActiveCodesList);
    setupCombobox(inputUsager, btnToggleUsagers, usagersDropdown, () => usagersList);
    setupCombobox(inputDomaineSNC, btnToggleDomainesSNC, domainesSNCDropdown, () => domainesSNCList);
    setupCombobox(inputThemeSNC, btnToggleThemesSNC, themesSNCDropdown, () => themesSNCList);
    setupCombobox(inputTypeAction, btnToggleTypesAction, typesActionDropdown, () => typesActionList);

    // Hide dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-container')) {
            document.querySelectorAll('.select-dropdown').forEach(d => d.classList.add('hidden'));
        }
    });

    let isRunning = false;

    // Mise à jour dynamique de l'aide géographique
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

    function setProgress(percent, status) {
        progressBar.style.width = `${percent}%`;
        percentText.textContent = `${percent}%`;
        statusText.textContent = status;
        statusText.style.color = "";
    }

    function updateProgressFromLog(line) {
        if (line.includes("session de cache") || line.includes("init_session_cache")) {
            setProgress(10, "Initialisation de la session de cache...");
        } else if (line.includes("dépendance") || line.includes("Vérifie la disponibilité")) {
            setProgress(20, "Vérification des dépendances...");
        } else if (line.includes("run_profiles_batch") || line.includes("Début d'exécution")) {
            setProgress(30, "Lancement du batch de profils...");
        } else if (line.includes("Chargement du profil") || line.includes("YAML")) {
            setProgress(40, "Lecture des configurations...");
        } else if (line.includes("Agrégation") || line.includes("agregations")) {
            setProgress(60, "Agrégation des données...");
        } else if (line.includes("QGIS") || line.includes("cartographie") || line.includes("carte")) {
            setProgress(80, "Production des cartes QGIS...");
        } else if (line.includes("Génération du rapport") || line.includes("reportlab") || line.includes("PDF")) {
            setProgress(90, "Génération du rapport PDF...");
        } else if (line.includes("[SUCCESS]")) {
            setProgress(100, "Génération complétée avec succès !");
        } else if (line.includes("[ERREUR]")) {
            setProgress(100, "Une erreur est survenue.");
            statusText.textContent = "Erreur de génération";
            statusText.style.color = "#D95C4A";
        }
    }

    // Gestion de l'affichage dynamique des sous-options de cartes
    const cartesCheckbox = document.getElementById('cartes');
    const cartesSubOptions = document.getElementById('cartes-sub-options');

    function toggleCartesSubOptions() {
        if (cartesCheckbox.checked) {
            cartesSubOptions.classList.remove('hidden');
        } else {
            cartesSubOptions.classList.add('hidden');
        }
    }
    cartesCheckbox.addEventListener('change', toggleCartesSubOptions);
    toggleCartesSubOptions();

    btnGenerate.addEventListener('click', () => {
        if (isRunning) return;

        isRunning = true;
        btnGenerate.disabled = true;
        btnGenerate.textContent = "Génération en cours...";
        resultCard.classList.add('hidden');

        // Reset progress bar
        progressBar.style.width = '0%';
        percentText.textContent = '0%';
        statusText.textContent = 'Lancement du traitement...';
        consoleOutput.textContent = '> Démarrage de la génération du bilan...\n';

        // Construction de la sélection des cartes
        const cartesSelection = [];
        if (cartesCheckbox.checked) {
            const profilId = inputProfil.value || 'global';
            if (document.getElementById('carte-domaines').checked) {
                cartesSelection.push(`${profilId}_domaines`);
            }
            if (document.getElementById('carte-resultats').checked) {
                cartesSelection.push(`${profilId}_resultats`);
            }
            if (document.getElementById('carte-usagers').checked) {
                cartesSelection.push(`${profilId}_usagers`);
            }
            if (document.getElementById('carte-procedures').checked) {
                cartesSelection.push(`${profilId}_procedures`);
            }

            // Cartes personnalisées depuis la zone de texte
            const customText = document.getElementById('cartes-perso').value;
            const lines = customText.split('\n');
            for (let line of lines) {
                line = line.trim();
                if (line) {
                    cartesSelection.push(line);
                }
            }
        }

        // Collect parameters from form
        const params = {
            profil: inputProfil.value,
            'date-deb': document.getElementById('date-deb').value,
            'date-fin': document.getElementById('date-fin').value,
            echelle: selectEchelle.value,
            code: inputCode.value,
            'type-usager': document.getElementById('type-usager').value,
            'domaines': document.getElementById('domaine-snc').value ? [document.getElementById('domaine-snc').value] : [],
            'themes': document.getElementById('theme-snc').value ? [document.getElementById('theme-snc').value] : [],
            'types_action': document.getElementById('type-action-snc').value ? [document.getElementById('type-action-snc').value] : [],
            cartes: cartesCheckbox.checked,
            cartes_selection: cartesSelection,
            pnf: document.getElementById('pnf').checked,
            brochure: document.getElementById('brochure').checked,
            diffusion: document.getElementById('diffusion').value,
            preset: document.getElementById('preset').value
        };

        // Call backend API
        fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        })
            .then(response => {
                if (!response.body) {
                    throw new Error("Le flux de réponse n'est pas disponible.");
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                function read() {
                    return reader.read().then(({ done, value }) => {
                        if (done) {
                            isRunning = false;
                            btnGenerate.disabled = false;
                            btnGenerate.textContent = "Génération du Bilan";

                            if (consoleOutput.textContent.includes('[SUCCESS]')) {
                                resultCard.classList.remove('hidden');
                            }
                            return;
                        }

                        const chunk = decoder.decode(value, { stream: true });
                        buffer += chunk;

                        const lines = buffer.split('\n');
                        buffer = lines.pop(); // Keep last partial line

                        lines.forEach(line => {
                            if (line.trim()) {
                                consoleOutput.textContent += line + '\n';
                                consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                updateProgressFromLog(line);
                            }
                        });

                        return read();
                    });
                }
                return read();
            })
            .catch(err => {
                isRunning = false;
                btnGenerate.disabled = false;
                btnGenerate.textContent = "Génération du Bilan";
                consoleOutput.textContent += `\n[ERREUR] Impossible de se connecter au serveur : ${err.message}\n`;
                consoleOutput.scrollTop = consoleOutput.scrollHeight;
                setProgress(100, "Erreur de connexion");
                statusText.style.color = "#D95C4A";
            });
    });

    const btnOpenPdf = document.getElementById('btn-open-pdf');
    const btnOpenFolder = document.getElementById('btn-open-folder');

    function openOutput(endpoint) {
        const profil = inputProfil.value;
        const code = inputCode.value;

        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ profil, code })
        })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    alert("Erreur lors de l'ouverture : " + data.error);
                }
            })
            .catch(err => {
                alert("Erreur réseau : " + err.message);
            });
    }

    btnOpenPdf.addEventListener('click', () => openOutput('/api/open-pdf'));
    btnOpenFolder.addEventListener('click', () => openOutput('/api/open-folder'));

    btnClear.addEventListener('click', () => {
        consoleOutput.textContent = '> Console effacée.\n';
    });

    // --- Accordéon : Filtres optionnels ---
    const accordHeader = document.getElementById('accordion-filtres-header');
    const accordBody = document.getElementById('accordion-filtres-body');
    const filtresBadge = document.getElementById('filtres-badge');
    const filtresInputs = [
        document.getElementById('type-usager'),
        document.getElementById('domaine-snc'),
        document.getElementById('theme-snc'),
        document.getElementById('type-action-snc')
    ];

    function updateFiltresBadge() {
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

    accordHeader.addEventListener('click', () => {
        const isOpen = accordBody.classList.contains('open');
        accordBody.classList.toggle('open', !isOpen);
        accordHeader.classList.toggle('open', !isOpen);
    });
});
