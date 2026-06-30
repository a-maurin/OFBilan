import zipfile
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
zip_path = root / "pack_configuration_referentiels.zip"

if zip_path.exists():
    with zipfile.ZipFile(zip_path, 'r') as z:
        files = z.namelist()
        ppp = [f for f in files if "natinf_ppp" in f]
        print(f"Trouvé dans le zip : {ppp}")
else:
    print("Zip introuvable")
