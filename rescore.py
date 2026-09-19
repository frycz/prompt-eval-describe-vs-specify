"""Re-score saved runs in results/ under strict and adjusted labels. Offline.

The model outputs don't change, only the scoring, so any difference between
the two columns is the label change and nothing else (no sampling noise, no
API calls). Ends with a paired significance test between the final prompts.

    uv run python rescore.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from math import comb
from pathlib import Path

from evalix import load_cases, load_custom
from evalix.scorers.builtin import norm

HERE = Path(__file__).resolve().parent
CASES = {c.id: c for c in load_cases(HERE / "cases.jsonl")}
ADJUSTED = load_custom(HERE / "score.py")
TAGS = ("easy", "edge", "holdout")


def strict(output: str, case) -> float:
    return 1.0 if norm(output) == norm(case.expected) else 0.0


def adjusted(output: str, case) -> float:
    return ADJUSTED(output, case, None)[0]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def report(path: Path) -> None:
    rows = json.loads(path.read_text())["results"]
    print(f"\n{path.name}")
    for name, fn in (("strict", strict), ("adjusted", adjusted)):
        by_repeat, by_tag, by_case = defaultdict(list), defaultdict(list), defaultdict(list)
        for row in rows:
            cid, _, rep = row["id"].partition("#")
            case = CASES[cid]
            s = fn(row["output"], case)
            by_repeat[rep or "1"].append(s)
            by_tag[case.tag].append(s)
            by_case[cid].append((s, norm(row["output"])))
        overall = mean([s for v in by_repeat.values() for s in v])
        repeats = " · ".join(f"{mean(v):.3f}" for _, v in sorted(by_repeat.items()))
        tags = "  ".join(f"{t} {mean(by_tag[t]):.3f}" for t in TAGS)
        print(f"  {name:<9} {overall:.3f}   repeats {repeats}   {tags}")
        misses = [
            f"{cid} {int(sum(s for s, _ in v))}/{len(v)} {[o for s, o in v if s < 1]}"
            for cid, v in by_case.items()
            if any(s < 1 for s, _ in v)
        ]
        print("            misses: " + (", ".join(misses) or "none"))


def majority(path: Path, fn) -> dict[str, bool]:
    """Per case: correct in at least half of its repeats."""
    by_case = defaultdict(list)
    for row in json.loads(path.read_text())["results"]:
        cid = row["id"].partition("#")[0]
        by_case[cid].append(fn(row["output"], CASES[cid]))
    return {cid: mean(v) > 0.5 for cid, v in by_case.items()}


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the two discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def paired(a: Path, b: Path) -> None:
    """Same cases, two prompts: only the cases they disagree on carry signal."""
    print(f"\n{label(a)} → {label(b)}   (case correct = majority of repeats)")
    for name, fn in (("strict", strict), ("adjusted", adjusted)):
        ma, mb = majority(a, fn), majority(b, fn)
        fixed = sorted(c for c in ma if not ma[c] and mb[c])
        broke = sorted(c for c in ma if ma[c] and not mb[c])
        p = mcnemar_exact(len(fixed), len(broke))
        print(f"  {name:<9} fixed {len(fixed)} {fixed}  broke {len(broke)} {broke}  exact McNemar p={p:.4f}")


def label(path: Path) -> str:
    return path.name.split("__")[1]


if __name__ == "__main__":
    runs = sorted((HERE / "results").glob("*.json"))
    for path in runs:
        report(path)
    final = {label(p): p for p in runs if label(p).startswith("final-")}
    paired(final["final-v1-lazy"], final["final-v2-spec"])
