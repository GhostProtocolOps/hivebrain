# HIVEBrain Meta-Brain — Technical Specification

**Version:** 2.0 · **Owner:** Principal Systems Architect · **Status:** Production-Grade Design

---

## 1. Executive Summary

HIVEBrain is a federated, append-only, MVCC-backed meta-brain enabling N concurrent agents (Herdr, OpenDots, Paperclip, OpenClaw) to read and write shared semantic state without lock contention. The system adopts the airline reservation paradigm: lock-free MVCC reads via snapshots, atomic reservations for commit windows, lease-based soft claims for long pipelines, and an append-only event log that fans out asynchronously to heavy layers (pgvector, Graphify).

The architecture is 4-layer federated (Relational → JSONB → pgvector → Graphify), employs dual-decomposition (every prompt and response decomposed into intent, entities, constraints, and metrics), and implements self-pruning with 5-day raw retention while permanently preserving concept centroids, god nodes, and metrics.

---

## 2. System Architecture

### 2.1 Logical Diagram

```
                     ┌─────────────────────────────────────────────────────┐
   Herdr ────────────┤                 MCP Server: hivebrain-mcp           │
   OpenDots ─────────┤  tools: brain_query | brain_ingest | brain_reserve  │
   Paperclip ────────┤  tools: brain_distill  (SSE transport)              │
   OpenClaw ─────────┤  resources: brain://entity/{id}                     │
                     └──────────────────┬──────────────────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
                    │       Control Plane Service           │
                    │  • OCC version-vector validator       │
                    │  • Reservation / Lease manager        │
                    │  • MVCC snapshot router               │
                    │  • Outbox fan-out coordinator         │
                    └───────┬───────────────┬───────────────┘
                            │               │
              ┌─────────────▼─────┐  ┌──────▼──────────────┐
              │  Commit Path      │  │  Read Path          │
              │  (L1 + L2 + Outbox)│ │  (Snapshot Router)  │
              └─────────┬─────────┘  └──────────┬──────────┘
                        │                       │
                        ▼                       ▼
              ┌──────────────────────────────────────────┐
              │  Event Log (WAL) — append-only           │
              │  partitioned by day                      │
              └──────────────┬───────────────────────────┘
                             │ async outbox fan-out
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ┌─────────┐         ┌──────────┐        ┌──────────┐
   │ L1 Rel. │         │ L2 JSONB │        │ Outbox   │
   │ PG      │         │ PG       │        │ (L3/L4)  │
   └─────────┘         └──────────┘        └────┬─────┘
        │                                      │
        ▼                                      ▼
   ┌─────────┐                         ┌──────────┐
   │ L3 pgvec│                         │ L4 Graph │
   │ HNSW    │                         │ (PG+adj) │
   └─────────┘                         └────┬─────┘
        │                                   │
        └───────────────────┬───────────────┘
                            ▼
                 ┌──────────────────────────────┐
                 │ Distillation Engine (5-day)  │
                 │ → centroids, god nodes, agg  │
                 │ → dead-letter queue          │
                 └──────────────┬───────────────┘
                                ▼
                 ┌──────────────────────────────┐
                 │ Sim Live Process Viewer      │
                 │ SSE port 5174                │
                 └──────────────────────────────┘
```

---

## 3. Data Model

### 3.1 Core Entities

| Table | Layer | Purpose |
|-------|-------|---------|
| `brain_entities` | L1 Relational | Canonical entity registry, version vector, active lease |
| `brain_events` | L1 Relational | Append-only event log, partitioned by day |
| `brain_json_state` | L2 JSONB | Flexible semantic payload per entity |
| `brain_outbox` | Outbox | Exactly-once fan-out records to L3/L4 |
| `brain_vector_index` | L3 pgvector | HNSW index over decomposed embeddings |
| `brain_graph_edges` | L4 Graphify | Adjacency list for concept graph |
| `brain_reservations` | Control | Atomic commit-window claims |
| `brain_leases` | Control | Soft claims with TTL |
| `brain_snapshots` | Control | Monotonic snapshot_id registry |
| `brain_distillation_log` | Distillation | Status of raw batch distillation |
| `brain_distillation_dlq` | Distillation | Dead-letter queue for failed events |

### 3.2 Dual-Decomposition Schema

Every `brain_ingest` call decomposes input into four indexed components:

```json
{
  "intent": "string",
  "entities": ["string"],
  "constraints": ["string"],
  "metrics": {"key": "value"}
}
```

Both prompts and responses undergo this decomposition and are written to L1, L2, L3, and L4.

---

## 4. Concurrency Model

### 4.1 Lock-Free MVCC Reads

All agent reads execute inside a `REPEATABLE READ` PostgreSQL snapshot, identified by a `snapshot_id` from `brain_snapshots`. No `SELECT ... FOR UPDATE` on the read path.

**Invariant R1 (Read Isolation):** For any agent A and layers L_i, L_j, if A reads at snapshot s, then `visible(L_i, s) ⊂ committed_at(s)` and `visible(L_j, s) ⊂ committed_at(s)`. No torn reads across layers.

Each MCP `brain_query` returns `{snapshot_id, layer_versions}` so clients can pin reads across layers.

### 4.2 Atomic Reservations

Before writing, an agent reserves a slot:

```sql
INSERT INTO brain_reservations (reservation_id, entity_id, agent_id, ttl_ms, payload_hash, commit_token)
VALUES ($1, $2, $3, 5000, $4, $5)
ON CONFLICT (entity_id) WHERE active DO NOTHING
RETURNING reservation_id;
```

Reservations use a unique partial index on `(entity_id) WHERE active`. They are TTL-bounded (~5s) and idempotent via `payload_hash` and `commit_token`.

### 4.3 Lease-Based Soft Claims

| Primitive | TTL | Blocks writers | Blocks readers | Use |
|-----------|-----|----------------|----------------|-----|
| Reservation | 5s | Yes (same entity) | No | Commit window |
| Lease | 60s | Advisory only | No | Distillation, long pipelines |
| Snapshot | ∞ | No | No | Reads |

**Invariant C1 (Claim Progress):** Every active claim has `expires_at > now()`. Expired claims are reclaimed by the janitor within `2 × heartbeat_interval` (default 4s).

### 4.4 Optimistic Concurrency Control

Every entity carries a version vector `VV: Map<agent_id, uint64>`.

On commit:
1. Client must have seen at least the server's committed state: for all `(agent, seq)` in `server_vv`, `client_vv.get(agent, 0) >= seq`.
2. Merge: `result_vv = version_vector_merge(client_vv, server_vv, delta)`.
3. Commit accepted iff `result_vv == client_vv + delta` and no conflicting active reservation exists.

**Invariant C2 (No Lost Updates):** A commit is accepted iff the version-vector merge condition holds and no conflicting reservation exists.

### 4.5 Deadlock Elimination

All entity reservations are acquired in total order by `entity_id` (ascending lexicographic) before any lock acquisition. Agents must sort their target entity IDs and reserve sequentially. This eliminates circular wait conditions and advisory-lock deadlocks.

---

## 5. Transactional Outbox Pattern

### 5.1 Commit Flow

1. Agent reserves entity slots in total order by `entity_id`.
2. Control plane begins transaction.
3. Write to `brain_entities` (L1) and `brain_json_state` (L2) within the same transaction.
4. Insert outbox records into `brain_outbox` with payload for L3 (pgvector) and L4 (Graphify) within the same transaction.
5. Commit transaction. L1/L2 are now ACID-consistent.
6. Background fan-out worker reads `brain_outbox`, writes to L3/L4, and marks records delivered with exactly-once semantics.

### 5.2 Read-Your-Writes Consistency

Clients receive `commit_token` and `snapshot_id` after commit. Subsequent `brain_query` calls with that `snapshot_id` or newer guarantee visibility of the committed write across L1 and L2. L3/L4 visibility is eventually consistent via outbox delivery, with staleness bounded by the fan-out interval.

---

## 6. Distillation and Pruning

### 6.1 5-Day Continuous Learning

Raw interaction rows are retained for 5 days. Purging occurs only when:

- `distillation_status = 'completed'` for the batch, AND
- Pre-prune reachability scan passes: `reference_count = 0` for all concepts referenced by the raw events.

Distilled knowledge (vector centroids, god nodes, relational milestones) is permanently preserved.

### 6.2 Dead-Letter Queue

Events that fail distillation are routed to `brain_distillation_dlq` with error context and retry metadata. They are not silently deleted. A replay mechanism allows operators to reprocess DLQ entries after remediation.

### 6.3 Janitor Process

- Reclaims expired leases and reservations every `2 × heartbeat_interval` (default 4s).
- Executes pre-prune reachability scans before raw retention purge.
- Publishes distillation status events to the Sim Live Process Viewer.

---

## 7. Performance and Reliability

### 7.1 Read/Write Separation

- Write path: primary PostgreSQL instance.
- Read path: read replicas for `brain_query`, isolated from write bursts.
- Connection pooling with `lock_timeout` and `statement_timeout` to fail fast instead of queuing.
- Token bucket caps write concurrency.

### 7.2 Latency Targets

- Snapshot reads on L1/L2: sub-10ms p99 under normal load.
- Write commit (L1 + L2 + outbox): sub-50ms p99.
- Outbox fan-out to L3/L4: sub-500ms p99.

### 7.3 Hot Partition Management

- Frequent queries materialized as precomputed snapshots.
- HNSW index builds on pgvector use `maintenance_work_mem` tuning and concurrent index creation where possible.
- Statement timeouts prevent long-running graph traversals from blocking the read pool.

---

## 8. MCP Server Contract

**Server:** `hivebrain-mcp`  
**Transport:** SSE

| Tool | Description |
|------|-------------|
| `brain_query` | Lock-free MVCC read across layers at a given `snapshot_id` |
| `brain_ingest` | Dual-decompose prompt/response and initiate commit |
| `brain_reserve` | Atomic reservation for commit window |
| `brain_distill` | Trigger distillation for a batch or entity |

**Resource:** `brain://entity/{id}`

---

## 9. Telemetry and Live Dashboard

Execution graph events are streamed to the Sim Live Process Viewer via SSE on port 5174. Events include:

- Reservation acquisition/release
- Commit acceptance/rejection with reason
- Outbox delivery success/failure
- Distillation batch start/complete/fail
- Pruning batch start/complete
- Lease expiry and reclamation

---

## 10. Invariants Summary

| ID | Invariant |
|----|-----------|
| R1 | No torn reads across layers at a given snapshot |
| C1 | Every active claim has `expires_at > now()` |
| C2 | No lost updates under OCC version-vector validation |
| D1 | Reservations acquired in total order by `entity_id` |
| O1 | L1/L2 commit is atomic with outbox insert |
| P1 | Raw purge only after distillation completion and reachability scan |
| P2 | Failed distillations go to dead-letter queue, not silent delete |

---