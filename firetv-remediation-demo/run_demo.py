#!/usr/bin/env python3
"""
Demo script: Creates Agent Builder conversations and triggers Kibana Workflows
to generate episodic, semantic, procedural, and remediation memories in Elasticsearch.

Flow:
  1. Have each persona's conversations with the Fire TV Support Specialist via Agent Builder
  2. Trigger generate_firetv_episodic_memory for each conversation (with session_date_override
     so the demo timeline looks realistic instead of every memory sharing ingest time)
  3. Trigger generate_firetv_semantic_memory per user/entity cluster
  4. Trigger generate_firetv_procedural_memory per user/issue context
  5. Trigger generate_firetv_remediation_memory per user/issue, tracking ladder progress
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone

KB_URL = os.environ.get("ES_URL", "").replace(".es.", ".kb.")
API_KEY = os.environ.get("ES_ADMIN_API_KEY")

if not KB_URL or not API_KEY:
    print("ERROR: ES_URL and ES_ADMIN_API_KEY environment variables required")
    sys.exit(1)

# Load workflow IDs registered by setup_workflows.py
_base = os.path.dirname(os.path.abspath(__file__))
_wf_ids_path = os.path.join(_base, "workflow_ids.json")
_wf_ids = {}
if os.path.exists(_wf_ids_path):
    with open(_wf_ids_path) as _f:
        _wf_ids = json.load(_f)

AGENT_ID = _wf_ids.get("agent", "elastic-ai-agent")
EPISODIC_WORKFLOW_ID = _wf_ids.get("episodic", "generate_firetv_episodic_memory")
SEMANTIC_WORKFLOW_ID = _wf_ids.get("semantic", "generate_firetv_semantic_memory")
PROCEDURAL_WORKFLOW_ID = _wf_ids.get("procedural", "generate_firetv_procedural_memory")
REMEDIATION_WORKFLOW_ID = _wf_ids.get("remediation", "generate_firetv_remediation_memory")

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}

# Canonical troubleshooting ladders per issue type
LADDER_STEPS = {
    "power_failure": "power cycle by unplugging for 30 seconds, factory reset via remote button combination, test a different power adapter and outlet, escalate to hardware replacement",
    "remote_network": "re-pair the remote to the Fire TV, restart the router and check available bandwidth, move the Fire TV closer to the router or use an ethernet adapter, escalate to network diagnostics",
    "app_crash": "clear app cache and update Fire TV firmware, uninstall and reinstall the affected app, escalate to firmware compatibility team",
}

# Demo personas and their conversation scripts (user turns only — agent replies are live)
DEMO_USERS = [
    {
        "user_id": "jordan_price",
        "user_name": "Jordan Price",
        "conversations": [
            {
                "session_date": "2026-07-28T10:00:00Z",
                "issue_context": "power_failure",
                "messages": [
                    "My Fire TV won't power on at all — no light, nothing on screen. This just started today, can you help?",
                    "It's plugged directly into the wall outlet, and the remote isn't doing anything either.",
                ],
            },
            {
                "session_date": "2026-07-30T11:30:00Z",
                "issue_context": "power_failure",
                "messages": [
                    "I unplugged it for 30 seconds like you suggested and plugged it back in, but it's still completely dead — no light at all.",
                    "I don't see the Amazon logo or anything on screen when I connect it to the TV.",
                ],
            },
            {
                "session_date": "2026-08-02T09:15:00Z",
                "issue_context": "power_failure",
                "messages": [
                    "I tried holding the back and right buttons on the remote for the factory reset like you said, but since the device won't even power on, the remote can't communicate with it at all.",
                    "I also already tried a different HDMI port.",
                ],
            },
        ],
    },
    {
        "user_id": "morgan_lee",
        "user_name": "Morgan Lee",
        "conversations": [
            {
                "session_date": "2026-09-10T13:00:00Z",
                "issue_context": "remote_network",
                "messages": [
                    "My Fire TV remote won't pair anymore and the screen also lags a lot when streaming. Can you help with the remote first?",
                    "It's an original remote, and holding the pairing button doesn't seem to do anything.",
                ],
            },
            {
                "session_date": "2026-09-14T16:20:00Z",
                "issue_context": "remote_network",
                "messages": [
                    "Re-pairing the remote worked, thanks! But the streaming lag issue is still happening — videos buffer constantly.",
                    "My router is a few rooms away from the Fire TV, if that matters.",
                ],
            },
        ],
    },
    {
        "user_id": "priya_nair",
        "user_name": "Priya Nair",
        "conversations": [
            {
                "session_date": "2026-09-01T08:40:00Z",
                "issue_context": "app_crash",
                "messages": [
                    "The Prime Video app on my Fire TV keeps crashing every time I try to open it. Netflix works fine though.",
                    "It's been happening for about a week now.",
                ],
            },
            {
                "session_date": "2026-09-03T09:10:00Z",
                "issue_context": "app_crash",
                "messages": [
                    "I cleared the cache and updated the firmware like you suggested, and Prime Video is working perfectly now. Thank you!",
                ],
            },
        ],
    },
]

# Entity clusters for semantic memory distillation
ENTITY_CLUSTERS = {
    "jordan_price": [
        ("power_failure", "concept"),
    ],
    "morgan_lee": [
        ("remote_pairing", "concept"),
        ("streaming_lag", "concept"),
    ],
    "priya_nair": [
        ("app_crash", "concept"),
    ],
}

# Procedural contexts for procedural memory extraction
PROCEDURAL_CONTEXTS = {
    "jordan_price": ["power_failure"],
    "morgan_lee": ["remote_network"],
    "priya_nair": ["app_crash"],
}

# Remediation ladder cases: one per persona/issue, drives the remediation workflow
REMEDIATION_CASES = {
    "jordan_price": {
        "issue_context": "power_failure",
        "device": "Amazon Fire TV",
        "purchase_date": "2025-08-01",
        "warranty_expiration_date": "2026-08-01",
    },
    "morgan_lee": {
        "issue_context": "remote_network",
        "device": "Amazon Fire TV",
        "purchase_date": "2026-06-01",
        "warranty_expiration_date": "2027-06-01",
    },
    "priya_nair": {
        "issue_context": "app_crash",
        "device": "Amazon Fire TV",
        "purchase_date": "2026-05-01",
        "warranty_expiration_date": "2027-05-01",
    },
}


def have_conversation(user, convo_script):
    """Have a multi-turn conversation with the Fire TV Support Specialist agent."""
    conversation_id = None
    print(f"    Starting conversation...")

    for i, user_message in enumerate(convo_script["messages"]):
        body = {
            "input": user_message,
            "agent_id": AGENT_ID,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id

        try:
            resp = requests.post(
                f"{KB_URL}/api/agent_builder/converse",
                headers=HEADERS,
                json=body,
                timeout=180,
            )

            if resp.status_code == 200:
                data = resp.json()
                conversation_id = data.get("conversation_id", conversation_id)
                response_snippet = str(data.get("response", {}).get("message", ""))[:80]
                print(f"      Turn {i+1}: ✓ Agent responded ({len(response_snippet)} chars...)")
            else:
                # Agent might not exist yet, fall back to elastic-ai-agent
                body["agent_id"] = "elastic-ai-agent"
                resp = requests.post(
                    f"{KB_URL}/api/agent_builder/converse",
                    headers=HEADERS,
                    json=body,
                    timeout=180,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    conversation_id = data.get("conversation_id", conversation_id)
                    print(f"      Turn {i+1}: ✓ (fallback to elastic-ai-agent)")
                else:
                    print(f"      Turn {i+1}: ERROR {resp.status_code}: {resp.text[:100]}")
        except requests.exceptions.Timeout:
            print(f"      Turn {i+1}: TIMEOUT (skipping turn)")
        except Exception as e:
            print(f"      Turn {i+1}: ERROR {e}")

        time.sleep(2)  # Be gentle with the API

    return conversation_id


def trigger_episodic_workflow(conversation_id, user_id, user_name, issue_context, session_date_override):
    """Trigger the generate_firetv_episodic_memory workflow for a conversation."""
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow/{EPISODIC_WORKFLOW_ID}/run",
        headers=HEADERS,
        json={
            "inputs": {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "user_name": user_name,
                "issue_context": issue_context,
                "session_date_override": session_date_override,
            }
        },
        timeout=120,
    )

    if resp.status_code in (200, 201, 202):
        data = resp.json()
        exec_id = data.get("execution_id") or data.get("id") or "unknown"
        status = data.get("status", "triggered")
        print(f"      Workflow: execution {exec_id[:16]}... | status: {status}")
        return exec_id
    else:
        print(f"      Workflow ERROR {resp.status_code}: {resp.text[:150]}")
        return None


def trigger_semantic_workflow(user_id, user_name, entity_name, entity_type):
    """Trigger the generate_firetv_semantic_memory workflow for a user/entity."""
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow/{SEMANTIC_WORKFLOW_ID}/run",
        headers=HEADERS,
        json={
            "inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "entity_name": entity_name,
                "entity_type": entity_type,
            }
        },
        timeout=120,
    )

    if resp.status_code in (200, 201, 202):
        data = resp.json()
        exec_id = data.get("execution_id") or data.get("id") or "unknown"
        status = data.get("status", "triggered")
        print(f"      Semantic workflow '{entity_name}': {exec_id[:16]}... | {status}")
        return exec_id
    else:
        print(f"      Semantic workflow ERROR {resp.status_code}: {resp.text[:150]}")
        return None


def trigger_procedural_workflow(user_id, user_name, procedure_context):
    """Trigger the generate_firetv_procedural_memory workflow for a user/context."""
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow/{PROCEDURAL_WORKFLOW_ID}/run",
        headers=HEADERS,
        json={
            "inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "procedure_context": procedure_context,
            }
        },
        timeout=120,
    )

    if resp.status_code in (200, 201, 202):
        data = resp.json()
        exec_id = data.get("execution_id") or data.get("id") or "unknown"
        status = data.get("status", "triggered")
        print(f"      Procedural workflow '{procedure_context}': {exec_id[:16]}... | {status}")
        return exec_id
    else:
        print(f"      Procedural workflow ERROR {resp.status_code}: {resp.text[:150]}")
        return None


def trigger_remediation_workflow(user_id, user_name, case):
    """Trigger the generate_firetv_remediation_memory workflow for a user/issue."""
    issue_context = case["issue_context"]
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow/{REMEDIATION_WORKFLOW_ID}/run",
        headers=HEADERS,
        json={
            "inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "issue_context": issue_context,
                "device": case["device"],
                "purchase_date": case["purchase_date"],
                "warranty_expiration_date": case["warranty_expiration_date"],
                "ladder_steps": LADDER_STEPS[issue_context],
                "current_date": datetime.now(timezone.utc).date().isoformat(),
            }
        },
        timeout=120,
    )

    if resp.status_code in (200, 201, 202):
        data = resp.json()
        exec_id = data.get("execution_id") or data.get("id") or "unknown"
        status = data.get("status", "triggered")
        print(f"      Remediation workflow '{issue_context}': {exec_id[:16]}... | {status}")
        return exec_id
    else:
        print(f"      Remediation workflow ERROR {resp.status_code}: {resp.text[:150]}")
        return None


def save_run_state(state):
    """Save conversation IDs to a JSON file for reference."""
    with open("demo_state.json", "w") as f:
        json.dump(state, f, indent=2)
    print(f"\n  State saved to demo_state.json")

    # Update seed manifest so reset_demo.py knows which IDs are canonical
    manifest = {"episodic_ids": {}}
    for conv in state["conversations"]:
        uid = conv["user_id"]
        cid = conv["conversation_id"]
        if uid not in manifest["episodic_ids"]:
            manifest["episodic_ids"][uid] = []
        if cid not in manifest["episodic_ids"][uid]:
            manifest["episodic_ids"][uid].append(cid)
    manifest_path = os.path.join(_base, "demo_seed_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Seed manifest saved to demo_seed_manifest.json")


def main():
    print("=== Fire TV Remediation Demo: Conversations + Workflows ===\n")

    state = {"conversations": [], "workflows": []}

    # Phase 1: Have conversations via Agent Builder
    print("Phase 1: Creating Agent Builder conversations\n")

    for user in DEMO_USERS:
        print(f"User: {user['user_name']} ({user['user_id']})")
        for i, convo_script in enumerate(user["conversations"]):
            print(f"  Conversation {i+1}/{len(user['conversations'])}:")
            conversation_id = have_conversation(user, convo_script)

            if conversation_id:
                print(f"    conversation_id: {conversation_id}")
                state["conversations"].append({
                    "conversation_id": conversation_id,
                    "user_id": user["user_id"],
                    "user_name": user["user_name"],
                    "convo_index": i + 1,
                    "issue_context": convo_script["issue_context"],
                    "session_date": convo_script["session_date"],
                })
            else:
                print(f"    WARNING: No conversation ID returned")
        print()

    print(f"  Created {len(state['conversations'])} conversations\n")

    # Phase 2: Trigger episodic memory workflow for each conversation
    print("Phase 2: Triggering generate_firetv_episodic_memory workflow\n")
    print("  (Each workflow: fetches conversation → AI summarizes → indexes to ES)\n")

    for conv in state["conversations"]:
        print(f"  Conversation {conv['convo_index']} for {conv['user_name']}:")
        exec_id = trigger_episodic_workflow(
            conv["conversation_id"],
            conv["user_id"],
            conv["user_name"],
            conv["issue_context"],
            conv["session_date"],
        )
        state["workflows"].append({
            "type": "episodic",
            "conversation_id": conv["conversation_id"],
            "execution_id": exec_id,
        })
        time.sleep(2)  # Allow workflows to process

    print()

    # Phase 3: Wait for episodic memories to be indexed
    print("Waiting 10s for episodic workflows to complete...\n")
    time.sleep(10)

    # Phase 4: Trigger semantic memory workflow for each user/entity
    print("Phase 3: Triggering generate_firetv_semantic_memory workflow\n")
    print("  (Each workflow: searches episodic memories → AI distills → indexes to ES)\n")

    for user_id, entities in ENTITY_CLUSTERS.items():
        user_name = next(
            u["user_name"] for u in DEMO_USERS if u["user_id"] == user_id
        )
        print(f"  User: {user_name}")
        for entity_name, entity_type in entities:
            exec_id = trigger_semantic_workflow(
                user_id, user_name, entity_name, entity_type
            )
            state["workflows"].append({
                "type": "semantic",
                "user_id": user_id,
                "entity_name": entity_name,
                "execution_id": exec_id,
            })
            time.sleep(3)
        print()

    # Phase 5: Trigger procedural memory workflow for each user/context
    print("Phase 4: Triggering generate_firetv_procedural_memory workflow\n")
    print("  (Each workflow: searches episodic memories → AI extracts steps → indexes to ES)\n")

    for user_id, contexts in PROCEDURAL_CONTEXTS.items():
        user_name = next(
            u["user_name"] for u in DEMO_USERS if u["user_id"] == user_id
        )
        print(f"  User: {user_name}")
        for procedure_context in contexts:
            exec_id = trigger_procedural_workflow(
                user_id, user_name, procedure_context
            )
            state["workflows"].append({
                "type": "procedural",
                "user_id": user_id,
                "procedure_context": procedure_context,
                "execution_id": exec_id,
            })
            time.sleep(3)
        print()

    # Phase 6: Trigger remediation memory workflow for each user/issue ladder
    print("Phase 5: Triggering generate_firetv_remediation_memory workflow\n")
    print("  (Each workflow: reads episode history + ladder + warranty → indexes ladder state)\n")

    for user_id, case in REMEDIATION_CASES.items():
        user_name = next(
            u["user_name"] for u in DEMO_USERS if u["user_id"] == user_id
        )
        print(f"  User: {user_name}")
        exec_id = trigger_remediation_workflow(user_id, user_name, case)
        state["workflows"].append({
            "type": "remediation",
            "user_id": user_id,
            "issue_context": case["issue_context"],
            "execution_id": exec_id,
        })
        time.sleep(3)
        print()

    save_run_state(state)

    print("\n=== Demo Complete ===")
    print(f"  Conversations created: {len(state['conversations'])}")
    print(f"  Workflows triggered:   {len(state['workflows'])}")
    print()
    print("Open http://localhost:5003 to view memories in the UI")
    print("Kibana: workflows visible at <kibana_url>/app/management/kibana/workflows")


if __name__ == "__main__":
    main()
