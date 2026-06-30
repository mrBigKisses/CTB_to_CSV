"""Validate a CSV file against the CTB schema.

Returns a list of ValidationIssue objects. Each issue carries:
- row:        1-based CSV row number (header = 0)
- aci_color:  the ACI color number (1-255) for context
- field:      field name
- value:      the offending value
- message:    human-readable problem description
- suggestion: suggested replacement value (or None)
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from ctb_csv.csv_handler import COLUMNS, _ENCODING

# ── Valid value maps ──────────────────────────────────────────────────────────

LINETYPE_NAMES = {
    0: "use_object", 1: "solid", 2: "dashed", 3: "dotted", 4: "dash_dot",
    5: "short_dash", 6: "medium_dash", 7: "long_dash", 8: "short_dash_x2",
    9: "medium_dash_x2", 10: "long_dash_x2", 11: "medium_long_dash",
    12: "medium_dash_short_dash_x2", 13: "long_dash_short_dash_x2",
    14: "dash_dot_dot", 15: "dash_dot_dot_x2",
    16: "dash_dot_short_dot_x2", 17: "long_dash_dot", 18: "long_dash_dot_x2",
    19: "long_dash_dot_dot", 20: "dash_dot_dot_dot", 21: "dash_dot_dot_dot_x2",
    22: "dash_dot_dot_dot_dot", 23: "short_long_short_dash", 24: "short_long_short_dash_x2",
    25: "short_dash_x3", 26: "long_dash_short_dash", 27: "short_dash_long_dash",
    28: "long_dash_two_short_dash", 29: "very_long_dash", 30: "very_long_dash_dot",
    31: "use_object",
}

FILL_STYLE_NAMES = {
    64: "solid", 65: "checkerboard", 66: "crosshatch", 67: "diamonds",
    68: "horizontal_bars", 69: "slant_left", 70: "slant_right",
    71: "square_dots", 72: "vertical_bars", 73: "use_object",
}

END_STYLE_NAMES = {
    0: "butt", 1: "square", 2: "round", 3: "diamond", 4: "use_object",
}

JOIN_STYLE_NAMES = {
    0: "miter", 1: "bevel", 2: "round", 3: "diamond", 4: "use_object", 5: "use_object",
}

COLOR_POLICY_NAMES = {
    1: "use_object_color", 2: "grayscale", 4: "dithering", 5: "specified_rgb",
}

STANDARD_LINEWEIGHTS = {
    0: 0.0, 1: 0.05, 2: 0.09, 3: 0.1, 4: 0.13, 5: 0.15, 6: 0.18, 7: 0.2,
    8: 0.25, 9: 0.3, 10: 0.35, 11: 0.4, 12: 0.45, 13: 0.5, 14: 0.53,
    15: 0.6, 16: 0.65, 17: 0.7, 18: 0.8, 19: 0.9, 20: 1.0, 21: 1.06,
    22: 1.2, 23: 1.4, 24: 1.58, 25: 2.0, 26: 2.11,
}


# ── Issue type ────────────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    row: int
    aci_color: int | str
    field: str
    value: str
    message: str
    suggestion: str | None = None

    def __str__(self) -> str:
        base = f"Row {self.row} (ACI {self.aci_color}) | {self.field}={self.value!r} — {self.message}"
        if self.suggestion is not None:
            base += f"  →  suggerito: {self.suggestion!r}"
        return base


# ── Internal helpers ──────────────────────────────────────────────────────────

def _int_field(row: dict, col: str, row_num: int, issues: list, lo: int, hi: int, valid_set=None):
    raw = row.get(col, "").strip()
    try:
        v = int(raw)
    except ValueError:
        issues.append(ValidationIssue(
            row=row_num, aci_color=row.get("aci_color", "?"), field=col, value=raw,
            message=f"deve essere un intero",
            suggestion=str(lo),
        ))
        return None
    if not (lo <= v <= hi):
        issues.append(ValidationIssue(
            row=row_num, aci_color=row.get("aci_color", "?"), field=col, value=raw,
            message=f"valore fuori range [{lo}, {hi}]",
            suggestion=str(max(lo, min(hi, v))),
        ))
        return None
    if valid_set is not None and v not in valid_set:
        valid_str = ", ".join(str(k) for k in sorted(valid_set))
        issues.append(ValidationIssue(
            row=row_num, aci_color=row.get("aci_color", "?"), field=col, value=raw,
            message=f"valore non riconosciuto (valori validi: {valid_str})",
        ))
    return v


def _float_field(row: dict, col: str, row_num: int, issues: list, lo: float):
    raw = row.get(col, "").strip()
    try:
        v = float(raw)
    except ValueError:
        issues.append(ValidationIssue(
            row=row_num, aci_color=row.get("aci_color", "?"), field=col, value=raw,
            message="deve essere un numero decimale",
            suggestion=str(lo),
        ))
        return None
    if v < lo:
        issues.append(ValidationIssue(
            row=row_num, aci_color=row.get("aci_color", "?"), field=col, value=raw,
            message=f"deve essere ≥ {lo}",
            suggestion=str(lo),
        ))
    return v


# ── Public API ────────────────────────────────────────────────────────────────

def validate_csv(csv_path: str | Path) -> list[ValidationIssue]:
    """Validate a CSV file. Returns a (possibly empty) list of ValidationIssue."""
    issues: list[ValidationIssue] = []
    path = Path(csv_path)

    if not path.exists():
        issues.append(ValidationIssue(
            row=0, aci_color="—", field="file", value=str(path),
            message="file non trovato",
        ))
        return issues

    with open(path, "r", newline="", encoding=_ENCODING) as f:
        reader = csv.DictReader(f)

        # Check required columns
        if reader.fieldnames is None:
            issues.append(ValidationIssue(
                row=0, aci_color="—", field="header", value="",
                message="file CSV vuoto o senza intestazione",
            ))
            return issues

        missing = [c for c in COLUMNS if c not in reader.fieldnames]
        if missing:
            issues.append(ValidationIssue(
                row=0, aci_color="—", field="header", value=", ".join(missing),
                message="colonne mancanti nel CSV",
            ))

        seen_indices: set[int] = set()
        rows = list(reader)

    if len(rows) != 255:
        issues.append(ValidationIssue(
            row=0, aci_color="—", field="row_count", value=str(len(rows)),
            message=f"il CSV deve avere esattamente 255 righe dati, trovate {len(rows)}",
        ))

    for row_num, row in enumerate(rows, start=2):  # row 1 = header
        aci_raw = row.get("aci_color", "").strip()
        idx_raw = row.get("aci_index", "").strip()

        # aci_index
        try:
            idx = int(idx_raw)
        except ValueError:
            issues.append(ValidationIssue(
                row=row_num, aci_color=aci_raw, field="aci_index", value=idx_raw,
                message="deve essere un intero 0–254",
            ))
            idx = -1

        if 0 <= idx <= 254:
            if idx in seen_indices:
                issues.append(ValidationIssue(
                    row=row_num, aci_color=aci_raw, field="aci_index", value=idx_raw,
                    message=f"aci_index {idx} duplicato",
                ))
            seen_indices.add(idx)
        elif idx != -1:
            issues.append(ValidationIssue(
                row=row_num, aci_color=aci_raw, field="aci_index", value=idx_raw,
                message="deve essere compreso tra 0 e 254",
            ))

        # aci_color coherence
        try:
            aci_color = int(aci_raw)
            if aci_color != idx + 1 and idx != -1:
                issues.append(ValidationIssue(
                    row=row_num, aci_color=aci_raw, field="aci_color", value=aci_raw,
                    message=f"aci_color deve essere aci_index+1 (atteso {idx + 1})",
                    suggestion=str(idx + 1),
                ))
        except ValueError:
            issues.append(ValidationIssue(
                row=row_num, aci_color=aci_raw, field="aci_color", value=aci_raw,
                message="deve essere un intero 1–255",
            ))

        # RGB channels
        for ch in ("color_r", "color_g", "color_b"):
            _int_field(row, ch, row_num, issues, 0, 255)

        # color_flag
        _int_field(row, "color_flag", row_num, issues, 0, 255)

        # color_raw coherence with r/g/b
        try:
            r = int(row.get("color_r", 0))
            g = int(row.get("color_g", 0))
            b = int(row.get("color_b", 0))
            flag = int(row.get("color_flag", 195))
            from ctb_csv.ctb_parser import rgb_to_color
            expected = rgb_to_color(r, g, b, flag)
            actual = int(row.get("color_raw", expected))
            if actual != expected:
                issues.append(ValidationIssue(
                    row=row_num, aci_color=aci_raw, field="color_raw",
                    value=str(actual),
                    message="color_raw non corrisponde a color_r/g/b+color_flag (sarà ricalcolato automaticamente)",
                    suggestion=str(expected),
                ))
        except (ValueError, TypeError):
            pass

        # color_policy
        _int_field(row, "color_policy", row_num, issues, 1, 5, set(COLOR_POLICY_NAMES))

        # screen
        _int_field(row, "screen", row_num, issues, 0, 100)

        # lineweight
        lw = _int_field(row, "lineweight", row_num, issues, 0, 26)
        if lw is not None:
            lw_mm_raw = row.get("lineweight_mm", "").strip()
            try:
                lw_mm = float(lw_mm_raw)
                expected_mm = STANDARD_LINEWEIGHTS.get(lw)
                if expected_mm is not None and abs(lw_mm - expected_mm) > 0.001:
                    issues.append(ValidationIssue(
                        row=row_num, aci_color=aci_raw, field="lineweight_mm",
                        value=lw_mm_raw,
                        message=f"lineweight_mm non corrisponde al peso standard per indice {lw} ({expected_mm} mm)",
                        suggestion=str(expected_mm),
                    ))
            except ValueError:
                pass  # lineweight_mm is informational; skip if blank or bad

        # linetype
        _int_field(row, "linetype", row_num, issues, 0, 31)

        # adaptive_linetype
        al = row.get("adaptive_linetype", "").strip().upper()
        if al not in ("TRUE", "FALSE"):
            issues.append(ValidationIssue(
                row=row_num, aci_color=aci_raw, field="adaptive_linetype", value=al,
                message="deve essere TRUE o FALSE",
                suggestion="TRUE",
            ))

        # linepattern_size
        _float_field(row, "linepattern_size", row_num, issues, lo=0.0)

        # physical_pen_number
        _int_field(row, "physical_pen_number", row_num, issues, 0, 32)

        # virtual_pen_number
        _int_field(row, "virtual_pen_number", row_num, issues, 0, 255)

        # fill_style
        _int_field(row, "fill_style", row_num, issues, 64, 73, set(FILL_STYLE_NAMES))

        # end_style
        _int_field(row, "end_style", row_num, issues, 0, 4, set(END_STYLE_NAMES))

        # join_style
        _int_field(row, "join_style", row_num, issues, 0, 5, set(JOIN_STYLE_NAMES))

    # Check that all 255 indices are present (if no row_count error already)
    if len(rows) == 255:
        all_expected = set(range(255))
        missing_idx = all_expected - seen_indices
        for idx in sorted(missing_idx):
            issues.append(ValidationIssue(
                row=0, aci_color=idx + 1, field="aci_index", value=str(idx),
                message=f"aci_index {idx} (ACI color {idx + 1}) mancante",
            ))

    return issues
