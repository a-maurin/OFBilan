"""Configuration centralisée pour les bilans, remplaçant les variables globales mutables."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from core.common.utilitaires_metier import get_perimetre_name
from core.chemins_projet import PROJECT_ROOT, get_out_dir


def resolve_perimetre_kwargs(
    *,
    echelle: str | None = None,
    code: str | None = None,
    dept_code: str | None = None,
) -> tuple[str, str]:
    """Résout échelle/code à partir des kwargs CLI ou PDF (rétro-compat dept_code)."""
    if echelle is not None and code is not None:
        return str(echelle).strip(), str(code).strip()
    if dept_code is not None:
        return "departement", str(dept_code).strip()
    return "departement", "21"


@dataclass
class BilanConfig:
    """Paramètres d'un bilan (période, département, chemins)."""
    date_deb: pd.Timestamp
    date_fin: pd.Timestamp
    echelle: str
    code: str
    root: Path = field(default_factory=lambda: PROJECT_ROOT)
    out_dir: Optional[Path] = None

    @property
    def entity_sds(self) -> list[str]:
        from core.common.utilitaires_metier import get_departements_pour_perimetre
        codes = get_departements_pour_perimetre(self.echelle, self.code)
        if codes and "FR" not in codes:
            return [f"SD{c}" for c in codes]
        return []

    @property
    def dept_code(self) -> str:
        """Alias rétro-compat : code du périmètre (ex. département 21)."""
        return self.code

    @property
    def perimetre_name(self) -> str:
        return get_perimetre_name(self.echelle, self.code)

    def get_out(self, programme: str) -> Path:
        """Return the output directory; use override if set, else default."""
        if self.out_dir is not None:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            return self.out_dir
        return get_out_dir(programme)

    @classmethod
    def from_strings(
        cls,
        date_deb: str,
        date_fin: str,
        echelle: str = "departement",
        code: str = "21",
        root: Optional[Path] = None,
        out_dir: Optional[Path] = None,
    ) -> "BilanConfig":
        return cls(
            date_deb=pd.to_datetime(date_deb),
            date_fin=pd.to_datetime(date_fin),
            echelle=str(echelle).strip(),
            code=str(code).strip(),
            root=root or PROJECT_ROOT,
            out_dir=out_dir,
        )
