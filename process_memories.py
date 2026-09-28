#!/usr/bin/env python3
"""
Process conversations and generate episodic + semantic memories in Elasticsearch.
Requires: ES_URL and ES_API_KEY environment variables.
"""

import os
import json
import time
import requests
from datetime import datetime
from elasticsearch import Elasticsearch
from collections import defaultdict

# Configuration
ES_URL = os.environ.get("ES_URL", "https://demo-c4ecc8.es.us-east-1.aws.elastic.cloud")
ES_API_KEY = os.environ.get("ES_API_KEY") or os.environ.get("ES_ADMIN_API_KEY")

if not ES_API_KEY:
    raise ValueError("ES_API_KEY or ES_ADMIN_API_KEY environment variable is required")

es = Elasticsearch(ES_URL, api_key=ES_API_KEY)

SIMILARITY_THRESHOLD = 0.75


def call_haiku(prompt):
    """Call Claude Haiku via Elasticsearch inference API."""
    resp = requests.post(
        f"{ES_URL}/_inference/completion/.anthropic-claude-4.5-haiku-completion",
        headers={
            "Authorization": f"ApiKey {ES_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"input": prompt},
        timeout=30
    )
    resp.raise_for_status()
    text = resp.json()["completion"][0]["result"]
    # Strip markdown code fences that Haiku adds
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def embed_text(text):
    """Embed text using Jina via Elasticsearch inference API."""
    resp = requests.post(
        f"{ES_URL}/_inference/text_embedding/.jina-embeddings-v5-text-small",
        headers={
            "Authorization": f"ApiKey {ES_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"input": text},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["text_embedding"][0]["embedding"]


def format_conversation(messages):
    """Format conversation messages as text."""
    return "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])


def process_episodic_memory(conversation):
    """Generate and index episodic memory from a conversation."""
    conv_text = format_conversation(conversation["messages"])

    # Call Claude Haiku to extract structured information
    prompt = f"""Analyze this customer support conversation and extract structured information. Return ONLY valid JSON, no other text.

Conversation:
{conv_text}

Return JSON with these exact fields:
{{
  "summary": "2-3 sentence summary of what was discussed and key outcomes",
  "key_entities": ["entity1", "entity2"],
  "topics": ["topic1", "topic2"],
  "emotional_valence": "positive" or "neutral" or "negative",
  "importance_score": 7.5,
  "action_items": ["action1", "action2"]
}}"""

    try:
        response_text = call_haiku(prompt)
        extracted = json.loads(response_text)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"  ERROR parsing Haiku response for {conversation['conversation_id']}: {e}")
        extracted = {
            "summary": "Conversation processed",
            "key_entities": [],
            "topics": ["general"],
            "emotional_valence": "neutral",
            "importance_score": 5.0,
            "action_items": []
        }

    # Build episodic memory document
    doc = {
        "conversation_id": conversation["conversation_id"],
        "user_id": conversation["user_id"],
        "user_name": conversation["user_name"],
        "session_date": conversation["session_date"],
        "topic": extracted["topics"][0] if extracted["topics"] else "general",
        "summary": extracted["summary"],
        "key_entities": extracted["key_entities"],
        "topics": extracted["topics"],
        "emotional_valence": extracted["emotional_valence"],
        "importance_score": float(extracted["importance_score"]),
        "action_items": extracted["action_items"],
        "raw_conversation_text": conv_text,
        # summary_vector will be added by episodic-embed-pipeline
    }

    # Index to episodic_memory with ingest pipeline
    es.index(
        index="episodic_memory",
        id=conversation["conversation_id"],
        document=doc,
        pipeline="episodic-embed-pipeline"
    )
    print(f"  Indexed episodic memory: {conversation['conversation_id']}")


def detect_entities(summaries_text, user_name):
    """Use Haiku to detect top entities/topics from episode summaries."""
    prompt = f"""Analyze these customer support conversation summaries for {user_name} and identify the top 3-5 distinct topics or entities they care about.

Summaries:
{summaries_text}

Return ONLY valid JSON array:
[
  {{"entity_name": "vector_search", "entity_type": "concept"}},
  {{"entity_name": "python_client", "entity_type": "product"}}
]
Use lowercase_with_underscores for entity_name. entity_type: concept, product, person, or organization."""

    try:
        response_text = call_haiku(prompt)
        return json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ERROR detecting entities: {e}")
        return [{"entity_name": "general_support", "entity_type": "concept"}]


def find_similar_semantic_memory(user_id, vector):
    """kNN search existing semantic memories for user. Returns (doc_id, entity_name, facts, score) or None."""
    try:
        result = es.search(
            index="semantic_memory",
            knn={
                "field": "knowledge_vector",
                "query_vector": vector,
                "k": 1,
                "num_candidates": 20,
                "filter": {"term": {"user_id": user_id}}
            },
            min_score=SIMILARITY_THRESHOLD,
            size=1
        )
        hits = result["hits"]["hits"]
        if hits:
            hit = hits[0]
            return (
                hit["_id"],
                hit["_source"].get("entity_name", ""),
                hit["_source"].get("facts", ""),
                hit["_score"]
            )
    except Exception as e:
        print(f"  WARNING: kNN search failed: {e}")
    return None


def process_semantic_memories():
    """Dynamically detect entities and synthesize semantic memories per user."""
    print("\n=== Distilling Semantic Memories ===")

    time.sleep(2)

    # Get all distinct users from episodic_memory
    result = es.search(
        index="episodic_memory",
        aggs={"users": {"terms": {"field": "user_id", "size": 50}}},
        size=0
    )
    users = [b["key"] for b in result["aggregations"]["users"]["buckets"]]

    for user_id in users:
        print(f"\nProcessing semantic memories for user: {user_id}")

        episodes_result = es.search(
            index="episodic_memory",
            query={"term": {"user_id": user_id}},
            size=10
        )
        episodes = episodes_result["hits"]["hits"]
        if not episodes:
            continue

        user_name = episodes[0]["_source"].get("user_name", user_id)
        summaries_text = "\n---\n".join([
            f"Topic: {ep['_source'].get('topic', 'general')}\nSummary: {ep['_source'].get('summary', '')}"
            for ep in episodes
        ])

        # Dynamically detect entities from episode summaries
        entities = detect_entities(summaries_text, user_name)
        print(f"  Detected {len(entities)} entities: {[e['entity_name'] for e in entities]}")

        for entity in entities:
            entity_name = entity["entity_name"]
            entity_type = entity.get("entity_type", "concept")
            print(f"  Processing entity: {entity_name}")

            # Synthesize facts for this entity
            prompt = f"""Based on these conversation summaries, synthesize what we know about {user_name} regarding "{entity_name}".

Summaries:
{summaries_text}

Return ONLY valid JSON:
{{
  "facts": "3-5 factual sentences synthesizing what we know",
  "confidence_score": 0.85
}}"""

            try:
                response_text = call_haiku(prompt)
                entity_data = json.loads(response_text)
                facts_text = entity_data["facts"]
                confidence = float(entity_data.get("confidence_score", 0.75))
            except (json.JSONDecodeError, ValueError) as e:
                print(f"    ERROR parsing entity response: {e}")
                facts_text = f"{user_name} discussed {entity_name} in support conversations."
                confidence = 0.5

            # Embed facts for similarity search
            try:
                vector = embed_text(facts_text)
            except Exception as e:
                print(f"    ERROR embedding facts: {e}")
                vector = [0.0] * 1024

            # kNN search for similar existing memory
            similar = find_similar_semantic_memory(user_id, vector)

            if similar:
                doc_id, existing_entity_name, existing_facts, score = similar
                print(f"    Similar memory found (score={score:.3f}): {doc_id} — merging")

                # Merge old + new facts via Haiku
                merge_prompt = f"""Merge these two knowledge summaries about {user_name} on the same topic into 3-5 updated factual sentences.

Existing knowledge:
{existing_facts}

New information:
{facts_text}

Return ONLY valid JSON:
{{"facts": "merged 3-5 sentences", "confidence_score": 0.9}}"""

                try:
                    merged_text = call_haiku(merge_prompt)
                    merged_data = json.loads(merged_text)
                    facts_text = merged_data["facts"]
                    confidence = float(merged_data.get("confidence_score", 0.85))
                except Exception as e:
                    print(f"    ERROR merging facts: {e}")

                semantic_doc = {
                    "entity_id": doc_id,
                    "entity_name": existing_entity_name,
                    "entity_type": entity_type,
                    "user_id": user_id,
                    "facts": facts_text,
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "source_episode_ids": [ep["_id"] for ep in episodes],
                    "confidence_score": confidence,
                    "knowledge_vector": vector,
                    "memory_source": "script_merge"
                }
                es.index(index="semantic_memory", id=doc_id, document=semantic_doc)
                print(f"    Merged into: {doc_id}")

            else:
                doc_id = f"{user_id}_{entity_name}"
                print(f"    No similar memory found — creating: {doc_id}")
                semantic_doc = {
                    "entity_id": doc_id,
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "user_id": user_id,
                    "facts": facts_text,
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "source_episode_ids": [ep["_id"] for ep in episodes],
                    "confidence_score": confidence,
                    "knowledge_vector": vector,
                    "memory_source": "script_create"
                }
                es.index(index="semantic_memory", id=doc_id, document=semantic_doc)
                print(f"    Created: {doc_id}")


def main():
    """Main entry point."""
    print("=== Elasticsearch Episodic Memory Demo ===\n")

    # Load conversations from file
    if not os.path.exists("conversations.json"):
        print("ERROR: conversations.json not found")
        return

    with open("conversations.json", "r") as f:
        conversations = json.load(f)

    print(f"Processing {len(conversations)} conversations...\n")

    # Process each conversation
    for i, conv in enumerate(conversations, 1):
        print(f"Processing conversation {i}/{len(conversations)}: {conv.get('conversation_id', 'unknown')}")
        try:
            process_episodic_memory(conv)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Distill semantic memories
    try:
        process_semantic_memories()
    except Exception as e:
        print(f"ERROR distilling semantic memories: {e}")

    print("\n=== Processing Complete ===")


if __name__ == "__main__":
    main()
