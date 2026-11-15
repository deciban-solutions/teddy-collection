"""Rebuild two_watch_criteria.json from docs/reference/2026-11-14-two-watch.

Usage: python3 tests/fixtures/build_two_watch_criteria.py
Unblinds the three scorers with scoring_keys.json and adds the objective F:*
spec features (both directions; "F:-x" is negated).
"""
import importlib.util
import json
import statistics as st
from pathlib import Path

REF = Path(__file__).resolve().parents[2] / "docs" / "reference" / "2026-11-14-two-watch"
P = ["brit", "adrien", "teddy", "marco", "james", "andrew"]
OCC = {"black_tie": 2, "suit": 20, "biz_casual": 150, "dinner": 40, "weekend": 100,
       "active": 30, "swim": 10, "scuba": 0, "travel": 12}

spec = importlib.util.spec_from_file_location("features", REF / "analysis" / "features.py")
features = importlib.util.module_from_spec(spec)
spec.loader.exec_module(features)

keys = json.loads((REF / "scoring" / "scoring_keys.json").read_text())
D = {}
for s in (1, 2, 3):
    d = json.loads((REF / "scoring" / f"scorer{s}" / "scores.json").read_text())
    pk, wk = keys[f"scorer{s}"], keys[f"scorer{s}_watches"]
    D[s] = {"pairs": {pk[c]: v for c, v in d["pairs"].items()},
            "watches": {wk[c]: v for c, v in d["watches"].items()}}
S3 = (1, 2, 3)
crit = {}
pc = ["differentiation", "coherence_expert", "anchor_strength", "tension_point", "gap_test",
      "wear_balance", "makes_sense_together", "beaten_path", "daily_driver",
      "sensible_spice", "everyday_livability"]
for c in pc:
    crit["S:" + c] = {p: st.mean(D[s]["pairs"][p][c] for s in S3) for p in P}
crit["S:expert_rank(inv)"] = {p: 7 - st.mean(D[s]["pairs"][p]["expert_rank"] for s in S3) for p in P}


def fit(p, s, o):
    w = D[s]["watches"]
    return max(w[p + "_A"]["occasion_fit"][o], w[p + "_B"]["occasion_fit"][o])


crit["C:coverage_weighted"] = {p: st.mean(sum(OCC[o] * fit(p, s, o) for o in OCC) / (2 * sum(OCC.values()))
                                          for s in S3) for p in P}
crit["C:coverage_unweighted"] = {p: st.mean(sum(fit(p, s, o) for o in OCC if o != "scuba") / 16
                                            for s in S3) for p in P}
crit["C:n_occasions_fully_covered"] = {p: st.mean(sum(1 for o in OCC if o != "scuba" and fit(p, s, o) == 2)
                                                  for s in S3) for p in P}
for c in ["robustness", "wearability", "useful_complications", "practicality",
          "horological_merit", "design_integrity", "value"]:
    crit["W:min_" + c] = {p: st.mean(min(D[s]["watches"][p + "_A"][c], D[s]["watches"][p + "_B"][c])
                                     for s in S3) for p in P}
    crit["W:sum_" + c] = {p: st.mean(D[s]["watches"][p + "_A"][c] + D[s]["watches"][p + "_B"][c]
                                     for s in S3) for p in P}


def reg(p, s):
    return D[s]["watches"][p + "_A"]["register"], D[s]["watches"][p + "_B"]["register"]


crit["W:register_gap"] = {p: st.mean(abs(reg(p, s)[0] - reg(p, s)[1]) for s in S3) for p in P}
crit["W:min_register(sportiest)"] = {p: -st.mean(min(reg(p, s)) for s in S3) for p in P}
crit["W:max_register(dressiest)"] = {p: st.mean(max(reg(p, s)) for s in S3) for p in P}
F = {p: features.pair_features(p) for p in P}
for f in F["brit"]:
    crit["F:" + f] = {p: F[p][f] for p in P}
    crit["F:-" + f] = {p: -F[p][f] for p in P}

out = Path(__file__).resolve().parent
(out / "two_watch_criteria.json").write_text(json.dumps(crit, indent=1), encoding="utf-8")
(out / "two_watch_ranking.json").write_text(json.dumps(P), encoding="utf-8")
print(len(crit), "criteria")
