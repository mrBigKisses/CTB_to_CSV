# CTB_to_CSV

Convert AutoCAD `.ctb` (Color-dependent Plot Style Table) files to CSV for editing in Excel, then back to `.ctb`.

## Features

- **CTB → CSV**: Export all 255 ACI color plot styles to a spreadsheet-friendly CSV
- **CSV → CTB**: Re-import edited CSV back to a valid `.ctb` file
- **Validator**: Check CSV integrity before conversion, with suggested corrections
- **GUI**: Simple drag-and-drop interface (tkinter)

## Requirements

- Python 3.10+
- `ezdxf`, `click`

## Installation

```bash
pip install -e .
```

## Usage

Launch the GUI:

```bash
python -m ctb_csv
```

Or via CLI:

```bash
ctb2csv input.ctb output.csv
csv2ctb input.csv output.ctb
validate input.csv
```

## CSV Format

UTF-8 BOM encoded. One row per ACI color (1–255). Column names match AutoCAD internal field names.
