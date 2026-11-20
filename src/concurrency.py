"""
HIVEBrain Concurrency Manager: Total-Order Reservations & Lease Manager.
Implements the Airline Ticket Booking Paradigm:
- Front-loaded atomic soft reservations with TTL.
- Total-order entity sorting to guarantee deadlock freedom (no circular waits).
- Optimistic Concurrency Control (OCC) version vector validation.
- Background lease and reservation janitor for automatic reclamation.
"""

import time
import uuid
import hashlib
from typing import List, Dict, Any, Tuple, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "/tmp",
    "dbname": "gravity_brain",
    "user": "nishant"
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

class ConcurrencyManager:
    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.db_config = db_config or DB_CONFIG

    def _get_conn(self):
        return psycopg2.connect(**self.db_config)

    def reserve_entities(
        self,
        entity_ids: List[str],
        agent_id: str,
        ttl_ms: int = 5000,
        commit_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Total-order reservation: sorts entity_ids lexicographically to eliminate deadlock cycles.
        Atomically claims reservations using partial unique index on (entity_id) WHERE active = true.
        """
        if not entity_ids:
            return {"status": "ok", "reservation_ids": [], "token": commit_token or str(uuid.uuid4())}

        # 1. Total-ordering by entity ID (lexicographic ascending)
        sorted_entities = sorted(list(set(entity_ids)))
        token = commit_token or str(uuid.uuid4())
        reservation_ids = []
        acquired_entities = []

        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First clean up any expired reservations on these entities
                cur.execute(
                    """
                    UPDATE brain_reservations
                    SET active = false
                    WHERE entity_id = ANY(%s) AND active = true AND expires_at <= NOW();
                    """,
                    (sorted_entities,)
                )

                for eid in sorted_entities:
                    payload_hash = hashlib.sha256(f"{eid}:{token}".encode()).hexdigest()
                    cur.execute(
                        """
                        INSERT INTO brain_reservations (
                            reservation_id, entity_id, agent_id, active,
                            payload_hash, commit_token, ttl_ms, expires_at
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s, true,
                            %s, %s, %s, NOW() + (%s * INTERVAL '1 millisecond')
                        )
                        ON CONFLICT (entity_id) WHERE active DO NOTHING
                        RETURNING reservation_id, expires_at;
                        """,
                        (eid, agent_id, payload_hash, token, ttl_ms, ttl_ms)
                    )
                    row = cur.fetchone()
                    if not row:
                        # Conflict! Roll back any previously acquired reservations in this batch
                        conn.rollback()
                        return {
                            "status": "conflict",
                            "conflicted_entity": eid,
                            "acquired_entities": acquired_entities,
                            "message": f"Entity '{eid}' is currently reserved by another agent."
                        }
                    reservation_ids.append(str(row["reservation_id"]))
                    acquired_entities.append(eid)

                conn.commit()
                return {
                    "status": "reserved",
                    "reservation_ids": reservation_ids,
                    "entities": acquired_entities,
                    "commit_token": token,
                    "ttl_ms": ttl_ms
                }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def release_reservations(self, commit_token: str, agent_id: str) -> int:
        """Explicitly releases all reservations associated with a commit token."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE brain_reservations
                    SET active = false
                    WHERE commit_token = %s AND agent_id = %s AND active = true;
                    """,
                    (commit_token, agent_id)
                )
                count = cur.rowcount
                conn.commit()
                return count
        finally:
            conn.close()

    def claim_lease(
        self,
        entity_id: str,
        agent_id: str,
        purpose: str,
        ttl_seconds: int = 60
    ) -> Dict[str, Any]:
        """Lease-based soft claim for long-running workflows/distillation."""
        lease_id = f"lease:{uuid.uuid4().hex[:12]}"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Reclaim expired leases for this entity
                cur.execute(
                    "DELETE FROM brain_leases WHERE entity_id = %s AND expires_at <= NOW();",
                    (entity_id,)
                )
                cur.execute(
                    """
                    INSERT INTO brain_leases (lease_id, entity_id, agent_id, purpose, expires_at)
                    VALUES (%s, %s, %s, %s, NOW() + (%s * INTERVAL '1 second'))
                    RETURNING lease_id, expires_at;
                    """,
                    (lease_id, entity_id, agent_id, purpose, ttl_seconds)
                )
                row = cur.fetchone()
                conn.commit()
                return {
                    "status": "leased",
                    "lease_id": row["lease_id"],
                    "expires_at": row["expires_at"].isoformat()
                }
        finally:
            conn.close()

    def validate_and_bump_version_vector(
        self,
        entity_id: str,
        client_vv: Dict[str, int],
        agent_id: str
    ) -> Tuple[bool, Dict[str, int], int]:
        """
        Optimistic Concurrency Control (OCC) version vector validator:
        1. Checks that client_vv >= server_vv for all agents.
        2. Bumps version and agent's entry in version_vector.
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT version, version_vector FROM brain_entities WHERE entity_id = %s FOR UPDATE;",
                    (entity_id,)
                )
                row = cur.fetchone()
                if not row:
                    # Entity does not exist yet; initialize
                    new_vv = {agent_id: 1}
                    return True, new_vv, 1

                server_version = row["version"]
                server_vv = row["version_vector"] or {}

                # Check for stale read
                for a, seq in server_vv.items():
                    if client_vv.get(a, 0) < seq:
                        return False, server_vv, server_version

                # Validation passed: bump agent sequence and version
                new_vv = dict(server_vv)
                new_vv[agent_id] = new_vv.get(agent_id, 0) + 1
                new_version = server_version + 1

                cur.execute(
                    """
                    UPDATE brain_entities
                    SET version = %s, version_vector = %s, updated_at = NOW()
                    WHERE entity_id = %s;
                    """,
                    (new_version, psycopg2.extras.Json(new_vv), entity_id)
                )
                conn.commit()
                return True, new_vv, new_version
        finally:
            conn.close()

    def janitor_reclaim_expired(self) -> Dict[str, int]:
        """Cleans up expired reservations and leases."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE brain_reservations SET active = false WHERE active = true AND expires_at <= NOW();"
                )
                reclaimed_res = cur.rowcount
                cur.execute("DELETE FROM brain_leases WHERE expires_at <= NOW();")
                reclaimed_leases = cur.rowcount
                conn.commit()
                return {
                    "reclaimed_reservations": reclaimed_res,
                    "reclaimed_leases": reclaimed_leases
                }
        finally:
            conn.close()
