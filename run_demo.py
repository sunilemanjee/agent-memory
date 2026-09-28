#!/usr/bin/env python3
"""
Demo script: Creates Agent Builder conversations and triggers Kibana Workflows
to generate episodic and semantic memories in Elasticsearch.

Flow:
  1. Load demo users and their conversation prompts
  2. Have each conversation with the ES Support Analyst via Agent Builder API
  3. Trigger generate-episodic-memory workflow for each conversation
  4. Trigger generate-semantic-memory workflow for each user/entity cluster
"""

import os
import sys
import json
import time
import requests

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
EPISODIC_WORKFLOW_ID = _wf_ids.get("episodic", "generate-episodic-memory")
SEMANTIC_WORKFLOW_ID = _wf_ids.get("semantic", "generate-semantic-memory")
PROCEDURAL_WORKFLOW_ID = _wf_ids.get("procedural", "generate-procedural-memory")

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}

# Demo users and their conversation scripts
DEMO_USERS = [
    {
        "user_id": "alice_chen",
        "user_name": "Alice Chen",
        "conversations": [
            {
                "messages": [
                    "How does kNN search work in Elasticsearch? I'm evaluating it for a machine learning project with about 1 million vectors.",
                    "What similarity metrics are available? We're using cosine similarity in our current system.",
                    "What's the expected query latency at that scale with HNSW?",
                ]
            },
            {
                "messages": [
                    "Can you explain serverless pricing for vector workloads? I need to budget for 500k document embeddings.",
                    "Are there any hidden costs I should know about — like data transfer or ingest fees?",
                ]
            },
            {
                "messages": [
                    "How do I use the Python elasticsearch client for bulk vector indexing? I'm using asyncio.",
                    "Does it integrate with LangChain for building RAG pipelines?",
                ]
            },
        ],
    },
    {
        "user_id": "bob_smith",
        "user_name": "Bob Smith",
        "conversations": [
            {
                "messages": [
                    "We're migrating from Apache Solr to Elasticsearch. What are the main schema differences I need to know about?",
                    "How do I translate Solr's dismax queries to Elasticsearch equivalents?",
                ]
            },
            {
                "messages": [
                    "What's the recommended cluster architecture for 50 million documents with high availability requirements?",
                    "How should I configure hot-warm-cold tiers for time-series log data?",
                ]
            },
            {
                "messages": [
                    "How do I set up monitoring for slow queries in Elasticsearch? We're having some latency spikes.",
                    "Can Elasticsearch alerting integrate with PagerDuty?",
                ]
            },
        ],
    },
    {
        "user_id": "carol_johnson",
        "user_name": "Carol Johnson",
        "conversations": [
            {
                "messages": [
                    "I'm evaluating Elasticsearch vs Algolia vs OpenSearch for a startup. We have about 100k products and need full-text plus filtering.",
                    "What's Elasticsearch's main advantage for AI-powered search compared to Algolia?",
                ]
            },
            {
                "messages": [
                    "Can you help me estimate total cost of ownership for Elasticsearch Cloud at different scales — 10k, 100k, and 1M documents?",
                    "What's the minimum viable setup for a startup on a budget?",
                ]
            },
            {
                "messages": [
                    "Tell me about ELSER — the Elastic Learned Sparse Encoder. How does it compare to OpenAI embeddings for semantic search?",
                    "Can I combine ELSER with vector search for a hybrid approach?",
                ]
            },
        ],
    },
]

# Procedural contexts for procedural memory extraction
PROCEDURAL_CONTEXTS = {
    "alice_chen": [
        "knn_benchmarking",
        "serverless_cost_estimation",
        "python_bulk_indexing",
    ],
    "bob_smith": [
        "solr_to_elasticsearch_migration",
        "cluster_sizing_and_architecture",
        "slow_query_debugging",
    ],
    "carol_johnson": [
        "vendor_evaluation",
        "tco_calculation",
        "hybrid_search_setup",
    ],
}

# Entity clusters for semantic memory distillation
ENTITY_CLUSTERS = {
    "alice_chen": [
        ("vector_search", "concept"),
        ("serverless_pricing", "product"),
        ("python_client", "product"),
    ],
    "bob_smith": [
        ("solr_migration", "concept"),
        ("cluster_architecture", "concept"),
        ("monitoring_alerting", "concept"),
    ],
    "carol_johnson": [
        ("competitive_analysis", "concept"),
        ("cost_estimation", "concept"),
        ("elser_semantic_search", "product"),
    ],
}


def have_conversation(user, convo_script):
    """Have a multi-turn conversation with the ES Support Analyst agent."""
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


def trigger_episodic_workflow(conversation_id, user_id, user_name):
    """Trigger the generate-episodic-memory workflow for a conversation."""
    resp = requests.post(
        f"{KB_URL}/api/workflows/workflow/{EPISODIC_WORKFLOW_ID}/run",
        headers=HEADERS,
        json={
            "inputs": {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "user_name": user_name,
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


def trigger_procedural_workflow(user_id, user_name, procedure_context):
    """Trigger the generate-procedural-memory workflow for a user/context."""
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


def trigger_semantic_workflow(user_id, user_name, entity_name, entity_type):
    """Trigger the generate-semantic-memory workflow for a user/entity."""
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
    print("=== Agent Memory Demo: Conversations + Workflows ===\n")

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
                })
            else:
                print(f"    WARNING: No conversation ID returned")
        print()

    print(f"  Created {len(state['conversations'])} conversations\n")

    # Phase 2: Trigger episodic memory workflow for each conversation
    print("Phase 2: Triggering generate-episodic-memory workflow\n")
    print("  (Each workflow: fetches conversation → AI summarizes → indexes to ES)\n")

    for conv in state["conversations"]:
        print(f"  Conversation {conv['convo_index']} for {conv['user_name']}:")
        exec_id = trigger_episodic_workflow(
            conv["conversation_id"],
            conv["user_id"],
            conv["user_name"],
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
    print("Phase 3: Triggering generate-semantic-memory workflow\n")
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
    print("Phase 4: Triggering generate-procedural-memory workflow\n")
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

    save_run_state(state)

    print("\n=== Demo Complete ===")
    print(f"  Conversations created: {len(state['conversations'])}")
    print(f"  Workflows triggered:   {len(state['workflows'])}")
    print()
    print("Open http://localhost:5002 to view memories in the UI")
    print("Kibana: workflows visible at <kibana_url>/app/management/kibana/workflows")


if __name__ == "__main__":
    main()
