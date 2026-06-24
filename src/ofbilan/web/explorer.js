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
    setupCombobox(inputDomaineSNC, btnToggleDomainesSNC, domainesSNCDropdown, () => domainesSNCList);
    setupCombobox(inputThemeSNC, btnToggleThemesSNC, themesSNCDropdown, () => themesSNCList);
    setupCombobox(inputTypeAction, btnToggleTypesAction, typesActionDropdown, () => typesActionList);

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
    L.tileLayer('https://data.geopf.fr/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.ign.fr/">IGN</a>'
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
            'type-usager': document.getElementById('type-usager').value,
            'domaines': document.getElementById('domaine-snc').value ? [document.getElementById('domaine-snc').value] : [],
            'themes': document.getElementById('theme-snc').value ? [document.getElementById('theme-snc').value] : [],
            'types_action': document.getElementById('type-action-snc').value ? [document.getElementById('type-action-snc').value] : []
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
            const chartData = res.charts || {};

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

            // Render Results Chart (Doughnut)
            if (chartResults) {
                chartResults.destroy();
            }
            const resultsData = chartData.results || {};
            const ctxResults = document.getElementById('chart-results').getContext('2d');
            chartResults = new Chart(ctxResults, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(resultsData),
                    datasets: [{
                        data: Object.values(resultsData),
                        backgroundColor: ['#53AB60', '#EF4444', '#64748B'],
                        borderWidth: 1
                    }]
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
                const resultsLabels = Object.keys(resultsData);
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

            // Render Usagers Chart (Doughnut)
            if (chartUsagers) {
                chartUsagers.destroy();
            }
            const usagersData = chartData.usagers || {};
            const rawLabels = Object.keys(usagersData);
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
            const ctxUsagers = document.getElementById('chart-usagers').getContext('2d');
            chartUsagers = new Chart(ctxUsagers, {
                type: 'doughnut',
                data: {
                    labels: usagersLabels,
                    datasets: [{
                        data: Object.values(usagersData),
                        backgroundColor: usagersColors,
                        borderWidth: 1
                    }]
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

            // Render Domains Chart (Bar)
            if (chartDomains) {
                chartDomains.destroy();
            }
            
            const sortedDomains = Object.entries(chartData.domains || {})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5);
            
            const domainLabels = sortedDomains.map(d => splitLabel(d[0], 25));
            const domainTotalLines = domainLabels.reduce((sum, lines) => sum + lines.length, 0);
            const domainHeight = Math.max(100, 45 + (domainLabels.length * 24) + (domainTotalLines - domainLabels.length) * 11);
            const wrapperDomains = document.getElementById('wrapper-domains');
            if (wrapperDomains) {
                wrapperDomains.style.height = `${domainHeight}px`;
            }
            
            const ctxDomains = document.getElementById('chart-domains').getContext('2d');
            chartDomains = new Chart(ctxDomains, {
                type: 'bar',
                data: {
                    labels: domainLabels,
                    datasets: [{
                        label: 'Contrôles',
                        data: sortedDomains.map(d => d[1]),
                        backgroundColor: '#003A76',
                        borderRadius: 4,
                        barThickness: 12
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: tooltipPercentageCallback
                        }
                    },
                    scales: {
                        x: { beginAtZero: true, ticks: { font: { size: 9 } } },
                        y: { 
                            grid: { display: false },
                            ticks: { autoSkip: false, font: { size: 9 } } 
                        }
                    }
                }
            });

            // Render Themes Chart (Bar)
            if (chartThemes) {
                chartThemes.destroy();
            }
            
            const sortedThemes = Object.entries(chartData.themes || {})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5);
            
            const themeLabels = sortedThemes.map(d => splitLabel(d[0], 25));
            const themeTotalLines = themeLabels.reduce((sum, lines) => sum + lines.length, 0);
            const themeHeight = Math.max(100, 45 + (themeLabels.length * 24) + (themeTotalLines - themeLabels.length) * 11);
            const wrapperThemes = document.getElementById('wrapper-themes');
            if (wrapperThemes) {
                wrapperThemes.style.height = `${themeHeight}px`;
            }
            
            const ctxThemes = document.getElementById('chart-themes').getContext('2d');
            chartThemes = new Chart(ctxThemes, {
                type: 'bar',
                data: {
                    labels: themeLabels,
                    datasets: [{
                        label: 'Contrôles',
                        data: sortedThemes.map(d => d[1]),
                        backgroundColor: '#4296CE',
                        borderRadius: 4,
                        barThickness: 12
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: tooltipPercentageCallback
                        }
                    },
                    scales: {
                        x: { beginAtZero: true, ticks: { font: { size: 9 } } },
                        y: { 
                            grid: { display: false },
                            ticks: { autoSkip: false, font: { size: 9 } } 
                        }
                    }
                }
            });

            // Render Seasonality Chart (Line)
            if (chartSeasonality) {
                chartSeasonality.destroy();
            }
            const monthsLabels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sept', 'Oct', 'Nov', 'Déc'];
            const seasonalityData = chartData.seasonality || { controls: Array(12).fill(0), infractions: Array(12).fill(0) };
            const ctxSeasonality = document.getElementById('chart-seasonality').getContext('2d');
            chartSeasonality = new Chart(ctxSeasonality, {
                type: 'line',
                data: {
                    labels: monthsLabels,
                    datasets: [
                        {
                            label: 'Contrôles',
                            data: seasonalityData.controls,
                            borderColor: '#003A76',
                            backgroundColor: 'rgba(0, 58, 118, 0.05)',
                            fill: true,
                            tension: 0.3
                        },
                        {
                            label: 'Infractions',
                            data: seasonalityData.infractions,
                            borderColor: '#EF4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.05)',
                            fill: true,
                            tension: 0.3
                        }
                    ]
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
            btnUpdate.textContent = 'Charger les données';
        });
    }

    btnUpdate.addEventListener('click', loadData);

    const btnPdf = document.getElementById('btn-pdf');
    if (btnPdf) {
        btnPdf.addEventListener('click', () => {
            alert('La génération PDF à partir des données de l\'explorateur sera implémentée ultérieurement.');
        });
    }

    // Initial load
    loadData();
});
