# Drafting a taxonomy

A taxonomy is a set of criteria for judging watches in one category, in layers: the wearer (who it is for), the watch (the object) and optionally the pair.

1. Start from `teddy.py taxonomy resolve <category>`. Never edit a shipped file; `teddy.py taxonomy branch <version_id> --additions <file.json> --reason "<why>"` writes a new `user:` version. Every branch is labelled `provisional`, even from a `compiled` base.
2. Each criterion needs `key`, `statement`, `kind` (must, more_is_better, evidence_settled), `evidence_class` (deductive, research, practitioner, contested), `check` and `sources`.
3. Prefer a deterministic check only when the statement reduces to a comparison over watch spec fields (for example `water_resistance_m >= 100`). Write planted examples: specs that must pass and specs that must fail. `teddy.py taxonomy check <version_id>` runs them. Otherwise use `judged`.
4. Rules use only comparisons, `and`, `or`, `not`, `in`, numbers, strings and booleans. Anything else is rejected. List every field a rule reads in the taxonomy's `spec_fields`, with its meaning and type; that is the contract watch records follow. `teddy.py taxonomy score` compares strings lower-case and marks a rule "not assessable" when a field it reads is missing, null, `unknown` or the wrong type.
5. Record why each addition was made in the branch reason; it goes into `change_log`.

## The additions file

`--additions` takes a JSON object with any of these keys, and no others (`branch` refuses an unknown key):

- `layers`: `{"wearer" | "watch" | "pair": [criterion, …]}`. A criterion whose `key` already exists in that layer replaces it; any other is appended.
- `spec_fields`: `{field: "type: meaning"}`, merged into the base's. Every field a new deterministic rule reads must be listed here or in the base; `branch` and `taxonomy check` refuse a rule that reads an unlisted field.
- `coherence`, `teddy_principles`: lists appended to the base's.
- `paradigm`: a string that replaces the base's.

Example (a dress-watch branch adding an everyday water-resistance rule):

```json
{"layers": {"watch": [
   {"key": "everyday_water_resistance",
    "statement": "Water resistance above the 30 m common on dress watches.",
    "kind": "more_is_better", "evidence_class": "practitioner",
    "check": {"type": "deterministic", "rule": "water_resistance_m >= 50",
              "planted": {"pass": [{"water_resistance_m": 50}], "fail": [{"water_resistance_m": 30}]}},
    "sources": ["https://www.youtube.com/watch?v=<id>&t=210s"]}]},
 "spec_fields": {"water_resistance_m": "number: rated water resistance in metres"},
 "teddy_principles": [{"quote": "…", "video": "<id>", "timestamp": "03:30"}]}
```
6. Quote Teddy's principles with video and timestamp in `teddy_principles`. Any page presenting these criteria carries the commercial context note.
7. A user branch of an old major version shadows a newer shipped version in `teddy.py taxonomy resolve`, because resolve prefers the user's newest branch. When a shipped major version supersedes the user's branch (for example `shipped:dive@3` arrives while the user has `user:dive@2.1`), re-branch from the new shipped version and carry the user's additions across.
8. When an older user branch fails `taxonomy check` (for example a rule reads a field its `spec_fields` does not list), branch the next minor version from it with the fix (`taxonomy branch user:<category>@<n>.<m> --additions …`) rather than editing the old file, which earlier video analyses still cite.
