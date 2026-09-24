import typer

from rbrs.experiments.e4 import run_e4

app = typer.Typer(help="RBRS Research Prototype CLI")

@app.command()
def run(profile: str, weights: str = "default", norm: str = "total_absolute") -> None:
    """Run the decision layer for a specific SME profile."""
    typer.echo(f"Starting run for profile: {profile} | weights={weights} | norm={norm}")
    run_e4(profile, weights, norm)

if __name__ == "__main__":
    app()
