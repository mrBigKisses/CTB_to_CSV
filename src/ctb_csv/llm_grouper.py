"""LLM-based inferential grouping of active CTB pen styles via the Claude API.

Sends active pen data to claude-opus-4-8 and receives structured group
assignments with Italian names and functional descriptions.
Requires: pip install anthropic
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ctb_csv.reporter import Group, PenRow

try:
    import anthropic
    from pydantic import BaseModel
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

_DEFAULT_MODEL = "claude-opus-4-8"


class _PenGroup(BaseModel):
    name: str
    description: str
    aci_colors: list[int]


class _GroupsResponse(BaseModel):
    groups: list[_PenGroup]


def infer_groups(active_rows: list[PenRow], *, model: str = _DEFAULT_MODEL) -> list[Group]:
    """Call the Claude API to infer logical pen groupings from active CTB pens.

    Args:
        active_rows: PenRow objects for all active pens (already built by reporter).
        model:       Claude model ID to use (default: claude-opus-4-8).

    Returns:
        Ordered list of Group objects, as Claude decided.

    Raises:
        ImportError:          if the ``anthropic`` package is not installed.
        anthropic.APIError:   on API-level failures (auth, quota, …).
    """
    if not _HAS_ANTHROPIC:
        raise ImportError(
            "Package 'anthropic' is required for LLM-assisted grouping. "
            "Install with:  pip install anthropic"
        )

    from ctb_csv.reporter import Group  # local import to avoid circular at module load

    # ── Build compact payload ─────────────────────────────────────────────────
    pen_data = []
    for row in active_rows:
        pen_data.append({
            "aci":          row.ps.aci_index + 1,
            "descrizione":  row.ps.description or row.ps.name,
            "stampa_hex":   row.print_hex,
            "spessore_mm":  round(row.mm, 2),
            "retino_pct":   row.ps.screen,
        })

    n = len(pen_data)
    pen_json = json.dumps(pen_data, ensure_ascii=False)

    prompt = f"""Sei un esperto di standard grafici CAD per elaborati tecnici di architettura e ingegneria.
Analizza queste {n} penne attive di un file CTB AutoCAD e raggruppale logicamente per la scheda di riferimento PDF.

PENNE ATTIVE:
{pen_json}

REGOLE DI RAGGRUPPAMENTO:
1. Raggruppa per colore di stampa simile (stampa_hex) — ogni gruppo cromatico porta il nome del colore
2. Le penne con retino_pct < 100 formano il gruppo "Mezzitoni · Screening" — mettile per ultime
3. Se le descrizioni rivelano funzioni distinte (es. "Struttura", "Architettura", "Demolizioni"),
   crea sottogruppi anche dentro lo stesso colore — usa un nome composito (es. "Neri — Struttura")
4. Nomi italiani concisi (1–3 parole); descrizioni funzionali brevi (≤ 12 parole) che spieghino
   il ruolo delle penne nell'elaborato grafico
5. Ordine: neri/scuri prima, poi luminosità crescente, mezzitoni ultimi
6. Ogni penna deve comparire in esattamente un gruppo — includi tutti i {n} valori aci"""

    # ── API call ──────────────────────────────────────────────────────────────
    client = anthropic.Anthropic()

    response = client.messages.parse(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        output_format=_GroupsResponse,
    )

    parsed: _GroupsResponse = response.parsed_output

    # ── Map ACI → PenRow, build Group objects ─────────────────────────────────
    aci_to_row: dict[int, PenRow] = {row.ps.aci_index + 1: row for row in active_rows}
    seen_aci: set[int] = set()
    groups: list[Group] = []

    for llm_group in parsed.groups:
        rows = []
        for aci in llm_group.aci_colors:
            if aci in aci_to_row and aci not in seen_aci:
                rows.append(aci_to_row[aci])
                seen_aci.add(aci)
        if not rows:
            continue
        rows.sort(key=lambda r: r.ps.aci_index)
        groups.append(Group(
            name=llm_group.name,
            description=llm_group.description,
            print_hex=rows[0].print_hex,
            rows=rows,
        ))

    # Safety net: any pens the LLM omitted go into a catch-all group
    missed = sorted(
        [row for row in active_rows if (row.ps.aci_index + 1) not in seen_aci],
        key=lambda r: r.ps.aci_index,
    )
    if missed:
        groups.append(Group(
            name="Altri",
            description="Penne non classificate.",
            print_hex=missed[0].print_hex,
            rows=missed,
        ))

    return groups
