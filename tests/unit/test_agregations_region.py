import pandas as pd
from pathlib import Path
from bilans.engine.agregations_region import analyse_region_par_departement

def test_analyse_region_par_departement(tmp_path, monkeypatch):
    import bilans.engine.agregations_region as mod
    
    # Mock config to test with Region BFC (27)
    monkeypatch.setattr(mod, "get_departements_pour_perimetre", lambda e, c: ["21", "25"] if e == "region" and c == "27" else [])
    
    point = pd.DataFrame([
        {"num_depart": "21", "domaine": "Eau", "theme": "Peche", "fc_id": "A"},
        {"num_depart": "21", "domaine": "Eau", "theme": "Peche", "fc_id": "A"},
        {"num_depart": "25", "domaine": "Nature", "theme": "Foret", "fc_id": "B"}
    ])
    
    pej = pd.DataFrame([
        {"ENTITE_ORIGINE_PROCEDURE": "SD21", "DOMAINE": "Eau", "THEME": "Peche"}
    ])
    
    pa = pd.DataFrame()
    pve = pd.DataFrame([
        {"INF-INSEE": "21000", "DOMAINE": "Nature", "THEME": "Chasse"}
    ])
    
    out_dir = tmp_path
    
    analyse_region_par_departement(point, pa, pej, pve, "region", "27", out_dir)
    
    out_file = out_dir / "region_detail_par_dept.csv"
    assert out_file.exists()
    
    df = pd.read_csv(out_file, sep=";", encoding="utf-8")
    df["departement"] = df["departement"].astype(str)
    
    assert "departement" in df.columns
    assert "nb_localisations" in df.columns
    
    # 21 Eau Peche has 2 localisations, 1 operation, 1 pej, 0 pve
    row21 = df[(df["departement"] == "21") & (df["domaine"] == "Eau") & (df["theme"] == "Peche")]
    assert not row21.empty
    assert row21["nb_localisations"].iloc[0] == 2
    assert row21["nb_operations"].iloc[0] == 1
    assert row21["nb_pej"].iloc[0] == 1
    
    # 21 Nature Chasse has 1 pve
    row21pv = df[(df["departement"] == "21") & (df["domaine"] == "Nature")]
    assert not row21pv.empty
    assert row21pv["nb_pve"].iloc[0] == 1
