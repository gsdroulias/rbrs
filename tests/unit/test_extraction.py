import pytest
from unittest.mock import patch, MagicMock
from rbrs.extraction.llm import extract_profile_from_text

@patch("rbrs.extraction.llm.genai.Client")
def test_extract_profile_mocked(MockClient):
    # Δημιουργία εικονικού (mock) LLM για να μην κάνουμε πραγματικά network calls
    mock_instance = MockClient.return_value
    mock_response = MagicMock()
    mock_response.text = '{"sector": "IT", "employees_fte": 10, "turnover_meur": 1.0, "scope1": {"tco2e": 0.0, "assessed": true}, "scope2": {"tco2e": 0.0, "assessed": true}, "scope3": {"tco2e": null, "assessed": false}, "energy_carriers": ["electricity"], "electricity_supply": "grid", "thermal_fuel": null, "residues": [], "certifications": [], "capital_availability": "moderate", "maturity_level": 1, "logistics_mode": "electric_van", "route_distance_km": 10.0, "material_type": "none", "process_efficiency": "high"}'
    mock_instance.models.generate_content.return_value = mock_response

    # Εκτέλεση και επαλήθευση
    profile = extract_profile_from_text("Dummy unstructured text containing SME details.")
    
    assert profile.sector == "IT"
    assert profile.employees_fte == 10
    assert profile.maturity_level == 1
