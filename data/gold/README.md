# Gold annotations for extraction evaluation (E9)

One YAML file per report, named `<doc_id>.yaml`, mapping field paths to the value
the report states. Use `null` when the report does **not** state the field: the
correct behaviour is then to abstain, and a value counts as unsupported.
Fields left out of the file are not scored.

```yaml
# data/gold/sme_017.yaml
sector: Manufacturing
employees_fte: 45
turnover_meur: null          # not stated in the report
scope1.tco2e: 1234.5
scope2.tco2e: 80
scope3.tco2e: null
residues.0.material: wood
residues.0.mass_t: 120
residues.0.disposition: energy_recovery
```

Recommended protocol (report it in the paper):

1. Two annotators label every report independently; report their agreement
   (Cohen's kappa for categorical fields, exact-match rate for numbers) and
   resolve disagreements before scoring.
2. Split documents before any tuning: `splits.yaml` with `dev: [...]` and
   `test: [...]`. The abstention threshold is calibrated on `dev` only and all
   reported metrics come from `test`.
3. Archive each extraction run with `rbrs extract <pdf> <doc_id>` (three runs per
   report by default) and, for the manual baseline, `rbrs ingest-manual`.

The PDFs themselves stay in `data/corpus/`, which is git-ignored.
