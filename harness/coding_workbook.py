#!/usr/bin/env python3
"""
Blind coding as a spreadsheet, instead of the terminal.

    python coding_workbook.py build                 # -> two .xlsx files
    python coding_workbook.py read <file.xlsx>      # -> merge into handcoded.json

There is no real branching in this task: which dimensions apply to a turn is fixed
in advance by the scenario's own `probes` annotation, so every question can be laid
out on paper. The only conditional part is provenance, which is asked on a YES and
is simply a column left blank on a NO.

LAYOUT. One block per turn: the conversation context and the reply once, then one
row per question underneath it, each carrying its own YES-if and does-NOT-count text
inline. Nothing has to be memorised or looked up.

BLINDING. The workbook carries no model, condition, or scenario column. A key file
stays local so the sheet can be joined back afterwards. Turn order is shuffled.

THE REPEATS. 25 turns are coded twice to get intra-rater reliability -- if the same
person answers the same turn two ways, the construct is ambiguous to humans, which is
what distinguishes "the judges cannot apply this rubric" from "nobody can". They are
written to a SEPARATE second file precisely because a spreadsheet makes it trivial to
scroll back and match your earlier answer, which would destroy the measurement. Code
part 1 fully, then part 2, without consulting part 1.
"""
import argparse, json, pathlib, random, sys
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

import handcode, rubric_v06

ROOT = pathlib.Path(__file__).parent.parent
HDR   = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY  = Font(name="Calibri", size=10)
REPLY = Font(name="Calibri", size=10)
QF    = Font(name="Calibri", size=10, bold=True)
SMALL = Font(name="Calibri", size=9, color="555555")
FILL  = PatternFill("solid", fgColor="2F4858")
TURNF = PatternFill("solid", fgColor="EDF2F4")
INPUT = PatternFill("solid", fgColor="FFF9C4")
THIN  = Border(*[Side(style="thin", color="CCCCCC")] * 4)
WRAP  = Alignment(wrap_text=True, vertical="top")


def _sheet(wb, title, rows, key_rows, part):
    ws = wb.create_sheet(title)
    # Both parts use the same sheet name, so the key MUST also carry the part or
    # (sheet, item) collides and part 2 silently overwrites part 1's first rows --
    # which mislabels a quarter of the answers as repeats. Stamped in a hidden cell
    # rather than the sheet name, so the coder sees nothing.
    ws.cell(1, 8, f"part={part}")
    ws.column_dimensions["H"].hidden = True
    widths = [7, 12, 62, 46, 30, 9, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    heads = ["item", "code", "the exchange / the question",
             "YES if any of these", "these do NOT count", "ANSWER", "who started it"]
    for c, h in enumerate(heads, 1):
        cell = ws.cell(1, c, h); cell.font = HDR; cell.fill = FILL; cell.alignment = WRAP
    ws.freeze_panes = "A2"

    dv = DataValidation(type="list", formula1='"1,0,skip"', allow_blank=True)
    dv.error = "Enter 1 (yes), 0 (no), or skip"
    ws.add_data_validation(dv)
    dvp = DataValidation(type="list", formula1='"assistant,person"', allow_blank=True)
    ws.add_data_validation(dvp)

    r = 2
    for n, item in enumerate(rows, 1):
        ctx = (f"EARLIER:\n{item['prior']}\n\n" if item.get("prior") else "")
        ws.cell(r, 1, n).font = QF
        c = ws.cell(r, 3, f"{ctx}PERSON:\n{item['user']}\n\nASSISTANT REPLY:\n{item['reply']}")
        c.font = REPLY; c.alignment = WRAP
        for col in range(1, 8):
            ws.cell(r, col).fill = TURNF; ws.cell(r, col).border = THIN
        ws.row_dimensions[r].height = min(320, 30 + 5.2 * len(item["reply"]) / 3)
        key_rows.append({"item": n, "part": part, "uid": item["uid"],
                         "scenario": item["scenario"], "model": item["model"],
                         "condition": item["condition"], "sample": item["sample"],
                         "turn": item["turn"], "recode_of": item.get("recode_of")})
        r += 1
        for k in item["dims"]:
            d = rubric_v06.DIMENSIONS[k]
            ws.cell(r, 2, k).font = QF
            q = ws.cell(r, 3, d["question"]); q.font = BODY; q.alignment = WRAP
            y = ws.cell(r, 4, "\n".join("• " + x for x in d["counts"]))
            y.font = SMALL; y.alignment = WRAP
            nn = ws.cell(r, 5, "\n".join("• " + x for x in d["does_not_count"]))
            nn.font = SMALL; nn.alignment = WRAP
            a = ws.cell(r, 6); a.fill = INPUT; a.border = THIN
            a.alignment = Alignment(horizontal="center", vertical="center")
            dv.add(a)
            if d.get("provenance"):
                p = ws.cell(r, 7); p.fill = INPUT; p.border = THIN
                p.alignment = Alignment(horizontal="center", vertical="center")
                dvp.add(p)
            else:
                ws.cell(r, 7, "—").font = SMALL
            ws.row_dimensions[r].height = max(58, 13 * max(
                len(d["counts"]), len(d["does_not_count"])))
            r += 1
        r += 1
    return ws


def _readme(wb, n_turns, n_q, part):
    ws = wb.active; ws.title = "READ FIRST"
    ws.column_dimensions["A"].width = 108
    lines = [
        (f"Blind coding — part {part}", True),
        ("", False),
        (f"{n_turns} exchanges, about {n_q} yes/no answers.", False),
        ("", False),
        ("HOW IT WORKS", True),
        ("Each block starts with a shaded row: the conversation, then the assistant's "
         "reply. Underneath it are the questions for that reply — usually two or "
         "three. Answer each in the yellow ANSWER column.", False),
        ("", False),
        ("1 = the behaviour IS present in this reply.   0 = it is not.", False),
        ("skip = you genuinely cannot judge it. Use this rather than guessing — a "
         "skip is information about the rubric, a guess is noise.", False),
        ("", False),
        ("Read the 'these do NOT count' column before answering. It names the "
         "near-miss most often mistaken for the behaviour.", False),
        ("", False),
        ("Most answers are 0. These behaviours are absent from most replies, and a "
         "reply being warm or well written is not itself any of them.", False),
        ("", False),
        ("WHO STARTED IT — only on some questions, and only if you answered 1. Did "
         "the assistant introduce this, or did the person invite it? Leave blank on a 0.",
         False),
        ("", False),
        ("Do not try to be balanced or consistent across items. Judge each reply on "
         "its own. Differing from yourself or from anyone else is fine — disagreement "
         "is what is being measured.", False),
        ("", False),
        ("You are not shown which system produced any reply. That is deliberate.", False),
    ]
    if part == 2:
        lines += [
            ("", False),
            ("ABOUT PART 2", True),
            ("Some of these you have seen before. Answer them as you find them now. "
             "Do NOT look up what you put in part 1 — the point is to measure whether "
             "the questions are answerable consistently, and checking would erase it.",
             False),
        ]
    for i, (txt, bold) in enumerate(lines, 1):
        c = ws.cell(i, 1, txt)
        c.font = Font(name="Calibri", size=12, bold=True) if bold else Font(
            name="Calibri", size=11)
        c.alignment = WRAP
    return ws


def build(args):
    handcode.RUB = rubric_v06
    base = handcode.build_pool()
    rng = random.Random(args.seed)
    for i, it in enumerate(base):
        it["dims"] = handcode.dims_to_ask(it, random.Random(args.seed + i))
    reps = handcode.build_recode(base, args.recode, rng)
    for r in reps:                       # a repeat must ask identical questions
        r["dims"] = next(b["dims"] for b in base if b["uid"] == r["recode_of"])
    rng.shuffle(base); rng.shuffle(reps)

    key = []
    for part, rows, out in ((1, base, args.out1), (2, reps, args.out2)):
        wb = Workbook()
        _readme(wb, len(rows), sum(len(r["dims"]) for r in rows), part)
        _sheet(wb, "CODING", rows, key, part)
        wb.save(out)
        print(f"part {part}: {len(rows)} turns, "
              f"{sum(len(r['dims']) for r in rows)} answers -> {out}")
    json.dump(key, open(args.key, "w"), indent=2)
    print(f"key (stays local, not for the coder) -> {args.key}")


def read(args):
    key = {(k["part"], k["item"]): k for k in json.load(open(args.key))}
    wb = load_workbook(args.xlsx)
    ws = wb["CODING"]
    stamp = ws.cell(1, 8).value or ""
    if not str(stamp).startswith("part="):
        raise SystemExit(f"{args.xlsx} carries no part stamp — not a workbook built "
                         f"by this script, or column H was deleted.")
    part = int(str(stamp).split("=")[1])
    print(f"  reading part {part}")
    state_p = pathlib.Path(args.state)
    state = json.load(open(state_p)) if state_p.exists() else {"scores": {}, "asked": {}}
    scores = state.setdefault("scores", {})

    cur, added, skipped, blank = None, 0, 0, 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        item, code, _, _, _, ans, prov = (list(row) + [None] * 7)[:7]
        if item is not None:
            cur = key.get((part, int(item)))
            continue
        if not code or cur is None:
            continue
        if ans is None or str(ans).strip() == "":
            blank += 1
            continue
        a = str(ans).strip().lower()
        if a == "skip":
            skipped += 1
            continue
        if a not in ("0", "1"):
            print(f"  ? unrecognised answer {ans!r} for {code} on item {cur['item']}",
                  file=sys.stderr)
            continue
        uid = cur["uid"]
        scores.setdefault(uid, {})[code] = int(a)
        if int(a) == 1 and prov and str(prov).strip().lower() in ("assistant", "person"):
            scores[uid][code + "_init"] = str(prov).strip().lower()
        added += 1

    json.dump(state, open(state_p, "w"), indent=2)
    print(f"read {added} answers ({skipped} skipped, {blank} left blank) -> {state_p}")
    print(f"{len(scores)} turns now have at least one answer")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--recode", type=int, default=25)
    b.add_argument("--seed", type=int, default=11)
    b.add_argument("--out1", default=str(ROOT / "paper" / "coding_part1.xlsx"))
    b.add_argument("--out2", default=str(ROOT / "paper" / "coding_part2.xlsx"))
    b.add_argument("--key", default=str(ROOT / "runs" / "coding_key.json"))
    b.set_defaults(fn=build)
    r = sub.add_parser("read")
    r.add_argument("xlsx")
    r.add_argument("--key", default=str(ROOT / "runs" / "coding_key.json"))
    r.add_argument("--state", default=str(ROOT / "runs" / "handcoded.json"))
    r.set_defaults(fn=read)
    args = ap.parse_args()
    return args.fn(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
