"""Shared experiment plumbing: output folders, deterministic writers, run manifests.

DESIGN.md: "A result without a manifest does not go into the paper." Every
experiment writes results/<EXP>/manifest.json with the git commit, whether the
working tree was clean, a hash of every configuration and data file, the seed,
package versions and timestamps. Results from a dirty tree are marked
"publishable": false.
"""

import csv
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml

from rbrs.profile.models import SMEProfile

CONFIG_DIRS = ("data/rules", "data/factors", "data/cases", "data/experiments", "prompts", "config")
CONFIG_FILES = ("data/interventions.yaml", "data/profile_coverage.yaml", "uv.lock")
PACKAGES = (
    "rbrs",
    "pydantic",
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "pyyaml",
    "krippendorff",
    "google-genai",
    "pymupdf",
)
DEFAULT_SEED = 42


class DirtyTreeError(RuntimeError):
    pass


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def git_state() -> dict[str, Any]:
    status = _git("status", "--porcelain", "--", ".", ":(exclude)results")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if status is None else bool(status),
    }


def config_files(root: Path = Path(".")) -> list[Path]:
    files = [root / f for f in CONFIG_FILES if (root / f).is_file()]
    for d in CONFIG_DIRS:
        if (root / d).is_dir():
            files += [p for p in (root / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return sorted(set(files))


def config_hash(root: Path = Path(".")) -> tuple[str, dict[str, str]]:
    per_file: dict[str, str] = {}
    total = hashlib.sha256()
    for f in config_files(root):
        digest = hashlib.sha256(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        rel = f.relative_to(root).as_posix()
        per_file[rel] = digest
        total.update(f"{rel}:{digest}\n".encode())
    return total.hexdigest(), per_file


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = None
    return out


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def write_json(path: Path, obj: Any) -> Path:
    return write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = columns or (list(rows[0]) if rows else [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path


def save_figure(fig: Any, path: Path) -> Path:
    """Save a matplotlib figure without timestamps or software tags, so reruns are identical."""
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return path


def load_profile(path: str | Path) -> SMEProfile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
    return SMEProfile(**data)


def load_cases(cases_dir: str | Path = "data/cases") -> dict[str, SMEProfile]:
    return {p.stem: load_profile(p) for p in sorted(Path(cases_dir).glob("*.yaml"))}


@dataclass
class Run:
    """One experiment run. Use `start_run`, write outputs into `out_dir`, then `finish`."""

    exp_id: str
    out_dir: Path
    seed: int | None
    started: str
    params: dict[str, Any]
    git: dict[str, Any]
    outputs: list[str] = field(default_factory=list)

    def path(self, name: str) -> Path:
        p = self.out_dir / name
        self.outputs.append(p.relative_to(self.out_dir).as_posix())
        return p

    def finish(
        self,
        status: str,
        summary: dict[str, Any],
        model_id: str | None = None,
        token_usage: dict[str, int] | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        """status: "COMPLETED", or "NOT_RUN" / "BLOCKED" with the reason in notes."""
        chash, per_file = config_hash()
        manifest = {
            "experiment": self.exp_id,
            "status": status,
            "publishable": status == "COMPLETED" and self.git.get("git_dirty") is False,
            **self.git,
            "config_hash": chash,
            "config_files": per_file,
            "seed": self.seed,
            "params": self.params,
            "model_id": model_id,
            "token_usage": token_usage,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": package_versions(),
            "started_utc": self.started,
            "finished_utc": datetime.now(UTC).isoformat(),
            "outputs": sorted(set(self.outputs)),
            "summary": summary,
            "notes": notes or [],
        }
        write_json(self.out_dir / "manifest.json", manifest)
        return manifest


def start_run(
    exp_id: str,
    seed: int | None = None,
    params: dict[str, Any] | None = None,
    results_dir: str | Path = "results",
    allow_dirty: bool = True,
) -> Run:
    git = git_state()
    if not allow_dirty and git["git_dirty"]:
        raise DirtyTreeError(
            "uncommitted changes in the working tree; commit them or pass --allow-dirty "
            "(results will then be marked publishable: false)"
        )
    out_dir = Path(results_dir) / exp_id
    if out_dir.exists():
        for old in sorted(out_dir.rglob("*"), reverse=True):  # stale outputs never survive a rerun
            old.unlink() if old.is_file() else old.rmdir()
    out_dir.mkdir(parents=True, exist_ok=True)
    return Run(exp_id, out_dir, seed, datetime.now(UTC).isoformat(), params or {}, git)
