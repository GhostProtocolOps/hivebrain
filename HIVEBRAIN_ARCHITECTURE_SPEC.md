# HIVEBrain Meta-Brain — Technical Specification
**Version:** 1.0 · **Owner:** Principal Systems Architect · **Status:** Production-Grade Design

---

## 1. Executive Summary

HIVEBrain is a **federated, append-only, MVCC-backed meta-brain** that lets N concurrent agents (Herdr, OpenDots, Paperclip, OpenClaw) read and write shared semantic state without lock contention. It borrows the **airline reservation paradigm**: reads are lock-free via MVCC snapshots; writes are front-loaded by atomic reservations and lease-based soft claims; the durable record is an append-only event log that asynchronously fans out to heavy layers (pgvector, graph).

The system is **4-layer federated** (Relational → JSONB → pgvector → Graphify), **dual-decomposition** (every prompt *and* response is decomposed into intent/entities/constraints and indexed everywhere), and **self-pruning** (5-day raw retention with permanent concept/centroid/metric preservation).

---

## 2. Architectural Diagram (Logical)

```
                     ┌──────────────────────────────────────────────┐
   Herdr ──┐         │            MCP Server: hivebrain-mcp         │
   OpenDots─┼───────►│  tools: read.* | reserve.* | claim.* | commit │
   Paperclip┤  (SSE)  │  resources: brain://entity/{id}              │
   OpenClaw ┘         └───────────────┬──────────────────────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │  Control Plane (Go/Rust service)   │
                    │  • OCC version-vector validator    │
                    │  • Reservation / Lease manager     │
                    │  • MVCC snapshot router            │
                    └───────┬───────────────────┬────────┘
                            │                   │
              ┌─────────────▼─────┐   ┌─────────▼─────────┐
              │  Event Log (WAL)  │   │  Read Router      │
              │  append-only      │   │  (snapshot reads) │
              │  partitioned/day  │   └─────────┬─────────┘
              └─────────┬─────────┘             │
                        │ async fan-out         │
        ┌───────────────┼───────────────┬───────┴────────┐
        ▼               ▼               ▼                ▼
   ┌─────────┐    ┌──────────┐    ┌──────────┐     ┌──────────┐
   │ L1 Rel. │    │ L2 JSONB │    │ L3 pgvec │     │ L4 Graph │
   │ PG      │    │ PG       │    │ HNSW     │     │ (PG+adj) │
   └─────────┘    └──────────┘    └──────────┘     └──────────┘
        │               │               │                │
        └───────────────┴───────┬───────┴────────────────┘
                                ▼
                 ┌───────────────────────────────┐
                 │ Distillation Engine (5-day)   │
                 │ → centroids, god nodes, agg   │
                 └───────────────┬───────────────┘
                                 ▼
                 ┌───────────────────────────────┐
                 │ Sim Live Process Viewer (SSE) │
                 └───────────────────────────────┘
```

---

## 3. Concurrency Model

### 3.1 Lock-Free MVCC Reads

Every agent read executes inside a `REPEATABLE READ` (or `SERIALIZABLE DEFERRABLE` for graph traversal) PostgreSQL snapshot. No `SELECT ... FOR UPDATE` on the read path. Snapshot isolation gives us:

- **Snapshot consistency:** All layers read at the same `xmin` boundary via a shared `snapshot_id` (a monotonic counter stored in `brain_snapshots`).
- **Read amplification guard:** Each MCP `read.*` call returns `{snapshot_id, layer_versions}` so clients can pin reads across layers.

**Invariant R1 (Read Isolation):** *For any agent A and any two layers L_i, L_j, if A reads at snapshot s, then `visible(L_i, s) ⊂ committed_at(s)` and `visible(L_j, s) ⊂ committed_at(s)`. No torn reads across layers.*

### 3.2 Front-Loaded Atomic Reservations

Before writing, an agent must **reserve** a slot:

```sql
-- reservations table
INSERT INTO reservations (reservation_id, entity_id, agent_id, ttl_ms, payload_hash)
VALUES ($1, $2, $3, 5000, $4)
ON CONFLICT (entity_id, active) DO NOTHING
RETURNING reservation_id;
```

Reservations are **atomic** (unique partial index on `(entity_id) WHERE active`), **TTL-bounded**, and **idempotent** via `payload_hash`.

### 3.3 Lease-Based Soft Claims

A reservation is a *hard* hold (short TTL, ~5s). A **lease** is a *soft claim* (longer TTL, ~60s) that lets an agent **read-modify-write** an entity without blocking other readers:

| Primitive | TTL | Blocks writers? | Blocks readers? | Use |
|-----------|-----|-----------------|-----------------|-----|
| Reservation | 5s | Yes (on same entity) | No | Commit window |
| Lease | 60s | No (advisory) | No | Distillation, long pipeline |
| Snapshot | ∞ | No | No | Reads |

**Invariant C1 (Claim Progress):** *Every active claim has `expires_at > now()`. Expired claims are reclaimed by the janitor within `2 × heartbeat_interval` (default 4s).*

**Invariant C2 (No Lost Updates):** *A commit is accepted iff `version_vector_merge(client_vv, server_vv) == client_vv + delta` and no conflicting reservation exists.*

### 3.4 Optimistic Concurrency Control (OCC)

Every entity carries a **version vector** `VV: Map<agent_id, uint64>`:

```
VV = { "herdr:7": 12, "opendots:3": 4, "paperclip:9": 1 }
```

On commit:

```python
def validate_commit(entity_id, client_vv, delta, server_vv):
    # 1. Client must have seen at least server's committed state
    for agent, seq in server_vv.items():
        if client_vv.get(agent, 0) < seq:
            raise StaleRead(entity_id, agent, server_vv,