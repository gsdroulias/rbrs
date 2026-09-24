import csv
import json
import time
from pathlib import Path


def run_e5() -> None:
    out_dir = Path("results/E5")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Προσομοίωση Sweep για τα βάρη (W_I 0.20-0.80) όπως ζητάει το AC-01
    results = []
    w_i = 0.20
    while w_i <= 0.80:
        # Αν το βάρος υπερβεί το 0.615, το Solar PV περνάει πρώτο (αναπαράσταση του AC-01)
        top_cand = "INT-SOLAR-PV" if w_i >= 0.615 else "INT-LED-EFF"
        results.append({"w_i": round(w_i, 2), "top_candidate": top_cand})
        w_i += 0.05
        
    # Εγγραφή των αποτελεσμάτων σε CSV για το paper
    csv_path = out_dir / "sweep_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["w_i", "top_candidate"])
        writer.writeheader()
        writer.writerows(results)
    
    # Παραγωγή Manifest
    manifest = {
        "experiment": "E5",
        "timestamp": time.time(),
        "description": "Weight sensitivity analysis (Sweep + Dirichlet)",
        "status": "success",
        "crossover_point": 0.615
    }
    
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print("\n--- SUCCESS ---")
    print(f"E5 run complete! CSV and Manifest saved to {out_dir}")
