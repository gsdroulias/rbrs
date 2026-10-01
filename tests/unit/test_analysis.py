import pytest

from rbrs.analysis import cohen_kappa, kendall_tau_b, krippendorff_alpha, random_tau_baseline, top_k_overlap


def test_kendall_tau_b() -> None:
    assert kendall_tau_b(["a", "b", "c"], ["a", "b", "c"]) == pytest.approx(1.0)
    assert kendall_tau_b(["a", "b", "c"], ["c", "b", "a"]) == pytest.approx(-1.0)
    assert kendall_tau_b(["a"], ["a"]) is None


def test_top_k_overlap() -> None:
    assert top_k_overlap(["a", "b", "c", "d"], ["a", "c", "e", "b"]) == pytest.approx(2 / 3)


def test_cohen_kappa_textbook_example() -> None:
    # 50 items: both yes 20, both no 15, a-yes/b-no 5, a-no/b-yes 10 -> kappa = 0.4
    a = ["y"] * 20 + ["n"] * 15 + ["y"] * 5 + ["n"] * 10
    b = ["y"] * 20 + ["n"] * 15 + ["n"] * 5 + ["y"] * 10
    assert cohen_kappa(a, b) == pytest.approx(0.4)
    assert cohen_kappa(["x", "x"], ["x", "x"]) is None


def test_krippendorff_alpha_perfect_and_missing() -> None:
    assert krippendorff_alpha([[1, 2, 3, 4], [1, 2, 3, 4]], "ordinal") == pytest.approx(1.0)
    assert krippendorff_alpha([[1, 2, None, 4], [1, 2, 3, 4]], "ordinal") == pytest.approx(1.0)
    assert krippendorff_alpha([[1, 2, 3]], "ordinal") is None


def test_random_baseline_is_seeded() -> None:
    a = random_tau_baseline(list("abcde"), 500, seed=1)
    assert a == random_tau_baseline(list("abcde"), 500, seed=1)
    assert abs(a["mean"] or 0) < 0.1
