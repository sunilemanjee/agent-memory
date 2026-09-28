#!/usr/bin/env python3
"""
Register Kibana Workflows and create the Fire TV Support Specialist agent.
Requires: ES_URL and ES_ADMIN_API_KEY environment variables.

Workflow IDs are saved to workflow_ids.json for use by app.py and run_demo.py.
"""

import os
import sys
import json
import requests

KB_URL = os.environ.get("ES_URL", "").replace(".es.", ".kb.")
API_KEY = os.environ.get("ES_ADMIN_API_KEY")

if not KB_URL or not API_KEY:
    print("ERROR: ES_URL and ES_ADMIN_API_KEY environment variables required")
    sys.exit(1)

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}

WORKFLOW_IDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow_ids.json")


def load_saved_ids():
    """Load previously saved workflow IDs."""
    if os.path.exists(WORKFLOW_IDS_FILE):
        with open(WORKFLOW_IDS_FILE) as f:
            return json.load(f)
    return {}


def save_ids(ids):
    """Save workflow IDs for use by other scripts."""
    with open(WORKFLOW_IDS_FILE, "w") as f:
        json.dump(ids, f, indent=2)


def get_workflow_by_id(workflow_id):
    """Check if a workflow exists by its ID."""
    resp = requests.get(
        f"{KB_URL}/api/workflows/workflow/{workflow_id}",
        headers=HEADERS,
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def register_workflow(yaml_path, logical_name):
    """
    Register or update a workflow.
    - If we have a saved ID from a previous run: try PUT to update it.
    - Otherwise: POST to create fresh (API assigns the ID).
    Returns the assigned workflow ID.
    """
    with open(yaml_path) as f:
        yaml_content = f.read()

    saved_ids = load_saved_ids()
    existing_id = saved_ids.get(logical_name)

    # Try PUT update on the previously-known ID
    if existing_id:
        existing = get_workflow_by_id(existing_id)
        if existing:
            resp = requests.put(
                f"{KB_URL}/api/workflows/workflow/{existing_id}",
                headers=HEADERS,
                json={"yaml": yaml_content},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                wf_id = data.get("id", existing_id)
                print(f"  ✓ Updated workflow '{logical_name}' → id: {wf_id}")
                return wf_id
            else:
                print(f"  PUT failed ({resp.status_code}), will recreate...")

    # POST to create new
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow",
        headers=HEADERS,
        json={"yaml": yaml_content},
        timeout=30,
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        wf_id = data.get("id", logical_name)
        print(f"  ✓ Created workflow '{logical_name}' → id: {wf_id}")
        return wf_id

    print(f"  ERROR creating '{logical_name}': {resp.status_code} {resp.text[:300]}")
    return None


def create_agent():
    """Create the Fire TV Support Specialist agent in Agent Builder."""
    agent = {
        "id": "firetv-support-specialist",
        "name": "Fire TV Support Specialist",
        "description": (
            "I'm an Amazon Fire TV support specialist. I help customers troubleshoot "
            "power issues, remote pairing, streaming/network problems, and app crashes, "
            "and I remember exactly which steps a customer has already tried."
        ),
        "labels": ["firetv", "support", "firetv-remediation-demo"],
        "avatar_color": "#FF9900",
        "avatar_symbol": "FTV",
        "configuration": {
            "instructions": (
                "You are an expert Amazon Fire TV support specialist. Help customers with:\n"
                "- Power and boot failures\n"
                "- Remote pairing and connectivity\n"
                "- Streaming lag and network/bandwidth issues\n"
                "- App crashes and firmware updates\n"
                "- Warranty status and remediation options\n\n"
                "Be concise, empathetic, and practical. Never ask a customer to repeat a "
                "troubleshooting step they've already told you they tried — check their "
                "history first. If every step in the troubleshooting ladder has been tried "
                "and failed and the device is out of warranty, offer the 10% off next "
                "purchase remediation immediately instead of more troubleshooting."
            ),
            "tools": [],
        },
    }

    # POST creates a new agent (id lives in the body here).
    resp = requests.post(
        f"{KB_URL}/api/agent_builder/agents",
        headers=HEADERS,
        json=agent,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        print(f"  ✓ Created agent: {agent['name']} (id: {agent['id']})")
        return agent["id"]

    if resp.status_code == 409 or "already exists" in resp.text:
        # Already exists — PUT updates it. The id lives in the URL, not the body.
        update_body = {k: v for k, v in agent.items() if k != "id"}
        resp = requests.put(
            f"{KB_URL}/api/agent_builder/agents/{agent['id']}",
            headers=HEADERS,
            json=update_body,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            print(f"  ✓ Updated agent: {agent['name']} (id: {agent['id']})")
            return agent["id"]

    print(f"  WARNING: Could not create custom agent ({resp.status_code}): {resp.text[:200]}")
    print(f"  Falling back to elastic-ai-agent")
    return "elastic-ai-agent"


def main():
    print("=== Fire TV Remediation Demo — Workflows Setup ===\n")

    # Step 1: Create support agent
    print("Creating Fire TV Support Specialist agent...")
    agent_id = create_agent()
    print()

    # Step 2: Register workflows
    print("Registering Kibana Workflows...")
    base = os.path.dirname(os.path.abspath(__file__))

    episodic_id = register_workflow(
        os.path.join(base, "workflows", "generate_firetv_episodic_memory.yaml"),
        "episodic",
    )
    semantic_id = register_workflow(
        os.path.join(base, "workflows", "generate_firetv_semantic_memory.yaml"),
        "semantic",
    )
    procedural_id = register_workflow(
        os.path.join(base, "workflows", "generate_firetv_procedural_memory.yaml"),
        "procedural",
    )
    remediation_id = register_workflow(
        os.path.join(base, "workflows", "generate_firetv_remediation_memory.yaml"),
        "remediation",
    )

    # Step 3: Save IDs for app.py and run_demo.py
    ids = {
        "episodic": episodic_id,
        "semantic": semantic_id,
        "procedural": procedural_id,
        "remediation": remediation_id,
        "agent": agent_id,
    }
    save_ids(ids)
    print(f"\n  Saved workflow IDs to {WORKFLOW_IDS_FILE}")

    print()
    print("=" * 60)
    print("Setup complete!")
    print(f"  Agent ID:              {agent_id}")
    print(f"  Episodic workflow:     {episodic_id}")
    print(f"  Semantic workflow:     {semantic_id}")
    print(f"  Procedural workflow:   {procedural_id}")
    print(f"  Remediation workflow:  {remediation_id}")
    print()
    print("Next: run python3 run_demo.py to create conversations and generate memories")


if __name__ == "__main__":
    main()
