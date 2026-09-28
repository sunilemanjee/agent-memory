#!/usr/bin/env python3
"""
Reset the demo to its seeded state for a specific user (or all users).

What it does:
  1. Deletes any episodic memory docs for the user NOT in demo_seed_manifest.json
     (i.e. removes episodes created during live chat demos)
  2. Re-triggers generate-semantic-memory workflow for all that user's entity clusters
  3. Re-triggers generate-procedural-memory workflow for all that user's contexts

Usage:
  python3 reset_demo.py                        # reset all users
  python3 reset_demo.py --user carol_johnson   # reset one user
"""

import os
import sys
import json
import time
import argparse
import requests

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

SEMANTIC_WF = WF_IDS.get("semantic", "generate-semantic-memory")
PROCEDURAL_WF = WF_IDS.get("procedural", "generate-procedural-memory")

USER_META = {
    "alice_chen":    {"name": "Alice Chen",    "entities": [("vector_search","concept"),("serverless_pricing","product"),("python_client","product")],    "procedures": ["knn_benchmarking","serverless_cost_estimation","python_bulk_indexing"]},
    "bob_smith":     {"name": "Bob Smith",     "entities": [("solr_migration","concept"),("cluster_architecture","concept"),("monitoring_alerting","concept")], "procedures": ["solr_to_elasticsearch_migration","cluster_sizing_and_architecture","slow_query_debugging"]},
    "carol_johnson": {"name": "Carol Johnson", "entities": [("competitive_analysis","concept"),("cost_estimation","concept"),("elser_semantic_search","product")], "procedures": ["vendor_evaluation","tco_calculation","hybrid_search_setup"]},
}


def delete_extra_episodes(user_id):
    """Delete episodic docs for user that are not in the seed manifest."""
    seed_ids = set(MANIFEST["episodic_ids"].get(user_id, []))

    resp = requests.get(
        f"{ES_URL}/episodic_memory/_search",
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
        r = requests.delete(f"{ES_URL}/episodic_memory/_doc/{doc_id}", headers=ES_HEADERS)
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


def reset_user(user_id):
    print(f"\n=== Resetting {user_id} ===")

    deleted = delete_extra_episodes(user_id)
    print(f"  Deleted {deleted} extra episode(s)")

    if deleted > 0:
        print("  Waiting 5s before re-triggering workflows...")
        time.sleep(5)
        retrigger_semantic(user_id)
        retrigger_procedural(user_id)
        print(f"  Workflows re-triggered. Semantic + procedural will update in ~30s.")
    else:
        print("  No extra episodes found — semantic/procedural memory unchanged.")


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
