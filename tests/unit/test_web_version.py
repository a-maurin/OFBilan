import sys
from pathlib import Path

# Add src/ to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ofbilan.web.serveur import get_latest_version

def test_get_latest_version():
    version = get_latest_version()
    # It should return a string starting with 'v' and containing version numbers
    assert isinstance(version, str)
    assert version.startswith("v")
    # Clean check that it has digits and dots
    parts = version[1:].split(".")
    assert len(parts) >= 2
    for p in parts:
        assert p.isdigit()
