#!/usr/bin/env python3
"""Bulk-generate synthetic episodic memories via Haiku, at volume, so entity
clustering has enough density to produce real clusters (and real noise).

Each episode is one Haiku call that both writes a synthetic support
conversation AND extracts the episodic-memory fields in a single shot
(summary/topics/entities/valence/importance/action_items) — half the calls
of generate-then-extract. Jina clustering-task embeddings are batched
separately. Everything lands in episodic_memory via the ES bulk helper.

Usage:
  python3 generate_bulk_episodes.py --count 60     # smoke test, ~20/persona
  python3 generate_bulk_episodes.py --count 2400   # full run, ~800/persona
"""

import os
import sys
import json
import time
import random
import argparse
import uuid
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from entity_clustering import call_haiku, embed_for_clustering

ES_URL = os.environ.get("ES_URL", "https://demo-c4ecc8.es.us-east-1.aws.elastic.cloud")
ES_API_KEY = os.environ.get("ES_ADMIN_API_KEY")

DATE_RANGE_START = datetime(2026, 3, 1, tzinfo=timezone.utc)
DATE_RANGE_END = datetime(2026, 9, 28, tzinfo=timezone.utc)

PERSONAS = {
    "alice_chen": {
        "user_name": "Alice Chen",
        "description": "a data scientist evaluating Elasticsearch for ML/vector search workloads",
        "topics": [
            ("kNN search fundamentals and similarity metrics", 4),
            ("HNSW performance tuning at scale", 3),
            ("serverless pricing for vector workloads", 3),
            ("Python elasticsearch-py client, async bulk indexing", 3),
            ("LangChain / RAG pipeline integration", 3),
            ("hybrid search with RRF", 2),
            ("embedding model choice (Jina, OpenAI, Cohere)", 2),
            ("shard sizing for ML workloads", 2),
            ("benchmarking query latency (p50/p95/p99)", 2),
            ("ELSER vs dense vector tradeoffs", 2),
            ("vector quantization (BBQ, int8)", 1),
            ("multi-modal embeddings", 1),
            ("approximate vs exact kNN", 1),
            ("filtering combined with kNN queries", 1),
            ("monitoring ML inference endpoints", 1),
            ("reducing embedding dimensionality", 1),
            ("what's a good coffee shop near the office", 0.4),
            ("planning a weekend hiking trip", 0.4),
        ],
    },
    "bob_smith": {
        "user_name": "Bob Smith",
        "description": "a DevOps engineer migrating a large deployment from Apache Solr to Elasticsearch",
        "topics": [
            ("Solr to Elasticsearch schema migration", 4),
            ("cluster architecture and sizing for 50M+ docs", 3),
            ("hot-warm-cold tier design", 3),
            ("monitoring and PagerDuty alerting", 3),
            ("snapshot lifecycle management and backups", 2),
            ("cross-cluster replication for disaster recovery", 2),
            ("TLS, LDAP, and field-level security", 2),
            ("role-based access control setup", 2),
            ("shard allocation strategy", 2),
            ("index lifecycle management policies", 2),
            ("rolling upgrades with zero downtime", 1),
            ("debugging slow queries and profiling", 2),
            ("capacity planning for growth", 1),
            ("Kibana dashboard setup", 1),
            ("log ingestion with Beats/Elastic Agent", 1),
            ("reindexing strategies at scale", 1),
            ("dedicated master/data/ingest node roles", 1),
            ("what's the best pizza place downtown", 0.4),
            ("recommend a good sci-fi novel", 0.4),
        ],
    },
    "carol_johnson": {
        "user_name": "Carol Johnson",
        "description": "a startup CTO evaluating search platforms for a growing product",
        "topics": [
            ("competitive analysis vs Algolia, OpenSearch, Typesense", 4),
            ("total cost of ownership at 10k/100k/1M docs", 3),
            ("AI features: ELSER, semantic search, RAG with OpenAI", 3),
            ("Node.js developer experience and documentation quality", 2),
            ("enterprise compliance, SLA, and support tiers", 2),
            ("hybrid search setup (BM25 + vectors)", 2),
            ("vendor lock-in concerns", 2),
            ("time-to-value and onboarding speed", 2),
            ("scaling plans across growth stages", 2),
            ("startup security requirements", 1),
            ("professional services and implementation help", 1),
            ("open-source vs managed cloud tradeoffs", 2),
            ("local development with Docker", 1),
            ("API design and query DSL evaluation", 1),
            ("investor due-diligence technical questions", 1),
            ("hiring engineers with search/ML skills", 1),
            ("favorite productivity apps for founders", 0.4),
            ("good podcasts for startup founders", 0.4),
        ],
    },
}


def random_session_date():
    delta = DATE_RANGE_END - DATE_RANGE_START
    seconds = random.uniform(0, delta.total_seconds())
    return (DATE_RANGE_START + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_conversation(messages):
    return "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])


def generate_episode(user_id, persona, topic):
    prompt = f"""You are generating a SYNTHETIC customer support conversation for an Elasticsearch product demo (not a real user, no real data).

Persona: {persona['user_name']}, {persona['description']}
Topic seed: {topic}

Write a realistic 2-4 turn conversation between this persona (role "user") and an Elasticsearch support agent (role "assistant") about the topic seed above. The assistant must NOT address the user by name or use greetings — jump straight into the technical content. Then extract structured metadata about it.

Return ONLY valid JSON, no other text, with this exact shape:
{{
  "messages": [{{"role": "user", "content": "..."}}, {{"role": "assistant", "content": "..."}}],
  "summary": "2-3 sentence summary of what was discussed and key outcomes",
  "key_entities": ["entity1", "entity2"],
  "topics": ["topic1", "topic2"],
  "emotional_valence": "positive" or "neutral" or "negative",
  "importance_score": 7.5,
  "action_items": ["action1"]
}}"""

    for attempt in range(2):
        try:
            data = json.loads(call_haiku(prompt))
            messages = data["messages"]
            raw_text = format_conversation(messages)
            conversation_id = f"bulk_{user_id}_{uuid.uuid4().hex[:10]}"
            return {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "user_name": persona["user_name"],
                "session_date": random_session_date(),
                "topic": data["topics"][0] if data.get("topics") else topic,
                "summary": data["summary"],
                "key_entities": data.get("key_entities", []),
                "topics": data.get("topics", [topic]),
                "emotional_valence": data.get("emotional_valence", "neutral"),
                "importance_score": float(data.get("importance_score", 5.0)),
                "action_items": data.get("action_items", []),
                "raw_conversation_text": raw_text,
                "memory_source": "bulk_synthetic",
            }
        except Exception as e:
            if attempt == 1:
                print(f"  FAILED episode for {user_id}/{topic}: {e}")
                return None
            time.sleep(1)


def pick_topics(persona, count):
    topics, weights = zip(*persona["topics"])
    return random.choices(topics, weights=weights, k=count)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=60, help="Total episodes across all personas")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if not ES_API_KEY:
        print("ERROR: ES_ADMIN_API_KEY required")
        sys.exit(1)

    es = Elasticsearch(ES_URL, api_key=ES_API_KEY)

    per_persona = args.count // len(PERSONAS)
    remainder = args.count - per_persona * len(PERSONAS)

    jobs = []
    for i, (user_id, persona) in enumerate(PERSONAS.items()):
        n = per_persona + (remainder if i == 0 else 0)
        for topic in pick_topics(persona, n):
            jobs.append((user_id, persona, topic))
    random.shuffle(jobs)

    print(f"Generating {len(jobs)} episodes with {args.workers} workers...")
    episodes = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(generate_episode, uid, persona, topic) for uid, persona, topic in jobs]
        for fut in as_completed(futures):
            result = fut.result()
            done += 1
            if result:
                episodes.append(result)
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} generated ({len(episodes)} ok)")

    print(f"\nEmbedding {len(episodes)} episodes for clustering (Jina, batched)...")
    texts = [f"{ep['summary']}\n\n{ep['raw_conversation_text']}"[:4000] for ep in episodes]
    vectors = embed_for_clustering(texts, batch_size=64)
    for ep, vec in zip(episodes, vectors):
        ep["cluster_vector"] = vec

    print(f"Bulk indexing {len(episodes)} episodes into episodic_memory...")
    actions = [
        {"_op_type": "index", "_index": "episodic_memory", "_id": ep["conversation_id"], "_source": ep}
        for ep in episodes
    ]
    success, errors = bulk(es, actions, raise_on_error=False, chunk_size=500)
    print(f"Indexed: {success} ok, {len(errors)} errors")
    if errors:
        print(json.dumps(errors[:3], indent=2))

    print("\nDone. Run entity_clustering.compute_clusters(user_id) per persona to (re)cluster.")


if __name__ == "__main__":
    main()
