#!/usr/bin/env python3
"""
Assert every structural and method claim the manuscript makes, against the
artifacts. Numbers are covered by check_manuscript.py and sources by
check_citations.py; this covers the prose claims about how the study was run,
which neither of those can see.

    python check_claims.py
"""
import glob, json, pathlib, re, sys, collections
import rubric_v07 as R

ROOT = pathlib.Path(__file__).parent.parent
FAILS = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main():
    scen = [json.loads(pathlib.Path(f).read_text())
            for f in sorted(glob.glob(str(ROOT / "scenarios" / "*.json")))]
    fr = json.loads((ROOT / "runs" / "frame.json").read_text())
    judged = {f: json.loads((ROOT / "runs" / f).read_text()) for f in
              ("judged_v06_local.json", "judged_v06_commercial.json",
               "judged_v07_sonnet.json")}
    rows = [r for v in judged.values() for r in v]
    ms = (ROOT / "paper" / "manuscript.md").read_text()

    # --- scenario set -----------------------------------------------------
    check("15 scenarios", len(scen) == 15, f"{len(scen)}")
    check("every scenario is 13 turns",
          all(len(d["turns"]) == 13 for d in scen),
          str(sorted({len(d["turns"]) for d in scen})))
    check("every scenario ends with a departure turn probing DEP5",
          all("DEP5" in (d["turns"][-1].get("probes") or []) for d in scen),
          str([d["id"] for d in scen
               if "DEP5" not in (d["turns"][-1].get("probes") or [])]))
    prof = collections.Counter((d["profile"], d["arm"]) for d in scen)
    check("Table 3 profile/arm counts: general 8 main 4 control, companion 2 main 1 control",
          prof[("general", "main")] == 8 and prof[("general", "control")] == 4
          and prof[("companion", "main")] == 2 and prof[("companion", "control")] == 1,
          str(dict(prof)))
    check("10 distinct personas",
          len({d["persona"]["id"] for d in scen}) == 10)
    check("every persona carries PHQ-9, GAD-7, loneliness and bond",
          all(all(k in d["persona"] for k in
                  ("phq9", "gad7", "ucla_loneliness", "companion_bond")) for d in scen))
    check("every authored turn carries a probes list",
          all("probes" in t for d in scen for t in d["turns"]))
    check("every scenario declares autofail conditions",
          all(d.get("autofail_conditions") for d in scen))

    # --- rubric -----------------------------------------------------------
    check("16 dimensions", len(R.DIMENSIONS) == 16, str(len(R.DIMENSIONS)))
    check("every dimension is binary (no ordinal levels)",
          all(set(s) >= {"counts", "does_not_count"} and "levels" not in s
              for s in R.DIMENSIONS.values()))
    prov = [d for d, s in R.DIMENSIONS.items() if s.get("provenance")]
    check("exactly 4 dimensions carry a provenance flag", len(prov) == 4, str(prov))
    check("ungated set is DEP3, DEP7, DEP8, PER1",
          R.ALWAYS_LIVE == {"DEP3", "DEP7", "DEP8", "PER1"}, str(sorted(R.ALWAYS_LIVE)))
    check("valence is never shown to a rater",
          all(w not in R.judge_prompt("u", "r", ["DEP1"]) for w in ("harm", "protective",
                                                                    "overcorrection")))
    check("the source field is never shown to a rater",
          "EmoClassifiers" not in R.judge_prompt("u", "r", ["DEP1"]))
    check("DEP5 is live only at departure turns",
          R.live_dims(["DEP5"], False) == [] or "DEP5" not in R.live_dims(["DEP5"], False),
          str(R.live_dims(["DEP5"], False)))
    check("DEP8 is not scored at departure turns",
          "DEP8" not in R.live_dims([], True), str(R.live_dims([], True)))

    # --- generation -------------------------------------------------------
    cells = collections.defaultdict(int)
    for f in sorted(glob.glob(str(ROOT / "runs" / "SC-*_sp-*_n*.json"))):
        d = json.loads(pathlib.Path(f).read_text())
        for m, conds in d["results"].items():
            for cond, blk in conds.items():
                if isinstance(blk, dict):
                    cells[(d["scenario_id"], d["system_prompt_id"], m, cond)] = \
                        max(cells[(d["scenario_id"], d["system_prompt_id"], m, cond)],
                            len(blk.get("samples", [])))
    bad = {k: v for k, v in cells.items() if v != 5}
    check("every generation cell is n = 5", not bad, f"{len(bad)} cells off: {list(bad)[:3]}")
    check("7 models generated",
          len({k[2] for k in cells}) == 7, str(sorted({k[2] for k in cells})))
    check("three prompt levels exist, all three only on SC-03",
          {k[1] for k in cells} == {"neutral", "warm", "retention"}
          and {k[0] for k in cells if k[1] in ("neutral", "retention")} == {"SC-03"},
          str(sorted({k[0] for k in cells if k[1] in ("neutral", "retention")})))

    # --- frame ------------------------------------------------------------
    check("frame is seeded", fr.get("seed") is not None, f"seed={fr.get('seed')}")
    check("frame is built against rubric v07", fr.get("rubric") == "v07")
    check("frame strata are live and background only",
          {t.get("stratum") for t in fr["turns"]} == {"live", "background"})
    check("every flagged frame turn is excluded from human coding",
          all(not t.get("human_code") for t in fr["turns"] if t.get("invalid_reason")))
    check("every frame turn has DEP3, DEP7 and PER1 live (ungated)",
          all({"DEP3", "DEP7", "PER1"} <= set(t.get("live_dims") or [])
              for t in fr["turns"]))
    check("DEP8 is live on every frame turn except departures",
          all(("DEP8" in (t.get("live_dims") or [])) != bool(t.get("is_farewell"))
              for t in fr["turns"]))

    # --- judging ----------------------------------------------------------
    self_scored = [(r["scenario"], r["model"], j) for r in rows
                   for j in r["judges"] if j == r["model"]]
    check("no model scored its own output", not self_scored, str(self_scored[:3]))
    check("judge prompt contains no model identity",
          not re.search(r"claude|gemini|llama|qwen|gemma|mistral",
                        R.judge_prompt("u", "r", ["DEP1"]), re.I))
    check("judge prompt contains no condition or sample index",
          not re.search(r"sp-warm|sp-retention|sample\s*\d", R.judge_prompt("u", "r", ["DEP1"]), re.I))
    check("zero judge failures recorded",
          sum(len(r.get("failures") or []) for r in rows) == 0)
    scored_offgate = [(r["scenario"], r["turn"], d) for r in rows
                      for sc in r["judges"].values() for d in sc
                      if not d.endswith("_init") and d not in R.ALWAYS_LIVE
                      and d not in (r.get("live_dims") or [])
                      and r.get("stratum") == "live"]
    check("gated dimensions were only put to judges where live, on live-stratum turns",
          not scored_offgate, f"{len(scored_offgate)} off-gate scores")

    # --- human coding -----------------------------------------------------
    hum = json.loads((ROOT / "runs" / "handcoded.json").read_text())["scores"]
    meta = {(t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]): t
            for t in fr["turns"]}
    keyed = lambda u: tuple(x if i < 3 else int(x) for i, x in
                            enumerate(u.replace("#recode", "").split("|")))
    check("every coded turn is in the frame",
          all(keyed(u) in meta for u in hum), "")
    check("every blind repeat has a first pass",
          all(u.replace("#recode", "") in hum for u in hum if u.endswith("#recode")))
    # Gated dimensions ARE deliberately asked off-gate, in the background stratum,
    # to estimate the false-positive rate. The claim to check is the count the
    # manuscript reports, not that it is zero.
    first = {u: s for u, s in hum.items() if not u.endswith("#recode")
             and keyed(u) in meta and not meta[keyed(u)].get("invalid_reason")}
    njudge = sum(1 for s in first.values() for d in s if not d.endswith("_init"))
    offgate = sum(1 for u, s in first.items() for d in s
                  if not d.endswith("_init") and d not in R.ALWAYS_LIVE
                  and d not in (meta[keyed(u)].get("live_dims") or []))
    check("human judgement count matches the manuscript (397)", njudge == 397, str(njudge))
    check("off-gate human judgements match the manuscript (120)",
          offgate == 120 and re.search(rf"{offgate} of (the )?{njudge}", ms) is not None,
          f"{offgate} of {njudge}")

    # --- manuscript internal consistency ----------------------------------
    caps = re.findall(r"\*\*Table (\d+)\.", ms)
    check("table captions are numbered 1..N without gaps or repeats",
          [int(x) for x in caps] == list(range(1, len(caps) + 1)), str(caps))
    refs_cited = {int(x) for m in re.findall(r"\[([0-9,\s]+)\]", ms)
                  for x in m.split(",") if x.strip().isdigit()}
    refs_listed = {int(m) for m in re.findall(r"^(\d+)\. [A-Z]", ms, re.M)}
    check("every cited reference number is in the reference list",
          refs_cited <= refs_listed, f"cited-not-listed: {sorted(refs_cited - refs_listed)}")
    check("every listed reference is cited",
          refs_listed <= refs_cited, f"listed-not-cited: {sorted(refs_listed - refs_cited)}")
    secs = re.findall(r"Section (\d+\.\d+)", ms)
    headings = set(re.findall(r"^### (\d+\.\d+)", ms, re.M)) | \
               set(re.findall(r"^## (\d+)\.", ms, re.M))
    missing = {s for s in secs if s not in headings}
    check("every cross-referenced section exists", not missing, str(sorted(missing)))
    check("no placeholder markers remain",
          not re.search(r"⏳|TODO|TBD|XXX|FIXME", ms))

    print(f"\n{len(FAILS)} failing checks" + (f": {FAILS}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
