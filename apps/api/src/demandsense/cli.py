import hashlib
import json
from pathlib import Path

import typer

from demandsense.pipeline import load_transactions, run_pipeline

app = typer.Typer(help="Retail Demand Forecasting local pipeline")
ROOT = Path(__file__).resolve().parents[4]


@app.command()
def pipeline(
    input: Path = typer.Option(..., exists=True, readable=True, help="Transaction workbook or CSV"),
    output: Path = typer.Option(ROOT / "artifacts"),
    data_mode: str = typer.Option(
        "local transaction data",
        help="Dataset label recorded in the manifest; use 'UCI Online Retail' for the cited UCI source.",
    ),
):
    """Prepare, train, backtest, calibrate, and persist serving artifacts."""
    result = run_pipeline(
        load_transactions(input), output, hashlib.sha256(input.read_bytes()).hexdigest(), data_mode
    )
    typer.echo(json.dumps(result, indent=2))


@app.command()
def inspect(artifacts: Path = typer.Option(ROOT / "artifacts")):
    """Print available run metadata and data quality."""
    for name in ("metadata.json", "quality.json"):
        p = artifacts / name
        typer.echo(f"{name}: {p.read_text() if p.exists() else 'not generated yet'}")


@app.command("build-demo")
def build_demo(
    input: Path = typer.Option(ROOT / "data" / "demo" / "transactions.csv", exists=True),
    output: Path = typer.Option(ROOT / "artifacts" / "demo"),
):
    """Train and evaluate on the explicitly synthetic offline demo fixture."""
    result = run_pipeline(
        load_transactions(input),
        output,
        hashlib.sha256(input.read_bytes()).hexdigest(),
        "synthetic demo fixture (not UCI)",
    )
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
