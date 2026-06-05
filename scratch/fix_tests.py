import os
import glob
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix DummyBilanConfig in tests/smoke/test_bilan_thematique_engine_smoke.py and test_bilan_global_smoke.py
    if "class DummyBilanConfig" in content:
        content = re.sub(
            r'def __init__\(self, root: Path\) -> None:\n(.*?)(?=\s*@classmethod)',
            r'def __init__(self, root: Path) -> None:\n\1        self.perimetre_name = "Côte-d\'Or"\n',
            content,
            flags=re.DOTALL
        )

    # Some tests may still have dept_code or dept_name
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root_dir, dirs, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root_dir, file))
