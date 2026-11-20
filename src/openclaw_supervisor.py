"""
OpenClaw Session Supervisor & Loop Breaker for AI-COS.
Audits subagent conversation transcripts, detects circular loops, and prevents runaway token spend.
"""

import os
import sys
import time
import json
import logging
import urllib.request
from typing import Dict, Any, List, Optional

logger = logging.getLogger("openclaw_supervisor")

OPENCLAW_URL = "http://127.0.0.1:18789"

class OpenClawSupervisor:
    def __init__(self, endpoint: str = OPENCLAW_URL, max_loop_repeats: int = 3, max_context_chars: int = 120_000):
        self.endpoint = endpoint
        self.max_loop_repeats = max_loop_repeats
        self.max_context_chars = max_context_chars
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    def audit_session_transcript(self, session_id: str, transcript_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Audits an agent's session transcript.
        Returns whether the session is healthy or has triggered a loop/cost circuit breaker.
        """
        total_chars = sum(len(str(e.get("content", ""))) for e in transcript_entries)
        
        # 1. Check runaway context length
        if total_chars > self.max_context_chars:
            logger.warning(f"🚨 [OpenClaw] Session {session_id} exceeded context limit ({total_chars} > {self.max_context_chars} chars)!")
            return {
                "healthy": False,
                "reason": "context_limit_exceeded",
                "total_chars": total_chars,
                "recommended_action": "swap_backup_model_and_prune"
            }

        # 2. Check circular repetition
        recent_actions = [e.get("action") or str(e.get("content", ""))[:40] for e in transcript_entries[-8:] if e]
        if len(recent_actions) >= 4:
            # Check for identical back-to-back repetitions
            from collections import Counter
            counts = Counter(recent_actions)
            for action, count in counts.items():
                if count >= self.max_loop_repeats:
                    logger.warning(f"🚨 [OpenClaw] Session {session_id} caught in circular loop on action: '{action}' ({count} repeats)!")
                    return {
                        "healthy": False,
                        "reason": "circular_loop_detected",
                        "repeated_action": action,
                        "repeats": count,
                        "recommended_action": "escalate_to_codex_reasoner"
                    }

        return {
            "healthy": True,
            "total_chars": total_chars,
            "entries_audited": len(transcript_entries),
            "status": "nominal"
        }

    def check_openclaw_gateway(self) -> bool:
        """Pings OpenClaw gateway service."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 404, 405)
        except Exception:
            return False
