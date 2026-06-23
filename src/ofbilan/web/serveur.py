import http.server
import socketserver
import os
import sys
from pathlib import Path

# Ajouter le dossier actuel au path pour importer reparer_logo
WEB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB_DIR))

try:
    from reparer_logo import generer_logo_blanc
    # Génère automatiquement le logo propre au démarrage
    generer_logo_blanc()
except ImportError:
    pass

PORT = 8000

import json
import subprocess

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
