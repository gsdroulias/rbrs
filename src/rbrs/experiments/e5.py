"""E5: weight sensitivity of the SAW ranking (AC-01, NFR-11).

1. Exact one-dimensional sweep: W_I in [0, 1] with W_F:W_C fixed. Every FIS is
   linear in W_I, so rank changes happen only where two lines cross. The
   crossings are computed in exact rational arithmetic, and the order in each
   interval is confirmed with the production SAWScorer.
2. Dirichlet sampling over the whole weight simplex (seeded).
"""

import itertools
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.stats import kendalltau

from rbrs.experiments.common import DEFAULT_SEED, Run, save_figure, start_run, write_csv, write_json
from rbrs.scoring import Candidate, SAWScorer

Triple = tuple[Fraction, Fraction, Fraction]


def _weights_at(w_i: Fraction, ratio: tuple[int, int]) -> Triple:
    f, c = ratio
    rest = 1 - w_i
    return w_i, rest * Fraction(f, f + c), rest * Fraction(c, f + c)


def exact_order(scores: dict[str, Triple], w: Triple) -> list[list[str]]:
    """Rank groups at exact weights: candidates with equal FIS share a group."""
    fis = {k: w[0] * i + w[1] * f + w[2] * c for k, (i, f, c) in scores.items()}
    groups: list[list[str]] = []
    for value in sorted(set(fis.values()), reverse=True):
        groups.append(sorted(k for k in fis if fis[k] == value))
    return groups


def breakpoints(scores: dict[str, Triple], ratio: tuple[int, int]) -> list[Fraction]:
    """W_I values in [0, 1] where two FIS lines cross."""
    pts = {Fraction(0), Fraction(1)}
    for a, b in itertools.combinations(scores, 2):
        # FIS_a(w) - FIS_b(w) = alpha + beta * w
        da0 = sum(x * y for x, y in zip(_weights_at(Fraction(0), ratio), scores[a], strict=True))
        db0 = sum(x * y for x, y in zip(_weights_at(Fraction(0), ratio), scores[b], strict=True))
        da1 = sum(x * y for x, y in zip(_weights_at(Fraction(1), ratio), scores[a], strict=True))
        db1 = sum(x * y for x, y in zip(_weights_at(Fraction(1), ratio), scores[b], strict=True))
        alpha, beta = da0 - db0, (da1 - db1) - (da0 - db0)
        if beta != 0:
            w = Fraction(-alpha) / Fraction(beta)
            if 0 <= w <= 1:
                pts.add(w)
    return sorted(pts)


def scorer_order(scores: dict[str, Triple], w: Triple) -> list[str]:
    scorer = SAWScorer(float(w[0]), float(w[1]), float(w[2]))
    cands = [
        Candidate(id=k, impact=float(i), feasibility=float(f), cost_effectiveness=float(c))
        for k, (i, f, c) in scores.items()
    ]
    return [s.candidate.id for s in scorer.rank(cands)]


def sweep(scores: dict[str, Triple], ratio: tuple[int, int], published: list[str]) -> dict[str, Any]:
    pts = breakpoints(scores, ratio)
    segments: list[dict[str, Any]] = []
    ties: list[dict[str, Any]] = []
    for lo, hi in itertools.pairwise(pts):
        mid = (lo + hi) / 2
        groups = exact_order(scores, _weights_at(mid, ratio))
        assert all(len(g) == 1 for g in groups), "ties can only occur at breakpoints"
        order = [g[0] for g in groups]
        if scorer_order(scores, _weights_at(mid, ratio)) != order:
            raise AssertionError(f"SAWScorer disagrees with exact arithmetic at W_I={float(mid)}")
        segments.append({"w_i_from": lo, "w_i_to": hi, "order": order})
    for p in pts:
        groups = exact_order(scores, _weights_at(p, ratio))
        rank = 1
        for g in groups:
            if len(g) > 1:
                ties.append({"w_i": p, "candidates": g, "ranks": list(range(rank, rank + len(g)))})
            rank += len(g)

    # Merge adjacent segments with the same order (crossings that change nothing).
    merged: list[dict[str, Any]] = []
    for s in segments:
        if merged and merged[-1]["order"] == s["order"]:
            merged[-1]["w_i_to"] = s["w_i_to"]
        else:
            merged.append(dict(s))

    # Published order: the closed interval over which, with the tie-break, it is
    # the ranking. Ties at the boundaries are resolved by the tie-break, so the
    # scorer decides membership of each breakpoint.
    holds = [s for s in merged if s["order"] == published]
    interval = None
    closed: dict[str, bool] = {}
    if holds:
        lo, hi = holds[0]["w_i_from"], holds[-1]["w_i_to"]
        interval = [lo, hi]
        closed = {
            "lower_closed": scorer_order(scores, _weights_at(lo, ratio)) == published,
            "upper_closed": scorer_order(scores, _weights_at(hi, ratio)) == published,
        }
    top = published[0]
    first_top: dict[str, Fraction] = {}
    for s in merged:
        first_top.setdefault(s["order"][0], s["w_i_from"])
    return {
        "breakpoints": pts,
        "segments": merged,
        "ties": ties,
        "published_interval": interval,
        "published_interval_closed": closed,
        "top_from": first_top,
        "published_top": top,
    }


def dirichlet(scores: dict[str, Triple], published: list[str], alpha: list[float], n: int, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    samples = rng.dirichlet(alpha, size=n)
    labels = list(scores)
    top_counts = dict.fromkeys(labels, 0)
    rank_counts = {k: [0] * len(labels) for k in labels}
    same, taus = 0, []
    cands = [
        Candidate(id=k, impact=float(i), feasibility=float(f), cost_effectiveness=float(c))
        for k, (i, f, c) in scores.items()
    ]
    pub_rank = {k: r for r, k in enumerate(published)}
    for w in samples:
        order = [s.candidate.id for s in SAWScorer(float(w[0]), float(w[1]), float(1 - w[0] - w[1])).rank(cands)]
        top_counts[order[0]] += 1
        for r, k in enumerate(order):
            rank_counts[k][r] += 1
        same += order == published
        taus.append(kendalltau([pub_rank[k] for k in order], range(len(order))).statistic)
    return {
        "samples": n,
        "alpha": [float(a) for a in alpha],
        "p_published_order": same / n,
        "p_top": {k: v / n for k, v in top_counts.items()},
        "rank_distribution": {k: [c / n for c in v] for k, v in rank_counts.items()},
        "kendall_tau_vs_published": {
            "mean": float(np.mean(taus)),
            "p05": float(np.percentile(taus, 5)),
            "median": float(np.median(taus)),
        },
    }


def _r3(x: Fraction | None) -> float | None:
    return None if x is None else round(float(x), 3)


def check_ac01(result: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    interval = result["published_interval"]
    tie_ok = any(_r3(t["w_i"]) == spec["tie_at_w_i"] and t["ranks"] == spec["tie_ranks"] for t in result["ties"])
    computed_top_from = result["top_from"].get(spec["top_candidate"])
    checks: dict[str, Any] = {
        "published_order_interval": {
            "expected": spec["published_order_interval"],
            "computed": None if interval is None else [_r3(interval[0]), _r3(interval[1])],
        },
        "tie": {"expected": {"ranks": spec["tie_ranks"], "w_i": spec["tie_at_w_i"]}, "computed": tie_ok},
        "top_from": {"expected": spec["top_from_w_i"], "computed": _r3(computed_top_from)},
    }
    checks["published_order_interval"]["pass"] = (
        checks["published_order_interval"]["computed"] == spec["published_order_interval"]
    )
    checks["tie"]["pass"] = tie_ok
    checks["top_from"]["pass"] = checks["top_from"]["computed"] == spec["top_from_w_i"]
    checks["all_pass"] = all(v["pass"] for v in checks.values() if isinstance(v, dict))
    return checks


def _figure(run: Run, scores: dict[str, Triple], ratio: tuple[int, int], result: dict[str, Any], step: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ws = np.round(np.arange(0.0, 1.0 + step / 2, step), 6)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for k, (i, f, c) in scores.items():
        wf, wc = ratio[0] / sum(ratio), ratio[1] / sum(ratio)
        ax.plot(ws, ws * float(i) + (1 - ws) * (wf * float(f) + wc * float(c)), label=k)
    if result["published_interval"]:
        lo, hi = (float(x) for x in result["published_interval"])
        ax.axvspan(lo, hi, alpha=0.15, color="grey", label="published order holds")
    ax.set_xlabel(f"$W_I$ (with $W_F:W_C$ = {ratio[0]}:{ratio[1]})")
    ax.set_ylabel("FIS")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    save_figure(fig, run.path("fig_e5_sweep.png"))


def run_e5(config: str | Path = "data/experiments/e5.yaml", allow_dirty: bool = True) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    run = start_run("E5", seed=DEFAULT_SEED, params={"config": str(config)}, allow_dirty=allow_dirty)
    scores: dict[str, Triple] = {
        c["label"]: (
            Fraction(str(c["impact"])),
            Fraction(str(c["feasibility"])),
            Fraction(str(c["cost_effectiveness"])),
        )
        for c in cfg["candidates"]
    }
    published = [c["label"] for c in cfg["candidates"]]
    ratio = (int(cfg["fc_ratio"][0]), int(cfg["fc_ratio"][1]))
    result = sweep(scores, ratio, published)
    ac01 = check_ac01(result, cfg["ac01"])

    write_csv(
        run.path("sweep_segments.csv"),
        [
            {
                "w_i_from": round(float(s["w_i_from"]), 6),
                "w_i_to": round(float(s["w_i_to"]), 6),
                "w_i_from_exact": str(s["w_i_from"]),
                "w_i_to_exact": str(s["w_i_to"]),
                "order": ">".join(s["order"]),
                "top": s["order"][0],
            }
            for s in result["segments"]
        ],
    )
    write_csv(
        run.path("sweep_ties.csv"),
        [
            {
                "w_i": round(float(t["w_i"]), 6),
                "w_i_exact": str(t["w_i"]),
                "candidates": "=".join(t["candidates"]),
                "ranks": "-".join(map(str, t["ranks"])),
            }
            for t in result["ties"]
        ],
        columns=["w_i", "w_i_exact", "candidates", "ranks"],
    )
    step = float(cfg["grid_step"])
    grid_rows = []
    for w in np.round(np.arange(0.0, 1.0 + step / 2, step), 6):
        wt = _weights_at(Fraction(str(w)), ratio)
        grid_rows.append({"w_i": float(w), "order": ">".join(scorer_order(scores, wt))})
    write_csv(run.path("sweep_grid.csv"), grid_rows)

    default = cfg["default_weights"]
    dirichlet_out = {}
    for design in cfg["dirichlet"]["designs"]:
        alpha = design.get("alpha") or [design["concentration"] * w for w in default]
        dirichlet_out[design["name"]] = dirichlet(
            scores, published, alpha, int(cfg["dirichlet"]["samples"]), DEFAULT_SEED
        )
    write_json(run.path("dirichlet.json"), dirichlet_out)
    write_json(run.path("ac01_check.json"), ac01)
    _figure(run, scores, ratio, result, step)

    summary = {
        "ac01_all_pass": ac01["all_pass"],
        "published_order_interval": ac01["published_order_interval"]["computed"],
        "published_order_interval_exact": [str(x) for x in result["published_interval"] or []],
        "published_order_interval_endpoints": result["published_interval_closed"],
        "top_from": {k: _r3(v) for k, v in result["top_from"].items()},
        "ties": [{"w_i": _r3(t["w_i"]), "ranks": t["ranks"], "candidates": t["candidates"]} for t in result["ties"]],
        "dirichlet_p_published_order": {k: v["p_published_order"] for k, v in dirichlet_out.items()},
    }
    notes = [] if ac01["all_pass"] else ["AC-01 FAILED: code disagrees with the manuscript; investigate first."]
    run.finish("COMPLETED", summary, notes=notes)
    return summary
