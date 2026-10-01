# Expert validation data (E12, E13)

Only anonymised data belongs here (NFR-08): expert IDs such as `E1`, no names,
e-mail addresses or affiliations. Nothing in this folder is ever sent to an LLM.

## E12: rankings (`e12_rankings.csv`)

One row per expert, case and intervention. `case_id` must match a profile in
`data/cases/<case_id>.yaml`; `intervention_id` must match the catalogue. The
three criterion columns are optional; when present, E12 decomposes disagreement
into "different criterion scores" versus "different aggregation".

```csv
expert_id,case_id,intervention_id,rank,impact,feasibility,cost_effectiveness
E1,case_A,INT-LED-EFF,1,0.50,1.00,1.00
E1,case_A,INT-SOLAR-PV,2,1.00,0.25,0.25
```

Reported: Krippendorff's alpha (ordinal) between experts; Kendall tau-b and top-3
overlap between the system and the expert consensus; tau-b against each expert;
an impact-only baseline; a random baseline (seeded permutations); and a
leave-one-out human ceiling (each expert against the others' consensus).

## E13: categorical judgements (`e13_labels.csv`)

```csv
item_id,rater,label
case_A:INT-LED-EFF,system,accept
case_A:INT-LED-EFF,E1,accept
```

Reported: Cohen's kappa for every pair of raters and Krippendorff's alpha
(nominal) across all raters. Use rater `system` for the prototype's judgement.
