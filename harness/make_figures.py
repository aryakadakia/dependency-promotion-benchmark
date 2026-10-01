#!/usr/bin/env python3
"""
The two figures in Results, drawn from paper/figures.json.

    python make_figures.py          # -> paper/fig1-prevalence-agreement.pdf (+ .png)

Figure 1 is the paper's central claim: agreement against the first coder plotted
against how far a dimension's prevalence sits from 50%. It is a figure rather than a
correlation coefficient because the claim is about the shape of the relationship and
about which dimensions sit where, neither of which a single r communicates.

Figure 2 is the rank reversal: each judge's agreement with the first coder joined to
its agreement with the second, on identical units. A slope chart because the claim is
that the ORDER changes, which a pair of bar charts hides.

Nothing is typed in here. Every value is read from figures.json, so a figure cannot
disagree with the prose that cites it.
"""
import json, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).parent.parent
F = json.loads((ROOT / "paper" / "figures.json").read_text())
OUT = ROOT / "paper"

# Mid-prevalence dimensions divide on construct type, which is the argument in 4.2:
# the ones asking how a reply positions itself behave differently from the one asking
# whether a discrete event occurred. Marked so the reader can see the split.
POSITIONING = {"DEP1", "DEP2", "DEP6", "DEP7", "PER1", "PER3"}
NAME = {"ollama:gemma3:12b": "Gemma 3 12B", "ollama:qwen3:14b": "Qwen3 14B",
        "ollama:llama3.1:8b": "Llama 3.1 8B", "google:gemini-3.7-flash": "Gemini 3.7 Flash",
        "anthropic:claude-haiku-4-5": "Claude Haiku 4.5",
        "anthropic:claude-sonnet-5": "Claude Sonnet 5"}
plt.rcParams.update({"font.family": "serif", "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelsize": 9, "figure.dpi": 150})


def fig1():
    jh = F["judge_vs_human"]
    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    # OVR1, OVR3 and OVR4 sit on the same point (0% prevalence, AC1 = 1.000).
    # Drawn once and labelled once, rather than three labels overprinting.
    groups = {}
    for d, e in jh.items():
        groups.setdefault((round(abs(e["prevalence"] - 0.5) * 100, 1),
                           round(e["ac1"], 3)), []).append((d, e))
    for (x, y), members in groups.items():
        e = members[0][1]
        pos = members[0][0] in POSITIONING
        ax.scatter(x, y, s=26 + 1.3 * e["n"] ** 0.5 * 6,
                   facecolor=("white" if pos else "#2F4858"),
                   edgecolor="#2F4858", linewidth=1.1, zorder=3)
        ax.annotate(", ".join(sorted(d for d, _ in members)), (x, y),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=7, color="#333333")
    ax.axhline(0.667, color="#B00020", lw=0.8, ls="--", zorder=1)
    ax.annotate("0.667, tentative agreement", (0, 0.667), xytext=(2, 4),
                textcoords="offset points", ha="left", fontsize=7, color="#B00020")
    ax.axhline(0.0, color="#999999", lw=0.6, zorder=1)
    ax.set_xlabel("distance of prevalence from 50% (percentage points)")
    ax.set_ylabel("Gwet's AC1, first coder against judge majority")
    ax.set_xlim(-2, 54); ax.set_ylim(-0.25, 1.1)
    h = [plt.Line2D([], [], marker="o", ls="", mfc="white", mec="#2F4858",
                    label="how the reply positions itself"),
         plt.Line2D([], [], marker="o", ls="", mfc="#2F4858", mec="#2F4858",
                    label="whether a discrete event occurred")]
    ax.legend(handles=h, frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig1-prevalence-agreement.{ext}", bbox_inches="tight")
    plt.close(fig)
    return f"r = {F['r_prevalence_ac1']}, {len(jh)} dimensions"


def fig2():
    pj = F["three_rater"]["per_judge"]
    order = sorted(pj, key=lambda j: -pj[j]["second_ac1"])
    maj = F["three_rater"]
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    for j in order:
        e = pj[j]
        c = "#2F4858" if not j.startswith("ollama") else "#C47A1E"
        ax.plot([0, 1], [e["primary_ac1"], e["second_ac1"]], color=c, lw=1.4,
                marker="o", ms=4, zorder=3)
    ax.plot([0, 1], [maj["primary_vs_judges"]["ac1"], maj["second_vs_judges"]["ac1"]],
            color="#B00020", lw=2.2, marker="s", ms=5, zorder=4)
    # Right-hand labels, pushed apart where two lines end close together: the
    # majority and the best judge differ by 0.007 and would otherwise overprint.
    ends = [(maj["second_vs_judges"]["ac1"], "six-judge majority", "#B00020", True)]
    ends += [(pj[j]["second_ac1"], NAME[j],
              "#2F4858" if not j.startswith("ollama") else "#C47A1E", False)
             for j in order]
    ends.sort(key=lambda r: -r[0])
    gap, placed = 0.030, []
    for y, lbl, c, bold in ends:
        if placed and placed[-1] - y < gap:
            y = placed[-1] - gap
        placed.append(y)
        ax.annotate(lbl, (1, y), xytext=(8, 0), fontsize=7.5,
                    textcoords="offset points", va="center", color=c,
                    weight=("bold" if bold else "normal"))
    ax.axhline(0.667, color="#999999", lw=0.8, ls="--", zorder=1)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["vs first coder", "vs second coder"])
    ax.set_xlim(-0.08, 1.62); ax.set_ylabel("Gwet's AC1")
    ax.set_title(f"same {maj['n']} judgements, Spearman "
                 f"{maj['judge_rank_spearman']:+.3f} between the two rankings",
                 fontsize=8, loc="left", color="#333333")
    h = [plt.Line2D([], [], color="#2F4858", label="commercial judge"),
         plt.Line2D([], [], color="#C47A1E", label="open-weight judge")]
    ax.legend(handles=h, frameon=False, fontsize=7, loc="lower left")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig2-judge-ranking.{ext}", bbox_inches="tight")
    plt.close(fig)
    return f"{len(pj)} judges, n = {maj['n']}"


if __name__ == "__main__":
    print("fig1:", fig1())
    print("fig2:", fig2())
