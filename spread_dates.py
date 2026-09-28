#!/usr/bin/env python3
"""
Spread memory timestamps across a realistic date range.

Demo seeding creates all episodic/semantic memories in one workflow run, so every
doc gets stamped with the same ingest time. This rewrites session_date (episodic)
and last_updated (semantic) to a plausible multi-week timeline so the demo data
doesn't look like it was generated in one sitting. Run after seeding/reset.
"""

import os
from elasticsearch import Elasticsearch

for line in open(os.path.join(os.path.dirname(__file__), "variables.env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

ES_URL = os.environ["ES_URL"]
ES_API_KEY = os.environ.get("ES_API_KEY") or os.environ["ES_ADMIN_API_KEY"]
es = Elasticsearch(ES_URL, api_key=ES_API_KEY)

# Per-user episode timelines (chronological, spread over ~6 weeks).
# Ordering matches original ingest order so summaries still make sense.
EPISODE_DATES = {
    "alice_chen": ["2026-08-11T14:23:00Z", "2026-08-19T09:47:00Z", "2026-09-02T16:05:00Z"],
    "bob_smith": ["2026-08-13T10:12:00Z", "2026-08-27T15:38:00Z", "2026-09-08T11:26:00Z"],
    "carol_johnson": ["2026-08-14T13:55:00Z", "2026-08-24T10:31:00Z", "2026-09-04T15:17:00Z", "2026-09-22T02:20:46Z"],
}

# Semantic memories pinned to dates shortly after the episode that produced them.
SEMANTIC_DATES = {
    "alice_chen_vector_search": "2026-08-11T14:31:00Z",
    "alice_chen_serverless_pricing": "2026-08-19T09:58:00Z",
    "alice_chen_python_client": "2026-09-02T16:14:00Z",
    "bob_smith_solr_migration": "2026-08-13T10:24:00Z",
    "bob_smith_cluster_architecture": "2026-08-27T15:49:00Z",
    "bob_smith_monitoring_alerting": "2026-09-08T11:33:00Z",
    "carol_johnson_elser_semantic_search": "2026-09-04T15:28:00Z",
    "carol_johnson_competitive_analysis": "2026-09-22T02:41:00Z",
    "carol_johnson_cost_estimation": "2026-09-22T02:52:00Z",
    "carol_johnson_ai_features": "2026-09-22T03:04:00Z",
}


def spread_episodes():
    r = es.search(index="episodic_memory", size=200, source=["user_id", "session_date"])
    by_user = {}
    for h in r["hits"]["hits"]:
        s = h["_source"]
        if "session_date" not in s:
            continue  # skip test/junk docs
        by_user.setdefault(s["user_id"], []).append((s["session_date"], h["_id"]))

    for user, docs in by_user.items():
        dates = EPISODE_DATES.get(user)
        if not dates:
            print(f"episodic: no timeline defined for {user}, skipping")
            continue
        docs.sort()  # keep original ingest order
        for (old, doc_id), new in zip(docs, dates):
            es.update(index="episodic_memory", id=doc_id, doc={"session_date": new})
            print(f"episodic {doc_id[:8]} ({user}): {old} -> {new}")


def spread_semantic():
    for doc_id, new in SEMANTIC_DATES.items():
        try:
            es.update(index="semantic_memory", id=doc_id, doc={"last_updated": new})
            print(f"semantic {doc_id}: -> {new}")
        except Exception as e:
            print(f"semantic {doc_id}: skipped ({e.__class__.__name__})")


if __name__ == "__main__":
    spread_episodes()
    spread_semantic()
    print("Done.")
