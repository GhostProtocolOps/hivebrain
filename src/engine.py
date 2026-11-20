"""
HIVEBrain Core Engine.
Combines 4-layer federated storage, concurrency manager, decomposer, outbox, and distillation.
Decoupled from MCP and AI CEO to prevent circular dependencies.
"""

import os
import sys
import uuid
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concurrency import ConcurrencyManager
from decomposer import SemanticDecomposer
from storage import FederatedStorage
from outbox_worker import OutboxWorker
from distillation import DistillationEngine
from telemetry import BrainTelemetry

class HIVEBrainEngine:
    def __init__(self):
        self.concurrency = ConcurrencyManager()
        self.decomposer = SemanticDecomposer(embedding_dim=384)
        self.storage = FederatedStorage()
        self.outbox = OutboxWorker()
        self.distillation = DistillationEngine()
        self.telemetry = BrainTelemetry()

    def query(self, query_text: str, mode: str = "hybrid", snapshot_id: Optional[int] = None, limit: int = 10) -> Dict[str, Any]:
        """Lock-free MVCC snapshot read across all 4 layers."""
        query_embedding = self.decomposer.generate_embedding(query_text)
        return self.storage.query_brain(
            query_text=query_text,
            query_embedding=query_embedding,
            mode=mode,
            snapshot_id=snapshot_id,
            limit=limit
        )

    def ingest(self, prompt: str, response: str, agent_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dual Ingestion Loop across L1, L2, L3, and L4."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.telemetry.register_run(run_id, root_workflow="HIVEBrain-Dual-Ingest", trigger_type=f"agent:{agent_id}")

        prompt_decomp = self.decomposer.decompose(prompt, role="prompt")
        response_decomp = self.decomposer.decompose(response, role="response")

        target_entities = list(set(prompt_decomp["entities"] + response_decomp["entities"]))
        res = self.concurrency.reserve_entities(target_entities, agent_id=agent_id, ttl_ms=5000)
        commit_token = res.get("commit_token", str(uuid.uuid4()))

        p_res = self.storage.ingest_transaction(
            agent_id=agent_id,
            event_type="prompt",
            raw_text=prompt,
            decomposition=prompt_decomp,
            commit_token=commit_token
        )
        r_res = self.storage.ingest_transaction(
            agent_id=agent_id,
            event_type="response",
            raw_text=response,
            decomposition=response_decomp,
            commit_token=commit_token
        )

        outbox_res = self.outbox.process_batch(batch_size=20)
        self.concurrency.release_reservations(commit_token, agent_id=agent_id)

        return {
            "status": "ingested",
            "prompt_event_id": p_res.get("event_id"),
            "response_event_id": r_res.get("event_id"),
            "prompt_intent": prompt_decomp["intent"],
            "entities_indexed": target_entities,
            "outbox_processed": outbox_res.get("processed", 0)
        }

    def reserve(self, entity_ids: List[str], agent_id: str, ttl_ms: int = 5000) -> Dict[str, Any]:
        return self.concurrency.reserve_entities(entity_ids=entity_ids, agent_id=agent_id, ttl_ms=ttl_ms)

    def distill(self, days_threshold: int = 5, dry_run: bool = False) -> Dict[str, Any]:
        return self.distillation.distill(days_threshold=days_threshold, dry_run=dry_run)

    def status(self) -> Dict[str, Any]:
        """Overview of the 4 database layers, reservations, and telemetry."""
        conn = self.storage._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM brain_events;")
                events_count = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM brain_entities;")
                entities_count = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM brain_json_state;")
                json_count = cur.fetchone()[0]
                cur.execute("SELECT count(*), count(*) FILTER (WHERE is_centroid = true) FROM brain_vector_index;")
                vec_total, centroids = cur.fetchone()
                cur.execute("SELECT count(*), count(*) FILTER (WHERE is_god_node_edge = true) FROM brain_graph_edges;")
                edges_total, god_nodes = cur.fetchone()
                cur.execute("SELECT count(*) FROM brain_reservations WHERE active = true;")
                active_res = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM brain_outbox WHERE status = 'pending';")
                pending_outbox = cur.fetchone()[0]

            concurrency_status = {"active_leases": active_res}
            return {
                "status": "online",
                "architecture": "AI-COS HIVEBrain Meta-Brain (PostgreSQL 18 + SIM.AI + Herdr)",
                "layers": {
                    "L1_Relational": {"events": events_count, "entities": entities_count, "status": "active"},
                    "L2_JSONB": {"semantic_states": json_count, "status": "active"},
                    "L3_pgvector": {"total_embeddings": vec_total, "permanent_centroids": centroids, "status": "active"},
                    "L4_Graphify": {"adjacency_edges": edges_total, "god_nodes": god_nodes, "status": "active"}
                },
                "reservations": concurrency_status,
                "pending_outbox": pending_outbox,
                "dashboard_url": "http://localhost:5174/",
                "telemetry_stream": "http://127.0.0.1:5175/api/stream"
            }
        finally:
            conn.close()

    def bridge(self, action: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = data or {}
        if action == "sync":
            return self.ingest(
                prompt=data.get("prompt", ""),
                response=data.get("response", ""),
                agent_id=data.get("agent_id", "bridge_user"),
                metadata=data.get("metadata")
            )
        elif action == "search":
            return self.query(
                query_text=data.get("query", ""),
                mode=data.get("mode", "hybrid"),
                limit=data.get("limit", 10)
            )
        elif action == "reserve":
            return self.reserve(
                entity_ids=data.get("entities", []),
                agent_id=data.get("agent_id", "bridge_agent"),
                ttl_ms=data.get("ttl_ms", 5000)
            )
        elif action == "distill":
            return self.distill(days_threshold=data.get("days", 5))
        elif action == "status":
            return self.status()
        return {"error": f"Unknown bridge action: {action}"}
