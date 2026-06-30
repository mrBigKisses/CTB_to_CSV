"""Export CTBFile → CSV and import CSV → CTBFile."""

import csv
import struct
from pathlib import Path

from ctb_csv.ctb_parser import CTBFile, PlotStyle, color_to_rgb, color_flag, rgb_to_color

# UTF-8 BOM so Excel opens correctly without import wizard
_ENCODING = "utf-8-sig"

# Column order in the CSV
COLUMNS = [
    "aci_index",        # 0–254  (block index in CTB)
    "aci_color",        # 1–255  (ACI color number shown in AutoCAD)
    "name",
    "localized_name",
    "description",
    "color_policy",     # 1=use object, 2=grayscale, 5=specified RGB
    "color_r",          # decoded R channel of the plot color
    "color_g",
    "color_b",
    "color_flag",       # high byte of color int (normally 0xC3 = 195)
    "color_raw",        # raw signed int32 — used for exact round-trip
    "mode_color_raw",   # raw signed int32 for mode_color
    "screen",           # 0–100
    "lineweight",       # index into lineweight table (0–26)
    "lineweight_mm",    # decoded mm value (informational)
    "linetype",         # 0–31  (31 = use object)
    "adaptive_linetype",
    "linepattern_size",
    "physical_pen_number",
    "virtual_pen_number",
    "fill_style",       # 64–73  (73 = use object)
    "end_style",        # 0–4   (4 = use object)
    "join_style",       # 0–5   (5 = use object)
]


def _style_to_row(ps: PlotStyle, lw_table: dict[int, float]) -> dict:
    r, g, b = color_to_rgb(ps.color)
    flag = color_flag(ps.color)
    lw_mm = lw_table.get(ps.lineweight, "")
    return {
        "aci_index":            ps.aci_index,
        "aci_color":            ps.aci_index + 1,
        "name":                 ps.name,
        "localized_name":       ps.localized_name,
        "description":          ps.description,
        "color_policy":         ps.color_policy,
        "color_r":              r,
        "color_g":              g,
        "color_b":              b,
        "color_flag":           flag,
        "color_raw":            ps.color,
        "mode_color_raw":       ps.mode_color,
        "screen":               ps.screen,
        "lineweight":           ps.lineweight,
        "lineweight_mm":        lw_mm,
        "linetype":             ps.linetype,
        "adaptive_linetype":    "TRUE" if ps.adaptive_linetype else "FALSE",
        "linepattern_size":     ps.linepattern_size,
        "physical_pen_number":  ps.physical_pen_number,
        "virtual_pen_number":   ps.virtual_pen_number,
        "fill_style":           ps.fill_style,
        "end_style":            ps.end_style,
        "join_style":           ps.join_style,
    }


def _row_to_style(row: dict, lw_table: dict[int, float]) -> PlotStyle:
    """Reconstruct a PlotStyle from a CSV row.

    If color_r/g/b are modified, rebuilds color_raw from them.
    If color_raw is present and consistent, uses it directly.
    """
    aci_index = int(row["aci_index"])
    flag = int(row.get("color_flag", 195))

    # Rebuild color: prefer color_r/g/b if they were changed
    r = int(row["color_r"])
    g = int(row["color_g"])
    b = int(row["color_b"])
    color_raw = int(row["color_raw"])

    # Verify consistency: if raw disagrees with decoded r/g/b, trust r/g/b
    expected_raw = rgb_to_color(r, g, b, flag)
    if color_raw != expected_raw:
        color_raw = expected_raw

    mode_color_raw = int(row["mode_color_raw"])

    return PlotStyle(
        aci_index=aci_index,
        localized_name=row["localized_name"],
        name=row["name"],
        description=row["description"],
        physical_pen_number=int(row["physical_pen_number"]),
        color=color_raw,
        mode_color=mode_color_raw,
        virtual_pen_number=int(row["virtual_pen_number"]),
        color_policy=int(row["color_policy"]),
        screen=int(row["screen"]),
        linepattern_size=float(row["linepattern_size"]),
        linetype=int(row["linetype"]),
        adaptive_linetype=row["adaptive_linetype"].strip().upper() == "TRUE",
        lineweight=int(row["lineweight"]),
        fill_style=int(row["fill_style"]),
        end_style=int(row["end_style"]),
        join_style=int(row["join_style"]),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def ctb_to_csv(ctb: CTBFile, csv_path: str | Path) -> None:
    """Write all plot styles from a CTBFile to a CSV file."""
    rows = [_style_to_row(ps, ctb.lineweight_table) for ps in ctb.plot_styles]

    with open(csv_path, "w", newline="", encoding=_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def csv_to_ctb(csv_path: str | Path, template_ctb: CTBFile) -> CTBFile:
    """Read a CSV and return a CTBFile ready to be written.

    Global settings and lineweight_table are taken from template_ctb.
    Only plot_styles are replaced with CSV data.
    """
    with open(csv_path, "r", newline="", encoding=_ENCODING) as f:
        reader = csv.DictReader(f)
        styles = [_row_to_style(row, template_ctb.lineweight_table) for row in reader]

    result = CTBFile(
        apply_factor=template_ctb.apply_factor,
        description=template_ctb.description,
        aci_table_available=template_ctb.aci_table_available,
        scale_factor=template_ctb.scale_factor,
        custom_lineweight_display_units=template_ctb.custom_lineweight_display_units,
        plot_styles=styles,
        lineweight_table=template_ctb.lineweight_table,
        _unknown_bytes=template_ctb._unknown_bytes,
    )
    return result
