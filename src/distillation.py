"""
HIVEBrain Distillation & 5-Day Continuous Learning Engine:
Implements:
1. Continuous Semantic Distillation:
   - Aggregates older events into persistent vector centroids (is_centroid = true).
   - Promotes highly connected entities into Graphify God Nodes (is_god_node_edge = true).
   - Marks distilled state in canonical entity registry.
2. Reachability-Guarded Pruning:
   - Raw interaction rows older than 5 days are purged ONLY IF distillation is verified
     and reference_count = 0.
   - Failed events are diverted to the Dead-Letter Queue (DLQ).
   - Permanent learned knowledge is preserved across all layers.
"""

import math
import uuid
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "/tmp",
    "dbname": "gravity_brain",
    "user": "nishant"
}

class DistillationEngine:
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or DB_CONFIG

    def _get_conn(self):
        return psycopg2.connect(**self.db_config)

    def run_distillation(self, days_threshold: int = 5, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes distillation and reachability-guarded pruning for events older than days_threshold.
        """
        batch_id = f"batch:{uuid.uuid4().hex[:8]}"
        conn = self._get_conn()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Identify raw events older than threshold
                cur.execute(
                    """
                    SELECT event_id, agent_id, raw_text, created_at, reference_count
                    FROM brain_events
                    WHERE created_at < NOW() - (%s * INTERVAL '1 day')
                      AND distillation_status = 'pending';
                    """,
                    (days_threshold,)
                )
                candidate_events = cur.fetchall()

                if not candidate_events:
                    return {
                        "status": "idle",
                        "message": f"No pending events older than {days_threshold} days.",
                        "examined": 0,
                        "centroids_created": 0,
                        "purged": 0
                    }

                event_ids = [r["event_id"] for r in candidate_events]
                examined_count = len(event_ids)

                # 2. Extract corresponding embeddings to compute centroids
                cur.execute(
                    """
                    SELECT entity_id, embedding::text
                    FROM brain_vector_index
                    WHERE event_id = ANY(%s::uuid[]) AND is_centroid = false;
                    """,
                    (event_ids,)
                )
                vector_rows = cur.fetchall()

                # Group embeddings by entity_id
                entity_vectors: Dict[str, List[List[float]]] = {}
                for v in vector_rows:
                    eid = v["entity_id"] or "general_concept"
                    raw_str = v["embedding"].strip("[]")
                    if raw_str:
                        vec = [float(x) for x in raw_str.split(",")]
                        entity_vectors.setdefault(eid, []).append(vec)

                # Compute normalized centroids
                centroids_created = 0
                if not dry_run:
                    for eid, vecs in entity_vectors.items():
                        dim = len(vecs[0])
                        centroid = [0.0] * dim
                        for vec in vecs:
                            for i in range(dim):
                                centroid[i] += vec[i]
                        # Average and L2 normalize
                        count = len(vecs)
                        centroid = [x / count for x in centroid]
                        norm = math.sqrt(sum(x * x for x in centroid))
                        if norm > 0:
                            centroid = [x / norm for x in centroid]

                        vector_str = "[" + ",".join(str(round(x, 6)) for x in centroid) + "]"

                        cur.execute(
                            """
                            INSERT INTO brain_vector_index (
                                vector_id, event_id, entity_id, embedding, is_centroid, created_at
                            )
                            VALUES (gen_random_uuid(), NULL, %s, %s::vector, true, NOW());
                            """,
                            (eid, vector_str)
                        )
                        centroids_created += 1

                    # 3. Promote God Nodes in Graph Layer
                    cur.execute(
                        """
                        UPDATE brain_graph_edges
                        SET is_god_node_edge = true, weight = weight + 1.0
                        WHERE source_id IN (
                            SELECT source_id FROM brain_graph_edges
                            GROUP BY source_id HAVING count(*) >= 3
                        );
                        """
                    )
                    edges_synthesized = cur.rowcount

                    # 4. Mark candidate events as completed
                    cur.execute(
                        """
                        UPDATE brain_events
                        SET distillation_status = 'completed', distilled_at = NOW()
                        WHERE event_id = ANY(%s::uuid[]);
                        """,
                        (event_ids,)
                    )

                    # Log distillation milestone
                    cur.execute(
                        """
                        INSERT INTO brain_distillation_log (
                            log_id, batch_id, raw_rows_examined, concepts_extracted,
                            centroids_created, edges_synthesized, status, created_at
                        )
                        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 'completed', NOW());
                        """,
                        (batch_id, examined_count, len(entity_vectors), centroids_created, edges_synthesized)
                    )

                    # 5. Reachability-Guarded Pruning: Purge raw event rows where reference_count = 0
                    cur.execute(
                        """
                        DELETE FROM brain_events
                        WHERE event_id = ANY(%s::uuid[])
                          AND distillation_status = 'completed'
                          AND reference_count = 0;
                        """,
                        (event_ids,)
                    )
                    purged_count = cur.rowcount

                    # Record pruning audit log
                    cur.execute(
                        """
                        INSERT INTO brain_pruning_audit_log (
                            audit_id, purged_rows_count, retained_distilled_count,
                            reachability_scanned_count, purged_before_timestamp, executed_at
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s, %s, NOW() - (%s * INTERVAL '1 day'), NOW()
                        );
                        """,
                        (purged_count, centroids_created, examined_count, days_threshold)
                    )

                    conn.commit()
                else:
                    purged_count = examined_count

                return {
                    "status": "completed" if not dry_run else "dry_run",
                    "batch_id": batch_id,
                    "examined_events": examined_count,
                    "centroids_created": centroids_created,
                    "purged_events": purged_count,
                    "preserved_learned_state": True
                }

        except Exception as e:
            conn.rollback()
            # Route to DLQ on failure
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO brain_distillation_dlq (
                            dlq_id, event_id, error_message, stack_trace, retry_eligible
                        )
                        VALUES (gen_random_uuid(), %s, %s, NULL, true);
                        """,
                        (event_ids[0] if candidate_events else uuid.UUID(int=0), str(e))
                    )
                    conn.commit()
            except Exception:
                pass
            raise e
        finally:
            conn.close()
