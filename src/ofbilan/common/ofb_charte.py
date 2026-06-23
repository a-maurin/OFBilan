"""Charte graphique OFB : couleurs, polices, styles PDF, Spinner."""
import os
import sys
import threading
import time
from pathlib import Path

# Activation des séquences ANSI (VT100) sur Windows pour le spinner multi-lignes
if sys.platform == "win32":
    import ctypes
    _STD_OUTPUT_HANDLE = -11
    _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    def _enable_windows_vt100() -> bool:
        """Active le mode VT100 sur la console Windows. Retourne True si réussi."""
        try:
            os.system("")  # Workaround connu pour activer ANSI sur Windows
            handle = ctypes.windll.kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
            if handle is None or handle == -1:
                return False
            # Essayer d'abord de préserver le mode existant
            mode = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                mode.value |= _ENABLE_VIRTUAL_TERMINAL_PROCESSING
                return ctypes.windll.kernel32.SetConsoleMode(handle, mode) != 0
            # Fallback : forcer le mode 7 (VT100 + processed output)
            return ctypes.windll.kernel32.SetConsoleMode(handle, 7) != 0
        except Exception:
            return False
else:

    def _enable_windows_vt100() -> bool:
        return True  # Non-Windows : ANSI déjà supporté

from reportlab.lib import colors as rl_colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Charte graphique OFB
# ---------------------------------------------------------------------------
COLOR_PRIMARY = "#003A76"
COLOR_SECONDARY = "#1E4E85"
COLOR_GREY = "#333333"
# Barres empilées horizontales : série « En attente » (aligné sur le gris foncé charte).
COLOR_CHART_AUTRE_RESULTAT = COLOR_GREY
COLOR_TABLE_HEADER_BG = rl_colors.HexColor("#003A76")
COLOR_TABLE_HEADER_FG = rl_colors.white
COLOR_TABLE_ALT_ROW = rl_colors.HexColor("#F0F4F8")
COLOR_TABLE_BORDER = rl_colors.HexColor("#CCCCCC")
# Couleurs d'appoint utilisées par les encarts PDF.
COLOR_NOTICE_BG = "#E8EEF4"
COLOR_CALLOUT_BG = "#EAF2F8"

# Couleurs pour les graphiques (camemberts, barres groupées) — aucune couleur en dur dans les scripts de bilan
COLOR_CHART_1 = COLOR_PRIMARY  # bleu OFB
COLOR_CHART_2 = "#53AB60"   # vert
COLOR_CHART_3 = "#F4A261"   # orangé
# Rouge pour les valeurs non conformes / infractions : rouge un peu adouci pour
# rester lisible sans être agressif.
COLOR_CHART_4 = "#D95C4A"   # rouge doux (moins vif que #E76F51)
COLOR_CHART_5 = "#90BF83"   # vert clair
COLOR_CHART_6 = "#4296CE"   # bleu clair
CHART_PIE_COLORS = [COLOR_CHART_1, COLOR_CHART_2, COLOR_CHART_3, COLOR_CHART_4, COLOR_CHART_5, COLOR_CHART_6]
CHART_BAR_GROUPED_COLORS = [COLOR_CHART_1, COLOR_CHART_2, COLOR_CHART_3, COLOR_CHART_4]

PAGE_W, PAGE_H = A4
# Marges latérales (moitié de l’ancien 17 mm) : zone utile du PDF plus large.
MARGIN_LEFT = 7.0 * mm
MARGIN_RIGHT = 7.0 * mm
MARGIN_BOTTOM = 22 * mm
# Marge supérieure pour pages intérieures
MARGIN_TOP = 14 * mm
SPACING_XXS = 0.5 * mm
SPACING_XS = 1.0 * mm
SPACING_S = 1.5 * mm
SPACING_M = 2.0 * mm
SPACING_L = 4.0 * mm

_HEADER_LINE_STEP = 3.2 * mm
_HEADER_GAP_RULE = 2.5 * mm
_HEADER_GAP_CONTENT = 4.5 * mm


def header_layout_metrics(n_header_lines: int) -> tuple[float, float]:
    """
    Retourne (rule_y_from_top, margin_top) en points ReportLab.

    Le trait d'en-tête est placé sous le bloc de texte ; le contenu commence
    juste en dessous du trait (marge haute minimale).
    """
    n = max(1, min(int(n_header_lines), 3))
    text_block_h = n * _HEADER_LINE_STEP
    rule_from_top = text_block_h + _HEADER_GAP_RULE
    margin_top = rule_from_top + _HEADER_GAP_CONTENT
    return rule_from_top, margin_top


ASCII_LOGO_OFB = r"""
  OOOOOOO   FFFFFFF   BBBBBBB 
  OOOOOOO   FFFFFFF   BBBBBBB 
  OO   OO   FF        BB   BB
  OO   OO   FFFFFF    BBBBBBB
  OO   OO   FFFFFF    BBBBBBB
  OO   OO   FF        BB   BB
  OOOOOOO   FF        BBBBBBB
  OOOOOOO   FF        BBBBBBB

   OFFICE FRANÇAIS
 DE LA BIODIVERSITÉ
"""


def print_ascii_logo_ofb() -> None:
    """Affiche le logo OFB en ASCII dans la console."""
    print(ASCII_LOGO_OFB)


def _ref_img(name: str) -> Path:
    """Chemin vers une image dans ref/programme/modele_ofb/word/media/."""
    ref_dir = Path(__file__).resolve().parents[3] / "ref" / "programme"
    return ref_dir / "modele_ofb" / "word" / "media" / name


# Médias charte OFB (ref/programme/modele_ofb/word/media/) — clés alignées sur defaults.charte.assets (YAML).
IMG_BANNER = _ref_img("image5.jpg")
IMG_TITLE_DECO = _ref_img("image6.jpeg")
IMG_FILIGRANE = _ref_img("image3.jpeg")
IMG_FILIGRANE_ALT = _ref_img("image4.png")

# Alias historiques (rétro-compatibilité).
IMG_LOGO_BANNER = IMG_BANNER
IMG_TITLE_PAGE_DECO = IMG_TITLE_DECO
IMG_FOOTER_DECO = IMG_FILIGRANE
IMG_BACKGROUND = IMG_FILIGRANE_ALT

CHARTE_ASSET_DEFAULT_FILES: dict[str, str] = {
    "banner": "image5.jpg",
    "title_page_deco": "image6.jpeg",
    "watermark": "image3.jpeg",
    "footer_deco": "image4.jpeg",
}


def charte_asset_path(
    assets_cfg: dict | None,
    key: str,
    default_filename: str,
    *,
    fallback: Path | None = None,
) -> Path:
    """Résout un fichier média charte depuis la config YAML (nom relatif à word/media/)."""
    name = default_filename
    if isinstance(assets_cfg, dict):
        raw = assets_cfg.get(key)
        if raw is not None and str(raw).strip():
            name = str(raw).strip()
    path = _ref_img(name)
    if path.exists():
        return path
    if fallback is not None and fallback.exists():
        return fallback
    return path


# ---------------------------------------------------------------------------
# Enregistrement polices
# ---------------------------------------------------------------------------
def _register_fonts() -> str:
    """Enregistre les polices dans reportlab. Retourne le nom de famille."""
    # Essayer d'abord la police Marianne (si disponible)
    marianne_dirs = [
        Path("/usr/share/fonts/truetype/marianne"),
        Path("/usr/share/fonts/opentype/marianne"),
        Path("/usr/local/share/fonts/marianne"),
        Path("~/.local/share/fonts/marianne").expanduser(),
    ]
    
    for marianne_dir in marianne_dirs:
        if marianne_dir.exists():
            # Look for the required font files
            regular_fonts = list(marianne_dir.glob("*Regular*"))
            bold_fonts = list(marianne_dir.glob("*Bold*"))
            italic_fonts = list(marianne_dir.glob("*Italic*"))
            bolditalic_fonts = list(marianne_dir.glob("*Bold*Italic*"))
            
            # Find the best matches
            regular = None
            bold = None
            italic = None
            bolditalic = None
            
            # Look for Regular font
            for font in regular_fonts:
                if "Regular" in font.name and not "Italic" in font.name:
                    regular = font
                    break
            
            # Look for Bold font (not italic)
            for font in bold_fonts:
                if "Bold" in font.name and "Italic" not in font.name and "ExtraBold" not in font.name and "Medium" not in font.name:
                    bold = font
                    break
            
            # Look for Italic font (not bold)
            for font in italic_fonts:
                if "Italic" in font.name and "Bold" not in font.name and "Regular" in font.name:
                    italic = font
                    break
            
            # Look for BoldItalic font
            for font in bolditalic_fonts:
                if "Bold" in font.name and "Italic" in font.name and "ExtraBold" not in font.name:
                    bolditalic = font
                    break
            
            # If we found all required fonts, register them
            if regular and bold and italic and bolditalic:
                try:
                    pdfmetrics.registerFont(TTFont("Marianne", str(regular)))
                    pdfmetrics.registerFont(TTFont("Marianne-Bold", str(bold)))
                    pdfmetrics.registerFont(TTFont("Marianne-Italic", str(italic)))
                    pdfmetrics.registerFont(TTFont("Marianne-BoldItalic", str(bolditalic)))
                    pdfmetrics.registerFontFamily(
                        "Marianne",
                        normal="Marianne",
                        bold="Marianne-Bold",
                        italic="Marianne-Italic",
                        boldItalic="Marianne-BoldItalic",
                    )
                    return "Marianne"
                except Exception as e:
                    print(f"Erreur lors de l'enregistrement de la police Marianne: {e}")
                    # Continue to fallback fonts
    
    # Essayer Arial sur Windows
    if sys.platform == "win32":
        fonts_dir = Path(r"C:\Windows\Fonts")
        arial = fonts_dir / "arial.ttf"
        arial_bd = fonts_dir / "arialbd.ttf"
        arial_it = fonts_dir / "ariali.ttf"
        arial_bi = fonts_dir / "arialbi.ttf"
        if arial.exists():
            pdfmetrics.registerFont(TTFont("Arial", str(arial)))
            pdfmetrics.registerFont(TTFont("Arial-Bold", str(arial_bd)))
            pdfmetrics.registerFont(TTFont("Arial-Italic", str(arial_it)))
            pdfmetrics.registerFont(TTFont("Arial-BoldItalic", str(arial_bi)))
            pdfmetrics.registerFontFamily(
                "Arial",
                normal="Arial",
                bold="Arial-Bold",
                italic="Arial-Italic",
                boldItalic="Arial-BoldItalic",
            )
            return "Arial"
    
    # Utiliser Liberation Sans comme alternative (disponible sur la plupart des systèmes Linux)
    try:
        liberation_regular = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
        liberation_bold = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
        liberation_italic = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf")
        liberation_bolditalic = Path("/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf")
        
        if liberation_regular.exists() and liberation_bold.exists() and liberation_italic.exists() and liberation_bolditalic.exists():
            pdfmetrics.registerFont(TTFont("LiberationSans", str(liberation_regular)))
            pdfmetrics.registerFont(TTFont("LiberationSans-Bold", str(liberation_bold)))
            pdfmetrics.registerFont(TTFont("LiberationSans-Italic", str(liberation_italic)))
            pdfmetrics.registerFont(TTFont("LiberationSans-BoldItalic", str(liberation_bolditalic)))
            pdfmetrics.registerFontFamily(
                "LiberationSans",
                normal="LiberationSans",
                bold="LiberationSans-Bold",
                italic="LiberationSans-Italic",
                boldItalic="LiberationSans-BoldItalic",
            )
            return "LiberationSans"
    except Exception:
        pass
    
    # Fallback final : Helvetica (police par défaut de ReportLab)
    return "Helvetica"


FONT_FAMILY = _register_fonts()

_CELL_NORMAL = ParagraphStyle(
    "CellNormal",
    fontName=FONT_FAMILY,
    fontSize=9,
    leading=12,
    textColor=rl_colors.black,
    alignment=TA_LEFT,
)
_CELL_RIGHT = ParagraphStyle(
    "CellRight",
    fontName=FONT_FAMILY,
    fontSize=9,
    leading=12,
    textColor=rl_colors.black,
    alignment=TA_RIGHT,
)
_CELL_HEADER = ParagraphStyle(
    "CellHeader",
    fontName=f"{FONT_FAMILY}-Bold",
    fontSize=10,
    leading=13,
    textColor=rl_colors.white,
    alignment=TA_LEFT,
)
_CELL_HEADER_RIGHT = ParagraphStyle(
    "CellHeaderRight",
    fontName=f"{FONT_FAMILY}-Bold",
    fontSize=10,
    leading=13,
    textColor=rl_colors.white,
    alignment=TA_RIGHT,
)


def _get_styles(typography_config: dict | None = None):
    """Construit les ParagraphStyles conformes à la charte OFB."""
    ss = getSampleStyleSheet()
    
    sub_italic = True
    if typography_config is not None:
        sub_italic = bool(typography_config.get("subsections_italic", True))
    
    h_font = f"{FONT_FAMILY}-BoldItalic" if sub_italic else f"{FONT_FAMILY}-Bold"

    styles = {
        "Title": ParagraphStyle(
            "OFBTitle",
            parent=ss["Title"],
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=26,
            leading=36,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_CENTER,
            spaceAfter=3 * mm,
        ),
        "Heading1": ParagraphStyle(
            "OFBH1",
            parent=ss["Heading1"],
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=18,
            leading=24,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_LEFT,
            spaceBefore=1 * mm,
            spaceAfter=1 * mm,
            keepWithNext=1,
        ),
        "Heading2": ParagraphStyle(
            "OFBH2",
            parent=ss["Heading2"],
            fontName=h_font,
            fontSize=14,
            leading=18,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_LEFT,
            spaceBefore=1 * mm,
            spaceAfter=1 * mm,
            keepWithNext=1,
        ),
        "Heading3": ParagraphStyle(
            "OFBH3",
            parent=ss["Heading3"],
            fontName=h_font,
            fontSize=12,
            leading=15,
            textColor=rl_colors.HexColor(COLOR_GREY),
            alignment=TA_LEFT,
            spaceBefore=0.5 * mm,
            spaceAfter=0.5 * mm,
            keepWithNext=1,
        ),
        "BodyText": ParagraphStyle(
            "OFBBody",
            parent=ss["BodyText"],
            fontName=FONT_FAMILY,
            fontSize=10,
            leading=14,
            textColor=rl_colors.black,
            alignment=TA_JUSTIFY,
            spaceBefore=0.5 * mm,
            spaceAfter=1 * mm,
        ),
        "BodySmall": ParagraphStyle(
            "OFBBodySmall",
            parent=ss["BodyText"],
            fontName=FONT_FAMILY,
            fontSize=8,
            leading=11,
            textColor=rl_colors.HexColor("#666666"),
            alignment=TA_LEFT,
            spaceBefore=0.5 * mm,
            spaceAfter=0.5 * mm,
        ),
        "TableCaption": ParagraphStyle(
            "OFBTableCaption",
            parent=ss["BodyText"],
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=10,
            leading=13,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_LEFT,
            spaceBefore=2 * mm,
            spaceAfter=1 * mm,
            keepWithNext=0,
        ),
        "FigureCaption": ParagraphStyle(
            "OFBFigureCaption",
            parent=ss["BodyText"],
            fontName=f"{FONT_FAMILY}-Italic",
            fontSize=9,
            leading=13,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=2 * mm,
        ),
        "KeyFigure": ParagraphStyle(
            "OFBKeyFigure",
            parent=ss["BodyText"],
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=22,
            leading=28,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_CENTER,
        ),
        "KeyFigureLabel": ParagraphStyle(
            "OFBKeyFigureLabel",
            parent=ss["BodyText"],
            fontName=FONT_FAMILY,
            fontSize=9,
            leading=12,
            textColor=rl_colors.HexColor(COLOR_GREY),
            alignment=TA_CENTER,
        ),
        "TOCEntry": ParagraphStyle(
            "OFBTOCEntry",
            parent=ss["BodyText"],
            fontName=FONT_FAMILY,
            fontSize=12,
            leading=20,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_LEFT,
            leftIndent=5 * mm,
        ),
    }
    return styles


class Spinner:
    """Spinner texte pour indiquer qu'un traitement est en cours.

    Animation type « machine à écrire » :
    - apparition caractère par caractère de
      « Traitement des données en cours. Patience... » (ou message personnalisé)
    - courte pause avec le message complet
    - effacement caractère par caractère
    - boucle tant que le contexte est actif.
    """

    def __init__(self, message: str = "Traitement des données en cours. Patience...") -> None:
        self.message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        message = self.message
        appear_delay = 0.06
        disappear_delay = 0.03
        pause_full = 1.5
        pause_empty = 0.3
        msg_len = len(message)

        while not self._stop_event.is_set():
            # Apparition caractère par caractère
            for i in range(1, msg_len + 1):
                if self._stop_event.is_set():
                    break
                sys.stdout.write("\r" + message[:i])
                sys.stdout.flush()
                time.sleep(appear_delay)

            if self._stop_event.is_set():
                break

            # Pause avec message complet
            elapsed = 0.0
            while elapsed < pause_full and not self._stop_event.is_set():
                time.sleep(0.1)
                elapsed += 0.1

            if self._stop_event.is_set():
                break

            # Effacement caractère par caractère
            for i in range(msg_len, -1, -1):
                if self._stop_event.is_set():
                    break
                # Ajouter des espaces pour effacer complètement la ligne
                sys.stdout.write("\r" + message[:i] + " " * (msg_len - i))
                sys.stdout.flush()
                time.sleep(disappear_delay)

            if self._stop_event.is_set():
                break

            # Pause sur ligne vide
            elapsed = 0.0
            while elapsed < pause_empty and not self._stop_event.is_set():
                time.sleep(0.1)
                elapsed += 0.1

    def __enter__(self) -> "Spinner":
        if not sys.stdout.isatty():
            return self
            
        import logging
        is_debug = False
        logger = logging.getLogger("ofbilan")
        for h in logger.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                if h.level <= logging.DEBUG:
                    is_debug = True
                    break
        if is_debug:
            return self
            
        _enable_windows_vt100()
        sys.stdout.write("\n")
        sys.stdout.flush()
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        if not sys.stdout.isatty():
            return
            
        import logging
        is_debug = False
        logger = logging.getLogger("ofbilan")
        for h in logger.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                if h.level <= logging.DEBUG:
                    is_debug = True
                    break
        if is_debug:
            return
            
        self._stop_event.set()
        self._thread.join()
        # Nettoyage de la ligne
        sys.stdout.write("\r" + " " * len(self.message) + "\r")
        sys.stdout.flush()
