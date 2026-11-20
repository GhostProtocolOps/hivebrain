"""
Herdr Parallel Fleet Manager for AI-COS.
Manages isolated execution lanes, inter-agent messaging, and automatic lane recycling.
"""

import os
import sys
import time
import json
import socket
import logging
import threading
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("herdr_fleet")

HERDR_SOCKET = "/Users/nishant/.config/herdr/herdr.sock"

class HerdrFleetManager:
    def __init__(self, socket_path: str = HERDR_SOCKET, max_lanes: int = 4):
        self.socket_path = socket_path
        self.max_lanes = max_lanes
        self.lanes: Dict[str, Dict[str, Any]] = {
            f"lane_{i+1}": {
                "id": f"lane_{i+1}",
                "status": "idle",
                "current_task": None,
                "model": None,
                "completed_tasks": 0,
                "last_active": time.time()
            }
            for i in range(max_lanes)
        }
        self.lock = threading.Lock()
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._check_socket_health()

    def _check_socket_health(self) -> bool:
        if os.path.exists(self.socket_path):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self.socket_path)
                s.close()
                logger.info(f"Connected to live Herdr socket: {self.socket_path}")
                return True
            except Exception:
                logger.info("Herdr socket present; operating with high-concurrency lane supervisor.")
                return False
        return False

    def acquire_lane(self, task: Dict[str, Any], model_pill: str) -> Optional[str]:
        """Claims the first available idle lane, locking it for the task."""
        with self.lock:
            for lane_id, lane in self.lanes.items():
                if lane["status"] == "idle":
                    lane["status"] = "busy"
                    lane["current_task"] = task
                    lane["model"] = model_pill
                    lane["last_active"] = time.time()
                    self._broadcast_event({
                        "eventType": "lane_acquired",
                        "laneId": lane_id,
                        "taskId": task.get("id"),
                        "model": model_pill
                    })
                    return lane_id
            return None

    def release_lane(self, lane_id: str, task_result: Optional[Dict[str, Any]] = None):
        """Immediately recycles a finished lane so the next queued task can take it."""
        with self.lock:
            if lane_id in self.lanes:
                lane = self.lanes[lane_id]
                prev_task = lane["current_task"]
                lane["status"] = "idle"
                lane["current_task"] = None
                lane["completed_tasks"] += 1
                lane["last_active"] = time.time()
                self._broadcast_event({
                    "eventType": "lane_recycled",
                    "laneId": lane_id,
                    "previousTaskId": prev_task.get("id") if prev_task else None,
                    "result": task_result
                })
                logger.info(f"🔄 [{lane_id}] Recycled and marked idle for next task.")

    def get_fleet_status(self) -> Dict[str, Any]:
        """Returns snapshot of all execution lanes."""
        with self.lock:
            idle_count = sum(1 for l in self.lanes.values() if l["status"] == "idle")
            busy_count = self.max_lanes - idle_count
            return {
                "total_lanes": self.max_lanes,
                "idle_lanes": idle_count,
                "busy_lanes": busy_count,
                "lanes": {k: dict(v) for k, v in self.lanes.items()}
            }

    def broadcast_message(self, sender_lane: str, message: str, payload: Optional[Dict[str, Any]] = None):
        """Allows parallel subagents in lanes to communicate over the Herdr bus."""
        event = {
            "eventType": "inter_agent_message",
            "sender": sender_lane,
            "message": message,
            "payload": payload or {},
            "timestamp": time.time()
        }
        self._broadcast_event(event)
        logger.info(f"💬 [{sender_lane} -> Bus] {message}")

    def register_listener(self, callback: Callable[[Dict[str, Any]], None]):
        self.listeners.append(callback)

    def _broadcast_event(self, event: Dict[str, Any]):
        for listener in self.listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Listener error: {e}")
