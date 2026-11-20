"""
HIVEBrain & AI-COS Master MCP Server (JSON-RPC 2.0 stdio).
Acts as the central industry-grade software pipeline:
- Integrates ProcessGuardian: automatically starts Telemetry Server (5175), Viewer (5174), and Daemon.
- Watchdog: continuously monitors Antigravity parent PID; terminates all child processes when Antigravity exits.
- Exposes complete AI Company OS toolset:
  * aicos_dispatch: Ultra-fast non-blocking handoff to AI CEO (<5ms).
  * aicos_progress: Real-time progress and Herdr fleet status.
  * aicos_plan: Micro-task DAG planning with cost-optimized model routing.
  * aicos_heal: Dynamic self-healing and model promotion on rate limits.
  * brain_query, brain_ingest, brain_reserve, brain_distill, brain_status, brain_bridge.
"""

import sys
import os
import json
import time
import uuid
import logging
from typing import Dict, Any, List, Optional

# Ensure src modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from concurrency import ConcurrencyManager
from decomposer import SemanticDecomposer
from storage import FederatedStorage
from outbox_worker import OutboxWorker
from distillation import DistillationEngine
from telemetry import BrainTelemetry
from guardian import ProcessGuardian
from gateway import UserGateway
from ai_ceo import get_ceo, AICEOOrchestrator
from lane_healer import DynamicLaneHealer

logger = logging.getLogger("aicos_mcp")

from engine import HIVEBrainEngine

gateway = UserGateway()
ceo = get_ceo()
healer = DynamicLaneHealer()

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
                "serverInfo": {"name": "aicos-master-mcp", "version": "3.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "aicos_dispatch",
                        "description": "Primary non-blocking gateway. Ingests prompt into HIVEBrain, hands off to the AI CEO in <5ms, and frees the Main Agent to chat freely. Streams execution live to the visual dashboard.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "The user prompt, task, or engineering objective to execute."}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "aicos_progress",
                        "description": "Checks real-time progress of active background tasks, Herdr execution lanes, and Paperclip issues without blocking.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "run_id": {"type": "string", "description": "Optional run ID to inspect."}
                            }
                        }
                    },
                    {
                        "name": "aicos_plan",
                        "description": "Decomposes any objective into a modular Sim.ai child workflow with multi-model cost routing (Free Tier primary, DeepSeek/Codex backup) without executing.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "The goal to plan."}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "aicos_heal",
                        "description": "Forces dynamic self-healing on an interrupted or rate-limited task, swapping in the backup model and resuming from the last checkpoint.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string", "description": "ID of the task to heal."},
                                "reason": {"type": "string", "description": "Failure reason (e.g. 'HTTP 429: Rate Limit', 'context_limit')."},
                                "current_model": {"type": "string", "description": "The model that encountered the blocker."}
                            },
                            "required": ["task_id", "reason", "current_model"]
                        }
                    },
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
                        "description": "Returns status and record counts across all 4 layers of the HIVEBrain Meta-Brain, background daemon, and Herdr fleet.",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "brain_bridge",
                        "description": "Unified multi-model bridge interface for HIVEBrain across Qwen, DeepSeek, Codex, and Herdr.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["sync", "search", "reserve", "status", "distill"],
                                    "description": "Bridge operation to execute."
                                },
                                "data": {"type": "object", "description": "Payload dict for the operation."}
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
            if tool_name == "aicos_dispatch":
                out = gateway.submit_request(args["prompt"])
            elif tool_name == "aicos_progress":
                out = gateway.check_progress(args.get("run_id"))
            elif tool_name == "aicos_plan":
                out = ceo._compile_child_workflow(args["prompt"])
            elif tool_name == "aicos_heal":
                out = healer.heal_task(
                    task={"id": args["task_id"]},
                    failure_reason=args["reason"],
                    current_model=args["current_model"]
                )
            elif tool_name == "brain_query":
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
    guardian = ProcessGuardian()
    guardian.ensure_services_running()
    guardian.start_parent_watchdog()

    engine = HIVEBrainEngine()

    try:
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
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        guardian.shutdown_all()

if __name__ == "__main__":
    main()
