"""Interface de configuration des profils YAML (pilotée par schema_ui.yaml)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

TOOLS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TOOLS_DIR.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config_profils_schema import (  # noqa: E402
    DEFAULTS_PATH,
    INHERITED_HINT,
    FieldSpec,
    PDF_PRESENTATION_PATH,
    PROFILS_DIR,
    ROOT_DIR,
    SectionSpec,
    coerce_field_value,
    dump_profile_yaml,
    fields_for_section,
    get_by_path,
    get_pdf_field_value,
    list_sections_for_profile,
    load_defaults_data,
    load_pdf_profile_overlay,
    load_schema,
    load_yaml_mapping,
    parse_profile_yaml,
    path_exists,
    resolve_field_state,
    save_yaml_mapping,
    set_by_path,
    set_pdf_field_value,
)

INHERITED_FG = "#6b6b6b"


def lister_profils(directory: Path) -> list[tuple[str, Path, str]]:
    """(label affiché, chemin fichier, id profil)."""
    profils: list[tuple[str, Path, str]] = []
    if not directory.exists():
        return profils

    try:
        from ofbilan.engine.catalogue_profils import list_profiles

        profile_ids = list_profiles()
    except Exception:
        profile_ids = sorted(
            p.stem
            for p in directory.glob("*.yaml")
            if p.is_file() and p.stem not in ("_defaults", "schema_ui")
        )

    for pid in profile_ids:
        path = directory / f"{pid}.yaml"
        if not path.exists():
            continue
        label = pid
        try:
            data = load_yaml_mapping(path)
            label_yaml = data.get("label")
            if isinstance(label_yaml, str) and label_yaml.strip():
                label = label_yaml.strip()
        except Exception:
            pass
        profils.append((f"{label} ({pid})", path, pid))

    if DEFAULTS_PATH.exists():
        profils.append(("Socle commun (_defaults)", DEFAULTS_PATH, "_defaults"))

    return profils


class ConfigProfilsApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Configurer les profils de bilans")
        self.geometry("960x640")
        self.minsize(820, 520)

        self.sections, self.pdf_catalog = load_schema()
        self.profils = lister_profils(PROFILS_DIR)
        self.current_path: Path | None = None
        self.current_id: str = ""
        self.profile_data: dict[str, Any] = {}
        self.defaults_data: dict[str, Any] = {}
        self.pdf_doc: dict[str, Any] | None = None
        self.pdf_prof_cfg: dict[str, Any] | None = None
        self.pdf_effective_blocks: dict[str, Any] = {}
        self.section_views: list[tuple[SectionSpec, list[FieldSpec]]] = []
        self._widgets: dict[str, Any] = {}
        self._initial_snapshot: dict[str, Any] = {}
        self._dirty_profile = False
        self._dirty_pdf = False
        self._dirty_yaml = False
        self._current_section_idx = 0
        self._yaml_editor: scrolledtext.ScrolledText | None = None
        self._yaml_editor_baseline = ""

        self._build_ui()
        if self.profils:
            self.profil_combo.current(0)
            self.on_select_profil()
        else:
            messagebox.showwarning("Aucun profil", f"Aucun YAML dans {PROFILS_DIR}")

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(top, text="Profil :").pack(side=tk.LEFT)
        self.profil_var = tk.StringVar()
        self.profil_combo = ttk.Combobox(
            top,
            textvariable=self.profil_var,
            values=[x[0] for x in self.profils],
            state="readonly",
            width=48,
        )
        self.profil_combo.pack(side=tk.LEFT, padx=6)
        self.profil_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_select_profil())

        self.info_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.info_var, foreground="#444").pack(side=tk.LEFT, padx=8)

        self.merge_hint_var = tk.StringVar(value="")
        ttk.Label(
            self,
            textvariable=self.merge_hint_var,
            wraplength=900,
            foreground=INHERITED_FG,
            font=("", 9),
        ).pack(fill=tk.X, padx=12, pady=(0, 4))

        search_row = ttk.Frame(self)
        search_row.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Label(search_row, text="Rechercher un paramètre :").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_a: self._render_current_section())
        ttk.Entry(search_row, textvariable=self.search_var, width=42).pack(side=tk.LEFT, padx=6)

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        nav_frame = ttk.Frame(body, width=220)
        body.add(nav_frame, weight=0)
        ttk.Label(nav_frame, text="Rubriques", font=("", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.nav_list = tk.Listbox(nav_frame, exportselection=False, activestyle="dotbox")
        self.nav_list.pack(fill=tk.BOTH, expand=True)
        self.nav_list.bind("<<ListboxSelect>>", self._on_nav_select)

        form_outer = ttk.Frame(body)
        body.add(form_outer, weight=1)

        self.section_title_var = tk.StringVar(value="")
        ttk.Label(form_outer, textvariable=self.section_title_var, font=("", 11, "bold")).pack(
            anchor=tk.W
        )
        self.section_help_var = tk.StringVar(value="")
        ttk.Label(
            form_outer,
            textvariable=self.section_help_var,
            wraplength=680,
            foreground="#555",
        ).pack(anchor=tk.W, pady=(0, 8))

        canvas = tk.Canvas(form_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(form_outer, orient=tk.VERTICAL, command=canvas.yview)
        self.form_frame = ttk.Frame(canvas)
        self.form_frame.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.form_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._form_canvas = canvas

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=10)
        self.status_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Aperçu des changements", command=self.on_apercu).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="Recharger", command=self.on_recharger).pack(side=tk.RIGHT, padx=4)
        self.btn_save = ttk.Button(bottom, text="Enregistrer", command=self.on_enregistrer, state=tk.DISABLED)
        self.btn_save.pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="Quitter", command=self.destroy).pack(side=tk.RIGHT, padx=4)

    def _uses_defaults_merge(self) -> bool:
        return bool(self.defaults_data) and self.current_id != "_defaults"

    def _rebuild_section_views(self) -> None:
        self.section_views = list_sections_for_profile(
            self.sections,
            profile=self.profile_data,
            profile_id=self.current_id,
            pdf_catalog=self.pdf_catalog,
            defaults=self.defaults_data,
        )

    def _current_section(self) -> SectionSpec | None:
        if not self.section_views:
            return None
        return self.section_views[self._current_section_idx][0]

    def _confirm_abandon(self) -> bool:
        if not (self._dirty_profile or self._dirty_pdf or self._dirty_yaml):
            return True
        return messagebox.askyesno(
            "Modifications non enregistrées",
            "Des modifications ne sont pas enregistrées.\nLes abandonner ?",
        )

    def on_select_profil(self) -> None:
        if not self._confirm_abandon():
            idx = next(
                (i for i, (lbl, _, _) in enumerate(self.profils) if lbl == self.profil_var.get()),
                -1,
            )
            if 0 <= idx < len(self.profils):
                self.profil_combo.current(idx)
            return

        idx = self.profil_combo.current()
        if idx < 0:
            return
        _label, path, pid = self.profils[idx]
        try:
            self.profile_data = load_yaml_mapping(path)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de charger {path}:\n{exc}")
            return

        self.current_path = path
        self.current_id = pid
        self.info_var.set(str(path.relative_to(ROOT_DIR)))
        self.defaults_data = {} if pid == "_defaults" else load_defaults_data()
        if self._uses_defaults_merge():
            self.merge_hint_var.set(
                "Valeur effective = profil + socle _defaults.yaml. "
                "Les paramètres en gris sont hérités du socle ; les modifier écrit une surcharge dans ce profil."
            )
        else:
            self.merge_hint_var.set("")

        self._dirty_profile = False
        self._dirty_pdf = False
        self._dirty_yaml = False
        self.btn_save.config(state=tk.DISABLED)
        self.search_var.set("")
        self._yaml_editor = None
        self._yaml_editor_baseline = ""

        self.pdf_doc = None
        self.pdf_prof_cfg = None
        self.pdf_effective_blocks = {}
        if pid not in ("_defaults",):
            try:
                doc, prof_cfg, effective = load_pdf_profile_overlay(pid)
                self.pdf_doc = doc
                self.pdf_prof_cfg = prof_cfg
                self.pdf_effective_blocks = effective
            except Exception:
                pass

        self._rebuild_section_views()

        self.nav_list.delete(0, tk.END)
        for section, _fields in self.section_views:
            self.nav_list.insert(tk.END, section.title)
        if self.section_views:
            self.nav_list.selection_set(0)
            self._current_section_idx = 0
            self._render_current_section()

        self._initial_snapshot = self._snapshot_values()
        self._update_status()

    def _on_nav_select(self, _event: Any = None) -> None:
        sel = self.nav_list.curselection()
        if not sel:
            return
        new_idx = int(sel[0])
        if new_idx == self._current_section_idx:
            return

        old_section = self.section_views[self._current_section_idx][0]
        if old_section.ui_mode == "yaml_editor":
            if not self._try_apply_yaml_editor(show_error=True):
                self.nav_list.selection_clear(0, tk.END)
                self.nav_list.selection_set(self._current_section_idx)
                self.nav_list.see(self._current_section_idx)
                return
        else:
            self._flush_widgets_to_model()

        self._current_section_idx = new_idx
        self._render_current_section()

    def _try_apply_yaml_editor(self, *, show_error: bool) -> bool:
        if self._yaml_editor is None:
            return True
        text = self._yaml_editor.get("1.0", "end-1c")
        if text == self._yaml_editor_baseline:
            self._dirty_yaml = False
            return True
        try:
            self.profile_data = parse_profile_yaml(text)
        except Exception as exc:
            if show_error:
                messagebox.showerror(
                    "YAML invalide",
                    f"Corrigez la syntaxe avant de continuer :\n\n{exc}",
                )
            return False
        self._yaml_editor_baseline = dump_profile_yaml(self.profile_data)
        self._rebuild_section_views()
        self._mark_dirty(profile=True)
        self._dirty_yaml = False
        return True

    def _on_yaml_edited(self) -> None:
        if self._yaml_editor is None:
            return
        text = self._yaml_editor.get("1.0", "end-1c")
        if text != self._yaml_editor_baseline:
            self._dirty_yaml = True
            self.btn_save.config(state=tk.NORMAL)
            self._update_status()

    def _flush_widgets_to_model(self) -> None:
        for _key, meta in self._widgets.items():
            spec: FieldSpec = meta["spec"]
            widget = meta["widget"]
            if spec.target == "pdf_presentation":
                if not self.pdf_prof_cfg:
                    continue
                blocks = self.pdf_prof_cfg.setdefault("blocks", {})
                if spec.widget == "bool" and isinstance(widget, tk.BooleanVar):
                    set_pdf_field_value(blocks, spec.path, widget.get())
                continue
            if spec.widget == "bool" and isinstance(widget, tk.BooleanVar):
                val = widget.get()
            elif spec.widget == "int" and isinstance(widget, tk.StringVar):
                val = coerce_field_value(spec, widget.get())
            elif spec.widget in ("text", "choice") and isinstance(widget, tk.StringVar):
                val = coerce_field_value(spec, widget.get())
            elif spec.widget == "list_lines" and isinstance(widget, scrolledtext.ScrolledText):
                val = coerce_field_value(spec, widget.get("1.0", tk.END))
            else:
                continue
            if spec.path == "restrict_geo" and val == "":
                if path_exists(self.profile_data, "restrict_geo"):
                    set_by_path(self.profile_data, "restrict_geo", None)
                continue
            set_by_path(self.profile_data, spec.path, val)

    def _snapshot_values(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        for _sec, fields in self.section_views:
            for spec in fields:
                key = f"{spec.target}:{spec.path}"
                if spec.target == "pdf_presentation":
                    snap[key] = get_pdf_field_value(self.pdf_effective_blocks, spec.path)
                else:
                    state = resolve_field_state(
                        spec,
                        self.profile_data,
                        profile_id=self.current_id,
                        defaults=self.defaults_data,
                    )
                    snap[key] = state.effective
        return snap

    def _render_current_section(self) -> None:
        for child in self.form_frame.winfo_children():
            child.destroy()
        self._widgets.clear()
        self._yaml_editor = None

        if not self.section_views:
            ttk.Label(self.form_frame, text="Aucune rubrique pour ce profil.").pack(anchor=tk.W)
            return

        section, all_fields = self.section_views[self._current_section_idx]
        self.section_title_var.set(section.title)
        self.section_help_var.set(section.help or "")

        if section.ui_mode == "yaml_editor":
            ttk.Label(
                self.form_frame,
                text=f"Fichier : {self.info_var.get()}",
                font=("", 9, "bold"),
            ).pack(anchor=tk.W, padx=4, pady=(0, 4))
            self._yaml_editor = scrolledtext.ScrolledText(
                self.form_frame,
                height=28,
                width=88,
                font=("Consolas", 10),
                wrap=tk.NONE,
            )
            text = dump_profile_yaml(self.profile_data)
            self._yaml_editor.insert("1.0", text)
            self._yaml_editor_baseline = text
            self._yaml_editor.bind("<KeyRelease>", lambda _e: self._on_yaml_edited())
            self._yaml_editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            return

        query = self.search_var.get().strip().lower()
        fields = [
            f
            for f in all_fields
            if not query or query in f"{f.label} {f.help} {f.path}".lower()
        ]
        if not fields:
            ttk.Label(self.form_frame, text="Aucun paramètre ne correspond à la recherche.").pack(
                anchor=tk.W, padx=4, pady=8
            )
            return

        for spec in fields:
            self._add_field_row(spec)

    def _add_inherited_badge(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text=INHERITED_HINT,
            foreground=INHERITED_FG,
            font=("", 8, "italic"),
        ).pack(anchor=tk.W)

    def _add_field_row(self, spec: FieldSpec) -> None:
        row = ttk.Frame(self.form_frame)
        row.pack(fill=tk.X, padx=4, pady=6)

        state = resolve_field_state(
            spec,
            self.profile_data,
            profile_id=self.current_id,
            defaults=self.defaults_data,
        )
        title_fg = INHERITED_FG if state.inherited else None
        title_kwargs: dict[str, Any] = {"font": ("", 10, "bold")}
        if title_fg:
            title_kwargs["foreground"] = title_fg
        ttk.Label(row, text=spec.label, **title_kwargs).pack(anchor=tk.W)
        if spec.help:
            ttk.Label(row, text=spec.help, wraplength=640, foreground="#555", font=("", 9)).pack(
                anchor=tk.W
            )
        ttk.Label(row, text=f"YAML : {spec.path}", foreground="#888", font=("", 8)).pack(anchor=tk.W)
        if state.inherited:
            self._add_inherited_badge(row)

        if spec.target == "pdf_presentation":
            val = get_pdf_field_value(self.pdf_effective_blocks, spec.path)
            var = tk.BooleanVar(value=val)
            var.trace_add("write", lambda *_a: self._mark_dirty(pdf=True))
            ttk.Checkbutton(row, text="Afficher dans le PDF", variable=var).pack(anchor=tk.W, padx=8, pady=2)
            self._widgets[f"pdf:{spec.path}"] = {"spec": spec, "widget": var}
            return

        if spec.path == "id":
            ttk.Label(row, text=self.current_id, font=("", 10)).pack(anchor=tk.W, padx=8)
            return

        display = state.effective

        if spec.widget == "bool":
            var = tk.BooleanVar(value=bool(display))
            var.trace_add("write", lambda *_a: self._mark_dirty(profile=True))
            ttk.Checkbutton(row, text="Oui", variable=var).pack(anchor=tk.W, padx=8)
            self._widgets[f"profile:{spec.path}"] = {"spec": spec, "widget": var}
        elif spec.widget == "int":
            var = tk.StringVar(value=str(display))
            var.trace_add("write", lambda *_a: self._mark_dirty(profile=True))
            entry = ttk.Entry(row, textvariable=var, width=12)
            if state.inherited:
                entry.configure(style="Inherited.TEntry")
            entry.pack(anchor=tk.W, padx=8)
            self._widgets[f"profile:{spec.path}"] = {"spec": spec, "widget": var}
        elif spec.widget == "choice":
            keys = list(spec.choices.keys())
            labels = [spec.choices[k] for k in keys]
            current_key = str(display) if str(display) in spec.choices else ""
            try:
                idx = keys.index(current_key)
            except ValueError:
                idx = 0 if keys else -1
            var = tk.StringVar(value=labels[idx] if 0 <= idx < len(labels) else "")
            combo = ttk.Combobox(row, textvariable=var, values=labels, state="readonly", width=58)
            combo.pack(anchor=tk.W, padx=8, fill=tk.X)
            combo.bind("<<ComboboxSelected>>", lambda _e: self._mark_dirty(profile=True))
            self._widgets[f"profile:{spec.path}"] = {"spec": spec, "widget": var}
        elif spec.widget == "list_lines":
            txt = scrolledtext.ScrolledText(row, height=5, width=72, font=("Consolas", 9))
            txt.insert(tk.END, str(display))
            if state.inherited:
                txt.configure(foreground=INHERITED_FG)
            txt.bind("<KeyRelease>", lambda _e: self._mark_dirty(profile=True))
            txt.pack(anchor=tk.W, padx=8, fill=tk.X)
            self._widgets[f"profile:{spec.path}"] = {"spec": spec, "widget": txt}
        elif spec.widget == "readonly":
            fg = INHERITED_FG if state.inherited else "black"
            ttk.Label(row, text=str(display), font=("", 10), foreground=fg).pack(anchor=tk.W, padx=8)
        else:
            var = tk.StringVar(value=str(display))
            var.trace_add("write", lambda *_a: self._mark_dirty(profile=True))
            entry = ttk.Entry(row, textvariable=var, width=72)
            entry.pack(anchor=tk.W, padx=8, fill=tk.X)
            self._widgets[f"profile:{spec.path}"] = {"spec": spec, "widget": var}

    def _mark_dirty(self, *, profile: bool = False, pdf: bool = False) -> None:
        if profile:
            self._dirty_profile = True
        if pdf:
            self._dirty_pdf = True
        self.btn_save.config(state=tk.NORMAL)
        self._update_status()

    def _update_status(self) -> None:
        parts = []
        if self._dirty_profile:
            parts.append("profil YAML")
        if self._dirty_pdf:
            parts.append("présentation PDF")
        if self._dirty_yaml:
            parts.append("éditeur YAML")
        self.status_var.set(
            "Modifications : " + ", ".join(parts) if parts else "Aucune modification en attente"
        )

    def on_recharger(self) -> None:
        if not self._confirm_abandon():
            return
        self.on_select_profil()

    def on_apercu(self) -> None:
        sec = self._current_section()
        if sec and sec.ui_mode == "yaml_editor":
            if not self._try_apply_yaml_editor(show_error=True):
                return
        else:
            self._flush_widgets_to_model()
        current = self._snapshot_values()
        lines = ["Paramètre | Avant | Après", "-" * 72]
        for key, old in sorted(self._initial_snapshot.items()):
            new = current.get(key, old)
            if old != new:
                lines.append(f"{key} | {old} | {new}")
        if len(lines) == 2:
            messagebox.showinfo("Aperçu", "Aucune modification.")
            return
        win = tk.Toplevel(self)
        win.title("Aperçu des changements")
        win.geometry("800x400")
        st = scrolledtext.ScrolledText(win, font=("Consolas", 9))
        st.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        st.insert(tk.END, "\n".join(lines))
        st.configure(state=tk.DISABLED)

    def on_enregistrer(self) -> None:
        if self.current_path is None:
            return
        sec = self._current_section()
        if sec and sec.ui_mode == "yaml_editor":
            if not self._try_apply_yaml_editor(show_error=True):
                return
        else:
            self._flush_widgets_to_model()
        try:
            if self._dirty_profile:
                save_yaml_mapping(self.current_path, self.profile_data)
            if self._dirty_pdf and self.pdf_doc is not None:
                save_yaml_mapping(PDF_PRESENTATION_PATH, self.pdf_doc)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Enregistrement impossible :\n{exc}")
            return

        saved = []
        if self._dirty_profile:
            saved.append(str(self.current_path))
        if self._dirty_pdf:
            saved.append(str(PDF_PRESENTATION_PATH.relative_to(ROOT_DIR)))
        messagebox.showinfo("Enregistré", "Fichiers mis à jour :\n" + "\n".join(saved))
        self._dirty_profile = False
        self._dirty_pdf = False
        self._dirty_yaml = False
        self.btn_save.config(state=tk.DISABLED)
        if self.pdf_doc is not None and self.current_id:
            _doc, prof_cfg, effective = load_pdf_profile_overlay(self.current_id)
            self.pdf_doc = _doc
            self.pdf_prof_cfg = prof_cfg
            self.pdf_effective_blocks = effective
        self._initial_snapshot = self._snapshot_values()
        if sec and sec.ui_mode == "yaml_editor" and self._yaml_editor is not None:
            self._yaml_editor_baseline = dump_profile_yaml(self.profile_data)
        self._update_status()

    def destroy(self) -> None:
        if self._confirm_abandon():
            super().destroy()


def main() -> None:
    app = ConfigProfilsApp()
    try:
        style = ttk.Style()
        style.configure("Inherited.TEntry", foreground=INHERITED_FG)
    except tk.TclError:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
