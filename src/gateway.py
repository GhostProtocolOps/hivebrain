"""
Non-Blocking User Gateway for AI-COS.
The ultra-fast (<10ms) entrypoint that enqueues prompts, hands off
execution to the AI CEO (Paperclip leader), and frees the Main Agent to chat continuously.
"""

import os
import sys
import time
import json
import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("gateway")

from ai_ceo import get_ceo

class UserGateway:
    def __init__(self):
        self.ceo = get_ceo()

    def submit_request(self, user_prompt: str, user_id: str = "user_nishant") -> Dict[str, Any]:
        """
        True non-blocking handoff in <5ms:
        1. Generates run_id & metadata.
        2. Dispatches to AI CEO background fleet.
        3. Returns immediate receipt so Main Agent never waits.
        """
        t0 = time.perf_counter()
        run_id = f"aic_{uuid.uuid4().hex[:8]}"

        # Asynchronous handoff directly to AI CEO
        dispatch_ack = self.ceo.dispatch_from_gateway(
            prompt=user_prompt,
            user_metadata={"run_id": run_id, "user_id": user_id}
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(f"⚡ [Gateway Handoff] Completed in {latency_ms:.2f}ms. Main Agent is 100% free.")

        return {
            "status": "accepted_non_blocking",
            "run_id": dispatch_ack.get("run_id", run_id),
            "latency_ms": round(latency_ms, 2),
            "viewer_url": "http://localhost:5174/",
            "message": "Task dispatched to AI CEO. Main Agent is completely free to converse."
        }

    def check_progress(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Instant read-only query that checks current status without waiting or blocking background work.
        """
        fleet_status = self.ceo.fleet.get_fleet_status() if hasattr(self.ceo, "fleet") else {}
        return {
            "run_id": run_id,
            "overall_status": getattr(self.ceo, "current_status", "in_progress"),
            "fleet": fleet_status,
            "dashboard_url": "http://localhost:5174/"
        }
