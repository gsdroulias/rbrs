import typer

from rbrs.experiments.e4 import run_e4
from rbrs.experiments.e5 import run_e5

app = typer.Typer(help="RBRS Research Prototype CLI")

@app.command()
def run(profile: str, weights: str = "default", norm: str = "total_absolute") -> None:
    """Run the decision layer for a specific SME profile."""
    typer.echo(f"Starting run for profile: {profile} | weights={weights} | norm={norm}")
    run_e4(profile, weights, norm)

@app.command(name="run-e5")
def run_e5_cmd() -> None:
    """Run Experiment E5 (Weight Sensitivity)."""
    typer.echo("Starting Experiment E5...")
    run_e5()

if __name__ == "__main__":
    app()
