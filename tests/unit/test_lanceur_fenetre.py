"""Tests unitaires pour le lanceur de fenêtre applicative dédiée."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

from core.web.lanceur_fenetre import ouvrir_fenetre_app, trouver_navigateur_app


def test_trouver_navigateur_app_existant():
    """Vérifie la détection d'un exécutable valide."""
    with patch("core.web.lanceur_fenetre.shutil.which", return_value=r"C:\fake\msedge.exe"), \
         patch("pathlib.Path.is_file", return_value=True):
        navigateur = trouver_navigateur_app()
        assert navigateur is not None
        assert "msedge.exe" in navigateur


def test_trouver_navigateur_app_aucun():
    """Vérifie que None est retourné si aucun navigateur Chromium n'est présent."""
    with patch("core.web.lanceur_fenetre.shutil.which", return_value=None), \
         patch("pathlib.Path.is_file", return_value=False):
        navigateur = trouver_navigateur_app()
        assert navigateur is None


def test_ouvrir_fenetre_app_chromium_maximise():
    """Vérifie le lancement Chromium avec les arguments --app et --start-maximized."""
    with patch("core.web.lanceur_fenetre.trouver_navigateur_app", return_value=r"C:\fake\msedge.exe"), \
         patch("core.web.lanceur_fenetre.subprocess.Popen") as mock_popen, \
         patch("core.web.lanceur_fenetre.webbrowser.open") as mock_webbrowser:
        
        url = "http://localhost:8000/loading.html"
        resultat = ouvrir_fenetre_app(url, maximiser=True)

        assert resultat is True
        mock_popen.assert_called_once()
        args_appeles = mock_popen.call_args[0][0]
        assert args_appeles[0] == r"C:\fake\msedge.exe"
        assert f"--app={url}" in args_appeles
        assert "--start-maximized" in args_appeles
        mock_webbrowser.assert_not_called()


def test_ouvrir_fenetre_app_chromium_non_maximise():
    """Vérifie le lancement Chromium avec --app sans --start-maximized."""
    with patch("core.web.lanceur_fenetre.trouver_navigateur_app", return_value=r"C:\fake\msedge.exe"), \
         patch("core.web.lanceur_fenetre.subprocess.Popen") as mock_popen, \
         patch("core.web.lanceur_fenetre.webbrowser.open") as mock_webbrowser:
        
        url = "http://localhost:8000/loading.html"
        resultat = ouvrir_fenetre_app(url, maximiser=False)

        assert resultat is True
        mock_popen.assert_called_once()
        args_appeles = mock_popen.call_args[0][0]
        assert f"--app={url}" in args_appeles
        assert "--start-maximized" not in args_appeles
        mock_webbrowser.assert_not_called()


def test_ouvrir_fenetre_app_repli_webbrowser():
    """Vérifie le repli transparent sur webbrowser.open si aucun navigateur Chromium."""
    with patch("core.web.lanceur_fenetre.trouver_navigateur_app", return_value=None), \
         patch("core.web.lanceur_fenetre.subprocess.Popen") as mock_popen, \
         patch("core.web.lanceur_fenetre.webbrowser.open", return_value=True) as mock_webbrowser:
        
        url = "http://localhost:8000/loading.html"
        resultat = ouvrir_fenetre_app(url)

        assert resultat is True
        mock_popen.assert_not_called()
        mock_webbrowser.assert_called_once_with(url)


def test_ouvrir_fenetre_app_repli_en_cas_erreur_subprocess():
    """Vérifie le repli sur webbrowser.open si Popen déclenche une exception."""
    with patch("core.web.lanceur_fenetre.trouver_navigateur_app", return_value=r"C:\fake\msedge.exe"), \
         patch("core.web.lanceur_fenetre.subprocess.Popen", side_effect=OSError("Access denied")), \
         patch("core.web.lanceur_fenetre.webbrowser.open", return_value=True) as mock_webbrowser:
        
        url = "http://localhost:8000/loading.html"
        resultat = ouvrir_fenetre_app(url)

        assert resultat is True
        mock_webbrowser.assert_called_once_with(url)
