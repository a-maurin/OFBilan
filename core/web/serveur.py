import http.server
import socketserver
import json
import os
import subprocess
import sys
import pandas as pd
from pathlib import Path

# Ajouter le dossier actuel au path pour importer reparer_logo
WEB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB_DIR))
SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

try:
    from reparer_logo import generer_logo_blanc
    # Génère automatiquement le logo propre au démarrage
    generer_logo_blanc()
except ImportError:
    pass

PORT = 8000

_PRELOAD_LOGS = []
_PRELOAD_STATUS = "loading"

def clean_nan(obj):
    import math
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(x) for x in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        import pandas as pd
        if pd.isna(obj):
            return None
    except Exception:
        pass
    if str(obj) in ("<NA>", "NaT", "NaN", "nan"):
        return None
    return obj

def get_latest_version():
    """Extrait le numéro de version de la release la plus récente dans CHANGELOG.md."""
    changelog_path = Path(__file__).resolve().parents[3] / "CHANGELOG.md"
    if changelog_path.exists():
        try:
            import re
            content = changelog_path.read_text(encoding="utf-8")
            match = re.search(r'##\s*\[v?(\d+\.\d+\.\d+)\]', content)
            if match:
                return f"v{match.group(1)}"
        except Exception:
            pass
    return "v1.0.2"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def handle(self):
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            print(f"  [Réseau] Connexion interrompue par le navigateur ({e.__class__.__name__})")

    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if self.path == "/api/preload-status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": _PRELOAD_STATUS,
                "logs": _PRELOAD_LOGS
            }).encode('utf-8'))
            return

        if self.path == '/api/restart':
            # Endpoint pour redémarrer le serveur
            import time
            import threading
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "restarting"}).encode('utf-8'))
            print("Redémarrage du serveur demandé via l'interface web...")
            
            def restart():
                time.sleep(0.5)
                # On utilise sys.executable pour relancer exactement le même script
                os.environ["OFBILAN_RESTART"] = "1"
                os.execv(sys.executable, [sys.executable] + sys.argv)
                
            threading.Thread(target=restart, daemon=True).start()
            return
            
        elif self.path == '/api/shutdown':
            # Endpoint pour éteindre le serveur
            import time
            import threading
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "shutting down"}).encode('utf-8'))
            print("Extinction du serveur demandée via l'interface web...")
            
            def shutdown():
                time.sleep(0.5)
                os._exit(0)
                
            threading.Thread(target=shutdown, daemon=True).start()
            return

        if self.path == "/api/version":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"version": get_latest_version()}).encode('utf-8'))
            return

        if self.path == "/api/profils":
            try:
                import yaml
                def yaml_include_dummy_constructor(loader, node):
                    return []
                try:
                    yaml.add_constructor("!include", yaml_include_dummy_constructor, Loader=yaml.SafeLoader)
                except Exception:
                    pass
                project_root = Path(__file__).resolve().parents[2]
                profiles_dir = project_root / "config" / "profils_bilan"
                profils_list = [{
                    "value": "global",
                    "label": "Tous (Sans profil)",
                    "sources": {"point_ctrl": True, "pej": True, "pa": True, "pve": True},
                    "has_action_filter": False,
                    "has_natinf_filter": False,
                    "has_custom_stats": False
                }]
                if profiles_dir.exists():
                    for yaml_file in profiles_dir.glob("*.yaml"):
                        try:
                            content = yaml_file.read_text(encoding="utf-8")
                            data = yaml.safe_load(content)
                            if not data:
                                continue
                            val_id = data.get("id")
                            val_label = data.get("label")
                            if val_id and val_label:
                                if any(p["value"] == val_id for p in profils_list):
                                    continue
                                    
                                sources_cfg = data.get("sources", {})
                                sources = {
                                    "point_ctrl": sources_cfg.get("point_ctrl", True),
                                    "pej": sources_cfg.get("pej", True),
                                    "pa": sources_cfg.get("pa", True),
                                    "pve": sources_cfg.get("pve", True)
                                }
                                # Rétrocompatibilité avec point_ctrl au premier niveau
                                if data.get("point_ctrl") is False:
                                    sources["point_ctrl"] = False
                                    
                                has_action_filter = False
                                filter_cfg = data.get("filter", {})
                                if filter_cfg and filter_cfg.get("type") != "all":
                                    has_action_filter = True
                                
                                import re
                                has_natinf_filter = bool(re.search(r'natinf_(pej|pve):\s*(?!\[\])(.*)', content))
                                has_custom_stats = "adapter" in data
                                
                                profils_list.append({
                                    "value": val_id,
                                    "label": val_label,
                                    "sources": sources,
                                    "has_action_filter": has_action_filter,
                                    "has_natinf_filter": has_natinf_filter,
                                    "has_custom_stats": has_custom_stats
                                })
                        except Exception:
                            pass
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(profils_list).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/generate":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data.decode('utf-8'))

            # Construction des arguments pour point_entree_cli.py
            cli_path = Path(__file__).resolve().parents[1] / "point_entree_cli.py"
            cmd = [sys.executable, str(cli_path)]

            # Paramètres de base
            if params.get("profil"):
                cmd.extend(["--profil", str(params["profil"])])
            if params.get("date-deb"):
                cmd.extend(["--date-deb", str(params["date-deb"])])
            if params.get("date-fin"):
                cmd.extend(["--date-fin", str(params["date-fin"])])
            if params.get("echelle"):
                cmd.extend(["--echelle", str(params["echelle"])])
            if params.get("code"):
                cmd.extend(["--code", str(params["code"])])
            if params.get("type-usager"):
                cmd.extend(["--type-usager", str(params["type-usager"])])
            if params.get("domaines"):
                for d in params["domaines"]:
                    if str(d).strip():
                        cmd.extend(["--domaine", str(d).strip()])
            if params.get("themes"):
                for t in params["themes"]:
                    if str(t).strip():
                        cmd.extend(["--theme", str(t).strip()])
            if params.get("types_action"):
                for a in params["types_action"]:
                    if str(a).strip():
                        cmd.extend(["--type-action", str(a).strip()])
            if params.get("diffusion"):
                cmd.extend(["--diffusion", str(params["diffusion"])])
            if params.get("preset"):
                cmd.extend(["--preset", str(params["preset"])])

            # Options oui/non (cartes, pnf, brochure)
            if params.get("cartes") is True:
                cmd.append("--cartes")
                if isinstance(params.get("cartes_selection"), list):
                    for c in params["cartes_selection"]:
                        c_clean = str(c).strip()
                        if c_clean:
                            cmd.extend(["--carte", c_clean])
            elif params.get("cartes") is False:
                cmd.append("--no-cartes")

            if params.get("pnf") is True:
                cmd.append("--pnf")
            elif params.get("pnf") is False:
                cmd.append("--no-pnf")

            if params.get("brochure") is True:
                cmd.append("--brochure")
            elif params.get("brochure") is False:
                cmd.append("--no-brochure")

            # Désactiver l'ouverture automatique du PDF sous Windows lors du run de la GUI
            cmd.append("--no-open")

            # Répondre avec un flux de texte en temps réel (chunked)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()

            # Lancement du processus
            self.wfile.write(f"> Commande : {' '.join(cmd)}\n\n".encode('utf-8'))
            self.wfile.flush()

            try:
                # On force PYTHONPATH pour que le module ofbilan soit résolu correctement
                env = os.environ.copy()
                project_root = str(Path(__file__).resolve().parents[3])
                src_dir = str(Path(__file__).resolve().parents[2])
                env["PYTHONPATH"] = src_dir + os.pathsep + project_root + os.pathsep + env.get("PYTHONPATH", "")
                env["PYTHONIOENCODING"] = "utf-8"

                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding='utf-8',
                    errors='replace',
                    cwd=project_root,
                    env=env
                )

                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        self.wfile.write(line.encode('utf-8'))
                        self.wfile.flush()

                process.wait()
                if process.returncode == 0:
                    self.wfile.write("\n[SUCCESS] Génération terminée avec succès.\n".encode('utf-8'))
                else:
                    self.wfile.write(f"\n[ERREUR] Le processus s'est arrêté avec le code d'erreur {process.returncode}.\n".encode('utf-8'))
            except Exception as e:
                self.wfile.write(f"\n[ERREUR] Impossible de lancer le traitement : {e}\n".encode('utf-8'))
            
            self.wfile.flush()
        elif self.path == "/api/data":
            try:
                import datetime
                from pathlib import Path
                project_root = Path(__file__).resolve().parents[2]
                
                debug_log = project_root / "tests" / "scratch" / "api_data_debug.log"
                debug_log.parent.mkdir(parents=True, exist_ok=True)
                def log_debug(msg):
                    with open(debug_log, "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.datetime.now()}] {msg}\n")
                        
                log_debug("=== NOUVELLE REQUÊTE /api/data ===")
                
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                params = json.loads(post_data.decode('utf-8'))
                log_debug(f"Params décodés: {params}")

                from ofbilan.common.chargeurs_donnees import load_point_ctrl, load_pej, load_pa, load_pve
                from ofbilan.engine.orchestrateur_profils import (
                    load_profile_config,
                    _filter_point_ctrl,
                    _filter_pej,
                    _filter_pa,
                    _filter_pve
                )
                from ofbilan.common.utilitaires_metier import classify_resultat_controle_series, agg_effectifs_usagers
                from ofbilan.common.bilan_config import BilanConfig
                import pandas as pd

                profil = params.get("profil", "global")
                date_deb = params.get("date-deb")
                date_fin = params.get("date-fin")
                echelle = params.get("echelle", "departement")
                code = params.get("code")
                type_usager = params.get("type-usager")
                domaines = params.get("domaines")
                themes = params.get("themes")
                types_action = params.get("types_action")
                resultats_filter = params.get("resultats")
                commune = params.get("commune")

                # project_root is already defined above

                # 1. Charger la configuration du profil
                profile_cfg = load_profile_config(project_root, profil)
                sources_cfg = profile_cfg.get("sources", {})
                load_pts_flag = sources_cfg.get("point_ctrl", True)
                load_pej_flag = sources_cfg.get("pej", True)
                load_pa_flag = sources_cfg.get("pa", True)
                load_pve_flag = sources_cfg.get("pve", True)

                cfg_obj = BilanConfig.from_strings(
                    date_deb=date_deb,
                    date_fin=date_fin,
                    echelle=echelle,
                    code=code,
                    root=project_root
                )

                from ofbilan.common.chargeurs_donnees import _SESSION_CACHE
                _original_cache_active = _SESSION_CACHE["active"]
                # Désactiver temporairement le cache pour pouvoir charger N-1 (évite le filtre de la session N)
                _SESSION_CACHE["active"] = False

                # 2. Chargement et filtrage des points de contrôle
                log_debug(f"Début chargement Points de contrôle (load_pts_flag={load_pts_flag})")
                df_pts_unfiltered = load_point_ctrl(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin) if load_pts_flag else pd.DataFrame()
                log_debug(f"Points de contrôle chargés : {len(df_pts_unfiltered)} lignes")
                df_pts = df_pts_unfiltered.copy()
                if profile_cfg.get("pipeline") != "global":
                    df_pts = _filter_point_ctrl(df_pts, profile_cfg)
                
                # Filtrage multi-usagers ou simple
                if type_usager:
                    if isinstance(type_usager, str):
                        type_usager = [type_usager]
                    tu_lower = {u.strip().lower() for u in type_usager if u.strip()}
                    if tu_lower and "type_usager" in df_pts.columns:
                        df_pts = df_pts[df_pts["type_usager"].astype(str).str.strip().str.lower().apply(
                            lambda val: any(u in str(val) for u in tu_lower)
                        )].copy()

                if domaines:
                    if isinstance(domaines, str):
                        domaines = [domaines]
                    td_lower = {d.strip().lower() for d in domaines if d.strip()}
                    if td_lower and "domaine" in df_pts.columns:
                        df_pts = df_pts[df_pts["domaine"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if themes:
                    if isinstance(themes, str):
                        themes = [themes]
                    tt_lower = {t.strip().lower() for t in themes if t.strip()}
                    if tt_lower:
                        col_pt_theme = "theme" if "theme" in df_pts.columns else ("type_actio" if "type_actio" in df_pts.columns else None)
                        if col_pt_theme:
                            df_pts = df_pts[df_pts[col_pt_theme].astype(str).str.strip().str.lower().isin(tt_lower)].copy()
                if types_action:
                    if isinstance(types_action, str):
                        types_action = [types_action]
                    ta_lower = {a.strip().lower() for a in types_action if a.strip()}
                    if ta_lower:
                        col_ta = "type_actio" if "type_actio" in df_pts.columns else ("type_action" if "type_action" in df_pts.columns else None)
                        if col_ta:
                            df_pts = df_pts[df_pts[col_ta].astype(str).str.strip().str.lower().apply(
                                lambda val: any(t in str(val) for t in ta_lower)
                            )].copy()

                # Filtrage résultat (Conforme / Non-conforme / En attente)
                if resultats_filter and not df_pts.empty:
                    if isinstance(resultats_filter, str):
                        resultats_filter = [resultats_filter]
                    res_series = classify_resultat_controle_series(df_pts["resultat"])
                    valeurs_reelles = []
                    for r in resultats_filter:
                        r_lower = r.lower()
                        if "non-conforme" in r_lower or "infraction" in r_lower or "manquement" in r_lower:
                            valeurs_reelles.extend(["Infraction", "Manquement"])
                        elif "conforme" in r_lower:
                            valeurs_reelles.append("Conforme")
                        elif "attente" in r_lower:
                            valeurs_reelles.append("En attente")
                    
                    if valeurs_reelles:
                        df_pts = df_pts[res_series.isin(valeurs_reelles)].copy()

                # Filtrage commune
                if commune and not df_pts.empty and "nom_commun" in df_pts.columns:
                    df_pts = df_pts[df_pts["nom_commun"].astype(str).str.lower().str.contains(commune.lower(), na=False)].copy()

                total_controles = len(df_pts)

                df_pej = pd.DataFrame()
                df_pa = pd.DataFrame()
                df_pve = pd.DataFrame()

                # 3. Chargement et filtrage PEJ
                log_debug(f"Début chargement PEJ (load_pej_flag={load_pej_flag})")
                df_pej = load_pej(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin) if load_pej_flag else pd.DataFrame()
                log_debug(f"PEJ chargées : {len(df_pej)} lignes")
                if profile_cfg.get("pipeline") != "global":
                    df_pej = _filter_pej(df_pej, profile_cfg, cfg_obj, df_pts)
                if type_usager and tu_lower and "type_usager" in df_pej.columns:
                    df_pej = df_pej[df_pej["type_usager"].astype(str).str.strip().str.lower().apply(
                        lambda val: any(u in str(val) for u in tu_lower)
                    )].copy()
                if domaines:
                    td_lower = {d.strip().lower() for d in domaines if d.strip()}
                    if td_lower and "DOMAINE" in df_pej.columns:
                        df_pej = df_pej[df_pej["DOMAINE"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if themes:
                    tt_lower = {t.strip().lower() for t in themes if t.strip()}
                    if tt_lower:
                        col_pej_theme = "THEME" if "THEME" in df_pej.columns else ("TYPE_ACTION" if "TYPE_ACTION" in df_pej.columns else None)
                        if col_pej_theme:
                            df_pej = df_pej[df_pej[col_pej_theme].astype(str).str.strip().str.lower().isin(tt_lower)].copy()
                if types_action:
                    ta_lower = {a.strip().lower() for a in types_action if a.strip()}
                    if ta_lower:
                        col_ta = "TYPE_ACTION" if "TYPE_ACTION" in df_pej.columns else None
                        if col_ta:
                            df_pej = df_pej[df_pej[col_ta].astype(str).str.strip().str.lower().apply(
                                lambda val: any(t in str(val) for t in ta_lower)
                            )].copy()
                total_pej = len(df_pej)

                # 4. Chargement et filtrage PA
                log_debug(f"Début chargement PA (load_pa_flag={load_pa_flag})")
                df_pa = pd.DataFrame()
                from ofbilan.common.utilitaires_metier import count_pa_induites_par_controles
                try:
                    df_pa = load_pa(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin) if load_pa_flag else pd.DataFrame()
                    log_debug(f"PA chargées : {len(df_pa)} lignes")
                    if profile_cfg.get("pipeline") != "global":
                        df_pa = _filter_pa(df_pa, profile_cfg, cfg_obj, df_pts)
                    else:
                        entity_sds = cfg_obj.entity_sds
                        if entity_sds and "ENTITE_ORIGINE_PROCEDURE" in df_pa.columns:
                            df_pa = df_pa[df_pa["ENTITE_ORIGINE_PROCEDURE"].isin(entity_sds)].copy()
                        from ofbilan.common.utilitaires_metier import resolve_type_usager_champ
                        usager_col = resolve_type_usager_champ(df_pa)
                        if type_usager and usager_col and tu_lower:
                            df_pa = df_pa[df_pa[usager_col].astype(str).str.strip().str.lower().apply(
                                lambda val: any(u in str(val) for u in tu_lower)
                            )].copy()
                        if "DC_ID" in df_pa.columns:
                            if "DATE_REF" in df_pa.columns:
                                df_pa = df_pa.sort_values("DATE_REF", ascending=False).drop_duplicates(subset="DC_ID", keep="first")
                            else:
                                df_pa = df_pa.drop_duplicates(subset="DC_ID", keep="first")
                    if domaines:
                        td_lower = {d.strip().lower() for d in domaines if d.strip()}
                        if td_lower and "DOMAINE" in df_pa.columns:
                            df_pa = df_pa[df_pa["DOMAINE"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                    if themes:
                        tt_lower = {t.strip().lower() for t in themes if t.strip()}
                        if tt_lower:
                            col_pa_theme = "THEME" if "THEME" in df_pa.columns else ("TYPE_ACTION" if "TYPE_ACTION" in df_pa.columns else None)
                            if col_pa_theme:
                                df_pa = df_pa[df_pa[col_pa_theme].astype(str).str.strip().str.lower().isin(tt_lower)].copy()
                    if types_action:
                        ta_lower = {a.strip().lower() for a in types_action if a.strip()}
                        if ta_lower:
                            col_ta = "TYPE_ACTION" if "TYPE_ACTION" in df_pa.columns else ("THEME" if "THEME" in df_pa.columns else None)
                            if col_ta:
                                df_pa = df_pa[df_pa[col_ta].astype(str).str.strip().str.lower().apply(
                                    lambda val: any(t in str(val) for t in ta_lower)
                                )].copy()
                    total_pa = count_pa_induites_par_controles(df_pts)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Erreur chargement/filtrage PA: {e}")
                    total_pa = 0

                # 5. Chargement et filtrage PVe
                log_debug(f"Début chargement PVe (load_pve_flag={load_pve_flag})")
                try:
                    df_pve = load_pve(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin) if load_pve_flag else pd.DataFrame()
                    log_debug(f"PVe chargés : {len(df_pve)} lignes")
                    
                    # LOG DE DIAGNOSTIC
                    debug_path = project_root / "tests" / "scratch"
                    debug_path.mkdir(parents=True, exist_ok=True)
                    with open(debug_path / "debug_pve.txt", "w", encoding="utf-8") as f:
                        f.write(f"GET /data for {date_deb} to {date_fin}\n")
                        f.write(f"load_pve returned {len(df_pve)} rows\n")
                        if not df_pve.empty:
                            f.write(f"Columns: {list(df_pve.columns)}\n")
                            if "INF-DATE-MIF" in df_pve.columns:
                                f.write(f"MIF head:\n{df_pve['INF-DATE-MIF'].head()}\n")
                            if "INF-DATE-INTG" in df_pve.columns:
                                f.write(f"INTG head:\n{df_pve['INF-DATE-INTG'].head()}\n")
                                
                    if profile_cfg.get("pipeline") != "global":
                        df_pve = _filter_pve(df_pve, profile_cfg)
                    if themes:
                        tt_lower = {t.strip().lower() for t in themes if t.strip()}
                        if tt_lower:
                            col_pve_theme = "theme" if "theme" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else None)
                            if col_pve_theme:
                                df_pve = df_pve[df_pve[col_pve_theme].astype(str).str.strip().str.lower().isin(tt_lower)].copy()
                    if types_action:
                        ta_lower = {a.strip().lower() for a in types_action if a.strip()}
                        if ta_lower:
                            col_ta = "type_action" if "type_action" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else ("type_actio" if "type_actio" in df_pve.columns else ("INF-TYP-INF-STAT-LIB" if "INF-TYP-INF-STAT-LIB" in df_pve.columns else None)))
                            if col_ta:
                                df_pve = df_pve[df_pve[col_ta].astype(str).str.strip().str.lower().apply(
                                    lambda val: any(t in str(val) for t in ta_lower)
                                )].copy()
                    
                    # DIAGNOSTIC LOG AFTER FILTERS
                    with open(project_root / "tests" / "scratch" / "debug_pve.txt", "a", encoding="utf-8") as f:
                        f.write(f"After keyword filters: {len(df_pve)} rows\n")
                        
                    total_pve = len(df_pve)
                except Exception as e:
                    with open(project_root / "tests" / "scratch" / "debug_pve.txt", "a", encoding="utf-8") as f:
                        f.write(f"EXCEPTION: {e}\n")
                    total_pve = 0

                # 4.bis. Restriction spatiale si echelle == "pnf"
                if echelle == "pnf":
                    import logging
                    from ofbilan.engine.orchestrateur_profils import _apply_restrict_geo_pnf, _coalesced_insee_for_pnf_mask
                    log = logging.getLogger(__name__)
                    df_pts, df_pej, df_pa, df_pve = _apply_restrict_geo_pnf(
                        df_pts, df_pej, df_pa, df_pve, project_root, log
                    )
                    
                    # Filtre additionnel sur le département pour le PNF
                    pnf_dept = params.get("pnf_dept", "")
                    if pnf_dept in ("21", "52"):
                        def _filter_by_dept(df):
                            if df.empty:
                                return df
                            insee_s = _coalesced_insee_for_pnf_mask(df)
                            return df[insee_s.notna() & insee_s.astype(str).str.startswith(pnf_dept)].copy()
                            
                        df_pts = _filter_by_dept(df_pts)
                        df_pej = _filter_by_dept(df_pej)
                        df_pa = _filter_by_dept(df_pa)
                        df_pve = _filter_by_dept(df_pve)

                    total_controles = len(df_pts)
                    total_pej = len(df_pej)
                    total_pa = count_pa_induites_par_controles(df_pts)
                    total_pve = len(df_pve)

                # 5. Calcul des répartitions statistiques (Combiné sur toutes les sources activées)
                results_counts = {"Conforme": 0, "Non-conforme": 0, "En attente": 0}
                if "resultat" in df_pts.columns and not df_pts.empty:
                    res_series = classify_resultat_controle_series(df_pts["resultat"])
                    results_counts["Conforme"] = int((res_series == "Conforme").sum())
                    results_counts["Non-conforme"] = int(res_series.isin(["Infraction", "Manquement"]).sum())
                    results_counts["En attente"] = int((res_series == "En attente").sum())

                usagers_counts = {}
                if not df_pts.empty and "type_usager" in df_pts.columns:
                    df_us = agg_effectifs_usagers(df_pts, "point_ctrl", "type_usager")
                    for _, row in df_us.iterrows():
                        u = str(row["type_usager"]).strip() if pd.notna(row.get("type_usager")) else "Non renseigné"
                        if u: usagers_counts[u] = usagers_counts.get(u, 0) + int(row["nb"])
                if not df_pej.empty and "type_usager" in df_pej.columns:
                    for k, v in df_pej["type_usager"].astype(str).fillna("Non renseigné").str.strip().value_counts().items():
                        if k and k.lower() != 'nan': usagers_counts[k] = usagers_counts.get(k, 0) + int(v)

                if type_usager and tu_lower:
                    filtered_counts = {}
                    for k, v in usagers_counts.items():
                        if any(u in k.lower() for u in tu_lower):
                            filtered_counts[k] = v
                    usagers_counts = filtered_counts


                def get_dept_series(df):
                    if df.empty:
                        return pd.Series(dtype=str)
                    for c in ["num_depart", "dept", "code_dept", "DEPT", "departement", "DEP", "DPT", "CODE_DEP"]:
                        if c in df.columns:
                            return df[c].astype(str).str.zfill(2).str[:2]
                    for c in ["ENTITE_ORIGINE_PROCEDURE", "entite_origine_procedure"]:
                        if c in df.columns:
                            s = df[c].astype(str).str.extract(r'(\d+)')[0]
                            s = s.where(s.notna() & (s.str.lower() != "nan"), None)
                            return s.str.zfill(2).str[:2]
                    for c in ["insee_comm", "insee_commun", "insee_com", "INF-INSEE"]:
                        if c in df.columns:
                            s = df[c].astype(str)
                            s = s.where(s.str.lower() != "nan", None)
                            return s.str.zfill(5).str[:2]
                    return pd.Series("N/A", index=df.index)

                domains_counts = {}
                themes_counts = {}

                if echelle == "region" or (echelle == "pnf" and pnf_dept not in ("21", "52")):
                    dom_records = []
                    for df_tmp, col_dom in [(df_pts, "domaine"), (df_pej, "DOMAINE"), (df_pa, "DOMAINE")]:
                        if not df_tmp.empty and col_dom in df_tmp.columns:
                            dept_s = get_dept_series(df_tmp)
                            dom_s = df_tmp[col_dom].astype(str).fillna("Hors domaine").str.strip()
                            df_merge = pd.DataFrame({"dom": dom_s, "dept": dept_s})
                            dom_records.append(df_merge)
                    
                    if dom_records:
                        df_all_dom = pd.concat(dom_records)
                        df_all_dom = df_all_dom[df_all_dom["dom"].str.lower() != 'nan']
                        for dom, group in df_all_dom.groupby("dom"):
                            dept_counts = group["dept"].value_counts().to_dict()
                            domains_counts[dom] = {k: int(v) for k, v in dept_counts.items() if str(k).strip() and str(k).lower() != 'nan'}

                    theme_records = []
                    for df_tmp, cols_th in [
                        (df_pts, ["theme", "type_actio"]),
                        (df_pej, ["THEME", "TYPE_ACTION"]),
                        (df_pa, ["THEME", "TYPE_ACTION"]),
                        (df_pve, ["theme", "THEME"])
                    ]:
                        if df_tmp.empty: continue
                        col_used = next((c for c in cols_th if c in df_tmp.columns), None)
                        if col_used:
                            dept_s = get_dept_series(df_tmp)
                            th_s = df_tmp[col_used].astype(str).fillna("Hors thème").str.strip()
                            df_merge = pd.DataFrame({"theme": th_s, "dept": dept_s})
                            theme_records.append(df_merge)
                    
                    if theme_records:
                        df_all_th = pd.concat(theme_records)
                        df_all_th = df_all_th[df_all_th["theme"].str.lower() != 'nan']
                        for th, group in df_all_th.groupby("theme"):
                            dept_counts = group["dept"].value_counts().to_dict()
                            themes_counts[th] = {k: int(v) for k, v in dept_counts.items() if str(k).strip() and str(k).lower() != 'nan'}
                else:
                    s_dom = []
                    if not df_pts.empty and "domaine" in df_pts.columns: s_dom.append(df_pts["domaine"].astype(str))
                    if not df_pej.empty and "DOMAINE" in df_pej.columns: s_dom.append(df_pej["DOMAINE"].astype(str))
                    if not df_pa.empty and "DOMAINE" in df_pa.columns: s_dom.append(df_pa["DOMAINE"].astype(str))
                    if s_dom:
                        for k, v in pd.concat(s_dom).fillna("Hors domaine").str.strip().value_counts().items():
                            if k and k.lower() != 'nan': domains_counts[k] = int(v)
    
                    s_theme = []
                    if not df_pts.empty:
                        c = "theme" if "theme" in df_pts.columns else ("type_actio" if "type_actio" in df_pts.columns else None)
                        if c: s_theme.append(df_pts[c].astype(str))
                    if not df_pej.empty:
                        c = "THEME" if "THEME" in df_pej.columns else ("TYPE_ACTION" if "TYPE_ACTION" in df_pej.columns else None)
                        if c: s_theme.append(df_pej[c].astype(str))
                    if not df_pa.empty:
                        c = "THEME" if "THEME" in df_pa.columns else ("TYPE_ACTION" if "TYPE_ACTION" in df_pa.columns else None)
                        if c: s_theme.append(df_pa[c].astype(str))
                    if not df_pve.empty:
                        c = "theme" if "theme" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else None)
                        if c: s_theme.append(df_pve[c].astype(str))
                    if s_theme:
                        for k, v in pd.concat(s_theme).fillna("Hors thème").str.strip().value_counts().items():
                            if k and k.lower() != 'nan': themes_counts[k] = int(v)

                monthly_controls = [0] * 12
                monthly_infractions = [0] * 12
                if not df_pts.empty and "date_ctrl" in df_pts.columns:
                    dt_series = pd.to_datetime(df_pts["date_ctrl"], errors="coerce")
                    res_series = classify_resultat_controle_series(df_pts["resultat"]) if "resultat" in df_pts.columns else pd.Series("En attente", index=df_pts.index)
                    for month in range(1, 13):
                        mask_month = dt_series.dt.month == month
                        monthly_controls[month - 1] += int(mask_month.sum())
                        monthly_infractions[month - 1] += int((mask_month & res_series.isin(["Infraction", "Manquement"])).sum())
                
                def add_infractions(df, cols_date):
                    if df.empty: return
                    for c in cols_date:
                        if c in df.columns:
                            dt_s = pd.to_datetime(df[c], errors="coerce")
                            for month in range(1, 13):
                                monthly_infractions[month - 1] += int((dt_s.dt.month == month).sum())
                            break
                            
                add_infractions(df_pej, ["DATE_REF", "date_ref", "DATE_CONSTATATION", "date_constatation"])
                add_infractions(df_pve, ["DATE_INFRACTION", "date_infraction"])
                add_infractions(df_pa, ["DATE_REF", "date_ref"])

                # 6. Extraction des points valides pour la cartographie
                points = []
                if not df_pts.empty:
                    df_pts_valid = df_pts.dropna(subset=["x", "y"])
                    for _, row in df_pts_valid.iterrows():
                        res_val = row.get("resultat")
                        dom_val = row.get("domaine")
                        theme_val = row.get("theme")
                        usager_val = row.get("type_usager")
                        com_val = row.get("nom_commun")
                        dc_val = row.get("dc_id")
                        date_val = row.get("date_ctrl")

                        points.append({
                            "dc_id": str(dc_val).strip() if pd.notna(dc_val) else "",
                            "date_ctrl": str(date_val)[:10] if pd.notna(date_val) else "",
                            "resultat": str(res_val).strip() if pd.notna(res_val) else "",
                            "domaine": str(dom_val).strip() if pd.notna(dom_val) else "",
                            "theme": str(theme_val).strip() if pd.notna(theme_val) else "",
                            "type_usager": str(usager_val).strip() if pd.notna(usager_val) else "",
                            "nom_commun": str(com_val).strip() if pd.notna(com_val) else "",
                            "x": float(row["x"]) if pd.notna(row.get("x")) else 0.0,
                            "y": float(row["y"]) if pd.notna(row.get("y")) else 0.0
                        })

                # 7. Extraction des procédures (PEJ, PA, PVe) pour la cartographie
                #    - PEJ : points de contrôle dont code_pej est renseigné
                #    - PA  : points de contrôle dont code_pa est renseigné
                #    - PVe : coordonnées issues de load_pve (centroïdes communaux)
                from ofbilan.common.utilitaires_metier import is_filled_procedure_code
                procedures = []

                def _pts_to_proc(df, code_col, label):
                    """Extrait les procédures depuis point_ctrl en filtrant sur code_col non nul."""
                    arr = []
                    if df.empty or code_col not in df.columns or "x" not in df.columns or "y" not in df.columns:
                        return arr
                    mask = df[code_col].map(is_filled_procedure_code)
                    df_valid = df.loc[mask].dropna(subset=["x", "y"])
                    col_ta = "type_actio" if "type_actio" in df.columns else ("type_action" if "type_action" in df.columns else None)
                    for _, r in df_valid.iterrows():
                        arr.append({
                            "type": label,
                            "dc_id": str(r.get("dc_id", "")).strip() if pd.notna(r.get("dc_id")) else "",
                            "date_ctrl": str(r.get("date_ctrl", ""))[:10] if pd.notna(r.get("date_ctrl")) else "",
                            "type_action": str(r.get(col_ta, "Non renseigné")).strip() if col_ta and pd.notna(r.get(col_ta)) else "Non renseigné",
                            "type_usager": str(r.get("type_usager", "Non renseigné")).strip() if pd.notna(r.get("type_usager")) else "Non renseigné",
                            "x": float(r["x"]),
                            "y": float(r["y"])
                        })
                    return arr

                # Extraction des PEJ
                if not df_pej.empty:
                    try:
                        from ofbilan.common.chargeurs_donnees import merge_pej_faits_locations
                        df_pej_loc = merge_pej_faits_locations(df_pej, project_root, echelle, code)
                        
                        # --- FALLBACK COORDONNEES VIA df_pts_unfiltered ---
                        if not df_pts_unfiltered.empty and "dc_id" in df_pts_unfiltered.columns and "x" in df_pts_unfiltered.columns and "y" in df_pts_unfiltered.columns:
                            import re
                            df_pts_clean = df_pts_unfiltered.copy()
                            df_pts_clean["dc_clean"] = df_pts_clean["dc_id"].astype(str).apply(lambda val: re.sub(r"\.0$", "", str(val)) if pd.notna(val) else "")
                            dict_x = df_pts_clean.set_index("dc_clean")["x"].to_dict()
                            dict_y = df_pts_clean.set_index("dc_clean")["y"].to_dict()
                            
                            if "x_faits" not in df_pej_loc.columns:
                                df_pej_loc["x_faits"] = pd.NA
                            if "y_faits" not in df_pej_loc.columns:
                                df_pej_loc["y_faits"] = pd.NA
                                
                            missing_mask = df_pej_loc["x_faits"].isna() | df_pej_loc["y_faits"].isna()
                            if missing_mask.any():
                                dc_clean = df_pej_loc.loc[missing_mask, "DC_ID"].astype(str).apply(lambda val: re.sub(r"\.0$", "", str(val)) if pd.notna(val) else "")
                                df_pej_loc.loc[missing_mask, "x_faits"] = dc_clean.map(dict_x).fillna(df_pej_loc.loc[missing_mask, "x_faits"])
                                df_pej_loc.loc[missing_mask, "y_faits"] = dc_clean.map(dict_y).fillna(df_pej_loc.loc[missing_mask, "y_faits"])

                        if not df_pej_loc.empty and "x_faits" in df_pej_loc.columns and "y_faits" in df_pej_loc.columns:
                            df_pej_valid = df_pej_loc.dropna(subset=["x_faits", "y_faits"])
                            for _, r in df_pej_valid.iterrows():
                                procedures.append({
                                    "type": "PEJ",
                                    "dc_id": str(r.get("DC_ID", "")).strip() if pd.notna(r.get("DC_ID")) else "",
                                    "date_ctrl": str(r.get("DATE_REF", ""))[:10] if pd.notna(r.get("DATE_REF")) else "",
                                    "type_action": str(r.get("TYPE_ACTION", "Non renseigné")).strip() if pd.notna(r.get("TYPE_ACTION")) else "Non renseigné",
                                    "type_usager": str(r.get("type_usager", "Non renseigné")).strip() if pd.notna(r.get("type_usager")) else "Non renseigné",
                                    "x": float(r["x_faits"]),
                                    "y": float(r["y_faits"])
                                })
                    except Exception as e:
                        print(f"Exception merging pej faits: {e}")
                        pass
                
                procedures.extend(_pts_to_proc(df_pts, "code_pa", "PA"))

                # PVe : load_pve() enrichit déjà avec x/y via centroïdes communaux
                if not df_pve.empty:
                    # Fallback 1: utiliser les colonnes GPS brutes si présentes
                    if "x" not in df_pve.columns:
                        df_pve["x"] = pd.NA
                    if "y" not in df_pve.columns:
                        df_pve["y"] = pd.NA
                        
                    if "inf_gps_long" in df_pve.columns:
                        df_pve["x"] = df_pve["x"].fillna(
                            pd.to_numeric(df_pve["inf_gps_long"].astype(str).str.replace(",", "."), errors="coerce")
                        )
                    if "inf_gps_lat" in df_pve.columns:
                        df_pve["y"] = df_pve["y"].fillna(
                            pd.to_numeric(df_pve["inf_gps_lat"].astype(str).str.replace(",", "."), errors="coerce")
                        )
                        
                    # Fallback 2: centroïdes des communes nationales si toujours vides
                    missing_pve_mask = df_pve["x"].isna() | df_pve["y"].isna()
                    if missing_pve_mask.any() and "INF-INSEE" in df_pve.columns:
                        try:
                            from ofbilan.common.chargeurs_donnees import load_communes_centroides
                            cen_com = load_communes_centroides(project_root)
                            if not cen_com.empty:
                                insee_col = "code_insee" if "code_insee" in cen_com.columns else ("CODE_INSEE" if "CODE_INSEE" in cen_com.columns else "insee")
                                lat_col = "latitude_centre" if "latitude_centre" in cen_com.columns else ("LATITUDE_CENTRE" if "LATITUDE_CENTRE" in cen_com.columns else "lat_centre")
                                lon_col = "longitude_centre" if "longitude_centre" in cen_com.columns else ("LONGITUDE_CENTRE" if "LONGITUDE_CENTRE" in cen_com.columns else "lon_centre")
                                
                                if insee_col and lat_col and lon_col:
                                    dict_lat = pd.to_numeric(cen_com.set_index(insee_col)[lat_col], errors="coerce").to_dict()
                                    dict_lon = pd.to_numeric(cen_com.set_index(insee_col)[lon_col], errors="coerce").to_dict()
                                    
                                    pve_insee = df_pve.loc[missing_pve_mask, "INF-INSEE"].astype(str).str.extract(r"(\d{1,5})", expand=False).fillna("").str.zfill(5)
                                    df_pve.loc[missing_pve_mask, "x"] = df_pve.loc[missing_pve_mask, "x"].fillna(pve_insee.map(dict_lon))
                                    df_pve.loc[missing_pve_mask, "y"] = df_pve.loc[missing_pve_mask, "y"].fillna(pve_insee.map(dict_lat))
                        except Exception as e:
                            print(f"Exception fallback communes PVe: {e}")

                    x_col = "x" if "x" in df_pve.columns else None
                    y_col = "y" if "y" in df_pve.columns else None
                    if x_col and y_col:
                        pve_valid = df_pve.dropna(subset=[x_col, y_col])
                        date_col_pve = "INF-DATE-MIF" if "INF-DATE-MIF" in df_pve.columns else "INF-DATE-INTG"
                        col_ta_pve = "type_action" if "type_action" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else ("type_actio" if "type_actio" in df_pve.columns else None))
                        col_usager_pve = "type_usager" if "type_usager" in df_pve.columns else ("USAGER" if "USAGER" in df_pve.columns else None)
                        for _, r in pve_valid.iterrows():
                            procedures.append({
                                "type": "PVe",
                                "dc_id": str(r.get("DC_ID", "")).strip() if pd.notna(r.get("DC_ID")) else "",
                                "date_ctrl": str(r.get(date_col_pve, ""))[:10] if pd.notna(r.get(date_col_pve)) else "",
                                "type_action": str(r.get(col_ta_pve, "Non renseigné")).strip() if col_ta_pve and pd.notna(r.get(col_ta_pve)) else "Non renseigné",
                                "type_usager": str(r.get(col_usager_pve, "Non renseigné")).strip() if col_usager_pve and pd.notna(r.get(col_usager_pve)) else "Non renseigné",
                                "x": float(r[x_col]),
                                "y": float(r[y_col])
                            })
                
                geojson_data = None
                try:
                    import geopandas as gpd
                    if echelle == "pnf":
                        shp_path = Path(project_root) / "ref" / "programme" / "sig" / "PNF" / "aoa_2021_pnforets" / "AOA_2021_PNForets.shp"
                        gdf_boundary = gpd.read_file(shp_path)
                        gdf_boundary.crs = "EPSG:2154"
                        for col in gdf_boundary.columns:
                            if col != "geometry":
                                gdf_boundary[col] = gdf_boundary[col].astype(str)
                    else:
                        from ofbilan.cartographie.pochoir_helper import load_department_gdf
                        os.environ["BILANS_CARTO_ECHELLE"] = echelle
                        gdf_boundary = load_department_gdf(code, project_root=project_root, dissolve=(echelle != "region"))
                    if not gdf_boundary.empty:
                        if gdf_boundary.crs is None:
                            gdf_boundary.set_crs(epsg=2154, inplace=True)
                        gdf_boundary_wgs84 = gdf_boundary.to_crs("EPSG:4326")
                        for col in gdf_boundary_wgs84.columns:
                            if col != "geometry":
                                gdf_boundary_wgs84[col] = gdf_boundary_wgs84[col].astype(str)
                        geojson_data = json.loads(gdf_boundary_wgs84.to_json())
                        with open(Path(project_root) / "geojson_success.log", "w", encoding="utf-8") as f_ok:
                            f_ok.write(f"Loaded successfully. Scale: {echelle}, Code: {code}, Params: {json.dumps(params)}\n")
                            f_ok.write(json.dumps(geojson_data)[:1000] + "\n")
                except Exception as e:
                    import traceback
                    with open(Path(project_root) / "geojson_error.log", "w", encoding="utf-8") as f_err:
                        f_err.write(f"Error loading boundary geojson: {e}\n")
                        traceback.print_exc(file=f_err)
                    print(f"Error loading boundary geojson: {e}")

                response_data = {
                    "stats": {
                        "total_controles": int(total_controles),
                        "total_pej": int(total_pej),
                        "total_pa": int(total_pa),
                        "total_pve": int(total_pve)
                    },
                    "charts": {
                        "results": results_counts,
                        "usagers": usagers_counts,
                        "domains": domains_counts,
                        "themes": themes_counts,
                        "seasonality": {
                            "controls": monthly_controls,
                            "infractions": monthly_infractions
                        }
                    },
                    "points": points,
                    "procedures": procedures,
                    "geojson": geojson_data
                }

                log_debug("Construction geojson terminée.")

                _SESSION_CACHE["active"] = _original_cache_active
                
                log_debug("Envoi de la réponse JSON...")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                resp_json = json.dumps(clean_nan(response_data))
                self.wfile.write(resp_json.encode('utf-8'))
                log_debug("Réponse envoyée avec succès.")

            except Exception as e:
                try:
                    from ofbilan.common.chargeurs_donnees import _SESSION_CACHE
                    if '_original_cache_active' in locals():
                        _SESSION_CACHE["active"] = _original_cache_active
                except Exception:
                    pass
                import traceback
                import datetime
                err_log_dir = project_root / "tests" / "scratch"
                err_log_dir.mkdir(parents=True, exist_ok=True)
                err_log_path = err_log_dir / "serveur_error.log"
                with open(err_log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n--- Erreur API /data à {datetime.datetime.now()} ---\n")
                    traceback.print_exc(file=f)
                traceback.print_exc()
                if 'log_debug' in locals():
                    log_debug(f"!!! EXCEPTION CAPTURÉE !!!\n{traceback.format_exc()}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        elif self.path in ("/api/open-pdf", "/api/open-folder"):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data.decode('utf-8'))
            profil = params.get("profil")
            code = params.get("code", "")
            
            if not profil:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Profil non spécifié"}).encode('utf-8'))
                return
                
            try:
                from ofbilan.engine.execution_lots_profils import resolve_profile_output_dir
                out_dir = resolve_profile_output_dir(profil, code)
                
                if self.path == "/api/open-folder":
                    target = out_dir
                else:
                    pdfs = list(out_dir.glob("*.pdf"))
                    if not pdfs:
                        raise FileNotFoundError("Aucun fichier PDF trouvé dans le dossier de sortie.")
                    target = max(pdfs, key=lambda p: p.stat().st_mtime)
                
                if target.exists():
                    if sys.platform == "win32":
                        os.startfile(target)
                    elif sys.platform == "darwin":
                        subprocess.run(["open", str(target)], check=False)
                    else:
                        subprocess.run(["xdg-open", str(target)], check=False)
                        
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                else:
                    raise FileNotFoundError(f"Le chemin {target} n'existe pas.")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        else:
            super().do_POST()

def preload_data_async():
    import threading
    def target():
        def log_preload(msg):
            print(msg)
            _PRELOAD_LOGS.append(msg)
            if len(_PRELOAD_LOGS) > 20:
                _PRELOAD_LOGS.pop(0)
                
        try:
            log_preload("  Démarrage du chargement des données en arrière-plan...")
            project_root = Path(__file__).resolve().parents[2]
            from ofbilan.common.chargeurs_donnees import load_point_ctrl, load_pej, load_pa, load_pve
            
            # 1. Charger les points de contrôle (toutes les années disponibles)
            log_preload("  Chargement des points de contrôle...")
            load_point_ctrl(project_root)
            
            # 2. Charger les procédures pénales (PEJ)
            log_preload("  Chargement des enquêtes judiciaires...")
            load_pej(project_root)
            
            # 3. Charger les procédures administratives (PA)
            log_preload("  Chargement des procédures administratives...")
            load_pa(project_root)
            
            # 4. Charger les PVe
            log_preload("  Chargement des PVe...")
            load_pve(project_root)
            
            # 5. Charger le shapefile des départements
            try:
                from ofbilan.cartographie.pochoir_helper import get_departements_admin_shp, _load_all_departements
                shp = get_departements_admin_shp(project_root)
                log_preload("  Chargement des contours géographiques...")
                _load_all_departements(str(shp.resolve()))
            except Exception as e:
                log_preload(f"  Note: Impossible de pré-charger les contours : {e}")

            log_preload("  Données chargées avec succès en mémoire. L'explorer est prêt !")
            global _PRELOAD_STATUS
            _PRELOAD_STATUS = "ready"
        except Exception as e:
            log_preload(f"  Erreur lors du pré-chargement : {e}")

    threading.Thread(target=target, daemon=True).start()

def run_server():
    # S'assurer que l'on sert depuis le bon dossier
    os.chdir(str(WEB_DIR))
    
    # Lancement du pré-chargement des données en tâche de fond
    try:
        preload_data_async()
    except Exception as e:
        print(f"Impossible d'initialiser le pré-chargement : {e}")
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n=================================================================================")
        print(f"  Serveur OFBilan actif sur http://localhost:{PORT}")
        print(f"  L'explorateur s'ouvrira automatiquement à la fin du préchargement des données.")
        print(f"  Appuyez sur Ctrl+C pour arrêter le serveur.")
        print(f"=================================================================================\n")
        
        if os.environ.get("OFBILAN_RESTART") != "1":
            import webbrowser
            webbrowser.open(f"http://localhost:{PORT}/loading.html")
            
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServeur arrêté.")

if __name__ == "__main__":
    run_server()
