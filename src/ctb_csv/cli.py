"""CLI commands: ctb2csv, csv2ctb, validate."""

import sys
import click
from pathlib import Path

from ctb_csv.ctb_parser import read_ctb, write_ctb
from ctb_csv.csv_handler import ctb_to_csv, csv_to_ctb
from ctb_csv.validator import validate_csv
from ctb_csv.reporter import generate_report


@click.group()
def cli():
    """CTB ↔ CSV conversion toolkit for AutoCAD plot style tables."""


@cli.command("ctb2csv")
@click.argument("ctb_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("csv_file", required=False)
def cmd_ctb2csv(ctb_file: str, csv_file: str | None):
    """Convert a CTB file to CSV.\n\nCSV_FILE defaults to <ctb_file>.csv"""
    ctb_path = Path(ctb_file)
    out_path = Path(csv_file) if csv_file else ctb_path.with_suffix(".csv")

    click.echo(f"Lettura: {ctb_path}")
    ctb = read_ctb(ctb_path)
    click.echo(f"  {len(ctb.plot_styles)} plot styles trovati")

    ctb_to_csv(ctb, out_path)
    click.echo(f"CSV scritto: {out_path}")


@cli.command("csv2ctb")
@click.argument("csv_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("template_ctb", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_ctb", required=False)
@click.option("--skip-validation", is_flag=True, help="Non eseguire la validazione prima della conversione")
def cmd_csv2ctb(csv_file: str, template_ctb: str, output_ctb: str | None, skip_validation: bool):
    """Convert a CSV back to CTB using TEMPLATE_CTB for global settings.\n
    OUTPUT_CTB defaults to <csv_file>.ctb"""
    csv_path = Path(csv_file)
    tmpl_path = Path(template_ctb)
    out_path = Path(output_ctb) if output_ctb else csv_path.with_suffix(".ctb")

    if not skip_validation:
        click.echo("Validazione CSV...")
        issues = validate_csv(csv_path)
        if issues:
            click.echo(f"  ⚠  {len(issues)} problemi trovati:")
            for issue in issues:
                click.echo(f"     {issue}")
            click.echo("Usa --skip-validation per convertire comunque (a tuo rischio).")
            sys.exit(1)
        else:
            click.echo("  ✓  Nessun problema trovato.")

    click.echo(f"Lettura template: {tmpl_path}")
    template = read_ctb(tmpl_path)

    click.echo(f"Lettura CSV: {csv_path}")
    ctb = csv_to_ctb(csv_path, template)

    write_ctb(ctb, out_path)
    click.echo(f"CTB scritto: {out_path}")


@cli.command("validate")
@click.argument("csv_file", type=click.Path(exists=True, dir_okay=False))
def cmd_validate(csv_file: str):
    """Validate a CSV file against the CTB schema."""
    csv_path = Path(csv_file)
    click.echo(f"Validazione: {csv_path}")
    issues = validate_csv(csv_path)

    if not issues:
        click.echo("✓  Nessun problema trovato. Il CSV è valido.")
        sys.exit(0)
    else:
        click.echo(f"⚠  {len(issues)} problemi trovati:\n")
        for issue in issues:
            click.echo(f"  {issue}")
        sys.exit(1)


@cli.command("report")
@click.argument("ctb_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("output", required=False)
@click.option("--pdf", is_flag=True, help="Esporta PDF via weasyprint (richiede: pip install weasyprint)")
def cmd_report(ctb_file: str, output: str | None, pdf: bool):
    """Generate an HTML (or PDF) reference sheet of active plot styles."""
    ctb_path = Path(ctb_file)
    out_base = Path(output) if output else ctb_path.with_suffix(".html")

    click.echo(f"Lettura: {ctb_path}")
    ctb = read_ctb(ctb_path)

    result = generate_report(ctb, out_base, source_filename=ctb_path.name, pdf=pdf)
    click.echo(f"Report scritto: {result}")

    if result.suffix == ".html":
        click.echo("Apri nel browser e usa Stampa → Salva come PDF per esportare in PDF.")


# Allow running as: python -m ctb_csv.cli <command>
if __name__ == "__main__":
    cli()
