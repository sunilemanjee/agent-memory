#!/usr/bin/env python3
"""
Reset the demo to its pre-live-demo baseline state for a specific user (or all users).

What it does:
  1. Deletes episodic memory docs created via live chat (memory_source == "kibana_workflow")
     that are NOT in demo_seed_manifest.json — leaves the bulk-generated corpus
     (memory_source == "bulk_synthetic") untouched.
  2. Restores semantic_memory + procedural_memory docs to the exact snapshot in
     demo_baseline_manifest.json (overwrite in place; delete anything not in the
     snapshot). This does NOT re-run the Kibana workflows — generate-semantic-memory
     merges old+new facts and can never fully "unlearn" a live-chat episode once
     merged in, so a snapshot restore is the only way to guarantee an exact revert.

Usage:
  python3 reset_demo.py                        # reset all users
  python3 reset_demo.py --user carol_johnson   # reset one user
"""

import os
import sys
import json
import argparse
import requests

ES_URL = os.environ.get("ES_URL")
API_KEY = os.environ.get("ES_ADMIN_API_KEY")

if not ES_URL or not API_KEY:
    print("ERROR: ES_URL and ES_ADMIN_API_KEY environment variables required")
    sys.exit(1)

ES_HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "Content-Type": "application/json",
}

BASE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(BASE, "demo_seed_manifest.json")
BASELINE_PATH = os.path.join(BASE, "demo_baseline_manifest.json")

with open(MANIFEST_PATH) as f:
    MANIFEST = json.load(f)
with open(BASELINE_PATH) as f:
    BASELINE = json.load(f)

USER_META = {
    "alice_chen":    {"name": "Alice Chen"},
    "bob_smith":     {"name": "Bob Smith"},
    "carol_johnson": {"name": "Carol Johnson"},
}


def delete_extra_episodes(user_id):
    """Delete live-chat episodic docs for user that are not in the seed manifest.
    Never touches memory_source == 'bulk_synthetic' docs (the generated corpus)."""
    seed_ids = set(MANIFEST["episodic_ids"].get(user_id, []))

    resp = requests.get(
        f"{ES_URL}/episodic_memory/_search",
        headers=ES_HEADERS,
        json={"query": {"term": {"user_id": user_id}}, "size": 10000, "_source": ["memory_source"]},
    )
    hits = resp.json().get("hits", {}).get("hits", [])
    extra_ids = [
        h["_id"] for h in hits
        if h["_id"] not in seed_ids and h["_source"].get("memory_source") != "bulk_synthetic"
    ]

    if not extra_ids:
        print(f"  {user_id}: no live-chat episodes to delete")
        return 0

    for doc_id in extra_ids:
        r = requests.delete(f"{ES_URL}/episodic_memory/_doc/{doc_id}", headers=ES_HEADERS)
        status = "deleted" if r.status_code == 200 else f"ERROR {r.status_code}"
        print(f"  {user_id}: {doc_id[:16]}... → {status}")

    return len(extra_ids)


def restore_baseline(index, user_id):
    """Overwrite index docs for user_id with the exact baseline snapshot;
    delete any doc for that user not present in the snapshot."""
    snapshot = BASELINE[index].get(user_id, {})

    resp = requests.get(
        f"{ES_URL}/{index}/_search",
        headers=ES_HEADERS,
        json={"query": {"term": {"user_id": user_id}}, "size": 100, "_source": False},
    )
    current_ids = {h["_id"] for h in resp.json().get("hits", {}).get("hits", [])}

    for doc_id, source in snapshot.items():
        r = requests.put(f"{ES_URL}/{index}/_doc/{doc_id}", headers=ES_HEADERS, json=source)
        print(f"    {index}/{doc_id}: restored ({r.status_code})")

    for doc_id in current_ids - set(snapshot.keys()):
        r = requests.delete(f"{ES_URL}/{index}/_doc/{doc_id}", headers=ES_HEADERS)
        print(f"    {index}/{doc_id}: removed, not in baseline ({r.status_code})")


def reset_user(user_id):
    print(f"\n=== Resetting {user_id} ===")

    deleted = delete_extra_episodes(user_id)
    print(f"  Deleted {deleted} live-chat episode(s)")

    if deleted > 0:
        print("  Restoring semantic + procedural memory to pre-demo baseline...")
        restore_baseline("semantic_memory", user_id)
        restore_baseline("procedural_memory", user_id)
        print("  Restored.")
    else:
        print("  No live-chat episodes found — semantic/procedural memory unchanged.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", choices=list(USER_META.keys()), help="Reset a single user (default: all)")
    args = parser.parse_args()

    users = [args.user] if args.user else list(USER_META.keys())

    print("=== Demo Reset ===")
    for user_id in users:
        reset_user(user_id)

    print("\nDone. Refresh the UI to see the restored state.")


if __name__ == "__main__":
    main()
