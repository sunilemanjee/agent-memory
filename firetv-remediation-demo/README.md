# Fire TV Support Memory Demo

A demonstration of episodic, semantic, procedural, **and remediation** memory for AI support agents, built on Elasticsearch + Kibana Agent Builder + Kibana Workflows. Same architecture as the sibling `agent-memory-sunman` demo, applied to a business-relatable use case: an Amazon Fire TV support agent that never asks a customer to repeat troubleshooting steps they've already tried.

## Project Overview

### The problem this solves

Anyone who has called a device support line has had this experience: you explain what's wrong, try the steps offered, call back when it doesn't work, and the agent — human or bot — has no memory of any of it. You re-explain everything. Eventually you've exhausted every troubleshooting step in existence and nobody tells you there's nothing left to try.

This demo is built around exactly that failure mode, using Amazon Fire TV support as the example. It shows an agent that:

1. Remembers exactly which troubleshooting steps a customer has already tried and failed (**remediation memory**)
2. Never re-asks for a step already tried
3. Once the fixed troubleshooting "ladder" is exhausted **and** the device is out of warranty, proactively offers the only remaining remediation — 10% off the next Fire TV purchase — instead of continuing to troubleshoot

### Four memory layers

- **Episodic Memory** — the raw record of what happened. "Jordan asked about a Fire TV that won't power on, on July 28."
- **Semantic Memory** — synthesized standing knowledge. "Jordan has a recurring power-failure issue with their Fire TV."
- **Procedural Memory** — a personalized step-by-step playbook, extracted from a user's own conversation history.
- **Remediation Memory** *(new in this demo)* — a stateful, per-(user, issue) tracker of which steps in a canonical troubleshooting ladder have been tried and failed, which remain, whether the ladder is exhausted, and whether warranty status means it's time to offer the final fallback.

### Why Elasticsearch

Same rationale as the original demo: native hybrid search (vector + BM25), `semantic_text` fields that auto-embed at index time with no ingest pipeline, metadata filtering at scale, and a single platform for search + storage + security — no external vector DB, no Memzero, no custom embedding service.

---

## Architecture

### System Flow

```
┌──────────────────────────────────────────────────────────────┐
│      ELASTIC AGENT BUILDER — Fire TV Support Specialist       │
│   • Customer chats about power/remote/network/app issues      │
│   • Multi-turn conversations stored in Kibana                 │
└──────────┬───────────────────────────────────────────────────┘
           │  conversation_id
           ▼
┌──────────────────────────────────────────────────────────────┐
│    WORKFLOW: generate_firetv_episodic_memory                  │
│   Fetch conversation → AI summarize + extract topics →         │
│   index → firetv_episodic_memory                               │
│   (accepts optional session_date_override for realistic demo   │
│   timelines — the fix for the original demo's "all memories    │
│   share ingest time" issue)                                   │
└──────────┬───────────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────────┐
│    WORKFLOW: generate_firetv_semantic_memory                  │
│   Fetch user's episodes → AI distills standing facts →         │
│   kNN merge-or-create → index → firetv_semantic_memory          │
└──────────┬───────────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────────┐
│    WORKFLOW: generate_firetv_procedural_memory                │
│   Fetch user's episodes → AI extracts personalized playbook →  │
│   index → firetv_procedural_memory                              │
└──────────┬───────────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────────┐
│    WORKFLOW: generate_firetv_remediation_memory (new)         │
│   Fetch episodes + canonical ladder + warranty dates →          │
│   AI tracks steps tried vs. remaining →                         │
│   Ladder exhausted + out of warranty? → 10% offer →             │
│   index → firetv_remediation_memory                             │
└──────────┬───────────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────────┐
│         FLASK WEB UI + MEMORY RECALL API (port 5003)           │
│   • Live chat, 4 memory browsers, search, recall, comparison   │
│   • /api/recall — kNN retrieval across all 4 memory types       │
└──────────────────────────────────────────────────────────────┘
```

### Remediation Memory Document

```json
{
  "remediation_id": "jordan_price-power_failure",
  "user_id": "jordan_price",
  "user_name": "Jordan Price",
  "device": "Amazon Fire TV",
  "issue_context": "power_failure",
  "purchase_date": "2025-08-01",
  "warranty_expiration_date": "2026-08-01",
  "warranty_status": "expired",
  "ladder_steps": "power cycle by unplugging for 30 seconds, factory reset via remote button combination, test a different power adapter and outlet, escalate to hardware replacement",
  "recommended_next_action": "STEPS_COMPLETED: power cycle, factory reset, different power adapter/outlet\nSTEPS_REMAINING: escalate to hardware replacement\nLADDER_EXHAUSTED: true\nNEXT_ACTION: Every troubleshooting step has failed and the unit is out of warranty. Offer 10% off next Fire TV purchase.",
  "ladder_exhausted": true,
  "final_offer_issued": true,
  "final_offer_text": "10% off your next Amazon Fire TV purchase",
  "last_updated": "2026-08-05T15:00:00Z"
}
```

`recommended_next_action` is stored as one raw AI-authored text block (`semantic_text`, so it's also kNN-searchable) — the app layer parses the `STEPS_COMPLETED:` / `STEPS_REMAINING:` / `LADDER_EXHAUSTED:` / `NEXT_ACTION:` markers for display. `ladder_exhausted` and `final_offer_issued` are separately derived booleans (via Jinja substring checks in the workflow) so they can be filtered on directly at the Elasticsearch query level.

### Canonical Troubleshooting Ladders

| Issue | Ladder |
|---|---|
| `power_failure` | power cycle (unplug 30s) → factory reset via remote → test different power adapter/outlet → escalate to hardware replacement |
| `remote_network` | re-pair remote → restart router / check bandwidth → move closer to router or use ethernet adapter → escalate to network diagnostics |
| `app_crash` | clear app cache + update firmware → uninstall/reinstall app → escalate to firmware compatibility team |

### Personas

| Persona | Issue | Ladder progress | Warranty | Outcome |
|---|---|---|---|---|
| **Jordan Price** | Fire TV won't power on | 4 conversations, all 3 steps tried and failed | Expired | Ladder exhausted → agent proactively offers 10% off |
| **Morgan Lee** | Remote pairing / streaming lag | 2 conversations, step 1 done, step 2 in progress | Active | Mid-ladder, unresolved |
| **Priya Nair** | App crashes | 2 conversations, step 1 resolved it | Active | Resolved early — happy path |

---

## Setup & Running

### Prerequisites

- Python 3.9+
- The same Elastic Cloud deployment as the original demo (Agent Builder + Workflows enabled, Jina inference endpoint)
- `variables.env` with `ES_URL` and `ES_ADMIN_API_KEY`

### 1. Install dependencies

```bash
cd firetv-remediation-demo
pip install -r requirements.txt
```

### 2. Create Elasticsearch indices

```bash
source variables.env && python3 setup_indices.py
```

Creates `firetv_episodic_memory`, `firetv_semantic_memory`, `firetv_procedural_memory`, `firetv_remediation_memory` — all new indices, no overlap with the original demo.

### 3. Register Kibana Workflows + agent

```bash
source variables.env && python3 setup_workflows.py
```

Registers 4 workflows and creates the **Fire TV Support Specialist** Agent Builder agent (`firetv-support-specialist`). Saves IDs to `workflow_ids.json`.

### 4. Seed the demo

```bash
source variables.env && python3 run_demo.py
```

Creates the 3 personas' conversations via Agent Builder, then triggers episodic → semantic → procedural → remediation workflows for each. Writes `demo_state.json` and `demo_seed_manifest.json`.

### 5. Start the Flask UI

```bash
source variables.env && python3 app.py
```

Open **http://localhost:5003**.

### Files

| File | Purpose |
|------|---------|
| `setup_indices.py` | Create the 4 ES indices |
| `setup_workflows.py` | Register Kibana Workflows + agent; saves `workflow_ids.json` |
| `run_demo.py` | Create Agent Builder conversations + trigger all workflows |
| `reset_demo.py` | Restore demo to seeded state for one user or all users |
| `app.py` | Flask API + web UI server (port 5003) |
| `workflows/generate_firetv_episodic_memory.yaml` | Episodic memory workflow |
| `workflows/generate_firetv_semantic_memory.yaml` | Semantic memory workflow |
| `workflows/generate_firetv_procedural_memory.yaml` | Procedural memory workflow |
| `workflows/generate_firetv_remediation_memory.yaml` | Remediation ladder workflow |

---

## API Reference

### `GET /api/episodes` / `/api/semantic` / `/api/procedural` / `/api/remediation`

List all documents in the corresponding index.

### `GET /api/search?q=...&type=both|episodic|semantic`

kNN + text search across episodic and semantic memory.

### `GET /api/recall?user_id=...&context=...`

Returns the top episodic, semantic, procedural, and remediation hits for a user + conversation context, plus a formatted context window.

### `POST /api/chat`

Converse with the Fire TV Support Specialist agent via Agent Builder.

### `POST /api/chat_comparison`

Runs the same question with and without memory injection, concurrently, so the two responses can be shown side by side. Body: `{user_id, user_name, message, memory_types}` where `memory_types` is any subset of `["episodic", "semantic", "procedural", "remediation"]`.

### `POST /api/trigger_episodic_workflow` / `_semantic_workflow` / `_procedural_workflow` / `_remediation_workflow`

Manually trigger a workflow for a given user (used by the "Save to Agent Memory" button and the Remediation Tracker's "Re-assess ladder" button).

### `POST /api/reset_demo`

Restores seeded state — deletes live-chat episodes not in the seed manifest and re-triggers downstream workflows. Body: `{user_id}` (optional — omit to reset all users).

---

## Reset / Re-run Demo

```bash
source variables.env
python3 reset_demo.py                     # reset all users
python3 reset_demo.py --user jordan_price # reset one user
```

---

## Relationship to the original demo

This demo is fully isolated from `agent-memory-sunman` at the repo root: separate folder, separate Elasticsearch indices, separate Kibana workflows, separate Agent Builder agent, separate port (5003 vs 5002). Both can run simultaneously against the same Elastic Cloud cluster with zero collision.
