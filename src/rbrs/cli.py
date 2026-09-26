import typer

from rbrs.experiments.e4 import run_e4
from rbrs.experiments.e5 import run_e5
from rbrs.experiments.e6 import run_e6
from rbrs.experiments.e7 import run_e7
from rbrs.experiments.e8 import run_e8
from rbrs.experiments.e9 import run_e9
from rbrs.experiments.e10 import run_e10
from rbrs.experiments.e11 import run_e11

app = typer.Typer(help="RBRS Research Prototype CLI")

@app.command(name="run-e4")
def run_e4_cmd(profile: str, weights: str = "default", norm: str = "total_absolute") -> None:
    """Run the decision layer for a specific SME profile."""
    typer.echo(f"Starting run for profile: {profile} | weights={weights} | norm={norm}")
    run_e4(profile, weights, norm)

@app.command(name="run-e5")
def run_e5_cmd() -> None:
    """Run Experiment E5 (Weight Sensitivity)."""
    typer.echo("Starting Experiment E5...")
    run_e5()

@app.command(name="run-e6")
def run_e6_cmd() -> None:
    """Run Experiment E6 (Burden Shifting & Constraints)."""
    run_e6()

@app.command(name="run-e7")
def run_e7_cmd() -> None:
    """Run Experiment E7 (Forward Chaining Analysis)."""
    run_e7()

@app.command(name="run-e8")
def run_e8_cmd() -> None:
    """Run Experiment E8 (Missing Data Handling)."""
    run_e8()

@app.command(name="run-e9")
def run_e9_cmd() -> None:
    """Run Experiment E9 (LLM Extraction Precision)."""
    run_e9()

@app.command(name="run-e10")
def run_e10_cmd() -> None:
    """Run Experiment E10 (Monte Carlo Stress Test)."""
    run_e10()

@app.command(name="run-e11")
def run_e11_cmd() -> None:
    """Run Experiment E11 (Synthetic Cohort Generation)."""
    run_e11()

if __name__ == "__main__":
    app()
