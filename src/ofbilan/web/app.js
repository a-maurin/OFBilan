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

    // Combobox Profils de bilan
    const inputProfil = document.getElementById('profil');
    const btnToggleProfils = document.getElementById('btn-toggle-profils');
    const profilsDropdown = document.getElementById('profils-dropdown');

    const profilesList = [
        { value: "global", label: "Bilan Global d'Activité" },
        { value: "synthese_activite_PA_PJ", label: "Synthèse Activité PA/PJ" },
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

    // Hide dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-container')) {
            profilsDropdown.classList.add('hidden');
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
});
