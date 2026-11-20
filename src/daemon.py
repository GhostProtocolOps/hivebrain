#!/usr/bin/env python3
"""
HIVEBrain Autonomous Continuous Daemon.
Orchestrates:
1. Transactional Outbox Fan-out: Async ingestion from L1/L2 into L3 (pgvector) and L4 (Graphify).
2. Concurrency Lease Janitor: Automatic reclamation of expired 5s soft reservations.
3. Continuous Distillation Engine: Synthesizing vector centroids & God Nodes with reachability-guarded pruning.
4. Heartbeat Telemetry: Emits real-time daemon metrics to PostgreSQL and Sim Process Viewer.
"""

import sys
import time
import signal
import threading
import logging
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HIVEBrain-Daemon] %(message)s"
)
logger = logging.getLogger("hivebrain_daemon")

from concurrency import ConcurrencyManager
from outbox_worker import OutboxWorker
from distillation import DistillationEngine
from telemetry import BrainTelemetry

class HIVEBrainDaemon:
    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.db_config = db_config or {
            "host": "/tmp",
            "port": 5432,
            "user": "nishant",
            "dbname": "gravity_brain"
        }
        self.concurrency = ConcurrencyManager(self.db_config)
        self.outbox_worker = OutboxWorker(self.db_config)
        self.distillation_engine = DistillationEngine(self.db_config)
        self.telemetry = BrainTelemetry(self.db_config)
        self.running = False
        self.threads = []

    def start(self):
        self.running = True
        logger.info("🚀 Starting HIVEBrain Autonomous Daemon...")

        # 1. Outbox Worker Thread
        t_outbox = threading.Thread(target=self._run_outbox_loop, daemon=True, name="OutboxWorker")
        # 2. Lease Janitor Thread
        t_janitor = threading.Thread(target=self._run_janitor_loop, daemon=True, name="LeaseJanitor")
        # 3. Distillation Scheduler Thread
        t_distill = threading.Thread(target=self._run_distillation_loop, daemon=True, name="DistillationJanitor")

        self.threads = [t_outbox, t_janitor, t_distill]
        for t in self.threads:
            t.start()
            logger.info(f"Started thread: {t.name}")

        logger.info("🟢 HIVEBrain Daemon is fully operational.")

    def stop(self):
        logger.info("Stopping HIVEBrain Daemon...")
        self.running = False
        for t in self.threads:
            t.join(timeout=2.0)
        logger.info("HIVEBrain Daemon stopped.")

    def _run_outbox_loop(self):
        while self.running:
            try:
                res = self.outbox_worker.process_batch()
                if res.get("processed", 0) > 0:
                    logger.info(f"[Outbox] Fan-out processed {res['processed']} events: {res['l3_vectors_written']} vectors, {res['l4_edges_written']} edges")
            except Exception as e:
                logger.error(f"[Outbox] Error in fan-out cycle: {e}")
            time.sleep(1.0)

    def _run_janitor_loop(self):
        while self.running:
            try:
                stats = self.concurrency.janitor_reclaim_expired()
                if stats.get("reclaimed_reservations", 0) > 0 or stats.get("reclaimed_leases", 0) > 0:
                    logger.info(f"[Janitor] Reclaimed expired: {stats}")
            except Exception as e:
                logger.error(f"[Janitor] Error in lease reclamation: {e}")
            time.sleep(5.0)

    def _run_distillation_loop(self):
        # Initial run after 10 seconds, then every 3600 seconds
        time.sleep(10.0)
        while self.running:
            try:
                logger.info("[Distillation] Checking 5-day continuous learning criteria...")
                distill_res = self.distillation_engine.run_distillation()
                if distill_res.get("events_distilled", 0) > 0:
                    logger.info(f"[Distillation] Completed: {distill_res}")
            except Exception as e:
                logger.error(f"[Distillation] Error in cycle: {e}")
            # Sleep 1 hour between full distillation checks
            for _ in range(3600):
                if not self.running:
                    break
                time.sleep(1.0)

def main():
    daemon = HIVEBrainDaemon()
    
    def handle_sig(sig, frame):
        logger.info("Signal received, shutting down daemon...")
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    daemon.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        daemon.stop()

if __name__ == "__main__":
    main()
