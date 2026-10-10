import sqlite3
import unittest

from rewindlab import ConflictingRevisionError, Revision, RevisionStore


def revision(
    revision_id: str,
    event_id: str = "event-1",
    valid_at: str = "2025-01-01T12:00:00Z",
    known_at: str = "2025-01-01T13:00:00Z",
    signal_value: int = 100,
) -> Revision:
    return Revision.from_dict(
        {
            "revision_id": revision_id,
            "event_id": event_id,
            "valid_at": valid_at,
            "known_at": known_at,
            "signal_value": signal_value,
            "source": "test-feed",
        }
    )


class RevisionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = RevisionStore()

    def tearDown(self) -> None:
        self.store.close()

    def test_late_correction_does_not_leak_into_as_known_snapshot(self) -> None:
        self.store.append(revision("r1"))
        self.store.append(
            revision("r2", known_at="2025-01-09T09:00:00Z", signal_value=900)
        )

        as_known = self.store.snapshot("2025-01-02T00:00:00Z", "2025-01-02T00:00:00Z")
        latest = self.store.snapshot("2025-01-02T00:00:00Z")

        self.assertEqual([record.signal_value for record in as_known], [100])
        self.assertEqual([record.signal_value for record in latest], [900])

    def test_late_arrival_is_absent_until_knowledge_cutoff(self) -> None:
        self.store.append(
            revision("r1", known_at="2025-01-10T09:00:00Z")
        )
        self.assertEqual(
            self.store.snapshot("2025-01-02T00:00:00Z", "2025-01-04T00:00:00Z"), []
        )
        self.assertEqual(len(self.store.snapshot("2025-01-02T00:00:00Z")), 1)

    def test_correction_moving_valid_time_out_of_window_does_not_restore_old_value(self) -> None:
        self.store.append(revision("r1"))
        self.store.append(
            revision(
                "r2",
                valid_at="2025-02-01T12:00:00Z",
                known_at="2025-02-02T13:00:00Z",
            )
        )
        self.assertEqual(self.store.snapshot("2025-01-31T23:59:59Z"), [])
        self.assertEqual(
            [record["revision_id"] for record in self.store.late_revisions(
                "2025-01-31T23:59:59Z", "2025-01-02T00:00:00Z"
            )],
            ["r2"],
        )
        self.assertEqual(
            [record.revision_id for record in self.store.snapshot(
                "2025-01-31T23:59:59Z", "2025-01-02T00:00:00Z"
            )],
            ["r1"],
        )

    def test_identical_revision_retry_is_idempotent_but_conflict_is_rejected(self) -> None:
        original = revision("r1")
        self.assertTrue(self.store.append(original))
        self.assertFalse(self.store.append(original))
        self.assertEqual(len(self.store.all_revisions()), 1)
        with self.assertRaises(ConflictingRevisionError):
            self.store.append(revision("r1", signal_value=999))
        with self.assertRaises(ConflictingRevisionError):
            self.store.append(revision("r2", signal_value=999))

    def test_revision_rows_cannot_be_updated_or_deleted(self) -> None:
        self.store.append(revision("r1"))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.store.connection.execute("UPDATE revisions SET signal_value = 1")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.store.connection.execute("DELETE FROM revisions")

    def test_timezone_normalization_preserves_chronological_order(self) -> None:
        self.store.append(revision("r1", known_at="2025-01-01T13:00:00+01:00"))
        self.assertEqual(
            self.store.snapshot("2025-01-02T00:00:00Z", "2025-01-01T12:30:00Z"),
            self.store.snapshot("2025-01-02T00:00:00Z", "2025-01-01T13:30:00+01:00"),
        )
        with self.assertRaisesRegex(ValueError, "timezone"):
            revision("r2", known_at="2025-01-01T13:00:00")

    def test_missing_knowledge_time_is_rejected_before_import(self) -> None:
        payload = revision("r1").to_dict()
        del payload["known_at"]
        with self.assertRaisesRegex(ValueError, "known_at"):
            Revision.from_dict(payload)
        self.assertEqual(self.store.all_revisions(), [])


if __name__ == "__main__":
    unittest.main()
