#!/usr/bin/env python3
"""
Flask application for the Fire TV remediation memory demo.
Requires: ES_URL and ES_ADMIN_API_KEY environment variables.
"""

import os
import json
import requests
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request
from elasticsearch import Elasticsearch

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

EPISODIC_WORKFLOW_ID = _WF_IDS.get("episodic", "generate_firetv_episodic_memory")
SEMANTIC_WORKFLOW_ID = _WF_IDS.get("semantic", "generate_firetv_semantic_memory")
PROCEDURAL_WORKFLOW_ID = _WF_IDS.get("procedural", "generate_firetv_procedural_memory")
REMEDIATION_WORKFLOW_ID = _WF_IDS.get("remediation", "generate_firetv_remediation_memory")
AGENT_ID = _WF_IDS.get("agent", "elastic-ai-agent")

# Memory Demo comparison tab plays back these two fixed, pre-recorded conversations
# instead of calling the agent live (avoids a real 70s "without memory" wait / API flake
# risk during a live demo). Recorded once in Kibana, then pinned here so every future
# comparison run replays the exact same "aha moment". Source of truth for these IDs is
# demo_seed_manifest.json's "memory_demo_conversations" key — reset_demo.py does not
# touch that key, so it survives a reset.
_MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "demo_seed_manifest.json")
_MANIFEST = {}
if os.path.exists(_MANIFEST_PATH):
    with open(_MANIFEST_PATH) as _f:
        _MANIFEST = json.load(_f)
_MEMORY_DEMO_CONVS = _MANIFEST.get("memory_demo_conversations", {})

SEED_COMP_WITHOUT_ID = _MEMORY_DEMO_CONVS.get("without_memory", "")
SEED_COMP_WITH_ID = _MEMORY_DEMO_CONVS.get("with_memory", "")

# Live Chat tab plays back this fixed, pre-recorded conversation round-by-round
# (looks live, but never calls the agent) so the demo never depends on a live
# multi-turn agent call mid-presentation. Source of truth is demo_seed_manifest.json's
# "live_chat_conversation" key — reset_demo.py does not touch that key.
SEED_CONV_ID = _MANIFEST.get("live_chat_conversation", "")

# Canonical troubleshooting ladders per issue type
LADDER_STEPS = {
    "power_failure": "power cycle by unplugging for 30 seconds, factory reset via remote button combination, test a different power adapter and outlet, escalate to hardware replacement",
    "remote_network": "re-pair the remote to the Fire TV, restart the router and check available bandwidth, move the Fire TV closer to the router or use an ethernet adapter, escalate to network diagnostics",
    "app_crash": "clear app cache and update Fire TV firmware, uninstall and reinstall the affected app, escalate to firmware compatibility team",
}

# Persona metadata: entity clusters (semantic), procedure contexts, remediation ladder case
PERSONA_META = {
    "jordan_price": {
        "name": "Jordan Price",
        "issue_context": "power_failure",
        "entities": [("power_failure", "concept")],
        "procedures": ["power_failure"],
        "remediation": {
            "device": "Amazon Fire TV",
            "purchase_date": "2025-08-01",
            "warranty_expiration_date": "2026-08-01",
        },
    },
    "morgan_lee": {
        "name": "Morgan Lee",
        "issue_context": "remote_network",
        "entities": [("remote_pairing", "concept"), ("streaming_lag", "concept")],
        "procedures": ["remote_network"],
        "remediation": {
            "device": "Amazon Fire TV",
            "purchase_date": "2026-06-01",
            "warranty_expiration_date": "2027-06-01",
        },
    },
    "priya_nair": {
        "name": "Priya Nair",
        "issue_context": "app_crash",
        "entities": [("app_crash", "concept")],
        "procedures": ["app_crash"],
        "remediation": {
            "device": "Amazon Fire TV",
            "purchase_date": "2026-05-01",
            "warranty_expiration_date": "2027-05-01",
        },
    },
}
ENTITY_CLUSTERS = {uid: meta["entities"] for uid, meta in PERSONA_META.items()}

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
    """List all episodic memories, sorted by session_date descending."""
    try:
        result = es.search(
            index="firetv_episodic_memory",
            sort=[{"session_date": {"order": "desc"}}],
            size=50
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/semantic", methods=["GET"])
def get_semantic():
    """List all semantic memories, sorted by last_updated descending."""
    try:
        result = es.search(
            index="firetv_semantic_memory",
            sort=[{"last_updated": {"order": "desc"}}],
            size=50
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/procedural", methods=["GET"])
def get_procedural():
    """List all procedural memories, sorted by last_refined descending."""
    try:
        result = es.search(
            index="firetv_procedural_memory",
            sort=[{"last_refined": {"order": "desc"}}],
            size=50
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/remediation", methods=["GET"])
def get_remediation():
    """List all remediation memories, sorted by last_updated descending."""
    try:
        result = es.search(
            index="firetv_remediation_memory",
            sort=[{"last_updated": {"order": "desc"}}],
            size=50
        )
        return jsonify([hit["_source"] for hit in result["hits"]["hits"]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["GET"])
def search_memories():
    """Semantic search across episodic, semantic, and/or procedural memories."""
    query = request.args.get("q", "")
    search_type = request.args.get("type", "both")  # episodic, semantic, or both

    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        results = []

        if search_type in ["episodic", "both"]:
            episodic_result = es.search(
                index="firetv_episodic_memory",
                query={"semantic": {"field": "summary", "query": query}},
                size=5
            )
            for hit in episodic_result["hits"]["hits"]:
                hit["_source"]["type"] = "episodic"
                hit["_source"]["score"] = hit["_score"]
                results.append(hit["_source"])

        if search_type in ["semantic", "both"]:
            semantic_result = es.search(
                index="firetv_semantic_memory",
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


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return memory counts and available personas."""
    try:
        episodic_count = es.count(index="firetv_episodic_memory")["count"]
        semantic_count = es.count(index="firetv_semantic_memory")["count"]
        try:
            procedural_count = es.count(index="firetv_procedural_memory")["count"]
        except Exception:
            procedural_count = 0
        try:
            remediation_count = es.count(index="firetv_remediation_memory")["count"]
        except Exception:
            remediation_count = 0

        return jsonify({
            "episodic_count": episodic_count,
            "semantic_count": semantic_count,
            "procedural_count": procedural_count,
            "remediation_count": remediation_count,
            "users": list(PERSONA_META.keys())
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _recall_remediation(user_id, size=1):
    """Fetch the most recent remediation ladder doc for a user."""
    try:
        res = es.search(
            index="firetv_remediation_memory",
            query={"term": {"user_id": user_id}},
            sort=[{"last_updated": {"order": "desc"}}],
            size=size
        )
        return [{**h["_source"], "score": h.get("_score") or 0} for h in res["hits"]["hits"]]
    except Exception as e:
        print(f"[recall] remediation: {e}")
        return []


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
            "procedural": [],
            "remediation": [],
        }

        episodic_result = es.search(
            index="firetv_episodic_memory",
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
            index="firetv_semantic_memory",
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
                index="firetv_procedural_memory",
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

        recalled["remediation"] = _recall_remediation(user_id)

        return jsonify(recalled)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _fetch_pending_prompts(conv_id, kb_headers):
    """Fetch pending_prompts (clarifying question) for a conversation awaiting user input."""
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
    return pending_prompts


def _extract_clarifying_qa(rnd):
    """Return a round's ask_user_question step (if any), structured for interactive
    replay of the same radio-button prompt the live agent showed — the presenter
    clicks through it live, just like the original conversation did."""
    for step in rnd.get("steps", []):
        if step.get("type") != "ask_user_question":
            continue
        return {"questions": step.get("questions", [])}
    return None


def _fetch_canned_round(conv_id, kb_headers, round_index=None):
    """Fetch a round of a pre-recorded conversation for canned playback: the response
    text, real recorded latency/token usage, and a Kibana deep link.
    round_index=None returns the last round (Memory Demo comparison usage)."""
    resp = requests.get(
        f"{KB_URL}/api/agent_builder/conversations/{conv_id}",
        headers=kb_headers, timeout=15,
    )
    data = resp.json()
    rounds = data.get("rounds", [])
    if not rounds:
        raise ValueError(f"conversation {conv_id} has no rounds")
    idx = len(rounds) - 1 if round_index is None else round_index
    if idx < 0 or idx >= len(rounds):
        raise IndexError(f"round {idx} not found (conversation has {len(rounds)} rounds)")
    rnd = rounds[idx]
    usage = rnd.get("model_usage") or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    agent_id = data.get("agent_id", AGENT_ID)
    user_input = rnd.get("input", {})
    if isinstance(user_input, dict):
        user_input = user_input.get("message", "")
    return {
        "response": rnd.get("response", {}).get("message", "") or "",
        "clarifying_qa": _extract_clarifying_qa(rnd),
        "duration_ms": rnd.get("time_to_last_token"),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
            "cached_input": usage.get("cached_input_tokens", 0),
        },
        "conversation_url": f"{KB_URL}/app/agent_builder/agents/{agent_id}/conversations/{conv_id}",
        "round_index": idx,
        "total_rounds": len(rounds),
        "user_input": str(user_input),
    }


@app.route("/api/chat", methods=["POST"])
def chat_with_agent():
    """Send a message to the Fire TV Support Specialist agent."""
    body = request.get_json()
    user_input = body.get("input", "")
    conversation_id = body.get("conversation_id")
    agent_id = body.get("agent_id", AGENT_ID)
    prompt_id = body.get("prompt_id")
    prompt_answers = body.get("answers")

    if prompt_id and prompt_answers is not None:
        # Answering a pending ask_user_question prompt — no free-text "input",
        # Kibana's converse API requires the structured `prompts` field instead.
        payload = {"agent_id": agent_id, "conversation_id": conversation_id, "prompts": {prompt_id: {"answers": prompt_answers}}}
    else:
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
            pending_prompts = _fetch_pending_prompts(conv_id, kb_headers)
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
    """Trigger the generate_firetv_episodic_memory Kibana Workflow for a conversation."""
    body = request.get_json()
    conversation_id = body.get("conversation_id")
    user_id = body.get("user_id", "demo_user")
    user_name = body.get("user_name", "Demo User")
    issue_context = body.get("issue_context", PERSONA_META.get(user_id, {}).get("issue_context", ""))

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
                "issue_context": issue_context,
            }},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code not in (200, 201, 202):
            return jsonify({"error": data.get("message", "Workflow failed"), "details": data}), resp.status_code

        print(f"[episodic workflow response] {data}")
        execution_id = data.get("workflowExecutionId") or data.get("execution_id") or data.get("executionId") or data.get("id")
        executions = [{
            "workflow": "firetv-episodic-memory",
            "label": "Generate Episodic Memory",
            "execution_id": execution_id,
            "execution_url": (
                f"{KB_URL}/app/workflows/{EPISODIC_WORKFLOW_ID}"
                f"?executionId={execution_id}&stepExecutionId=__overview&tab=executions"
            ) if execution_id else None,
        }]

        # Auto-trigger semantic workflows for each entity cluster
        entities = ENTITY_CLUSTERS.get(user_id, [])
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
            "workflow": "generate_firetv_episodic_memory",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trigger_semantic_workflow", methods=["POST"])
def trigger_semantic_workflow():
    """Trigger the generate_firetv_semantic_memory Kibana Workflow for a user."""
    body = request.get_json()
    user_id = body.get("user_id")
    user_name = body.get("user_name", "Demo User")
    entity_name = body.get("entity_name", "general")
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
                "workflow": "generate_firetv_semantic_memory",
            })
        return jsonify({"error": data.get("message", "Workflow failed"), "details": data}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trigger_procedural_workflow", methods=["POST"])
def trigger_procedural_workflow():
    """Trigger the generate_firetv_procedural_memory Kibana Workflow for a user."""
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
                "workflow": "generate_firetv_procedural_memory",
            })
        return jsonify({"error": data.get("message", "Workflow failed"), "details": data}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trigger_remediation_workflow", methods=["POST"])
def trigger_remediation_workflow():
    """Trigger the generate_firetv_remediation_memory Kibana Workflow for a user's issue ladder."""
    body = request.get_json()
    user_id = body.get("user_id")
    user_name = body.get("user_name", "Demo User")
    meta = PERSONA_META.get(user_id)

    if not user_id or not meta:
        return jsonify({"error": "user_id required and must be a known persona"}), 400

    issue_context = meta["issue_context"]
    rem = meta["remediation"]

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            f"{KB_URL}/api/workflows/workflow/{REMEDIATION_WORKFLOW_ID}/run",
            headers=kb_headers,
            json={"inputs": {
                "user_id": user_id,
                "user_name": user_name,
                "issue_context": issue_context,
                "device": rem["device"],
                "purchase_date": rem["purchase_date"],
                "warranty_expiration_date": rem["warranty_expiration_date"],
                "ladder_steps": LADDER_STEPS[issue_context],
                "current_date": datetime.now(timezone.utc).date().isoformat(),
            }},
            timeout=120,
        )
        data = resp.json()
        if resp.status_code in (200, 201, 202):
            return jsonify({
                "execution_id": data.get("execution_id") or data.get("id"),
                "status": data.get("status", "triggered"),
                "workflow": "generate_firetv_remediation_memory",
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


def _build_memory_context(user_id, user_name, recalled):
    """Build a human-readable memory context block, including remediation ladder state."""
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
        lines.append("Known troubleshooting procedure for this user:")
        for pm in recalled["procedural"]:
            lines.append(f"  - {pm.get('procedure_text', '')}")
    if recalled.get("remediation"):
        lines.append("Remediation ladder status (do NOT ask the customer to repeat these steps):")
        for rm in recalled["remediation"]:
            lines.append(
                f"  - Issue: {rm.get('issue_context', '')} | Device: {rm.get('device', '')} | "
                f"Warranty: {rm.get('warranty_status', '')} | Ladder exhausted: {rm.get('ladder_exhausted', '')}"
            )
            lines.append(f"    {rm.get('recommended_next_action', '')}")
    lines.append("")
    return "\n".join(lines)


@app.route("/api/comparison_context", methods=["GET"])
def comparison_context():
    """Recall memories and return augmented message — no LLM call, fast ES only."""
    user_id = request.args.get("user_id", "jordan_price")
    user_name = request.args.get("user_name", "User")
    query = request.args.get("query", "")
    memory_types = request.args.getlist("memory_types") or ["semantic"]

    recalled = {"episodic": [], "semantic": [], "procedural": [], "remediation": []}

    if "episodic" in memory_types:
        try:
            res = es.search(
                index="firetv_episodic_memory",
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
                index="firetv_semantic_memory",
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
                index="firetv_procedural_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "procedure_text", "query": query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=2
            )
            recalled["procedural"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[context] procedural: {e}")

    if "remediation" in memory_types:
        recalled["remediation"] = _recall_remediation(user_id)

    context = _build_memory_context(user_id, user_name, recalled)

    return jsonify({
        "context": context,
        "recalled": recalled,
        "total": sum(len(v) for v in recalled.values()),
    })


@app.route("/api/chat_comparison", methods=["POST"])
def chat_comparison():
    """Chat with or without injected memory context. Runs both calls concurrently."""
    from concurrent.futures import ThreadPoolExecutor

    body = request.get_json()
    user_id = body.get("user_id", "jordan_price")
    user_name = body.get("user_name", "Jordan Price")
    message = body.get("message", "")
    context_query = body.get("context_query", message)
    # which memory types to inject: list of "episodic", "semantic", "procedural", "remediation"
    memory_types = body.get("memory_types", ["semantic", "remediation"])

    if not message:
        return jsonify({"error": "message required"}), 400

    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }

    # --- Recall selected memory types from ES (fast, not an LLM call) ---
    recalled = {"episodic": [], "semantic": [], "procedural": [], "remediation": []}
    if "episodic" in memory_types:
        try:
            res = es.search(
                index="firetv_episodic_memory",
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
                index="firetv_semantic_memory",
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
                index="firetv_procedural_memory",
                query={"bool": {
                    "must": {"semantic": {"field": "procedure_text", "query": context_query}},
                    "filter": {"term": {"user_id": user_id}}
                }},
                size=2
            )
            recalled["procedural"] = [{**h["_source"], "score": h["_score"]} for h in res["hits"]["hits"]]
        except Exception as e:
            print(f"[comparison] procedural recall error: {e}")

    if "remediation" in memory_types:
        recalled["remediation"] = _recall_remediation(user_id)

    total_recalled = sum(len(v) for v in recalled.values())
    print(f"[comparison] recalled {total_recalled} memories for {user_id} ({memory_types})")

    # --- Both panels replay fixed, pre-recorded conversations (see
    # demo_seed_manifest.json → memory_demo_conversations) instead of calling the
    # live agent. Keeps the demo fast/reliable while still surfacing the real
    # recorded latency and token usage from when these were captured. ---
    def call_without():
        if not SEED_COMP_WITHOUT_ID:
            return {"error": "without_memory conversation id not configured"}
        try:
            canned = _fetch_canned_round(SEED_COMP_WITHOUT_ID, kb_headers)
            return {
                "response": canned["response"],
                "conversation_id": SEED_COMP_WITHOUT_ID,
                "duration_ms": canned["duration_ms"],
                "tokens": canned["tokens"],
                "conversation_url": canned["conversation_url"],
            }
        except Exception as e:
            return {"error": str(e)}

    def call_with():
        if not SEED_COMP_WITH_ID:
            return {"error": "with_memory conversation id not configured", "recalled": recalled}
        try:
            canned = _fetch_canned_round(SEED_COMP_WITH_ID, kb_headers)
            return {
                "response": canned["response"],
                "conversation_id": SEED_COMP_WITH_ID,
                "duration_ms": canned["duration_ms"],
                "tokens": canned["tokens"],
                "conversation_url": canned["conversation_url"],
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
    """Replay a round of the fixed Live Chat demo conversation: looks live, but plays
    back a real recorded round (response text, latency, tokens) instead of calling
    the agent."""
    if not SEED_CONV_ID:
        return jsonify({"error": "Seed conversation not configured yet"}), 404
    round_index = int(request.args.get("round_index", 0))
    kb_headers = {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "kbn-xsrf": "true",
    }
    try:
        canned = _fetch_canned_round(SEED_CONV_ID, kb_headers, round_index)
        return jsonify({
            "conversation_id": SEED_CONV_ID,
            "response": canned["response"],
            "round_index": canned["round_index"],
            "total_rounds": canned["total_rounds"],
            "is_last": canned["round_index"] >= canned["total_rounds"] - 1,
            "user_input": canned["user_input"],
            "duration_ms": canned["duration_ms"],
            "tokens": canned["tokens"],
            "conversation_url": canned["conversation_url"],
            "clarifying_qa": canned["clarifying_qa"],
        })
    except IndexError:
        return jsonify({"error": "Round not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/seed_comp", methods=["GET"])
def seed_comp():
    """Return a pre-baked response from the seed comparison conversations."""
    panel = request.args.get("panel", "without")  # "without" or "with"
    conv_id = SEED_COMP_WITH_ID if panel == "with" else SEED_COMP_WITHOUT_ID
    if not conv_id:
        return jsonify({"error": "Seed comparison conversation not configured yet"}), 404
    round_index = int(request.args.get("round_index", 0))
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
    """Delete live-chat episodes not in the seed manifest, re-trigger semantic/procedural/remediation workflows."""
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
    app.run(host="0.0.0.0", port=5003, debug=True)
