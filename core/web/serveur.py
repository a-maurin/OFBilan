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

"""
========================================================================================
MODULE : SERVEUR WEB LOCAL ET API REST (`serveur.py`)
========================================================================================
Ce module implémente le serveur Web HTTP local (basé sur `http.server.SimpleHTTPRequestHandler`)
qui alimente l'interface utilisateur web d'OFBilan (Édition de Bilan Web & Explorateur).

Endpoints et rôles API :
  1. `/api/generate` : déclenche la génération d'un bilan PDF / Excel en arrière-plan.
  2. `/api/profiles` : fournit la liste dynamique des profils YAML et de leurs paramètres.
  3. `/api/explorer/data` : renvoie les données spatiales et tabulaires pour la carte interactive Leaflet.
  4. `/api/config` : gestion des paramètres utilisateur et préférences de l'application.
  5. Service des fichiers statiques HTML, CSS, JavaScript et assets du dossier web.
========================================================================================
"""
from __future__ import annotations
import http.server
import threading
import socketserver
import json
import os
import subprocess
import sys
import datetime
from pathlib import Path

def check_is_debug() -> bool:
    if "--debug" in sys.argv or os.environ.get("DEBUG") == "1" or os.environ.get("OFBILAN_DEBUG") == "1":
        return True
    try:
        from core.parametres_utilisateur import lire_parametres
        return bool(lire_parametres().get("tech", {}).get("mode_debug", False))
    except Exception:
        return False

IS_DEBUG = check_is_debug()

def apply_server_debug_mode(enabled: bool | None = None) -> bool:
    global IS_DEBUG
    if enabled is None:
        IS_DEBUG = check_is_debug()
    else:
        IS_DEBUG = bool(enabled)
    try:
        import logging
        from core.configuration_journalisation import configure_logging
        configure_logging(logging.DEBUG if IS_DEBUG else logging.INFO)
    except Exception:
        pass
    return IS_DEBUG

WEB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB_DIR))
SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

try:
    from core.parametres_utilisateur import lire_parametres
    _params = lire_parametres()
    PORT = int(_params.get("tech", {}).get("port_serveur", 8000))
except Exception:
    PORT = 8000

_PRELOAD_LOGS = []

def _get_plugin_version(default: str = "1.0.7") -> str:
    metadata_path = SRC_DIR / "metadata.txt"
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf8') as f:
                for line in f:
                    if line.startswith('version='):
                        val = line.strip().split('=')[1].strip()
                        if val:
                            return val
        except Exception:
            pass
    return default

_PRELOAD_STATUS = "loading"
_preload_lock = threading.Lock()

try:
    from core.chemins_projet import get_app_data_dir
    _SERVER_LOG_FILE = get_app_data_dir() / "logs" / "serveur_web.log"
except Exception:
    _SERVER_LOG_FILE = SRC_DIR / "logs" / "serveur_web.log"

_server_log_lock = threading.Lock()
_MAX_SERVER_RUNS = 3

import time

_LAST_REQUEST_TIME = time.time()
_watchdog_started = False
_watchdog_lock = threading.Lock()


def touch_watchdog() -> None:
    """Réinitialise le compteur d'inactivité du watchdog."""
    global _LAST_REQUEST_TIME
    _LAST_REQUEST_TIME = time.time()


def start_watchdog(timeout_seconds: int = 1800) -> None:
    """Démarre le watchdog d'inactivité (30 min par défaut)."""
    global _watchdog_started
    with _watchdog_lock:
        if _watchdog_started:
            return
        _watchdog_started = True

    env_val = os.environ.get("OFBILAN_WATCHDOG_TIMEOUT")
    if env_val is not None:
        try:
            timeout_seconds = int(env_val)
        except ValueError:
            pass

    if timeout_seconds <= 0:
        return

    def _loop():
        global _LAST_REQUEST_TIME
        while True:
            time.sleep(30)
            idle = time.time() - _LAST_REQUEST_TIME
            if idle >= timeout_seconds:
                log_server(f"Inactivité détectée ({int(idle // 60)} min). Extinction automatique du serveur.", level="INFO")
                _cleanup_server_pid()
                os._exit(0)

    t = threading.Thread(target=_loop, daemon=True, name="WatchdogInactivite")
    t.start()


def _get_pid_file() -> Path:
    try:
        from core.chemins_projet import get_app_data_dir
        return get_app_data_dir() / "server.pid"
    except Exception:
        return SRC_DIR / "server.pid"


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            cwd_win = os.environ.get("SystemRoot", r"C:\Windows")
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd_win,
            )
            return str(pid) in res.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        cwd_win = os.environ.get("SystemRoot", r"C:\Windows")
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False, cwd=cwd_win)
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def _register_server_pid() -> None:
    pid_file = _get_pid_file()
    try:
        if pid_file.exists():
            old_pid_str = pid_file.read_text(encoding="utf-8").strip()
            if old_pid_str.isdigit():
                old_pid = int(old_pid_str)
                if old_pid != os.getpid() and _is_pid_alive(old_pid):
                    log_server(f"Processus serveur précédent orphelin détecté (PID {old_pid}). Extinction...", level="WARNING")
                    _kill_pid(old_pid)
    except Exception as e:
        log_server(f"Impossible de vérifier le fichier PID : {e}", level="WARNING")

    try:
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        log_server(f"Impossible d'enregistrer le fichier PID : {e}", level="WARNING")


def _cleanup_server_pid() -> None:
    try:
        pid_file = _get_pid_file()
        if pid_file.exists():
            current = pid_file.read_text(encoding="utf-8").strip()
            if current == str(os.getpid()):
                pid_file.unlink(missing_ok=True)
    except Exception:
        pass


def init_server_logger(log_file: Path | str | None = None) -> Path:
    """
    Initialise le fichier de log de débogage du serveur web.
    Conserve les 2 derniers runs précédents du serveur (afin que le nouveau run soit le 3e max)
    et écrit la balise d'en-tête === START RUN ... ===.
    """
    target_log = Path(log_file) if log_file else _SERVER_LOG_FILE
    target_log.parent.mkdir(parents=True, exist_ok=True)
    
    with _server_log_lock:
        existing_runs = []
        if target_log.exists():
            try:
                content = target_log.read_text(encoding="utf-8")
                raw_chunks = content.split("=== START RUN ")
                for chunk in raw_chunks:
                    if chunk.strip():
                        existing_runs.append("=== START RUN " + chunk)
            except Exception:
                existing_runs = []
        
        max_previous = max(0, _MAX_SERVER_RUNS - 1)
        if len(existing_runs) > max_previous:
            existing_runs = existing_runs[-max_previous:]
        
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_header = f"=== START RUN [{now_str}] (PID: {os.getpid()}) ===\n"
        
        new_content = "".join(existing_runs)
        if new_content and not new_content.endswith("\n\n"):
            if not new_content.endswith("\n"):
                new_content += "\n"
            new_content += "\n"
        new_content += new_header
        
        target_log.write_text(new_content, encoding="utf-8")
    return target_log

def log_server(msg: str, level: str = "INFO", log_file: Path | str | None = None) -> None:
    """
    Inscrit un message horodaté dans le fichier de log du serveur et sur la console via logger.
    """
    target_log = Path(log_file) if log_file else _SERVER_LOG_FILE
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{now_str}] [{level}] {msg}\n"
    
    with _server_log_lock:
        try:
            target_log.parent.mkdir(parents=True, exist_ok=True)
            with open(target_log, "a", encoding="utf-8") as f:
                f.write(formatted_msg)
        except Exception:
            pass

    try:
        import logging
        logger = logging.getLogger("ofbilan.serveur")
        lvl = getattr(logging, level.upper(), logging.INFO)
        logger.log(lvl, msg)
    except Exception:
        pass

def finalize_server_logger(reason: str = "Stopped", log_file: Path | str | None = None) -> None:
    """
    Inscrit la balise de fin de run === END RUN ... === dans le log du serveur.
    """
    target_log = Path(log_file) if log_file else _SERVER_LOG_FILE
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer = f"=== END RUN [{now_str}] (Status: {reason}) ===\n\n"
    
    with _server_log_lock:
        try:
            if target_log.exists():
                with open(target_log, "a", encoding="utf-8") as f:
                    f.write(footer)
        except Exception:
            pass


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
    changelog_path = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
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

_DIRECTEUR_ENQUETE_COLS = (
    "DIRECTEUR_ENQUETE", "DIRECTEUR ENQUETE", "DIRECTEUR_D_ENQUETE",
    "NOM_DIRECTEUR_ENQUETE", "DIRECTEUR_DE_L_ENQUETE",
    "RESPONSABLE_ENQUETE", "PILOTE_ENQUETE", "DIRECTEUR",
)


def _extract_directeur_enquete(record: dict) -> str:
    """Extrait l'identité du directeur d'enquête depuis un enregistrement PEJ."""
    import pandas as pd
    for col in _DIRECTEUR_ENQUETE_COLS:
        val = record.get(col)
        if val is not None and pd.notna(val):
            s = str(val).strip()
            if s and s not in ("N/A", "nan", "None", "<NA>"):
                return s
    return ""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def address_string(self):
        host, _ = self.client_address[:2]
        return str(host)

    def handle_one_request(self):
        touch_watchdog()
        return super().handle_one_request()

    def log_message(self, format, *args):
        msg = format % args
        if IS_DEBUG:
            log_server(f"HTTP {self.address_string()} - {msg}", level="DEBUG")
        else:
            code = str(args[1]) if len(args) > 1 else ""
            if code.startswith(("4", "5")):
                log_server(f"HTTP Error {self.address_string()} - {msg}", level="ERROR")

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def handle(self):
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            log_server(f"Connexion réseau interrompue par le client ({e.__class__.__name__})", level="DEBUG")

    def do_GET(self):
        from core.chemins_projet import PROJECT_ROOT
        project_root = PROJECT_ROOT
        parsed_path = self.path.split('?')[0]
        if parsed_path == "/favicon.ico":
            ico_path = WEB_DIR / "favicon.ico"
            if ico_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'image/x-icon')
                content = ico_path.read_bytes()
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            png_path = WEB_DIR / "icon.png"
            if png_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                content = png_path.read_bytes()
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # Route pour servir les logos et ressources du répertoire ref/
        if parsed_path.startswith("/ref/"):
            ref_path = SRC_DIR / parsed_path.lstrip('/')
            if ref_path.exists() and ref_path.is_file():
                self.send_response(200)
                if ref_path.suffix == '.png':
                    self.send_header('Content-Type', 'image/png')
                elif ref_path.suffix == '.svg':
                    self.send_header('Content-Type', 'image/svg+xml')
                self.end_headers()
                with open(ref_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "File not found")
                return

        if parsed_path == "/api/preload-status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            with _preload_lock:
                payload = {"status": _PRELOAD_STATUS, "logs": list(_PRELOAD_LOGS)}
            self.wfile.write(json.dumps(payload).encode('utf-8'))
            return

        if parsed_path == "/api/system-health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            try:
                from core.common.chargeurs_donnees import get_source_files_metadata
                import shutil
                out_dir = SRC_DIR / "data" / "out"
                out_dir.mkdir(parents=True, exist_ok=True)
                usage = shutil.disk_usage(out_dir)
                health_info = {
                    "status": "OK",
                    "plugin_version": _get_plugin_version(),
                    "python_version": sys.version.split()[0],
                    "platform": sys.platform,
                    "disk_free_mb": round(usage.free / (1024 * 1024), 1),
                    "sources": get_source_files_metadata(SRC_DIR),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as exc:
                health_info = {"status": "ERROR", "message": str(exc)}
            self.wfile.write(json.dumps(health_info, ensure_ascii=False).encode('utf-8'))
            return
        if parsed_path == "/api/profile-schema":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            try:
                import yaml
                schema_path = SRC_DIR / "config" / "profils_bilan" / "schema_ui.yaml"
                if schema_path.exists():
                    schema_data = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
                else:
                    schema_data = {}
                self.wfile.write(json.dumps(schema_data, ensure_ascii=False).encode('utf-8'))
            except Exception as exc:
                self.wfile.write(json.dumps({"error": str(exc)}).encode('utf-8'))
            return

        if parsed_path == "/api/update-sources":
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            script_path = SRC_DIR / "scripts" / "donnees" / "fetch_sources.py"
            if not script_path.exists():
                script_path = SRC_DIR / "scripts" / "fetch_sources.py"

            import subprocess
            try:
                process = subprocess.Popen(
                    [sys.executable, "-u", str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(SRC_DIR)
                )

                _timeout_hit = threading.Event()

                def _kill_on_timeout():
                    import time
                    time.sleep(300)
                    if process.poll() is None:
                        try:
                            process.kill()
                        except Exception:
                            pass
                        _timeout_hit.set()

                t = threading.Thread(target=_kill_on_timeout, daemon=True)
                t.start()

                for line in iter(process.stdout.readline, ''):
                    if not line: break
                    msg = f"data: {line.strip()}\n\n"
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
                process.wait()

                if _timeout_hit.is_set():
                    msg = "data: [ERREUR] Délai dépassé (5 min). Le serveur SSSC ne répond pas. Vérifiez votre connexion réseau.\n\n"
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
                else:
                    msg = f"data: [TERMINE] Code de retour: {process.returncode}\n\n"
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
            except Exception as e:
                msg = f"data: [ERREUR] {str(e)}\n\n"
                self.wfile.write(msg.encode('utf-8'))
                self.wfile.flush()
            return

        if parsed_path == "/api/check-sources":
            sources_dir = SRC_DIR / "data" / "sources"
            needs_update = True
            if sources_dir.exists():
                items = [p for p in sources_dir.iterdir() if p.name != ".gitkeep"]
                if items:
                    needs_update = False
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps({"needs_update": needs_update}).encode('utf-8'))
            return

        if parsed_path == "/api/cache/clear":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            try:
                from core.common.chargeurs_donnees import clear_session_cache, clear_disk_cache
                clear_session_cache()
                deleted_count = clear_disk_cache()
                res = {"success": True, "deleted": deleted_count, "message": "Cache mémoire et disque vidés avec succès."}
            except Exception as e:
                res = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
            return

        if parsed_path == "/api/logs/open":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            try:
                from core.chemins_projet import get_app_data_dir
                log_dir = get_app_data_dir() / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                if sys.platform == "win32":
                    os.startfile(str(log_dir))
                else:
                    subprocess.Popen(["xdg-open", str(log_dir)])
                res = {"success": True, "path": str(log_dir)}
            except Exception as e:
                res = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
            return

        if parsed_path == "/api/logs/download":
            target_log = _SERVER_LOG_FILE
            if target_log.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="serveur_web.log"')
                self.end_headers()
                with open(target_log, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write("Aucun journal disponible.".encode('utf-8'))
            return

        if parsed_path == "/api/check_update":
            import urllib.request
            import ssl
            
            current_version = _get_plugin_version(default="0.0.0")
            update_data = {"update_available": False, "latest_version": current_version, "zip_url": ""}
            
            try:
                req = urllib.request.Request('https://api.github.com/repos/a-maurin/OFBilan/releases/latest')
                req.add_header('User-Agent', 'OFBilan-Web-App')
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                response = urllib.request.urlopen(req, timeout=5, context=ctx)
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get('tag_name', '').lstrip('v')
                
                if latest_version and latest_version > current_version:
                    zip_url = data.get('html_url')
                    for asset in data.get('assets', []):
                        if asset.get('name', '').endswith('.zip'):
                            zip_url = asset.get('browser_download_url')
                            break
                    update_data["update_available"] = True
                    update_data["latest_version"] = latest_version
                    update_data["zip_url"] = zip_url
            except Exception as e:
                print(f"  [Update] Impossible de vérifier la mise à jour: {e}")
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(update_data).encode('utf-8'))
            return

        if parsed_path == '/api/restart':
            # Endpoint pour recharger les données (simule un redémarrage)
            import time
            import threading
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "restarting"}).encode('utf-8'))
            print("Rechargement des données demandé via l'interface web...")
            
            def reload_data():
                time.sleep(0.5)
                try:
                    from core.common.chargeurs_donnees import (
                        _POINT_CTRL_RAW_CACHE, _PEJ_RAW_CACHE, 
                        _PA_RAW_CACHE, _PVE_RAW_CACHE, clear_session_cache
                    )
                    _POINT_CTRL_RAW_CACHE.clear()
                    _PEJ_RAW_CACHE.clear()
                    _PA_RAW_CACHE.clear()
                    _PVE_RAW_CACHE.clear()
                    clear_session_cache()
                except Exception as e:
                    print("Erreur clear cache:", e)
                
                preload_data_async()
                
            threading.Thread(target=reload_data, daemon=True).start()
            return
            
        elif parsed_path == '/api/shutdown':
            # Endpoint pour éteindre le serveur
            import time
            import threading
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "shutting down"}).encode('utf-8'))
            log_server("Extinction du serveur demandée via l'interface web...", level="INFO")
            
            def shutdown():
                time.sleep(0.3)
                _cleanup_server_pid()
                finalize_server_logger(reason="Stopped via Web GUI")
                def _force_exit():
                    time.sleep(1.5)
                    os._exit(0)
                threading.Thread(target=_force_exit, daemon=True).start()
                try:
                    self.server.shutdown()
                except Exception:
                    pass
                os._exit(0)
                
            threading.Thread(target=shutdown, daemon=True).start()
            return

        if parsed_path == "/api/version":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"version": get_latest_version()}).encode('utf-8'))
            return

        if parsed_path == "/api/settings":
            try:
                from core.parametres_utilisateur import lire_parametres
                parametres = lire_parametres()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(parametres).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        if parsed_path in ("/api/gabarits", "/api/gabarits/list"):
            try:
                from core.common.chargeur_gabarits import list_gabarits
                gabarits = list_gabarits(SRC_DIR)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(json.dumps(gabarits, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        if parsed_path in ("/api/gabarit/detail", "/api/gabarits/detail"):
            try:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                gid = (qs.get("id") or ["gabarit_defaut"])[0]
                from core.common.chargeur_gabarits import load_gabarit, is_system_gabarit
                import yaml
                data = load_gabarit(gid, SRC_DIR)
                if data:
                    is_sys = is_system_gabarit(gid, SRC_DIR)
                    raw_yaml = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
                    resp = {"success": True, "data": data, "is_system": is_sys, "raw_yaml": raw_yaml}
                    status_code = 200
                else:
                    resp = {"success": False, "error": f"Gabarit '{gid}' introuvable."}
                    status_code = 404
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        if parsed_path == "/api/profils":
            try:
                import yaml
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                target = (qs.get("target") or [None])[0]
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
                excluded_ids = {"pnf_foret", "_defaults", "types_usager", "synthese_activite_PA_PJ"}
                if target == "explorer":
                    excluded_ids.update({"pnf_v2", "types_usager_cible", "procedures_pve"})

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
                                if val_id in excluded_ids:
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
                                    "departements": data.get("departements", []),
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
        import urllib.parse
        from pathlib import Path
        from core.chemins_projet import PROJECT_ROOT
        project_root = PROJECT_ROOT
        parsed_path = urllib.parse.urlparse(self.path).path

        if parsed_path == "/api/shutdown":
            return self.do_GET()

        if parsed_path == "/api/log":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                log_data = json.loads(post_data.decode('utf-8'))
                
                level = str(log_data.get("level", "INFO")).upper()
                msg = str(log_data.get("message", ""))
                source = str(log_data.get("source", "JS"))
                line = str(log_data.get("line", ""))
                ctx = log_data.get("context")
                
                ctx_str = f" | Context: {json.dumps(ctx, ensure_ascii=False)}" if ctx else ""
                loc_str = f" [{source}:{line}]" if line else f" [{source}]"
                
                log_server(f"[CLIENT_JS]{loc_str} {msg}{ctx_str}", level=level)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                log_server(f"Erreur traitement /api/log : {e}", level="ERROR")
                self.send_response(400)
                self.end_headers()
                return

        elif parsed_path == "/api/settings":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                nouveaux_parametres = json.loads(post_data.decode('utf-8'))
                
                from core.parametres_utilisateur import lire_parametres, sauvegarder_parametres
                sauvegarder_parametres(nouveaux_parametres)
                
                parametres_mis_a_jour = lire_parametres()
                mode_debug_active = bool(parametres_mis_a_jour.get("tech", {}).get("mode_debug", False))
                apply_server_debug_mode(mode_debug_active)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(parametres_mis_a_jour).encode('utf-8'))
                return
            except Exception as e:
                log_server(f"Erreur traitement /api/settings : {e}", level="ERROR")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return

        elif parsed_path == "/api/generate":
            try:
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
                if params.get("gabarit"):
                    cmd.extend(["--gabarit", str(params["gabarit"])])

                # Options oui/non (cartes, brochure)
                if params.get("cartes") is True:
                    cmd.append("--cartes")
                    if isinstance(params.get("cartes_selection"), list):
                        for c in params["cartes_selection"]:
                            c_clean = str(c).strip()
                            if c_clean:
                                cmd.extend(["--carte", c_clean])
                elif params.get("cartes") is False:
                    cmd.append("--no-cartes")

                if params.get("brochure") is True:
                    cmd.append("--brochure")
                elif params.get("brochure") is False:
                    cmd.append("--no-brochure")

                is_debug_req = params.get("mode_debug")
                if is_debug_req is None:
                    is_debug_req = params.get("debug")
                if is_debug_req is None:
                    try:
                        from core.parametres_utilisateur import lire_parametres
                        is_debug_req = bool(lire_parametres().get("tech", {}).get("mode_debug", False))
                    except Exception:
                        is_debug_req = False

                if is_debug_req:
                    cmd.append("--debug")

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
                    project_root = str(Path(__file__).resolve().parents[2])
                    src_dir = str(Path(__file__).resolve().parents[2])
                    env["PYTHONPATH"] = src_dir + os.pathsep + project_root + os.pathsep + env.get("PYTHONPATH", "")
                    env["PYTHONIOENCODING"] = "utf-8"
                    env["PYTHONDONTWRITEBYTECODE"] = "1"

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
                            try:
                                self.wfile.write(line.encode('utf-8'))
                                self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                log_server("Client web déconnecté pendant la génération. Arrêt du processus de calcul.", level="WARNING")
                                try:
                                    process.kill()
                                except Exception:
                                    pass
                                break

                    process.wait()
                    if process.returncode == 0:
                        self.wfile.write("\n[SUCCESS] Génération terminée avec succès.\n".encode('utf-8'))
                    else:
                        self.wfile.write(f"\n[ERREUR] Le processus s'est arrêté avec le code d'erreur {process.returncode}.\n".encode('utf-8'))
                except Exception as e:
                    self.wfile.write(f"\n[ERREUR] Impossible de lancer le traitement : {e}\n".encode('utf-8'))
                self.wfile.flush()

            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f"ERREUR CATASTROPHIQUE SERVEUR: {str(e)}".encode('utf-8'))
                except Exception:
                    pass

        elif parsed_path == "/api/data":
            try:
                from core.chemins_projet import get_app_data_dir
                debug_log = get_app_data_dir() / "logs" / "api_data_debug.log"
                debug_log.parent.mkdir(parents=True, exist_ok=True)
                def log_debug(msg):
                    if IS_DEBUG:
                        with open(debug_log, "a", encoding="utf-8") as f:
                            f.write(f"[{datetime.datetime.now()}] {msg}\n")
                        
                log_debug("=== NOUVELLE REQUÊTE /api/data ===")
                
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                params = json.loads(post_data.decode('utf-8'))
                log_debug(f"Params décodés: {params}")

                from core.common.chargeurs_donnees import load_point_ctrl, load_pej, load_pa, load_pve
                from core.engine.orchestrateur_profils import (
                    load_profile_config,
                    _filter_point_ctrl,
                    _filter_pej,
                    _filter_pa,
                    _filter_pve
                )
                from core.common.utilitaires_metier import classify_resultat_controle_series, agg_effectifs_usagers
                from core.common.bilan_config import BilanConfig
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
                
                # Forcer l'échelle nationale pour charger toutes les données avant restriction SIG pour TUB
                if profile_cfg.get("restrict_geo") == "tub":
                    echelle = "national"
                    code = "FR"
                
                sources_cfg = profile_cfg.get("sources", {})
                load_pts_flag = sources_cfg.get("point_ctrl", True)
                load_pej_flag = sources_cfg.get("pej", True)
                load_pa_flag = sources_cfg.get("pa", True)
                load_pve_flag = sources_cfg.get("pve", True)
                
                # Desactiver PVe si on filtre sur Domaines, Thèmes ou Type d'action (Optionnel)
                if ((domaines and any(d.strip() for d in (domaines if isinstance(domaines, list) else [domaines]))) or
                    (themes and any(t.strip() for t in (themes if isinstance(themes, list) else [themes]))) or
                    (types_action and any(a.strip() for a in (types_action if isinstance(types_action, list) else [types_action])))):
                    if profil == "global":
                        profile_cfg = dict(profile_cfg)
                        profile_cfg["analyse_PVe"] = False
                        if "sources" in profile_cfg:
                            profile_cfg["sources"] = dict(profile_cfg["sources"])
                            profile_cfg["sources"]["pve"] = False
                        load_pve_flag = False

                cfg_obj = BilanConfig.from_strings(
                    date_deb=date_deb,
                    date_fin=date_fin,
                    echelle=echelle,
                    code=code,
                    root=project_root
                )

                from core.common.chargeurs_donnees import _SESSION_CACHE
                _original_cache_active = _SESSION_CACHE["active"]
                _SESSION_CACHE["active"] = True

                # Bug B : initialisation préventive pour éviter UnboundLocalError
                tu_lower = set()

                # 2. Chargement et filtrage des points de contrôle
                log_debug(f"Début chargement Points de contrôle (load_pts_flag={load_pts_flag})")
                df_pts_unfiltered = load_point_ctrl(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin) if load_pts_flag else pd.DataFrame()
                log_debug(f"Points de contrôle chargés : {len(df_pts_unfiltered)} lignes")
                df_pts = df_pts_unfiltered.copy()
                if profile_cfg.get("pipeline") != "global":
                    df_pts = _filter_point_ctrl(df_pts, profile_cfg)
                
                # Filtrage multi-usagers ou simple (tu_lower déjà initialisé à set() plus haut)
                if type_usager:
                    if isinstance(type_usager, str):
                        type_usager = [type_usager]
                    tu_lower = {u.strip().lower() for u in type_usager if u.strip()}
                    if tu_lower and "type_usager" in df_pts.columns:
                        df_pts = df_pts[df_pts["type_usager"].astype(str).str.strip().str.lower().apply(
                            lambda val: any(u in str(val).lower() or str(val).lower() in u for u in tu_lower if str(val).strip())
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
                        lambda val: any(u in str(val).lower() or str(val).lower() in u for u in tu_lower if str(val).strip())
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
                            df_pej = df_pej[df_pej[col_pej_theme].astype(str).str.strip().str.lower().apply(
                                lambda val: any(t in str(val) for t in tt_lower) if val else False
                            )].copy()
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
                from core.common.utilitaires_metier import count_pa_induites_par_controles
                try:
                    df_pa = load_pa(project_root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin) if load_pa_flag else pd.DataFrame()
                    log_debug(f"PA chargées : {len(df_pa)} lignes")
                    if profile_cfg.get("pipeline") != "global":
                        df_pa = _filter_pa(df_pa, profile_cfg, cfg_obj, df_pts)
                    else:
                        entity_sds = cfg_obj.entity_sds
                        if entity_sds and "ENTITE_ORIGINE_PROCEDURE" in df_pa.columns:
                            df_pa = df_pa[df_pa["ENTITE_ORIGINE_PROCEDURE"].isin(entity_sds)].copy()
                        from core.common.utilitaires_metier import resolve_type_usager_champ
                        usager_col = resolve_type_usager_champ(df_pa)
                        if type_usager and usager_col and tu_lower:
                            df_pa = df_pa[df_pa[usager_col].astype(str).str.strip().str.lower().apply(
                                lambda val: any(u in str(val).lower() or str(val).lower() in u for u in tu_lower if str(val).strip())
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
                                df_pa = df_pa[df_pa[col_pa_theme].astype(str).str.strip().str.lower().apply(
                                    lambda val: any(t in str(val) for t in tt_lower) if val else False
                                )].copy()
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

                    if profile_cfg.get("pipeline") != "global":
                        df_pve = _filter_pve(df_pve, profile_cfg)
                    if themes:
                        tt_lower = {t.strip().lower() for t in themes if t.strip()}
                        if tt_lower:
                            col_pve_theme = "theme" if "theme" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else None)
                            if col_pve_theme:
                                df_pve = df_pve[df_pve[col_pve_theme].astype(str).str.strip().str.lower().apply(
                                    lambda val: any(t in str(val) for t in tt_lower) if val else False
                                )].copy()
                    if types_action:
                        ta_lower = {a.strip().lower() for a in types_action if a.strip()}
                        if ta_lower:
                            col_ta = "type_action" if "type_action" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else ("type_actio" if "type_actio" in df_pve.columns else ("INF-TYP-INF-STAT-LIB" if "INF-TYP-INF-STAT-LIB" in df_pve.columns else None)))
                            if col_ta:
                                df_pve = df_pve[df_pve[col_ta].astype(str).str.strip().str.lower().apply(
                                    lambda val: any(t in str(val) for t in ta_lower)
                                )].copy()

                    total_pve = len(df_pve)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Erreur chargement/filtrage PVe: {e}")
                    total_pve = 0

                # 4.bis. Restriction spatiale globale PNF ou TUB
                if echelle == "pnf":
                    import logging
                    from core.common.chargeurs_donnees import merge_pej_faits_locations
                    from core.engine.orchestrateur_profils import _apply_restrict_geo_pnf, _coalesced_insee_for_pnf_mask
                    log = logging.getLogger(__name__)
                    if not df_pej.empty:
                        df_pej = merge_pej_faits_locations(df_pej, project_root, echelle, code)
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

                elif profile_cfg.get("restrict_geo") == "tub":
                    import logging
                    from core.engine.orchestrateur_profils import _apply_restrict_geo_tub
                    log = logging.getLogger(__name__)
                    df_pts, df_pej, df_pa, df_pve = _apply_restrict_geo_tub(
                        df_pts, df_pej, df_pa, df_pve, project_root, log
                    )

                # 4.ter. Filtrage par organisme / service d'agents (OFB vs PNF) - réservé à l'Explorer Web
                agent_service = params.get("agent_service", "tous")
                if agent_service and str(agent_service).strip().lower() != "tous":
                    from core.engine.orchestrateur_profils import filter_by_agent_service
                    agent_cols = ["entite_ctrl", "entit_ctrl", "entite", "entit", "ENTITE", "ENTITE_CTRL", "UNITE_libelle", "unite_libelle", "service", "organisme"]
                    df_pts = filter_by_agent_service(df_pts, agent_cols, agent_service, profile_cfg)
                    df_pej = filter_by_agent_service(df_pej, agent_cols + ["ENTITE_ORIGINE_PROCEDURE"], agent_service, profile_cfg)
                    df_pa = filter_by_agent_service(df_pa, agent_cols + ["ENTITE_ORIGINE_PROCEDURE"], agent_service, profile_cfg)
                    df_pve = filter_by_agent_service(df_pve, agent_cols + ["UNITE_LIBELLE", "UNITE", "unite"], agent_service, profile_cfg)

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
                    
                    dept_s = pd.Series(index=df.index, dtype=str)
                    
                    # 1) Fallback prioritaire : si num_depart est dispo
                    for c in ["num_depart", "dept", "code_dept", "DEPT", "departement", "DEP", "DPT", "CODE_DEP"]:
                        if c in df.columns:
                            s = df[c].astype(str).str.strip()
                            s = s.where(s.notna() & (s.str.lower() != "nan") & (s != ""), None)
                            s = s.apply(lambda x: str(x).split(".")[0] if pd.notna(x) else x)
                            dept_s = dept_s.fillna(s.str.zfill(2).str[:2])
                            break
                            
                    for c in ["ENTITE_ORIGINE_PROCEDURE", "entite_origine_procedure"]:
                        if c in df.columns:
                            s = df[c].astype(str).str.extract(r'(\d+)')[0]
                            s = s.where(s.notna() & (s.str.lower() != "nan"), None)
                            dept_s = dept_s.fillna(s.str.zfill(2).str[:2])
                            break
                            
                    # 2) Priorité INSEE : écrase si présent (vrai lieu géographique)
                    for c in ["insee_comm", "insee_commun", "insee_com", "INF-INSEE"]:
                        if c in df.columns:
                            s = df[c].astype(str).str.strip()
                            s = s.where(s.notna() & (s.str.lower() != "nan") & (s != ""), None)
                            s = s.apply(lambda x: str(x).split(".")[0] if pd.notna(x) else x)
                            insee_dept = s.str.zfill(5).str[:2]
                            # on remplace si l'INSEE donne une info
                            dept_s = insee_dept.fillna(dept_s)
                            break

                    return dept_s.fillna("N/A")

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
                if not df_pts.empty and "x" in df_pts.columns and "y" in df_pts.columns:
                    df_pts_valid = df_pts.dropna(subset=["x", "y"]).copy()
                    df_pts_valid["_code_dept_calc"] = get_dept_series(df_pts_valid)
                    for row in df_pts_valid.to_dict("records"):
                        dc_val = row.get("dc_id")
                        date_val = row.get("date_ctrl")
                        res_val = row.get("resultat")
                        dom_val = row.get("domaine")
                        theme_val = row.get("theme")
                        action_val = row.get("type_action")
                        usager_val = row.get("type_usager")
                        com_val = row.get("nom_commun")
                        dept_calc = str(row.get("_code_dept_calc", "")).strip()
                        code_dept_val = "" if dept_calc in ("N/A", "nan", "None") else dept_calc

                        try:
                            x_val = float(row["x"])
                            y_val = float(row["y"])
                        except (ValueError, TypeError):
                            continue

                        points.append({
                            "dc_id": str(dc_val).strip() if pd.notna(dc_val) else "",
                            "date_ctrl": str(date_val)[:10] if pd.notna(date_val) else "",
                            "resultat": str(res_val).strip() if pd.notna(res_val) else "",
                            "domaine": str(dom_val).strip() if pd.notna(dom_val) else "",
                            "theme": str(theme_val).strip() if pd.notna(theme_val) else "",
                            "type_action": str(action_val).strip() if pd.notna(action_val) else "",
                            "type_usager": str(usager_val).strip() if pd.notna(usager_val) else "",
                            "nom_commun": str(com_val).strip() if pd.notna(com_val) else "",
                            "code_dept": code_dept_val,
                            "x": x_val,
                            "y": y_val
                        })

                # 7. Extraction des procédures (PEJ, PA, PVe) pour la cartographie
                #    - PEJ : points de contrôle dont code_pej est renseigné
                #    - PA  : points de contrôle dont code_pa est renseigné
                #    - PVe : coordonnées issues de load_pve (centroïdes communaux)
                from core.common.utilitaires_metier import is_filled_procedure_code
                procedures = []

                def _pts_to_proc(df, code_col, label):
                    """Extrait les procédures depuis point_ctrl en filtrant sur code_col non nul."""
                    arr = []
                    if df.empty or code_col not in df.columns or "x" not in df.columns or "y" not in df.columns:
                        return arr
                    mask = df[code_col].map(is_filled_procedure_code)
                    df_valid = df.loc[mask].dropna(subset=["x", "y"]).copy()
                    df_valid["_code_dept_calc"] = get_dept_series(df_valid)
                    col_ta = "type_actio" if "type_actio" in df.columns else ("type_action" if "type_action" in df.columns else None)
                    col_insee = next((c for c in ("code_insee", "insee_comm", "insee_com", "insee", "code_com") if c in df_valid.columns), None)
                    col_dom = next((c for c in ("domaine", "DOMAINE") if c in df_valid.columns), None)
                    col_th = next((c for c in ("theme", "THEME") if c in df_valid.columns), None)
                    col_res = next((c for c in ("resultat", "RESULTAT") if c in df_valid.columns), None)
                    col_com = next((c for c in ("nom_commun", "NOM_COM", "commune") if c in df_valid.columns), None)
                    for r in df_valid.to_dict("records"):
                        dept_calc = str(r.get("_code_dept_calc", "")).strip()
                        code_dept_proc = "" if dept_calc in ("N/A", "nan", "None") else dept_calc
                        insee_proc = str(r.get(col_insee, "")).strip() if col_insee and pd.notna(r.get(col_insee)) else ""
                        if insee_proc in ("N/A", "nan", "None", "<NA>"):
                            insee_proc = ""
                        try:
                            x_val = float(r["x"])
                            y_val = float(r["y"])
                        except (ValueError, TypeError):
                            continue
                        arr.append({
                            "type": label,
                            "dc_id": str(r.get("dc_id", "")).strip() if pd.notna(r.get("dc_id")) else "",
                            "date_ctrl": str(r.get("date_ctrl", ""))[:10] if pd.notna(r.get("date_ctrl")) else "",
                            "resultat": str(r.get(col_res, f"Infraction ({label})")).strip() if col_res and pd.notna(r.get(col_res)) else f"Infraction ({label})",
                            "domaine": str(r.get(col_dom, "")).strip() if col_dom and pd.notna(r.get(col_dom)) else "",
                            "theme": str(r.get(col_th, "")).strip() if col_th and pd.notna(r.get(col_th)) else "",
                            "type_action": str(r.get(col_ta, "Non renseigné")).strip() if col_ta and pd.notna(r.get(col_ta)) else "Non renseigné",
                            "type_usager": str(r.get("type_usager", "Non renseigné")).strip() if pd.notna(r.get("type_usager")) else "Non renseigné",
                            "nom_commun": str(r.get(col_com, "")).strip() if col_com and pd.notna(r.get(col_com)) else "",
                            "code_dept": code_dept_proc,
                            "code_insee": insee_proc,
                            "precision_loc": "Point de contrôle rattaché",
                            "x": x_val,
                            "y": y_val
                        })
                    return arr

                # Extraction des PEJ
                if not df_pej.empty:
                    try:
                        from core.common.chargeurs_donnees import merge_pej_faits_locations
                        df_pej_loc = merge_pej_faits_locations(df_pej, project_root, echelle, code)
                        
                        # --- FALLBACK 1: COORDONNEES VIA df_pts_unfiltered ---
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
                                mapped_x = dc_clean.map(dict_x)
                                mapped_y = dc_clean.map(dict_y)
                                found_pts = mapped_x.notna() & mapped_y.notna()
                                if found_pts.any():
                                    idx_found = dc_clean[found_pts].index
                                    df_pej_loc.loc[idx_found, "x_faits"] = mapped_x[found_pts]
                                    df_pej_loc.loc[idx_found, "y_faits"] = mapped_y[found_pts]
                                    if "precision_loc" in df_pej_loc.columns:
                                        df_pej_loc.loc[idx_found, "precision_loc"] = "Point de contrôle rattaché"

                        # --- FALLBACK 2: CENTROIDES COMMUNAUX POUR PEJ ---
                        missing_pej_mask = df_pej_loc["x_faits"].isna() | df_pej_loc["y_faits"].isna()
                        if missing_pej_mask.any():
                            try:
                                from core.common.chargeurs_donnees import load_communes_centroides
                                cen_com = load_communes_centroides(project_root)
                                if not cen_com.empty:
                                    insee_col = "code_insee" if "code_insee" in cen_com.columns else ("CODE_INSEE" if "CODE_INSEE" in cen_com.columns else "insee")
                                    lat_col = "lat" if "lat" in cen_com.columns else "latitude_centre"
                                    lon_col = "lon" if "lon" in cen_com.columns else "longitude_centre"
                                    
                                    if insee_col and lat_col in cen_com.columns and lon_col in cen_com.columns:
                                        dict_lat = pd.to_numeric(cen_com.set_index(insee_col)[lat_col], errors="coerce").to_dict()
                                        dict_lon = pd.to_numeric(cen_com.set_index(insee_col)[lon_col], errors="coerce").to_dict()
                                        
                                        col_insee_pej = next((c for c in ("code_insee", "insee_comm", "insee_com", "insee", "code_com") if c in df_pej_loc.columns), None)
                                        if col_insee_pej:
                                            pej_insee = df_pej_loc.loc[missing_pej_mask, col_insee_pej].astype(str).str.extract(r"(\d{1,5})", expand=False).fillna("").str.zfill(5)
                                            mapped_pej_x = pej_insee.map(dict_lon)
                                            mapped_pej_y = pej_insee.map(dict_lat)
                                            found_pej = mapped_pej_x.notna() & mapped_pej_y.notna()
                                            if found_pej.any():
                                                idx_pej = pej_insee[found_pej].index
                                                df_pej_loc.loc[idx_pej, "x_faits"] = mapped_pej_x[found_pej]
                                                df_pej_loc.loc[idx_pej, "y_faits"] = mapped_pej_y[found_pej]
                                                df_pej_loc.loc[idx_pej, "precision_loc"] = "Centroïde communal (Approximatif)"
                            except Exception as e:
                                print(f"Exception fallback communes PEJ: {e}")

                        if not df_pej_loc.empty:
                            df_pej_all = df_pej_loc.copy()
                            df_pej_all["_code_dept_calc"] = get_dept_series(df_pej_all)
                            for r in df_pej_all.to_dict("records"):
                                dept_calc = str(r.get("_code_dept_calc", "")).strip()
                                code_dept_pej = "" if dept_calc in ("N/A", "nan", "None") else dept_calc
                                insee_pej = str(r.get("code_insee", r.get("insee_comm", r.get("insee_com", r.get("insee", ""))))).strip()
                                if insee_pej in ("N/A", "nan", "None", "<NA>"):
                                    insee_pej = ""
                                
                                prec_val = str(r.get("precision_loc", "")).strip()
                                try:
                                    x_val = float(r["x_faits"]) if pd.notna(r.get("x_faits")) else None
                                    y_val = float(r["y_faits"]) if pd.notna(r.get("y_faits")) else None
                                except (ValueError, TypeError):
                                    x_val, y_val = None, None

                                if x_val is None or y_val is None:
                                    x_val, y_val = None, None
                                    prec_val = "Infraction non localisée"
                                elif not prec_val or prec_val in ("N/A", "nan", "None", "<NA>"):
                                    prec_val = "GPS Fait (Exacte)"

                                dom_val = str(r.get("DOMAINE", r.get("domaine", ""))).strip()
                                if dom_val in ("N/A", "nan", "None", "<NA>"): dom_val = ""
                                theme_val = str(r.get("THEME", r.get("theme", ""))).strip()
                                if theme_val in ("N/A", "nan", "None", "<NA>"): theme_val = ""
                                com_val = str(r.get("NOM_COM", r.get("NOM_COM_FAITS", r.get("nom_commun", r.get("commune", ""))))).strip()
                                if com_val in ("N/A", "nan", "None", "<NA>"): com_val = "Non géolocalisée"

                                procedures.append({
                                    "type": "PEJ",
                                    "dc_id": str(r.get("DC_ID", "")).strip() if pd.notna(r.get("DC_ID")) else "",
                                    "date_ctrl": str(r.get("DATE_REF", ""))[:10] if pd.notna(r.get("DATE_REF")) else "",
                                    "resultat": "Infraction (PEJ)",
                                    "domaine": dom_val,
                                    "theme": theme_val,
                                    "type_action": str(r.get("TYPE_ACTION", "Non renseigné")).strip() if pd.notna(r.get("TYPE_ACTION")) else "Non renseigné",
                                    "type_usager": str(r.get("type_usager", "Non renseigné")).strip() if pd.notna(r.get("type_usager")) else "Non renseigné",
                                    "nom_commun": com_val if com_val else "Non géolocalisée",
                                    "code_dept": code_dept_pej,
                                    "code_insee": insee_pej,
                                    "precision_loc": prec_val,
                                    "x": x_val,
                                    "y": y_val,
                                    "directeur_enquete": _extract_directeur_enquete(r),
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
                    if "precision_loc" not in df_pve.columns:
                        df_pve["precision_loc"] = pd.Series("GPS Fait (Exacte)", index=df_pve.index)
                        
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
                            from core.common.chargeurs_donnees import load_communes_centroides
                            cen_com = load_communes_centroides(project_root)
                            if not cen_com.empty:
                                insee_col = "code_insee" if "code_insee" in cen_com.columns else ("CODE_INSEE" if "CODE_INSEE" in cen_com.columns else "insee")
                                lat_col = "lat" if "lat" in cen_com.columns else "latitude_centre"
                                lon_col = "lon" if "lon" in cen_com.columns else "longitude_centre"
                                
                                if insee_col and lat_col in cen_com.columns and lon_col in cen_com.columns:
                                    dict_lat = pd.to_numeric(cen_com.set_index(insee_col)[lat_col], errors="coerce").to_dict()
                                    dict_lon = pd.to_numeric(cen_com.set_index(insee_col)[lon_col], errors="coerce").to_dict()
                                    
                                    pve_insee = df_pve.loc[missing_pve_mask, "INF-INSEE"].astype(str).str.extract(r"(\d{1,5})", expand=False).fillna("").str.zfill(5)
                                    mapped_pve_x = pve_insee.map(dict_lon)
                                    mapped_pve_y = pve_insee.map(dict_lat)
                                    found_pve = mapped_pve_x.notna() & mapped_pve_y.notna()
                                    if found_pve.any():
                                        idx_pve = pve_insee[found_pve].index
                                        df_pve.loc[idx_pve, "x"] = mapped_pve_x[found_pve]
                                        df_pve.loc[idx_pve, "y"] = mapped_pve_y[found_pve]
                                        df_pve.loc[idx_pve, "precision_loc"] = "Centroïde communal (Approximatif)"
                        except Exception as e:
                            print(f"Exception fallback communes PVe: {e}")

                    x_col = "x" if "x" in df_pve.columns else None
                    y_col = "y" if "y" in df_pve.columns else None
                    if x_col and y_col:
                        pve_valid = df_pve.dropna(subset=[x_col, y_col]).copy()
                        pve_valid["_code_dept_calc"] = get_dept_series(pve_valid)
                        date_col_pve = "INF-DATE-MIF" if "INF-DATE-MIF" in df_pve.columns else "INF-DATE-INTG"
                        col_ta_pve = "type_action" if "type_action" in df_pve.columns else ("THEME" if "THEME" in df_pve.columns else ("type_actio" if "type_actio" in df_pve.columns else None))
                        col_usager_pve = "type_usager" if "type_usager" in df_pve.columns else ("USAGER" if "USAGER" in df_pve.columns else None)
                        col_dom_pve = "DOMAINE" if "DOMAINE" in pve_valid.columns else ("domaine" if "domaine" in pve_valid.columns else None)
                        col_th_pve = "THEME" if "THEME" in pve_valid.columns else ("theme" if "theme" in pve_valid.columns else None)
                        col_com_pve = "NOM_COM" if "NOM_COM" in pve_valid.columns else ("nom_commun" if "nom_commun" in pve_valid.columns else ("INF-COMMUNE" if "INF-COMMUNE" in pve_valid.columns else None))

                        for r in pve_valid.to_dict("records"):
                            dept_calc = str(r.get("_code_dept_calc", "")).strip()
                            code_dept_pve = "" if dept_calc in ("N/A", "nan", "None") else dept_calc
                            insee_pve = str(r.get("INF-INSEE", r.get("code_insee", r.get("insee_comm", r.get("insee", ""))))).strip()
                            if insee_pve in ("N/A", "nan", "None", "<NA>"):
                                insee_pve = ""
                            try:
                                x_val = float(r[x_col])
                                y_val = float(r[y_col])
                            except (ValueError, TypeError):
                                continue
                            
                            dom_pve = str(r.get(col_dom_pve, "")).strip() if col_dom_pve and pd.notna(r.get(col_dom_pve)) else ""
                            if dom_pve in ("N/A", "nan", "None", "<NA>"): dom_pve = ""
                            th_pve = str(r.get(col_th_pve, "")).strip() if col_th_pve and pd.notna(r.get(col_th_pve)) else ""
                            if th_pve in ("N/A", "nan", "None", "<NA>"): th_pve = ""
                            com_pve = str(r.get(col_com_pve, "")).strip() if col_com_pve and pd.notna(r.get(col_com_pve)) else ""
                            if com_pve in ("N/A", "nan", "None", "<NA>"): com_pve = ""

                            procedures.append({
                                "type": "PVe",
                                "dc_id": str(r.get("DC_ID", "")).strip() if pd.notna(r.get("DC_ID")) else "",
                                "date_ctrl": str(r.get(date_col_pve, ""))[:10] if pd.notna(r.get(date_col_pve)) else "",
                                "resultat": "PVe",
                                "domaine": dom_pve,
                                "theme": th_pve,
                                "type_action": str(r.get(col_ta_pve, "Non renseigné")).strip() if col_ta_pve and pd.notna(r.get(col_ta_pve)) else "Non renseigné",
                                "type_usager": str(r.get(col_usager_pve, "Non renseigné")).strip() if col_usager_pve and pd.notna(r.get(col_usager_pve)) else "Non renseigné",
                                "nom_commun": com_pve,
                                "code_dept": code_dept_pve,
                                "code_insee": insee_pve,
                                "precision_loc": str(r.get("precision_loc", "GPS Fait (Exacte)")),
                                "x": x_val,
                                "y": y_val
                            })
                
                geojson_data = None
                perimeter_geojson_data = None
                gdf_boundary = None
                try:
                    import geopandas as gpd
                    if profile_cfg.get("restrict_geo") == "tub":
                        from core.common.chargeurs_donnees import load_zone_tub_gdf
                        gdf_boundary = load_zone_tub_gdf(Path(project_root))
                        if not gdf_boundary.empty and gdf_boundary.crs is None:
                            gdf_boundary.crs = "EPSG:2154"
                        for col in gdf_boundary.columns:
                            if col != "geometry":
                                gdf_boundary[col] = gdf_boundary[col].astype(str)
                    elif echelle == "pnf":
                        from core.common.chargeurs_donnees import get_pnf_127_communes_aoa_shp_path, get_pnf_aoa_shp_path
                        # Entités du territoire PNF (127 communes) pour la discrétisation du choroplèthe
                        shp_127 = get_pnf_127_communes_aoa_shp_path(Path(project_root))
                        if shp_127.exists():
                            gdf_boundary = gpd.read_file(shp_127)
                            if gdf_boundary.crs is None:
                                gdf_boundary.set_crs(epsg=2154, inplace=True)
                        else:
                            from core.cartographie.pochoir_helper import load_department_gdf
                            target_dep = (code and str(code).strip()) or "21, 52"
                            gdf_boundary = load_department_gdf(target_dep, project_root=project_root, dissolve=False)

                        # Périmètre officiel de l'AOA du Parc (contour bleu boundaryLayer unique, sans bordures internes)
                        shp_aoa = get_pnf_aoa_shp_path(Path(project_root))
                        if shp_aoa and shp_aoa.exists():
                            try:
                                gdf_aoa = gpd.read_file(shp_aoa)
                                if gdf_aoa.crs is None:
                                    gdf_aoa.set_crs(epsg=2154, inplace=True)
                                union_geom = gdf_aoa.geometry.unary_union
                                gdf_aoa_dissolved = gpd.GeoDataFrame(geometry=[union_geom], crs=gdf_aoa.crs)
                                gdf_aoa_wgs84 = gdf_aoa_dissolved.to_crs("EPSG:4326")
                                perimeter_geojson_data = json.loads(gdf_aoa_wgs84.to_json())
                            except Exception as e_aoa:
                                log_server(f"[EXPLORER_GEOJSON] AOA PNF non chargé : {e_aoa}", level="WARN")

                        for col in gdf_boundary.columns:
                            if col != "geometry":
                                gdf_boundary[col] = gdf_boundary[col].astype(str)
                    elif (echelle in ("national", "france") or str(code).upper() in ("FR", "FRANCE", "NATIONAL")) and profile_cfg.get("restrict_geo") != "tub":
                        from core.cartographie.pochoir_helper import (
                            get_national_departments_wgs84_geojson_cached,
                            get_national_regions_perim_gdf_cached
                        )
                        geojson_data = get_national_departments_wgs84_geojson_cached(str(project_root))
                        nb_features = len(geojson_data.get("features", [])) if isinstance(geojson_data, dict) else 0
                        log_server(f"[EXPLORER_GEOJSON] GeoJSON national réutilisé du cache : {nb_features} entité(s)", level="INFO")

                        perimeter_geojson_data = None
                        try:
                            gdf_perim = get_national_regions_perim_gdf_cached(str(project_root))
                            if gdf_perim is not None and not gdf_perim.empty:
                                if gdf_perim.crs is None:
                                    gdf_perim.set_crs(epsg=2154, inplace=True)
                                gdf_perim_wgs84 = gdf_perim.to_crs("EPSG:4326")
                                perimeter_geojson_data = json.loads(gdf_perim_wgs84.to_json())
                        except Exception as e_perim:
                            print(f"Error loading perimeter geojson: {e_perim}")
                    else:
                        from core.cartographie.pochoir_helper import load_department_gdf, load_communes_gdf
                        os.environ["BILANS_CARTO_ECHELLE"] = echelle
                        if echelle == "departement":
                            gdf_com = load_communes_gdf(code, project_root=project_root)
                            if gdf_com is not None and not gdf_com.empty:
                                gdf_boundary = gdf_com
                            else:
                                gdf_boundary = load_department_gdf(code, project_root=project_root, dissolve=False)
                        else:
                            is_multi_unit = (echelle in ("region", "bmi", "national", "france") or str(code).upper() in ("FR", "FRANCE", "NATIONAL"))
                            gdf_boundary = load_department_gdf(code, project_root=project_root, dissolve=not is_multi_unit)

                    if gdf_boundary is not None and not gdf_boundary.empty:
                        if gdf_boundary.crs is None:
                            gdf_boundary.set_crs(epsg=2154, inplace=True)
                        gdf_boundary_wgs84 = gdf_boundary.to_crs("EPSG:4326")
                        
                        # Normalisation des propriétés identifiantes pour le choroplèthe front-end (insensible à la casse)
                        col_map = {c.lower(): c for c in gdf_boundary_wgs84.columns}
                        
                        for dep_alias in ["code_dept", "insee_dep", "code_dep", "dep"]:
                            if dep_alias in col_map:
                                gdf_boundary_wgs84["code_dept"] = gdf_boundary_wgs84[col_map[dep_alias]]
                                gdf_boundary_wgs84["insee_dep"] = gdf_boundary_wgs84[col_map[dep_alias]]
                                break

                        for nom_alias in ["nom", "nom_dept", "nom_dep", "nom_com", "nom_comm", "nom_commune", "libelle"]:
                            if nom_alias in col_map:
                                gdf_boundary_wgs84["nom_dept"] = gdf_boundary_wgs84[col_map[nom_alias]]
                                gdf_boundary_wgs84["nom"] = gdf_boundary_wgs84[col_map[nom_alias]]
                                break

                        for insee_alias in ["code_insee", "insee_comm", "insee_com", "insee", "insee_com_m", "com"]:
                            if insee_alias in col_map:
                                gdf_boundary_wgs84["code_insee"] = gdf_boundary_wgs84[col_map[insee_alias]]
                                gdf_boundary_wgs84["insee_comm"] = gdf_boundary_wgs84[col_map[insee_alias]]
                                break

                        def _fix_str_encoding(val):
                            if isinstance(val, str) and ("Ã" in val or "Â" in val):
                                try:
                                    return val.encode("iso-8859-1").decode("utf-8")
                                except Exception:
                                    return val
                            return str(val) if val is not None else ""

                        for col in gdf_boundary_wgs84.columns:
                            if col != "geometry":
                                gdf_boundary_wgs84[col] = gdf_boundary_wgs84[col].apply(_fix_str_encoding)
                        geojson_data = json.loads(gdf_boundary_wgs84.to_json())
                        nb_features = len(geojson_data.get("features", [])) if isinstance(geojson_data, dict) else 0
                        log_server(f"[EXPLORER_GEOJSON] GeoJSON généré avec succès : {nb_features} entité(s) (Échelle: {echelle}, Code: {code})", level="INFO")

                        # Construction du périmètre administratif officiel (perimeter_geojson)
                        try:
                            gdf_perim = None
                            if echelle == "pnf":
                                if perimeter_geojson_data is None:
                                    target_dep = (code and str(code).strip()) or "21, 52"
                                    gdf_perim = load_department_gdf(target_dep, project_root=project_root, dissolve=False)
                                else:
                                    gdf_perim = None
                            elif profile_cfg.get("restrict_geo") == "tub":
                                gdf_perim = load_department_gdf("FR", project_root=project_root, dissolve=False)
                            elif echelle == "departement":
                                gdf_perim = load_department_gdf(code, project_root=project_root, dissolve=False)
                            else:
                                is_multi_unit = (echelle in ("region", "bmi", "national", "france") or str(code).upper() in ("FR", "FRANCE", "NATIONAL"))
                                gdf_perim = load_department_gdf(code, project_root=project_root, dissolve=not is_multi_unit)

                            if gdf_perim is not None and not gdf_perim.empty:
                                if gdf_perim.crs is None:
                                    gdf_perim.set_crs(epsg=2154, inplace=True)
                                gdf_perim_wgs84 = gdf_perim.to_crs("EPSG:4326")
                                for col in gdf_perim_wgs84.columns:
                                    if col != "geometry":
                                        gdf_perim_wgs84[col] = gdf_perim_wgs84[col].astype(str)
                                perimeter_geojson_data = json.loads(gdf_perim_wgs84.to_json())
                        except Exception as e_perim:
                            print(f"Error loading perimeter geojson: {e_perim}")

                except Exception as e:
                    import traceback
                    log_server(f"[EXPLORER_GEOJSON] Erreur génération contours GeoJSON (Échelle: {echelle}, Code: {code}) : {e}\n{traceback.format_exc()}", level="ERROR")
                    from core.chemins_projet import get_app_data_dir
                    err_file = get_app_data_dir() / "logs" / "geojson_error.log"
                    err_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(err_file, "w", encoding="utf-8") as f_err:
                        f_err.write(f"Error loading boundary geojson: {e}\n")
                        traceback.print_exc(file=f_err)
                    print(f"Error loading boundary geojson: {e}")

                total_usagers_controles = sum(usagers_counts.values()) if usagers_counts else 0

                pej_mapped_count = len([p for p in procedures if str(p.get("type", "")).upper() == "PEJ" and p.get("x") is not None and p.get("y") is not None])
                unmapped_pej = max(0, int(total_pej) - pej_mapped_count)

                response_data = {
                    "stats": {
                        "total_controles": int(total_controles),
                        "total_usagers_controles": int(total_usagers_controles),
                        "total_pej": int(total_pej),
                        "mapped_pej": int(pej_mapped_count),
                        "unmapped_pej": int(unmapped_pej),
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
                    "geojson": geojson_data,
                    "perimeter_geojson": perimeter_geojson_data if perimeter_geojson_data is not None else (None if echelle in ("pnf", "departement") else geojson_data)
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
                    from core.common.chargeurs_donnees import _SESSION_CACHE
                    if '_original_cache_active' in locals():
                        _SESSION_CACHE["active"] = _original_cache_active
                except Exception:
                    pass
                import traceback
                from core.chemins_projet import get_app_data_dir
                err_log_dir = get_app_data_dir() / "logs"
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
        elif parsed_path in ("/api/open-pdf", "/api/open-folder"):
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
                from core.engine.execution_lots_profils import resolve_profile_output_dir
                out_dir = resolve_profile_output_dir(profil, code)
                
                if parsed_path == "/api/open-folder":
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
        elif parsed_path in ("/api/gabarits/save", "/api/gabarit/save"):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                params = json.loads(post_data.decode('utf-8'))
                g_data = params.get("gabarit") or params
                file_stem = params.get("file_stem")
                from core.common.chargeur_gabarits import save_user_gabarit
                ok, clean_id, errors = save_user_gabarit(g_data, file_stem=file_stem)
                resp = {"success": ok, "gabarit_id": clean_id, "errors": errors}
                self.send_response(200 if ok else 400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        elif parsed_path in ("/api/gabarits/delete", "/api/gabarit/delete"):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                params = json.loads(post_data.decode('utf-8'))
                gid = params.get("gabarit_id") or params.get("id")
                from core.common.chargeur_gabarits import delete_user_gabarit
                ok, msg = delete_user_gabarit(gid, SRC_DIR)
                resp = {"success": ok, "message": msg}
                self.send_response(200 if ok else 400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        elif parsed_path in ("/api/gabarits/import", "/api/gabarit/import"):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                params = json.loads(post_data.decode('utf-8'))
                yaml_content = params.get("yaml_content", "")
                file_stem = params.get("file_stem")
                from core.common.chargeur_gabarits import import_gabarit_content
                ok, clean_id, errors = import_gabarit_content(yaml_content, file_stem=file_stem)
                resp = {"success": ok, "gabarit_id": clean_id, "errors": errors}
                self.send_response(200 if ok else 400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        else:
            super().do_POST()

def _append_preload_log(msg: str) -> None:
    clean = msg.strip()
    if not clean:
        return
    with _preload_lock:
        _PRELOAD_LOGS.append(clean)
        if len(_PRELOAD_LOGS) > 30:
            _PRELOAD_LOGS.pop(0)


def preload_data_async():
    import threading
    import time

    def target():
        def log_preload(msg, level="INFO"):
            log_server(msg.strip(), level=level)
            _append_preload_log(msg)

        # Laisser le temps au serveur HTTP de traiter la requête de loading.html et d'afficher la fenêtre
        time.sleep(0.4)

        try:
            from reparer_logo import generer_logo_blanc, generer_favicon_ico
            generer_logo_blanc()
            generer_favicon_ico()
        except Exception:
            pass

        t_start = time.perf_counter()
        try:
            project_root = Path(__file__).resolve().parents[2]

            try:
                from core.common.verifier_dependances import verifier_et_installer_accelerateurs
                verifier_et_installer_accelerateurs(log_preload if IS_DEBUG else None)
            except Exception as e:
                log_server(f"Erreur lors de la vérification des accélérateurs : {e}", level="WARNING")

            t0 = time.perf_counter()
            log_preload("[1/2] Vérification des modules et composants système...")
            # Les données d'activité ne sont plus pré-chargées au démarrage nationalement :
            # elles seront chargées à la demande et mises en cache au clic dans l'explorateur.

            t1 = time.perf_counter()
            log_preload("[2/2] Préparation des contours géographiques...")
            try:
                from core.cartographie.pochoir_helper import get_departements_admin_shp, _load_all_departements
                shp = get_departements_admin_shp(project_root)
                _load_all_departements(str(shp.resolve()))
                log_preload(f"Contours géographiques prêts ({time.perf_counter() - t1:.1f}s)")
            except Exception as e:
                log_preload(f"Impossible de pré-charger les contours : {e}", level="WARNING")

            elapsed = time.perf_counter() - t_start
            log_preload(f"Initialisation terminée avec succès (en {elapsed:.1f}s). L'explorateur est prêt !")
            global _PRELOAD_STATUS
            with _preload_lock:
                _PRELOAD_STATUS = "ready"
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            log_preload(f"Échec du pré-chargement : {e}\n{traceback_str if IS_DEBUG else ''}", level="ERROR")
            with _preload_lock:
                _PRELOAD_STATUS = "error"

    threading.Thread(target=target, daemon=True).start()

def run_server():
    # S'assurer que l'on sert depuis le bon dossier
    os.chdir(str(WEB_DIR))

    apply_server_debug_mode()
    _register_server_pid()
    init_server_logger()
    start_watchdog()

    import atexit
    atexit.register(lambda: finalize_server_logger(reason="Terminated"))
    atexit.register(_cleanup_server_pid)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    import random
    max_tries = 30
    active_port = PORT
    httpd = None

    for attempt in range(max_tries):
        try:
            httpd = socketserver.ThreadingTCPServer(("", active_port), Handler)
            break
        except OSError as e:
            if getattr(e, "errno", None) in (10048, 98) or "10048" in str(e) or "Address already in use" in str(e):
                log_server(f"Port {active_port} déjà occupé, recherche d'un port disponible...", level="INFO")
                active_port += 1
                time.sleep(random.uniform(0.05, 0.2))
            else:
                log_server(f"Erreur d'ouverture du port {active_port} : {e}", level="CRITICAL")
                finalize_server_logger(reason=f"Port Error ({e})")
                raise

    if httpd is None:
        log_server(f"Impossible d'allouer un port libre après {max_tries} tentatives.", level="CRITICAL")
        finalize_server_logger(reason="No Port Available")
        return

    # Ouverture immédiate de la fenêtre GUI dédiée avant les messages d'initialisation
    if os.environ.get("OFBILAN_RESTART") != "1":
        try:
            from core.web.lanceur_fenetre import ouvrir_fenetre_app
        except ImportError:
            from lanceur_fenetre import ouvrir_fenetre_app
        ouvrir_fenetre_app(f"http://localhost:{active_port}/loading.html")

    # Diffusion des journaux de démarrage (sur console et dans l'interface de chargement)
    msg_init = f"Initialisation du serveur web OFBilan (Port: {active_port}, PID: {os.getpid()})"
    log_server(msg_init)
    _append_preload_log(msg_init)

    msg_ready = f"Serveur web actif sur http://localhost:{active_port}"
    log_server(msg_ready)
    _append_preload_log(msg_ready)

    log_server("L'explorateur web s'ouvre automatiquement. Appuyez sur Ctrl+C pour arrêter.")

    # Lancement du pré-chargement des données en tâche de fond
    try:
        preload_data_async()
    except Exception as e:
        log_server(f"Impossible d'initialiser le pré-chargement : {e}", level="ERROR")

    try:
        with httpd:
            httpd.serve_forever()
            log_server("Arrêt normal du serveur web.", level="INFO")
            _cleanup_server_pid()
            finalize_server_logger(reason="Stopped")
            os._exit(0)
    except KeyboardInterrupt:
        log_server("Interruption utilisateur (Ctrl+C). Extinction du serveur.", level="INFO")
        finalize_server_logger(reason="Stopped by user (Ctrl+C)")
    except Exception as e:
        log_server(f"Erreur critique serveur : {e}", level="CRITICAL")
        finalize_server_logger(reason=f"Crashed ({e})")
        raise

if __name__ == "__main__":
    run_server()
