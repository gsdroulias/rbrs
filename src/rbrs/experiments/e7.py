from pathlib import Path

import typer


def run_e7() -> None:
    out_dir = Path("results/E7")
    out_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Experiment E7 skeleton running. Results will be saved in {out_dir}")
    # TODO: Add specific logic for E7
