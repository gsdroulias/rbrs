import json
import random
import time
from pathlib import Path


def get_top_candidate(scores: dict[str, float]) -> str:
    best_k = ""
    best_v = -1.0
    for k, v in scores.items():
        if v > best_v:
            best_v = v
            best_k = k
    return best_k

def run_e10(iterations: int = 10000) -> None:
    out_dir = Path("results/E10")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Πίνακας απόδοσης παρεμβάσεων (Κανονικοποιημένος 0-1)
    # Κριτήρια: [ghg (Μείωση Ρύπων), cost (Απόδοση Κόστους), feasibility (Εφικτότητα)]
    candidates = {
        "INT-LED-EFF": {"ghg": 0.3, "cost": 0.9, "feasibility": 0.9},
        "INT-SOLAR-PV": {"ghg": 0.8, "cost": 0.4, "feasibility": 0.6},
        "INT-BIOFUEL-SHIFT": {"ghg": 0.5, "cost": 0.5, "feasibility": 0.5},
        "INT-ROUTE-OPT": {"ghg": 0.6, "cost": 0.7, "feasibility": 0.8}
    }
    
    # Βασικά Βάρη (Baseline Weights)
    base_weights = {"ghg": 0.5, "cost": 0.3, "feasibility": 0.2}
    
    def calc_score(c_data: dict[str, float], w: dict[str, float]) -> float:
        return sum(c_data[k] * w[k] for k in w)
        
    # Υπολογισμός αρχικής, σταθερής βαθμολογίας
    base_scores = {k: calc_score(v, base_weights) for k, v in candidates.items()}
    top_base = get_top_candidate(base_scores)
    
    top_counts: dict[str, int] = {k: 0 for k in candidates}
    
    # Εκτέλεση Monte Carlo Simulation (10.000 επαναλήψεις)
    for _ in range(iterations):
        # Προσθήκη ομοιόμορφου θορύβου [-0.2, 0.2] και επανακανονικοποίηση ώστε το άθροισμα να είναι 1
        w_noisy = {k: max(0.05, v + random.uniform(-0.2, 0.2)) for k, v in base_weights.items()}
        tot = sum(w_noisy.values())
        w_norm = {k: v / tot for k, v in w_noisy.items()}
        
        # Επαναϋπολογισμός βαθμολογίας με τα "μολυσμένα" βάρη
        scores = {k: calc_score(v, w_norm) for k, v in candidates.items()}
        top_counts[get_top_candidate(scores)] += 1
        
    stability = (top_counts[top_base] / iterations) * 100
    
    manifest = {
        "experiment": "E10",
        "timestamp": time.time(),
        "description": "Monte Carlo Sensitivity Analysis on SAW weights to prove ranking robustness.",
        "iterations": iterations,
        "base_weights": base_weights,
        "base_top_candidate": top_base,
        "rank_stability_pct": stability,
        "distribution": top_counts
    }
    
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print("\n--- SUCCESS ---")
    print("Experiment E10: Monte Carlo Stress Test complete.")
    print(f"Iterations: {iterations}")
    print(f"Original Top Candidate: {top_base}")
    print(f"Rank Stability (Top-1 retention): {stability:.1f}%")
    print(f"Manifest saved to {manifest_path}")
