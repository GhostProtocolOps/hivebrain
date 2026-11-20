"""
Process Guardian & Lifecycle Watchdog for AI-COS.
Guarantees zero zombie processes:
- Automatically starts master services (Telemetry server on 5175, Viewer on 5174, Daemon) when MCP starts.
- Continuously polls parent PID (Antigravity). When Antigravity terminates, crashes, or closes stdin,
  it immediately reaps and terminates all child processes cleanly.
"""

import os
import sys
import time
import socket
import signal
import logging
import subprocess
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger("process_guardian")

REPO_ROOT = "/Users/nishant/Documents/gravity_work"
HIVEBRAIN_ROOT = os.path.join(REPO_ROOT, "HIVEBrain")
VIEWER_ROOT = os.path.join(REPO_ROOT, "sim-live-process-viewer")

class ProcessGuardian:
    def __init__(self, parent_pid: Optional[int] = None):
        self.parent_pid = parent_pid or os.getppid()
        self.managed_procs: Dict[str, subprocess.Popen] = {}
        self.running = False
        self.watchdog_thread: Optional[threading.Thread] = None

        # Register shutdown signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"🛑 Received signal {signum}. Initiating full AI-COS teardown...")
        self.shutdown_all()
        sys.exit(0)

    @staticmethod
    def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
        """Checks if a TCP port is currently accepting connections."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            return False

    def ensure_services_running(self):
        """Checks required services and spawns any missing ones."""
        # 1. Telemetry Server (port 5175)
        if not self.is_port_open(5175):
            logger.info("Starting Telemetry Server on port 5175...")
            telemetry_script = os.path.join(VIEWER_ROOT, "server", "telemetry_server.py")
            p = subprocess.Popen(
                [sys.executable, telemetry_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            self.managed_procs["telemetry_server"] = p
            # Wait briefly for startup
            for _ in range(10):
                if self.is_port_open(5175):
                    break
                time.sleep(0.2)

        # 2. Sim Live Process Viewer (port 5174)
        if not self.is_port_open(5174):
            logger.info("Starting Sim Live Process Viewer on port 5174...")
            npm_cmd = "npm run dev"
            p = subprocess.Popen(
                npm_cmd,
                shell=True,
                cwd=VIEWER_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            self.managed_procs["viewer_ui"] = p

        # 3. HIVEBrain Daemon (Outbox + Janitor)
        daemon_script = os.path.join(HIVEBRAIN_ROOT, "src", "daemon.py")
        # Check if daemon is already running via pgrep
        res = subprocess.run(["pgrep", "-f", "HIVEBrain/src/daemon.py"], capture_output=True, text=True)
        if not res.stdout.strip():
            logger.info("Starting HIVEBrain Continuous Background Daemon...")
            p = subprocess.Popen(
                [sys.executable, daemon_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            self.managed_procs["hivebrain_daemon"] = p

    def start_parent_watchdog(self):
        """Starts background watchdog checking if parent process (Antigravity) is alive."""
        self.running = True
        self.watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="Guardian-Watchdog"
        )
        self.watchdog_thread.start()
        logger.info(f"🛡️ Process Guardian active. Watching Parent PID: {self.parent_pid}")

    def _watchdog_loop(self):
        while self.running:
            time.sleep(1.5)
            current_ppid = os.getppid()

            # If parent PID changed (on POSIX, orphaned child gets reparented to 1 / launchd)
            if current_ppid != self.parent_pid or current_ppid == 1:
                logger.warning(
                    f"⚠️ Antigravity parent process (PID {self.parent_pid}) exited (new PPID={current_ppid}). "
                    f"Killing all managed services to prevent zombie processes."
                )
                self.shutdown_all()
                os._exit(0)

            # Check if parent process is still alive via kill 0
            try:
                os.kill(self.parent_pid, 0)
            except OSError:
                logger.warning(f"⚠️ Parent PID {self.parent_pid} no longer reachable. Terminating services.")
                self.shutdown_all()
                os._exit(0)

    def shutdown_all(self):
        """Cleanly terminates all managed child processes."""
        self.running = False
        logger.info(f"Reaping {len(self.managed_procs)} managed subprocesses...")
        for name, proc in list(self.managed_procs.items()):
            try:
                logger.info(f"Terminating {name} (PID: {proc.pid})...")
                # Send SIGTERM to process group
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.managed_procs.clear()
        logger.info("✔ All managed services cleanly shut down.")
