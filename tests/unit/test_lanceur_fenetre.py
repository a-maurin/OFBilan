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

"""Tests unitaires pour le lanceur de fenêtre applicative dédiée."""

from __future__ import annotations

from pathlib import Path
import threading
from unittest.mock import MagicMock, patch

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


def test_ouvrir_fenetre_app_declenche_maximisation_windows():
    """Vérifie que la routine de maximisation est déclenchée sous Windows lorsque maximiser=True."""
    with patch("core.web.lanceur_fenetre.trouver_navigateur_app", return_value=r"C:\fake\msedge.exe"), \
         patch("core.web.lanceur_fenetre.subprocess.Popen"), \
         patch("core.web.lanceur_fenetre.os.name", "nt"), \
         patch("core.web.lanceur_fenetre._maximiser_fenetre_windows") as mock_max:
        
        ouvrir_fenetre_app("http://localhost:8000/loading.html", maximiser=True)
        mock_max.assert_called_once()


def test_ouvrir_fenetre_app_ne_declenche_pas_maximisation_si_faux():
    """Vérifie que la routine de maximisation n'est pas appelée si maximiser=False."""
    with patch("core.web.lanceur_fenetre.trouver_navigateur_app", return_value=r"C:\fake\msedge.exe"), \
         patch("core.web.lanceur_fenetre.subprocess.Popen"), \
         patch("core.web.lanceur_fenetre.os.name", "nt"), \
         patch("core.web.lanceur_fenetre._maximiser_fenetre_windows") as mock_max:
        
        ouvrir_fenetre_app("http://localhost:8000/loading.html", maximiser=False)
        mock_max.assert_not_called()


def test_maximiser_fenetre_windows_non_nt():
    """Vérifie que _maximiser_fenetre_windows ne fait rien si l'OS n'est pas Windows (nt)."""
    from core.web.lanceur_fenetre import _maximiser_fenetre_windows
    with patch("core.web.lanceur_fenetre.os.name", "posix"), \
         patch("threading.Thread") as mock_thread:
        _maximiser_fenetre_windows()
        mock_thread.assert_not_called()


def test_maximiser_fenetre_windows_worker_trouve_et_maximise():
    """Vérifie le traitement de maximisation et de focus par l'API Win32."""
    from core.web.lanceur_fenetre import _maximiser_fenetre_windows
    import ctypes

    mock_user32 = MagicMock()
    mock_kernel32 = MagicMock()

    mock_user32.IsWindowVisible.return_value = 1
    mock_user32.GetWindowTextLengthW.return_value = 7
    
    def fake_get_text(hwnd, buf, max_len):
        buf.value = "OFBilan"
        return 7
    mock_user32.GetWindowTextW.side_effect = fake_get_text

    def fake_get_pid(hwnd, pid_ref):
        pid_ref._obj.value = 1234
        return 1
    mock_user32.GetWindowThreadProcessId.side_effect = fake_get_pid

    mock_kernel32.OpenProcess.return_value = 100
    def fake_query_img(hproc, flags, buf, size_ref):
        buf.value = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        return 1
    mock_kernel32.QueryFullProcessImageNameW.side_effect = fake_query_img

    def fake_enum_windows(cb, lparam):
        cb(1001, lparam)
        return 1
    mock_user32.EnumWindows.side_effect = fake_enum_windows

    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    mock_windll.kernel32 = mock_kernel32

    # Exécution synchrone du worker en interceptant Thread.start
    mock_thread_inst = MagicMock()
    with patch("core.web.lanceur_fenetre.os.name", "nt"), \
         patch.object(ctypes, "windll", mock_windll, create=True), \
         patch.object(ctypes, "WINFUNCTYPE", lambda *args: (lambda f: f), create=True), \
         patch("threading.Thread", return_value=mock_thread_inst):
        _maximiser_fenetre_windows(titre_partiel="OFBilan", delai_max_sec=1.0)
        # Appel direct du worker transmis au thread
        worker_func = threading.Thread.call_args[1]["target"]
        worker_func()

    mock_user32.ShowWindowAsync.assert_called_once_with(1001, 3)
    mock_user32.PostMessageW.assert_called_once_with(1001, 0x0112, 0xF030, 0)
    mock_user32.SetForegroundWindow.assert_called_once_with(1001)
    mock_kernel32.CloseHandle.assert_called_once_with(100)


def test_maximiser_fenetre_windows_ignore_onglets_parasites():
    """Vérifie que les fenêtres de navigateur tierces (ex. onglet GitHub du projet) sont ignorées."""
    from core.web.lanceur_fenetre import _maximiser_fenetre_windows
    import ctypes

    mock_user32 = MagicMock()
    mock_kernel32 = MagicMock()

    mock_user32.IsWindowVisible.return_value = 1
    mock_user32.GetWindowTextLengthW.return_value = 45

    def fake_get_text(hwnd, buf, max_len):
        buf.value = "chore: commit · a-maurin/OFBilan · GitHub"
        return len(buf.value)
    mock_user32.GetWindowTextW.side_effect = fake_get_text

    def fake_enum_windows(cb, lparam):
        cb(2001, lparam)
        return 1
    mock_user32.EnumWindows.side_effect = fake_enum_windows

    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    mock_windll.kernel32 = mock_kernel32

    mock_thread_inst = MagicMock()
    with patch("core.web.lanceur_fenetre.os.name", "nt"), \
         patch.object(ctypes, "windll", mock_windll, create=True), \
         patch.object(ctypes, "WINFUNCTYPE", lambda *args: (lambda f: f), create=True), \
         patch("threading.Thread", return_value=mock_thread_inst):
        _maximiser_fenetre_windows(titre_partiel="OFBilan", delai_max_sec=0.2)
        worker_func = threading.Thread.call_args[1]["target"]
        worker_func()

    mock_user32.ShowWindowAsync.assert_not_called()


def test_maximiser_fenetre_windows_trouve_loading_html():
    """Vérifie la détection et maximisation d'une fenêtre de chargement."""
    from core.web.lanceur_fenetre import _maximiser_fenetre_windows
    import ctypes

    mock_user32 = MagicMock()
    mock_kernel32 = MagicMock()

    mock_user32.IsWindowVisible.return_value = 1
    mock_user32.GetWindowTextLengthW.return_value = 23

    def fake_get_text(hwnd, buf, max_len):
        buf.value = "OFBilan - Chargement..."
        return len(buf.value)
    mock_user32.GetWindowTextW.side_effect = fake_get_text

    def fake_get_pid(hwnd, pid_ref):
        pid_ref._obj.value = 5678
        return 1
    mock_user32.GetWindowThreadProcessId.side_effect = fake_get_pid

    mock_kernel32.OpenProcess.return_value = 200
    def fake_query_img(hproc, flags, buf, size_ref):
        buf.value = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        return 1
    mock_kernel32.QueryFullProcessImageNameW.side_effect = fake_query_img

    def fake_enum_windows(cb, lparam):
        cb(3001, lparam)
        return 1
    mock_user32.EnumWindows.side_effect = fake_enum_windows

    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    mock_windll.kernel32 = mock_kernel32

    mock_thread_inst = MagicMock()
    with patch("core.web.lanceur_fenetre.os.name", "nt"), \
         patch.object(ctypes, "windll", mock_windll, create=True), \
         patch.object(ctypes, "WINFUNCTYPE", lambda *args: (lambda f: f), create=True), \
         patch("threading.Thread", return_value=mock_thread_inst):
        _maximiser_fenetre_windows(titre_partiel="OFBilan", delai_max_sec=1.0)
        worker_func = threading.Thread.call_args[1]["target"]
        worker_func()

    mock_user32.ShowWindowAsync.assert_called_once_with(3001, 3)
    mock_user32.PostMessageW.assert_called_once_with(3001, 0x0112, 0xF030, 0)



