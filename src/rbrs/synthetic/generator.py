"""Seeded synthetic SME profiles with plausibility constraints (FR-15)."""

import itertools
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from rbrs.profile.models import Emissions, ResidueStream, SMEProfile


def load_config(path: str | Path = "data/experiments/synthetic.yaml") -> dict[str, Any]:
    cfg: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return cfg


def _log_uniform(rng: np.random.Generator, lo: float, hi: float) -> float:
    return float(round(math.exp(rng.uniform(math.log(lo), math.log(hi))), 2))


def _choice(rng: np.random.Generator, options: list[Any]) -> Any:
    return options[int(rng.integers(len(options)))]


def _profile(rng: np.random.Generator, cfg: dict[str, Any], fixed: dict[str, Any]) -> SMEProfile:
    strata = cfg["strata"]
    maturity = fixed.get("maturity_level", _choice(rng, strata["maturity_level"]))
    capital = fixed.get("capital_availability", _choice(rng, strata["capital_availability"]))
    efficiency = fixed.get("process_efficiency", _choice(rng, strata["process_efficiency"]))

    thermal = _choice(rng, cfg["thermal_fuels"])
    logistics = _choice(rng, cfg["logistics_modes"])
    # Plausibility: market or on-site supply only for firms past the first maturity level.
    supplies = cfg["electricity_supply"] if maturity > 1 else ["grid", "grid_mixed"]
    supply = _choice(rng, supplies)

    residues: list[ResidueStream] = []
    if rng.random() < cfg["p_residues"]:
        material = _choice(rng, cfg["residue_materials"])
        # Plausibility: only combustible residues are burned for energy.
        dispositions = (
            cfg["residue_dispositions"] if material in ("wood", "paper") else ["landfill", "material_recovery"]
        )
        disposition = _choice(rng, dispositions)
        residues.append(
            ResidueStream(
                material=material,
                mass_t=_log_uniform(rng, *cfg["residue_mass_t"]),
                disposition=disposition,
                moisture_content=round(float(rng.uniform(*cfg["residue_moisture"])), 3),
            )
        )

    # Plausibility: carriers follow from the fuels, fleet and residues actually in use.
    carriers = ["electricity"]
    if thermal:
        carriers.append(thermal)
    if logistics == "diesel_truck" and "diesel" not in carriers:
        carriers.append("diesel")
    if any(r.disposition == "energy_recovery" and r.material not in carriers for r in residues):
        carriers.append(residues[0].material)

    scope3_assessed = bool(rng.random() < cfg["p_scope3_assessed"])
    return SMEProfile(
        sector=_choice(rng, cfg["sectors"]),
        employees_fte=int(rng.integers(cfg["employees_fte"][0], cfg["employees_fte"][1] + 1)),
        turnover_meur=None
        if rng.random() < cfg["p_turnover_missing"]
        else round(float(rng.uniform(*cfg["turnover_meur"])), 2),
        scope1=Emissions(tco2e=_log_uniform(rng, *cfg["scope1_tco2e"]), assessed=True),
        scope2=Emissions(tco2e=_log_uniform(rng, *cfg["scope2_tco2e"]), assessed=True),
        scope3=Emissions(
            tco2e=_log_uniform(rng, *cfg["scope3_tco2e"]) if scope3_assessed else None, assessed=scope3_assessed
        ),
        energy_carriers=carriers,
        electricity_supply=supply,
        thermal_fuel=thermal,
        residues=residues,
        certifications=[c for c in cfg["certifications"] if rng.random() < cfg["p_certification"]],
        capital_availability=capital,
        maturity_level=maturity,
        logistics_mode=logistics,
        route_distance_km=None
        if rng.random() < cfg["p_route_missing"]
        else round(float(rng.uniform(*cfg["route_distance_km"])), 1),
        material_type=_choice(rng, cfg["material_types"]),
        process_efficiency=efficiency,
    )


def generate_cohort(cfg: dict[str, Any] | None = None, seed: int | None = None) -> list[tuple[str, SMEProfile]]:
    """27 stratified profiles (one per stratum) followed by random ones, all seeded."""
    cfg = cfg or load_config()
    rng = np.random.default_rng(cfg["seed"] if seed is None else seed)
    strata = cfg["strata"]
    keys = list(strata)
    cohort: list[tuple[str, SMEProfile]] = []
    for combo in itertools.product(*(strata[k] for k in keys)):
        cohort.append((f"SYN-S{len(cohort) + 1:03d}", _profile(rng, cfg, dict(zip(keys, combo, strict=True)))))
    n_strat = len(cohort)
    for i in range(cfg["n_total"] - n_strat):
        cohort.append((f"SYN-R{i + 1:03d}", _profile(rng, cfg, {})))
    return cohort
