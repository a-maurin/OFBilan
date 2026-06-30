import pathlib
import re

count = 0
for f in (pathlib.Path(__file__).parent.parent / 'tests').rglob('*.py'):
    text = f.read_text(encoding='utf-8')
    new_text = re.sub(r'\bofbilan\.', 'core.', text)
    if text != new_text:
        f.write_text(new_text, encoding='utf-8')
        count += 1

print(f"Modifié {count} fichiers dans tests/")
