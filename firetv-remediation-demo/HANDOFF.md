# Handoff — Fire TV Remediation Demo

Status as of 2026-09-24. Read this before touching anything.

## Hard constraint

Do not edit anything at the repo root outside `firetv-remediation-demo/` —
`app.py`, `run_demo.py`, `reset_demo.py`, `setup_indices.py`, `setup_workflows.py`,
`workflows/*.yaml`, `templates/index.html` at the repo root belong to a separate,
working demo (port 5002, indices `episodic_memory`/`semantic_memory`/`procedural_memory`).
Read-only reference only.

## What's done

Full pipeline built and seeded against the live Elastic Cloud cluster:
indices `firetv_episodic_memory` (8 docs), `firetv_semantic_memory` (4),
`firetv_procedural_memory` (3), `firetv_remediation_memory` (3) — one remediation
doc per persona (`jordan_price_power_failure`, `morgan_lee_remote_network`,
`priya_nair_app_crash`). Verified via curl:

- Jordan Price: `warranty_status=expired`, `ladder_exhausted=true`, `final_offer_issued=true`
- Morgan Lee: `warranty_status=active`, `ladder_exhausted=false`, `final_offer_issued=false`
- Priya Nair: `warranty_status=active`, `ladder_exhausted=false`, `final_offer_issued=false`

`app.py` runs cleanly on port 5003. All 4 `/api/*` list endpoints return the
expected counts.

## Bugs found + fixed this session (all in `workflows/generate_firetv_*.yaml`)

This Kibana Workflows instance's Jinja-like templating is **not** real Jinja —
confirmed via a disposable probe workflow. Two operators silently misbehave:

1. **`{{ a or b }}` doesn't return a or b — it returns a stringified boolean**
   (`"true"`/`"false"`). Broke `session_date` in the episodic workflow (was
   writing the literal string `"true"` into a `date`-typed field, hard-failing
   every index request). Fixed with `{% if a %}{{ a }}{% else %}{{ b }}{% endif %}`.

2. **`{% if 'x' in y %}` always evaluates true**, regardless of actual
   containment — confirmed via probe (`in_test_false` returned `CONTAINS_YES`
   for a string that should not have matched). Broke `ladder_exhausted` and
   `final_offer_issued` in the remediation workflow (both always came out
   `"true"`). Fixed by removing the containment check entirely — replaced with
   a dedicated `ai.agent` step that judges the underlying fact directly
   (e.g. "has every ladder step been tried?") rather than text-matching
   another step's output. Also learned the AI is unreliable at literal
   "does this text contain X" meta-questions — ask it to judge the fact, not
   parse a string.

3. **GET-by-id 404s hard-fail a workflow.** `elasticsearch.request` with
   `method: GET /_doc/{id}` on a missing doc returns 404, which the engine
   treats as a fatal workflow error (the documented `on-failure: continue`
   step option did not prevent this). Fixed by switching to `POST /_search`
   with a `term` query instead — a missing doc then returns 200 + empty hits,
   which is easy to branch on with plain `{% if %}` truthiness (which works
   fine — only `or`/`in` are broken, not plain conditionals or `<`/`==`
   comparisons).

4. Also: `execution.startedAt` renders as a JS `Date.toString()` string
   (`"Thu Sep 24 2026 18:31:06 GMT+0000..."`), not ISO — useless for date
   comparison. Added an explicit `current_date` workflow input (ISO
   `YYYY-MM-DD`), computed in Python (`run_demo.py`, `app.py`, `reset_demo.py`
   all pass it now) and compared via `<`, which does work correctly.

**Takeaway for any future Kibana Workflow YAML in this repo**: avoid `or`,
`and`, and `in` in Jinja expressions entirely. Plain truthiness checks and
comparison operators (`<`, `>`, `==`) work. For anything resembling boolean
combination logic, either nest single-condition `{% if %}` blocks, or delegate
the judgment to a dedicated `ai.agent` step and interpolate its raw output
directly.

## What's NOT done — the actual next task

**Task #12 (browser verification) never ran.** All verification above was via
`curl`/API — the browser tool errored (`AbortError: interrupt`) every time it
was invoked this session, so the UI itself was never visually confirmed.

Next agent should:

1. Confirm `http://localhost:5003` is up (`lsof -ti:5003`; if not, from this
   folder: `set -a && source variables.env && set +a && python3 app.py`).
2. Open it in a browser, walk all 9 tabs.
3. On **Remediation Tracker**: confirm Jordan Price's card shows the ladder
   fully checked off, warranty badge "Expired", and the 10%-off banner.
   Confirm Morgan Lee shows mid-ladder/active/no banner, Priya Nair shows
   resolved-early/active/no banner.
4. On **Memory Demo** (comparison tab): select Jordan Price, ask "I already
   tried everything you told me — it still doesn't work. What now?", run the
   comparison. Confirm the with-memory panel surfaces the 10% offer and cites
   the 3 prior steps by name; confirm the without-memory panel does not.
5. Confirm `http://localhost:5002` (original demo) still returns 200 and is
   unaffected.

See `/Users/sunilemanjee/.claude/plans/compressed-jumping-snowglobe.md` for
the full original spec (personas, memory model, ladders) if more context is
needed.
