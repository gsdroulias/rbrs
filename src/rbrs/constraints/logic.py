"""Constraint layer (FR-09).

(a) energy substitution: net change when a residue burned for energy is diverted
(b) biogenic CO2 from residue combustion, reported on its own line, never in Scope 1
(c) scope shifting: a reduction in one scope paid for by an increase elsewhere
(d) additionality flag for market-based Scope 2 instruments
"""

from dataclasses import dataclass, field
from typing import Any

from rbrs.constraints.factors import FactorTable
from rbrs.profile.models import SMEProfile
from rbrs.rules.interventions import Intervention

BURDEN_SHIFTING = "BURDEN_SHIFTING"
SCOPE_SHIFT = "SCOPE_SHIFT"
ADDITIONALITY_UNVERIFIED = "ADDITIONALITY_UNVERIFIED"
OFFSET = "OFFSET_LAST_RESORT"

LATENT_HEAT_FACTOR = "latent_heat_vaporisation_water"


def calculate_substitution_delta(
    m_diverted_kg: float,
    lhv_mj_kg: float,
    eta_boiler: float,
    ef_replacement_tco2_mj: float,
    ef_displaced_virgin_tco2_kg: float,
) -> float:
    """Net tCO2 change of diverting a combustible residue to material use.

    > 0 means emissions rise (burden shifting).
    """
    e_lost_mj = m_diverted_kg * lhv_mj_kg
    f_repl_mj = e_lost_mj / eta_boiler
    co2_repl_t = f_repl_mj * ef_replacement_tco2_mj
    co2_avoided_t = m_diverted_kg * ef_displaced_virgin_tco2_kg
    return co2_repl_t - co2_avoided_t


def lhv_at_moisture(lhv_dry_mj_kg: float, moisture: float, latent_heat_mj_kg: float) -> float:
    """As-received net calorific value from the dry-basis value and wet-basis moisture."""
    if not 0.0 <= moisture < 1.0:
        raise ValueError("moisture must be a wet-basis fraction in [0, 1)")
    return lhv_dry_mj_kg * (1.0 - moisture) - latent_heat_mj_kg * moisture


@dataclass
class ConstraintResult:
    intervention_id: str
    # tCO2e change per line; negative = reduction. None = cannot be computed.
    changes_t: dict[str, float | None] = field(default_factory=dict)
    biogenic_co2_t: float | None = None  # separate line, excluded from Scope 1
    flags: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def net_delta_t(self) -> float | None:
        if not self.changes_t or any(v is None for v in self.changes_t.values()):
            return None
        return sum(v for v in self.changes_t.values() if v is not None)

    @property
    def abatement_t(self) -> float | None:
        net = self.net_delta_t
        return None if net is None else -net


def _residue_diversion(iv: Intervention, profile: SMEProfile, factors: FactorTable, res: ConstraintResult) -> None:
    rd = iv.residue_diversion
    assert rd is not None
    streams = [s for s in profile.residues if s.material == rd.material and s.disposition == rd.from_disposition]
    if not streams:
        res.missing.append(f"no {rd.material} stream with disposition {rd.from_disposition}")
        res.changes_t["scope1"] = None
        return
    ids = [rd.displaced_virgin_factor]
    if rd.from_disposition == "energy_recovery":
        ids += [rd.lhv_dry_factor, LATENT_HEAT_FACTOR, rd.boiler_efficiency_factor, rd.replacement_fuel_factor]
        if rd.biogenic_factor:
            ids.append(rd.biogenic_factor)
    absent = factors.missing(ids)
    needs_moisture = rd.from_disposition == "energy_recovery"
    no_moisture = needs_moisture and any(s.moisture_content is None for s in streams)
    if absent or no_moisture:
        res.missing += [f"factor:{m}" for m in absent]
        if no_moisture:
            res.missing.append(f"moisture_content of {rd.material} stream")
        res.changes_t.update({"scope1": None, "avoided_virgin_material": None})
        return
    ef_virgin = factors.get(rd.displaced_virgin_factor, "tCO2/t")
    added = avoided = biogenic = 0.0
    per_stream = []
    for s in streams:
        if rd.from_disposition == "energy_recovery":
            assert s.moisture_content is not None
            lhv = lhv_at_moisture(
                factors.get(rd.lhv_dry_factor, "MJ/kg"),
                s.moisture_content,
                factors.get(LATENT_HEAT_FACTOR, "MJ/kg"),
            )
            e_lost_mj = s.mass_t * 1000.0 * lhv
            fuel_mj = e_lost_mj / factors.get(rd.boiler_efficiency_factor, "fraction")
            co2_repl = fuel_mj * factors.get(rd.replacement_fuel_factor, "tCO2/MJ")
            if rd.biogenic_factor:
                biogenic += e_lost_mj * factors.get(rd.biogenic_factor, "tCO2/MJ")
        else:
            lhv = e_lost_mj = fuel_mj = co2_repl = 0.0
        co2_avoided = s.mass_t * ef_virgin
        added += co2_repl
        avoided += co2_avoided
        per_stream.append(
            {
                "mass_t": s.mass_t,
                "moisture": s.moisture_content,
                "lhv_mj_kg": lhv,
                "energy_lost_mj": e_lost_mj,
                "replacement_fuel_mj": fuel_mj,
                "co2_replacement_t": co2_repl,
                "co2_avoided_t": co2_avoided,
            }
        )
    prior = res.changes_t.get("scope1", 0.0)
    res.changes_t["scope1"] = None if prior is None else prior + added
    res.changes_t["avoided_virgin_material"] = -avoided
    # Combustion that no longer happens: its biogenic CO2 disappears from the separate line.
    res.biogenic_co2_t = -biogenic if rd.biogenic_factor else None
    res.details["energy_substitution"] = per_stream


def evaluate_constraints(iv: Intervention, profile: SMEProfile, factors: FactorTable) -> ConstraintResult:
    res = ConstraintResult(iv.id)
    for eff in iv.effects:
        scope = getattr(profile, eff.scope)
        if not scope.assessed or scope.tco2e is None:
            res.missing.append(f"{eff.scope} not assessed")
            res.changes_t[eff.scope] = None
        elif eff.change_fraction is None:
            res.missing.append(f"effect.{eff.scope} (SOURCE_NEEDED)")
            res.changes_t[eff.scope] = None
        else:
            res.changes_t[eff.scope] = eff.change_fraction * scope.tco2e
    if iv.residue_diversion is not None:
        _residue_diversion(iv, profile, factors, res)
    if not iv.effects and iv.residue_diversion is None:
        res.missing.append(f"no quantified effect declared ({iv.hierarchy} action)")

    known = [v for v in res.changes_t.values() if v is not None]
    if any(v > 0 for v in known) and any(v < 0 for v in known):
        res.flags.append(SCOPE_SHIFT)
    net = res.net_delta_t
    if net is not None and net > 0:
        res.flags.append(BURDEN_SHIFTING)
    if iv.instrument == "market_based":
        res.flags.append(ADDITIONALITY_UNVERIFIED)
    if iv.hierarchy == "offset":
        res.flags.append(OFFSET)
    return res
