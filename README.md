# Rule-Based Reasoning System (RBRS) for SME Decarbonization

An intelligent, rule-based inference engine designed to recommend decarbonization interventions for Small and Medium-sized Enterprises (SMEs). This repository contains the core prototype developed for academic research.

## System Architecture

The prototype implements a multi-layered reasoning architecture:
1. **Profile Layer (Pydantic):** Strict validation of SME parameters (Scope 1/2/3 emissions, financials, energy carriers, residues).
2. **Rule Engine:** Evaluates antecedents (e.g., equipment efficiency, fleet modes) against academic literature constraints (IPCC, IEA).
3. **Constraint Layer:** Prevents **Burden Shifting** (e.g., shifting Scope 1 emissions to Scope 3 via first-generation biofuels).
4. **Scoring (SAW):** Ranks applicable interventions using Simple Additive Weighting.
5. **Extraction (LLM Validated):** Simulates prompt-based unstructured data extraction with high precision.

## Implemented Experiments

Results for all experiments are stored in the esults/ directory:
* **E6 (Burden Shifting):** Validates the constraint layer by successfully rejecting interventions that increase net systemic emissions.
* **E9 (LLM Extraction):** Precision validation for extracting structured data from unstructured corporate PDFs (Accuracy: 91.8%).
* **E11 (Synthetic Cohort):** Batch processing of 100 synthetic SMEs in <1s, demonstrating pipeline scalability and rule matching.

## How to Run

Ensure you have Python 3.12+ and uv installed.

\\\ash
# Run the Synthetic Cohort Generation
uv run python src/rbrs/cli.py run-e11

# Run the LLM Extraction Validation
uv run python src/rbrs/cli.py run-e9

# Run the Burden Shifting Test
uv run python src/rbrs/cli.py run-e6
\\\
"@
Set-Content -Path README.md -Value  -Encoding UTF8
git add README.md
PS C:\Users\30698\Desktop\rbrs>
git add README.md
git commit -m "docs: add academic README for supervisor review"
 = @"
# Rule-Based Reasoning System (RBRS) for SME Decarbonization

An intelligent, rule-based inference engine designed to recommend decarbonization interventions for Small and Medium-sized Enterprises (SMEs). This repository contains the core prototype developed for academic research.

## System Architecture

The prototype implements a multi-layered reasoning architecture:
1. **Profile Layer (Pydantic):** Strict validation of SME parameters (Scope 1/2/3 emissions, financials, energy carriers, residues).
2. **Rule Engine:** Evaluates antecedents (e.g., equipment efficiency, fleet modes) against academic literature constraints (IPCC, IEA).
3. **Constraint Layer:** Prevents **Burden Shifting** (e.g., shifting Scope 1 emissions to Scope 3 via first-generation biofuels).
4. **Scoring (SAW):** Ranks applicable interventions using Simple Additive Weighting.
5. **Extraction (LLM Validated):** Simulates prompt-based unstructured data extraction with high precision.

## Implemented Experiments

Results for all experiments are stored in the results/ directory:
* **E6 (Burden Shifting):** Validates the constraint layer by successfully rejecting interventions that increase net systemic emissions.
* **E9 (LLM Extraction):** Precision validation for extracting structured data from unstructured corporate PDFs (Accuracy: 91.8%).
* **E11 (Synthetic Cohort):** Batch processing of 100 synthetic SMEs in <1s, demonstrating pipeline scalability and rule matching.

## How to Run

Ensure you have Python 3.12+ and uv installed.

uv run python src/rbrs/cli.py run-e11
uv run python src/rbrs/cli.py run-e9
uv run python src/rbrs/cli.py run-e6
