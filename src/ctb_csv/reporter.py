"""Generate an HTML reference sheet of active CTB plot styles, exportable to PDF.

"Active" = any pen that deviates from the AutoCAD default:
  - color_policy != 1  (specific print colour rather than "use object")
  - lineweight != 0    (explicit lineweight)
  - screen != 100      (screening / halftone)

Pens with screen < 100 are collected in a "Mezzitoni · Screening" group;
the rest are clustered by their (R,G,B) print colour.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ezdxf.colors import aci2rgb

from ctb_csv.ctb_parser import CTBFile, PlotStyle, color_to_rgb

# ── Lineweight resolution (1-based: CTB value N → table[N-1]) ────────────────

def _lw_mm(ps: PlotStyle, table: dict[int, float]) -> float:
    key = ps.lineweight - 1 if ps.lineweight > 0 else 0
    return table.get(key, 0.0)


# ── Colour helpers ────────────────────────────────────────────────────────────

# Italian group names for common print colours
_NAMED_COLORS: dict[tuple[int, int, int], tuple[str, str]] = {
    (  0,   0,   0): ("Neri",    "Stampa in nero."),
    (255,   0,   0): ("Rossi",   "Stampa in rosso."),
    (  0, 255,   0): ("Verdi",   "Stampa in verde."),
    (  0,   0, 255): ("Blu",     "Stampa in blu."),
    (255, 255,   0): ("Gialli",  "Stampa in giallo."),
    (  0, 255, 255): ("Ciano",   "Stampa in ciano."),
    (255,   0, 255): ("Magenta", "Stampa in magenta."),
    (255, 255, 255): ("Bianchi", "Stampa in bianco."),
}

_THRESHOLD = 35000  # squared Euclidean distance to accept a "close-enough" match


def _color_group_name(r: int, g: int, b: int) -> tuple[str, str]:
    """Return (Italian group name, brief description) for a print colour."""
    best_dist = float("inf")
    best: tuple[str, str] = (f"#{r:02X}{g:02X}{b:02X}",
                              f"Stampa in #{r:02X}{g:02X}{b:02X}.")
    for ref, names in _NAMED_COLORS.items():
        d = (r - ref[0]) ** 2 + (g - ref[1]) ** 2 + (b - ref[2]) ** 2
        if d < best_dist:
            best_dist = d
            if d < _THRESHOLD:
                best = names
    return best


def _is_ritoccato(print_rgb: tuple[int, int, int], aci_color: int) -> bool:
    """True when the pen's print colour differs from the ACI native colour."""
    native = aci2rgb(aci_color)
    return print_rgb != native


def _line_height_px(mm: float) -> float:
    """Visual thickness in px for the line-preview bar."""
    return max(0.6, mm * 20)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class PenRow:
    ps: PlotStyle
    aci_hex: str          # ACI native colour as #RRGGBB
    print_rgb: tuple[int, int, int]
    print_hex: str        # actual print colour as #RRGGBB
    mm: float             # resolved lineweight in mm
    is_obj: bool          # True when colour_policy == 1 (use object colour)
    is_rit: bool          # True when print ≠ ACI native
    is_screen: bool       # True when screen < 100
    anomaly: str | None   # human-readable anomaly description, or None


@dataclass
class Group:
    name: str
    description: str
    print_hex: str        # representative colour hex for styling
    rows: list[PenRow] = field(default_factory=list)


# ── Active-pen detection & grouping ──────────────────────────────────────────

def _build_pen_row(ps: PlotStyle, lw_table: dict[int, float]) -> PenRow:
    aci_rgb = aci2rgb(ps.aci_index + 1)        # aci_index 0 = ACI colour 1
    aci_hex = "#{:02X}{:02X}{:02X}".format(*aci_rgb)

    is_obj = ps.color_policy == 1
    pr, pg, pb = color_to_rgb(ps.color)
    print_rgb = (pr, pg, pb)
    print_hex = "#{:02X}{:02X}{:02X}".format(pr, pg, pb)

    # For "use object colour" pens the print colour IS the ACI colour
    effective_rgb = aci_rgb if is_obj else print_rgb

    mm = _lw_mm(ps, lw_table)
    is_rit = not is_obj and _is_ritoccato(print_rgb, ps.aci_index + 1)
    is_screen = ps.screen < 100

    return PenRow(
        ps=ps,
        aci_hex=aci_hex,
        print_rgb=effective_rgb,
        print_hex=print_hex if not is_obj else aci_hex,
        mm=mm,
        is_obj=is_obj,
        is_rit=is_rit,
        is_screen=is_screen,
        anomaly=None,
    )


def _is_active(ps: PlotStyle) -> bool:
    return ps.color_policy != 1 or ps.lineweight != 0 or ps.screen != 100


def _is_template_description(desc: str) -> bool:
    return not desc or re.match(r"^Descrizione_\d+$", desc.strip()) is not None


def _build_groups(ctb: CTBFile) -> list[Group]:
    rows = [
        _build_pen_row(ps, ctb.lineweight_table)
        for ps in sorted(ctb.plot_styles, key=lambda p: p.aci_index)
        if _is_active(ps)
    ]

    screening: Group = Group(
        name="Mezzitoni · Screening",
        description="Nero a retino decrescente: campiture e sfondi graduati.",
        print_hex="#000000",
    )
    color_groups: dict[tuple[int, int, int], Group] = {}

    for row in rows:
        if row.is_screen:
            screening.rows.append(row)
        else:
            key = row.print_rgb
            if key not in color_groups:
                name, desc = _color_group_name(*key)
                color_groups[key] = Group(
                    name=name,
                    description=desc,
                    print_hex=row.print_hex,
                )
            color_groups[key].rows.append(row)

    # Sort colour groups: black first, then by hue
    def hue_key(g: Group) -> float:
        r, gr, b = g.rows[0].print_rgb if g.rows else (0, 0, 0)
        if (r, gr, b) == (0, 0, 0):
            return -1.0
        import colorsys
        h, _, _ = colorsys.rgb_to_hsv(r / 255, gr / 255, b / 255)
        return h

    groups = sorted(color_groups.values(), key=hue_key)

    if screening.rows:
        groups.append(screening)

    return [g for g in groups if g.rows]


# ── Anomaly detection ─────────────────────────────────────────────────────────

_WEIGHT_KEYWORDS: dict[str, tuple[float, float]] = {
    "sottilissim": (0.0,  0.07),
    "sottile":     (0.07, 0.15),
    "medio":       (0.15, 0.25),
    "grosso":      (0.22, 0.45),
    "spessore linea": (0.0, 0.01),   # "a spessore linea" = 0.0 mm
}


def _detect_anomaly(row: PenRow) -> str | None:
    desc = row.ps.description.lower()
    mm = row.mm
    for kw, (lo, hi) in _WEIGHT_KEYWORDS.items():
        if kw in desc:
            if not (lo <= mm <= hi):
                return f"descrizione '{kw}' suggerisce {lo:.2f}–{hi:.2f} mm, trovato {mm:.2f} mm"
    return None


# ── HTML rendering ────────────────────────────────────────────────────────────

_CSS = """
:root{
  --ink:#16130f; --ink2:#4a443c; --muted:#9a9285;
  --paper:#faf8f3; --card:#ffffff; --line:#e6e0d4; --line2:#d6cfc0;
  --accent:#b3382c;
  --warn:#b26a00; --warn-bg:#fbf2e2;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Space Grotesk",system-ui,sans-serif;
  line-height:1.45; padding:40px 24px 80px;
}
.sheet{max-width:960px; margin:0 auto}
.head{display:flex; justify-content:space-between; align-items:flex-end;
  gap:24px; padding-bottom:18px; border-bottom:2px solid var(--ink); flex-wrap:wrap}
.brand{font-weight:700; letter-spacing:.34em; font-size:13px; text-transform:uppercase}
.brand b{color:var(--accent)}
.title{font-size:clamp(26px,5vw,42px); font-weight:700; line-height:1.02; margin:.32em 0 .18em}
.file{font-family:"Space Mono",monospace; font-size:12.5px; color:var(--ink2);
  background:#fff; border:1px solid var(--line); padding:3px 8px; border-radius:4px}
.tagline{font-size:12.5px; color:var(--ink2); margin:.35em 0 .5em; max-width:52ch}
.stats{display:flex; gap:0; font-family:"Space Mono",monospace; text-align:right}
.stats div{display:flex; flex-direction:column; padding:0 18px}
.stats div+div{border-left:1px solid var(--line)}
.stats div:last-child{padding-right:0}
.stats .v{font-size:24px; font-weight:700; line-height:1}
.stats .k{font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin-top:4px}
.v.v-warn{color:var(--warn)}
.legend{display:flex; flex-wrap:wrap; gap:18px 26px; margin:20px 0 8px;
  font-size:12.5px; color:var(--ink2); font-family:"Space Mono",monospace}
.legend span{display:inline-flex; align-items:center; gap:7px}
.legend .objl{width:13px; height:13px; border-radius:3px;
  background:repeating-linear-gradient(45deg,#c9c2b4 0 3px,#fff 3px 6px); border:1px solid var(--line2)}
.legend .ritl{background:var(--accent); color:#fff; font-weight:700; font-size:9.5px;
  padding:1px 4px; border-radius:3px; letter-spacing:.05em}
.legend .warnl{background:var(--warn); color:#fff; font-weight:700; font-size:10px;
  padding:1px 5px; border-radius:3px; line-height:1}
.grp{margin-top:34px; break-inside:avoid}
.grp-h{display:grid; grid-template-columns:1fr auto; align-items:baseline;
  border-bottom:1px solid var(--ink); padding-bottom:7px; column-gap:14px}
.grp-h h2{margin:0; font-size:19px; font-weight:700; letter-spacing:.01em; grid-column:1}
.grp-h p{margin:3px 0 0; grid-column:1; font-size:12.5px; color:var(--ink2); max-width:62ch}
.grp-h .count{grid-row:1; grid-column:2; font-family:"Space Mono",monospace;
  font-size:13px; color:var(--muted)}
.grp-h .count::before{content:"× "}
table.pens{width:100%; border-collapse:collapse; margin-top:6px}
.pens thead th{font-family:"Space Mono",monospace; font-size:10px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); text-align:left; font-weight:400;
  padding:8px 10px 6px}
.pens tbody tr{border-top:1px solid var(--line)}
.pens tbody tr:hover{background:#fffdf7}
.pens td{padding:9px 10px; vertical-align:middle}
.c-aci{width:66px} .c-print{width:148px} .c-mm{width:92px} .c-scr{width:104px}
.c-line{width:150px} .c-desc{width:auto}
.c-desc{font-size:14px; font-weight:500; letter-spacing:.005em; color:var(--ink); padding-right:16px}
.chip{display:inline-flex; align-items:center; gap:7px; font-family:"Space Mono",monospace;
  font-weight:700; font-size:14px}
.chip i{width:15px; height:15px; border-radius:50%; border:1px solid rgba(0,0,0,.18); flex:none}
.sw{display:inline-block; width:18px; height:18px; border-radius:4px; vertical-align:middle;
  margin-right:8px; border:1px solid rgba(0,0,0,.14)}
.sw-wb{border-color:var(--line2)}
.obj-sw{background:repeating-linear-gradient(45deg,#c9c2b4 0 3px,#fff 3px 6px);
  border:1px solid var(--line2)}
.hex{font-family:"Space Mono",monospace; font-size:12.5px; letter-spacing:.02em}
.mod{display:inline-block; margin-left:7px; background:var(--accent); color:#fff;
  font-family:"Space Mono",monospace; font-size:9px; font-weight:700; letter-spacing:.06em;
  padding:1px 4px; border-radius:3px; vertical-align:middle}
.c-line{position:relative}
.ln{display:block; width:100%; min-width:60px; border-radius:2px}
.c-mm b{font-family:"Space Mono",monospace; font-size:15px; font-weight:700}
.c-mm .code{display:block; font-family:"Space Mono",monospace; font-size:10px;
  color:var(--muted); margin-top:2px}
.scr{display:flex; align-items:center; gap:8px; font-family:"Space Mono",monospace; font-size:12px}
.scr-bar{width:54px; height:6px; background:#ece6da; border-radius:3px; overflow:hidden}
.scr-bar i{display:block; height:100%; background:var(--ink)}
.muted{color:var(--muted)}
.warn{display:inline-block; margin-top:4px; background:var(--warn); color:#fff;
  font-family:"Space Mono",monospace; font-size:9.5px; font-weight:700; letter-spacing:.03em;
  padding:2px 5px; border-radius:3px; white-space:nowrap}
tr.anom td{background:var(--warn-bg)}
.pens tbody tr.anom:hover td{background:var(--warn-bg)}
tr.anom td.c-aci{box-shadow:inset 3px 0 0 var(--warn)}
.alert{margin:20px 0 4px; border:1px solid var(--warn); background:var(--warn-bg);
  border-radius:8px; padding:15px 18px}
.alert.ok{border-color:#9ab98e; background:#f1f6ed}
.alert-h{font-weight:700; font-size:15px; display:flex; align-items:center; gap:9px}
.alert-badge{background:var(--warn); color:#fff; font-family:"Space Mono",monospace;
  font-size:13px; min-width:24px; height:24px; display:inline-flex; align-items:center;
  justify-content:center; border-radius:6px; padding:0 6px}
.alert-list{list-style:none; margin:12px 0 0; padding:0; display:grid; gap:7px}
.alert-list li{font-size:13px; display:flex; align-items:baseline; gap:8px; flex-wrap:wrap}
.a-aci{font-family:"Space Mono",monospace; font-size:11px; color:var(--muted)}
.a-is{font-family:"Space Mono",monospace; color:var(--warn); font-weight:700}
.a-arrow{font-family:"Space Mono",monospace; font-size:12px}
.a-cls{font-size:11px; color:var(--muted)}
.alert-foot{margin:12px 0 0; font-size:11.5px; color:var(--ink2);
  font-family:"Space Mono",monospace; line-height:1.55}
.foot{margin-top:42px; padding-top:14px; border-top:1px solid var(--line);
  display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap;
  font-family:"Space Mono",monospace; font-size:11px; color:var(--muted)}
@media(max-width:620px){
  body{padding:24px 14px 60px}
  .c-print{width:120px} .hex{display:none}
  .stats{gap:16px} .stats .v{font-size:19px}
}
@media print{
  body{background:#fff; padding:0}
  .pens tbody tr:hover{background:none}
  .grp,.pens tr{break-inside:avoid}
  @page{margin:14mm}
}
"""

_GFONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700'
    '&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">'
)

_E = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")  # noqa: E731


def _pen_row_html(row: PenRow) -> str:
    ps = row.ps
    aci_color = ps.aci_index + 1
    desc = ps.description if not _is_template_description(ps.description) else ps.name

    # ACI chip
    chip = (
        f'<span class="chip" style="--n:{row.aci_hex}">'
        f'<i style="background:{row.aci_hex}"></i>{aci_color}</span>'
    )

    # Print colour cell
    if row.is_obj:
        print_cell = (
            '<span class="sw obj-sw"></span>'
            '<span class="hex">OBJ</span>'
        )
    else:
        sw_border = ' sw-wb' if row.print_hex in ("#FFFFFF", "#FFFFFFFF") else ""
        rit_badge = '<span class="mod" title="colore ritoccato rispetto all\'ACI nativo">RIT</span>' if row.is_rit else ""
        print_cell = (
            f'<span class="sw{sw_border}" style="background:{row.print_hex}"></span>'
            f'<span class="hex">{row.print_hex}</span>{rit_badge}'
        )

    # Line preview
    h = _line_height_px(row.mm)
    line_color = row.print_hex if not row.is_obj else row.aci_hex
    line_cell = f'<span class="ln" style="height:{h:.2f}px;background:{line_color}"></span>'

    # Lineweight cell
    if row.mm == 0.0 and ps.lineweight == 0:
        mm_val = '<b><span class="muted">0.00</span></b>'
    else:
        mm_val = f"<b>{row.mm:.2f}</b>"
    mm_cell = f'{mm_val}<span class="code">idx {ps.lineweight}</span>'

    # Screen cell
    if row.is_screen:
        pct = ps.screen
        scr_cell = (
            f'<span class="scr"><span class="scr-bar">'
            f'<i style="width:{pct}%"></i></span>{pct}%</span>'
        )
    else:
        scr_cell = '<span class="muted">—</span>'

    # Anomaly
    anom_html = ""
    if row.anomaly:
        anom_html = f'<br><span class="warn">≠ {_E(row.anomaly)}</span>'

    tr_class = ' class="anom"' if row.anomaly else ""
    return (
        f"<tr{tr_class}>\n"
        f'      <td class="c-aci">{chip}</td>\n'
        f'      <td class="c-desc">{_E(desc)}{anom_html}</td>\n'
        f'      <td class="c-print">{print_cell}</td>\n'
        f'      <td class="c-line">{line_cell}</td>\n'
        f'      <td class="c-mm">{mm_cell}</td>\n'
        f'      <td class="c-scr">{scr_cell}</td>\n'
        f'    </tr>'
    )


def _group_html(g: Group) -> str:
    rows_html = "\n".join(_pen_row_html(r) for r in g.rows)
    return f"""
  <section class="grp">
      <header class="grp-h">
        <h2>{_E(g.name)}</h2>
        <p>{_E(g.description)}</p>
        <span class="count">{len(g.rows)}</span>
      </header>
      <table class="pens">
        <thead><tr>
          <th class="c-aci">ACI</th><th class="c-desc">Descrizione</th><th class="c-print">Stampa</th>
          <th class="c-line">Tratto</th><th class="c-mm">Spessore</th><th class="c-scr">Retino</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>"""


def _build_html(ctb: CTBFile, source_filename: str = "") -> str:
    groups = _build_groups(ctb)

    # Run anomaly detection
    all_rows: list[PenRow] = [r for g in groups for r in g.rows]
    for row in all_rows:
        row.anomaly = _detect_anomaly(row)
    anomalies = [r for r in all_rows if r.anomaly]

    # Stats
    total_active = len(all_rows)
    non_screen = [r for r in all_rows if not r.is_screen]
    mms = [r.mm for r in non_screen if r.mm > 0]
    lw_range = f"{min(mms):.2f}–{max(mms):.2f}" if mms else "—"
    n_anom = len(anomalies)
    anom_class = "v-warn" if n_anom else ""

    # Anomaly alert box
    if n_anom == 0:
        alert_html = (
            '<div class="alert ok">\n'
            '      <div class="alert-h">Nessuna incoerenza nome ↔ spessore rilevata</div>\n'
            '    </div>'
        )
    else:
        items = "\n".join(
            f'<li><span class="a-aci">ACI {r.ps.aci_index + 1}</span> '
            f'<span class="a-is">{_E(r.anomaly or "")}</span></li>'
            for r in anomalies
        )
        alert_html = (
            f'<div class="alert">\n'
            f'      <div class="alert-h">'
            f'<span class="alert-badge">{n_anom}</span> '
            f'incoerenze nome ↔ spessore</div>\n'
            f'      <ul class="alert-list">{items}</ul>\n'
            f'    </div>'
        )

    # Groups HTML
    groups_html = "".join(_group_html(g) for g in groups)

    filename_label = _E(source_filename or "CTB file")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scheda penne CTB · {_E(source_filename)}</title>
{_GFONTS}
<style>{_CSS}</style>
</head>
<body>
<div class="sheet">

  <div class="head">
    <div>
      <div class="brand">CTB <b>to</b> CSV · scheda penne</div>
      <h1 class="title">Stili di stampa CTB</h1>
      <p class="tagline">Rappresentazione esatta del file, per individuare e correggere le incoerenze.</p>
      <span class="file">{filename_label} · {total_active} stili attivi su 255</span>
    </div>
    <div class="stats">
      <div><span class="v">{len(non_screen)}</span><span class="k">Penne</span></div>
      <div><span class="v">{lw_range}</span><span class="k">Spessori mm</span></div>
      <div><span class="v {anom_class}">{n_anom}</span><span class="k">Anomalie</span></div>
    </div>
  </div>

  <div class="legend">
    <span><i class="objl"></i> <b>OBJ</b> · colore dell'oggetto</span>
    <span><i class="ritl">RIT</i> colore ritoccato vs ACI nativo</span>
    <span><i class="warnl">≠</i> spessore incoerente con la classe</span>
  </div>

  {alert_html}

  {groups_html}

  <div class="foot">
    <span>CTB to CSV · scheda di riferimento penne</span>
    <span>generato il {now}</span>
  </div>

</div>
</body>
</html>"""


# ── PDF export ────────────────────────────────────────────────────────────────

def _export_pdf_weasyprint(html_text: str, pdf_path: Path) -> None:
    import weasyprint  # type: ignore
    weasyprint.HTML(string=html_text).write_pdf(str(pdf_path))


def _open_browser(html_path: Path) -> None:
    webbrowser.open(html_path.as_uri())


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(
    ctb: CTBFile,
    output_path: Path,
    *,
    source_filename: str = "",
    pdf: bool = False,
) -> Path:
    """Generate an HTML (and optionally PDF) report for the given CTBFile.

    Args:
        ctb:             The parsed CTB data.
        output_path:     Where to write the output file (.html or .pdf).
        source_filename: Original filename shown in the report header.
        pdf:             If True, try to export PDF (requires weasyprint).
                         Falls back to HTML + browser if weasyprint is absent.

    Returns:
        The path to the generated file.
    """
    html_text = _build_html(ctb, source_filename=source_filename)

    if pdf:
        try:
            import weasyprint  # noqa: F401
            pdf_path = output_path.with_suffix(".pdf")
            _export_pdf_weasyprint(html_text, pdf_path)
            return pdf_path
        except ImportError:
            pass  # fall through to HTML

    html_path = output_path.with_suffix(".html")
    html_path.write_text(html_text, encoding="utf-8")
    return html_path
