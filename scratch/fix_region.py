import re
from pathlib import Path

path = Path(r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\src\bilans\engine\agregations_region.py")
content = path.read_text(encoding="utf-8")

content = content.replace(
    'pt["domaine"] = pt.get("domaine", "Hors domaine").fillna("Hors domaine").astype(str)',
    'pt["domaine"] = pt["domaine"].fillna("Hors domaine").astype(str) if "domaine" in pt.columns else "Hors domaine"'
)

content = content.replace(
    'pt["theme"] = pt.get("theme", pt.get("thematique", "Hors thème")).fillna("Hors thème").astype(str)',
    'pt["theme"] = pt["theme"].fillna("Hors thème").astype(str) if "theme" in pt.columns else (pt["thematique"].fillna("Hors thème").astype(str) if "thematique" in pt.columns else "Hors thème")'
)

content = content.replace(
    'pj["domaine"] = pj.get("DOMAINE", "Hors domaine").fillna("Hors domaine").astype(str)',
    'pj["domaine"] = pj["DOMAINE"].fillna("Hors domaine").astype(str) if "DOMAINE" in pj.columns else "Hors domaine"'
)

content = content.replace(
    'pj["theme"] = pj.get("THEME", "Hors thème").fillna("Hors thème").astype(str)',
    'pj["theme"] = pj["THEME"].fillna("Hors thème").astype(str) if "THEME" in pj.columns else "Hors thème"'
)

content = content.replace(
    'pt_pa["domaine"] = pt_pa.get("domaine", "Hors domaine").fillna("Hors domaine").astype(str)',
    'pt_pa["domaine"] = pt_pa["domaine"].fillna("Hors domaine").astype(str) if "domaine" in pt_pa.columns else "Hors domaine"'
)

content = content.replace(
    'pt_pa["theme"] = pt_pa.get("theme", pt_pa.get("thematique", "Hors thème")).fillna("Hors thème").astype(str)',
    'pt_pa["theme"] = pt_pa["theme"].fillna("Hors thème").astype(str) if "theme" in pt_pa.columns else (pt_pa["thematique"].fillna("Hors thème").astype(str) if "thematique" in pt_pa.columns else "Hors thème")'
)

content = content.replace(
    'pv["domaine"] = pv.get("DOMAINE", "Hors domaine").fillna("Hors domaine").astype(str)',
    'pv["domaine"] = pv["DOMAINE"].fillna("Hors domaine").astype(str) if "DOMAINE" in pv.columns else "Hors domaine"'
)

path.write_text(content, encoding="utf-8")
print("agregations_region.py fixed")
