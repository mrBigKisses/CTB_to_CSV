"""Tkinter GUI for CTB ↔ CSV conversion."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path

from ctb_csv.ctb_parser import read_ctb, write_ctb
from ctb_csv.csv_handler import ctb_to_csv, csv_to_ctb
from ctb_csv.validator import validate_csv


# ── Colour palette ────────────────────────────────────────────────────────────
BG          = "#1e1e2e"
PANEL       = "#2a2a3e"
ACCENT      = "#7c83fd"
GREEN       = "#50fa7b"
RED         = "#ff5555"
YELLOW      = "#f1fa8c"
FG          = "#cdd6f4"
FG_MUTED    = "#6c7086"
FONT        = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 9)
FONT_TITLE  = ("Segoe UI", 12, "bold")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CTB ↔ CSV  |  AutoCAD Plot Style Converter")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(680, 520)

        self._ctb_path: Path | None = None
        self._csv_path: Path | None = None
        self._template_path: Path | None = None

        self._build_ui()
        self.geometry("780x580")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        title_frame = tk.Frame(self, bg=BG)
        title_frame.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(title_frame, text="CTB ↔ CSV", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(title_frame, text="AutoCAD Plot Style Converter", font=FONT, bg=BG, fg=FG_MUTED).pack(side="left", padx=8)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=10)

        # ── CTB → CSV panel ──────────────────────────────────────────────────
        section = tk.LabelFrame(self, text=" CTB  →  CSV ", bg=BG, fg=ACCENT,
                                font=FONT, relief="groove", bd=1)
        section.pack(fill="x", padx=20, pady=6)

        row1 = tk.Frame(section, bg=BG)
        row1.pack(fill="x", padx=10, pady=6)

        self._ctb_var = tk.StringVar(value="Nessun file selezionato")
        tk.Button(row1, text="Seleziona .ctb", command=self._browse_ctb,
                  bg=PANEL, fg=FG, activebackground=ACCENT, relief="flat",
                  font=FONT, padx=10).pack(side="left")
        tk.Label(row1, textvariable=self._ctb_var, bg=BG, fg=FG_MUTED,
                 font=FONT_MONO, anchor="w").pack(side="left", padx=10, fill="x", expand=True)

        tk.Button(section, text="  Converti CTB → CSV  ", command=self._run_ctb2csv,
                  bg=ACCENT, fg="white", activebackground="#5a60d4",
                  relief="flat", font=FONT, padx=16, pady=4).pack(pady=(0, 8))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=2)

        # ── CSV → CTB panel ──────────────────────────────────────────────────
        section2 = tk.LabelFrame(self, text=" CSV  →  CTB ", bg=BG, fg=ACCENT,
                                 font=FONT, relief="groove", bd=1)
        section2.pack(fill="x", padx=20, pady=6)

        row2a = tk.Frame(section2, bg=BG)
        row2a.pack(fill="x", padx=10, pady=(6, 2))
        self._csv_var = tk.StringVar(value="Nessun file CSV selezionato")
        tk.Button(row2a, text="Seleziona .csv", command=self._browse_csv,
                  bg=PANEL, fg=FG, activebackground=ACCENT, relief="flat",
                  font=FONT, padx=10).pack(side="left")
        tk.Label(row2a, textvariable=self._csv_var, bg=BG, fg=FG_MUTED,
                 font=FONT_MONO, anchor="w").pack(side="left", padx=10, fill="x", expand=True)

        row2b = tk.Frame(section2, bg=BG)
        row2b.pack(fill="x", padx=10, pady=(0, 6))
        self._tmpl_var = tk.StringVar(value="Nessun template .ctb (opzionale — usa il .ctb originale)")
        tk.Button(row2b, text="Template .ctb", command=self._browse_template,
                  bg=PANEL, fg=FG, activebackground=ACCENT, relief="flat",
                  font=FONT, padx=10).pack(side="left")
        tk.Label(row2b, textvariable=self._tmpl_var, bg=BG, fg=FG_MUTED,
                 font=FONT_MONO, anchor="w").pack(side="left", padx=10, fill="x", expand=True)

        btn_row = tk.Frame(section2, bg=BG)
        btn_row.pack(pady=(0, 8))
        tk.Button(btn_row, text="  Valida CSV  ", command=self._run_validate,
                  bg=PANEL, fg=YELLOW, activebackground=ACCENT,
                  relief="flat", font=FONT, padx=12, pady=4).pack(side="left", padx=4)
        tk.Button(btn_row, text="  Converti CSV → CTB  ", command=self._run_csv2ctb,
                  bg=ACCENT, fg="white", activebackground="#5a60d4",
                  relief="flat", font=FONT, padx=16, pady=4).pack(side="left", padx=4)

        # ── Log area ─────────────────────────────────────────────────────────
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=4)
        log_frame = tk.Frame(self, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        tk.Label(log_frame, text="Log", bg=BG, fg=FG_MUTED, font=FONT).pack(anchor="w")
        self._log = scrolledtext.ScrolledText(
            log_frame, bg=PANEL, fg=FG, font=FONT_MONO,
            relief="flat", bd=0, state="disabled", height=8,
        )
        self._log.pack(fill="both", expand=True)
        self._log.tag_config("ok",   foreground=GREEN)
        self._log.tag_config("err",  foreground=RED)
        self._log.tag_config("warn", foreground=YELLOW)
        self._log.tag_config("info", foreground=FG_MUTED)

        # Status bar
        self._status = tk.StringVar(value="Pronto.")
        tk.Label(self, textvariable=self._status, bg=PANEL, fg=FG_MUTED,
                 font=FONT, anchor="w", padx=10).pack(fill="x", side="bottom")

    # ── Log helpers ───────────────────────────────────────────────────────────

    def _log_write(self, text: str, tag: str = ""):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_ok(self, msg: str):   self._log_write("✓  " + msg, "ok")
    def _log_err(self, msg: str):  self._log_write("✗  " + msg, "err")
    def _log_warn(self, msg: str): self._log_write("⚠  " + msg, "warn")
    def _log_info(self, msg: str): self._log_write("   " + msg, "info")

    def _set_status(self, msg: str):
        self._status.set(msg)

    # ── Browse buttons ────────────────────────────────────────────────────────

    def _browse_ctb(self):
        p = filedialog.askopenfilename(
            title="Seleziona file CTB",
            filetypes=[("AutoCAD Plot Style", "*.ctb"), ("Tutti i file", "*.*")],
        )
        if p:
            self._ctb_path = Path(p)
            self._ctb_var.set(str(self._ctb_path))
            # Auto-set template if not already set
            if self._template_path is None:
                self._template_path = self._ctb_path
                self._tmpl_var.set(str(self._ctb_path))

    def _browse_csv(self):
        p = filedialog.askopenfilename(
            title="Seleziona file CSV",
            filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")],
        )
        if p:
            self._csv_path = Path(p)
            self._csv_var.set(str(self._csv_path))

    def _browse_template(self):
        p = filedialog.askopenfilename(
            title="Seleziona template CTB",
            filetypes=[("AutoCAD Plot Style", "*.ctb"), ("Tutti i file", "*.*")],
        )
        if p:
            self._template_path = Path(p)
            self._tmpl_var.set(str(self._template_path))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _run_in_thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _run_ctb2csv(self):
        if not self._ctb_path:
            messagebox.showwarning("File mancante", "Seleziona prima un file .ctb")
            return
        self._run_in_thread(self._do_ctb2csv)

    def _do_ctb2csv(self):
        try:
            self._set_status("Conversione CTB → CSV in corso…")
            self._log_info(f"Lettura: {self._ctb_path}")
            ctb = read_ctb(self._ctb_path)
            self._log_info(f"  {len(ctb.plot_styles)} plot styles trovati")

            out = self._ctb_path.with_suffix(".csv")
            ctb_to_csv(ctb, out)
            self._log_ok(f"CSV scritto: {out}")
            self._set_status(f"Fatto: {out.name}")

            # Auto-load for CSV→CTB panel
            self._csv_path = out
            self._csv_var.set(str(out))
        except Exception as e:
            self._log_err(f"Errore: {e}")
            self._set_status("Errore durante la conversione.")

    def _run_validate(self):
        if not self._csv_path:
            messagebox.showwarning("File mancante", "Seleziona prima un file .csv")
            return
        self._run_in_thread(self._do_validate)

    def _do_validate(self):
        try:
            self._set_status("Validazione in corso…")
            self._log_info(f"Validazione: {self._csv_path}")
            issues = validate_csv(self._csv_path)
            if not issues:
                self._log_ok("CSV valido — nessun problema trovato.")
                self._set_status("Validazione OK.")
            else:
                self._log_warn(f"{len(issues)} problemi trovati:")
                for issue in issues:
                    self._log_warn(str(issue))
                self._set_status(f"Validazione: {len(issues)} problemi.")
        except Exception as e:
            self._log_err(f"Errore: {e}")
            self._set_status("Errore durante la validazione.")

    def _run_csv2ctb(self):
        if not self._csv_path:
            messagebox.showwarning("File mancante", "Seleziona prima un file .csv")
            return
        if not self._template_path:
            messagebox.showwarning("Template mancante", "Seleziona il .ctb originale come template")
            return
        self._run_in_thread(self._do_csv2ctb)

    def _do_csv2ctb(self):
        try:
            self._set_status("Validazione CSV prima della conversione…")
            issues = validate_csv(self._csv_path)
            if issues:
                self._log_warn(f"{len(issues)} problemi nel CSV:")
                for issue in issues:
                    self._log_warn(str(issue))
                # Ask user on main thread
                self.after(0, self._ask_continue_with_issues)
                return

            self._set_status("Conversione CSV → CTB in corso…")
            self._do_csv2ctb_write()
        except Exception as e:
            self._log_err(f"Errore: {e}")
            self._set_status("Errore durante la conversione.")

    def _ask_continue_with_issues(self):
        if messagebox.askyesno("Problemi nel CSV",
                               "Il CSV contiene problemi. Vuoi convertire comunque?"):
            threading.Thread(target=self._do_csv2ctb_write, daemon=True).start()

    def _do_csv2ctb_write(self):
        try:
            self._log_info(f"Lettura template: {self._template_path}")
            template = read_ctb(self._template_path)
            self._log_info(f"Lettura CSV: {self._csv_path}")
            ctb = csv_to_ctb(self._csv_path, template)
            out = self._csv_path.with_suffix(".ctb")
            write_ctb(ctb, out)
            self._log_ok(f"CTB scritto: {out}")
            self._set_status(f"Fatto: {out.name}")
        except Exception as e:
            self._log_err(f"Errore: {e}")
            self._set_status("Errore durante la conversione.")


def main():
    app = App()
    app.mainloop()
