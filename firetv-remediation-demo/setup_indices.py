#!/usr/bin/env python3
"""
Setup Elasticsearch indices for the Fire TV remediation memory demo.

Uses semantic_text field type — ES auto-embeds text at index time via the
.jina-embeddings-v5-omni-small inference endpoint. No ingest pipelines needed.

Environment variables:
  ES_URL: Elasticsearch endpoint
  ES_ADMIN_API_KEY: API key for authentication
"""

import os
import sys
from elasticsearch import Elasticsearch

INFERENCE_ID = ".jina-embeddings-v5-omni-small"


def setup_indices():
    es_url = os.environ.get("ES_URL")
    es_api_key = os.environ.get("ES_ADMIN_API_KEY")

    if not es_url or not es_api_key:
        raise ValueError("ES_URL and ES_ADMIN_API_KEY environment variables must be set")

    print(f"Connecting to Elasticsearch at {es_url}")
    client = Elasticsearch([es_url], api_key=es_api_key, verify_certs=True)
    info = client.info()
    print(f"Connected to Elasticsearch {info['version']['number']}")

    indices_config = {
        "firetv_episodic_memory": {
            "mappings": {
                "properties": {
                    "conversation_id":      {"type": "keyword"},
                    "user_id":              {"type": "keyword"},
                    "user_name":            {"type": "keyword"},
                    "session_date":         {"type": "date"},
                    "topic":                {"type": "keyword"},
                    "summary":              {"type": "semantic_text", "inference_id": INFERENCE_ID},
                    "key_entities":         {"type": "keyword"},
                    "topics":               {"type": "keyword"},
                    "issue_context":        {"type": "keyword"},
                    "emotional_valence":    {"type": "keyword"},
                    "importance_score":     {"type": "float"},
                    "action_items":         {"type": "text"},
                    "raw_conversation_text":{"type": "text"},
                    "memory_source":        {"type": "keyword"},
                    "workflow_execution_id":{"type": "keyword"},
                }
            }
        },
        "firetv_semantic_memory": {
            "mappings": {
                "properties": {
                    "entity_id":            {"type": "keyword"},
                    "entity_name":          {"type": "keyword"},
                    "entity_type":          {"type": "keyword"},
                    "user_id":              {"type": "keyword"},
                    "user_name":            {"type": "keyword"},
                    "facts":                {"type": "semantic_text", "inference_id": INFERENCE_ID},
                    "last_updated":         {"type": "keyword"},
                    "source_episode_ids":   {"type": "keyword"},
                    "confidence_score":     {"type": "float"},
                    "total_episodes_analyzed": {"type": "integer"},
                    "memory_source":        {"type": "keyword"},
                    "workflow_execution_id":{"type": "keyword"},
                }
            }
        },
        "firetv_procedural_memory": {
            "mappings": {
                "properties": {
                    "procedure_id":         {"type": "keyword"},
                    "user_id":              {"type": "keyword"},
                    "user_name":            {"type": "keyword"},
                    "procedure_context":    {"type": "keyword"},
                    "procedure_text":       {"type": "semantic_text", "inference_id": INFERENCE_ID},
                    "last_refined":         {"type": "keyword"},
                    "created_from_episodes":{"type": "integer"},
                    "memory_source":        {"type": "keyword"},
                    "workflow_execution_id":{"type": "keyword"},
                }
            }
        },
        "firetv_remediation_memory": {
            "mappings": {
                "properties": {
                    "remediation_id":            {"type": "keyword"},
                    "user_id":                   {"type": "keyword"},
                    "user_name":                 {"type": "keyword"},
                    "device":                    {"type": "keyword"},
                    "issue_context":             {"type": "keyword"},
                    "issue_description":         {"type": "text"},
                    "purchase_date":             {"type": "keyword"},
                    "warranty_expiration_date":  {"type": "keyword"},
                    "warranty_status":           {"type": "keyword"},
                    "ladder_steps":              {"type": "text"},
                    "steps_completed":           {"type": "text"},
                    "steps_remaining":           {"type": "text"},
                    "ladder_exhausted":          {"type": "boolean"},
                    "recommended_next_action":   {"type": "semantic_text", "inference_id": INFERENCE_ID},
                    "final_offer_issued":        {"type": "boolean"},
                    "final_offer_text":          {"type": "text"},
                    "last_updated":              {"type": "keyword"},
                    "source_episode_ids":        {"type": "keyword"},
                    "memory_source":             {"type": "keyword"},
                    "workflow_execution_id":     {"type": "keyword"},
                }
            }
        }
    }

    print("\nCleaning up existing indices...")
    for index_name in indices_config:
        try:
            client.indices.delete(index=index_name)
            print(f"  ✓ Deleted: {index_name}")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                print(f"  - {index_name} does not exist (skipping)")
            else:
                raise

    print("\nCreating indices...")
    for index_name, config in indices_config.items():
        client.indices.create(index=index_name, **config)
        print(f"  ✓ Created: {index_name}")

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"\nInference ID: {INFERENCE_ID}")
    print("All four indices use semantic_text — no ingest pipelines needed.")
    print("\nNext: python3 setup_workflows.py && python3 run_demo.py")


if __name__ == "__main__":
    setup_indices()
