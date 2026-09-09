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
import pandas as pd
import pytest

from core.common.chargeurs_donnees import (
    _compute_files_signature,
    _load_disk_cache,
    _save_disk_cache,
)


def test_disk_cache_roundtrip(tmp_path: Path):
    df_test = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    fake_file = tmp_path / "test_file.txt"
    fake_file.write_text("hello", encoding="utf-8")
    
    sig = _compute_files_signature([fake_file])
    assert sig is not None and len(sig) > 0
    
    # Doit retourner None si pas encore en cache
    assert _load_disk_cache(tmp_path, "test_key", sig) is None
    
    # Sauvegarder dans le cache
    _save_disk_cache(tmp_path, "test_key", sig, df_test)
    
    # Relire depuis le cache
    df_cached = _load_disk_cache(tmp_path, "test_key", sig)
    assert df_cached is not None
    assert len(df_cached) == 3
    assert list(df_cached.columns) == ["col1", "col2"]
    
    # Test d'invalidation (signature différente)
    assert _load_disk_cache(tmp_path, "test_key", "invalid_sig") is None


def test_disk_cache_corrupted(tmp_path: Path):
    fake_file = tmp_path / "test_file.txt"
    fake_file.write_text("hello", encoding="utf-8")
    sig = _compute_files_signature([fake_file])
    
    cache_dir = tmp_path / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    meta_file = cache_dir / "corrupt_key.meta.json"
    data_file = cache_dir / "corrupt_key.pkl.gz"
    
    meta_file.write_text(f'{{"files_sig": "{sig}"}}', encoding="utf-8")
    data_file.write_text("invalid_gzip_content", encoding="utf-8")
    
    # Doit retourner None et nettoyer le cache corrompu
    assert _load_disk_cache(tmp_path, "corrupt_key", sig) is None
    assert not data_file.exists()
