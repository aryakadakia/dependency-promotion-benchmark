#!/usr/bin/env python3
"""
Emit the Results tables as markdown from paper/figures.json, so no reported
number is ever typed by hand.

    python figures.py --save && python dump_tables.py --table 6
"""
import argparse, json, pathlib
import rubric_v07 as R

ROOT = pathlib.Path(__file__).parent.parent
NAME = {"anthropic:claude-sonnet-5": "Claude Sonnet 5",
        "anthropic:claude-haiku-4-5": "Claude Haiku 4.5",
        "google:gemini-3.7-flash": "Gemini 3.7 Flash",
        "ollama:gemma3:12b": "Gemma 3 12B", "ollama:qwen3:14b": "Qwen3 14B",
        "ollama:qwen3:8b": "Qwen3 8B", "ollama:llama3.1:8b": "Llama 3.1 8B"}
LABEL = {d: R.DIMENSIONS[d]["name"].lower() for d in R.DIMENSIONS}


def pc(x):
    return f"{x*100:.0f}%"


def t6(F):
    print("| Dim | Units | Stimuli | Prevalence | Agreement | Alpha | AC1 | 95% CI | Pooled AC1 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for d in R.DIMENSIONS:
        e = F["panel_reliability"].get(d, {})
        L, P = e.get("LIVE"), e.get("POOLED")
        if not L:
            continue
        ci = f"{L['ci'][0]:.2f}, {L['ci'][1]:.2f}" if "ci" in L else "—"
        print(f"| {d} | {L['units']} | {L['stimuli']} | {pc(L['prevalence'])} "
              f"| {pc(L['agreement'])} | {L['alpha']:.3f} | {L['ac1']:.3f} | {ci} "
              f"| {P['ac1']:.3f} |")


def t7(F):
    print("| Dim | Units | Prevalence | Agreement | AC1 |")
    print("|---|---|---|---|---|")
    for d, e in sorted(F["judge_vs_human"].items(), key=lambda x: -x[1]["ac1"]):
        print(f"| {d} | {e['n']} | {pc(e['prevalence'])} | {pc(e['agreement'])} "
              f"| {e['ac1']:.3f} |")


def t8(F):
    print("| Dim | Human present, judges absent | Human absent, judges present |")
    print("|---|---|---|")
    for d, (a, b) in sorted(F["disagreement_direction"].items()):
        mark = " *" if d in F["contested_dimensions"] else ""
        print(f"| {d}{mark} | {a} | {b} |")


def t9(F):
    print("| Judge | Tier | n | Agreement | AC1 |")
    print("|---|---|---|---|---|")
    for j, e in sorted(F["per_judge_vs_human"].items(), key=lambda x: -x[1]["ac1"]):
        tier = "open" if j.startswith("ollama") else "commercial"
        print(f"| {NAME.get(j, j)} | {tier} | {e['n']} | {pc(e['agreement'])} "
              f"| {e['ac1']:.3f} |")


def t10(F):
    val = lambda d: R.DIMENSIONS[d]["valence"].replace("overcorrection", "over-correction")
    print("| Dim | Valence | Live turns | Prevalence |")
    print("|---|---|---|---|")
    for d, e in sorted(F["prevalence_by_dimension"].items(),
                       key=lambda x: -x[1]["prevalence"]):
        print(f"| {d} {LABEL[d]} | {val(d)} | {e['live_turns']} "
              f"| {e['prevalence']*100:.1f}% |")


def t11(F):
    print("| Model | DEP | PRO | OVR | FMR |")
    print("|---|---|---|---|---|")
    for m, e in sorted(F["prevalence_by_model"].items(),
                       key=lambda x: x[1].get("DEP", 0)):
        cell = lambda k: f"{e[k]*100:.1f}%" if k in e else "—"
        print(f"| {NAME.get(m, m)} | {cell('DEP')} | {cell('PRO')} | {cell('OVR')} "
              f"| {cell('FMR')} |")


def t12(F):
    print("| Dim | Baseline n | Calibrated n | Baseline AC1 | Calibrated AC1 |")
    print("|---|---|---|---|---|")
    for d, e in F["calibration"].items():
        b = f"{e['baseline_ac1']:.3f}" if "baseline_ac1" in e else "—"
        c = f"{e['calibrated_ac1']:.3f}" if "calibrated_ac1" in e else "—"
        print(f"| {d} | {e['baseline_n']} | {e['calibrated_n']} | {b} | {c} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", type=int, required=True, choices=range(6, 13))
    a = ap.parse_args()
    F = json.loads((ROOT / "paper" / "figures.json").read_text())
    {6: t6, 7: t7, 8: t8, 9: t9, 10: t10, 11: t11, 12: t12}[a.table](F)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
