# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

import pytest
import pandas as pd
from pathlib import Path
from core.engine.orchestrateur_profils import filter_by_agent_service, load_profile_config

def test_filter_by_agent_service_basic():
    df = pd.DataFrame({
        "entite_ctrl": ["SD21", "PNF - Agents", "SD52", None, "PARC NATIONAL"],
        "nb": [10, 20, 30, 40, 50]
    })
    
    cfg = {
        "agent_rules": {
            "pnf_keywords": ["PNF", "PARC"],
            "ofb_keywords": ["OFB", "SD"]
        }
    }
    
    # Mode "tous"
    df_tous = filter_by_agent_service(df, ["entite_ctrl"], "tous", cfg)
    assert len(df_tous) == 5
    
    # Mode "pnf" -> seules les entités PNF/PARC
    df_pnf = filter_by_agent_service(df, ["entite_ctrl"], "pnf", cfg)
    assert len(df_pnf) == 2
    assert set(df_pnf["nb"]) == {20, 50}
    
    # Mode "ofb" -> SD21, SD52 et NULL (fallback OFB)
    df_ofb = filter_by_agent_service(df, ["entite_ctrl"], "ofb", cfg)
    assert len(df_ofb) == 3
    assert set(df_ofb["nb"]) == {10, 30, 40}


def test_filter_by_agent_service_pve_column():
    df = pd.DataFrame({
        "UNITE_libelle": ["Brigade SD21", "Unité PNF Forets", "Agent SD52"],
        "val": [1, 2, 3]
    })
    cfg = {"agent_rules": {"pnf_keywords": ["PNF"]}}
    
    df_pnf = filter_by_agent_service(df, ["UNITE_libelle", "unite_libelle"], "pnf", cfg)
    assert len(df_pnf) == 1
    assert df_pnf.iloc[0]["val"] == 2

    df_ofb = filter_by_agent_service(df, ["UNITE_libelle", "unite_libelle"], "ofb", cfg)
    assert len(df_ofb) == 2
    assert set(df_ofb["val"]) == {1, 3}


def test_explorer_html_has_pnf_agent_select():
    html_path = Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.html"
    content = html_path.read_text(encoding="utf-8")
    assert "pnf-agent-select" in content
    assert "Tous les agents" in content
    assert "OFB uniquement" in content
    assert "PNF uniquement" in content


def test_explorer_js_has_agent_service_params():
    js_path = Path(__file__).resolve().parents[2] / "core" / "web" / "explorer.js"
    content = js_path.read_text(encoding="utf-8")
    assert "pnf-agent-select" in content
    assert "agent_service" in content


def test_filter_by_agent_service_accents_and_multicol():
    df = pd.DataFrame({
        "entite": ["SD21", "Parc National de Forêts", "SD52"],
        "UNITE_libelle": ["SD21", "P.N.F - Agents", "Brigade"],
        "val": [100, 200, 300]
    })
    cfg = {"agent_rules": {"pnf_keywords": ["PNF", "P.N.F", "PARC", "FORETS", "FORET", "FORÊTS", "FORÊT"]}}

    df_pnf = filter_by_agent_service(df, ["entite_ctrl"], "pnf", cfg)
    assert len(df_pnf) == 1
    assert df_pnf.iloc[0]["val"] == 200

    df_ofb = filter_by_agent_service(df, ["entite_ctrl"], "ofb", cfg)
    assert len(df_ofb) == 2
    assert set(df_ofb["val"]) == {100, 300}

