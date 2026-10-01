"""Agreement statistics for expert validation (FR-17). Pure functions, no LLM."""

from collections import Counter
from collections.abc import Hashable, Sequence
from typing import Literal

import krippendorff
import numpy as np
from scipy.stats import kendalltau


def kendall_tau_b(order_a: Sequence[str], order_b: Sequence[str]) -> float | None:
    """Kendall tau-b between two rankings of the same items (best first)."""
    common = [x for x in order_a if x in set(order_b)]
    if len(common) < 2:
        return None
    pos_b = {x: i for i, x in enumerate(order_b)}
    tau = kendalltau(range(len(common)), [pos_b[x] for x in common], variant="b").statistic
    return float(tau)


def top_k_overlap(order_a: Sequence[str], order_b: Sequence[str], k: int = 3) -> float | None:
    if not order_a or not order_b:
        return None
    k = min(k, len(order_a), len(order_b))
    return len(set(order_a[:k]) & set(order_b[:k])) / k


def krippendorff_alpha(
    matrix: list[list[float | None]], level: Literal["nominal", "ordinal", "interval", "ratio"] = "ordinal"
) -> float | None:
    """Rows = raters, columns = units; None marks a missing rating."""
    data = np.array([[np.nan if v is None else v for v in row] for row in matrix], dtype=float)
    if data.shape[0] < 2 or np.count_nonzero(~np.isnan(data).all(axis=0)) < 2:
        return None
    try:
        return float(krippendorff.alpha(reliability_data=data, level_of_measurement=level))
    except (ValueError, ZeroDivisionError):
        return None


def cohen_kappa(labels_a: Sequence[Hashable], labels_b: Sequence[Hashable]) -> float | None:
    if len(labels_a) != len(labels_b) or not labels_a:
        raise ValueError("label sequences must be non-empty and of equal length")
    n = len(labels_a)
    p_o = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / n
    ca, cb = Counter(labels_a), Counter(labels_b)
    p_e = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    if p_e == 1.0:
        return None  # both raters used one identical label throughout: kappa undefined
    return (p_o - p_e) / (1 - p_e)


def random_tau_baseline(order: Sequence[str], permutations: int, seed: int) -> dict[str, float | None]:
    """Distribution of tau-b between `order` and random rankings (chance level)."""
    if len(order) < 2:
        return {"mean": None, "p95": None}
    rng = np.random.default_rng(seed)
    taus = []
    for _ in range(permutations):
        perm = list(rng.permutation(list(order)))
        t = kendall_tau_b(order, perm)
        if t is not None:
            taus.append(t)
    return {"mean": float(np.mean(taus)), "p95": float(np.percentile(taus, 95))}
