"""Adjusted scorer: exact match, with a documented escape valve.

Most cases have one right answer. A case whose ticket is missing the fact that
decides between two categories lists the other reading in `also_accept`, with
the reason in `label_note`. Scoring such a case single-label punishes the model
for picking a valid reading, and rewards a prompt for guessing the author's.

    score = 1.0   if the output is `expected` or one of `also_accept`
          = 0.0   otherwise

`--scorer exact` still scores against `expected` alone, so the strict number
stays reproducible.
"""

from __future__ import annotations

# The same normalisation as `--scorer exact`, so strict and adjusted scores
# differ only by the labels.
from evalix.scorers.builtin import norm


def score(output: str, case) -> tuple[float, str]:
    got = norm(output)
    accepted = [case["expected"], *case.get("also_accept", [])]
    if got in {norm(a) for a in accepted}:
        extra = "" if got == norm(case["expected"]) else " (also_accept)"
        return 1.0, f"got={got!r}{extra}"
    return 0.0, f"want one of {accepted!r} got={got[:60]!r}"
