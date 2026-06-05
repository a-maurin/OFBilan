import sys
sys.stdout.reconfigure(encoding="utf-8")

with open("diff_orchestrateur.txt", "r", encoding="utf-16", errors="ignore") as f:
    lines = f.readlines()

print("Total lines in diff:", len(lines))
diff_lines = [
    line.strip() for line in lines
    if (line.startswith("+") or line.startswith("-"))
    and not line.startswith("+++")
    and not line.startswith("---")
]

print("Total modifications:", len(diff_lines))
for idx, line in enumerate(diff_lines):
    print(f"{idx}: {line}")
