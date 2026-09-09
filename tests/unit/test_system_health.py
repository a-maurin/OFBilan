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

from pathlib import Path
from core.common.chargeurs_donnees import get_source_files_metadata

def test_get_source_files_metadata_structure(tmp_path: Path) -> None:
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = sources_dir / "Stats_PVe_OFB_test.csv"
    test_file.write_text("col1;col2\nval1;val2\n", encoding="utf-8")
    
    meta = get_source_files_metadata(tmp_path)
    assert len(meta) == 1
    assert meta[0]["nom"] == "Stats_PVe_OFB_test.csv"
    assert "taille" in meta[0]
    assert "date" in meta[0]
    assert "empreinte" in meta[0]
    assert len(meta[0]["empreinte"]) == 12


def test_get_source_files_metadata_recursive_and_sidecars(tmp_path: Path) -> None:
    sources_dir = tmp_path / "data" / "sources"
    
    # 1. Fichier à la racine
    (sources_dir / "Stats_PVe_test.xlsx").parent.mkdir(parents=True, exist_ok=True)
    (sources_dir / "Stats_PVe_test.xlsx").write_text("dummy", encoding="utf-8")
    
    # 2. Sous-dossier SIG avec GPKG
    sig_dir = sources_dir / "sig" / "point_infraction_PJ"
    sig_dir.mkdir(parents=True, exist_ok=True)
    (sig_dir / "localisation_infrac_FAITS.gpkg").write_text("gpkg_content", encoding="utf-8")
    
    # 3. Layer Shapefile avec sidecars (.shp, .dbf, .prj)
    shp_dir = sources_dir / "sig" / "CARTO"
    shp_dir.mkdir(parents=True, exist_ok=True)
    (shp_dir / "limite_zone.shp").write_text("shp_content", encoding="utf-8")
    (shp_dir / "limite_zone.dbf").write_text("dbf_content", encoding="utf-8")
    (shp_dir / "limite_zone.prj").write_text("prj_content", encoding="utf-8")
    
    # 4. Fichiers non-données (ignorés)
    (sources_dir / ".gitkeep").write_text("", encoding="utf-8")
    (sources_dir / "~$temp.xlsx").write_text("temp", encoding="utf-8")
    (sig_dir / "Thumbs.db").write_text("thumbs", encoding="utf-8")
    (sig_dir / "style.qml").write_text("qml", encoding="utf-8")
    (sig_dir / "notice.docx").write_text("docx", encoding="utf-8")
    (sig_dir / "archive.zip").write_text("zip", encoding="utf-8")
    (sig_dir / "index.qix").write_text("qix", encoding="utf-8")
    (sig_dir / "meta.qmd").write_text("qmd", encoding="utf-8")
    
    meta = get_source_files_metadata(tmp_path)
    
    noms = [m["nom"] for m in meta]
    assert "sig/CARTO/limite_zone.shp" in noms
    assert "sig/CARTO/limite_zone.dbf" not in noms
    assert "sig/CARTO/limite_zone.prj" not in noms
    assert "sig/point_infraction_PJ/localisation_infrac_FAITS.gpkg" in noms
    assert "Stats_PVe_test.xlsx" in noms
    assert ".gitkeep" not in noms
    assert "~$temp.xlsx" not in noms
    assert "sig/point_infraction_PJ/Thumbs.db" not in noms
    assert "sig/point_infraction_PJ/style.qml" not in noms
    assert "sig/point_infraction_PJ/notice.docx" not in noms
    assert "sig/point_infraction_PJ/archive.zip" not in noms
    assert "sig/point_infraction_PJ/index.qix" not in noms
    assert "sig/point_infraction_PJ/meta.qmd" not in noms
    
    # Vérification du tri alphabétique
    assert noms == sorted(noms, key=lambda x: x.lower())


