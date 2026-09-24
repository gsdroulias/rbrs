Technology stack

Purpose	Choice

Language and environment	Python 3.12, uv, pyproject.toml + uv.lock

Data models and validation	Pydantic v2

Rules and factors	YAML (PyYAML, loaded into Pydantic models)

LLM access	google-genai SDK, Gemini API with structured output

PDF text for verification	PyMuPDF

Numerics and statistics	NumPy, SciPy (Kendall tau-b, Spearman), pandas; krippendorff package for alpha

Plots	matplotlib

CLI	Typer

Quality	pytest, pytest-cov, Hypothesis, ruff, mypy (strict), import-linter

Layered architecture

Layer	Package	Responsibility

L0	rbrs.extraction	PDF → ExtractionRecord → SMEProfile. Stochastic. May import only rbrs.profile.

L1	rbrs.profile	Typed profile, validation, profile\_coverage()

L2	rbrs.rules	YAML rule loading and validation, statistics

L3	rbrs.inference	Working memory, matching, conflict resolution, traces

L4	rbrs.constraints	Energy substitution, biogenic CO2, scope shifting, additionality

L5	rbrs.scoring	Normalisation modes, SAW, tie-break, ranking

—	rbrs.experiments	E1–E13 harness, manifests, figures

—	rbrs.synthetic	Profile generator

Dependency rule: arrows point downwards only (L5 may use L1–L4; nothing in L1–L5 may import L0). rbrs.extraction depends only on rbrs.profile and the Gemini SDK.

Repository layout

rbrs/

&#x20; GEMINI.md                 # rules for the agent (short!)

&#x20; pyproject.toml  uv.lock  Makefile  README.md  .importlinter

&#x20; docs/  REQUIREMENTS.md  DESIGN.md  AI\_USAGE.md  adr/

&#x20; prompts/  extraction\_v1.md          # versioned prompts

&#x20; data/

&#x20;   rules/  scope1.yaml  scope2.yaml  scope3\_circularity.yaml

&#x20;   factors/  emission\_factors.yaml  heating\_values.yaml

&#x20;   cases/  case\_A.yaml ...           # anonymised profiles

&#x20;   corpus/                            # PDFs (git-ignored)

&#x20;   gold/                              # annotated gold profiles

&#x20; src/rbrs/

&#x20;   profile/  rules/  inference/  constraints/  scoring/

&#x20;   extraction/  experiments/  synthetic/  cli.py

&#x20; tests/  unit/  property/  golden/  architecture/

&#x20; results/                             # git-ignored, regenerated



Core data models (abridged)

class Emissions(BaseModel):

&#x20;   tco2e: float | None

&#x20;   assessed: bool                       # Scope 3 is often False

&#x20;

class ResidueStream(BaseModel):

&#x20;   material: str                        # e.g. "wood residues"

&#x20;   mass\_t: float

&#x20;   disposition: Literal\["landfill", "energy\_recovery", "material\_recovery"]

&#x20;   moisture\_content: float | None       # fraction, needed for LHV

&#x20;

class SMEProfile(BaseModel):

&#x20;   sector: str

&#x20;   employees\_fte: int

&#x20;   turnover\_meur: float | None

&#x20;   scope1: Emissions; scope2: Emissions; scope3: Emissions

&#x20;   energy\_carriers: list\[str]

&#x20;   electricity\_supply: Literal\["grid", "grid\_mixed", "green\_tariff", "onsite"]

&#x20;   thermal\_fuel: str | None

&#x20;   residues: list\[ResidueStream]

&#x20;   certifications: list\[str]

&#x20;   capital\_availability: Literal\["low", "low\_moderate", "moderate", "high"]

&#x20;   maturity\_level: Literal\[1, 2, 3]

&#x20;   # ... remaining attributes to reach the 17 in the protocol

&#x20;

class Provenance(BaseModel):

&#x20;   page: int; section: str | None; quote: str

&#x20;

class ExtractedField(BaseModel):

&#x20;   field: str

&#x20;   value: str | float | int | None

&#x20;   status: Literal\["EXTRACTED", "ABSTAINED"]

&#x20;   confidence: float = Field(ge=0, le=1)

&#x20;   provenance: Provenance | None

&#x20;   verified\_in\_source: bool | None      # set by the deterministic check



Rule format

\- id: S2-001

&#x20; name: High-efficiency equipment and LED retrofit

&#x20; antecedent:

&#x20;   - {field: scope2.tco2e, op: ">", value: 0}

&#x20;   - {field: electricity\_supply, op: in, value: \[grid, grid\_mixed]}

&#x20; maturity\_gate: 1

&#x20; capital\_gate: null

&#x20; consequent: INT-LED-EFF

&#x20; provenance: "<citation or named expert source>"



Key algorithms

Inference. Initialise working memory with profile facts. Repeat: find all eligible rules (antecedent true, gates passed, not yet fired); if none, stop; order by specificity, then priority, then declaration order; fire the first; assert its consequent (an intervention candidate or a derived fact); append to the trace. Stop after a cycle cap and report non-termination. After building the rule base, the test suite must report whether any derived fact ever enables another rule.

Energy substitution (constraint 4a), with every factor read from cited YAML:

E\_lost  \[MJ]    = m\_diverted \[kg] x LHV(moisture) \[MJ/kg]

F\_repl  \[MJ]    = E\_lost / eta\_boiler\_replacement

CO2\_repl \[t]    = F\_repl x EF\_replacement\_fuel \[tCO2/MJ]

CO2\_avoided \[t] = m\_diverted x EF\_displaced\_virgin\_material \[tCO2/t]

net\_delta \[t]   = CO2\_repl - CO2\_avoided        # > 0 means emissions rise



If net\_delta > 0 the candidate is flagged BURDEN\_SHIFTING and its Carbon Impact is set to 0.00. Biogenic CO2 from the residues is reported on a separate line and never added to Scope 1.

Scoring. In total\_absolute mode, share = net abatement / total Scope 1+2; banded to 0.00 (≤ 0), 0.25 (< 5%), 0.50 (5–10%), 0.75 (10–20%), 1.00 (> 20%). FIS = W\_I·I + W\_F·F + W\_C·C. Sort by FIS descending, then the tie-break.

Extraction design

Two passes. Pass 1 (stochastic): send the PDF plus a versioned prompt to Gemini with response\_json\_schema set to the extraction schema, thinking\_level configurable, and media\_resolution medium for PDFs. The prompt instructs the model to quote its source for every value and to abstain rather than infer. The raw response and usage\_metadata are archived. Pass 2 (deterministic): extract the PDF text with PyMuPDF; confirm each quote occurs in the text of the stated page; confirm each numeric value occurs in its quote; apply the abstention threshold; assemble the SMEProfile.

Correction to the earlier Claude Code brief: temperature

The earlier implementation brief asked for temperature 0. Google's Gemini 3 guidance is to keep temperature at the default 1.0, because lower values can cause looping or degraded reasoning. Use the default. Reproducibility then rests on: a pinned model ID; a versioned prompt; schema-constrained output; archived raw responses; and a measured run-to-run stability — run each report three times and report field-level agreement across runs as part of E1. This is more honest than temperature 0 would have been, and reviewers will value it.



from google import genai

from google.genai import types

&#x20;

client = genai.Client()   # reads GEMINI\_API\_KEY from the environment

&#x20;

def call\_gemini(pdf\_bytes: bytes, prompt: str, schema: dict, cfg) -> tuple\[str, dict]:

&#x20;   resp = client.models.generate\_content(

&#x20;       model=cfg.model\_id,                      # pinned in config, e.g. the Pro ID

&#x20;       contents=\[types.Part.from\_bytes(data=pdf\_bytes, mime\_type="application/pdf"),

&#x20;                 prompt],                       # variable part last

&#x20;       config=types.GenerateContentConfig(

&#x20;           response\_mime\_type="application/json",

&#x20;           response\_json\_schema=schema,

&#x20;           thinking\_config=types.ThinkingConfig(thinking\_level=cfg.thinking\_level),

&#x20;       ),

&#x20;   )

&#x20;   u = resp.usage\_metadata

&#x20;   usage = {"prompt": u.prompt\_token\_count, "output": u.candidates\_token\_count,

&#x20;            "thinking": u.thoughts\_token\_count, "cached": u.cached\_content\_token\_count}

&#x20;   return resp.text, usage



Check the parameter names against the current SDK documentation before use; the SDK evolves, and Google also offers a newer Interactions API. The structure above — schema-constrained JSON, configurable thinking, logged usage — is what matters.

Run manifest

Every experiment writes results/<exp\_id>/manifest.json containing the git commit, a hash of all configuration files, the seed, the model ID and thinking level (for extraction runs), the Python and package versions, the start and end timestamps, and summed token usage. A result without a manifest does not go into the paper.



