# Agent Memory Demo Script

**Audience:** Elastic customers evaluating AI agent capabilities  
**Time:** 10–15 minutes  
**URL:** http://localhost:5002  
**Core message:** Elasticsearch natively powers agent memory — no external vector DB, no Memzero, no custom embedding service.

---

## Before You Start

Make sure these are running:

```bash
# Terminal 1 — Flask app
cd /Users/sunilemanjee/Documents/GitHub/agent-memory-sunman
source variables.env && python3 app.py

# Verify it's alive
open http://localhost:5002
```

You should see 8 tabs: **🏗️ Architecture | 💬 Live Chat | 📅 Episodic Memory | 🧠 Semantic Memory | ⚙️ Procedural Memory | 🔍 Memory Search | 🔎 Memory Recall | 🧪 Memory Demo**

---

## Act 1 — The Problem (30 seconds, no UI yet)

**Say to customer:**

> "AI agents have a memory problem. Every conversation starts from zero. The agent doesn't know you've asked about vector search three times, or that you're on a budget, or that you already tried ELSER. This demo shows how Elasticsearch solves that — natively, with no external tools."

---

## Act 2 — Have a Conversation (2 minutes)

**Click the Chat tab.**

Carol Johnson is selected by default. Two suggested questions appear as chips above the input box — click them instead of typing:

Click: **"We're building a RAG pipeline with about 500k product embeddings. We're evaluating Elasticsearch vs Pinecone. What should we know?"**

The agent responds — expect a breakdown of: native kNN/ANN support, ELSER for semantic search, operational simplicity vs standalone vector DBs, ecosystem fit.

Click the second chip: **"What's the pricing model for Elasticsearch serverless at that scale?"**

The agent explains Virtual Compute Units (VCUs), storage costs, and how serverless billing scales with query and indexing load.

**Say to customer:**

> "This is a real conversation happening inside Elastic Agent Builder — Kibana's native AI chat. The conversation ID is now live in the system. Watch what happens when we save it."

---

## Act 3 — Save to Agent Memory (2 minutes)

Click the **"⚡ Save to Agent Memory"** button (top-left sidebar of the Chat tab). It becomes enabled after the first agent reply.

The UI immediately shows 4 workflow execution links — each is a live Kibana Workflow run you can click into:

- **Generate Episodic Memory** — stores this conversation as a searchable episode
- **Semantic: Competitive Analysis** — updates Carol's standing knowledge on competitive analysis
- **Semantic: Cost Estimation** — updates Carol's standing knowledge on cost estimation
- **Semantic: Ai Features** — updates Carol's standing knowledge on AI features

**What happens behind the scenes (explain this):**

> "One button fires **4 Kibana Workflows** in parallel — YAML-defined automations, zero custom code.
>
> The **episodic workflow** runs 4 steps:
> 1. Fetch the full conversation from Agent Builder via Kibana API
> 2. AI agent summarizes it into 2–3 sentences
> 3. AI agent extracts topic tags, entities, importance score
> 4. Index into Elasticsearch — the `semantic_text` field type auto-embeds via Jina v5 at index time (no ingest pipeline)
>
> The **3 semantic workflows** run automatically right after, one per knowledge entity:
> 1. Fetch all of Carol's episodic memories
> 2. AI distills 3–5 factual sentences about that entity
> 3. Embed the facts → kNN search existing semantic memories
> 4. If similarity > 0.75: merge new facts with existing knowledge. If not: create a new memory.
> 5. Index to semantic_memory"

**Switch to the Episodic Memory tab.** Wait ~20–25 seconds (or it auto-refreshes).

> "The conversation is now a searchable memory."

Point out Carol Johnson's new card — it shows:
- **Summary**: "The user was evaluating Elasticsearch versus Pinecone for a RAG pipeline over a 500k-product-embedding dataset, with focus on kNN performance and operational overhead..."
- **Topic tags**: pricing, vector search, serverless, RAG pipeline
- The date and user name
- **⚡ workflow** badge (Kibana Workflow created this, not a script)

---

## Act 4 — Browse Episodic Memory (2 minutes)

**Stay on Episodic Memory tab.**

Show the existing cards (Alice Chen, Bob Smith, Carol Johnson are pre-loaded).

Click a card to expand it. Point out:

- **Summary** — written by the AI agent inside the Workflow, not hardcoded
- **Tags** — extracted topics (e.g. "kNN search, HNSW, vector similarity")
- **Importance score** — set by the workflow, can be tuned
- **Memory source** — ⚡ workflow vs 📄 imported

**Say:**

> "Every conversation across every user is stored here. This is the episodic layer — raw experiences, time-stamped."

---

## Act 5 — Show Semantic Memory (2 minutes)

**Click the Semantic Memory tab.**

Show the cards for Alice Chen, Bob Smith, Carol Johnson.

Click Alice's `vector_search` card. Point out:

- **Facts** — 3–5 sentences distilled from ALL of Alice's past conversations about vector search
- Not tied to one conversation — synthesized across her entire history
- Generated automatically when any episodic memory is saved — no manual trigger

**The smart part:** before writing, the semantic workflow embeds the new facts and runs a kNN search against existing semantic memories. If it finds a similar entity (similarity > 0.75), it **merges** the new knowledge into the existing card rather than creating a duplicate. If nothing similar exists, it creates a new card.

**Say:**

> "This is the semantic layer. Instead of replaying old conversations, the agent has standing knowledge about each user. Alice cares about latency at 1M vectors. Bob is migrating from Solr. Carol is price-sensitive. The agent knows this before the conversation starts."

> "And the system is smart about updates — it uses vector similarity to decide whether to merge new knowledge into an existing memory or create a new one. No duplicate entities, no stale overrides."

**The key architecture point:**

> "Four Kibana Workflows fire from one button — fetch, summarize, embed, index, distill, merge. No custom Python pipeline, no cron jobs, no external services."

---

## Act 5b — Show Procedural Memory (2 minutes)

**Click the Procedural Memory tab.**

Show the cards grouped by user. Click **Alice Chen's** `knn_benchmarking` card. Point out:

- **Procedure name** — "Elasticsearch kNN Benchmarking Setup"
- **Trigger** — exactly when to apply this procedure ("Apply this when planning or validating a kNN/vector search deployment...")
- **Steps** — 4-6 concrete, ordered actions extracted by the AI from Alice's conversation history

**Say:**

> "This is the third memory layer — procedural memory. Not what happened, not what's true — but *how to do it*. The AI watched Alice ask about kNN benchmarking across multiple conversations and extracted the optimal step-by-step playbook. Next time Alice starts a new session, the agent doesn't just know she cares about kNN — it knows the *exact procedure* that's worked for her problem type."

Show Bob Smith's `solr_to_elasticsearch_migration` card:

> "Bob is migrating from Solr. The agent has a personalized migration playbook — built from his own conversations, refined across sessions. This is how agents go from being stateless to genuinely skilled."

**The three-layer architecture:**

> "Episodic answers *what happened*. Semantic answers *what's true*. Procedural answers *how to act*. Three Kibana Workflows, three indices, one search engine — Elasticsearch."

---

## Act 6 — Memory Search (2 minutes)

**Click the 🔍 Memory Search tab.**

Two suggestion chips appear — click **"vector search performance at scale"** (no typing needed).

- Results come from **both** indices — episodic and semantic
- Ranked by vector similarity (kNN, Jina embeddings, 1024 dimensions)

**Say:**

> "One query searches across conversation history and synthesized knowledge simultaneously. This is native Elasticsearch kNN — the same engine powering your product search and log analytics."

Click the second chip: **"Python client async bulk indexing"**

Show that it finds Alice's conversation about async elasticsearch-py — even though the query phrasing is different. That's semantic search working.

---

## Act 7 — Memory Recall (technical customers, 2 minutes)

**Click the 🔎 Memory Recall tab.**

Select **Alice Chen** from the User dropdown. Type this in the context box:

> `I want to continue our work on vector search`

Click **Recall Memory**.

The UI shows three sections:
- **Episodic hits** — her most relevant past conversations, ranked by semantic similarity
- **Semantic hits** — her distilled knowledge about entities related to vector search
- **Procedural hits** — the step-by-step procedure most relevant to this context

Each result has a relevance score (kNN similarity).

**Say:**

> "This is the API your production app calls at the start of every new conversation. You get the most relevant past episodes, standing knowledge, and proven procedures for that user — all retrieved in a single round-trip. You inject that into the LLM context window. The agent now has memory across all three layers, without replaying the entire conversation history every time."

**For technical audiences**, show the raw API response:
```
http://localhost:5002/api/recall?user_id=alice_chen&context=I+want+to+continue+our+work+on+vector+search
```
Point out the `score` field on each hit — that's the kNN dot_product similarity from Jina v5 embeddings.

---

## Act 8 — Architecture Summary (1 minute)

Draw or point to this flow:

```
User chats with Agent Builder
        ↓
"Save to Agent Memory" triggers 4 workflows simultaneously
        ↓
Workflow 1: generate-episodic-memory (YAML, no code)
  → Fetch conversation from Kibana API
  → AI summarizes → AI extracts topic tags, entities, importance score
  → Index to episodic_memory (semantic_text field auto-embeds via Jina at index time)
        ↓
Workflows 2–4: generate-semantic-memory × 3 (one per knowledge entity)
  → Search ALL episodic memories for this user
  → AI distills 3–5 facts about the entity
  → Embed facts via Jina inference API → kNN search existing semantic_memory (same user)
  → Similarity > 0.75? → Merge with existing entity
  → Similarity ≤ 0.75? → Create new semantic memory
  → Index to semantic_memory (semantic_text field auto-embeds via Jina at index time)
        ↓
At next conversation start:
  → kNN query on all three indices (episodic + semantic + procedural)
  → Inject top results into LLM context window
  → Agent knows: what happened, what's true, how to act
```

**Closing line:**

> "Three memory layers. Four Kibana Workflows firing from one button. Three Elasticsearch indices. No external vector database, no Memzero, no ingest pipelines. Embeddings happen automatically via the `semantic_text` field type — Jina v5 runs as a built-in Elasticsearch inference endpoint. The AI is your existing Elastic AI assistant. Workflows are the unit of work that builds memory — and Elasticsearch is the engine that stores, indexes, and retrieves it."

---

## Act 9 — Memory Comparison: Before and After (2 minutes)

**Click the 🧪 Memory Demo tab.**

This is the "aha moment" tab. Select **Alice Chen** from the dropdown (pre-selected).

Two pre-loaded question chips appear — click the first:

> **"What were we working on last time, and what do you recommend we focus on next?"**

Click **⚡ Run Comparison**. The app sends the **same question** to the agent twice simultaneously:

| Left panel: 🚫 Without Memory | Right panel: 🧠 With Memory |
|---|---|
| Fresh conversation, no context | Alice's episodic, semantic, and procedural memories injected |
| Agent gives generic answer | Agent recalls Alice's specific work on kNN benchmarking, vector search latency, async Python client |

**What happens behind the scenes:**

> "On the left — a clean slate. The agent has no idea who Alice is. Generic answer.
>
> On the right — before asking the question, the app called `/api/recall` to retrieve Alice's top episodic episodes, synthesized semantic knowledge, and procedural memory about kNN. That context was injected into the conversation using the **Kibana Agent Builder attachments API** — the native Elastic way to attach memory to a conversation. Same agent, same question, completely different response."

Point out the **Injected Memory Context** section below the right panel — it shows pills for each memory that was retrieved:
- 📅 Episodic: recent conversation summaries
- 🧠 Semantic: standing knowledge about Alice's entities (vector_search, python_client, pricing)
- ⚙️ Procedural: her kNN benchmarking procedure

**Say:**

> "This is what production looks like. At the start of every new conversation, you call `/api/recall`, get the most relevant memories for that user, attach them to the conversation, and your agent instantly has context it would have taken 10 previous conversations to accumulate. No conversation replay, no external vector DB — pure Elasticsearch."

Click the second chip: **"Can you remind me of my specific concerns about Elasticsearch?"**

> "Without memory: the agent guesses. With memory: it knows Alice cares about latency at 1M vectors and cluster overhead for async bulk indexing — because those facts live in her semantic memory."

---

## Common Customer Questions

**Q: Can we use our own embedding model?**  
A: Yes — swap the inference endpoint. Any model in the Elasticsearch inference API works.

**Q: How does this scale?**  
A: Same as any ES index — billions of documents, distributed, with RBAC and audit logging built in.

**Q: What triggers the workflows in production?**  
A: Webhooks, scheduled triggers, or API calls from your app. Same Kibana Workflow, different trigger type.

**Q: What's the latency of the recall API?**  
A: kNN query on dense_vector index — typically <50ms for millions of documents.

**Q: Do we need Kibana?**  
A: Workflows and Agent Builder run in Kibana. The memory indices are pure Elasticsearch — you can query them from any app.

---

## Reset / Re-run Demo

To regenerate fresh conversations and memories:

```bash
source variables.env

# Re-run conversations + trigger workflows
python3 run_demo.py

# Or just trigger workflows for existing conversations
python3 setup_workflows.py  # re-registers YAMLs if changed
```
