"""
HIVEBrain MCP Server: Standard JSON-RPC 2.0 stdio MCP Server.
Exposes tools:
- brain_query: Lock-free MVCC snapshot read across all 4 layers (Relational, JSONB, pgvector, Graphify).
- brain_ingest: Dual-decomposes prompt & response into 4 layers via Transactional Outbox pattern.
- brain_reserve: Front-loaded atomic reservation (Airline Ticket Booking Paradigm) with deadlock-free total ordering.
- brain_distill: 5-day continuous learning semantic centroid synthesis & reachability-guarded pruning.
- brain_status: Overview of all 4 database layers, storage counts, and telemetry.
"""

import sys
import os
import json
import time
import uuid
from typing import Dict, Any, List, Optional

# Ensure src modules are importable
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
        """
        Dual Ingestion Loop:
        1. Decompose prompt & response into intent, entities, constraints, metrics, AST, and 384-dim embeddings.
        2. Total-order reservation for involved entities (Airline Ticket Booking paradigm).
        3. Transactional Outbox ACID commit (L1 + L2 + Outbox).
        4. Immediate fan-out to L3 (pgvector) and L4 (Graphify).
        5. Emit execution graph events to Sim Live Process Viewer (port 5174).
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.telemetry.register_run(run_id, root_workflow="HIVEBrain-Dual-Ingest", trigger_type=f"agent:{agent_id}")
        self.telemetry.record_stage(run_id, "Prompt Ingress", "node_prompt_ingress", status="completed", duration_ms=5)

        # 1. Decompose Prompt
        prompt_decomp = self.decomposer.decompose(prompt, role="prompt")
        self.telemetry.record_stage(run_id, "Prompt Decomposition", "node_semantic_decomposer", status="completed", duration_ms=10)

        # 2. Decompose Response
        response_decomp = self.decomposer.decompose(response, role="response")

        # Combine entities for reservation
        target_entities = list(set(prompt_decomp["entities"] + response_decomp["entities"]))
        res = self.concurrency.reserve_entities(target_entities, agent_id=agent_id, ttl_ms=5000)
        self.telemetry.record_stage(run_id, "Total-Order Reservation", "node_concurrency_res", status="completed", duration_ms=8)

        commit_token = res.get("commit_token", str(uuid.uuid4()))

        # 3. Commit Prompt Event (L1 + L2 + Outbox)
        p_res = self.storage.ingest_transaction(
            agent_id=agent_id,
            event_type="prompt",
            raw_text=prompt,
            decomposition=prompt_decomp,
            commit_token=commit_token
        )

        # 4. Commit Response Event (L1 + L2 + Outbox)
        r_res = self.storage.ingest_transaction(
            agent_id=agent_id,
            event_type="response",
            raw_text=response,
            decomposition=response_decomp,
            commit_token=commit_token
        )
        self.telemetry.record_stage(run_id, "ACID Commit (L1+L2)", "node_acid_commit", status="completed", duration_ms=15)

        # 5. Process Outbox Fan-out to L3 & L4
        outbox_res = self.outbox.process_batch(batch_size=20)
        self.telemetry.record_stage(run_id, "L3 pgvector Fan-out", "node_vector_fanout", status="completed", duration_ms=12)
        self.telemetry.record_stage(run_id, "L4 Graphify Fan-out", "node_graph_fanout", status="completed", duration_ms=10)

        # Release reservation
        self.concurrency.release_reservations(commit_token, agent_id=agent_id)
        self.telemetry.complete_run(run_id, status="completed", total_duration_ms=60)

        return {
            "status": "ingested",
            "run_id": run_id,
            "prompt_event_id": p_res["event_id"],
            "response_event_id": r_res["event_id"],
            "snapshot_id": r_res["snapshot_id"],
            "prompt_intent": prompt_decomp["intent"],
            "response_intent": response_decomp["intent"],
            "entities_indexed": target_entities,
            "fanout_stats": outbox_res,
            "latency_ms": round(p_res["latency_ms"] + r_res["latency_ms"], 2)
        }

    def reserve(self, entity_ids: List[str], agent_id: str, ttl_ms: int = 5000) -> Dict[str, Any]:
        """Front-loaded atomic reservation with total-order sorting."""
        return self.concurrency.reserve_entities(entity_ids=entity_ids, agent_id=agent_id, ttl_ms=ttl_ms)

    def distill(self, days_threshold: int = 5, dry_run: bool = False) -> Dict[str, Any]:
        """5-day continuous learning centroid synthesis & reachability-guarded pruning."""
        run_id = f"distill_{uuid.uuid4().hex[:12]}"
        self.telemetry.register_run(run_id, root_workflow="HIVEBrain-5Day-Distillation", trigger_type="scheduler")
        self.telemetry.record_stage(run_id, "Distillation Start", "node_distillation_janitor", status="running", duration_ms=5)

        result = self.distillation.run_distillation(days_threshold=days_threshold, dry_run=dry_run)

        self.telemetry.record_stage(run_id, "Distillation & Pruning", "node_distillation_janitor", status="completed", duration_ms=25)
        self.telemetry.complete_run(run_id, status="completed", total_duration_ms=30)
        return result

    def status(self) -> Dict[str, Any]:
        """Overview of the 4 database layers and telemetry counts."""
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

                return {
                    "architecture": "HIVEBrain 4-Layer Federated Meta-Brain (RFC-014)",
                    "layers": {
                        "L1_Relational": {"events": events_count, "entities": entities_count},
                        "L2_JSONB": {"semantic_states": json_count},
                        "L3_pgvector": {"total_embeddings": vec_total, "permanent_centroids": centroids},
                        "L4_Graphify": {"total_edges": edges_total, "god_nodes": god_nodes}
                    },
                    "concurrency": {
                        "active_reservations": active_res,
                        "pending_outbox": pending_outbox
                    },
                    "telemetry": "Streaming live to Sim Live Process Viewer (port 5174)"
                }
        finally:
            conn.close()

    def bridge(self, action: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Unified multi-model bridge interface for HIVEBrain:
        - action='sync': Ingests interaction, runs outbox fan-out, returns updated snapshot & latency.
        - action='search': Multi-layer hybrid semantic search.
        - action='reserve': Front-loaded atomic soft lease.
        - action='status': Current 4-layer state overview.
        - action='distill': 5-day continuous learning pass.
        """
        data = data or {}
        if action == "sync":
            prompt = data.get("prompt", "")
            response = data.get("response", "")
            agent_id = data.get("agent_id", "multi-model-bridge")
            entities = data.get("entities", [])
            if entities:
                self.reserve(entities, agent_id=agent_id, ttl_ms=data.get("ttl_ms", 5000))
            ingest_res = self.ingest(prompt, response, agent_id=agent_id, metadata=data.get("metadata"))
            return {"status": "synced", "ingest": ingest_res, "bridge": "active"}
        elif action == "search":
            return self.query(query_text=data.get("query", ""), mode=data.get("mode", "hybrid"), limit=data.get("limit", 10))
        elif action == "reserve":
            return self.reserve(entity_ids=data.get("entities", []), agent_id=data.get("agent_id", "bridge"), ttl_ms=data.get("ttl_ms", 5000))
        elif action == "status":
            return self.status()
        elif action == "distill":
            return self.distill(days_threshold=data.get("days_threshold", 5), dry_run=data.get("dry_run", False))
        else:
            raise ValueError(f"Unknown bridge action: {action}")

# MCP Protocol Implementation
def handle_mcp_request(engine: HIVEBrainEngine, req: Dict[str, Any]) -> Dict[str, Any]:
    method = req.get("method")
    msg_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hivebrain-mcp", "version": "2.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "brain_query",
                        "description": "Lock-free MVCC snapshot read across all 4 layers (Relational, JSONB, pgvector 384-dim, and Graphify edges).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search text or semantic inquiry."},
                                "mode": {"type": "string", "enum": ["hybrid", "relational", "vector", "graph"], "description": "Query execution strategy."},
                                "snapshot_id": {"type": "integer", "description": "Optional pinned snapshot ID for repeatable reads."},
                                "limit": {"type": "integer", "description": "Max results to return (default: 10)."}
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "brain_ingest",
                        "description": "Dual-decompose prompt and response into intent, entities, constraints, and metrics, indexing across all 4 layers with total-ordered reservation locking.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "User prompt or agent command."},
                                "response": {"type": "string", "description": "Generated model response or execution result."},
                                "agent_id": {"type": "string", "description": "Identifier of the calling agent (e.g. 'herdr:1', 'opendots:cto', 'paperclip:dev')."},
                                "metadata": {"type": "object", "description": "Optional arbitrary metadata dict."}
                            },
                            "required": ["prompt", "response", "agent_id"]
                        }
                    },
                    {
                        "name": "brain_reserve",
                        "description": "Front-loaded atomic soft reservation for entity IDs using the airline ticket booking pattern (deadlock-free total ordering).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "entity_ids": {"type": "array", "items": {"type": "string"}, "description": "Entity keys to reserve."},
                                "agent_id": {"type": "string", "description": "Agent acquiring the reservation."},
                                "ttl_ms": {"type": "integer", "description": "Time-to-live in milliseconds (default: 5000)."}
                            },
                            "required": ["entity_ids", "agent_id"]
                        }
                    },
                    {
                        "name": "brain_distill",
                        "description": "Executes 5-day continuous learning pass: generates permanent vector centroids and god nodes, then executes reachability-guarded pruning of raw rows.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "days_threshold": {"type": "integer", "description": "Retention age in days for raw rows (default: 5)."},
                                "dry_run": {"type": "boolean", "description": "If true, simulates distillation and pruning without mutating data."}
                            }
                        }
                    },
                    {
                        "name": "brain_status",
                        "description": "Returns status and record counts across all 4 layers of the HIVEBrain Meta-Brain.",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "brain_bridge",
                        "description": "Unified multi-model bridge interface for HIVEBrain. Enables any model (DeepSeek, Qwen, GPT, Codex) or agent (Herdr, Paperclip, OpenDots, OpenClaw) to sync, search, reserve, or inspect brain state in one unified call.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["sync", "search", "reserve", "status", "distill"],
                                    "description": "Bridge operation to execute."
                                },
                                "data": {
                                    "type": "object",
                                    "description": "Payload dict for the operation (e.g. {prompt, response, agent_id, entities} for sync, {query, mode} for search)."
                                }
                            },
                            "required": ["action"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "brain_query":
                out = engine.query(
                    query_text=args["query"],
                    mode=args.get("mode", "hybrid"),
                    snapshot_id=args.get("snapshot_id"),
                    limit=args.get("limit", 10)
                )
            elif tool_name == "brain_ingest":
                out = engine.ingest(
                    prompt=args["prompt"],
                    response=args["response"],
                    agent_id=args["agent_id"],
                    metadata=args.get("metadata")
                )
            elif tool_name == "brain_reserve":
                out = engine.reserve(
                    entity_ids=args["entity_ids"],
                    agent_id=args["agent_id"],
                    ttl_ms=args.get("ttl_ms", 5000)
                )
            elif tool_name == "brain_distill":
                out = engine.distill(
                    days_threshold=args.get("days_threshold", 5),
                    dry_run=args.get("dry_run", False)
                )
            elif tool_name == "brain_status":
                out = engine.status()
            elif tool_name == "brain_bridge":
                out = engine.bridge(
                    action=args["action"],
                    data=args.get("data")
                )
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": json.dumps(out, indent=2)}], "isError": False}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}], "isError": True}
            }

    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32600, "message": f"Unhandled method: {method}"}}

def main():
    engine = HIVEBrainEngine()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_mcp_request(engine, req)
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as err:
            err_res = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {str(err)}"}}
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
