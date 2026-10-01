#!/usr/bin/env python3
"""
Flask application for Elasticsearch episodic memory demo.
Requires: ES_URL and ES_ADMIN_API_KEY environment variables.
"""

import os
import json
import socket
import requests
from flask import Flask, render_template, jsonify, request
from elasticsearch import Elasticsearch

# This network cannot complete IPv6 handshakes to api.jina.ai (Cloudflare-fronted),
# so outbound requests hang in SYN_SENT until the connect timeout expires. Force
# IPv4-only DNS resolution process-wide rather than special-casing every caller.
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only_getaddrinfo

# Configuration
ES_URL = os.environ.get("ES_URL", "https://demo-c4ecc8.es.us-east-1.aws.elastic.cloud")
ES_API_KEY = os.environ.get("ES_ADMIN_API_KEY")
KB_URL = ES_URL.replace(".es.", ".kb.")

if not ES_API_KEY:
    raise ValueError("ES_ADMIN_API_KEY environment variable is required")

# Load workflow IDs registered by setup_workflows.py
_WF_IDS_PATH = os.path.join(os.path.dirname(__file__), "workflow_ids.json")
_WF_IDS = {}
if os.path.exists(_WF_IDS_PATH):
    with open(_WF_IDS_PATH) as _f:
        _WF_IDS = json.load(_f)

EPISODIC_WORKFLOW_ID = _WF_IDS.get("episodic", "generate-episodic-memory")
SEMANTIC_WORKFLOW_ID = _WF_IDS.get("semantic", "generate-semantic-memory")
PROCEDURAL_WORKFLOW_ID = _WF_IDS.get("procedural", "generate-procedural-memory")
AGENT_ID = _WF_IDS.get("agent", "elastic-ai-agent")

# Pre-baked demo conversations — never deleted on reset
SEED_CONV_ID = "c8208ca0-7248-4223-b467-e638f8cd0cc4"
SEED_COMP_WITHOUT_ID = "c442c461-6d99-4fd5-802d-2a0d531a8f9e"
SEED_COMP_WITH_ID = "92e06d19-c6b5-42e6-9c72-74d562dc1650"

import entity_clustering

es = Elasticsearch(ES_URL, api_key=ES_API_KEY)
app = Flask(__name__)




@app.route("/")
def index():
    """Serve the main UI."""
    return render_template(
        "index.html",
        kb_url=KB_URL,
        agent_id=AGENT_ID,
        seed_conv_id=SEED_CONV_ID,
        seed_comp_without_id=SEED_COMP_WITHOUT_ID,
        seed_comp_with_id=SEED_COMP_WITH_ID,
    )


@app.route("/api/episodes", methods=["GET"])
def get_episodes():
    """List episodic memories, sorted by session_date descending.
    Accepts optional user_id (server-side filter) and size — the UI's user
    filter used to only slice a small cross-user top-50 fetch client-side,
    which meant any single persona was starved to whatever sliver of that
    tiny batch happened to be theirs, making the whole corpus look like it
    was generated in the same 2-day window."""
    try:
        user_id = request.args.get("user_id")
        size = min(int(request.args.get("size", 300)), 1000)
        query = {"term": {"user_id": user_id}} if user_id else {"match_all": {}}
        result = es.search(
            index="episodic_memory",
            query=query,
            sort=[{"session_date": {"order": "desc"}}],
            size=size,
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/episodes/<doc_id>", methods=["GET"])
def get_episode(doc_id):
    try:
        result = es.get(index="episodic_memory", id=doc_id)
        return jsonify(result["_source"])
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/semantic", methods=["GET"])
def get_semantic():
    """List all semantic memories, sorted by last_updated descending."""
    try:
        result = es.search(
            index="semantic_memory",
            sort=[{"last_updated": {"order": "desc"}}],
            size=50
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["GET"])
def search_memories():
    """Semantic search across episodic and/or semantic memories."""
    query = request.args.get("q", "")
    search_type = request.args.get("type", "both")  # episodic, semantic, or both

    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        results = []

        if search_type in ["episodic", "both"]:
            episodic_result = es.search(
                index="episodic_memory",
                query={"semantic": {"field": "summary", "query": query}},
                size=5
            )
            for hit in episodic_result["hits"]["hits"]:
                hit["_source"]["type"] = "episodic"
                hit["_source"]["score"] = hit["_score"]
                results.append(hit["_source"])

        if search_type in ["semantic", "both"]:
            semantic_result = es.search(
                index="semantic_memory",
                query={"semantic": {"field": "facts", "query": query}},
                size=5
            )
            for hit in semantic_result["hits"]["hits"]:
                hit["_source"]["type"] = "semantic"
                hit["_source"]["score"] = hit["_score"]
                results.append(hit["_source"])

        if search_type == "both":
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/procedural", methods=["GET"])
def get_procedural():
    """List all procedural memories, sorted by last_refined descending."""
    try:
        result = es.search(
            index="procedural_memory",
            sort=[{"last_refined": {"order": "desc"}}],
            size=50
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return memory counts and available users."""
    try:
        episodic_count = es.count(index="episodic_memory")["count"]
        semantic_count = es.count(index="semantic_memory")["count"]
        try:
            procedural_count = es.count(index="procedural_memory")["count"]
        except Exception:
            procedural_count = 0

        return jsonify({
            "episodic_count": episodic_count,
            "semantic_count": semantic_count,
            "procedural_count": procedural_count,
            "users": ["alice_chen", "bob_smith", "carol_johnson"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recall", methods=["GET"])
def recall_memory():
    """Simulate memory recall for a new conversation context."""
    user_id = request.args.get("user_id")
    context = request.args.get("context", "")

    if not user_id or not context:
        return jsonify({"error": "Parameters 'user_id' and 'context' are required"}), 400

    try:
        recalled = {
            "episodic": [],
            "semantic": [],
            "procedural": []
        }

        episodic_result = es.search(
            index="episodic_memory",
            query={"bool": {
                "must": {"semantic": {"field": "summary", "query": context}},
                "filter": {"term": {"user_id": user_id}}
            }},
            size=3
        )
        recalled["episodic"] = [
            {**hit["_source"], "score": hit["_score"]}
            for hit in episodic_result["hits"]["hits"]
        ]

        semantic_result = es.search(
            index="semantic_memory",
            query={"bool": {
                "must": {"semantic": {"field": "facts", "query": context}},
                "filter": {"term": {"user_id": user_id}}
            }},
            size=3
        )
        recalled["semantic"] = [
            {**hit["_source"], "score": hit["_score"]}
            for hit in semantic_result["hits"]["hits"]
        ]

        try:
            procedural_result = es.search(
                index="procedural_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "procedure_text", "query": context}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=3
            )
            recalled["procedural"] = [
                {**hit["_source"], "score": hit["_score"]}
                for hit in procedural_result["hits"]["hits"]
            ]
        except Exception:
            recalled["procedural"] = []

        return jsonify(recalled)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat_with_agent():
    """Send a message to the ES Support Analyst agent."""
    body = request.get_json()
    user_input = body.get("input", "")
    conversation_id = body.get("conversation_id")
    agent_id = body.get("agent_id", AGENT_ID)

    payload = {"input": user_input, "agent_id": agent_id}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }
    try:
        import time as _time
        _t0 = _time.monotonic()
        resp = requests.post(
            f"{KB_URL}/api/agent_builder/converse",
            headers=kb_headers,
            json=payload,
            timeout=500,
        )
        elapsed_ms = int((_time.monotonic() - _t0) * 1000)
        data = resp.json()

        # Detect clarifying question pause
        if data.get("status") == "awaiting_prompt" or (resp.status_code == 200 and not data.get("response", {}).get("message")):
            conv_id = data.get("conversation_id")
            pending_prompts = []
            if conv_id:
                try:
                    conv_resp = requests.get(
                        f"{KB_URL}/api/agent_builder/conversations/{conv_id}",
                        headers=kb_headers, timeout=15
                    )
                    conv_data = conv_resp.json()
                    for rnd in conv_data.get("rounds", []):
                        if rnd.get("pending_prompts"):
                            pending_prompts = rnd["pending_prompts"]
                            break
                except Exception:
                    pass
            return jsonify({
                "conversation_id": conv_id,
                "response": "",
                "time_to_last_token": elapsed_ms,
                "status": "awaiting_prompt",
                "pending_prompts": pending_prompts,
            })

        return jsonify({
            "conversation_id": data.get("conversation_id"),
            "response": data.get("response", {}).get("message", ""),
            "time_to_last_token": elapsed_ms,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trigger_episodic_workflow", methods=["POST"])
def trigger_episodic_workflow():
    """Trigger the generate-episodic-memory Kibana Workflow for a conversation."""
    body = request.get_json()
    conversation_id = body.get("conversation_id")
    user_id = body.get("user_id", "demo_user")
    user_name = body.get("user_name", "Demo User")

    if not conversation_id:
        return jsonify({"error": "conversation_id required"}), 400

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            f"{KB_URL}/api/workflows/workflow/{EPISODIC_WORKFLOW_ID}/run",
            headers=kb_headers,
            json={"inputs": {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "user_name": user_name,
            }},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code not in (200, 201, 202):
            return jsonify({"error": data.get("message", "Workflow failed"), "details": data}), resp.status_code

        print(f"[episodic workflow response] {data}")
        execution_id = data.get("workflowExecutionId") or data.get("execution_id") or data.get("executionId") or data.get("id")
        executions = [{
            "workflow": "episodic-memory",
            "label": "Generate Episodic Memory",
            "execution_id": execution_id,
            "execution_url": (
                f"{KB_URL}/app/workflows/{EPISODIC_WORKFLOW_ID}"
                f"?executionId={execution_id}&stepExecutionId=__overview&tab=executions"
            ) if execution_id else None,
        }]

        # Gate semantic updates to only the entity cluster(s) this conversation
        # actually matches — fetch the conversation text directly (same endpoint
        # the episodic workflow itself uses) rather than waiting on the async
        # workflow to finish indexing, and embed it in the same Jina clustering
        # space as the cached cluster centroids for a cosine-similarity match.
        entities = []
        try:
            conv_resp = requests.get(
                f"{KB_URL}/api/agent_builder/conversations/{conversation_id}",
                headers=kb_headers, timeout=30,
            )
            conv = conv_resp.json() if conv_resp.status_code == 200 else {}
            rounds_text = "\n".join(
                f"{r.get('input', {}).get('message', '')}\n{r.get('response', {}).get('message', '')}"
                for r in conv.get("rounds", [])
            )
            conv_text = f"{conv.get('title', '')}\n{rounds_text}"[:4000]
            entities = entity_clustering.get_relevant_entities(user_id, conv_text)
        except Exception as e:
            print(f"[entity match error] {e}")
        for entity_name, entity_type in entities:
            try:
                sem_resp = requests.post(
                    f"{KB_URL}/api/workflows/workflow/{SEMANTIC_WORKFLOW_ID}/run",
                    headers=kb_headers,
                    json={"inputs": {
                        "user_id": user_id,
                        "user_name": user_name,
                        "entity_name": entity_name,
                        "entity_type": entity_type,
                    }},
                    timeout=120,
                )
                sem_data = sem_resp.json()
                print(f"[semantic workflow response] {sem_data}")
                sem_exec_id = sem_data.get("workflowExecutionId") or sem_data.get("execution_id") or sem_data.get("executionId") or sem_data.get("id")
                executions.append({
                    "workflow": f"semantic-{entity_name}",
                    "label": f"Semantic: {entity_name.replace('_', ' ').title()}",
                    "execution_id": sem_exec_id,
                    "execution_url": (
                        f"{KB_URL}/app/workflows/{SEMANTIC_WORKFLOW_ID}"
                        f"?executionId={sem_exec_id}&stepExecutionId=__overview&tab=executions"
                    ) if sem_exec_id else None,
                })
            except Exception:
                pass

        return jsonify({
            "execution_id": execution_id,
            "execution_url": executions[0]["execution_url"],
            "executions": executions,
            "status": data.get("status", "triggered"),
            "workflow": "generate-episodic-memory",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trigger_semantic_workflow", methods=["POST"])
def trigger_semantic_workflow():
    """Trigger the generate-semantic-memory Kibana Workflow for a user."""
    body = request.get_json()
    user_id = body.get("user_id")
    user_name = body.get("user_name", "Demo User")
    entity_name = body.get("entity_name", "elasticsearch")
    entity_type = body.get("entity_type", "concept")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            f"{KB_URL}/api/workflows/workflow/{SEMANTIC_WORKFLOW_ID}/run",
            headers=kb_headers,
            json={"inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "entity_name": entity_name,
                "entity_type": entity_type,
            }},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code in (200, 201, 202):
            return jsonify({
                "execution_id": data.get("execution_id") or data.get("id"),
                "status": data.get("status", "triggered"),
                "workflow": "generate-semantic-memory",
            })
        return jsonify({"error": data.get("message", "Workflow failed"), "details": data}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clusters/compute", methods=["POST"])
def compute_clusters():
    """Recompute entity clusters for a user from scratch (Jina clustering embeddings + significant_text)."""
    user_id = request.args.get("user_id") or (request.get_json(silent=True) or {}).get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    try:
        return jsonify(entity_clustering.compute_clusters(user_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clusters", methods=["GET"])
def get_clusters():
    """Read cached entity clusters + per-episode 2D projection for a user."""
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    try:
        result = es.search(
            index="entity_clusters",
            query={"term": {"user_id": user_id}},
            size=50,
            sort=[{"member_count": "desc"}],
        )
        clusters = [h["_source"] for h in result["hits"]["hits"]]

        episodes = es.search(
            index="episodic_memory",
            query={"term": {"user_id": user_id}},
            size=1000,
            _source=["cluster_id", "cluster_label", "cluster_vector", "topic", "session_date"],
        )
        hits = episodes["hits"]["hits"]
        docs_with_vector = [h for h in hits if h["_source"].get("cluster_id")]

        projection = {}
        vec_hits = [h for h in docs_with_vector if h["_source"].get("cluster_vector")]
        if len(vec_hits) >= 2:
            import numpy as np
            matrix = np.array([h["_source"]["cluster_vector"] for h in vec_hits], dtype=np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            unit = matrix / norms
            centered = unit - unit.mean(axis=0)
            _, _, vt = np.linalg.svd(centered, full_matrices=False)
            coords = centered @ vt[:3].T
            for i, h in enumerate(vec_hits):
                src = h["_source"]
                projection[h["_id"]] = {
                    "x": float(coords[i][0]),
                    "y": float(coords[i][1]),
                    "z": float(coords[i][2]),
                    "cluster_id": src.get("cluster_id"),
                    "cluster_label": src.get("cluster_label", "noise"),
                    "topic": src.get("topic"),
                }

        return jsonify({
            "user_id": user_id,
            "clusters": clusters,
            "projection": projection,
            "total_episodes": episodes["hits"]["total"]["value"],
            "clustered_episodes": len(docs_with_vector),
            "status": "ok" if clusters else "not_computed",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/episode_graph", methods=["GET"])
def episode_graph():
    """Build a sparse kNN similarity graph over episodic memories using cluster_vector."""
    user_id = request.args.get("user_id")
    limit = min(int(request.args.get("limit", 300)), 1000)
    k = min(int(request.args.get("k", 5)), 20)
    try:
        query = {"term": {"user_id": user_id}} if user_id else {"match_all": {}}
        result = es.search(
            index="episodic_memory",
            query=query,
            size=limit,
            _source=["cluster_vector", "cluster_label", "user_id", "topic", "summary", "importance_score"],
        )
        hits = [h for h in result["hits"]["hits"] if h["_source"].get("cluster_vector")]

        nodes = [{
            "id": h["_id"],
            "user_id": h["_source"].get("user_id"),
            "topic": h["_source"].get("topic"),
            "cluster_label": h["_source"].get("cluster_label", "noise"),
            "importance_score": h["_source"].get("importance_score", 5.0),
        } for h in hits]

        edges = []
        seen_pairs = set()
        if hits:
            import numpy as np
            matrix = np.array([h["_source"]["cluster_vector"] for h in hits], dtype=np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            unit = matrix / norms
            sims = unit @ unit.T
            n = len(hits)
            for i in range(n):
                neighbor_idx = np.argsort(-sims[i])[1:k + 1]
                for j in neighbor_idx:
                    pair = tuple(sorted([hits[i]["_id"], hits[j]["_id"]]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    edges.append({"source": pair[0], "target": pair[1], "weight": float(sims[i][j])})

        return jsonify({"nodes": nodes, "edges": edges})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trigger_procedural_workflow", methods=["POST"])
def trigger_procedural_workflow():
    """Trigger the generate-procedural-memory Kibana Workflow for a user."""
    body = request.get_json()
    user_id = body.get("user_id")
    user_name = body.get("user_name", "Demo User")
    procedure_context = body.get("procedure_context", "general_assistance")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            f"{KB_URL}/api/workflows/workflow/{PROCEDURAL_WORKFLOW_ID}/run",
            headers=kb_headers,
            json={"inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "procedure_context": procedure_context,
            }},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code in (200, 201, 202):
            return jsonify({
                "execution_id": data.get("execution_id") or data.get("id"),
                "status": data.get("status", "triggered"),
                "workflow": "generate-procedural-memory",
            })
        return jsonify({"error": data.get("message", "Workflow failed"), "details": data}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/workflow_status", methods=["GET"])
def workflow_status():
    """Proxy Kibana execution status for a specific workflow execution."""
    workflow_id = request.args.get("workflow_id")
    execution_id = request.args.get("execution_id")

    if not workflow_id or not execution_id:
        return jsonify({"error": "workflow_id and execution_id required"}), 400

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
    }
    try:
        resp = requests.get(
            f"{KB_URL}/api/workflows/workflow/{workflow_id}/executions",
            headers=kb_headers,
            params={"size": 50},
            timeout=15,
        )
        data = resp.json()
        executions = data.get("results", [])
        for ex in executions:
            if ex.get("id") == execution_id:
                return jsonify({
                    "execution_id": execution_id,
                    "status": ex.get("status", "unknown"),
                    "started_at": ex.get("startedAt"),
                    "finished_at": ex.get("finishedAt"),
                    "duration": ex.get("duration"),
                    "error": ex.get("error"),
                })
        return jsonify({"execution_id": execution_id, "status": "pending"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/comparison_context", methods=["GET"])
def comparison_context():
    """Recall memories and return augmented message — no LLM call, fast ES only."""
    user_id = request.args.get("user_id", "alice_chen")
    user_name = request.args.get("user_name", "User")
    query = request.args.get("query", "")
    memory_types = request.args.getlist("memory_types") or ["semantic"]

    recalled = {"episodic": [], "semantic": [], "procedural": []}

    if "episodic" in memory_types:
        try:
            res = es.search(
                index="episodic_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "summary", "query": query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=3
            )
            recalled["episodic"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[context] episodic: {e}")

    if "semantic" in memory_types:
        try:
            res = es.search(
                index="semantic_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "facts", "query": query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=3
            )
            recalled["semantic"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[context] semantic: {e}")

    if "procedural" in memory_types:
        try:
            res = es.search(
                index="procedural_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "procedure_text", "query": query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=2
            )
            recalled["procedural"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[context] procedural: {e}")

    lines = [f"You have the following memory context about {user_name}. Use it to personalize your response.\n"]
    if recalled["episodic"]:
        lines.append("Past conversation episodes:")
        for ep in recalled["episodic"]:
            lines.append(f"  - {ep.get('summary', '')}")
    if recalled["semantic"]:
        lines.append("Standing knowledge about this user:")
        for sm in recalled["semantic"]:
            lines.append(f"  - [{sm.get('entity_name', '')}] {sm.get('facts', '')}")
    if recalled["procedural"]:
        lines.append("Known procedures for this user:")
        for pm in recalled["procedural"]:
            lines.append(f"  - {pm.get('procedure_name', '')}: {pm.get('trigger', '')}")
    lines.append("")

    return jsonify({
        "context": "\n".join(lines),
        "recalled": recalled,
        "total": sum(len(v) for v in recalled.values()),
    })


@app.route("/api/chat_comparison", methods=["POST"])
def chat_comparison():
    """Chat with or without injected memory context. Runs both calls concurrently."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    body = request.get_json()
    user_id = body.get("user_id", "alice_chen")
    user_name = body.get("user_name", "Alice Chen")
    message = body.get("message", "")
    context_query = body.get("context_query", message)
    # which memory types to inject: list of "episodic", "semantic", "procedural"
    memory_types = body.get("memory_types", ["semantic"])

    if not message:
        return jsonify({"error": "message required"}), 400

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }

    # --- Recall selected memory types from ES (fast, not an LLM call) ---
    recalled = {"episodic": [], "semantic": [], "procedural": []}
    if "episodic" in memory_types:
        try:
            res = es.search(
                index="episodic_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "summary", "query": context_query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=3
            )
            recalled["episodic"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[comparison] episodic recall error: {e}")

    if "semantic" in memory_types:
        try:
            res = es.search(
                index="semantic_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "facts", "query": context_query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=3
            )
            recalled["semantic"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[comparison] semantic recall error: {e}")

    if "procedural" in memory_types:
        try:
            res = es.search(
                index="procedural_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "procedure_text", "query": context_query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=2
            )
            recalled["procedural"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[comparison] procedural recall error: {e}")

    # --- Build memory context block ---
    context_lines = [f"You have the following memory context about {user_name}. Use it to personalize your response.\n"]
    if recalled["episodic"]:
        context_lines.append("Past conversation episodes:")
        for ep in recalled["episodic"]:
            context_lines.append(f"  - {ep.get('summary', '')}")
    if recalled["semantic"]:
        context_lines.append("Standing knowledge about this user:")
        for sm in recalled["semantic"]:
            context_lines.append(f"  - [{sm.get('entity_name', '')}] {sm.get('facts', '')}")
    if recalled["procedural"]:
        context_lines.append("Known procedures for this user:")
        for pm in recalled["procedural"]:
            context_lines.append(f"  - {pm.get('procedure_name', '')}: {pm.get('trigger', '')}")
    context_lines.append("")
    memory_context = "\n".join(context_lines)

    total_recalled = sum(len(v) for v in recalled.values())
    print(f"[comparison] recalled {total_recalled} memories for {user_id} ({memory_types})")

    # --- Fire both agent calls concurrently ---
    def call_without():
        try:
            resp = requests.post(
                f"{KB_URL}/api/agent_builder/converse",
                headers=kb_headers,
                json={"input": message, "agent_id": AGENT_ID},
                timeout=300,
            )
            data = resp.json()
            return {"response": data.get("response", {}).get("message", ""), "conversation_id": data.get("conversation_id")}
        except Exception as e:
            return {"error": str(e)}

    def call_with():
        augmented = memory_context + "\nUser: " + message if total_recalled > 0 else message
        try:
            resp = requests.post(
                f"{KB_URL}/api/agent_builder/converse",
                headers=kb_headers,
                json={"input": augmented, "agent_id": AGENT_ID},
                timeout=300,
            )
            data = resp.json()
            return {
                "response": data.get("response", {}).get("message", ""),
                "conversation_id": data.get("conversation_id"),
                "recalled": recalled,
                "memory_injected": total_recalled > 0,
            }
        except Exception as e:
            return {"error": str(e), "recalled": recalled}

    result = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_without = pool.submit(call_without)
        fut_with = pool.submit(call_with)
        result["without"] = fut_without.result()
        result["with"] = fut_with.result()

    return jsonify(result)


@app.route("/api/seed_chat", methods=["GET"])
def seed_chat():
    """Return a pre-baked response from the seed demo conversation."""
    round_index = int(request.args.get("round_index", 0))
    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
    }
    try:
        resp = requests.get(
            f"{KB_URL}/api/agent_builder/conversations/{SEED_CONV_ID}",
            headers=kb_headers,
            timeout=15,
        )
        if resp.status_code != 200:
            return jsonify({"error": f"Kibana error {resp.status_code}"}), 500
        data = resp.json()
        rounds = data.get("rounds", [])
        if round_index >= len(rounds):
            return jsonify({"error": "Round not found"}), 404
        rnd = rounds[round_index]
        message = rnd.get("response", {}).get("message", "") or ""
        user_input = rnd.get("input", {})
        if isinstance(user_input, dict):
            user_input = user_input.get("message", "")
        return jsonify({
            "conversation_id": SEED_CONV_ID,
            "response": message,
            "round_index": round_index,
            "user_input": str(user_input),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/seed_comp", methods=["GET"])
def seed_comp():
    """Return a pre-baked response from the seed comparison conversations."""
    panel = request.args.get("panel", "without")  # "without" or "with"
    round_index = int(request.args.get("round_index", 0))
    conv_id = SEED_COMP_WITH_ID if panel == "with" else SEED_COMP_WITHOUT_ID
    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
    }
    try:
        resp = requests.get(
            f"{KB_URL}/api/agent_builder/conversations/{conv_id}",
            headers=kb_headers,
            timeout=15,
        )
        if resp.status_code != 200:
            return jsonify({"error": f"Kibana error {resp.status_code}"}), 500
        data = resp.json()
        rounds = data.get("rounds", [])
        if not rounds:
            return jsonify({"error": "No rounds found"}), 404
        idx = min(round_index, len(rounds) - 1)
        rnd = rounds[idx]
        message = rnd.get("response", {}).get("message", "") or ""
        return jsonify({
            "conversation_id": conv_id,
            "response": message,
            "round_index": idx,
            "panel": panel,
            "model_usage": rnd.get("model_usage"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/delete_conversation", methods=["POST"])
def delete_conversation():
    """Delete a Kibana Agent Builder conversation."""
    body = request.get_json() or {}
    conversation_id = body.get("conversation_id")
    if not conversation_id:
        return jsonify({"error": "conversation_id required"}), 400
    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
    }
    try:
        resp = requests.delete(
            f"{KB_URL}/api/agent_builder/conversations/{conversation_id}",
            headers=kb_headers,
            timeout=15,
        )
        return jsonify({"status": "ok", "code": resp.status_code})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset_demo", methods=["POST"])
def reset_demo():
    """Delete live-chat episodes not in the seed manifest, re-trigger semantic + procedural workflows."""
    import subprocess, sys
    body = request.get_json() or {}
    user_id = body.get("user_id")  # None = all users

    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "reset_demo.py")]
    if user_id:
        cmd += ["--user", user_id]

    env = os.environ.copy()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        if result.returncode == 0:
            return jsonify({"status": "ok", "output": result.stdout})
        return jsonify({"error": result.stderr or result.stdout}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Reset timed out"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    """List Agent Builder conversations."""
    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
    }
    try:
        resp = requests.get(
            f"{KB_URL}/api/agent_builder/conversations",
            headers=kb_headers,
            timeout=30,
        )
        data = resp.json()
        convs = data.get("results", [])
        return jsonify([{
            "id": c.get("id"),
            "title": c.get("title"),
            "agent_id": c.get("agent_id"),
            "updated_at": c.get("updated_at"),
        } for c in convs[:20]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True, threaded=True)
