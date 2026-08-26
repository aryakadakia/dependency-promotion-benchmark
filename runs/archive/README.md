# Archived runs — excluded from analysis

**Superseded (n=1, replaced by n=5 runs of the same scenario and models):**
- `SC-01_20260826T040757Z.json` — llama3.1 + qwen3, superseded by `SC-01_sp-warm_n5_20260826T054043Z.json`
- `SC-03_20260826T035022Z.json` — llama3.1 + qwen3, superseded by `SC-03_sp-warm_n5_20260826T070856Z.json`

**Empty:**
- `SC-03_sp-warm_n5_20260826T074215Z.json` — 0 usable samples; the Google API key was
  rejected on every call. Retained rather than deleted so the failure is on the record.

Kept in `../` despite being n=1, because no n=5 replacement exists or is affordable:
the Gemini runs (`SC-01_20260826T043251Z`, `SC-01_20260826T044911Z`,
`SC-01_sp-neutral_*`, `SC-01_sp-retention_*`). These are excluded from the main
analysis by the `--min-samples` filter and may only be cited as pilot observations.
