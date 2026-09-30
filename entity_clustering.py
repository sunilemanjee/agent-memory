#!/usr/bin/env python3
"""Dynamic entity clustering for episodic memories.

Density-probed centroid classification (Jina `task=clustering` embeddings +
client-side numpy similarity) + `significant_text` for cluster labeling, per
https://www.elastic.co/search-labs/blog/unsupervised-document-clustering-elasticsearch-jina-embeddings
"""

import os
import re
import json
from datetime import datetime, timezone

import requests
import numpy as np
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

ES_URL = os.environ.get("ES_URL", "https://demo-c4ecc8.es.us-east-1.aws.elastic.cloud")
ES_API_KEY = os.environ.get("ES_ADMIN_API_KEY")
JINA_API_KEY = os.environ.get("JINA_API_KEY")
JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v5-omni-small"

CLUSTER_VECTOR_DIMS = 1024
MIN_SAMPLES_FOR_PROBES = 50
PROBE_FRACTION = 0.05
PROBE_K = 15
SEPARATION_PERCENTILE = 75
NOISE_FLOOR_PERCENTILE = 25
MIN_CLUSTER_SIZE = 8
MAX_CLUSTERS = 12


def _es():
    return Elasticsearch(ES_URL, api_key=ES_API_KEY)


def embed_for_clustering(texts, batch_size=64):
    """Embed texts with Jina's clustering-task LoRA adapter. Returns vectors in input order."""
    if not JINA_API_KEY:
        raise ValueError("JINA_API_KEY environment variable is required")
    vectors = [None] * len(texts)
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        resp = requests.post(
            JINA_API_URL,
            headers={"Authorization": f"Bearer {JINA_API_KEY}", "Content-Type": "application/json"},
            json={"model": JINA_MODEL, "task": "clustering", "input": batch},
            timeout=60,
        )
        resp.raise_for_status()
        for item in resp.json()["data"]:
            vectors[start + item["index"]] = item["embedding"]
    return vectors


def call_haiku(prompt):
    resp = requests.post(
        f"{ES_URL}/_inference/completion/.anthropic-claude-4.5-haiku-completion",
        headers={"Authorization": f"ApiKey {ES_API_KEY}", "Content-Type": "application/json"},
        json={"input": prompt},
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["completion"][0]["result"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def _slugify(text):
    text = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return text.strip("_") or "unknown"


def _fetch_user_vectors(es, user_id):
    """Return (ids, vectors) for all of a user's episodes, backfilling
    cluster_vector for any docs that don't have one yet (e.g. episodes saved
    via the Kibana workflow, which doesn't set it)."""
    docs = []
    search_after = None
    while True:
        body = {
            "query": {"term": {"user_id": user_id}},
            "size": 1000,
            "sort": [{"conversation_id": "asc"}],
            "_source": ["cluster_vector", "summary", "raw_conversation_text"],
        }
        if search_after:
            body["search_after"] = search_after
        result = es.search(index="episodic_memory", **body)
        hits = result["hits"]["hits"]
        if not hits:
            break
        docs.extend(hits)
        if len(hits) < 1000:
            break
        search_after = hits[-1]["sort"]

    ids = [hit["_id"] for hit in docs]
    vectors = [hit["_source"].get("cluster_vector") for hit in docs]

    missing_ids, missing_texts = [], []
    for hit in docs:
        if not hit["_source"].get("cluster_vector"):
            src = hit["_source"]
            text = f"{src.get('summary', '')}\n\n{src.get('raw_conversation_text', '')}"[:4000]
            missing_ids.append(hit["_id"])
            missing_texts.append(text)

    if missing_ids:
        new_vectors = embed_for_clustering(missing_texts)
        id_to_idx = {doc_id: i for i, doc_id in enumerate(ids)}
        actions = []
        for doc_id, vec in zip(missing_ids, new_vectors):
            vectors[id_to_idx[doc_id]] = vec
            actions.append({"_op_type": "update", "_index": "episodic_memory", "_id": doc_id, "doc": {"cluster_vector": vec}})
        bulk(es, actions)

    return ids, vectors


def compute_clusters(user_id):
    es = _es()
    ids, vectors = _fetch_user_vectors(es, user_id)
    n = len(ids)

    if n < MIN_CLUSTER_SIZE:
        return {"user_id": user_id, "clusters": [], "projection": {}, "total_episodes": n, "noise_count": n, "status": "insufficient_data"}

    id_to_idx = {doc_id: i for i, doc_id in enumerate(ids)}
    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = matrix / norms

    # --- density probing ---
    n_probes = min(n, max(MIN_SAMPLES_FOR_PROBES, int(n * PROBE_FRACTION)))
    rng = np.random.default_rng(42)
    probe_idx = rng.choice(n, size=n_probes, replace=False)
    probe_sims = unit[probe_idx] @ unit.T
    k = min(PROBE_K + 1, n)
    density = np.sort(probe_sims, axis=1)[:, -k:-1].mean(axis=1)

    order = np.argsort(-density)
    median_density = np.median(density)

    # Thresholds are corpus-relative, not fixed absolutes: synthetic/domain-narrow
    # text can sit at a uniformly high cosine-similarity floor (e.g. median ~0.9),
    # which would make a fixed 0.85 stricter than the data itself and collapse
    # everything into one cluster. Separation is derived from this user's raw
    # probe-to-corpus similarity distribution (excluding self-matches).
    non_self_sims = probe_sims[probe_sims < 0.999]
    separation_threshold = float(np.percentile(non_self_sims, SEPARATION_PERCENTILE))

    seeds = []
    for rank in order:
        if density[rank] < median_density:
            break
        cand_idx = probe_idx[rank]
        if not seeds:
            seeds.append(cand_idx)
        elif (unit[cand_idx] @ unit[seeds].T).max() < separation_threshold:
            seeds.append(cand_idx)
        if len(seeds) >= MAX_CLUSTERS:
            break
    if not seeds:
        seeds = [probe_idx[order[0]]]

    # --- classification ---
    sims_to_seeds = unit @ unit[seeds].T
    best_seed = np.argmax(sims_to_seeds, axis=1)
    best_sim = np.max(sims_to_seeds, axis=1)
    # Noise floor is a percentile of THIS run's best-match-to-nearest-seed scores,
    # not raw pairwise similarity — raw-similarity percentiles undershoot badly
    # here since best-of-several-seeds skews much higher than a random pair.
    # Directly targets ~NOISE_FLOOR_PERCENTILE% of episodes classified as noise.
    noise_floor = float(np.percentile(best_sim, NOISE_FLOOR_PERCENTILE))
    assignment = np.where(best_sim >= noise_floor, best_seed, -1)


    cluster_members = {}
    for seed_i in range(len(seeds)):
        member_ids = [ids[i] for i in range(n) if assignment[i] == seed_i]
        if len(member_ids) >= MIN_CLUSTER_SIZE:
            cluster_members[seed_i] = member_ids

    # --- labeling via significant_text (quality gate: no terms -> noise) ---
    # Exclude the persona's own first name (user_id is "firstname_lastname") and
    # generic conversational filler, which would otherwise leak into labels
    # since assistant replies sometimes greet the user by name.
    exclude_terms = [user_id.split("_")[0]] + [
        "hi", "hello", "hey", "thanks", "thank", "please", "okay", "sure",
        "great", "sounds", "yes", "questions", "question", "help", "sorry",
    ]
    exclude_pattern = "|".join(exclude_terms)

    clusters = []
    final_id_to_cluster = {}
    for seed_i, member_ids in cluster_members.items():
        agg = es.search(
            index="episodic_memory",
            size=0,
            query={"terms": {"conversation_id": member_ids}},
            aggs={"sig": {"significant_text": {
                "field": "raw_conversation_text", "size": 5,
                "filter_duplicate_text": True, "exclude": exclude_pattern,
            }}},
        )
        buckets = agg["aggregations"]["sig"]["buckets"]
        if not buckets:
            continue

        terms = [b["key"] for b in buckets]
        entity_name = _slugify(terms[0])
        try:
            type_prompt = (
                "Classify this topic label as one of: concept, product, person, organization.\n"
                f"Label: {entity_name}\nRelated terms: {', '.join(terms)}\n"
                'Return ONLY valid JSON: {"entity_type": "concept"}'
            )
            entity_type = json.loads(call_haiku(type_prompt)).get("entity_type", "concept")
        except Exception:
            entity_type = "concept"

        member_vecs = unit[[id_to_idx[d] for d in member_ids]]
        cluster_id = f"{user_id}_{entity_name}"
        clusters.append({
            "cluster_id": cluster_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "significant_terms": terms,
            "member_count": len(member_ids),
            "centroid_vector": member_vecs.mean(axis=0).tolist(),
        })
        for doc_id in member_ids:
            final_id_to_cluster[doc_id] = cluster_id

    label_by_cluster_id = {c["cluster_id"]: c["entity_name"] for c in clusters}
    label_by_cluster_id["noise"] = "noise"
    for doc_id in ids:
        final_id_to_cluster.setdefault(doc_id, "noise")

    # --- write back cluster_id/cluster_label onto episodes ---
    bulk(es, [
        {"_op_type": "update", "_index": "episodic_memory", "_id": doc_id,
         "doc": {"cluster_id": cid, "cluster_label": label_by_cluster_id[cid]}}
        for doc_id, cid in final_id_to_cluster.items()
    ])

    # --- refresh entity_clusters cache for this user ---
    es.delete_by_query(index="entity_clusters", query={"term": {"user_id": user_id}}, conflicts="proceed")
    now = datetime.now(timezone.utc).isoformat()
    if clusters:
        bulk(es, [
            {"_op_type": "index", "_index": "entity_clusters", "_id": c["cluster_id"],
             "_source": {**c, "user_id": user_id, "computed_at": now}}
            for c in clusters
        ])

    # --- 2D projection via PCA for the scatter plot ---
    centered = unit - unit.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    coords = centered @ vt[:3].T
    projection = {
        doc_id: {
            "x": float(coords[i][0]), "y": float(coords[i][1]), "z": float(coords[i][2]),
            "cluster_id": final_id_to_cluster[doc_id],
            "cluster_label": label_by_cluster_id[final_id_to_cluster[doc_id]],
        }
        for i, doc_id in enumerate(ids)
    }

    noise_count = sum(1 for cid in final_id_to_cluster.values() if cid == "noise")
    return {
        "user_id": user_id,
        "clusters": clusters,
        "projection": projection,
        "total_episodes": n,
        "noise_count": noise_count,
        "status": "ok",
    }


def get_relevant_entities(user_id, text, max_entities=2, epsilon=0.03):
    """Return the entity cluster(s) a piece of text (e.g. a live conversation)
    best matches, by cosine similarity to each cached cluster's centroid —
    used to gate which semantic-memory entities get updated after a save,
    instead of refreshing every cached entity regardless of relevance."""
    es = _es()
    result = es.search(
        index="entity_clusters",
        query={"term": {"user_id": user_id}},
        size=50,
        _source=["entity_name", "entity_type", "centroid_vector"],
    )
    hits = result["hits"]["hits"]
    if not hits:
        computed = compute_clusters(user_id)
        clusters = computed.get("clusters", [])
        if not clusters:
            return []
        hits = [{"_source": c} for c in clusters]

    if not text.strip():
        return []

    vec = np.array(embed_for_clustering([text])[0], dtype=np.float32)
    vec = vec / (np.linalg.norm(vec) or 1.0)

    scored = []
    for h in hits:
        src = h["_source"]
        centroid = np.array(src["centroid_vector"], dtype=np.float32)
        centroid = centroid / (np.linalg.norm(centroid) or 1.0)
        sim = float(vec @ centroid)
        scored.append((sim, src["entity_name"], src["entity_type"]))

    scored.sort(key=lambda x: -x[0])
    best_sim = scored[0][0]
    return [(name, etype) for sim, name, etype in scored if sim >= best_sim - epsilon][:max_entities]


def get_current_entity_clusters(user_id):
    """Returns [(entity_name, entity_type), ...] for a user — replaces the old
    hardcoded ENTITY_CLUSTERS dict. Reads the cache; computes it if empty."""
    es = _es()
    result = es.search(
        index="entity_clusters",
        query={"term": {"user_id": user_id}},
        size=50,
        sort=[{"member_count": "desc"}],
    )
    hits = result["hits"]["hits"]
    if not hits:
        computed = compute_clusters(user_id)
        return [(c["entity_name"], c["entity_type"]) for c in computed.get("clusters", [])]
    return [(h["_source"]["entity_name"], h["_source"]["entity_type"]) for h in hits]
