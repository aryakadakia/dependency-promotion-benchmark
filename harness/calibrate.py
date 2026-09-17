#!/usr/bin/env python3
"""
Can a judge learn the human coder's threshold from examples?

Six judges disagree with each other (mean AC1 0.593) about as much as they disagree
with the human coder (0.569), so the coder is not an outlier and the contested
dimensions -- DEP1, DEP2, DEP6, DEP7 -- are contested for everyone. This asks whether
the disagreement is an ANCHOR problem, fixable by demonstration, or a CONSTRUCT one.

    train on the coder's labels from 60% of scenarios
    score the held-out 40% with those examples in the prompt
    compare against the SAME judge, SAME turns, without them

The result is asymmetric and worth stating before running it:

  FAILS  -> conclusive. If a judge shown worked examples still cannot match the coder
            on held-out turns, the construct is not pinned down by demonstration and
            better anchor wording will not rescue it.
  WORKS  -> the judge can learn THIS coder's threshold. Whether that threshold is the
            correct one is a separate question needing a second human coder.

Split is by SCENARIO, not by turn: splitting by turn would let a judge see labelled
examples from the same conversation it is then tested on.

    python calibrate.py --judge anthropic:claude-sonnet-5 --max-spend 2.00
"""
import argparse, json, pathlib, random, sys
from collections import defaultdict
import providers, rubric_v07 as R, reliability as rel

ROOT = pathlib.Path(__file__).parent.parent
CONTESTED = ["DEP1", "DEP2", "DEP6", "DEP7", "PER1", "DEP3"]


def load():
    fr = {(t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]): t
          for t in json.load(open(ROOT / "data" / "frame" / "frame.json"))["turns"]}
    hum = json.load(open(ROOT / "data" / "human" / "handcoded.json"))["scores"]
    judged = defaultdict(dict)
    for f in ("judged_v06_local.json", "judged_v06_commercial.json", "judged_v07_sonnet.json"):
        for r in json.load(open(ROOT / "data" / "judged" / f)):
            k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
            judged[k].update(r["judges"])
    items = []
    for uid, hs in hum.items():
        if uid.endswith("#recode"):
            continue
        p = uid.split("|"); k = (p[0], p[1], p[2], int(p[3]), int(p[4]))
        t = fr.get(k)
        if not t or t.get("invalid_reason"):
            continue
        dims = [d for d in CONTESTED if d in hs and d in t["live_dims"]]
        if dims:
            items.append({"k": k, "t": t, "human": hs, "dims": dims})
    return items, judged


def fewshot_block(train, dim, n, rng):
    ex = [i for i in train if dim in i["dims"]]
    pos = [i for i in ex if i["human"][dim] == 1]
    neg = [i for i in ex if i["human"][dim] == 0]
    rng.shuffle(pos); rng.shuffle(neg)
    picked = pos[:n // 2] + neg[:n - n // 2]
    rng.shuffle(picked)
    if not picked:
        return ""
    out = [f"\nWorked examples for {dim}, scored by an experienced human coder:"]
    for i in picked:
        out.append(f"\n  PERSON: {i['t']['user'][:150]}"
                   f"\n  ASSISTANT: {i['t']['reply'][:400]}"
                   f"\n  -> {dim} = {i['human'][dim]}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="anthropic:claude-sonnet-5")
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--max-spend", type=float, default=2.00)
    ap.add_argument("-o", "--out", default=str(ROOT / "data" / "judged" / "calibration.json"))
    args = ap.parse_args()

    ok, why = providers.check(args.judge)
    print(f"  judge {'OK ' if ok else '-- '}{args.judge}: {why}")
    if not ok:
        return 1
    providers.set_run_budget(args.max_spend)

    items, judged = load()
    rng = random.Random(args.seed)
    scen = sorted({i["k"][0] for i in items})
    rng.shuffle(scen)
    cut = int(len(scen) * 0.6)
    train_s, test_s = set(scen[:cut]), set(scen[cut:])
    train = [i for i in items if i["k"][0] in train_s]
    test = [i for i in items if i["k"][0] in test_s]
    print(f"\nsplit by scenario: {len(train_s)} train / {len(test_s)} test")
    print(f"  train turns {len(train)}, test turns {len(test)}")
    print(f"  test judgements: {sum(len(i['dims']) for i in test)}")

    results = []
    for n, i in enumerate(test, 1):
        blocks = "".join(fewshot_block(train, d, args.examples, rng) for d in i["dims"])
        prompt = R.judge_prompt(i["t"]["user"], i["t"]["reply"], i["dims"],
                                i["t"].get("prior", ""))
        prompt = prompt.replace("--- QUESTIONS ---",
                                blocks + "\n--- QUESTIONS ---")
        try:
            rep = providers.chat(args.judge, "", [{"role": "user", "content": prompt}],
                                 max_tokens=2000, think=False)
        except providers.SpendCap as e:
            print(f"\n!! {e}", file=sys.stderr); break
        import judge as J
        sc = J.parse_scores(rep.text, i["dims"], R) or {}
        results.append({"key": list(i["k"]), "dims": i["dims"],
                        "human": {d: i["human"][d] for d in i["dims"]},
                        "calibrated": {d: sc.get(d) for d in i["dims"]},
                        "baseline": {d: judged[i["k"]].get(args.judge, {}).get(d)
                                     for d in i["dims"]}})
        if n % 10 == 0:
            print(f"  {n}/{len(test)}", flush=True)
    json.dump(results, open(args.out, "w"), indent=2)

    print(f"\n{'dim':<7}{'n':>5}{'baseline AC1':>14}{'calibrated AC1':>16}   change")
    print("-" * 60)
    for d in CONTESTED + ["ALL"]:
        b, c = [], []
        for r in results:
            for dd in r["dims"]:
                if d not in (dd, "ALL"):
                    continue
                h = r["human"][dd]
                if r["baseline"].get(dd) is not None: b.append([h, r["baseline"][dd]])
                if r["calibrated"].get(dd) is not None: c.append([h, r["calibrated"][dd]])
        if len(b) < 8 or len(c) < 8:
            print(f"{d:<7}{len(c):>5}{'  too few':>14}"); continue
        ba, ca = rel.gwet_ac1(b), rel.gwet_ac1(c)
        print(f"{d:<7}{len(c):>5}{ba:>14.3f}{ca:>16.3f}   {ca-ba:+.3f}")
    print(f"\nspend this run: ${providers.spent_this_run():.4f}")
    print("\nBaseline is the SAME judge on the SAME held-out turns without examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
