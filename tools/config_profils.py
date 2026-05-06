from pathlib import Path
from typing import Any, Dict, List, Tuple
import sys

import tkinter as tk
from tkinter import ttk, messagebox

import yaml


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

PROFILS_DIR = ROOT_DIR / "config" / "profils_bilan"
DEFAULTS_PATH = PROFILS_DIR / "_defaults.yaml"


def _charger_yaml_brut(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Le fichier {path} ne contient pas un document YAML de type mapping.")
    return data


def lister_profils(directory: Path) -> List[Tuple[str, Path]]:
    """Retourne une liste (label_affiche, chemin_fichier) alignée avec le moteur."""
    profils: List[Tuple[str, Path]] = []
    if not directory.exists():
        return profils

    try:
        from bilans.engine.catalogue_profils import list_profiles

        profile_ids = list_profiles()
    except Exception:
        # Fallback : liste brute si l'import moteur échoue.
        profile_ids = sorted(
            p.stem for p in directory.glob("*.yaml") if p.is_file() and p.stem != "_defaults"
        )

    for pid in profile_ids:
        path = directory / f"{pid}.yaml"
        if not path.exists():
            continue
        label = pid
        try:
            data = _charger_yaml_brut(path)
            label_yaml = data.get("label")
            if isinstance(label_yaml, str) and label_yaml.strip():
                label = label_yaml.strip()
        except Exception:
            pass
        profils.append((f"{label} ({pid})", path))

    # Le socle _defaults n'est pas un profil exécutable mais reste éditable.
    if DEFAULTS_PATH.exists():
        profils.append(("Socle commun (_defaults)", DEFAULTS_PATH))

    return profils


def charger_profil(path: Path) -> Dict[str, Any]:
    return _charger_yaml_brut(path)


def sauvegarder_profil(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


class BoolField:
    def __init__(self, group: str, path: str, label: str, value: bool) -> None:
        self.group = group
        self.path = path
        self.label = label
        self.value = value


def _label_from_key(key: str) -> str:
    # Transforme un nom_de_cle en libellé lisible.
    return key.replace("_", " ").replace("-", " ").strip().capitalize()


def extraire_bools_profil(data: Dict[str, Any]) -> List[BoolField]:
    """Extrait les champs booléens d'un profil sous forme de BoolField."""
    fields: List[BoolField] = []

    # 1. Booléens au premier niveau
    for key, value in data.items():
        if isinstance(value, bool):
            label = _label_from_key(key)
            fields.append(BoolField(group="Généraux", path=key, label=label, value=value))

    # 2. Section 'sources'
    sources = data.get("sources")
    if isinstance(sources, dict):
        for key, value in sources.items():
            if isinstance(value, bool):
                label = _label_from_key(key)
                path = f"sources.{key}"
                fields.append(BoolField(group="Sources", path=path, label=label, value=value))

    # 3. Section 'options'
    options = data.get("options")
    if isinstance(options, dict):
        for opt_key, opt_data in options.items():
            if not isinstance(opt_data, dict):
                continue
            opt_label = opt_data.get("label") or _label_from_key(opt_key)

            # Champ 'default'
            default_val = opt_data.get("default")
            if isinstance(default_val, bool):
                path = f"options.{opt_key}.default"
                fields.append(
                    BoolField(
                        group="Options",
                        path=path,
                        label=opt_label,
                        value=default_val,
                    )
                )

            # Champ 'ask'
            ask_val = opt_data.get("ask")
            if isinstance(ask_val, bool):
                path = f"options.{opt_key}.ask"
                ask_label = f"Demander : {opt_label}"
                fields.append(
                    BoolField(
                        group="Options",
                        path=path,
                        label=ask_label,
                        value=ask_val,
                    )
                )

    # 4. Section 'analyses'
    analyses = data.get("analyses")
    if isinstance(analyses, dict):
        for key, value in analyses.items():
            if isinstance(value, bool):
                label = _label_from_key(key)
                path = f"analyses.{key}"
                fields.append(
                    BoolField(
                        group="Analyses",
                        path=path,
                        label=label,
                        value=value,
                    )
                )

    return fields


def appliquer_bools_profil(data: Dict[str, Any], mapping_valeurs: Dict[str, bool]) -> None:
    """Applique les valeurs booléennes (mapping chemin->valeur) dans la structure Python."""
    for full_path, new_val in mapping_valeurs.items():
        parts = full_path.split(".")
        node: Any = data
        try:
            for i, part in enumerate(parts):
                is_last = i == len(parts) - 1
                if is_last:
                    if isinstance(node, dict):
                        # On ne force que les clés existantes ou les nouveaux booléens.
                        node[part] = bool(new_val)
                else:
                    if not isinstance(node, dict):
                        node = None
                        break
                    if part not in node or not isinstance(node[part], dict):
                        # Si le chemin n'existe pas, on ne crée pas de structure complexe.
                        node = None
                        break
                    node = node[part]
        except Exception:
            # On ignore les chemins problématiques sans interrompre le reste.
            continue


class ConfigProfilsApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Configuration des profils YAML")

        # Données
        self.profils: List[Tuple[str, Path]] = lister_profils(PROFILS_DIR)
        self.current_profile_path: Path | None = None
        self.current_profile_data: Dict[str, Any] | None = None
        self.bool_fields: List[BoolField] = []
        self.bool_vars: Dict[str, tk.BooleanVar] = {}
        self.initial_mapping: Dict[str, bool] = {}
        self._dirty = False

        # Widgets principaux
        self._build_widgets()

        if not self.profils:
            messagebox.showwarning(
                "Aucun profil",
                f"Aucun fichier YAML trouvé dans :\n{PROFILS_DIR}",
            )
        else:
            # Sélectionner automatiquement le premier profil
            self.profil_combobox.current(0)
            self.on_select_profil()

    def _build_widgets(self) -> None:
        # Cadre de sélection du profil
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(top_frame, text="Profil :").pack(side=tk.LEFT)

        profil_names = [label for label, _ in self.profils]
        self.profil_var = tk.StringVar()
        self.profil_combobox = ttk.Combobox(
            top_frame,
            textvariable=self.profil_var,
            values=profil_names,
            state="readonly",
            width=50,
        )
        self.profil_combobox.pack(side=tk.LEFT, padx=5)
        self.profil_combobox.bind("<<ComboboxSelected>>", lambda event: self.on_select_profil())

        self.profile_info_var = tk.StringVar(value="")
        ttk.Label(top_frame, textvariable=self.profile_info_var).pack(side=tk.LEFT, padx=10)

        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Label(search_frame, text="Recherche :").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self._rebuild_checkboxes())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Cadre principal pour les cases à cocher
        self.checkboxes_container = ttk.Frame(self)
        self.checkboxes_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Boutons de bas de fenêtre
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.btn_enregistrer = ttk.Button(bottom_frame, text="Enregistrer", command=self.on_enregistrer)
        self.btn_enregistrer.pack(side=tk.RIGHT, padx=5)
        self.btn_enregistrer.state(["disabled"])

        btn_apercu = ttk.Button(bottom_frame, text="Aperçu changements", command=self.on_apercu_changements)
        btn_apercu.pack(side=tk.RIGHT, padx=5)

        btn_recharger = ttk.Button(bottom_frame, text="Recharger", command=self.on_recharger)
        btn_recharger.pack(side=tk.RIGHT, padx=5)

        btn_quitter = ttk.Button(bottom_frame, text="Quitter", command=self.destroy)
        btn_quitter.pack(side=tk.RIGHT)

    def on_select_profil(self) -> None:
        if self._dirty and not self._confirm_abandon_changes():
            return

        index = self.profil_combobox.current()
        if index < 0 or index >= len(self.profils):
            return

        label, path = self.profils[index]
        try:
            data = charger_profil(path)
        except Exception as exc:
            messagebox.showerror(
                "Erreur",
                f"Impossible de charger le profil '{label}' ({path}):\n{exc}",
            )
            return

        self.current_profile_path = path
        self.current_profile_data = data
        self.profile_info_var.set(str(path.relative_to(ROOT_DIR)))
        self._dirty = False
        self.btn_enregistrer.state(["disabled"])
        self.search_var.set("")

        self.bool_fields = extraire_bools_profil(data)
        self.initial_mapping = {field.path: bool(field.value) for field in self.bool_fields}
        self._rebuild_checkboxes()

    def _clear_checkboxes(self) -> None:
        for child in self.checkboxes_container.winfo_children():
            child.destroy()
        self.bool_vars.clear()

    def _rebuild_checkboxes(self) -> None:
        self._clear_checkboxes()

        if not self.bool_fields:
            ttk.Label(self.checkboxes_container, text="Aucun paramètre booléen détecté pour ce profil.").pack(
                anchor=tk.W
            )
            return

        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        filtered_fields: List[BoolField] = []
        for field in self.bool_fields:
            haystack = f"{field.group} {field.label} {field.path}".lower()
            if not query or query in haystack:
                filtered_fields.append(field)
        if not filtered_fields:
            ttk.Label(self.checkboxes_container, text="Aucun résultat pour cette recherche.").pack(anchor=tk.W)
            return

        # Grouper les champs par groupe
        groups: Dict[str, List[BoolField]] = {}
        for field in filtered_fields:
            groups.setdefault(field.group, []).append(field)

        for group_name, fields in groups.items():
            lf = ttk.LabelFrame(self.checkboxes_container, text=group_name)
            lf.pack(fill=tk.X, padx=5, pady=5)

            for field in fields:
                var = tk.BooleanVar(value=field.value)
                var.trace_add("write", lambda *_args: self._mark_dirty())
                self.bool_vars[field.path] = var
                cb = ttk.Checkbutton(lf, text=field.label, variable=var)
                cb.pack(anchor=tk.W, padx=10, pady=2)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.btn_enregistrer.state(["!disabled"])

    def _confirm_abandon_changes(self) -> bool:
        return messagebox.askyesno(
            "Modifications non enregistrées",
            "Des modifications ne sont pas enregistrées.\nVoulez-vous les abandonner ?",
        )

    def on_recharger(self) -> None:
        if self.current_profile_path is None:
            return
        if self._dirty and not self._confirm_abandon_changes():
            return
        self._dirty = False
        self.on_select_profil()

    def _current_mapping(self) -> Dict[str, bool]:
        return {path: var.get() for path, var in self.bool_vars.items()}

    def _compute_changes(self) -> List[tuple[str, bool, bool]]:
        current = self._current_mapping()
        all_paths = sorted(set(self.initial_mapping.keys()) | set(current.keys()))
        changes: List[tuple[str, bool, bool]] = []
        for path in all_paths:
            old_val = bool(self.initial_mapping.get(path, False))
            new_val = bool(current.get(path, old_val))
            if old_val != new_val:
                changes.append((path, old_val, new_val))
        return changes

    def on_apercu_changements(self) -> None:
        changes = self._compute_changes()
        if not changes:
            messagebox.showinfo("Aperçu", "Aucune modification en attente.")
            return

        win = tk.Toplevel(self)
        win.title("Aperçu des changements")
        win.geometry("760x420")

        txt = tk.Text(win, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert(tk.END, "Chemin YAML | Avant -> Après\n")
        txt.insert(tk.END, "-" * 72 + "\n")
        for path, old_val, new_val in changes:
            txt.insert(tk.END, f"{path} | {old_val} -> {new_val}\n")
        txt.configure(state=tk.DISABLED)

    def on_enregistrer(self) -> None:
        if self.current_profile_path is None or self.current_profile_data is None:
            messagebox.showwarning("Aucun profil", "Aucun profil n'est chargé.")
            return

        # Construire le mapping chemin -> valeur
        mapping: Dict[str, bool] = self._current_mapping()

        try:
            appliquer_bools_profil(self.current_profile_data, mapping)
            sauvegarder_profil(self.current_profile_path, self.current_profile_data)
        except Exception as exc:
            messagebox.showerror(
                "Erreur lors de l'enregistrement",
                f"Impossible d'enregistrer les modifications :\n{exc}",
            )
            return

        messagebox.showinfo(
            "Enregistré",
            f"Les modifications ont été enregistrées dans :\n{self.current_profile_path}",
        )
        self.initial_mapping = mapping
        self._dirty = False
        self.btn_enregistrer.state(["disabled"])


def main() -> None:
    app = ConfigProfilsApp()
    app.geometry("700x500")
    app.mainloop()


if __name__ == "__main__":
    main()

