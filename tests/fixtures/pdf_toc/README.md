# Fixtures tests PDF (TOC / ordre des sections)

Jeux CSV minimaux pour les tests d’intégration dans `tests/unit/test_pdf_toc_*_integration.py`.

- **Séparateur** : point-virgule (`;`), comme `bilans.common.utilitaires_metier._load_csv_opt`.
- **Diffusion** : les tests génèrent en `interne` ; le fichier PDF porte le suffixe `_int`.

| Dossier | Profil / moteur | Fichiers |
|---------|-----------------|----------|
| `pdf_toc_agrainage/` | thématique `agrainage` | `zone_ctrl`, `tab_resultats_controles`, `synthese_zone` |
| `pdf_toc_chasse/` | thématique `chasse` | `tab_resultats_controles` |
| `pdf_toc_global/` | global | `controles_global_par_domaine`, `controles_global_resultats_controles`, résumés PEJ/PA/PVe |

Commandes :

```bash
# Jeux TOC + présentation PDF
python -m pytest tests/unit/test_pdf_toc_agrainage_integration.py tests/unit/test_pdf_toc_global_integration.py tests/unit/test_pdf_presentation_config.py -q

# Suite complète (comme la CI)
python -m pytest -q
# ou : .\scripts\verify.ps1  /  ./scripts/verify.sh
```
