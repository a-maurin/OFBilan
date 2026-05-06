"""Configuration centralisée pour les bilans, remplaçant les variables globales mutables."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from bilans.common.utilitaires_metier import get_dept_name
from bilans.chemins_projet import PROJECT_ROOT, get_out_dir


@dataclass
class BilanConfig:
    """Paramètres d'un bilan (période, département, chemins)."""
    date_deb: pd.Timestamp
    date_fin: pd.Timestamp
    dept_code: str
    root: Path = field(default_factory=lambda: PROJECT_ROOT)
    out_dir: Optional[Path] = None

    @property
    def entity_sd(self) -> str:
        return f"SD{self.dept_code}"

    @property
    def dept_name(self) -> str:
        return get_dept_name(self.dept_code)

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
        dept_code: str = "21",
        root: Optional[Path] = None,
        out_dir: Optional[Path] = None,
    ) -> "BilanConfig":
        return cls(
            date_deb=pd.to_datetime(date_deb),
            date_fin=pd.to_datetime(date_fin),
            dept_code=str(dept_code).strip(),
            root=root or PROJECT_ROOT,
            out_dir=out_dir,
        )
