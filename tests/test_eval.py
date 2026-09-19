"""Smoke tests for the evaluation material itself.

The harness has its own suite over in evalix. What is left to check here is
that *this repo's* case file, prompts and saved runs are still coherent: ids
unique, JSON well-formed, every prompt buildable against every case, and the
scorer no more lenient than it claims. All of it offline — no key, no tokens.

It is the cheap version of the habit this experiment argues for: if you can't
check it, you're guessing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evalix import Case, build_request, load_cases, load_custom

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "cases.jsonl"
PROMPTS = sorted((ROOT / "prompts").glob("*.txt"))
RESULTS = sorted((ROOT / "results").glob("*.json"))


class TestCaseFile:
    def test_loads(self):
        """Unique ids and valid JSON — load_cases raises on either."""
        assert len(load_cases(CASES_FILE)) == 44

    def test_every_case_has_a_string_input(self):
        for case in load_cases(CASES_FILE):
            assert isinstance(case.input, str) and case.input, f"{case.id} has no input"

    def test_every_case_is_tagged(self):
        """A half-tagged file makes --only-tag silently drop cases, and the
        per-tag columns in the report are only as good as these."""
        assert {c.tag for c in load_cases(CASES_FILE)} == {"easy", "edge", "holdout"}


@pytest.mark.parametrize("prompt", PROMPTS, ids=[p.name for p in PROMPTS])
def test_prompt_builds_against_every_case(prompt):
    """Catches a stray {input} under the default placement, which used to be
    sent to the model as a literal string and scored."""
    text = prompt.read_text().strip()
    placement = "user" if "{input}" in text else "system"
    for case in load_cases(CASES_FILE):
        request = build_request(case, text, placement=placement)
        assert isinstance(request.text, str)
        assert request.system or request.text


# The adjusted scorer accepts a second label only where a case documents why.
LABEL_SCORER = load_custom(ROOT / "score.py")
AMBIGUOUS_CASE = Case(id="t13", expected="billing", extra={"also_accept": ["integration"]})


class TestLabelScorer:
    def test_expected_and_also_accept_both_pass(self):
        assert LABEL_SCORER("billing", AMBIGUOUS_CASE, None)[0] == 1.0
        assert LABEL_SCORER("Integration.", AMBIGUOUS_CASE, None)[0] == 1.0

    def test_anything_else_fails(self):
        assert LABEL_SCORER("bug", AMBIGUOUS_CASE, None)[0] == 0.0

    def test_single_label_case_is_exact_match(self):
        """Too lenient is how a scorer quietly lies."""
        case = Case(id="t10", expected="bug")
        assert LABEL_SCORER("bug", case, None)[0] == 1.0
        assert LABEL_SCORER("billing", case, None)[0] == 0.0

    def test_every_also_accept_is_explained(self):
        """The label audit's rule, enforced: a second label needs a reason in
        the case file, or the adjusted score is just tuning on failures."""
        for case in load_cases(CASES_FILE):
            if case.get("also_accept"):
                assert case.get("label_note"), f"{case.id} accepts a second label without saying why"


def test_readme_prompts_match_the_files():
    """The report quotes both prompts in full. A reader checks the report's
    claims against what they read there, so a README copy that has drifted
    from the file actually sent to the model is a lie about the experiment."""
    readme = (ROOT / "README.md").read_text()
    quoted = dict(
        re.findall(r"^### \[`([^`]+)`\][^\n]*\n\n```text\n(.*?)\n```", readme, re.S | re.M)
    )
    assert set(quoted) == {p.stem for p in PROMPTS}, "a prompt is missing from the report"
    for name, body in quoted.items():
        assert body.strip() == (ROOT / "prompts" / f"{name}.txt").read_text().strip(), (
            f"README's {name} block has drifted from prompts/{name}.txt"
        )


class TestSavedRuns:
    """rescore.py recomputes the report from these, offline. If they drift,
    the report stops being reproducible."""

    def test_the_reported_runs_are_present(self):
        labels = {p.name.split("__")[1] for p in RESULTS}
        assert {"final-v1-lazy", "final-v2-spec"} <= labels

    @pytest.mark.parametrize("path", RESULTS, ids=[p.name for p in RESULTS])
    def test_every_run_covers_every_case(self, path):
        ids = {c.id for c in load_cases(CASES_FILE)}
        rows = json.loads(path.read_text())["results"]
        assert {r["id"].partition("#")[0] for r in rows} == ids
        assert all(r["error"] is None for r in rows), "a failed call would skew the score"
