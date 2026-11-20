"""
HIVEBrain Telemetry & Sim Live Process Viewer Bridge:
Streams execution milestones, stages, and topological snapshots into:
- gravity_sql.sim_process_runs
- gravity_sql.sim_stage_milestones
- gravity_jsonb.sim_graph_snapshots
Allowing real-time monitoring of HIVEBrain DAG operations on Sim Live Process Viewer (port 5174).
"""

import time
import uuid
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import Json

DB_HOST = "/tmp"

class BrainTelemetry:
    def __init__(self, host: str = DB_HOST):
        self.host = host

    def _get_conn(self, dbname: str):
        return psycopg2.connect(host=self.host, dbname=dbname, user="nishant")

    def register_run(
        self,
        run_id: str,
        root_workflow: str = "HIVEBrain-Meta-Brain",
        trigger_type: str = "agent_ingest"
    ) -> str:
        """Initializes a run in sim_process_runs."""
        conn = self._get_conn("gravity_sql")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sim_process_runs (
                        process_run_id, parent_run_id, root_workflow_id,
                        trigger_type, status, started_at, reconciled
                    )
                    VALUES (%s, NULL, %s, %s, 'running', NOW(), false)
                    ON CONFLICT (process_run_id) DO NOTHING;
                    """,
                    (run_id, root_workflow, trigger_type)
                )
                conn.commit()
        finally:
            conn.close()

        # Save topology snapshot in sim_graph_snapshots
        self._record_graph_snapshot(run_id, root_workflow)
        return run_id

    def record_stage(
        self,
        run_id: str,
        stage_name: str,
        block_id: str,
        status: str = "completed",
        duration_ms: int = 15,
        depth: int = 0,
        error_message: Optional[str] = None
    ):
        """Records an individual execution milestone into sim_stage_milestones."""
        node_key = f"{run_id}:{block_id}:{int(time.time() * 1000) % 100000}"
        conn = self._get_conn("gravity_sql")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sim_stage_milestones (
                        process_run_id, node_instance_key, block_id,
                        workflow_id, depth, status, duration_ms,
                        identity_quality, error_message, recorded_at
                    )
                    VALUES (%s, %s, %s, 'HIVEBrain', %s, %s, %s, 'explicit', %s, NOW());
                    """,
                    (run_id, node_key, block_id, depth, status, duration_ms, error_message)
                )
                conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def complete_run(self, run_id: str, status: str = "completed", total_duration_ms: int = 45):
        """Marks run completed and reconciled in sim_process_runs."""
        conn = self._get_conn("gravity_sql")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sim_process_runs
                    SET status = %s, completed_at = NOW(), duration_ms = %s, reconciled = true
                    WHERE process_run_id = %s;
                    """,
                    (status, total_duration_ms, run_id)
                )
                conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def _record_graph_snapshot(self, run_id: str, workflow_id: str):
        """Stores the immutable React Flow DAG topology in sim_graph_snapshots."""
        topology = {
            "nodes": [
                {"id": "node_prompt_ingress", "type": "processNode", "data": {"label": "Prompt Ingress", "stage": "ingress"}},
                {"id": "node_semantic_decomposer", "type": "processNode", "data": {"label": "Dual Decomposition (Intent/AST)", "stage": "decomposition"}},
                {"id": "node_concurrency_res", "type": "processNode", "data": {"label": "Total-Order Reservation", "stage": "reservation"}},
                {"id": "node_acid_commit", "type": "processNode", "data": {"label": "ACID Commit (L1 + L2 + Outbox)", "stage": "commit"}},
                {"id": "node_vector_fanout", "type": "processNode", "data": {"label": "L3 pgvector Fan-out", "stage": "vector_indexing"}},
                {"id": "node_graph_fanout", "type": "processNode", "data": {"label": "L4 Graphify Adjacency Fan-out", "stage": "graph_indexing"}},
                {"id": "node_response_ingress", "type": "processNode", "data": {"label": "Response Ingress & Decomposition", "stage": "response_loop"}},
                {"id": "node_distillation_janitor", "type": "processNode", "data": {"label": "5-Day Continuous Distillation & Prune", "stage": "distillation"}}
            ],
            "edges": [
                {"id": "e1", "source": "node_prompt_ingress", "target": "node_semantic_decomposer"},
                {"id": "e2", "source": "node_semantic_decomposer", "target": "node_concurrency_res"},
                {"id": "e3", "source": "node_concurrency_res", "target": "node_acid_commit"},
                {"id": "e4", "source": "node_acid_commit", "target": "node_vector_fanout"},
                {"id": "e5", "source": "node_acid_commit", "target": "node_graph_fanout"},
                {"id": "e6", "source": "node_acid_commit", "target": "node_response_ingress"},
                {"id": "e7", "source": "node_response_ingress", "target": "node_distillation_janitor"}
            ]
        }

        try:
            conn = self._get_conn("gravity_jsonb")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sim_graph_snapshots (
                        run_id, workflow_id, snapshot_version,
                        graph_topology, sub_workflow_graphs, created_at
                    )
                    VALUES (%s, %s, 'v2.0', %s, '{}'::jsonb, NOW())
                    ON CONFLICT (run_id) DO NOTHING;
                    """,
                    (run_id, workflow_id, Json(topology))
                )
                conn.commit()
            conn.close()
        except Exception:
            pass
