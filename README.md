# RBRS: Rule-Based Reasoning System for SME Decarbonisation

A research prototype that turns an SME's sustainability disclosure into an
auditable, ranked list of carbon-mitigation interventions. Perception is
stochastic and decision is deterministic. A large language model extracts facts
into a schema and does nothing else. Rule evaluation, constraints, scoring and
ranking are pure, traceable functions.

See [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) and [docs/DESIGN.md](docs/DESIGN.md)
for the specification. [docs/VALIDATION.md](docs/VALIDATION.md) explains how the
outputs support claims in a paper.

## Architecture

| Layer | Package | Role |
|---|---|---|
| L0 | `rbrs.extraction` | PDF → Gemini (schema-constrained JSON) → quote and number verification against the PDF text → abstention → profile. May import only `rbrs.profile`. |
| L1 | `rbrs.profile` | Typed `SMEProfile` (17 attributes), extraction records, `profile_coverage()` |
| L2 | `rbrs.rules` | YAML rule base (validated at load) and intervention catalogue |
| L3 | `rbrs.inference` | Forward chaining with working memory, refraction, conflict resolution, cycle cap and a deterministic trace |
| L4 | `rbrs.constraints` | Energy substitution (net ΔtCO2e), biogenic CO2 on its own line, scope shifting, additionality, using cited factors with unit checks |
| L5 | `rbrs.scoring` | Impact banding, `total_absolute` / `scope_relative` normalisation, SAW, tie-break with "decided by" record |
| | `rbrs.pipeline` | `recommend(profile)`: the single decision path every experiment uses |
| | `rbrs.experiments`, `rbrs.analysis`, `rbrs.synthetic` | E4–E13, agreement statistics, seeded cohort |

`import-linter` enforces the layering and keeps the LLM SDK out of the decision layer.

Any number without a source stays `null` and is reported as UNQUANTIFIED,
never substituted. This applies to emission factors, intervention effects and
feasibility or cost scores. Draft rules (`status: draft`) are excluded from paper
runs until they are sourced.

## Current status

`rbrs audit` prints the live state. At the time of writing:

| Experiment | What it does | Status |
|---|---|---|
| E4 | Case-firm runs (JSON, CSV, Markdown report) | Blocked: interventions lack sourced I/F/C data |
| E5 | Weight sensitivity: exact breakpoints and 10,000 Dirichlet samples | **Computed. AC-01 passes** |
| E6 | Constraint layer and burden shifting (AC-05) | Blocked: needs the case firm and 3 sourced factors |
| E7 | Forward chaining and single-pass ablation | Computed: no chaining with active rules |
| E8 | Missing-data handling | Computed |
| E9 | Extraction precision, recall and abstention against gold, dev/test split | Not run: needs gold annotations and archived runs |
| E10 | Monte Carlo stress test of inputs | Computed (candidate sets only until I/F/C are sourced) |
| E11 | Synthetic cohort (27 stratified + 73 random, seed 42): coverage | Computed |
| E12/E13 | Expert agreement: Krippendorff α, Kendall τ-b, top-3, Cohen κ, baselines | Not run: needs expert data |

Results are regenerated, not committed (`results/` is git-ignored). Each run
writes `results/<EXP>/manifest.json` with the git commit, a clean or dirty flag,
the config hash, seed, package versions and token usage. Only manifests with
`"publishable": true` belong in the paper.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run rbrs --help
uv run rbrs run --profile data/cases/case_A.yaml        # one firm, Markdown report
uv run rbrs rules --include-drafts                      # rule stats, dead rules, chaining
uv run rbrs audit                                       # what is still unsourced or blocked
uv run rbrs reproduce                                   # E4–E13 offline (needs a clean git tree)
uv run rbrs reproduce --allow-dirty                     # same, marked not publishable
```

Checks (`make check` runs them all):

```bash
uv run ruff check src tests
uv run mypy
uv run lint-imports
uv run pytest --cov=rbrs
```

### Extraction

```bash
# 1. set a pinned model_id in config/extraction.yaml, and GEMINI_API_KEY in the environment
uv run rbrs extract data/corpus/report.pdf sme_017      # 3 runs, raw responses archived
uv run rbrs assemble data/extractions/sme_017/run1.json --confirm answers.yaml --out data/cases/sme_017.yaml
uv run rbrs run-e9                                      # metrics against data/gold/
```

Fields that are abstained, below the calibrated confidence threshold, or whose
quote or number is not found in the PDF are never filled in automatically.
`assemble` lists them for a person to confirm.

## Repository layout

```
config/extraction.yaml       pinned model, prompt, threshold
prompts/extraction_v2.md     versioned extraction prompt (v1 kept for history)
data/rules/*.yaml            rule base: scope1, scope2, scope3_circularity
data/interventions.yaml      effects, feasibility, cost, each with a source
data/factors/*.yaml          emission factors and constants, each with a source
data/cases/                  case-firm profiles
data/experiments/            experiment configurations (E5, E10, synthetic cohort)
data/gold/, data/expert/     annotation and expert-data formats (see READMEs)
src/rbrs/                    code (see Architecture)
tests/                       unit, property, architecture and experiment tests
```
