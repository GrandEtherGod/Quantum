from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .db import Database
from .ledger import ChronoScribeLedger
from .memory_index import BlindedTokenIndex, derive_index_key
from .models import EvidenceState
from .utils import canonical_json, sha256_hex, tokenize, utc_now


class ChrysalisMemory:
    """Encrypted episodic memory plus curated semantic crystals."""

    def __init__(self, data_dir: Path, database: Database, ledger: ChronoScribeLedger):
        self.database = database
        self.ledger = ledger
        key_dir = data_dir / "keys"
        key_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = key_dir / "memory.fernet"
        if self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            self.key_path.chmod(0o600)
        self.cipher = Fernet(key)
        self.token_index = BlindedTokenIndex(database, derive_index_key(key))
        self._backfill_index_if_needed()

    def _backfill_index_if_needed(self) -> None:
        """One-time rebuild for databases written before the blinded index existed."""
        episodes = self.database.connection.execute(
            "SELECT COUNT(*) AS count FROM episodes WHERE tombstoned_at IS NULL"
        ).fetchone()["count"]
        if episodes and not self.token_index.row_count():
            rows = self.database.connection.execute(
                "SELECT episode_id, ciphertext FROM episodes WHERE tombstoned_at IS NULL"
            ).fetchall()
            with self.database.transaction() as connection:
                for row in rows:
                    try:
                        content = self._decrypt(row["ciphertext"])
                    except InvalidToken:
                        continue
                    self.token_index.index_episode(
                        connection, row["episode_id"], content
                    )

    def add_episode(
        self,
        content: str,
        *,
        session_id: str,
        kind: str,
        importance: float = 0.5,
        evidence_state: EvidenceState = EvidenceState.SUPPORTED,
        actor: str = "system",
    ) -> str:
        if not content.strip():
            raise ValueError("Empty episodes are not stored.")
        if not 0.0 <= importance <= 1.0:
            raise ValueError("importance must be in [0, 1]")
        episode_id = str(uuid.uuid4())
        content_hash = sha256_hex(content)
        ciphertext = self.cipher.encrypt(content.encode("utf-8"))
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO episodes(
                    episode_id, session_id, kind, ciphertext, content_hash,
                    importance, evidence_state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    session_id,
                    kind,
                    ciphertext,
                    content_hash,
                    importance,
                    evidence_state.value,
                    utc_now(),
                ),
            )
            self.ledger.append(
                "memory_episode_stored",
                {
                    "episode_id": episode_id,
                    "kind": kind,
                    "content_hash": content_hash,
                    "importance": importance,
                    "evidence_state": evidence_state.value,
                },
                session_id=session_id,
                actor=actor,
                connection=connection,
            )
            self.token_index.index_episode(connection, episode_id, content)
        return episode_id

    def _decrypt(self, ciphertext: bytes | None) -> str:
        if ciphertext is None:
            raise InvalidToken("Episode payload was deleted.")
        return self.cipher.decrypt(ciphertext).decode("utf-8")

    def command_for_session(self, session_id: str) -> str | None:
        row = self.database.connection.execute(
            """
            SELECT ciphertext FROM episodes
            WHERE session_id=? AND kind='command' AND tombstoned_at IS NULL
            ORDER BY created_at LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            return self._decrypt(row["ciphertext"])
        except InvalidToken:
            return None

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        candidate_ids = self.token_index.candidates(query_tokens)
        if not candidate_ids and self.token_index.row_count() == 0:
            # Defensive: index was somehow emptied after backfill; rebuild once.
            self._backfill_index_if_needed()
            candidate_ids = self.token_index.candidates(query_tokens)
        if not candidate_ids:
            return []
        rows: list[Any] = []
        ids = list(candidate_ids)
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows.extend(
                self.database.connection.execute(
                    f"SELECT * FROM episodes WHERE episode_id IN ({placeholders})"
                    " AND tombstoned_at IS NULL ORDER BY created_at DESC",
                    chunk,
                ).fetchall()
            )
        scored: list[dict[str, Any]] = []
        for row in rows:
            try:
                content = self._decrypt(row["ciphertext"])
            except InvalidToken:
                continue
            content_tokens = tokenize(content)
            union = query_tokens | content_tokens
            score = len(query_tokens & content_tokens) / len(union) if union else 0.0
            if score > 0.0:
                scored.append(
                    {
                        "episode_id": row["episode_id"],
                        "session_id": row["session_id"],
                        "kind": row["kind"],
                        "content": content,
                        "score": round(score, 6),
                        "importance": row["importance"],
                        "evidence_state": row["evidence_state"],
                        "created_at": row["created_at"],
                    }
                )
        scored.sort(key=lambda item: (item["score"], item["importance"]), reverse=True)
        return scored[:limit]

    def tombstone(self, episode_id: str, *, actor: str, reason: str) -> bool:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT content_hash, session_id, tombstoned_at FROM episodes WHERE episode_id=?",
                (episode_id,),
            ).fetchone()
            if row is None:
                return False
            if row["tombstoned_at"] is not None:
                return True
            connection.execute(
                "UPDATE episodes SET ciphertext=NULL, tombstoned_at=? WHERE episode_id=?",
                (utc_now(), episode_id),
            )
            self.token_index.remove_episode(connection, episode_id)
            self.ledger.append(
                "memory_episode_tombstoned",
                {
                    "episode_id": episode_id,
                    "content_hash": row["content_hash"],
                    "reason": reason,
                },
                session_id=row["session_id"],
                actor=actor,
                connection=connection,
            )
        return True

    def consolidate(self, *, threshold: float, actor: str = "system") -> dict[str, Any]:
        rows = self.database.connection.execute(
            """
            SELECT * FROM episodes
            WHERE tombstoned_at IS NULL AND importance >= ?
            ORDER BY created_at
            """,
            (threshold,),
        ).fetchall()
        if not rows:
            return {"created": False, "reason": "no_eligible_episodes"}
        source_ids: list[str] = []
        words: list[str] = []
        seen: set[str] = set()
        importance_values: list[float] = []
        for row in rows:
            try:
                content = self._decrypt(row["ciphertext"])
            except InvalidToken:
                continue
            source_ids.append(row["episode_id"])
            importance_values.append(float(row["importance"]))
            for word in content.split():
                normalized = word.lower().strip(".,:;!?()[]{}\"'")
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    words.append(word)
                if len(words) >= 80:
                    break
            if len(words) >= 80:
                break
        if not source_ids:
            return {"created": False, "reason": "eligible_payloads_unavailable"}
        summary = " ".join(words)
        crystal_id = str(uuid.uuid4())
        stability = round(sum(importance_values) / len(importance_values), 6)
        confidence = min(stability, 0.95)
        ciphertext = self.cipher.encrypt(summary.encode("utf-8"))
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO crystals(
                    crystal_id, summary_ciphertext, source_episode_ids_json,
                    stability, confidence, evidence_state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    crystal_id,
                    ciphertext,
                    canonical_json(source_ids),
                    stability,
                    confidence,
                    EvidenceState.PLAUSIBLE.value,
                    utc_now(),
                ),
            )
            event = self.ledger.append(
                "memory_crystallized",
                {
                    "crystal_id": crystal_id,
                    "source_episode_ids": source_ids,
                    "summary_hash": sha256_hex(summary),
                    "stability": stability,
                    "confidence": confidence,
                    "evidence_state": EvidenceState.PLAUSIBLE.value,
                },
                actor=actor,
                connection=connection,
            )
        return {
            "created": True,
            "crystal_id": crystal_id,
            "source_episode_count": len(source_ids),
            "stability": stability,
            "confidence": confidence,
            "event_hash": event["event_hash"],
        }

    def stats(self) -> dict[str, int]:
        episodes = self.database.connection.execute(
            "SELECT COUNT(*) AS count FROM episodes WHERE tombstoned_at IS NULL"
        ).fetchone()["count"]
        tombstones = self.database.connection.execute(
            "SELECT COUNT(*) AS count FROM episodes WHERE tombstoned_at IS NOT NULL"
        ).fetchone()["count"]
        crystals = self.database.connection.execute(
            "SELECT COUNT(*) AS count FROM crystals WHERE active=1"
        ).fetchone()["count"]
        return {"active_episodes": episodes, "tombstones": tombstones, "active_crystals": crystals}

