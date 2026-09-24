def calculate_substitution_delta(
    m_diverted_kg: float,
    lhv_mj_kg: float,
    eta_boiler: float,
    ef_replacement_tco2_mj: float,
    ef_displaced_virgin_tco2_kg: float
) -> float:
    """
    Calculates the net CO2 delta when diverting a combustible residue to material use.
    If the result is > 0, emissions rise (burden shifting occurs).
    """
    e_lost_mj = m_diverted_kg * lhv_mj_kg
    f_repl_mj = e_lost_mj / eta_boiler
    co2_repl_t = f_repl_mj * ef_replacement_tco2_mj
    co2_avoided_t = m_diverted_kg * ef_displaced_virgin_tco2_kg
    
    return co2_repl_t - co2_avoided_t
