import typer
from pathlib import Path

def run_e8() -> None:
    out_dir = Path("results/E8")
    out_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Experiment E8 skeleton running. Results will be saved in {out_dir}")
    # TODO: Add specific logic for E8
