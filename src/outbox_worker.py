"""
HIVEBrain Transactional Outbox Worker:
Asynchronously fans out committed events to:
- Layer 3: pgvector embeddings (gravity_brain & gravity_vector)
- Layer 4: Graphify adjacency edges (brain_graph_edges)
- Sim Live Process Viewer Telemetry
Ensures sub-10ms write responsiveness by decoupling heavy indexing from the write path.
"""

import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import Dict, Any

DB_CONFIG = {
    "host": "/tmp",
    "dbname": "gravity_brain",
    "user": "nishant"
}

class OutboxWorker:
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or DB_CONFIG

    def _get_conn(self, dbname: str = None):
        cfg = dict(self.db_config)
        if dbname:
            cfg["dbname"] = dbname
        return psycopg2.connect(**cfg)

    def process_batch(self, batch_size: int = 50) -> Dict[str, int]:
        """
        Polls pending outbox records using FOR UPDATE SKIP LOCKED to allow concurrent workers.
        """
        conn = self._get_conn()
        processed_count = 0
        failed_count = 0

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT outbox_id, event_id, target_layer, payload, retry_count
                    FROM brain_outbox
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED;
                    """,
                    (batch_size,)
                )
                tasks = cur.fetchall()

                for task in tasks:
                    outbox_id = task["outbox_id"]
                    layer = task["target_layer"]
                    payload = task["payload"]

                    try:
                        if layer == "L3_VECTOR":
                            self._fanout_vector(payload)
                        elif layer == "L4_GRAPH":
                            self._fanout_graph(payload)
                        elif layer == "SIM_TELEMETRY":
                            self._fanout_telemetry(payload)

                        cur.execute(
                            """
                            UPDATE brain_outbox
                            SET status = 'processed', processed_at = NOW()
                            WHERE outbox_id = %s;
                            """,
                            (outbox_id,)
                        )
                        processed_count += 1
                    except Exception as err:
                        failed_count += 1
                        cur.execute(
                            """
                            UPDATE brain_outbox
                            SET retry_count = retry_count + 1,
                                last_error = %s,
                                status = CASE WHEN retry_count >= 5 THEN 'failed' ELSE 'pending' END
                            WHERE outbox_id = %s;
                            """,
                            (str(err), outbox_id)
                        )

                conn.commit()
        finally:
            conn.close()

        return {"processed": processed_count, "failed": failed_count}

    def _fanout_vector(self, payload: Dict[str, Any]):
        """Writes 384-dimensional dense embedding to pgvector."""
        event_id = payload["event_id"]
        entity_id = payload["entity_id"]
        embedding = payload["embedding"]
        cluster_id = payload.get("semantic_cluster_id", 0)

        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Write to primary gravity_brain
        conn = self._get_conn("gravity_brain")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO brain_vector_index (vector_id, event_id, entity_id, embedding, semantic_cluster_id, is_centroid)
                    VALUES (gen_random_uuid(), %s, %s, %s::vector, %s, false);
                    """,
                    (event_id, entity_id, vector_str, cluster_id)
                )
                conn.commit()
        finally:
            conn.close()

        # Mirror to gravity_vector if available
        try:
            conn_vec = self._get_conn("gravity_vector")
            with conn_vec.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO brain_vector_index (vector_id, event_id, entity_id, embedding, semantic_cluster_id, is_centroid)
                    VALUES (gen_random_uuid(), %s, %s, %s::vector, %s, false);
                    """,
                    (event_id, entity_id, vector_str, cluster_id)
                )
                conn_vec.commit()
            conn_vec.close()
        except Exception:
            pass

    def _fanout_graph(self, payload: Dict[str, Any]):
        """Writes relational knowledge edges between primary_entity and related_entities."""
        primary = payload["primary_entity"]
        related = payload.get("related_entities", [])
        intent = payload.get("intent", "relates")

        conn = self._get_conn("gravity_brain")
        try:
            with conn.cursor() as cur:
                for target in related:
                    if target != primary:
                        cur.execute(
                            """
                            INSERT INTO brain_graph_edges (edge_id, source_id, target_id, relationship_type, weight, properties)
                            VALUES (gen_random_uuid(), %s, %s, %s, 1.0, %s);
                            """,
                            (primary, target, "RELATES_TO", Json({"intent": intent}))
                        )
                conn.commit()
        finally:
            conn.close()

    def _fanout_telemetry(self, payload: Dict[str, Any]):
        """Pushes stage milestones to sim_stage_milestones in gravity_sql."""
        try:
            conn_sql = self._get_conn("gravity_sql")
            with conn_sql.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sim_stage_milestones (
                        run_id, stage_id, stage_name, status, duration_ms, error_trace, timestamp
                    )
                    VALUES (%s, %s, %s, 'completed', 15.0, NULL, NOW());
                    """,
                    (
                        payload.get("event_id", "00000000-0000-0000-0000-000000000000"),
                        f"stage:{payload.get('type', 'event')}",
                        f"HIVEBrain Ingest [{payload.get('intent', 'general')}]"
                    )
                )
                conn_sql.commit()
            conn_sql.close()
        except Exception:
            pass
