"""
Dynamic Lane Self-Healing & Model Swapper for AI-COS.
Intercepts rate limits, token exhaustion, or agent errors; automatically promotes
the pre-planned backup model, adjusts effort, and resumes execution from latest HIVEBrain checkpoint.
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("lane_healer")

class DynamicLaneHealer:
    def __init__(self, fallback_catalog: Optional[Dict[str, Any]] = None):
        self.fallback_catalog = fallback_catalog or {
            "rate_limit_429": {
                "free/qwen-3.8-max": {"swap_to": "deepseek-chat", "effort": "medium"},
                "free/gpt-6-luna": {"swap_to": "deepseek-chat", "effort": "medium"},
                "deepseek-chat": {"swap_to": "o3-mini", "effort": "high"}
            },
            "context_exhaustion": {
                "free/qwen-3.8-max": {"swap_to": "deepseek-reasoner", "effort": "high"},
                "free/gpt-6-luna": {"swap_to": "o3-mini", "effort": "high"},
                "deepseek-reasoner": {"swap_to": "codex-cli", "effort": "high"}
            },
            "task_timeout": {
                "default": {"swap_to": "codex-cli", "effort": "high"}
            }
        }
        self.healing_log: list = []

    def heal_task(self, task: Dict[str, Any], failure_reason: str, current_model: str) -> Dict[str, Any]:
        """
        Calculates the repaired task configuration with promoted backup model and adjusted effort.
        """
        category = "rate_limit_429" if "429" in failure_reason or "rate" in failure_reason.lower() else \
                   "context_exhaustion" if "context" in failure_reason.lower() or "token" in failure_reason.lower() else \
                   "task_timeout"

        mapping = self.fallback_catalog.get(category, {})
        remediation = mapping.get(current_model, mapping.get("default", {"swap_to": "deepseek-reasoner", "effort": "high"}))

        new_model = remediation["swap_to"]
        new_effort = remediation["effort"]

        healing_event = {
            "taskId": task.get("id"),
            "failureReason": failure_reason,
            "previousModel": current_model,
            "promotedModel": new_model,
            "adjustedEffort": new_effort,
            "timestamp": time.time(),
            "status": "repaired"
        }
        self.healing_log.append(healing_event)

        logger.warning(
            f"🩹 [Self-Healing] Intercepted '{failure_reason}' on {current_model}. "
            f"Promoting backup model -> {new_model} (Effort: {new_effort}). Resuming from checkpoint."
        )

        repaired_task = dict(task)
        repaired_task["active_model"] = new_model
        repaired_task["effort"] = new_effort
        repaired_task["retry_count"] = repaired_task.get("retry_count", 0) + 1
        repaired_task["healed"] = True

        return repaired_task
