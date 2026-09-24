import pytest
from pydantic import ValidationError
from rbrs.constraints.factors import Factor, load_factors
from rbrs.constraints.logic import calculate_substitution_delta

def test_factor_missing_source_fails():
    with pytest.raises(ValidationError):
        Factor(id="test", value=1.0, unit="kg", source="")
        
def test_factor_missing_source_fails_whitespace():
    with pytest.raises(ValidationError):
        Factor(id="test", value=1.0, unit="kg", source="   ")

def test_calculate_substitution_delta():
    # Δοκιμή με πλαστά νούμερα για επαλήθευση των μαθηματικών
    delta = calculate_substitution_delta(
        m_diverted_kg=1000.0,
        lhv_mj_kg=15.0,
        eta_boiler=0.8,
        ef_replacement_tco2_mj=0.0001,
        ef_displaced_virgin_tco2_kg=0.002
    )
    # E_lost = 1000 * 15 = 15000 MJ
    # F_repl = 15000 / 0.8 = 18750 MJ
    # CO2_repl = 18750 * 0.0001 = 1.875 tCO2
    # CO2_avoided = 1000 * 0.002 = 2.0 tCO2
    # net_delta = 1.875 - 2.0 = -0.125
    assert delta == pytest.approx(-0.125)
