-- ==============================================================================
-- RFC-014: HIVEBrain Meta-Brain Database Schema (PostgreSQL 18 + pgvector)
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Snapshot Registry (Lock-free MVCC Snapshot tracking)
CREATE TABLE IF NOT EXISTS brain_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);

-- 2. Canonical Entity Registry (L1 Relational + OCC Version Vectors)
CREATE TABLE IF NOT EXISTS brain_entities (
    entity_id VARCHAR(128) PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    name VARCHAR(256) NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    version_vector JSONB NOT NULL DEFAULT '{}'::jsonb,
    active_lease_id VARCHAR(64),
    reference_count INT NOT NULL DEFAULT 0,
    is_distilled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Append-Only Event Log (WAL of prompts, responses, thoughts, decisions)
CREATE TABLE IF NOT EXISTS brain_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    raw_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    distillation_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    distilled_at TIMESTAMPTZ,
    reference_count INT NOT NULL DEFAULT 0
);

-- 4. Deconstructed Semantic JSONB State (L2 NoSQL)
CREATE TABLE IF NOT EXISTS brain_json_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES brain_events(event_id) ON DELETE CASCADE,
    entity_id VARCHAR(128) REFERENCES brain_entities(entity_id) ON DELETE CASCADE,
    intent VARCHAR(128) NOT NULL,
    entities JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    ast_representation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Dense Semantic Vector Index (L3 pgvector 384-dim)
CREATE TABLE IF NOT EXISTS brain_vector_index (
    vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES brain_events(event_id) ON DELETE CASCADE,
    entity_id VARCHAR(128),
    embedding vector(384) NOT NULL,
    semantic_cluster_id INT,
    is_centroid BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Knowledge Graph Adjacency List (L4 Graphify)
CREATE TABLE IF NOT EXISTS brain_graph_edges (
    edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(128) NOT NULL,
    target_id VARCHAR(128) NOT NULL,
    relationship_type VARCHAR(64) NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_god_node_edge BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Front-Loaded Atomic Reservations (Airline Ticket Booking Pattern)
CREATE TABLE IF NOT EXISTS brain_reservations (
    reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id VARCHAR(128) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    payload_hash VARCHAR(64) NOT NULL,
    commit_token VARCHAR(64) NOT NULL,
    ttl_ms INT NOT NULL DEFAULT 5000,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Lease-Based Soft Claims (Long pipelines & distillation)
CREATE TABLE IF NOT EXISTS brain_leases (
    lease_id VARCHAR(64) PRIMARY KEY,
    entity_id VARCHAR(128) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    purpose VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Transactional Outbox (Asynchronous Fan-out to L3 & L4)
CREATE TABLE IF NOT EXISTS brain_outbox (
    outbox_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    target_layer VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- 10. Distillation Execution Log
CREATE TABLE IF NOT EXISTS brain_distillation_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id VARCHAR(64) NOT NULL,
    raw_rows_examined INT NOT NULL,
    concepts_extracted INT NOT NULL,
    centroids_created INT NOT NULL,
    edges_synthesized INT NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. Dead-Letter Queue (DLQ) for Failed Distillations
CREATE TABLE IF NOT EXISTS brain_distillation_dlq (
    dlq_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    retry_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Pruning Audit Log (5-Day Reachability-Guarded Retention Audit)
CREATE TABLE IF NOT EXISTS brain_pruning_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purged_rows_count INT NOT NULL,
    retained_distilled_count INT NOT NULL,
    reachability_scanned_count INT NOT NULL,
    purged_before_timestamp TIMESTAMPTZ NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance & Integrity Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_reservations_active_entity 
    ON brain_reservations (entity_id) WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_events_created_at 
    ON brain_events (created_at);

CREATE INDEX IF NOT EXISTS idx_events_distill_status 
    ON brain_events (distillation_status);

CREATE INDEX IF NOT EXISTS idx_outbox_pending 
    ON brain_outbox (status, created_at) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_vector_hnsw 
    ON brain_vector_index USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_json_state_gin 
    ON brain_json_state USING gin (entities);

CREATE INDEX IF NOT EXISTS idx_graph_edges_src_tgt 
    ON brain_graph_edges (source_id, target_id);

CREATE INDEX IF NOT EXISTS idx_leases_expiry 
    ON brain_leases (expires_at);
