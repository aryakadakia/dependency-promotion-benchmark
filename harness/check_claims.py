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
    check("DEP5 is live at departure turns and only there",
          "DEP5" in R.live_dims(["DEP5"], True)
          and "DEP5" not in R.live_dims(["DEP5"], False),
          f"farewell={R.live_dims(['DEP5'], True)} non={R.live_dims(['DEP5'], False)}")
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

    # --- derived prose claims about the results ---------------------------
    # Regenerate rather than trust what is on disk. Running this checker standalone
    # against a stale figures.json validated the manuscript against numbers that no
    # longer came from the data: a deliberate break in figures.py went undetected
    # because figures.json still held the pre-break values.
    import subprocess as _sp0
    _r = _sp0.run([sys.executable, str(ROOT / "harness" / "figures.py"), "--save"],
                  capture_output=True, text=True, cwd=ROOT / "harness")
    if _r.returncode:
        print("figures.py failed; cannot check:\n" + _r.stderr)
        return 2
    F = json.loads((ROOT / "paper" / "figures.json").read_text())
    jh, per = F["judge_vs_human"], F["per_judge_vs_human"]
    pan, pbd = F["panel_reliability"], F["prevalence_by_dimension"]

    check("panel is 3 open-weight and 3 commercial",
          sum(j.startswith("ollama") for j in per) == 3 and
          sum(not j.startswith("ollama") for j in per) == 3)
    check("no judge reaches the 0.667 threshold against the human coder",
          max(v["ac1"] for v in per.values()) < 0.667,
          f"max {max(v['ac1'] for v in per.values()):.3f}")
    check("judge ordering is monotone in tier (all commercial above all open)",
          min(v["ac1"] for j, v in per.items() if not j.startswith("ollama")) >
          max(v["ac1"] for j, v in per.items() if j.startswith("ollama")))
    spread = max(v["ac1"] for v in per.values()) - min(v["ac1"] for v in per.values())
    check("judge spread is 0.164 as stated", abs(spread - 0.164) < 0.0005, f"{spread:.4f}")
    check("DEP1 and DEP6 are at or below chance against the human coder",
          jh["DEP1"]["ac1"] <= 0 and jh["DEP6"]["ac1"] <= 0)

    gated_bg = [d for d in R.DIMENSIONS
                if "BACKGROUND" in pan.get(d, {}) and "LIVE" in pan[d]]
    up = [d for d in gated_bg if pan[d]["POOLED"]["ac1"] > pan[d]["LIVE"]["ac1"]]
    down = [d for d in gated_bg if pan[d]["POOLED"]["ac1"] < pan[d]["LIVE"]["ac1"]]
    check("pooling raises AC1 on 8 of 10 gated dimensions and lowers it on 2 (PRO4, OVR1)",
          len(gated_bg) == 10 and len(up) == 8 and set(down) == {"PRO4", "OVR1"},
          f"{len(gated_bg)} gated, up={len(up)}, down={down}")
    rise = max(pan[d]["POOLED"]["ac1"] - pan[d]["LIVE"]["ac1"] for d in gated_bg)
    check("largest pooling inflation is 0.124 on PER3", abs(rise - 0.124) < 0.001, f"{rise:.4f}")

    pairs = F["pairwise_judge_ac1"]
    top2 = sorted(pairs.items(), key=lambda x: -x[1])[:2]
    check("the two highest-agreeing judge pairs are both cross-vendor",
          all(len({p.split(":")[0] for p in k.split("|")}) == 2 or
              ("gemma" in k and "qwen" in k) or ("sonnet" in k and "gemini" in k)
              for k, _ in top2), str([k for k, _ in top2]))
    lla = [v for k, v in pairs.items() if "llama3.1:8b" in k]
    others = [v for k, v in pairs.items() if "llama3.1:8b" not in k]
    low5 = [k for k, _ in sorted(pairs.items(), key=lambda x: x[1])[:5]]
    check("llama occupies four of the five lowest-agreeing pairs",
          sum("llama3.1:8b" in k for k in low5) == 4, str(low5))

    check("OVR1 and OVR4 are at 0% prevalence on the frame, OVR3 at 14.3%",
          pbd["OVR1"]["prevalence"] == 0 and pbd["OVR4"]["prevalence"] == 0
          and abs(pbd["OVR3"]["prevalence"] - 0.1429) < 0.001)
    top6 = sorted(pbd.items(), key=lambda x: -x[1]["prevalence"])[:6]
    contested = set(F["contested_dimensions"])
    check("two of the six highest prevalences are contested dimensions (DEP2, DEP6)",
          {d for d, _ in top6} & contested == {"DEP2", "DEP6"},
          str(sorted({d for d, _ in top6} & contested)))
    check("the four dimensions named in 5.5 as exceeding 0.80 all do",
          all(jh[d]["ac1"] > 0.80 for d in ("DEP4", "DEP8", "PRO2", "PRO4")),
          str({d: round(jh[d]["ac1"], 3) for d in ("DEP4", "DEP8", "PRO2", "PRO4")}))
    check("extreme-prevalence dimensions number 7 and mid-prevalence 5",
          F["n_dimensions_extreme"] == 7 and F["n_dimensions_mid"] == 5)
    check("33 of 39 contested disagreements run human-present",
          F["contested_disagreements_human_present"] == 33
          and F["contested_disagreements_total"] == 39)

    cal = F["calibration"]["ALL"]
    check("calibration change is +0.025 on 46 baseline and 54 calibrated judgements",
          abs(cal["change"] - 0.0251) < 0.001 and cal["baseline_n"] == 46
          and cal["calibrated_n"] == 54, str(cal))
    check("the manuscript reports the calibration change it computes",
          f"+{cal['change']:.3f}".rstrip("0") in ms or f"+{cal['change']:.3f}" in ms,
          f"computed +{cal['change']:.3f}")
    ci = F["calibration"]["ALL"]["change_ci"]
    check("the manuscript reports the calibration interval it computes",
          f"{ci[0]:.3f}".lstrip("-") in ms and f"{ci[1]:.3f}" in ms, str(ci))

    # --- abstract agrees with results -------------------------------------
    abstract = ms[ms.index("## Abstract"):ms.index("## 1. Introduction")]
    have = lambda j: per.get(j, {}).get("ac1")
    for claim, ok_ in [
        ("r = 0.806", f"{F['r_prevalence_ac1']}" == "0.806"),
        ("AC1 = 0.883 extreme", f"{F['mean_ac1_extreme_prevalence']}" == "0.883"),
        ("0.230 mid", abs(F["mean_ac1_mid_prevalence"] - 0.23) < 0.001),
        ("0.488 llama", have("ollama:llama3.1:8b") is not None and abs(have("ollama:llama3.1:8b") - 0.4882) < 0.001),
        ("0.652 sonnet", have("anthropic:claude-sonnet-5") is not None and abs(have("anthropic:claude-sonnet-5") - 0.6521) < 0.001),
        ("0.593 judge-judge", abs(F["mean_judge_judge_ac1"] - 0.593) < 0.001),
        ("0.569 judge-human", abs(F["mean_judge_human_ac1"] - 0.569) < 0.001),
    ]:
        check(f"abstract figure holds: {claim}", ok_)
    check("every number in the abstract also appears in the body",
          all(tok in ms[ms.index("## 1. Introduction"):]
              for tok in set(re.findall(r"[0-9]+\.[0-9]{3}", abstract))),
          str([t for t in set(re.findall(r"[0-9]+\.[0-9]{3}", abstract))
               if t not in ms[ms.index("## 1. Introduction"):]]))

    # --- data-availability table points at scripts that exist -------------
    for script in re.findall(r"`harness/([a-z_]+\.py)`", ms):
        check(f"script exists: {script}", (ROOT / "harness" / script).exists())

    # --- reported sub-study figures ---------------------------------------
    import subprocess
    def run(script):
        r = subprocess.run([sys.executable, str(ROOT / "harness" / script)],
                           capture_output=True, text=True, cwd=ROOT / "harness")
        return r.stdout

    echo = run("echo_report.py")
    for want in ("809", "1365", "59.3%", "63.4%", "38.5%", "1.5%"):
        check(f"echo_report reproduces {want!r}", want in echo)
    for want in ("59.3%", "63.4%", "38.5%", "1.5%"):
        check(f"manuscript carries the echo figure {want}", want in ms)

    end = run("endearments.py")
    for want in ("0.0%", "7.7%", "17.2%", "325"):
        check(f"endearments.py reproduces {want}", want in end)
        check(f"manuscript carries the endearment figure {want}", want in ms)

    corp = run("corpus_probe.py")
    for want in ("2123", "48.5%", "26 hits (1.2%)", "7 hits (0.3%)", "9 labels"):
        check(f"corpus_probe reproduces {want!r}", want in corp)
    for want in ("2,123", "48%", "26 conversations (1.2%)", "7 (0.3%)"):
        check(f"manuscript carries the corpus figure {want!r}", want in ms)

    # --- pilot claims -----------------------------------------------------
    pilot = json.loads((ROOT / "runs" / "judged_pilot.json").read_text())
    J = sorted({j for r in pilot for j in r["judges"]})
    both = [r for r in pilot if all(j in r["judges"] and r["judges"][j] for j in J)]
    check("pilot has 101 turns scored by both judges", len(both) == 101, str(len(both)))
    probes = {(d["id"], t["n"]): set(t.get("probes") or [])
              for d in scen for t in d["turns"]}
    cnt = collections.Counter()
    for r in both:
        for d in R.live_dims(probes.get((r["scenario"], r["turn"]), set()),
                             r.get("is_farewell", False)):
            cnt[d] += 1
    check("pilot DEP2 was live on 3 of 101 turns and PER3 on 5",
          cnt["DEP2"] == 3 and cnt["PER3"] == 5, f"DEP2={cnt['DEP2']} PER3={cnt['PER3']}")
    drop, tot = collections.Counter(), collections.Counter()
    for r in pilot:
        for j in J:
            if j == r["model"]:
                continue
            tot[(r["model"], j)] += 1
            if not r["judges"].get(j):
                drop[(r["model"], j)] += 1
    rates = {k: drop[k] / tot[k] for k in tot if tot[k]}
    high = sorted(round(v * 100) for v in rates.values() if v > 0)
    check("pilot drop-out was 0% for one judge and 29-39% for the other",
          any(v == 0 for v in rates.values()) and high and min(high) == 29
          and max(high) == 39, f"nonzero rates {high}")

    # --- method constants -------------------------------------------------
    rel = (ROOT / "harness" / "reliability.py").read_text()
    check("bootstrap uses 2,000 resamples as stated", "B=2000" in rel)
    sp = (ROOT / "harness" / "system_prompts.py").read_text()
    body = sp[sp.index('"retention": ('):]
    check("the retention prompt contains no instruction to manipulate, deceive or harm",
          not re.search(r"manipulat|deceive|mislead|lie to|harm the user", body, re.I))
    check("three system prompts are defined", sp.count('": (') >= 3)

    # --- the worked example in 5.4 ----------------------------------------
    coded_keys = {keyed(u) for u in hum}
    ex = [t for t in fr["turns"]
          if (t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]) in coded_keys
          and re.search(r"can(no|.)t .{0,40}leave", t.get("reply") or "", re.I)
          and re.search(r"human connection", t.get("reply") or "", re.I)]
    check("the reply described in 5.4 exists in the human-coded set, with DEP2 live",
          bool(ex) and "DEP2" in (ex[0].get("live_dims") or []), f"{len(ex)} match")

    # --- reproducibility and provenance -----------------------------------
    import subprocess
    tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                                 cwd=ROOT).stdout.split())
    needed = ["runs/frame.json", "runs/judged_v06_local.json",
              "runs/judged_v06_commercial.json", "runs/judged_v07_sonnet.json",
              "runs/calibration.json", "data/AICompanionBench.csv",
              "paper/figures.json", "paper/citations.json"]
    for f in needed:
        check(f"released: {f}", f in tracked)
    # Every input any released script reads must itself be released, or the
    # availability statement is false.
    inputs = set(re.findall(r'ROOT\s*/\s*"(runs|data|paper)"\s*/\s*"([^"]+)"',
                            "\n".join((ROOT / "harness" / f).read_text()
                                       for f in ("figures.py", "reliability.py",
                                                 "prevalence.py", "panel_analysis.py",
                                                 "calibrate.py", "corpus_probe.py",
                                                 "echo_report.py", "check_manuscript.py"))))
    missing = [f"{a}/{b}" for a, b in inputs if f"{a}/{b}" not in tracked]
    check("every input a released script reads is itself released", not missing, str(missing))
    check("the paper does not claim primary results run without API access",
          "Primary results use open-weight models run locally" not in ms)

    spec_versions = collections.Counter(d["spec_version"] for d in scen)
    check("Limitations states the scenario specification versions accurately",
          all(f"{v}" in ms for v in spec_versions)
          and str(spec_versions["0.5"]) in ms and str(spec_versions["0.3"]) in ms,
          str(dict(spec_versions)))

    packet = json.loads((ROOT / "runs" / "second_coder_key.json").read_text())
    nq = sum(len(e["dims"]) for e in packet)
    check("second-coder packet is 40 turns and 142 questions as stated",
          len(packet) == 40 and nq == 142, f"{len(packet)} turns, {nq} questions")

    plan = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ad",
                           "--date=short", "--", "spec/analysis-plan-v1.md"],
                          capture_output=True, text=True, cwd=ROOT).stdout.split()
    tool = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ad",
                           "--date=short", "--", "harness/reliability.py"],
                          capture_output=True, text=True, cwd=ROOT).stdout.split()
    check("the analysis plan predates the analysis tool, as Methods claims",
          plan and tool and min(plan) <= min(tool), f"plan {plan[-1:]} tool {tool[-1:]}")

    # --- pre-registered analyses are reported -----------------------------
    dr = F["decision_rule"]
    check("the decision rule outcome is reported as computed",
          ("met" if dr["met"] else "not met") in ms.lower()
          and str(dr["n_adequate"]) in ms and "decision rule" in ms.lower(),
          f"met={dr['met']} n={dr['n_adequate']}")
    check("the dimensions meeting the decision rule are named",
          all(d["dim"] in ms for d in dr["adequate"]),
          str([d["dim"] for d in dr["adequate"] if d["dim"] not in ms]))
    check("the zero-prevalence caveat on the decision rule is stated",
          all(d in ms for d in dr["at_zero_prevalence"]) and "0% prevalence" in ms)
    op = F["off_probe"]
    check("off-probe firing is reported with its overall rate and extremes",
          f"{op['overall']*100:.1f}%" in ms
          and f"{op['by_dimension']['PRO4']*100:.0f}%" in ms
          and f"{op['by_dimension']['PRO2']*100:.1f}%" in ms,
          f"overall {op['overall']:.3f}")
    check("the number of unprobed turns swept is reported", str(op["turns"]) in ms)
    pr = F["provenance"]
    check("provenance proportions are reported for all four flagged dimensions",
          all(f"{v['assistant']*100:.0f}%" in ms and str(v["n"]) in ms
              for v in pr.values()), str({k: round(v["assistant"], 3) for k, v in pr.items()}))
    check("the PER1 gate-widening deviation is disclosed",
          "deviation" in ms.lower() and "PER1 was" in ms)

    # --- the Discussion's grouping arguments -------------------------------
    mid = [d for d, v in jh.items() if 0.35 <= v["prevalence"] <= 0.65]
    mid_low = [d for d in mid if jh[d]["ac1"] < 0.5]
    check("four of the five mid-prevalence dimensions are below AC1 0.5, as 4.2 states",
          len(mid) == 5 and len(mid_low) == 4, f"mid={mid} low={mid_low}")
    check("PRO2 is the mid-prevalence exception the text names",
          set(mid) - set(mid_low) == {"PRO2"} and jh["PRO2"]["ac1"] > 0.80,
          f"exception {set(mid) - set(mid_low)}")
    sec54 = ms[ms.index("### 5.4 What the contested"):ms.index("### 5.5 Implications")]
    named = re.findall(r"\((DEP\d|PRO\d|PER\d|OVR\d), 0\.\d{3}\)", sec54)
    check("every dimension named in 5.4 as scoring reliably is above AC1 0.80",
          named and all(jh[d]["ac1"] > 0.80 for d in named),
          str({d: round(jh[d]["ac1"], 3) for d in named}))
    check("the six contested dimensions named in 5.4 match the computed set",
          set(F["contested_dimensions"]) ==
          set(re.search(r"agreement collapses \(([^)]+)\)", ms).group(1).split(", ")),
          str(F["contested_dimensions"]))

    pjd = F["per_judge_by_dimension"]
    for d in ("DEP1", "DEP6"):
        vals = [v["ac1"] for v in pjd[d].values()]
        ns = [v["n"] for v in pjd[d].values()]
        check(f"no judge reaches 0.667 on {d}", max(vals) < 0.667, f"max {max(vals):.3f}")
        check(f"the {d} per-judge range in the text matches the data",
              f"{min(vals):.2f}".replace("-", "−") in ms and f"{max(vals):.2f}" in ms,
              f"[{min(vals):.2f}, {max(vals):.2f}]")
        words = {6: "six", 7: "seven", 8: "eight", 9: "nine"}
        check(f"the {d} per-judge n range in the text matches the data",
              f"{words.get(min(ns), min(ns))} to {words.get(max(ns), max(ns))} judgements"
              in ms, f"n {min(ns)}-{max(ns)}")
    check("the paper no longer claims every judge sits at chance",
          "every judge sits at chance" not in ms)
    check("no invented prevalence is attributed to DarkBench",
          "firing in\n2% of responses" not in ms and "firing in half" not in ms)

    # --- model-size and threshold statements -------------------------------
    import re as _re
    sizes = lambda names: sorted({int(x) for nm in names
                                  for x in _re.findall(r"(\d+)b$", nm.lower())})
    gen = sizes([m for m in {r["model"] for r in rows} if m.startswith("ollama")])
    jud = sizes([j for j in per if j.startswith("ollama")])
    check("the paper states the open-weight generation size range correctly",
          f"{min(gen)}B to {max(gen)}B" in ms, f"{min(gen)}-{max(gen)}B")
    check("the paper states the open-weight judge size range correctly",
          f"{min(jud)}B to {max(jud)}B" in ms, f"{min(jud)}-{max(jud)}B")
    check("no stale 8-12B claim remains", "8–12B" not in ms and "8-12B" not in ms)
    check("DEP3 is described as only just reaching the threshold",
          0.667 <= jh["DEP3"]["ac1"] < 0.70 and "only just reaches the" in ms,
          f"{jh['DEP3']['ac1']:.3f}")
    check("DEP7 is described as well below the threshold",
          jh["DEP7"]["ac1"] < 0.5 and "well below it" in ms, f"{jh['DEP7']['ac1']:.3f}")

    # --- cross-section consistency ----------------------------------------
    check("no section claims capability makes no difference on DEP1/DEP6",
          "capability makes no difference" not in ms)
    check("the PRO2 exception is carried into the abstract, 5.1 and 5.7",
          ms.count("exception") >= 3 and "largely" in ms
          and "most of\nthe dimensions" in ms)
    check("no section claims agreement spans the full range of the coefficient",
          "spans the full range of the coefficient" not in ms)
    # every dimension-with-coefficient pairing anywhere in the paper must match data
    for d, val in re.findall(r"\b(DEP\d|PER\d|PRO\d|OVR\d)[^.\n]{0,40}?"
                             r"(?:AC1 = |, )(-?0\.\d{3})\b", ms):
        # A coefficient quoted for a dimension is either the judge-human figure
        # (Table 7) or the panel figure (Table 6); both are legitimately cited.
        legit = [jh[d]["ac1"]] if d in jh else []
        legit += [pan[d][p]["ac1"] for p in ("LIVE", "POOLED") if p in pan.get(d, {})]
        check(f"stated coefficient for {d} matches a computed value ({val})",
              any(abs(float(val) - v) < 0.0015 for v in legit),
              f"computed {[round(v, 3) for v in legit]}")

    # --- the probe-to-dimension mapping is disclosed as it is --------------
    lm = R.LIVE_MAP
    inherited = sorted({d for p, tg in lm.items() for d in tg if d != p})
    used = set()
    for d_ in scen:
        for t_ in d_["turns"]:
            used |= set(t_.get("probes") or [])
    no_own = sorted(d for d in R.DIMENSIONS if d not in used and d not in R.ALWAYS_LIVE)
    check("dimensions with no probe label of their own are named in the paper",
          all(d in ms for d in no_own) and "inherit liveness" in ms, str(no_own))
    check("the paper does not claim probes name dimensions one-to-one",
          "`probes` list naming the dimensions whose" not in ms)
    orphan = sorted(p for p in used if p not in R.DIMENSIONS and p not in lm)
    check("probe labels that map to no dimension are disclosed",
          not orphan or all(p in ms for p in (orphan[0], orphan[-1])), str(orphan))
    frame_live = collections.Counter()
    for t_ in fr["turns"]:
        for d in t_.get("live_dims") or []:
            frame_live[d] += 1
    check("the inherited-liveness turn counts in the paper match the frame",
          all(str(frame_live[d]) in ms for d in no_own),
          str({d: frame_live[d] for d in no_own}))
    # the mapping must be applied consistently to the frame
    pr = {(d_["id"], t_["n"]): set(t_.get("probes") or [])
          for d_ in scen for t_ in d_["turns"]}
    mismatch = [t_["scenario"] for t_ in fr["turns"]
                if sorted(t_.get("live_dims") or []) !=
                sorted(R.live_dims(pr.get((t_["scenario"], t_["turn"]), set()),
                                   t_.get("is_farewell", False)))]
    check("every frame turn's live_dims equals the mapping applied to its probes",
          not mismatch, f"{len(mismatch)} mismatched")

    # --- numbers bound to their specific claim ----------------------------
    # check_manuscript only proves a figure is sourced somewhere in the registry.
    # Mutation testing showed that lets a figure be moved to the wrong sentence
    # undetected. These bind a figure to the sentence that states it.
    flat = re.sub(r"\s+", " ", ms)

    def bound(label, pattern, value):
        # EVERY occurrence must agree. Checking only the first let a fact stated
        # in two places drift apart: a mutation test changed the second statement
        # of a stimulus count and the check passed on the first.
        got = re.findall(pattern, flat)
        check(label, bool(got) and all(g == str(value) for g in got),
              f"text={got!r} data={str(value)!r}")

    bound("disagreement total is bound to its sentence",
          r"Of (\d+) disagreements on the six dimensions below",
          F["contested_disagreements_total"])
    bound("one-directional count is bound to its sentence",
          r"threshold, (\d+) are cases where the coder recorded",
          F["contested_disagreements_human_present"])
    for d, v in F["provenance"].items():
        bound(f"{d} provenance proportion is bound to its sentence",
              rf"(\d+)% of {d}[ ,]", round(v["assistant"] * 100))
    words = {2: "two", 3: "three", 6: "six"}
    st = F["stimuli_per_dimension"]
    # Word form only: "OVR3 on 1.0%" in the off-probe sentence is a different
    # claim and must not be matched here.
    for d, pat in (("PER3", r"PER3 on ([a-z]+)"), ("OVR3", r"OVR3 on ([a-z]+)"),
                   ("DEP2", r"DEP2 on ([a-z]+)")):
        bound(f"{d} stimulus count is bound to its sentence", pat,
              words.get(st[d], st[d]))
    fl = collections.Counter()
    for t_ in fr["turns"]:
        for dd in t_.get("live_dims") or []:
            fl[dd] += 1
    for d in ("OVR1", "OVR3", "OVR4", "PRO5"):
        bound(f"{d} inherited-liveness count is bound to its sentence",
              rf"{d} \((\d+)", fl[d])
    nwords = {4: "Four", 5: "Five", 6: "Six"}
    bound("decision-rule count is bound to its sentence",
          r"(\w+) dimensions meet it",
          nwords.get(F["decision_rule"]["n_adequate"]))
    bound("off-probe overall rate is bound to its sentence",
          r"Overall firing was ([\d.]+)%", f"{F['off_probe']['overall']*100:.1f}")

    # --- independent implementations must still agree ----------------------
    # figures.py, reliability.py, prevalence.py and panel_analysis.py compute
    # overlapping quantities by different code paths. The original double-count
    # bug was found because two of them disagreed; nothing enforced that since.
    import subprocess as _sp

    def out(script, *args):
        return _sp.run([sys.executable, str(ROOT / "harness" / script), *args],
                       capture_output=True, text=True, cwd=ROOT / "harness").stdout

    rel = out("reliability.py", "--judged",
              str(ROOT / "runs" / "judged_v06_local.json"),
              str(ROOT / "runs" / "judged_v06_commercial.json"),
              str(ROOT / "runs" / "judged_v07_sonnet.json"),
              "--human", str(ROOT / "runs" / "handcoded.json"), "--no-boot")
    hum_tbl = rel[rel.index("HUMAN vs JUDGE-MAJORITY"):] if "HUMAN vs JUDGE" in rel else ""
    rows_h = dict((m[0], float(m[1])) for m in
                  re.findall(r"^(\w+)\s+LIVE\s+\d+\s+\d+\s+\d+%\s+\d+%"
                             r"\s+-?[\d.]+\s+(-?[\d.]+)", hum_tbl, re.M))
    mism = {d: (v, jh[d]["ac1"]) for d, v in rows_h.items()
            if d in jh and abs(v - jh[d]["ac1"]) > 0.0015}
    check("reliability.py and figures.py agree on judge-vs-human AC1",
          rows_h and not mism, f"{len(rows_h)} compared, mismatches {mism}")

    panel_tbl = rel[:rel.index("LOCAL PANEL ONLY")] if "LOCAL PANEL" in rel else rel
    rows_p = dict((m[0], float(m[1])) for m in
                  re.findall(r"^(\w+)\s+LIVE\s+\d+\s+\d+\s+\d+%\s+\d+%"
                             r"\s+-?[\d.]+\s+(-?[\d.]+)", panel_tbl, re.M))
    mism_p = {d: (v, pan[d]["LIVE"]["ac1"]) for d, v in rows_p.items()
              if d in pan and abs(v - pan[d]["LIVE"]["ac1"]) > 0.0015}
    check("reliability.py and figures.py agree on panel AC1",
          rows_p and not mism_p, f"{len(rows_p)} compared, mismatches {mism_p}")

    prev = out("prevalence.py")
    rows_v = dict((m[0], (int(m[1]), float(m[2]) / 100)) for m in
                  re.findall(r"^(\w+)\s+(\d+)\s+([\d.]+)%", prev, re.M))
    mism_v = {d: (v, pbd[d]) for d, v in rows_v.items()
              if d in pbd and (v[0] != pbd[d]["live_turns"]
                               or abs(v[1] - pbd[d]["prevalence"]) > 0.001)}   # printed to 1dp
    check("prevalence.py and figures.py agree on live turns and prevalence",
          rows_v and not mism_v, f"{len(rows_v)} compared, mismatches {mism_v}")

    pa = out("panel_analysis.py")
    rows_j = dict((m[0], float(m[1])) for m in
                  re.findall(r"^(\S+)\s+(?:open|commercial)\s+\d+\s+\d+%\s+"
                             r"(-?[\d.]+)", pa, re.M))
    mism_j = {j: (v, per[j]["ac1"]) for j, v in rows_j.items()
              if j in per and abs(v - per[j]["ac1"]) > 0.0015}
    check("panel_analysis.py and figures.py agree on per-judge AC1",
          rows_j and not mism_j, f"{len(rows_j)} compared, mismatches {mism_j}")

    check("figures.py is deterministic",
          out("figures.py") == out("figures.py"))

    gen_app = out("dump_instrument.py")
    check("Appendix A is in sync with the rubric module",
          gen_app.strip() == (ROOT / "paper" / "appendix-a-instrument.md").read_text().strip())
    gen_t5 = out("dump_instrument.py", "--table")
    check("Table 5 is in sync with the rubric module",
          all(l.strip() in ms for l in gen_t5.splitlines() if l.strip()))

    print(f"\n{len(FAILS)} failing checks" + (f": {FAILS}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
