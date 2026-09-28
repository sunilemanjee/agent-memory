#!/usr/bin/env python3
"""
Reset the Fire TV remediation demo to its seeded state for a specific user (or all users).

What it does:
  1. Deletes any episodic memory docs for the user NOT in demo_seed_manifest.json
     (i.e. removes episodes created during live chat demos)
  2. Re-triggers generate_firetv_semantic_memory workflow for all that user's entity clusters
  3. Re-triggers generate_firetv_procedural_memory workflow for all that user's contexts
  4. Re-triggers generate_firetv_remediation_memory workflow for that user's issue ladder

Usage:
  python3 reset_demo.py                       # reset all users
  python3 reset_demo.py --user jordan_price   # reset one user
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone

ES_URL = os.environ.get("ES_URL")
API_KEY = os.environ.get("ES_ADMIN_API_KEY")
KB_URL = ES_URL.replace(".es.", ".kb.") if ES_URL else ""

if not ES_URL or not API_KEY:
    print("ERROR: ES_URL and ES_ADMIN_API_KEY environment variables required")
    sys.exit(1)

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}
ES_HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "Content-Type": "application/json",
}

BASE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(BASE, "demo_seed_manifest.json")
WF_IDS_PATH = os.path.join(BASE, "workflow_ids.json")

# Load manifest and workflow IDs
with open(MANIFEST_PATH) as f:
    MANIFEST = json.load(f)

WF_IDS = {}
if os.path.exists(WF_IDS_PATH):
    with open(WF_IDS_PATH) as f:
        WF_IDS = json.load(f)

SEMANTIC_WF = WF_IDS.get("semantic", "generate_firetv_semantic_memory")
PROCEDURAL_WF = WF_IDS.get("procedural", "generate_firetv_procedural_memory")
REMEDIATION_WF = WF_IDS.get("remediation", "generate_firetv_remediation_memory")

LADDER_STEPS = {
    "power_failure": "power cycle by unplugging for 30 seconds, factory reset via remote button combination, test a different power adapter and outlet, escalate to hardware replacement",
    "remote_network": "re-pair the remote to the Fire TV, restart the router and check available bandwidth, move the Fire TV closer to the router or use an ethernet adapter, escalate to network diagnostics",
    "app_crash": "clear app cache and update Fire TV firmware, uninstall and reinstall the affected app, escalate to firmware compatibility team",
}

USER_META = {
    "jordan_price": {
        "name": "Jordan Price",
        "entities": [("power_failure", "concept")],
        "procedures": ["power_failure"],
        "remediation": {
            "issue_context": "power_failure",
            "device": "Amazon Fire TV",
            "purchase_date": "2025-08-01",
            "warranty_expiration_date": "2026-08-01",
        },
    },
    "morgan_lee": {
        "name": "Morgan Lee",
        "entities": [("remote_pairing", "concept"), ("streaming_lag", "concept")],
        "procedures": ["remote_network"],
        "remediation": {
            "issue_context": "remote_network",
            "device": "Amazon Fire TV",
            "purchase_date": "2026-06-01",
            "warranty_expiration_date": "2027-06-01",
        },
    },
    "priya_nair": {
        "name": "Priya Nair",
        "entities": [("app_crash", "concept")],
        "procedures": ["app_crash"],
        "remediation": {
            "issue_context": "app_crash",
            "device": "Amazon Fire TV",
            "purchase_date": "2026-05-01",
            "warranty_expiration_date": "2027-05-01",
        },
    },
}


def delete_extra_episodes(user_id):
    """Delete episodic docs for user that are not in the seed manifest."""
    seed_ids = set(MANIFEST["episodic_ids"].get(user_id, []))

    resp = requests.get(
        f"{ES_URL}/firetv_episodic_memory/_search",
        headers=ES_HEADERS,
        json={"query": {"term": {"user_id": user_id}}, "size": 100, "_source": False},
    )
    hits = resp.json().get("hits", {}).get("hits", [])
    all_ids = {h["_id"] for h in hits}
    extra_ids = all_ids - seed_ids

    if not extra_ids:
        print(f"  {user_id}: no extra episodes to delete")
        return 0

    for doc_id in extra_ids:
        r = requests.delete(f"{ES_URL}/firetv_episodic_memory/_doc/{doc_id}", headers=ES_HEADERS)
        status = "deleted" if r.status_code == 200 else f"ERROR {r.status_code}"
        print(f"  {user_id}: {doc_id[:16]}... → {status}")

    return len(extra_ids)


def retrigger_semantic(user_id):
    """Re-run semantic memory workflow for all entity clusters of a user."""
    meta = USER_META[user_id]
    user_name = meta["name"]
    print(f"  Re-triggering semantic workflows for {user_name}...")
    for entity_name, entity_type in meta["entities"]:
        resp = requests.post(
            f"{KB_URL}/api/workflows/workflow/{SEMANTIC_WF}/run",
            headers=HEADERS,
            json={"inputs": {"user_id": user_id, "user_name": user_name, "entity_name": entity_name, "entity_type": entity_type}},
            timeout=60,
        )
        status = resp.status_code
        print(f"    semantic/{entity_name}: {status}")
        time.sleep(2)


def retrigger_procedural(user_id):
    """Re-run procedural memory workflow for all contexts of a user."""
    meta = USER_META[user_id]
    user_name = meta["name"]
    print(f"  Re-triggering procedural workflows for {user_name}...")
    for ctx in meta["procedures"]:
        resp = requests.post(
            f"{KB_URL}/api/workflows/workflow/{PROCEDURAL_WF}/run",
            headers=HEADERS,
            json={"inputs": {"user_id": user_id, "user_name": user_name, "procedure_context": ctx}},
            timeout=60,
        )
        status = resp.status_code
        print(f"    procedural/{ctx}: {status}")
        time.sleep(2)


def retrigger_remediation(user_id):
    """Re-run remediation memory workflow for a user's issue ladder."""
    meta = USER_META[user_id]
    user_name = meta["name"]
    rem = meta["remediation"]
    print(f"  Re-triggering remediation workflow for {user_name}...")
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow/{REMEDIATION_WF}/run",
        headers=HEADERS,
        json={
            "inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "issue_context": rem["issue_context"],
                "device": rem["device"],
                "purchase_date": rem["purchase_date"],
                "warranty_expiration_date": rem["warranty_expiration_date"],
                "ladder_steps": LADDER_STEPS[rem["issue_context"]],
                "current_date": datetime.now(timezone.utc).date().isoformat(),
            }
        },
        timeout=60,
    )
    status = resp.status_code
    print(f"    remediation/{rem['issue_context']}: {status}")
    time.sleep(2)


def reset_user(user_id):
    print(f"\n=== Resetting {user_id} ===")

    deleted = delete_extra_episodes(user_id)
    print(f"  Deleted {deleted} extra episode(s)")

    if deleted > 0:
        print("  Waiting 5s before re-triggering workflows...")
        time.sleep(5)
        retrigger_semantic(user_id)
        retrigger_procedural(user_id)
        retrigger_remediation(user_id)
        print(f"  Workflows re-triggered. Semantic/procedural/remediation will update in ~30s.")
    else:
        print("  No extra episodes found — re-triggering remediation only to keep ladder state fresh.")
        retrigger_remediation(user_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", choices=list(USER_META.keys()), help="Reset a single user (default: all)")
    args = parser.parse_args()

    users = [args.user] if args.user else list(USER_META.keys())

    print("=== Demo Reset ===")
    for user_id in users:
        reset_user(user_id)

    print("\nDone. Refresh the UI in ~30s to see the restored state.")


if __name__ == "__main__":
    main()
