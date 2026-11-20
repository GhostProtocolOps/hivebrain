**Concurrency deadlock and race risks**

PostgreSQL advisory locks used for lease-based claims can serialize writers and deadlock if two agents reserve overlapping entities in different orders. The OCC version-vector validator risks lost updates under write bursts because concurrent commits can pass validation against stale snapshots and then collide at commit time, causing abort storms. Graphify adjacency writes are not covered by the same MVCC snapshot isolation as the relational layer, so concurrent edge mutations can create dangling pointers or duplicate edges unless you use advisory locks or `SELECT ... FOR SKIP LOCKED` on edge rows. The append-only WAL itself is safe, but the async fan-out to pgvector and Graphify is not transactionally atomic with the commit, so readers can see a commit in L1 that is missing from L3/L4 until fan-out completes.

**5-day pruning safety**

Five-day raw retention is unsafe if distillation has not completed. A concept referenced by a day-6 event but never surfaced in a centroid or metric will be permanently lost. You need a reference-count or reachability check before pruning raw events, plus a dead-letter queue for events that fail distillation so they are not silently deleted.

**Sub-10ms query guarantees under write bursts**

Snapshot reads on L1/L2 can meet sub-10ms targets only if read replicas are isolated from write bursts and hot partitions are cached. Heavy writes will bloat indexes, trigger autovacuum, and cause WAL contention on pgvector HNSW builds, spiking p99 latency. You must separate read and write paths, use connection pooling with statement timeouts, and materialize frequent queries as precomputed snapshots rather than joining live layers during bursts.

**Concrete hardening recommendations**

1. Total-order all entity reservations by entity ID to prevent advisory-lock deadlocks.
2. Make fan-out to pgvector and Graphify synchronous within the commit transaction, or use an outbox table with exactly-once delivery and read-your-writes consistency.
3. Add a pre-prune reachability scan: retain raw events that are referenced by uncommitted concepts or missing centroids.
4. Deploy read replicas for `brain_query`, cap write concurrency with a token bucket, and set `lock_timeout` plus `statement_timeout` to fail fast instead of queuing.
5. Add idempotent commit tokens so retried reservations do not create duplicate events.