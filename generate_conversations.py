#!/usr/bin/env python3
"""
Generate synthetic conversations for episodic memory demo.

Creates 15 realistic conversations across 3 users:
  - Alice Chen: Data scientist evaluating Elasticsearch for ML/vector search
  - Bob Smith: DevOps engineer migrating from Apache Solr
  - Carol Johnson: Startup CTO evaluating search platforms

Saves to conversations.json
"""

import json
from datetime import datetime


def generate_conversations():
    """Generate 15 synthetic conversations for episodic memory demo."""

    conversations = []

    # =========================================================================
    # Alice Chen - Data Scientist (5 conversations, Aug 1-25, 2026)
    # =========================================================================
    alice_conversations = [
        {
            "conversation_id": "conv_001",
            "user_id": "alice_chen",
            "user_name": "Alice Chen",
            "session_date": "2026-08-01T10:00:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Can you explain how kNN search works in Elasticsearch? I'm specifically interested in dense vector fields and whether the search is approximate or exact."
                },
                {
                    "role": "assistant",
                    "content": "kNN search in Elasticsearch uses HNSW (Hierarchical Navigable Small World) algorithm for approximate nearest neighbor search by default, which provides a great balance between speed and accuracy. Dense vector fields store embeddings and enable similarity searches, with approximate search being much faster than exact for large datasets. You can also perform exact kNN search if needed, though it's slower and used mainly for smaller result sets or when you need guaranteed accuracy."
                },
                {
                    "role": "user",
                    "content": "What about performance with over 1 million vectors? Will HNSW handle that well?"
                },
                {
                    "role": "assistant",
                    "content": "HNSW scales well to millions of vectors and is specifically designed for that use case. Performance depends on factors like vector dimensions, shard configuration, and hardware. With proper shard sizing (typically 1-5GB per shard for dense vectors), you can expect sub-millisecond latency on queries. Consider using smaller vector dimensions when possible and testing with your specific data distribution."
                }
            ]
        },
        {
            "conversation_id": "conv_002",
            "user_id": "alice_chen",
            "user_name": "Alice Chen",
            "session_date": "2026-08-05T14:30:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How does Elasticsearch serverless pricing work compared to managed deployments? I need to budget for 500k vectors."
                },
                {
                    "role": "assistant",
                    "content": "Serverless pricing is based on your actual usage (compute and storage) with no fixed costs, making it ideal for variable workloads. For 500k vectors at 1024 dimensions, you're looking at roughly 2-4GB of storage depending on metadata. Serverless charges per GB of storage and per compute unit, typically costing less than managed if you have unpredictable traffic patterns."
                },
                {
                    "role": "user",
                    "content": "What about data transfer fees? Are there hidden costs I should know about?"
                },
                {
                    "role": "assistant",
                    "content": "Inbound data transfer is typically free, but outbound traffic from Elasticsearch to external services may incur charges depending on your cloud provider and region. Storage costs are the main variable for vector workloads. I'd recommend using the Elastic pricing calculator with your expected query volume and data size to get an accurate estimate."
                }
            ]
        },
        {
            "conversation_id": "conv_003",
            "user_id": "alice_chen",
            "user_name": "Alice Chen",
            "session_date": "2026-08-10T09:15:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Does the elasticsearch-py client support async operations? I want to integrate with LangChain for ML workloads."
                },
                {
                    "role": "assistant",
                    "content": "Yes, elasticsearch-py 8.0+ has excellent async support through AsyncElasticsearch class. It also supports bulk indexing, connection pooling, and has full compatibility with LangChain's vector store integrations. The client handles retries and load balancing automatically."
                },
                {
                    "role": "user",
                    "content": "How about compatibility with LangChain specifically? Any gotchas?"
                },
                {
                    "role": "assistant",
                    "content": "LangChain's Elasticsearch integration works seamlessly with the Python client. Just make sure you're using version 8.0 or later and that your dense vector fields are properly configured. The main consideration is ensuring your embeddings match the vector dimensions defined in your index (1024 for Jina in this case)."
                }
            ]
        },
        {
            "conversation_id": "conv_004",
            "user_id": "alice_chen",
            "user_name": "Alice Chen",
            "session_date": "2026-08-15T11:45:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "What latency should I expect when running kNN queries? How do I benchmark performance for my specific use case?"
                },
                {
                    "role": "assistant",
                    "content": "Query latency typically ranges from 10-100ms depending on dataset size, shard configuration, and hardware. For benchmarking, Elastic provides the Rally tool which can simulate realistic query patterns. You can also write custom Python scripts to measure p50, p95, and p99 latencies under your expected load."
                },
                {
                    "role": "user",
                    "content": "What's the optimal shard configuration for ML workloads with millions of vectors?"
                },
                {
                    "role": "assistant",
                    "content": "Target 1-5GB per shard as a general rule; for dense vectors, aim toward the lower end (1-2GB) to keep memory usage reasonable. With 500k vectors at 1024 dims, that's roughly 2-4GB, so 1-2 shards would be appropriate. Monitor heap usage and query latency to fine-tune further."
                }
            ]
        },
        {
            "conversation_id": "conv_005",
            "user_id": "alice_chen",
            "user_name": "Alice Chen",
            "session_date": "2026-08-25T16:20:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How can I combine BM25 full-text search with kNN vector search? What's RRF and should I use it?"
                },
                {
                    "role": "assistant",
                    "content": "Hybrid search combines BM25 (lexical) and kNN (semantic) results for better relevance. RRF (Reciprocal Rank Fusion) is a technique that merges these result sets while avoiding score normalization issues. It's ideal when you want both keyword and semantic matches."
                },
                {
                    "role": "user",
                    "content": "What about query time vs index time tradeoffs? Are there boosting strategies I should consider?"
                },
                {
                    "role": "assistant",
                    "content": "Query-time boosting offers more flexibility and faster experimentation but costs more CPU. Index-time boosting is set once and is faster at query time. For hybrid search, query-time boosting of BM25 and kNN components separately gives you the most control. Start with equal weights (0.5/0.5) and adjust based on your relevance metrics."
                }
            ]
        }
    ]

    # =========================================================================
    # Bob Smith - DevOps Engineer (5 conversations, Aug 3-28, 2026)
    # =========================================================================
    bob_conversations = [
        {
            "conversation_id": "conv_006",
            "user_id": "bob_smith",
            "user_name": "Bob Smith",
            "session_date": "2026-08-03T08:00:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "We're migrating from Apache Solr to Elasticsearch. What are the main schema differences I need to know about?"
                },
                {
                    "role": "assistant",
                    "content": "Elasticsearch uses JSON mappings instead of XML schemas. Key differences: field types are defined per field (not in schema.xml), analysis chains are configured differently, and Elasticsearch handles dynamic field creation. The query syntax is also different - Elasticsearch uses Query DSL instead of Solr's query parser."
                },
                {
                    "role": "user",
                    "content": "What's the equivalent of SolrJ client in Elasticsearch ecosystem?"
                },
                {
                    "role": "assistant",
                    "content": "The elasticsearch-py client for Python and elasticsearch-java for Java are direct equivalents. There's also the low-level REST API if you need language-agnostic solutions. Most teams find the language-specific clients more convenient for application code."
                }
            ]
        },
        {
            "conversation_id": "conv_007",
            "user_id": "bob_smith",
            "user_name": "Bob Smith",
            "session_date": "2026-08-08T13:30:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How should I architect a cluster for 50M documents? Should I use hot-warm-cold nodes?"
                },
                {
                    "role": "assistant",
                    "content": "Hot-warm-cold architecture is excellent for time-series data. Hot nodes handle recent writes, warm nodes are for older data still in frequent use, and cold nodes for archival. For 50M documents, you'd typically need 3+ master nodes, several data nodes depending on your hardware, and consider dedicated ingestion nodes for high-volume indexing."
                },
                {
                    "role": "user",
                    "content": "What about shard allocation strategy? How many shards for 50M documents?"
                },
                {
                    "role": "assistant",
                    "content": "Aim for shards in the 20-50GB range, so 50M documents would need roughly 5-15 shards depending on document size. Use shard allocation awareness to distribute replicas across hot/warm/cold tiers. Consider future growth - it's easier to plan upfront than to reindex later."
                }
            ]
        },
        {
            "conversation_id": "conv_008",
            "user_id": "bob_smith",
            "user_name": "Bob Smith",
            "session_date": "2026-08-12T10:15:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "What monitoring and alerting capabilities does Elasticsearch provide? How do I integrate with PagerDuty?"
                },
                {
                    "role": "assistant",
                    "content": "Elasticsearch Monitoring collects detailed metrics on cluster health, node performance, and query latency. Kibana provides dashboards for visualization. For alerting, use Kibana Alerting to detect issues like high heap usage or slow queries, then route notifications to PagerDuty via webhooks."
                },
                {
                    "role": "user",
                    "content": "How do I set up alerts for slow queries specifically?"
                },
                {
                    "role": "assistant",
                    "content": "Use Kibana's Alerting feature to create rules based on slow log indices. Define thresholds (e.g., queries taking over 500ms) and actions (notification to PagerDuty). You can also enable query profiling to understand query performance bottlenecks in detail."
                }
            ]
        },
        {
            "conversation_id": "conv_009",
            "user_id": "bob_smith",
            "user_name": "Bob Smith",
            "session_date": "2026-08-20T15:45:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How do snapshot and backup work in Elasticsearch? Can I automate the process?"
                },
                {
                    "role": "assistant",
                    "content": "Snapshots capture your cluster state at a point in time and store them in repositories (S3, GCS, local filesystem, etc.). You can automate snapshots using Snapshot Lifecycle Management (SLM) policies that define frequency, retention, and deletion rules. Restoration is straightforward - select a snapshot and restore specific indices."
                },
                {
                    "role": "user",
                    "content": "What about cross-cluster replication for disaster recovery?"
                },
                {
                    "role": "assistant",
                    "content": "Cross-cluster replication keeps a secondary cluster in sync with your primary for failover scenarios. It uses CCR which continuously replicates data at the index level. It's ideal for active-passive DR setups and can provide better RPO/RTO than snapshots alone."
                }
            ]
        },
        {
            "conversation_id": "conv_010",
            "user_id": "bob_smith",
            "user_name": "Bob Smith",
            "session_date": "2026-08-28T09:30:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How do I set up TLS encryption for Elasticsearch? What about field-level security and LDAP integration?"
                },
                {
                    "role": "assistant",
                    "content": "TLS is configured per node in elasticsearch.yml with certificates. For authentication, LDAP integrates with X-Pack security realms. Field-level security is a paid feature allowing you to restrict access to specific document fields based on roles. Audit logging captures all security events for compliance."
                },
                {
                    "role": "user",
                    "content": "What's the proper way to set up role-based access control?"
                },
                {
                    "role": "assistant",
                    "content": "Define roles in Kibana or via the Security API, specifying permissions for indices and operations. Users are assigned roles, which determine what they can access and modify. Common patterns include read-only roles for analysts, admin roles for operators, and restricted roles for applications."
                }
            ]
        }
    ]

    # =========================================================================
    # Carol Johnson - Startup CTO (5 conversations, Aug 5-30, 2026)
    # =========================================================================
    carol_conversations = [
        {
            "conversation_id": "conv_011",
            "user_id": "carol_johnson",
            "user_name": "Carol Johnson",
            "session_date": "2026-08-05T12:00:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How does Elasticsearch compare to Algolia, OpenSearch, and Typesense for a startup? What are the pros and cons?"
                },
                {
                    "role": "assistant",
                    "content": "Elasticsearch is feature-rich and handles complex queries well but requires more operational overhead. Algolia excels at autocomplete and fast hosting but is pricier. OpenSearch is open-source like Elasticsearch but has a smaller community. Typesense is lightweight and developer-friendly but newer. For startups, it depends on your data size, query complexity, and team ops capacity."
                },
                {
                    "role": "user",
                    "content": "Which would you recommend for search-first UX with vector capabilities?"
                },
                {
                    "role": "assistant",
                    "content": "Elasticsearch or OpenSearch are your best bets for vector search. Algolia is adding vector capabilities but is still primarily optimized for traditional search. Typesense has some vector support but less mature. Elasticsearch serverless removes operational burden while giving you the full feature set."
                }
            ]
        },
        {
            "conversation_id": "conv_012",
            "user_id": "carol_johnson",
            "user_name": "Carol Johnson",
            "session_date": "2026-08-12T14:20:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Can you help me estimate total cost of ownership? We expect 10k, 100k, and 1M documents at different growth stages."
                },
                {
                    "role": "assistant",
                    "content": "For 10k documents, serverless costs almost nothing (~$10-50/month). At 100k, you're looking at $50-200/month. At 1M, costs depend heavily on query volume and retention - typically $200-1000/month for moderate loads. Use Elastic's pricing calculator for exact estimates based on your region and query patterns."
                },
                {
                    "role": "user",
                    "content": "What about self-hosted vs Elastic Cloud costs?"
                },
                {
                    "role": "assistant",
                    "content": "Self-hosted has lower per-GB costs but requires ops overhead (infrastructure, monitoring, upgrades). Elastic Cloud serverless is best for variable workloads and reduces ops burden. At startup stage, serverless typically wins on total cost when you factor in team time."
                }
            ]
        },
        {
            "conversation_id": "conv_013",
            "user_id": "carol_johnson",
            "user_name": "Carol Johnson",
            "session_date": "2026-08-18T10:45:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "How's the developer experience? We're a Node.js shop. Is documentation good and is there active community support?"
                },
                {
                    "role": "assistant",
                    "content": "Elasticsearch has excellent documentation and a large, active community. The Node.js client (@elastic/elasticsearch) is first-class and well-maintained. Stack Overflow has thousands of answered questions, and Elastic has a community forum for support."
                },
                {
                    "role": "user",
                    "content": "What about local development setup? Can I run it in Docker?"
                },
                {
                    "role": "assistant",
                    "content": "Yes, Elasticsearch runs perfectly in Docker. Elastic provides official images, and docker-compose makes local setup trivial. You get full feature parity locally, making development and testing seamless. This is ideal for startup iteration cycles."
                }
            ]
        },
        {
            "conversation_id": "conv_014",
            "user_id": "carol_johnson",
            "user_name": "Carol Johnson",
            "session_date": "2026-08-22T16:30:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "What about AI features? Does Elasticsearch have ELSER, semantic search, or QA capabilities? Can I integrate with OpenAI?"
                },
                {
                    "role": "assistant",
                    "content": "ELSER (Elastic Learned Sparse Encoder) enables semantic search without external embeddings. You can also bring your own embeddings from OpenAI, Cohere, or open-source models. Elasticsearch has built-in inference capabilities for these integrations. For Q&A, combine semantic search with LLM APIs to build RAG applications."
                },
                {
                    "role": "user",
                    "content": "How hard is it to build a RAG pipeline using Elasticsearch and OpenAI?"
                },
                {
                    "role": "assistant",
                    "content": "It's straightforward with elasticsearch-py and openai libraries. Index your documents with embeddings, search semantically, then feed results to OpenAI's API for generation. Python makes this workflow simple - most teams build working prototypes in hours."
                }
            ]
        },
        {
            "conversation_id": "conv_015",
            "user_id": "carol_johnson",
            "user_name": "Carol Johnson",
            "session_date": "2026-08-30T13:15:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "What enterprise features does Elasticsearch offer? SLA guarantees, support tiers, compliance certifications?"
                },
                {
                    "role": "assistant",
                    "content": "Elastic Cloud offers 99.95% SLA for production deployments. Support tiers range from community to dedicated success managers. Compliance includes SOC2, HIPAA, PCI-DSS, and GDPR certifications depending on your plan. Enterprise features include advanced security, machine learning, and observability."
                },
                {
                    "role": "user",
                    "content": "Do you offer professional services for implementation and optimization?"
                },
                {
                    "role": "assistant",
                    "content": "Yes, Elastic Services provides consulting for architecture design, migration planning, optimization, and training. They help startups architect for scale from day one, reducing future technical debt and accelerating time-to-market."
                }
            ]
        }
    ]

    # Combine all conversations
    conversations.extend(alice_conversations)
    conversations.extend(bob_conversations)
    conversations.extend(carol_conversations)

    # Save to file
    output_file = "conversations.json"
    with open(output_file, "w") as f:
        json.dump(conversations, f, indent=2)

    print("="*60)
    print("Conversation Generation Complete")
    print("="*60)
    print(f"\nGenerated {len(conversations)} conversations:")
    print(f"  - Alice Chen (alice_chen): 5 conversations (Aug 1-25)")
    print(f"  - Bob Smith (bob_smith): 5 conversations (Aug 3-28)")
    print(f"  - Carol Johnson (carol_johnson): 5 conversations (Aug 5-30)")
    print(f"\nSaved to: {output_file}")


if __name__ == "__main__":
    generate_conversations()
