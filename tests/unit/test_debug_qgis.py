import subprocess
import os
import pytest
from pathlib import Path

@pytest.mark.skip(reason="Debug helper only")
def test_debug_bat_file():
    print("Testing BAT file directly")
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    bat = PROJECT_ROOT / "src" / "ofbilan" / "cartographie" / "lancer_production_cartographique.bat"
    print(f"Bat exists: {bat.exists()}")
    
    cmd = [
        "cmd.exe",
        "/c",
        str(bat),
        "global",
        "--date-deb", "2025-01-01",
        "--date-fin", "2025-12-31",
        "--dept-code", "27",
        "--diffusion", "interne"
    ]
    env = os.environ.copy()
    env["BILANS_CARTO_HEADLESS"] = "1"
    
    res = subprocess.run(cmd, env=env, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    print("STDOUT:")
    print(res.stdout)
    print("STDERR:")
    print(res.stderr)
    print(f"RETURNCODE: {res.returncode}")
    from ofbilan.chemins_projet import PROJECT_ROOT
    rel = PROJECT_ROOT / "src" / "ofbilan" / "cartographie" / "qgis_python_path.txt"
    print(f"File exists: {rel.exists()}")
    if rel.exists():
        raw_bytes = rel.read_bytes()
        print("Raw bytes:", raw_bytes)
        content_utf8 = rel.read_text(encoding="utf-8")
        print("UTF-8 decoded repr:", repr(content_utf8))
        
    from ofbilan.cartographie.qgis_runtime import find_qgis_python_executable
    exe = find_qgis_python_executable()
    print(f"QGIS Executable: {exe}")
    
    if exe:
        # Check if we can run it
        cmd = [
            str(exe),
            "-c",
            "import sys; print('Python executable:', sys.executable); import qgis.core; print('QGIS version:', qgis.core.Qgis.QGIS_VERSION)"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print("OSGeo4W python run stdout:", res.stdout)
        print("OSGeo4W python run stderr:", res.stderr)
        print("OSGeo4W python run returncode:", res.returncode)

    o4w_env = Path(r"C:\Program Files\QGIS 3.44.8\bin\o4w_env.bat")
    print(f"o4w_env.bat exists: {o4w_env.exists()}")
    if o4w_env.exists():
        content = o4w_env.read_text(encoding="cp1252", errors="replace")
        print("o4w_env.bat content:")
        print(content)

    # Let's run the batch script cartography launcher to see why it fails
    bat = PROJECT_ROOT / "src" / "ofbilan" / "cartographie" / "lancer_production_cartographique.bat"
    cmd = [
        "cmd.exe",
        "/c",
        str(bat),
        "global_domaines",
        "--date-deb", "2025-01-01",
        "--date-fin", "2025-12-31",
        "--dept-code", "27",
        "--diffusion", "interne"
    ]
    env = os.environ.copy()
    env["BILANS_CARTO_HEADLESS"] = "1"
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    print("Batch run stdout repr:", repr(res.stdout))
    print("Batch run stderr repr:", repr(res.stderr))
    print("Batch run returncode:", res.returncode)
    
    assert False, "Show output"
