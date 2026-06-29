import os
from pathlib import Path

def replace_imports():
    root_dir = Path(__file__).resolve().parents[1]
    core_dir = root_dir / "core"
    
    count = 0
    for root, _, files in os.walk(core_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = content.replace("from ofbilan", "from core").replace("import ofbilan", "import core")
                
                if new_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    count += 1
                    print(f"Modifié : {file_path.relative_to(root_dir)}")
                    
    # Modifier également point_entree_cli.py s'il est à la racine ou dans core
    cli_path = core_dir / "point_entree_cli.py"
    if cli_path.exists():
        with open(cli_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = content.replace("from ofbilan", "from core").replace("import ofbilan", "import core")
        if new_content != content:
            with open(cli_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1
            print(f"Modifié : {cli_path.relative_to(root_dir)}")

    # Modifier ofbilan_plugin.py
    plugin_path = root_dir / "ofbilan_plugin.py"
    if plugin_path.exists():
        with open(plugin_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = content.replace("from ofbilan", "from core").replace("import ofbilan", "import core")
        if new_content != content:
            with open(plugin_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1
            print(f"Modifié : {plugin_path.relative_to(root_dir)}")

    print(f"\\nTerminé. {count} fichiers modifiés.")

if __name__ == "__main__":
    replace_imports()
