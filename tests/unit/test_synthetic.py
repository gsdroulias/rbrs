import itertools

from rbrs.synthetic import generate_cohort, load_config
from tests.conftest import REPO


def test_cohort_is_seeded_and_stratified() -> None:
    cfg = load_config(REPO / "data" / "experiments" / "synthetic.yaml")
    cohort = generate_cohort(cfg)
    assert cohort == generate_cohort(cfg)
    assert len(cohort) == 100
    strat = [p for pid, p in cohort if pid.startswith("SYN-S")]
    assert len(strat) == 27
    combos = {(p.maturity_level, p.capital_availability, p.process_efficiency) for p in strat}
    assert combos == set(itertools.product([1, 2, 3], ["low", "moderate", "high"], ["low", "medium", "high"]))
    assert generate_cohort(cfg, seed=7) != cohort


def test_plausibility_constraints() -> None:
    for _, p in generate_cohort(load_config(REPO / "data" / "experiments" / "synthetic.yaml")):
        assert 10 <= p.employees_fte < 250
        if p.thermal_fuel:
            assert p.thermal_fuel in p.energy_carriers
        if p.logistics_mode == "diesel_truck":
            assert "diesel" in p.energy_carriers
        for r in p.residues:
            if r.disposition == "energy_recovery":
                assert r.material in ("wood", "paper")
        if p.maturity_level == 1:
            assert p.electricity_supply in ("grid", "grid_mixed")
