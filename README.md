# Category list vs. spec: a support-ticket classifier on Haiku 4.5

A small, fully reproducible prompt evaluation. It asks how much a written
specification (definitions plus tie-break rules) improves a classifier over a
bare list of categories, what that costs, and how much of the measured
difference is noise.

## Summary

- **The spec prompt beats the category list:** 0.970 vs 0.780 accuracy (mean
  of 3 repeats, strict scoring). It fixed 9 cases and broke none. Paired exact
  McNemar test: **p ≈ 0.004**.
- **The spec costs 4.8× more per ticket** ($0.46 vs $0.10 per 1,000, estimated),
  almost entirely from prompt length.
- **Repeats matter at this size.** Across 5 passes, the spec prompt's score
  ranged from 0.955 to 0.977, and four different cases failed at least once.
- **A label audit found one ticket with no single right answer.** Accepting
  both readings changes the spec prompt's score by 0.7 points. The other
  remaining errors are down to the prompt, including one case where the spec
  contradicts itself.

## The task

Classify a customer support ticket into exactly one of 8 categories:
`billing`, `bug`, `feature_request`, `account_access`, `how_to`,
`integration`, `performance`, `spam`.

## The two prompts

Everything below is a claim about the difference between these two texts. Both
are sent as the system prompt, with the ticket as the user message.

| Prompt | Words | What it contains |
|---|---:|---|
| `v1-lazy` | 25 | The category list and "answer with the category name" |
| `v2-spec` | 283 | A definition for every category, and four tie-break rules |

### [`v1-lazy`](prompts/v1-lazy.txt)

```text
Classify this support ticket into one of these categories:
billing, bug, feature_request, account_access, how_to, integration, performance, spam

Answer with the category name and nothing else.
```

### [`v2-spec`](prompts/v2-spec.txt)

```text
Classify this support ticket into exactly one of these categories:
billing, bug, feature_request, account_access, how_to, integration, performance, spam.

Categories:
billing - what the customer pays or is subscribed to: charges, refunds, invoices, plan changes, cancelling or closing an account.
bug - our app behaves incorrectly: wrong results, wrong data shown, errors, a state that isn't applied.
performance - our app works correctly but is too slow, freezes or hangs.
account_access - who can get into or control an account: sign-in, credentials, 2FA, roles, ownership. Not closing an account.
integration - a connection between our app and an external system misbehaves. If it works correctly inside our app but goes wrong in or through the external system, it is integration.
how_to - the user asks how to do something or whether something exists or is included.
feature_request - the user asks for a capability that doesn't exist, or for an intended limit to change.
spam - unsolicited sales, marketing or partnership pitches, scams.

How to decide:
1. Classify by the action support must take to resolve the ticket, not by the user's wording ("broken", "bug") or by where in the product it happened.
2. If the fix is to change money or a subscription, it is billing. If the fix is to change our app's behaviour, it is bug or performance. An external system mentioned only as background doesn't make it integration.
3. Incorrect result -> bug. Correct result, delivered too slowly -> performance.
4. When a ticket reports a concrete problem and also asks a question or makes a suggestion, classify the problem. A question with a hypothetical "if not, add it" is still how_to.

Answer with the category name and nothing else.
```

## The cases

There are 44 hand-written cases ([`cases.jsonl`](cases.jsonl)) with three tags:

| Tag | n | What it is | Example |
|---|---:|---|---|
| easy | 8 | One obvious signal | "I was charged twice for the October invoice. Can you refund the duplicate?" → `billing` |
| edge | 14 | Built on a category boundary | "Your app is broken, it won't let me log in. Says my password is wrong but I know it isn't." → `account_access`, not `bug` |
| holdout | 22 | Same boundaries, different wording, held back for checking generalisation | "Every nightly HubSpot sync creates duplicate contacts on the HubSpot side. Contacts look fine in your app." → `integration`, not `bug` |

## Setup

- **Model:** `claude-haiku-4-5`, runs on 2026-09-14 and 2026-09-15. Prompt sent
  as the system prompt, ticket as the user message. No extended thinking;
  temperature not set (API default). `max_tokens` 16 for the final runs,
  2,000 for the two earlier runs. Outputs are ~5 tokens either way.
- **Repeats:** every case is answered 3 times per prompt. All calls in a run
  are sent in parallel, so "repeat 2" means the second answer to each case, not
  a later run.
- **Harness:** [evalix](https://github.com/frycz/evalix) at commit `d3af3eb`,
  calling Claude through [capix](https://pypi.org/project/capix/) 0.1.2.
  `pyproject.toml` pins that commit, so `uv sync` installs the harness these
  runs were produced with.
- **Run files** in [`results/`](results/) keep the names the harness gave them,
  including the `01-baseline-vs-spec` prefix of the directory this experiment
  was first run in. They are the original artifacts; renaming them would only
  obscure where the numbers came from.
- **Cost:** estimated from token counts at $1 / $5 per million input / output
  tokens, from evalix's price table. Not billed amounts.
- **Scoring,** two ways, on the **same model outputs**:
  - **strict:** exact match against the original labels.
  - **adjusted:** additionally accepts a second label for the one case the
    [label audit](#label-audit) found ambiguous.

  Adjusted scoring was defined after seeing results, so strict is the primary
  number throughout. [`rescore.py`](rescore.py) recomputes every number and
  the significance test in this report from the saved runs in
  [`results/`](results/), offline.

## Results

| Prompt | Strict | Strict per repeat | Adjusted | easy | edge | holdout | $ / 1k tickets |
|---|---:|---|---:|---:|---:|---:|---:|
| `v1-lazy` | **0.780** | 0.773 · 0.773 · 0.795 | 0.780 | 1.000 | 0.595 | 0.818 | $0.10 |
| `v2-spec` | **0.970** | 0.977 · 0.955 · 0.977 | 0.977 | 1.000 | 0.952 | 0.970 | $0.46 |

Tag columns use strict scoring. Input is ~71 vs ~437 tokens per call. The
whole measurement (264 calls) cost an estimated $0.07.

### Is the difference real?

Both prompts answer the same cases, so the comparison is **paired**: only cases
where the two prompts disagree carry information. A case counts as correct if
at least 2 of its 3 repeats were.

| | Fixed | Broke | Exact McNemar p |
|---|---:|---:|---:|
| `v1-lazy` → `v2-spec`, strict | 9 | 0 | **0.004** |
| `v1-lazy` → `v2-spec`, adjusted | 9 | 0 | **0.004** |

The improvement is real. With 44 cases, though, that's close to the limit of
what can be detected: **a prompt change needs to fix at least 6 cases without
breaking any to reach p < 0.05.** Smaller prompt tweaks on this case set can't
be told apart from noise.

## What changed between prompts

Cases that differ between `v1-lazy` and `v2-spec`, grouped by the boundary they
sit on. `n/3` is correct repeats (strict).

| Boundary | Cases | v1-lazy | v2-spec | v2-spec rule that covers it |
|---|---|---|---|---|
| bug ↔ integration | t15, h03, h15 | 0/3 each | 3/3 each | "works correctly inside our app but goes wrong in or through the external system → integration" |
| how_to ↔ feature_request | t16, h07 | 0/3 each | 3/3 each | "asks … whether something exists or is included → how_to"; "a question with a hypothetical 'if not, add it' is still how_to" |
| billing ↔ account_access | t14 | 0/3 | 3/3 | "cancelling or closing an account" is billing; account_access says "not closing an account" |
| bug ↔ billing | t21 | 0/3 | 3/3 | bug includes "a state that isn't applied" |
| bug ↔ billing | t10 | 0/3 | 2/3 | "not by … where in the product it happened" |
| bug ↔ performance | t17 | 1/3 | 3/3 | "incorrect result → bug; correct result, delivered too slowly → performance" |
| bug ↔ billing | h18 | 0/3 | 1/3 | two rules point different ways (see [label audit](#label-audit)) |
| billing ↔ integration | t13 | 3/3 | 2/3 | ambiguous ticket (see [label audit](#label-audit)) |

The rules listed are the ones that *apply* to each case. The spec was written
as a whole, not added one rule at a time with a measurement after each, so the
data can't say which sentence caused which fix.

**The lazy prompt's errors were consistent.** Of its 10 failing cases, 9 were
wrong in all 3 repeats, usually with the same wrong answer. On these boundaries
the model has a stable default that differs from the labels, which is exactly
what a tie-break rule overrides. (Three samples each, at default temperature.)

## Noise

`v2-spec` has been run in 5 passes over all 44 cases: the 3 repeats above plus
two earlier single runs of the same prompt.

| Pass | Strict | Adjusted | Failed (strict) |
|---|---:|---:|---|
| earlier run 1 | 0.977 | 0.977 | h18 |
| earlier run 2 | 0.977 | 0.977 | h15 |
| final, repeat 1 | 0.977 | 1.000 | t13 (answered `integration`, accepted under adjusted) |
| final, repeat 2 | 0.955 | 0.955 | t10, h18 |
| final, repeat 3 | 0.977 | 0.977 | h18 |

The two earlier runs are matched to this prompt by their identical per-call
input size (437 tokens); the harness doesn't record a prompt hash.

| Case | Correct (of 5) | Label | Wrong answer |
|---|---:|---|---|
| h18 | 2 | bug | billing |
| t10 | 4 | bug | billing |
| h15 | 4 | integration | bug |
| t13 | 4 strict, 5 adjusted | billing (or integration) | integration |

- No case fails every time. Every remaining error sits on a boundary the prompt
  draws, but not firmly enough to be stable.
- Any single pass shows only one or two of these cases, so **one run would
  have understated both the number of weak cases and the spread.**

## Label audit

When a case keeps failing, the tempting move is to call its label wrong. Doing
that only for the failing cases inflates the score. So all 44 labels were
checked against one question, set in advance of any relabelling:

> Does the ticket leave out a fact that decides the category, even with
> v2-spec's rules applied?

That's a narrower test than "could someone argue for another category". Several
tickets sit on a boundary (t09, t12, t14, t20, h17), but the facts are all
there and the spec's rules settle them. Those are **conventions**, which is the
prompt's job, not the label's.

**One case failed the test:**

- **t13 accepts `billing` or `integration`.** "We got an invoice for 12 seats
  but our Okta SCIM provisioning only ever created 9 users." If 9 is the real
  headcount, the invoice is wrong (`billing`). If 3 more users should exist and
  SCIM didn't create them, it's `integration`. The ticket doesn't say which.
  The case keeps its original label and adds `also_accept` and a `label_note`
  ([`score.py`](score.py)). A test in the repo fails if a second label is ever
  added without a note. t13 is also the only case that scored lower under
  `v2-spec` than under `v1-lazy` (3/3 → 2/3 strict). The spec's integration
  definition makes the `integration` reading more likely, and that reading is
  valid.

Rewriting the ticket to remove the ambiguity was the alternative. It was
rejected because it changes the input: the saved outputs could no longer be
re-scored, and new API calls would mix the label change with sampling noise.

**The other remaining failures are prompt problems:**

- **h18** looked like a label problem when judged from the failures alone. It
  isn't. The facts are complete and match t21 (paid, but the new plan isn't
  applied), which is labelled `bug` and scores 3/3. **The spec contradicts
  itself** on this pattern: `bug` covers "a state that isn't applied", while
  rule 2 says "if the fix is to change money or a subscription, it is billing".
  Both apply, and the model picks `billing` 3 times in 5. A clarifying rule
  would be a legitimate fix, but it would be tuned on a holdout case, so it
  isn't part of this measurement.
- **t10** ("There's a bug in your billing page, the annual price shows monthly")
  has a sound label, `bug`. The rule against classifying by location covers it,
  and it still fails 1 time in 5.
- **h15** follows the integration definition directly and failed once in 5.

The audit's effect on scores is small: +0.7 points for `v2-spec`, none for
`v1-lazy`.

## Limits

- **Labels, cases and prompts come from the same author,** so the evaluation
  checks one person's view of the categories against a prompt encoding that
  view. The label audit was done by the same side, with AI assistance.
- **One label was changed after seeing results.** It was checked against a
  stated rule applied to all 44 cases, and strict scores are reported first.
  It's still post hoc.
- **n = 44.** One case is 2.3 points, and only large effects are detectable
  (see the paired test).
- **The holdout isn't clean.** The prompt was revised after the holdout set had
  been run once (that run failed h15 and t14), so `v2-spec`'s 0.970 holdout
  score is partly tuned. The only untouched holdout result is that first run:
  21/22, on an intermediate prompt version that wasn't kept.
- **The holdout is easier than the edge set.** The lazy prompt scores 0.818 on
  holdout but 0.595 on edge, so the holdout overstates how well the rules
  generalise to hard cases.
- **The easy cases don't separate the prompts:** both score 1.000 on them.
- **Prompt history is incomplete.** `v2-spec` was edited in place, and its
  intermediate versions weren't kept, so there's no record of how the final
  prompt was reached.
- **One model, one sampling setup, exact-match scoring.** Nothing here says how
  the result transfers to other models or to a real ticket distribution.

## Takeaways

1. **A category list is not a spec.** The lazy prompt's errors were consistent,
   not random. The model had an answer for every boundary, just not the one the
   labels wanted. Writing the tie-break rules is where the accuracy came from.
2. **Test for significance, even at this size.** A paired test takes a few
   lines. Here it confirms the main result, and it also shows that with 44
   cases, a change fixing fewer than 6 cases can't be told apart from noise.
3. **Run repeats.** One pass of the spec prompt shows one or two weak cases;
   five passes show four.
4. **Audit labels by a rule set in advance, not by the failures.** "Is a
   deciding fact missing?" separated one genuinely ambiguous ticket from one
   that turned out to be a contradiction in the spec itself.
5. **Put cost next to accuracy.** The spec is 4.8× more expensive per ticket.
   Trivial here, but it's the trade-off that matters at scale.

## Reproduce

**Every number in this report, offline.** No API key, nothing spent — it
re-scores the saved runs in [`results/`](results/):

```bash
uv sync                    # installs evalix from git at the pinned commit
uv run python rescore.py
```

The checks on the material itself — ids unique, prompts build against every
case, the scorer no more lenient than it claims, every saved run covering all
44 cases — are also offline:

```bash
uv run pytest -q
```

**To re-run the model calls** (~$0.07; expect ±1 case per pass):

```bash
cp .env.example .env       # then paste your ANTHROPIC_API_KEY into it

for p in v1-lazy v2-spec; do
  uv run evalix run --cases cases.jsonl --prompt prompts/$p.txt \
      --scorer exact --repeat 3 --label final-$p -t 16
done
```

Runs land in `runs/` (gitignored); the four in `results/` are the ones this
report is computed from. Use `--scorer custom --scorer-file score.py` for
adjusted scoring.
