# Using RBRS as a validation instrument

This note explains how the prototype's outputs map to claims a paper can make,
and what must be supplied before each claim is supported. `rbrs audit` shows
the current state.

## Verification versus validation

| Question | Evidence the prototype produces | Experiment |
|---|---|---|
| Does the code implement the method as specified? (verification) | Unit, property and architecture tests; exact AC-01 check; byte-identical reruns | test suite, E5 |
| Is the decision layer deterministic and traceable? | Pure `recommend()`; rule trace in every report; manifests | E4, AC-09 test |
| Does the constraint layer catch burden shifting? | Net ΔtCO2e from cited factors only | E6 (AC-05) |
| Is chaining real, and does it matter? | Chaining report and single-pass ablation | E7 |
| How robust is the ranking to weights, missing data and input noise? | Exact breakpoints, Dirichlet sampling, perturbation studies | E5, E8, E10 |
| Does the rule base cover the profile space? | Activation frequency, dead rules, unused attributes | E11 |
| Is extraction accurate, and does it know when to abstain? | Precision, recall, abstention accuracy, unsupported-value rate, run-to-run agreement on a held-out test split; LLM vs manual baseline | E9 |
| **Are the recommendations good?** (validation) | Agreement with independent experts, compared with chance and simple baselines | E12, E13 |

Only E12/E13 speak to recommendation quality. E11 (synthetic cohort) shows
coverage and scalability, not correctness, and the paper should say so.

## Findings the paper should reflect (computed by E5 and E7)

- AC-01 holds exactly: the published order is the ranking for
  W_I ∈ [1/2, 6/11) (0.500–0.545; at exactly 6/11 the tie-break reorders ranks 3–4),
  ranks 4 and 5 tie at W_I = 1/2, and solar PV (M4) is top from W_I = 8/13 ≈ 0.615.
- Between W_I = 7/12 ≈ 0.583 and 8/13 the top candidate is M2, not M1 or solar PV.
- Over the whole weight simplex the published order is uncommon: about 1.9% of
  uniform Dirichlet samples and 16% of samples centred on the default weights
  (see `results/E5/dirichlet.json` for the exact values on your run).
- With the active rule base no derived fact enables another rule, so the
  system must not be described as forward-chaining unless the draft rules that
  use derived facts are sourced and activated (REQUIREMENTS, locked constraints).

## Before any number goes into the paper

1. Every intervention reached by an active rule has sourced effect, feasibility
   and cost values (`data/interventions.yaml`).
2. Every factor is `verified_by_author: true`; the `SOURCE_NEEDED` factors are
   supplied (`data/factors/`).
3. The manuscript case firm is in `data/cases/` (AC-05 needs its wood residues).
4. Gold annotations and a dev/test split exist (`data/gold/`), and extraction runs
   are archived with a pinned `model_id` (`config/extraction.yaml`).
5. Expert data is collected and anonymised (`data/expert/`).
6. Commit everything, then `rbrs reproduce`. Only manifests with
   `"publishable": true` (clean tree, status COMPLETED) are reportable.

## Open questions for the author

- **Experiment numbering.** The CLI and README use E6 = constraints,
  E7 = chaining, E8 = missing data, E9 = extraction, E10 = Monte Carlo, while the
  REQUIREMENTS traceability table maps FR-09 to E7 and extraction to E1–E3.
  The code follows the CLI numbering; align the documents with the paper.
- **Impact band boundaries.** DESIGN.md does not say which band 10% and 20%
  fall in; the code uses (5%, 10%] → 0.50 and (10%, 20%] → 0.75
  (`IMPACT_BAND_EDGES` in `scoring/saw.py`). Confirm against the manuscript.
- **scope_relative (v7) definition.** Implemented as net abatement over the
  intervention's first declared target scope. Confirm against v7.
- **Tie-break.** FR-12 says "lower cost class" after F; the code uses higher
  cost-effectiveness C (the same ordering if C is the inverse of cost class),
  then intervention ID as a last resort, and records which criterion decided.
