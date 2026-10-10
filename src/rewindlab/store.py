"""SQLite-backed immutable revisions with separate valid and knowledge times."""

from __future__ import annotations

import sqlite3
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class ConflictingRevisionError(ValueError):
    """A revision ID was reused with different content."""


class BatchValidationError(ValueError):
    """A revision failed schema validation at a zero-based batch row index."""

    def __init__(self, row_index: int, detail: str) -> None:
        self.row_index = row_index
        self.detail = detail
        super().__init__(detail)


def normalize_time(value: str) -> str:
    """Return a fixed-width UTC timestamp so SQLite text ordering is chronological."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid ISO 8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


@dataclass(frozen=True)
class Revision:
    revision_id: str
    event_id: str
    valid_at: str
    known_at: str
    signal_value: int
    source: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Revision:
        if not isinstance(raw, dict):
            raise ValueError("Revision must be a JSON object")
        required = {"revision_id", "event_id", "valid_at", "known_at", "signal_value", "source"}
        missing = required - raw.keys()
        if missing:
            raise ValueError(f"Missing revision fields: {', '.join(sorted(missing))}")
        unexpected = raw.keys() - required
        if unexpected:
            raise ValueError(f"Unexpected revision fields: {', '.join(sorted(unexpected))}")
        if any(not isinstance(raw[key], str) or not raw[key].strip() for key in
               ("revision_id", "event_id", "valid_at", "known_at", "source")):
            raise ValueError("Revision IDs, source, and timestamps must be nonempty strings")
        if type(raw["signal_value"]) is not int:
            raise ValueError("signal_value must be an integer")
        if not -(1 << 63) <= raw["signal_value"] <= (1 << 63) - 1:
            raise ValueError("signal_value must fit a signed SQLite 64-bit integer")
        return cls(
            revision_id=raw["revision_id"],
            event_id=raw["event_id"],
            valid_at=normalize_time(raw["valid_at"]),
            known_at=normalize_time(raw["known_at"]),
            signal_value=raw["signal_value"],
            source=raw["source"],
        )

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class RevisionStore:
    """One append-only revision log; callers own the store and close it when done."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS revisions (
                revision_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                valid_at TEXT NOT NULL,
                known_at TEXT NOT NULL,
                signal_value INTEGER NOT NULL,
                source TEXT NOT NULL,
                UNIQUE (event_id, known_at)
            );
            CREATE INDEX IF NOT EXISTS idx_revisions_known_event
                ON revisions (known_at, event_id);
            CREATE TRIGGER IF NOT EXISTS revisions_no_update
                BEFORE UPDATE ON revisions
                BEGIN SELECT RAISE(ABORT, 'revisions are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS revisions_no_delete
                BEFORE DELETE ON revisions
                BEGIN SELECT RAISE(ABORT, 'revisions are immutable'); END;
            """
        )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> RevisionStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def append(self, revision: Revision) -> bool:
        """Append a revision; return False for an identical retry."""
        inserted, _ = self.import_batch([revision])
        return inserted == 1

    def import_batch(self, revisions: Iterable[Revision | dict[str, Any]]) -> tuple[int, int]:
        """Atomically import a batch; return (new rows, identical retries).

        Validation and conflict checks occur inside one SQLite savepoint.
        A bad later row rolls back this batch while preserving an outer
        transaction owned by the caller.
        """
        inserted = duplicate = 0
        self.connection.execute("SAVEPOINT rewindlab_import_batch")
        try:
            for row_index, raw in enumerate(revisions):
                try:
                    normalized = Revision.from_dict(raw.to_dict() if isinstance(raw, Revision) else raw)
                except ValueError as exc:
                    raise BatchValidationError(row_index, str(exc)) from exc
                values = tuple(normalized.to_dict().values())
                try:
                    self.connection.execute(
                        """INSERT INTO revisions
                           (revision_id, event_id, valid_at, known_at, signal_value, source)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        values,
                    )
                    inserted += 1
                except sqlite3.IntegrityError as exc:
                    row = self.connection.execute(
                        "SELECT * FROM revisions WHERE revision_id = ?", (normalized.revision_id,)
                    ).fetchone()
                    if row is not None and dict(row) == normalized.to_dict():
                        duplicate += 1
                        continue
                    raise ConflictingRevisionError(
                        f"Revision {normalized.revision_id!r} conflicts with an existing revision "
                        "or another revision for the same event and known_at"
                    ) from exc
        except BaseException:
            self.connection.execute("ROLLBACK TO SAVEPOINT rewindlab_import_batch")
            self.connection.execute("RELEASE SAVEPOINT rewindlab_import_batch")
            raise
        self.connection.execute("RELEASE SAVEPOINT rewindlab_import_batch")
        return inserted, duplicate

    def dataset_digest(self) -> str:
        """SHA-256 of sorted logical revisions, independent of import order."""
        rows = [revision.to_dict() for revision in self.all_revisions()]
        rows.sort(key=lambda row: row["revision_id"])
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def snapshot(self, valid_through: str, known_through: str | None = None) -> list[Revision]:
        """Latest version of each event known at a time, then valid-time filtered.

        When ``known_through`` is omitted, this is a naive current-knowledge
        historical query. The valid-time filter is applied after selecting the
        latest known revision, so a correction can move an event out of range.
        """
        valid_cutoff = normalize_time(valid_through)
        knowledge_cutoff = normalize_time(known_through) if known_through else None
        rows = self.connection.execute(
            """
            WITH ranked AS (
                SELECT revision_id, event_id, valid_at, known_at,
                       signal_value, source,
                       ROW_NUMBER() OVER (
                           PARTITION BY event_id
                           ORDER BY known_at DESC, revision_id DESC
                       ) AS revision_rank
                FROM revisions
                WHERE (? IS NULL OR known_at <= ?)
            )
            SELECT revision_id, event_id, valid_at, known_at, signal_value, source
            FROM ranked
            WHERE revision_rank = 1 AND valid_at <= ?
            ORDER BY valid_at, event_id
            """,
            (knowledge_cutoff, knowledge_cutoff, valid_cutoff),
        ).fetchall()
        return [Revision(**dict(row)) for row in rows]

    def all_revisions(self) -> list[Revision]:
        rows = self.connection.execute(
            """SELECT revision_id, event_id, valid_at, known_at, signal_value, source
               FROM revisions ORDER BY known_at, event_id, revision_id"""
        ).fetchall()
        return [Revision(**dict(row)) for row in rows]

    def late_revisions(self, valid_through: str, known_through: str) -> list[dict[str, Any]]:
        """Revisions affecting the historical valid-time window learned later."""
        valid_cutoff = normalize_time(valid_through)
        knowledge_cutoff = normalize_time(known_through)
        rows = self.connection.execute(
            """
            SELECT r.revision_id, r.event_id, r.valid_at, r.known_at,
                   r.signal_value, r.source,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM revisions previous
                       WHERE previous.event_id = r.event_id
                         AND previous.known_at < r.known_at
                   ) THEN 'correction' ELSE 'late_arrival' END AS change_type
            FROM revisions r
            WHERE r.known_at > ?
              AND (
                  r.valid_at <= ?
                  OR EXISTS (
                      SELECT 1 FROM revisions previous
                      WHERE previous.event_id = r.event_id
                        AND previous.known_at < r.known_at
                        AND previous.valid_at <= ?
                  )
              )
            ORDER BY r.known_at, r.event_id, r.revision_id
            """,
            (knowledge_cutoff, valid_cutoff, valid_cutoff),
        ).fetchall()
        return [dict(row) for row in rows]
