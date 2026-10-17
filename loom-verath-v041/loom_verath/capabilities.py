from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from .db import Database
from .errors import CapabilityDenied
from .ledger import ChronoScribeLedger
from .utils import canonical_json, sha256_hex, utc_now


class CapabilityBroker:
    """Least-privilege bearer capabilities stored only as token hashes."""

    def __init__(self, database: Database, ledger: ChronoScribeLedger):
        self.database = database
        self.ledger = ledger

    def issue(
        self,
        *,
        principal: str,
        actions: Iterable[str],
        resource: str,
        ttl_seconds: int = 3600,
        risk: str = "low",
        human_approved: bool = False,
    ) -> str:
        actions = sorted(set(actions))
        if not actions:
            raise ValueError("A capability must authorize at least one action.")
        if risk in {"high", "critical"} and not human_approved:
            raise CapabilityDenied("High-risk capability issuance requires explicit human approval.")
        capability_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        token_hash = sha256_hex(token)
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO capabilities(
                    capability_id, principal, token_hash, actions_json, resource,
                    issued_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    capability_id,
                    principal,
                    token_hash,
                    canonical_json(actions),
                    resource,
                    issued_at.isoformat().replace("+00:00", "Z"),
                    expires_at.isoformat().replace("+00:00", "Z"),
                ),
            )
            self.ledger.append(
                "capability_issued",
                {
                    "capability_id": capability_id,
                    "principal": principal,
                    "actions": actions,
                    "resource": resource,
                    "risk": risk,
                    "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
                },
                connection=connection,
            )
        return token

    def authorize(self, token: str, action: str, resource: str) -> dict[str, Any]:
        row = self.database.connection.execute(
            "SELECT * FROM capabilities WHERE token_hash=?", (sha256_hex(token),)
        ).fetchone()
        if row is None:
            raise CapabilityDenied("Unknown capability.")
        if row["revoked_at"] is not None:
            raise CapabilityDenied("Capability was revoked.")
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if datetime.now(UTC) >= expires_at:
            raise CapabilityDenied("Capability expired.")
        actions = json.loads(row["actions_json"])
        if action not in actions and "*" not in actions:
            raise CapabilityDenied(f"Capability does not authorize {action!r}.")
        if row["resource"] not in {"*", resource}:
            raise CapabilityDenied(f"Capability is not scoped to {resource!r}.")
        return {
            "capability_id": row["capability_id"],
            "principal": row["principal"],
            "action": action,
            "resource": resource,
        }

    def revoke(self, capability_id: str, *, actor: str, reason: str) -> bool:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT revoked_at FROM capabilities WHERE capability_id=?", (capability_id,)
            ).fetchone()
            if row is None:
                return False
            if row["revoked_at"] is None:
                connection.execute(
                    "UPDATE capabilities SET revoked_at=? WHERE capability_id=?",
                    (utc_now(), capability_id),
                )
                self.ledger.append(
                    "capability_revoked",
                    {"capability_id": capability_id, "reason": reason},
                    actor=actor,
                    connection=connection,
                )
        return True

