from pathlib import Path
from typing import Dict

from config_cartes_model import (
    GlobalConfig,
    ProfileConfig,
    LayerSymbologyConfig,
    OutputConfig,
    BasemapConfig,
)


def _layer_repr(lc: LayerSymbologyConfig) -> str:
    parts = [
        f"layer_name={repr(lc.layer_name)}",
        f"legend_label={repr(lc.legend_label)}",
        f"filter_type={repr(getattr(lc, 'filter_type', '') or '')}",
        f"geometry_mode={repr(lc.geometry_mode)}",
        f"renderer_type={repr(lc.renderer_type)}",
        f"field={repr(lc.field)}",
        f"classification_mode={repr(lc.classification_mode)}",
        f"num_classes={lc.num_classes}",
        f"palette={repr(lc.palette)}",
    ]
    if getattr(lc, "color_rgb", None):
        parts.append(f"color_rgb={tuple(lc.color_rgb)}")
    parts.append(f"symbol_size_mm={lc.symbol_size_mm}")
    parts.append(f"symbol_shape={repr(lc.symbol_shape)}")
    return "LayerSymbologyConfig(\n        " + ",\n        ".join(parts) + "\n    )"


def _profile_repr(p: ProfileConfig) -> str:
    layers_repr = "{\n"
    for k, v in p.layers.items():
        layers_repr += f"            {repr(k)}: {_layer_repr(v)},\n"
    layers_repr += "        }"
    return (
        "ProfileConfig(\n"
        f"        id={repr(p.id)},\n"
        f"        title={repr(p.title)},\n"
        f"        layout_name={repr(p.layout_name)},\n"
        f"        output_filename={repr(p.output_filename)},\n"
        f"        date_deb={repr(p.date_deb)},\n"
        f"        date_fin={repr(p.date_fin)},\n"
        f"        layers={layers_repr},\n"
        f"        title_main={repr(getattr(p, 'title_main', '') )},\n"
        f"        subtitle={repr(getattr(p, 'subtitle', '') )},\n"
        f"        layout_title_item_id={repr(getattr(p, 'layout_title_item_id', 'titre_principal'))},\n"
        f"        layout_subtitle_item_id={repr(getattr(p, 'layout_subtitle_item_id', 'sous_titre'))},\n"
        "    )"
    )


def _profiles_dict_repr(profiles: Dict[str, ProfileConfig]) -> str:
    lines = ["{"]
    for key, prof in profiles.items():
        lines.append(f"    {repr(key)}: {_profile_repr(prof)},")
    lines.append("}")
    return "\n".join(lines)


def serialize_config(cfg: GlobalConfig) -> str:
    """Sérialise un GlobalConfig vers le contenu Python de config_cartes.py."""
    profiles_repr = _profiles_dict_repr(cfg.profiles)

    header = '''"""
Configuration des cartes pour les bilans agrainage / chasse-agrainage.
Généré par les outils de configuration (GUI ou mode interactif).

Les dates de période doivent correspondre à celles des scripts d'analyse :
- agrainage : analyse_agrainage.py (DATE_DEB, DATE_FIN)
- chasse : analyse_chasse_agrainage.py (ou analyse_chasse.py) — thématique chasse uniquement
"""

from typing import Dict

from config_cartes_model import (
    GeometryMode,
    FilterType,
    RendererType,
    ClassificationMode,
    OutputFormat,
    LayerSymbologyConfig,
    ProfileConfig,
    OutputConfig,
    BasemapConfig,
    GlobalConfig,
)


'''

    profiles_block = f"DEFAULT_PROFILES: Dict[str, ProfileConfig] = {profiles_repr}\n\n\n"

    config_block = (
        "# Configuration globale par défaut\n"
        "CONFIG = GlobalConfig(\n"
        f"    project_qgis_path={repr(cfg.project_qgis_path)},\n"
        f"    kit_ofb_path={repr(cfg.kit_ofb_path)},\n"
        f"    output_dir={repr(cfg.output_dir)},\n"
        f"    basemap=BasemapConfig(enabled={cfg.basemap.enabled}),\n"
        f"    output=OutputConfig(format={repr(cfg.output.format)}, dpi={cfg.output.dpi}, "
        f"page_size={repr(cfg.output.page_size)}, orientation={repr(cfg.output.orientation)}),\n"
        "    profiles=DEFAULT_PROFILES.copy(),\n"
        ")\n"
    )

    return header + profiles_block + config_block


def write_config_file(cfg: GlobalConfig, path: Path) -> None:
    """Écrit un GlobalConfig complet dans le fichier config_cartes.py."""
    content = serialize_config(cfg)
    path.write_text(content, encoding="utf-8")

