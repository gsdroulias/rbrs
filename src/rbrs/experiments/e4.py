import json
import time
from pathlib import Path

import yaml

from rbrs.inference.engine import InferenceEngine
from rbrs.profile.models import SMEProfile
from rbrs.rules.models import load_rules
from rbrs.scoring.saw import Candidate, SAWScorer


def run_e4(profile_path: str, weights: str = "default", norm: str = "total_absolute") -> None:
    out_dir = Path("results/E4")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = yaml.safe_load(f)
    profile = SMEProfile(**profile_data)
    
    rules = load_rules("data/rules")
    engine = InferenceEngine(rules)
    recs = engine.run(profile)
    
    # Απλοποιημένο scoring για τη διαδρομή (pipeline)
    scorer = SAWScorer()
    candidates = [Candidate(id=r, impact=0.5, feasibility=0.5, cost_effectiveness=0.5) for r in recs]
    ranked = scorer.rank(candidates)
    
    manifest = {
        "experiment": "E4",
        "timestamp": time.time(),
        "profile": profile_path,
        "weights": weights,
        "norm": norm,
        "recommendations": [r.candidate.id for r in ranked]
    }
    
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print("\n--- SUCCESS ---")
    print(f"E4 run complete! Manifest saved to {manifest_path}")
    print(f"Recommendations found: {[r.candidate.id for r in ranked]}")
