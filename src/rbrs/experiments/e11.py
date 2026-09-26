import json
import time
import random
import csv
from pathlib import Path
from rbrs.profile.models import SMEProfile, Emissions, ResidueStream
from rbrs.rules.models import load_rules
from rbrs.inference.engine import InferenceEngine

def run_e11(num_samples: int = 100) -> None:
    out_dir = Path("results/E11")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    rules = load_rules("data/rules")
    engine = InferenceEngine(rules)
    
    sectors = ["Manufacturing", "Logistics", "Retail", "IT"]
    results = []
    intervention_counts: dict[str, int] = {}
    
    for i in range(num_samples):
        sector = random.choice(sectors)
        has_biomass = random.random() < 0.30
        
        # FIXED: Η διάθεση είναι "energy_recovery" σύμφωνα με το Pydantic Schema
        residues_list = [
            ResidueStream(
                material="biomass", 
                mass_t=50.0, 
                disposition="energy_recovery",
                moisture_content=0.15
            )
        ] if has_biomass else []
        
        profile = SMEProfile(
            sector=sector,
            employees_fte=random.randint(10, 250),
            turnover_meur=random.uniform(1.0, 50.0),
            scope1=Emissions(tco2e=random.uniform(10, 1000), assessed=True),
            scope2=Emissions(tco2e=random.uniform(10, 500), assessed=True),
            scope3=Emissions(tco2e=0.0, assessed=False),
            energy_carriers=["electricity", "diesel"] if sector in ["Manufacturing", "Logistics"] else ["electricity"],
            electricity_supply="grid_mixed",
            thermal_fuel="diesel" if sector == "Manufacturing" else "none",
            residues=residues_list,
            certifications=[],
            capital_availability=random.choice(["low", "moderate", "high"]),
            maturity_level=random.choice([1, 2, 3]),  # type: ignore
            logistics_mode=random.choice(["diesel_truck", "rail", "electric_van"]),  # type: ignore
            route_distance_km=random.uniform(50, 2000),
            material_type="none",
            process_efficiency="medium"
        )
        
        recs = engine.run(profile)
        results.append({
            "id": f"SME-{i:03d}",
            "sector": sector,
            "recommendations": "|".join(recs)
        })
        
        for r in recs:
            intervention_counts[r] = intervention_counts.get(r, 0) + 1
            
    csv_path = out_dir / "cohort_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "sector", "recommendations"])
        writer.writeheader()
        writer.writerows(results)
        
    manifest = {
        "experiment": "E11",
        "timestamp": time.time(),
        "description": "Synthetic Cohort Generation. Now successfully testing constraint-bound biomass shifts.",
        "samples": num_samples,
        "intervention_frequencies": intervention_counts
    }
    
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\n--- SUCCESS ---")
    print(f"Experiment E11: Generated {num_samples} synthetic SMEs.")
    print(f"Intervention frequencies: {intervention_counts}")
