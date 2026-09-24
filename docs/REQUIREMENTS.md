Purpose

The prototype turns an SME's published sustainability disclosure into an auditable, ranked list of carbon-mitigation interventions, and produces every number, table and figure reported in the paper. Its central architectural claim is that perception is stochastic and decision is deterministic: a large language model extracts facts into a schema and does nothing else; rule evaluation, constraints, scoring and ranking are fully deterministic and traceable.

Stakeholders

Stakeholder	Interest

G. Sdroulias (developer, first author)	A correct, maintainable prototype that produces the paper's results and supports the PhD

A. Karageorgos (supervisor, PI)	Scientific integrity, reproducibility, alignment with AICoSME

Journal reviewers	Ability to verify claims; code and rule base availability

Expert panel	Indirect: their scores are compared with the system's; their data must be protected

AICoSME project	Future integration with the platform's ontology and footprint modules (out of scope now)

Scope

In scope: PDF ingestion via Gemini with provenance and abstention; manual ingestion; typed SME profile; YAML rule base; inference with traces; constraint layer; SAW scoring; experiment harness E1–E11; statistical analysis for E12–E13; synthetic profile generator; packaging for reproduction.

Out of scope: web or graphical user interface; multi-user operation; database back end; AICoSME ontology or knowledge-graph integration (deferred to a follow-up paper); real-time data feeds; production deployment; any LLM involvement in scoring or ranking.

Functional requirements

ID	Requirement

FR-01	Load and validate an SMEProfile from YAML or JSON; reject invalid profiles with clear messages.

FR-02	Extract an SMEProfile from a PDF sustainability report using Gemini with schema-constrained JSON output. Every field is either a typed value with provenance (page, section, verbatim quote) and confidence in \[0,1], or ABSTAINED.

FR-03	Verify every extracted quote and numeric value against the PDF text; flag values that do not appear in the source (hallucination check).

FR-04	Abstain on any field whose confidence falls below a threshold calibrated on a development split; route abstained fields to human confirmation.

FR-05	Provide a manual ingestion mode that produces the same schema, so LLM and analyst ingestion are comparable (E3).

FR-06	Load rules from YAML files (one per module: Scope 1, Scope 2, Scope 3/circularity); validate at load; report rule count, activation frequency and dead rules (rules --stats).

FR-07	Evaluate rules with a working memory and documented conflict resolution; support derived facts; cap cycles; record a complete firing trace per recommendation. Report explicitly whether any rule chain actually occurs.

FR-08	Apply maturity and capital-availability gates to rule eligibility.

FR-09	Constraint layer: (a) energy-substitution net ΔtCO2e for diversions of streams currently used as fuel; (b) biogenic CO2 reported as a separate line excluded from Scope 1; (c) scope-shifting detection; (d) additionality flag for market-based Scope 2 instruments.

FR-10	SAW scoring with configurable weights (default W\_I=0.50, W\_F=0.30, W\_C=0.20) on an absolute discrete scale: I ∈ {0.00, 0.25, 0.50, 0.75, 1.00}; F, C ∈ {0.25, 0.50, 0.75, 1.00}.

FR-11	Two Carbon Impact normalisation modes: scope\_relative (the v7 definition, retained for comparison) and total\_absolute (net abatement as a share of total Scope 1+2; the default). Unassessed target scopes yield an explicit UNQUANTIFIED class, never a substituted value.

FR-12	Deterministic tie-break (higher I, then higher F, then lower cost class), recording for each rank whether score or tie-break decided it.

FR-13	Output the ranked list with criterion scores, FIS, flags, warnings and traces as JSON, CSV and a readable report.

FR-14	Experiment CLI running E1–E11, each writing CSV results, a figure and a run manifest to results/<exp\_id>/.

FR-15	Synthetic profile generator: 17 attributes, plausibility constraints, 27 stratified + 73 random profiles, N=100, seed 42.

FR-16	profile\_coverage() diagnostic listing profile attributes never read by any rule.

FR-17	Statistical analysis for E12 (Krippendorff's alpha, Kendall tau-b, top-3 overlap, author-vs-expert score decomposition) and E13 (Cohen's kappa) from anonymised CSV input. No LLM involvement.

Non-functional requirements

ID	Quality	Requirement

NFR-01	Reproducibility	make reproduce regenerates every result from a fresh clone. Fixed seeds; locked dependencies; manifest with git commit, config hash, seed, model ID, timestamp and token usage.

NFR-02	Determinism	The decision layer (profile → ranking) is a pure function: same inputs, same outputs, always.

NFR-03	Auditability	Every recommendation is traceable to rules, facts and cited factors.

NFR-04	Architectural boundary	The extraction package cannot import inference, constraints or scoring. Enforced mechanically (import-linter) in the test suite.

NFR-05	Testability	Coverage above 85% on inference, constraints, scoring and extraction parsing; property-based tests for scoring invariants.

NFR-06	Offline core	The decision-layer test suite runs with no network; the Gemini client is mockable.

NFR-07	Provenance of data	Every emission factor and heating value lives in versioned YAML with a cited source. Missing sources are flagged, never invented.

NFR-08	Data protection	No personal data (expert responses) is ever sent to an LLM. Expert data is stored anonymised.

NFR-09	Cost control	Token usage logged per call and summed per experiment; budget alert on the API key.

NFR-10	Portability	Runs on Linux, macOS and Windows via uv.

NFR-11	Performance	E5 with 10,000 Dirichlet samples completes in minutes on a laptop.

Constraints (locked decisions — not to be revisited)

•	Knowledge-based rule architecture; no collaborative filtering or learned ranker (cold-start domain).

•	SAW is the only scoring model; no competing formula.

•	Absolute threshold normalisation only; never relative max-normalisation (rank reversal).

•	Mitigation hierarchy Avoid > Reduce > Replace > Offset; scope-shifting blocked.

•	The LLM is confined to perception.

•	"Forward chaining" may be claimed only if chaining is implemented and exercised by the rule base.

Acceptance criteria

ID	Criterion

AC-01	On the manuscript's criterion scores (I,F,C) = (0.50,1.00,1.00), (0.75,0.75,0.50), (0.50,0.75,1.00), (1.00,0.25,0.25), (0.75,0.50,0.50), with W\_F:W\_C held at 3:2, E5 reports that the published order holds only for W\_I in \[0.500, 0.545], that ranks 4 and 5 tie at W\_I = 0.50, and that solar PV becomes top-ranked from W\_I ≈ 0.615. If the code disagrees, stop and investigate before anything else.

AC-02	Under default weights, every FIS is a multiple of 0.025 (property test).

AC-03	Adding a candidate never changes another candidate's score (property test).

AC-04	The ranking is invariant to the order in which candidates are supplied (property test).

AC-05	For the case firm, the constraint layer computes and reports net ΔtCO2e for diverting wood residues from combustion to material use, using only cited factors. The result is not predetermined; the code must report whatever the calculation gives.

AC-06	import-linter passes: extraction cannot import decision-layer modules.

AC-07	Every emission factor in data/factors/\*.yaml has a non-empty source field.

AC-08	No extracted numeric value lacks provenance; every quote is found in the PDF text or flagged.

AC-09	A fresh clone plus make reproduce regenerates all decision-layer results byte-identically.

AC-10	profile\_coverage() reports zero unused attributes, or each unused attribute is documented with a reason.

Traceability to the paper

Requirements	Experiments	Paper section

FR-02 to FR-05	E1, E2, E3	Extraction evaluation; robustness under extraction error

FR-06 to FR-08	E4, E10, E11	Case studies; architectural ablations

FR-09	E7	Constraint-layer demonstration

FR-10 to FR-12	E5, E6, E8, E9	Robustness under weights; normalisation; comparators; diagnostics

FR-15, FR-16	E11	Coverage and robustness

FR-17	E12, E13	Expert validation



