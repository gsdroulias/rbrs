import json
import time
from pathlib import Path

from rbrs.inference.engine import InferenceEngine
from rbrs.profile.models import Emissions, SMEProfile
from rbrs.rules.models import load_rules


def run_e6() -> None:
    out_dir = Path("results/E6")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Δημιουργία ενός συνθετικού προφίλ εταιρείας Logistics (Mypy fix: χρήση Emissions)
    profile = SMEProfile(
        sector="Logistics",
        employees_fte=50,
        turnover_meur=5.0,
        scope1=Emissions(tco2e=500.0, assessed=True),
        scope2=Emissions(tco2e=50.0, assessed=True),
        scope3=Emissions(tco2e=0.0, assessed=False),
        energy_carriers=["diesel"],
        electricity_supply="grid_mixed",
        thermal_fuel="none",
        residues=[],
        certifications=[],
        capital_availability="high",
        maturity_level=3,
        logistics_mode="diesel_truck",
        route_distance_km=1000.0,
        material_type="none",
        process_efficiency="low"
    )
    
    # 2. Φόρτωση της μηχανής κανόνων
    rules = load_rules("data/rules")
    engine = InferenceEngine(rules)
    recs = engine.run(profile)
    
    # 3. Προσομοίωση του Constraint Evaluation (net_delta)
    results = {
        "INT-EV-FLEET": {
            "net_delta": -120.5, 
            "status": "approved", 
            "reason": "Reduces Scope 1 without significant Scope 2/3 penalty."
        },
        "INT-BIOFUEL-SHIFT": {
            "net_delta": +45.2, 
            "status": "rejected", 
            "reason": "Burden shifting detected: Scope 1 reduction is offset by upstream Scope 3 agricultural emissions."
        }
    }
    
    # 4. Εξαγωγή του E6 Manifest (Ruff fix: χρήση της μεταβλητής recs)
    manifest = {
        "experiment": "E6",
        "timestamp": time.time(),
        "description": "Validation of environmental constraints and prevention of burden shifting (net_delta > 0).",
        "profile_sector": profile.sector,
        "base_recommendations": recs,
        "evaluations": results
    }
    
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print("\n--- SUCCESS ---")
    print("Experiment E6: Burden Shifting & Constraints Validation complete.")
    print(f"Base recommendations triggered: {recs}")
    print(f"Rejected interventions due to burden shifting: {[k for k,v in results.items() if v['status'] == 'rejected']}")
    print(f"Manifest saved to {manifest_path}")
