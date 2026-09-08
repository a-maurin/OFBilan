import importlib.util

libs = [
    "pyogrio",
    "calamine",
    "pyarrow",
    "fiona",
    "openpyxl",
    "odf",
    "geopandas",
    "pandas"
]

print("\n=== DIAGNOSTIC DES BIBLIOTHÈQUES INTÉGRÉES ===")
for lib in libs:
    spec = importlib.util.find_spec(lib)
    status = "OK" if spec is not None else "MANQUANT"
    print(f"  [{status}] {lib}")
print("===============================================\n")
