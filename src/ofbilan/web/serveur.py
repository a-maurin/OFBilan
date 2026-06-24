import http.server
import socketserver
import json
import os
import subprocess
import sys
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

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

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
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data.decode('utf-8'))

            try:
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

                project_root = Path(__file__).resolve().parents[3]

                # 1. Charger la configuration du profil
                profile_cfg = load_profile_config(project_root, profil)
                cfg_obj = BilanConfig.from_strings(
                    date_deb=date_deb,
                    date_fin=date_fin,
                    echelle=echelle,
                    code=code,
                    root=project_root
                )

                # 2. Chargement et filtrage des points de contrôle
                df_pts = load_point_ctrl(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin)
                if profile_cfg.get("pipeline") != "global":
                    df_pts = _filter_point_ctrl(df_pts, profile_cfg)
                if type_usager:
                    df_pts = df_pts[df_pts["type_usager"].astype(str).str.lower().str.contains(type_usager.lower(), na=False)].copy()
                if domaines:
                    td_lower = {d.strip().lower() for d in domaines if d.strip()}
                    if td_lower and "domaine" in df_pts.columns:
                        df_pts = df_pts[df_pts["domaine"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if themes:
                    tt_lower = {t.strip().lower() for t in themes if t.strip()}
                    if tt_lower:
                        col_pt_theme = "theme" if "theme" in df_pts.columns else ("type_actio" if "type_actio" in df_pts.columns else None)
                        if col_pt_theme:
                            df_pts = df_pts[df_pts[col_pt_theme].astype(str).str.strip().str.lower().isin(tt_lower)].copy()
                if types_action:
                    ta_lower = {a.strip().lower() for a in types_action if a.strip()}
                    if ta_lower:
                        col_ta = "type_actio" if "type_actio" in df_pts.columns else ("type_action" if "type_action" in df_pts.columns else None)
                        if col_ta:
                            df_pts = df_pts[df_pts[col_ta].astype(str).str.strip().str.lower().isin(ta_lower)].copy()

                total_controles = len(df_pts)

                # 3. Chargement et filtrage PEJ
                df_pej = load_pej(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin)
                if profile_cfg.get("pipeline") != "global":
                    df_pej = _filter_pej(df_pej, profile_cfg, cfg_obj, df_pts)
                if type_usager:
                    df_pej = df_pej[df_pej["type_usager"].astype(str).str.lower().str.contains(type_usager.lower(), na=False)].copy()
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
                            df_pej = df_pej[df_pej[col_ta].astype(str).str.strip().str.lower().isin(ta_lower)].copy()
                total_pej = len(df_pej)

                # 4. Chargement et filtrage PA
                try:
                    df_pa = load_pa(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin)
                    if profile_cfg.get("pipeline") != "global":
                        df_pa = _filter_pa(df_pa, profile_cfg, cfg_obj, df_pts)
                    else:
                        entity_sds = cfg_obj.entity_sds
                        if entity_sds and "ENTITE_ORIGINE_PROCEDURE" in df_pa.columns:
                            df_pa = df_pa[df_pa["ENTITE_ORIGINE_PROCEDURE"].isin(entity_sds)].copy()
                        from ofbilan.common.utilitaires_metier import resolve_type_usager_champ
                        usager_col = resolve_type_usager_champ(df_pa)
                        if type_usager and usager_col:
                            df_pa = df_pa[df_pa[usager_col].astype(str).str.lower().str.contains(type_usager.lower(), na=False)].copy()
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
                            col_ta = "TYPE_ACTION" if "TYPE_ACTION" in df_pa.columns else None
                            if col_ta:
                                df_pa = df_pa[df_pa[col_ta].astype(str).str.strip().str.lower().isin(ta_lower)].copy()
                    total_pa = len(df_pa)
                except Exception:
                    total_pa = 0

                # 5. Chargement et filtrage PVe
                try:
                    df_pve = load_pve(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin)
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
                            col_ta = "type_action" if "type_action" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else None)
                            if col_ta:
                                df_pve = df_pve[df_pve[col_ta].astype(str).str.strip().str.lower().isin(ta_lower)].copy()
                    total_pve = len(df_pve)
                except Exception:
                    total_pve = 0

                # 5. Calcul des répartitions statistiques (identiques aux bilans PDF)
                results_counts = {"Conforme": 0, "Non-conforme": 0, "En attente": 0}
                if "resultat" in df_pts.columns and not df_pts.empty:
                    res_series = classify_resultat_controle_series(df_pts["resultat"])
                    results_counts["Conforme"] = int((res_series == "Conforme").sum())
                    results_counts["Non-conforme"] = int(res_series.isin(["Infraction", "Manquement"]).sum())
                    results_counts["En attente"] = int((res_series == "En attente").sum())

                usagers_counts = {}
                if "type_usager" in df_pts.columns and not df_pts.empty:
                    df_us = agg_effectifs_usagers(df_pts, "point_ctrl", "type_usager")
                    for _, row in df_us.iterrows():
                        u_label = str(row["type_usager"]).strip() if pd.notna(row.get("type_usager")) else "Non renseigné"
                        u_val = int(row["nb"]) if pd.notna(row.get("nb")) else 0
                        if u_label:
                            usagers_counts[u_label] = u_val

                domains_counts = {}
                if "domaine" in df_pts.columns and not df_pts.empty:
                    pt_filled = df_pts.copy()
                    pt_filled["domaine"] = pt_filled["domaine"].fillna("Hors domaine").astype(str).str.strip()
                    vc = pt_filled["domaine"].value_counts()
                    for k, v in vc.items():
                        k_label = str(k).strip() if pd.notna(k) else "Hors domaine"
                        if k_label:
                            domains_counts[k_label] = int(v)

                themes_counts = {}
                col_theme = "theme" if "theme" in df_pts.columns else ("type_actio" if "type_actio" in df_pts.columns else None)
                if col_theme and not df_pts.empty:
                    pt_theme_filled = df_pts.copy()
                    pt_theme_filled[col_theme] = pt_theme_filled[col_theme].fillna("Hors theme").astype(str).str.strip()
                    vc = pt_theme_filled[col_theme].value_counts()
                    for k, v in vc.items():
                        k_label = str(k).strip() if pd.notna(k) else "Hors thème"
                        if k_label:
                            themes_counts[k_label] = int(v)

                monthly_controls = [0] * 12
                monthly_infractions = [0] * 12
                if "date_ctrl" in df_pts.columns and not df_pts.empty:
                    dt_series = pd.to_datetime(df_pts["date_ctrl"], errors="coerce")
                    res_series = classify_resultat_controle_series(df_pts["resultat"]) if "resultat" in df_pts.columns else pd.Series("En attente", index=df_pts.index)
                    for month in range(1, 13):
                        mask_month = dt_series.dt.month == month
                        monthly_controls[month - 1] = int(mask_month.sum())
                        monthly_infractions[month - 1] = int((mask_month & res_series.isin(["Infraction", "Manquement"])).sum())

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

                geojson_data = None
                try:
                    from ofbilan.cartographie.pochoir_helper import load_department_gdf
                    os.environ["BILANS_CARTO_ECHELLE"] = echelle
                    gdf_boundary = load_department_gdf(code, project_root=project_root)
                    if not gdf_boundary.empty:
                        gdf_boundary_wgs84 = gdf_boundary.to_crs("EPSG:4326")
                        geojson_data = json.loads(gdf_boundary_wgs84.to_json())
                except Exception as e:
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
                    "geojson": geojson_data
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(clean_nan(response_data)).encode('utf-8'))

            except Exception as e:
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

def run_server():
    # S'assurer que l'on sert depuis le bon dossier
    os.chdir(str(WEB_DIR))
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n=======================================================")
        print(f"  Serveur OFBilan actif sur http://localhost:{PORT}")
        print(f"  Ouvrez cette adresse dans votre navigateur web.")
        print(f"  Appuyez sur Ctrl+C pour arrêter le serveur.")
        print(f"=======================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServeur arrêté.")

if __name__ == "__main__":
    run_server()
