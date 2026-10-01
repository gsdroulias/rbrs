# RBRS research prototype - agent rules
Purpose: reproducible research prototype for a journal paper. Every number in the
paper comes from this code. Correctness and reproducibility outrank features.
Read docs/REQUIREMENTS.md and docs/DESIGN.md before planning any task.

## Architecture (non-negotiable)
- LLM = perception only (package rbrs.extraction). It never scores or ranks.
- rbrs.extraction may import only rbrs.profile. Enforced by import-linter.
- Decision layer (profile, rules, inference, constraints, scoring) is pure and
  deterministic. No network calls, no randomness except seeded experiments.
- SAW is the only scoring model. Absolute thresholds only. Never relative
  max-normalisation.

## Working rules
- Always produce a plan first and wait for approval before editing files.
- Touch only the files named in the task. Ask before creating others.
- Write tests first. Never weaken, skip or delete a test to make it pass; if you
  think a test is wrong, stop and say why.
- Never invent an emission factor, heating value, citation or package name. If a
  value has no source, write SOURCE_NEEDED and tell me.
- Never hardcode numeric factors in Python; they live in data/factors/*.yaml.
- Report numbers only from code you have executed in this session.
- Python 3.12, type hints everywhere, mypy strict, ruff clean, pytest.
- End every answer with: files changed, tests run and result, open assumptions.
