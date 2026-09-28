# Elastic Agent Memory Demo

A demonstration of episodic and semantic memory capabilities for AI agents using Elasticsearch. This project showcases how conversational AI systems can maintain, retrieve, and recall context across conversations by leveraging both raw episode storage and synthesized knowledge.

## Project Overview

### What is Agent Memory?

AI agents that interact with users over extended periods face a fundamental challenge: **how do they remember what happened before?**

This demo illustrates two complementary memory types:

- **Episodic Memory**: The raw record of what happened. "Alice asked about vector search performance on August 15."
- **Semantic Memory**: Synthesized knowledge extracted from episodes. "Alice is concerned about vector search latency with large datasets."

When a user returns in a new conversation, the agent can query these memories to:
1. Retrieve relevant past interactions (episodic)
2. Understand the user's preferences and constraints (semantic)
3. Construct a context window for the LLM without sending the entire conversation history
4. Deliver personalized, informed responses

### Why Elasticsearch?

Vector databases and semantic search are table-stakes for modern AI apps, but Elasticsearch provides:

- **Hybrid Search**: Combine vector similarity with BM25 full-text search (semantic + keyword)
- **Semantic Storage**: Native `dense_vector` type optimized for kNN search and filtering
- **Ingest Pipelines**: Automatic embedding generation within the indexing pipeline
- **Filtering at Scale**: Combine semantic search with metadata filters (user, date, importance)
- **Analytics**: Full-text queries, aggregations, and scoring for ranking memories by relevance
- **Production Ready**: RBAC, audit logging, backup/restore out of the box

### Why NOT alternatives?

- **Pinecone/Weaviate**: Vector-only; need separate DB for metadata and full-text search
- **Memzero**: Proprietary; limited to vector similarity; higher cost
- **Chroma/Milvus**: In-memory or lightweight; not production-grade for compliance/SLA requirements
- **PostgreSQL + pgvector**: Limited vector indexing; weak semantic search quality

---

## Architecture

### System Flow

The key differentiator is **Elastic Workflows** — Kibana's YAML-based automation engine. Workflows are the trigger that converts raw Agent Builder conversations into indexed memories.

```
┌──────────────────────────────────────────────────────────────┐
│           ELASTIC AGENT BUILDER (Conversations)               │
│   • User chats with the ES Support Analyst agent              │
│   • Multi-turn conversations stored in Kibana                 │
│   • Each conversation gets a conversation_id                  │
└──────────┬───────────────────────────────────────────────────┘
           │  conversation_id
           ▼
┌──────────────────────────────────────────────────────────────┐
│         ELASTIC WORKFLOW: generate_episodic_memory            │
│   Triggered manually or via API with conversation_id          │
│                                                               │
│   Step 1: kibana.request                                      │
│     GET /api/agent_builder/conversations/{id}                 │
│     → Fetches full conversation (all rounds)                  │
│                                                               │
│   Step 2: ai.agent (elastic-ai-agent)                         │
│     → Summarizes conversation in 2-3 sentences                │
│                                                               │
│   Step 3: ai.agent (elastic-ai-agent)                         │
│     → Extracts comma-separated topic tags                     │
│                                                               │
│   Step 4: elasticsearch.request                               │
│     PUT /episodic_memory/_doc/{id}?pipeline=episodic-embed    │
│     → Ingest pipeline auto-embeds summary → summary_vector    │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│      ELASTICSEARCH: episodic_memory index                     │
│   • summary (text) + summary_vector (dense_vector 1024d)      │
│   • Filterable by user_id, session_date, topics               │
│   • kNN search on summary_vector for semantic retrieval       │
└──────────┬───────────────────────────────────────────────────┘
           │  (after enough episodic memories accumulate)
           ▼
┌──────────────────────────────────────────────────────────────┐
│         ELASTIC WORKFLOW: generate_semantic_memory            │
│   Triggered per user/entity with user_id + entity_name        │
│                                                               │
│   Step 1: elasticsearch.request                               │
│     POST /episodic_memory/_search {term: {user_id: ...}}      │
│     → Fetches all episodic memories for the user              │
│                                                               │
│   Step 2: ai.agent (elastic-ai-agent)                         │
│     → Distills 3-5 factual sentences about this entity        │
│                                                               │
│   Step 3: elasticsearch.request                               │
│     PUT /semantic_memory/_doc/{id}?pipeline=semantic-embed    │
│     → Ingest pipeline auto-embeds facts → knowledge_vector    │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│      ELASTICSEARCH: semantic_memory index                     │
│   • facts (text) + knowledge_vector (dense_vector 1024d)      │
│   • One document per user/entity combination                  │
│   • kNN search on knowledge_vector for semantic recall        │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│         FLASK WEB UI + MEMORY RECALL API                      │
│   • Live chat with Agent Builder (tab 1)                      │
│   • Episodic memory browser (tab 2)                           │
│   • Semantic memory browser (tab 3)                           │
│   • Semantic search across both indices (tab 4)               │
│   • /api/recall — kNN retrieval per user + context            │
└──────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Technology | Role |
|-----------|-----------|------|
| Conversations | Elastic Agent Builder | Chat interface + conversation storage |
| Memory trigger | Elastic Workflows (Kibana YAML) | Orchestrates fetch → summarize → index |
| AI summarization | elastic-ai-agent (via Workflows) | Generates summaries and distills facts |
| Embeddings | Jina v5 (1024d) via ES inference | Converts text to vectors at index time |
| Memory store | Elasticsearch `dense_vector` | kNN search + metadata filtering |
| Ingest pipeline | ES `episodic-embed-pipeline` | Auto-embeds `summary` → `summary_vector` |
| Ingest pipeline | ES `semantic-embed-pipeline` | Auto-embeds `facts` → `knowledge_vector` |
| Demo UI | Flask + vanilla JS | 4-tab interface for customers |

### Data Model

#### Episodic Memory Document

```json
{
  "id": "episode-123",
  "user": "Alice Chen",
  "date": "2024-08-15T10:30:00Z",
  "summary": "Discussed vector search performance concerns with 1M+ vectors",
  "full_transcript": "...",
  "key_entities": ["vector search", "performance", "kNN", "1M+ vectors"],
  "topics": ["elasticsearch", "performance"],
  "emotional_valence": "neutral",
  "importance_score": 8.5,
  "embedding": [0.123, -0.456, ...],
  "conversation_id": "conv-456"
}
```

#### Semantic Memory Document

```json
{
  "id": "entity-vec-search",
  "entity_name": "Vector Search",
  "entity_type": "technology",
  "user": "Alice Chen",
  "facts": "Alice has evaluated kNN search at scale with 1M+ vectors. Primary concern is query latency (p99 > 100ms). Interested in tuning num_candidates and ef_construction.",
  "confidence": 92,
  "source_episodes": [3, 7, 12],
  "last_updated": "2024-08-22T14:15:00Z",
  "embedding": [0.234, -0.567, ...]
}
```

---

## Memory Types Explained

### Episodic Memory

**What**: A timestamped record of a user's specific interactions with the agent.

**Example from Demo**:
- Date: Aug 15, 2024
- User: Alice Chen
- Topic: "Discussed vector search performance"
- Key Entities: `[vector search, performance, kNN, 1M+ vectors]`
- Emotional Tone: Neutral (user was asking questions, not frustrated)
- Importance: 8.5/10 (technical detail, planning phase)

**Why it matters**: When Alice returns weeks later saying "Let's get back to what we were discussing," the agent can:
1. Retrieve this episode by user + date range + keyword match
2. Remind Alice of the exact context (not paraphrased or summarized)
3. Continue from where they left off

**Elasticsearch benefit**: Store episodes as dense vectors + full text. This allows both semantic similarity ("What did we talk about regarding performance?") and exact recall ("Show me conversations from Aug 15").

---

### Semantic Memory

**What**: Generalized, synthesized knowledge about a user extracted from multiple episodes over time.

**Example from Demo**:
- Entity: "Vector Search Performance"
- Type: Technology Concern
- Knowledge: "Alice has evaluated kNN at scale with 1M+ vectors. Concerns: query latency. Interested in tuning num_candidates."
- Confidence: 92% (derived from 3 mentions across 3 conversations)
- Source Episodes: 3 conversations from Aug, Sep, Sep

**Why it matters**: Instead of retrieving 10 episodic records and asking the LLM to synthesize, semantic memory provides pre-digested facts. The agent can instantly say: "Based on your past interest in vector search optimization, here's a solution..."

**Elasticsearch benefit**: kNN search makes finding relevant semantic knowledge fast. Confidence scores allow filtering for high-quality facts. Multiple lookups can run in parallel (one query for "vector search", another for "performance tuning").

---

## Elasticsearch Components

### Indices

#### `agent-memory-episodes`

Stores raw conversation episodes with hybrid search capability.

**Field Mapping**:

```yaml
properties:
  user:
    type: keyword                # Filter by user
  date:
    type: date                   # Time-range queries
  summary:
    type: text                   # Full-text search
    analyzer: standard
  full_transcript:
    type: text                   # Searchable conversation
  key_entities:
    type: keyword                # Tag-based filtering
  topics:
    type: keyword                # Category filtering
  emotional_valence:
    type: keyword                # positive | neutral | negative
  importance_score:
    type: float                  # Range filter & sort
  embedding:
    type: dense_vector           # Vector similarity search
    dims: 768
    index: true
    similarity: cosine
  conversation_id:
    type: keyword
  @timestamp:
    type: date
```

**Key Queries**:
- Vector similarity: Find episodes semantically similar to query
- BM25 text search: "Show me conversations about performance"
- Filtered search: "Episodes from Alice about Elasticsearch, sorted by importance"
- Range queries: "Conversations in the last 30 days"

#### `agent-memory-semantic`

Stores synthesized entity knowledge with confidence weighting.

**Field Mapping**:

```yaml
properties:
  entity_name:
    type: text                   # Alice's concern: Vector Search
  entity_type:
    type: keyword                # technology | person | concept | etc.
  user:
    type: keyword                # Which user this is about
  facts:
    type: text                   # Synthesized knowledge (multiple sentences)
  confidence:
    type: float                  # 0-100 (how certain is this fact?)
  source_episodes:
    type: integer                # Episode IDs that contributed to this
  last_updated:
    type: date                   # When this entity was last refreshed
  embedding:
    type: dense_vector           # Vector of the facts text
    dims: 768
    index: true
    similarity: cosine
```

**Key Queries**:
- Vector search on entity facts: "Find knowledge about this user's concerns"
- Confidence filtering: "Only retrieve facts > 85% confidence"
- User + type filtering: "All technology concerns mentioned by Alice"
- Recency: "Knowledge updated in last 60 days"

### Ingest Pipeline

The `agent-memory-embeddings` pipeline automatically generates vectors during indexing:

```yaml
pipeline:
  name: agent-memory-embeddings
  processors:
    - inference:
        model_id: sentence-transformers__all-minilm-l6-v2
        input_output:
          summary: embedding
```

This ensures:
- No manual embedding computation in application code
- Consistent embedding generation for all documents
- Automatic re-embedding when documents update

### Search Queries

#### Hybrid Search (Episodic)

```json
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.123, -0.456, ...],
    "k": 5,
    "num_candidates": 20,
    "filter": {
      "bool": {
        "must": [
          { "term": { "user": "Alice Chen" } },
          { "range": { "date": { "gte": "2024-08-01" } } }
        ]
      }
    }
  }
}
```

This query:
1. Finds 20 candidate episodes using vector similarity
2. Filters to only Alice's episodes after Aug 1
3. Returns top 5 by vector relevance

#### Metadata Filtering + Vector Search (Semantic)

```json
{
  "query": {
    "bool": {
      "must": [
        { "term": { "user": "alice" } },
        { "range": { "confidence": { "gte": 85 } } },
        { "term": { "entity_type": "technology" } }
      ],
      "should": {
        "knn": {
          "field": "embedding",
          "query_vector": [0.2, -0.5, ...],
          "k": 10
        }
      }
    }
  }
}
```

This retrieves Alice's high-confidence tech-related entities, scored higher if semantically similar to the query.

---

## Setup & Running

### Prerequisites

- Python 3.9+
- **Elastic Cloud deployment** with Kibana (required for Agent Builder + Workflows)
  - Jina embeddings inference endpoint: `.jina-embeddings-v5-text-small`
  - Agent Builder and Workflows features enabled
- API key with admin permissions

### 1. Clone & Install

```bash
git clone https://github.com/your-org/agent-memory-sunman.git
cd agent-memory-sunman
pip install -r requirements.txt
```

### 2. Configure Environment

Create `variables.env`:

```bash
ES_URL=https://your-cluster.es.us-east-1.aws.elastic.cloud
ES_ADMIN_API_KEY=your-base64-encoded-api-key
```

The Kibana URL is auto-derived: `.es.` → `.kb.`

### 3. Create Elasticsearch Indices + Pipelines

```bash
source variables.env && python3 setup_indices.py
```

Creates:
- `episodic_memory` index with `summary_vector` (dense_vector 1024d, dot_product)
- `semantic_memory` index with `knowledge_vector` (dense_vector 1024d, dot_product)
- `episodic-embed-pipeline` — embeds `summary` field → `summary_vector` via Jina
- `semantic-embed-pipeline` — embeds `facts` field → `knowledge_vector` via Jina

### 4. Register Kibana Workflows

```bash
source variables.env && python3 setup_workflows.py
```

Registers two YAML workflows in Kibana:
- `generate_episodic_memory` — fetches conversation → AI summarize → index to episodic_memory
- `generate_semantic_memory` — searches episodic memories → AI distill → index to semantic_memory

Saves workflow IDs to `workflow_ids.json` (used by app.py and run_demo.py).

### 5. Run the Demo (Agent Builder Conversations + Workflows)

```bash
source variables.env && python3 run_demo.py
```

This:
1. Creates 9 multi-turn conversations via Agent Builder API (3 users × 3 topics)
2. Triggers `generate_episodic_memory` workflow for each conversation
3. Waits for episodic workflows to complete
4. Triggers `generate_semantic_memory` workflow per user/entity

### 6. Start the Flask UI

```bash
source variables.env && python3 app.py
```

Open **http://localhost:5002** to explore:
- **Chat** tab — converse with the ES Support Analyst, trigger memory workflow after each conversation
- **Episodic Memory** tab — browse all conversation summaries
- **Semantic Memory** tab — browse synthesized entity knowledge
- **Search** tab — semantic kNN search across both indices

### Files

| File | Purpose |
|------|---------|
| `setup_indices.py` | Create ES indices + ingest pipelines |
| `setup_workflows.py` | Register Kibana Workflows; saves IDs to `workflow_ids.json` |
| `run_demo.py` | Create Agent Builder conversations + trigger workflows |
| `app.py` | Flask API + web UI server (port 5002) |
| `workflows/generate_episodic_memory.yaml` | Kibana Workflow YAML for episodic memory |
| `workflows/generate_semantic_memory.yaml` | Kibana Workflow YAML for semantic memory |
| `workflow_ids.json` | Auto-generated; maps `episodic`/`semantic` → Kibana workflow IDs |

---

## API Reference

All endpoints return JSON. The UI queries these endpoints via fetch.

### Episodes

#### `GET /api/episodes`

Fetch all episodic memory records.

**Query Parameters**: None (UI handles filtering)

**Response**:

```json
[
  {
    "id": "episode-1",
    "user": "Alice Chen",
    "date": "2024-08-15T10:30:00Z",
    "summary": "Discussed vector search performance...",
    "topics": ["elasticsearch", "performance"],
    "key_entities": ["vector search", "kNN", "1M+ vectors"],
    "emotional_valence": "neutral",
    "importance_score": 8.5
  },
  ...
]
```

---

### Semantic Memory

#### `GET /api/semantic`

Fetch all semantic memory (synthesized entities).

**Query Parameters**: None

**Response**:

```json
[
  {
    "id": "entity-1",
    "entity_name": "Vector Search Performance",
    "entity_type": "technology",
    "user": "Alice Chen",
    "facts": "Alice has evaluated kNN search at scale...",
    "confidence": 92,
    "source_episodes": 3,
    "last_updated": "2024-08-22T14:15:00Z"
  },
  ...
]
```

---

### Search

#### `GET /api/search`

Hybrid search across both episodic and semantic memory.

**Query Parameters**:
- `q` (string, required): Search query (e.g., "vector search performance")
- `type` (string, optional): `both` (default) | `episodic` | `semantic`
- `min_confidence` (int, optional): For semantic results, min confidence score (0-100)

**Response**:

```json
{
  "episodic": [
    {
      "id": "episode-1",
      "user": "Alice Chen",
      "date": "2024-08-15T10:30:00Z",
      "summary": "Discussed vector search performance...",
      "similarity": 0.92
    }
  ],
  "semantic": [
    {
      "id": "entity-1",
      "entity_name": "Vector Search",
      "entity_type": "technology",
      "facts": "Alice has evaluated kNN...",
      "user": "Alice Chen",
      "similarity": 0.88
    }
  ]
}
```

---

### Recall

#### `GET /api/recall`

Simulate agent memory recall for a new conversation context.

**Query Parameters**:
- `user_id` (string, required): User identifier (alice | bob | carol)
- `context` (string, required): New conversation context (e.g., "I'd like to continue our discussion about...")

**Response**:

```json
{
  "user": "Alice Chen",
  "interaction_count": 5,
  "episodic": [
    {
      "id": "episode-3",
      "user": "Alice Chen",
      "date": "2024-08-15T10:30:00Z",
      "summary": "Discussed vector search performance...",
      "relevance_score": 0.94
    }
  ],
  "semantic": [
    {
      "id": "entity-1",
      "entity_name": "Vector Search",
      "entity_type": "technology",
      "facts": "Alice has evaluated kNN...",
      "relevance_score": 0.89
    }
  ],
  "context_window": "AGENT MEMORY CONTEXT\n====================\n..."
}
```

---

## Demo Script for Customers

### Opening (2 min)

> "Today I want to show you a fundamental challenge with AI agents: **memory**. When a user talks to an AI assistant once, the assistant learns things—their preferences, their constraints, their domain knowledge. But when that user comes back a week later, the assistant has amnesia. We rebuild context from scratch.
>
> What if the agent could remember? Not just transcript chunks, but synthesized understanding of *who the user is and what they care about?* That's what Elastic Agent Memory does."

### Demo Flow (10 min)

**Tab 1: Episodic Memory (3 min)**

> "First, let's look at the raw material: **episodes**. Think of this as a log of every important conversation. Each card is a conversation the agent had. Notice:
> - Date and user (Alice, Bob, Carol)
> - What they discussed
> - Key entities extracted from the conversation
> - Emotional tone (was the user frustrated? Curious?)
> - Importance score (did this conversation matter?)
>
> You can filter by user, by tone, or sort by recency or importance. This is the first layer of memory: *what happened?*"

Show filtering by user = "Alice Chen". Show sorting by importance. Point out the importance scores and valence indicators.

**Tab 2: Semantic Memory (3 min)**

> "But storing raw conversations doesn't scale. Imagine an agent with 1000 conversations. Retrieving 100 relevant episodes and asking an LLM to synthesize takes time and tokens.
>
> So we do the synthesis *once*, upfront. **Semantic memory** is what the agent learned about each user. Instead of 'Alice asked about X on Aug 15', we have 'Alice is concerned about vector search latency at scale.'
>
> Notice the confidence score. If Alice only mentioned vector search once, confidence is lower. If she brought it up in 3 conversations, confidence is 92%. The agent knows to trust that fact."

Highlight the confidence bars. Click on a few entities to show different confidence levels. Point out the "source episodes" count.

**Tab 3: Memory Search (2 min)**

> "When the agent needs to find relevant memories, it searches using *vector embeddings*. This isn't keyword matching—it's semantic similarity.
>
> If I search for 'latency optimization', the system finds both explicit matches ('We discussed query latency') and conceptual matches ('We talked about making search faster').
>
> Here's the Elasticsearch advantage: we combine vector search *with* metadata filters. So we don't just find 'latency' globally—we find 'latency concerns that Alice mentioned, with high confidence, in the last 30 days.' This precision saves tokens and time."

Demonstrate a few searches. Show the similarity scores. Explain the difference between vector and keyword matching.

**Tab 4: Memory Recall (2 min)**

> "Finally, when Alice starts a new conversation, here's what happens behind the scenes:
> 1. Agent detects it's Alice
> 2. Agent queries: 'What do I know about Alice?'
> 3. Retrieves relevant episodes (the raw facts)
> 4. Retrieves synthesized knowledge (her concerns, preferences)
> 5. Formats as a context window
> 6. Passes to the LLM
>
> Now the LLM can say 'Welcome back, Alice. I see you were interested in vector search optimization. Here's an update...' *without ever retrieving the full transcripts.*"

Show the context window format. Explain how this compresses memory (5 conversations → 2-3 KB context window).

### Closing (2 min)

> "Why Elasticsearch for this?
> - **Hybrid search**: Vector + text search together
> - **Scalable**: Millions of episodes, searchable in milliseconds
> - **Flexible**: Combine any metadata filter with semantic search
> - **Production-ready**: RBAC, audit logs, observability built in
>
> This is a simple example—3 users, 15 conversations. But the same pattern scales to enterprise-grade systems. Imagine a customer support agent that remembers every interaction a customer had, or a sales assistant that knows your whole company's deal history. That's the power of Elastic Agent Memory."

---

## Key Concepts for Customers

### Episodic vs. Semantic Memory: Why Both?

**Episodic alone is inefficient**:
- 1000 conversations = 1000 records to potentially scan
- Even with vector search, retrieving 50 episodes and asking LLM to synthesize costs tokens
- User asks: "What was that thing we discussed?" → Agent needs exact recall (episodic strength)

**Semantic alone is incomplete**:
- "Alice cares about vector performance" (semantic) ≠ exact context of past discussion (episodic)
- Agent can't cite "On Aug 15 you mentioned..." without episodic record
- New learnings (hot facts) aren't in semantic layer until next batch sync

**Both together**: Fast, accurate, complete memory
- Semantic retrieval (fast) finds candidates
- Episodic retrieval (detailed) fills in specifics
- Agent has both generalized understanding + situational context

### Why Elasticsearch vs. Pinecone / Weaviate?

| Dimension | Elasticsearch | Pinecone | Weaviate |
|-----------|---------------|----------|----------|
| **Vector Search** | ✓ (kNN, HNSW) | ✓ Native | ✓ Native |
| **Full-Text Search** | ✓ BM25, regex, etc. | ✗ No | ✗ No |
| **Hybrid Ranking** | ✓ Native | ✗ Must build | ✗ Must build |
| **Metadata Filtering at Scale** | ✓ Efficient | ✓ Yes | ✓ Yes |
| **Self-Hosted / Sovereign** | ✓ Yes | ✗ SaaS only | ✓ Yes |
| **Multi-Tenancy** | ✓ Spaces, RBAC | ✓ Limited | ✓ Limited |
| **Cost (at scale)** | ✓ Lower (open) | ✗ Higher | ✓ Comparable |

**When to choose Elasticsearch**:
- You need full-text search + vector search together
- You want fine-grained filtering + ranking
- You have compliance/data-residency requirements
- You want one platform for search + observability + security

### Confidence Scoring in Semantic Memory

Confidence isn't "how sure is the system" but "how validated is this knowledge?"

**Examples**:
- Entity appears in 1 episode → 60% confidence (single mention, could be ephemeral)
- Entity appears in 3+ episodes with consistent facts → 90% confidence (established pattern)
- Fact explicitly confirmed by user → 95% confidence
- Fact inferred from user behavior (user never asked about X, only about Y) → 70% confidence

In queries, the agent can request `min_confidence: 90` to avoid acting on weak signals.

---

## Extension Ideas

### 1. **Real-Time Episode Ingestion**

**Current**: Load sample data, static demo

**Production**: After each conversation, automatically:
1. Call Claude to summarize & extract entities
2. Generate embeddings with Jina
3. Write to Elasticsearch (ingest pipeline handles vectors)
4. Trigger semantic consolidation

**Implementation**:
```python
@app.route('/conversations', methods=['POST'])
def ingest_conversation():
    transcript = request.json['transcript']
    user_id = request.json['user_id']
    
    # Summarize
    summary, entities = summarize_with_claude(transcript)
    
    # Store episodic
    episode_doc = {
        'user': user_id,
        'date': datetime.now(),
        'summary': summary,
        'key_entities': entities,
        # ... Elasticsearch ingests & embeds
    }
    es.index(index='agent-memory-episodes', body=episode_doc)
    
    # Later: batch semantic consolidation
    return {'status': 'indexed'}
```

### 2. **Semantic Consolidation Job**

**Current**: Semantic memory is pre-computed in sample data

**Production**: Periodic batch job (e.g., nightly) that:
1. Queries all episodes from a user
2. Uses LLM to synthesize entities and facts
3. Merges with existing semantic memory (update confidence, source_episodes)
4. Recomputes embeddings
5. Prunes low-confidence entities (< 60%)

**Implementation**:
```bash
# Run nightly
0 2 * * * python scripts/semantic_consolidation.py --date-range 7d
```

### 3. **Agent-Facing Recall API**

**Current**: Demo UI calls `/api/recall` with hardcoded user

**Production**: Agent (Claude, GPT, etc.) calls recall API automatically:

```python
# Agent pseudocode
def respond_to_user(user_id: str, message: str, conversation_id: str):
    # Recall memories
    memories = recall_memories(user_id, message, top_k=5)
    
    # Construct context
    context = format_memory_context(memories)
    
    # Prompt
    prompt = f"""
    {context}
    
    User: {message}
    """
    
    response = claude.messages.create(
        model="claude-3-5-sonnet",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content
```

### 4. **Multi-Modal Memory**

**Current**: Text-only episodes and semantic facts

**Production**: Store rich metadata from conversations:
- Chat attachments (docs, images, code)
- Structured data (JSON configs, outputs)
- Time series (benchmarks, metrics)
- Web links referenced

**Implementation**:
```json
{
  "summary": "Discussed Elasticsearch capacity planning",
  "attachments": [
    {
      "type": "benchmark",
      "url": "s3://memory-store/bench-123.json",
      "embedded_summary": "2M documents, 500GB heap, p99 search latency 200ms"
    }
  ]
}
```

### 5. **Audit & Compliance**

**Current**: No logging of memory access

**Production**: Track all memory queries & recalls for audit:

```python
def log_memory_access(user_id, agent_id, query, results_count, timestamp):
    es.index(index='agent-memory-audit', body={
        'user_id': user_id,
        'agent_id': agent_id,
        'query': query,
        'results_returned': results_count,
        '@timestamp': timestamp,
        'ip': request.remote_addr,
        'action': 'memory_recall'
    })
```

This enables compliance teams to answer: "What did the agent remember about this user?" or "Which agents accessed this user's memory?"

### 6. **Forgetting / Privacy**

**Current**: All memory is permanent

**Production**: Support user requests to be forgotten:

```python
@app.route('/users/<user_id>/forget', methods=['POST'])
def forget_user(user_id):
    # Delete episodic records
    es.delete_by_query(
        index='agent-memory-episodes',
        body={'query': {'term': {'user': user_id}}}
    )
    
    # Delete semantic records
    es.delete_by_query(
        index='agent-memory-semantic',
        body={'query': {'term': {'user': user_id}}}
    )
    
    return {'status': 'forgotten', 'deleted_episodes': ...}
```

### 7. **Competitive Analysis Memory**

**Current**: User-centric memory only

**Production**: Track competitive intelligence, product changes, market events:

```json
{
  "entity_name": "Claude Opus",
  "entity_type": "competitor_product",
  "facts": "Anthropic released Claude 3 in March 2024 with improved coding...",
  "associated_users": ["alice", "bob"],  // Users who asked about it
  "external_source": true
}
```

### 8. **Retrieval Augmented Generation (RAG) Integration**

**Current**: Memory recall returns pre-formed facts

**Production**: Feed recall results + external docs to LLM for synthesis:

```python
# Agent
memories = recall_memories(user_id, context)
documents = rag_search(user_query)  # Search knowledge base

prompt = f"""
Context from user history:
{memories}

Relevant documents:
{documents}

Answer user question.
"""
```

---

## Troubleshooting

### "Connection refused: Cannot reach Elasticsearch"

Check Elasticsearch is running:
```bash
curl -u elastic:changeme http://localhost:9200
```

If using Docker:
```bash
docker ps  # Verify container is running
docker logs <container-id>  # Check for startup errors
```

### "No indices found"

Run setup:
```bash
python scripts/setup_indices.py
python scripts/load_sample_data.py
```

### Embeddings are all zeros

Check the Jina API key or embeddings model is loaded:
```bash
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('all-minilm-l6-v2'); print(m.encode('test'))"
```

### Search results are poor quality

Try adjusting:
- `k` (number of candidates in kNN)
- `num_candidates` (pre-filter pool)
- Confidence threshold in semantic queries
- Similarity threshold (0.5 vs 0.7)

---

## Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -am 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a PR

---

## License

MIT License. See LICENSE file for details.

---

## Questions?

- Email: sunile.manjee@elastic.co
- Docs: https://www.elastic.co/guide/en/elasticsearch/reference/current/
- Demo: https://cloud.elastic.co (try free tier)
