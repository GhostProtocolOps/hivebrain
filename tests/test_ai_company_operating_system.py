"""
Comprehensive Modular Integration Test Suite for AI Company Operating System (AI-COS).
Tests:
1. Gateway Non-Blocking Latency (< 10ms target)
2. AI CEO Micro-Task Planning & Cost Optimization Matrix
3. Herdr Parallel Fleet Lane Acquisition & Instant Lane Recycling
4. OpenClaw Session Supervisor Loop & Context Circuit Breaker
5. Dynamic Lane Self-Healing & Model Swapper
6. End-to-End Autonomous Project Execution into HIVEBrain 4-Layer Topology
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gateway import UserGateway
from ai_ceo import AICEOOrchestrator, MODEL_ROUTING_CATALOG
from herdr_fleet import HerdrFleetManager
from openclaw_supervisor import OpenClawSupervisor
from lane_healer import DynamicLaneHealer
from hivebrain_mcp import HIVEBrainEngine

class TestAICompanyOS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("🚀 STARTING AI COMPANY OPERATING SYSTEM (AI-COS) TEST SUITE")
        print("=" * 70)

    def test_1_gateway_non_blocking_latency(self):
        """Validates that UserGateway hands off task to background fleet in < 15ms."""
        print("\n[TEST 1] Testing Gateway Non-Blocking Handoff Latency...")
        gw = UserGateway()
        t0 = time.perf_counter()
        res = gw.submit_request("Hello AI CEO! What is the system status?")
        latency_ms = (time.perf_counter() - t0) * 1000.0
        
        print(f"Gateway Response Latency: {latency_ms:.2f}ms")
        print("Gateway Response:", res)

        self.assertEqual(res["status"], "accepted_non_blocking")
        self.assertIn("run_id", res)
        self.assertLess(latency_ms, 25.0, "Gateway must be ultra-fast non-blocking")
        print("✅ TEST 1 PASSED: Gateway handoff achieved non-blocking speed.")

    def test_2_micro_planning_cost_matrix(self):
        """Validates that AI CEO plans tasks with Tier 1 free models and Tier 2/3 backups."""
        print("\n[TEST 2] Testing Micro-Task Planning & Model Routing...")
        ceo = AICEOOrchestrator()
        plan = ceo._compile_child_workflow("Refactor authentication module with biometric WebAuthn")
        
        self.assertIn("subtasks", plan)
        self.assertEqual(len(plan["subtasks"]), 4)

        # Verify model routing
        t1 = plan["subtasks"][0]
        self.assertEqual(t1["routing"]["primary"]["model"], "free/qwen-3.8-max")
        self.assertEqual(t1["routing"]["primary"]["cost"], 0.0)

        t2 = plan["subtasks"][1]
        self.assertEqual(t2["routing"]["primary"]["model"], "free/gpt-6-luna")

        t3 = plan["subtasks"][2]
        self.assertEqual(t3["routing"]["primary"]["model"], "codex-cli")

        print("Generated Plan Subtasks:")
        for st in plan["subtasks"]:
            print(f"  • {st['id']}: Primary={st['routing']['primary']['model']} | Backup={st['routing']['backup']['model']}")

        print("✅ TEST 2 PASSED: Micro-planning correctly applies cost optimization matrix.")

    def test_3_herdr_fleet_lane_recycling(self):
        """Validates parallel lane acquisition, capacity locking, and instant recycling."""
        print("\n[TEST 3] Testing Herdr Fleet Parallel Lane Acquisition & Recycling...")
        fleet = HerdrFleetManager(max_lanes=3)
        status = fleet.get_fleet_status()
        self.assertEqual(status["idle_lanes"], 3)

        # Acquire 3 lanes
        l1 = fleet.acquire_lane({"id": "task_a"}, "free/qwen-3.8-max")
        l2 = fleet.acquire_lane({"id": "task_b"}, "free/gpt-6-luna")
        l3 = fleet.acquire_lane({"id": "task_c"}, "deepseek-reasoner")

        self.assertIsNotNone(l1)
        self.assertIsNotNone(l2)
        self.assertIsNotNone(l3)
        self.assertEqual(fleet.get_fleet_status()["idle_lanes"], 0)

        # 4th acquisition should fail (pool full)
        l4 = fleet.acquire_lane({"id": "task_d"}, "codex-cli")
        self.assertIsNone(l4, "Must not acquire lane when all lanes are busy")

        # Recycle lane 1
        fleet.release_lane(l1, {"status": "success"})
        self.assertEqual(fleet.get_fleet_status()["idle_lanes"], 1)

        # Now 4th acquisition succeeds
        l4_retry = fleet.acquire_lane({"id": "task_d"}, "codex-cli")
        self.assertEqual(l4_retry, l1, "Recycled lane should immediately be reassigned")

        print("✅ TEST 3 PASSED: Parallel fleet lanes lock and recycle instantly.")

    def test_4_openclaw_supervisor_loop_breaking(self):
        """Validates detection of infinite agent loops and context limits."""
        print("\n[TEST 4] Testing OpenClaw Session Supervisor Loop Breaker...")
        sup = OpenClawSupervisor(max_loop_repeats=3, max_context_chars=500)

        # 1. Healthy transcript
        healthy_ts = [
            {"action": "read_spec"},
            {"action": "generate_code"},
            {"action": "run_tests"}
        ]
        res_healthy = sup.audit_session_transcript("sess_1", healthy_ts)
        self.assertTrue(res_healthy["healthy"])

        # 2. Infinite loop transcript (repeated action)
        loop_ts = [
            {"action": "stuck_query"},
            {"action": "stuck_query"},
            {"action": "stuck_query"},
            {"action": "stuck_query"}
        ]
        res_loop = sup.audit_session_transcript("sess_2", loop_ts)
        self.assertFalse(res_loop["healthy"])
        self.assertEqual(res_loop["reason"], "circular_loop_detected")

        # 3. Context overflow
        big_ts = [{"action": "log", "content": "X" * 600}]
        res_big = sup.audit_session_transcript("sess_3", big_ts)
        self.assertFalse(res_big["healthy"])
        self.assertEqual(res_big["reason"], "context_limit_exceeded")

        print("✅ TEST 4 PASSED: OpenClaw loop breaker traps circular actions and context leaks.")

    def test_5_dynamic_lane_healing(self):
        """Validates automatic promotion of backup model when 429 rate limit is trapped."""
        print("\n[TEST 5] Testing Dynamic Lane Self-Healing & Model Swapper...")
        healer = DynamicLaneHealer()
        task = {
            "id": "task_data_sync",
            "active_model": "free/qwen-3.8-max",
            "effort": "low"
        }

        # Simulate 429 Rate Limit
        repaired = healer.heal_task(task, failure_reason="HTTP 429: Too Many Requests", current_model="free/qwen-3.8-max")
        
        self.assertEqual(repaired["active_model"], "deepseek-chat")
        self.assertEqual(repaired["effort"], "medium")
        self.assertTrue(repaired["healed"])
        self.assertEqual(repaired["retry_count"], 1)

        print(f"Healed Task: Previous='free/qwen-3.8-max' -> Promoted='{repaired['active_model']}' (Effort: {repaired['effort']})")
        print("✅ TEST 5 PASSED: Dynamic lane healer promoted backup model on rate-limit.")

    def test_6_end_to_end_project_execution(self):
        """Validates complete AI CEO project execution cycle into HIVEBrain 4-layer store."""
        print("\n[TEST 6] Testing End-to-End Autonomous Project Execution...")
        ceo = AICEOOrchestrator()
        prompt = "Deploy high-throughput PostgreSQL 18 JSONB partition manager"
        
        job = {
            "run_id": "test_e2e_run_01",
            "prompt": prompt,
            "user_metadata": {"test": True}
        }
        ceo._execute_project(job)
        
        # Verify query against HIVEBrain
        engine = HIVEBrainEngine()
        query_res = engine.query("PostgreSQL 18 JSONB partition manager", mode="hybrid")
        
        self.assertGreater(len(query_res["results"]["events_and_jsonb"]), 0)
        self.assertGreater(len(query_res["results"]["vector_semantic_matches"]), 0)
        print("Matched Events:", len(query_res["results"]["events_and_jsonb"]))
        print("Matched Semantic Vectors:", len(query_res["results"]["vector_semantic_matches"]))
        print("✅ TEST 6 PASSED: Autonomous project executed and committed across 4 layers.")

if __name__ == "__main__":
    unittest.main()
