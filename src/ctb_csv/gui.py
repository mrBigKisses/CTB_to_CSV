"""Tkinter GUI for CTB ↔ CSV conversion.

Designed to run from any working directory — every path is chosen
explicitly via file dialogs; nothing is auto-saved next to the source.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path

from ctb_csv.ctb_parser import read_ctb, write_ctb
from ctb_csv.csv_handler import ctb_to_csv, csv_to_ctb
from ctb_csv.validator import validate_csv
from ctb_csv.reporter import generate_report

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
PANEL    = "#2a2a3e"
ACCENT   = "#7c83fd"
GREEN    = "#50fa7b"
RED      = "#ff5555"
YELLOW   = "#f1fa8c"
FG       = "#cdd6f4"
MUTED    = "#6c7086"
AI_BG    = "#2f2a4e"
FONT     = ("Segoe UI", 10)
MONO     = ("Consolas", 9)
BOLD     = ("Segoe UI", 10, "bold")


def _open(path: Path) -> None:
    os.startfile(str(path))


# ── Reusable file-row widget ──────────────────────────────────────────────────

class _FileRow(tk.Frame):
    """One row: [label]  [path display]  [action button]"""

    def __init__(self, parent, label: str, btn_text: str, btn_cmd, *,
                 btn_bg=PANEL, btn_fg=FG):
        super().__init__(parent, bg=BG)
        self._var = tk.StringVar(value="—")

        tk.Label(self, text=label, bg=BG, fg=MUTED, font=FONT,
                 width=13, anchor="w").pack(side="left")
        tk.Label(self, textvariable=self._var, bg=BG, fg=FG,
                 font=MONO, anchor="w").pack(side="left", fill="x",
                                             expand=True, padx=(4, 8))
        tk.Button(self, text=btn_text, command=btn_cmd,
                  bg=btn_bg, fg=btn_fg, activebackground=ACCENT,
                  relief="flat", font=FONT, padx=8).pack(side="right")

    @property
    def path(self) -> Path | None:
        v = self._var.get()
        return Path(v) if v and v != "—" else None

    @path.setter
    def path(self, p: Path | None) -> None:
        self._var.set(str(p) if p else "—")


# ── Main app ──────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CTB ↔ CSV  ·  AutoCAD Plot Style Converter")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(740, 560)
        self._build_ui()
        self.geometry("900x640")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _section(self, title: str) -> tk.LabelFrame:
        f = tk.LabelFrame(self, text=f"  {title}  ", bg=BG, fg=ACCENT,
                          font=BOLD, relief="groove", bd=1)
        f.pack(fill="x", padx=18, pady=(6, 0))
        return f

    def _btn(self, parent, text: str, cmd, *,
             primary=False, ai=False, warn=False, **kw) -> tk.Button:
        if primary:
            bg, fg, ab = ACCENT, "white", "#5a60d4"
        elif ai:
            bg, fg, ab = AI_BG, ACCENT, "#4a3a7e"
        elif warn:
            bg, fg, ab = PANEL, YELLOW, ACCENT
        else:
            bg, fg, ab = PANEL, FG, ACCENT
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         activebackground=ab, relief="flat",
                         font=FONT, padx=12, pady=4, **kw)

    def _thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── log / status ──────────────────────────────────────────────────────────

    def _write(self, text: str, tag: str = ""):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def ok(self, msg):   self._write("✓  " + msg, "ok")
    def err(self, msg):  self._write("✗  " + msg, "err")
    def warn(self, msg): self._write("⚠  " + msg, "warn")
    def info(self, msg): self._write("   " + msg, "info")
    def status(self, msg): self._status.set(msg)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(bar, text="CTB ↔ CSV", font=("Segoe UI", 13, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(bar, text="AutoCAD Plot Style Converter",
                 font=FONT, bg=BG, fg=MUTED).pack(side="left", padx=10)
        ttk.Separator(self).pack(fill="x", padx=18, pady=(6, 2))

        # ── CTB → CSV ─────────────────────────────────────────────────────────
        s1 = self._section("CTB  →  CSV")

        self._ctb_src = _FileRow(s1, "Sorgente CTB:", "Sfoglia…", self._pick_ctb_src)
        self._ctb_src.pack(fill="x", padx=10, pady=(8, 2))

        self._csv_dst = _FileRow(s1, "Salva CSV in:", "Cambia…", self._pick_csv_dst)
        self._csv_dst.pack(fill="x", padx=10, pady=(0, 2))

        r1 = tk.Frame(s1, bg=BG)
        r1.pack(pady=(2, 8))
        self._btn(r1, "Converti CTB → CSV", self._run_ctb2csv, primary=True).pack(side="left", padx=4)
        self._open_csv_btn = self._btn(r1, "Apri CSV  ↗", self._open_csv)
        self._open_csv_btn.pack(side="left", padx=4)
        self._open_csv_btn.config(state="disabled")

        # ── Report ────────────────────────────────────────────────────────────
        s2 = self._section("Report HTML / PDF / AI")

        self._html_dst = _FileRow(s2, "Salva HTML in:", "Cambia…", self._pick_html_dst)
        self._html_dst.pack(fill="x", padx=10, pady=(8, 2))

        r2 = tk.Frame(s2, bg=BG)
        r2.pack(pady=(2, 8))
        self._btn(r2, "HTML", self._run_report_html).pack(side="left", padx=4)
        self._btn(r2, "PDF", self._run_report_pdf).pack(side="left", padx=4)
        self._btn(r2, "AI  ✦", self._run_report_ai, ai=True).pack(side="left", padx=4)

        # ── CSV → CTB ─────────────────────────────────────────────────────────
        s3 = self._section("CSV  →  CTB")

        self._csv_src = _FileRow(s3, "Sorgente CSV:", "Sfoglia…", self._pick_csv_src)
        self._csv_src.pack(fill="x", padx=10, pady=(8, 2))

        self._tmpl_ctb = _FileRow(s3, "Template CTB:", "Sfoglia…", self._pick_tmpl)
        self._tmpl_ctb.pack(fill="x", padx=10, pady=(0, 2))

        self._ctb_dst = _FileRow(s3, "Salva CTB in:", "Cambia…", self._pick_ctb_dst)
        self._ctb_dst.pack(fill="x", padx=10, pady=(0, 2))

        r3 = tk.Frame(s3, bg=BG)
        r3.pack(pady=(2, 8))
        self._btn(r3, "Valida CSV", self._run_validate, warn=True).pack(side="left", padx=4)
        self._btn(r3, "Converti CSV → CTB", self._run_csv2ctb, primary=True).pack(side="left", padx=4)

        # ── Log ───────────────────────────────────────────────────────────────
        ttk.Separator(self).pack(fill="x", padx=18, pady=(8, 2))
        lf = tk.Frame(self, bg=BG)
        lf.pack(fill="both", expand=True, padx=18, pady=(0, 0))
        tk.Label(lf, text="Log", bg=BG, fg=MUTED, font=FONT).pack(anchor="w")
        self._log = scrolledtext.ScrolledText(
            lf, bg=PANEL, fg=FG, font=MONO,
            relief="flat", bd=0, state="disabled", height=7,
        )
        self._log.pack(fill="both", expand=True)
        self._log.tag_config("ok",   foreground=GREEN)
        self._log.tag_config("err",  foreground=RED)
        self._log.tag_config("warn", foreground=YELLOW)
        self._log.tag_config("info", foreground=MUTED)

        # Status bar
        self._status = tk.StringVar(value="Pronto.")
        tk.Label(self, textvariable=self._status, bg=PANEL, fg=MUTED,
                 font=FONT, anchor="w", padx=10).pack(fill="x", side="bottom")

    # ── File pickers ──────────────────────────────────────────────────────────

    def _pick_ctb_src(self):
        p = filedialog.askopenfilename(
            title="Seleziona file CTB sorgente",
            filetypes=[("AutoCAD Plot Style", "*.ctb"), ("Tutti i file", "*.*")],
        )
        if not p:
            return
        path = Path(p)
        self._ctb_src.path = path
        # Auto-suggest output paths
        if self._csv_dst.path is None:
            self._csv_dst.path = path.with_suffix(".csv")
        if self._html_dst.path is None:
            self._html_dst.path = path.with_suffix(".html")
        # Use as template default
        if self._tmpl_ctb.path is None:
            self._tmpl_ctb.path = path

    def _pick_csv_dst(self):
        init = self._csv_dst.path or (
            self._ctb_src.path.with_suffix(".csv") if self._ctb_src.path else Path.home()
        )
        p = filedialog.asksaveasfilename(
            title="Salva CSV come…",
            initialfile=init.name,
            initialdir=str(init.parent),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")],
        )
        if p:
            self._csv_dst.path = Path(p)

    def _pick_html_dst(self):
        init = self._html_dst.path or (
            self._ctb_src.path.with_suffix(".html") if self._ctb_src.path else Path.home()
        )
        p = filedialog.asksaveasfilename(
            title="Salva Report HTML come…",
            initialfile=init.name,
            initialdir=str(init.parent),
            defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("Tutti i file", "*.*")],
        )
        if p:
            self._html_dst.path = Path(p)

    def _pick_csv_src(self):
        p = filedialog.askopenfilename(
            title="Seleziona file CSV sorgente",
            filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")],
        )
        if not p:
            return
        path = Path(p)
        self._csv_src.path = path
        if self._ctb_dst.path is None:
            self._ctb_dst.path = path.with_suffix(".ctb")

    def _pick_tmpl(self):
        p = filedialog.askopenfilename(
            title="Seleziona CTB template (struttura globale)",
            filetypes=[("AutoCAD Plot Style", "*.ctb"), ("Tutti i file", "*.*")],
        )
        if p:
            self._tmpl_ctb.path = Path(p)

    def _pick_ctb_dst(self):
        init = self._ctb_dst.path or (
            self._csv_src.path.with_suffix(".ctb") if self._csv_src.path else Path.home()
        )
        p = filedialog.asksaveasfilename(
            title="Salva CTB come…",
            initialfile=init.name,
            initialdir=str(init.parent),
            defaultextension=".ctb",
            filetypes=[("AutoCAD Plot Style", "*.ctb"), ("Tutti i file", "*.*")],
        )
        if p:
            self._ctb_dst.path = Path(p)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_csv(self):
        if self._csv_dst.path and self._csv_dst.path.exists():
            _open(self._csv_dst.path)
        else:
            messagebox.showwarning("File non trovato", "Converti prima il CTB in CSV.")

    def _run_ctb2csv(self):
        if not self._ctb_src.path:
            messagebox.showwarning("File mancante", "Seleziona il file CTB sorgente.")
            return
        if not self._csv_dst.path:
            self._pick_csv_dst()
        if not self._csv_dst.path:
            return
        self._thread(self._do_ctb2csv)

    def _do_ctb2csv(self):
        try:
            self.status("Conversione CTB → CSV in corso…")
            self.info(f"Lettura: {self._ctb_src.path}")
            ctb = read_ctb(self._ctb_src.path)
            self.info(f"  {len(ctb.plot_styles)} plot styles trovati")
            ctb_to_csv(ctb, self._csv_dst.path)
            self.ok(f"CSV scritto: {self._csv_dst.path}")
            self.status(f"Fatto: {self._csv_dst.path.name}")
            self.after(0, lambda: self._open_csv_btn.config(state="normal"))
            # Auto-load into CSV→CTB section
            if self._csv_src.path is None:
                self._csv_src.path = self._csv_dst.path
            if self._ctb_dst.path is None:
                self._ctb_dst.path = self._csv_dst.path.with_suffix(".ctb")
        except Exception as e:
            self.err(f"Errore: {e}")
            self.status("Errore durante la conversione.")

    def _run_validate(self):
        if not self._csv_src.path:
            messagebox.showwarning("File mancante", "Seleziona il file CSV sorgente.")
            return
        self._thread(self._do_validate)

    def _do_validate(self):
        try:
            self.status("Validazione in corso…")
            self.info(f"Validazione: {self._csv_src.path}")
            issues = validate_csv(self._csv_src.path)
            if not issues:
                self.ok("CSV valido — nessun problema trovato.")
                self.status("Validazione OK.")
            else:
                self.warn(f"{len(issues)} problemi trovati:")
                for issue in issues:
                    self.warn(str(issue))
                self.status(f"Validazione: {len(issues)} problemi.")
        except Exception as e:
            self.err(f"Errore: {e}")
            self.status("Errore durante la validazione.")

    def _run_csv2ctb(self):
        if not self._csv_src.path:
            messagebox.showwarning("File mancante", "Seleziona il file CSV sorgente.")
            return
        if not self._tmpl_ctb.path:
            messagebox.showwarning("Template mancante",
                                   "Seleziona il CTB originale come template.")
            return
        if not self._ctb_dst.path:
            self._pick_ctb_dst()
        if not self._ctb_dst.path:
            return
        self._thread(self._do_csv2ctb)

    def _do_csv2ctb(self):
        try:
            self.status("Validazione CSV prima della conversione…")
            issues = validate_csv(self._csv_src.path)
            if issues:
                self.warn(f"{len(issues)} problemi nel CSV:")
                for issue in issues:
                    self.warn(str(issue))
                self.after(0, self._ask_continue)
                return
            self._do_csv2ctb_write()
        except Exception as e:
            self.err(f"Errore: {e}")
            self.status("Errore durante la conversione.")

    def _ask_continue(self):
        if messagebox.askyesno("Problemi nel CSV",
                               "Il CSV contiene problemi. Vuoi convertire comunque?"):
            self._thread(self._do_csv2ctb_write)

    def _do_csv2ctb_write(self):
        try:
            self.status("Conversione CSV → CTB in corso…")
            self.info(f"Template: {self._tmpl_ctb.path}")
            template = read_ctb(self._tmpl_ctb.path)
            self.info(f"CSV: {self._csv_src.path}")
            ctb = csv_to_ctb(self._csv_src.path, template)
            write_ctb(ctb, self._ctb_dst.path)
            self.ok(f"CTB scritto: {self._ctb_dst.path}")
            self.status(f"Fatto: {self._ctb_dst.path.name}")
        except Exception as e:
            self.err(f"Errore: {e}")
            self.status("Errore durante la conversione.")

    def _run_report_html(self):
        self._run_report(pdf=False, use_llm=False)

    def _run_report_pdf(self):
        self._run_report(pdf=True, use_llm=False)

    def _run_report_ai(self):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            messagebox.showwarning(
                "API key mancante",
                "Imposta ANTHROPIC_API_KEY prima di usare il report AI.\n\n"
                "Esempio (PowerShell):\n  $env:ANTHROPIC_API_KEY = 'sk-ant-...'",
            )
            return
        self._run_report(pdf=False, use_llm=True)

    def _run_report(self, *, pdf: bool, use_llm: bool):
        if not self._ctb_src.path:
            messagebox.showwarning("File mancante", "Seleziona il file CTB sorgente.")
            return
        if not self._html_dst.path:
            self._pick_html_dst()
        if not self._html_dst.path:
            return
        self._thread(lambda: self._do_report(pdf=pdf, use_llm=use_llm))

    def _do_report(self, *, pdf: bool, use_llm: bool):
        import webbrowser
        try:
            label = "AI" if use_llm else ("PDF" if pdf else "HTML")
            self.status(f"Generazione report {label} in corso…")
            if use_llm:
                self.info("Chiamata API Claude per inferire i raggruppamenti…")
            self.info(f"Lettura: {self._ctb_src.path}")
            ctb = read_ctb(self._ctb_src.path)
            result = generate_report(
                ctb,
                self._html_dst.path,
                source_filename=self._ctb_src.path.name,
                pdf=pdf,
                use_llm=use_llm,
            )
            self.ok(f"Report scritto: {result}")
            self.status(f"Fatto: {result.name}")
            if result.suffix == ".html":
                webbrowser.open(result.as_uri())
        except ImportError as e:
            self.err(f"Pacchetto mancante: {e}")
            self.status("Installa 'anthropic' per il report AI.")
        except Exception as e:
            self.err(f"Errore: {e}")
            self.status("Errore durante la generazione del report.")


def main():
    app = App()
    app.mainloop()
