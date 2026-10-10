# Design: point-in-time core

## Approach

Use a small Python 3.14 standard-library package and SQLite file. Each row is
an immutable revision, identified by `revision_id`; `event_id` groups revisions
of the same logical observation. Store `valid_at` (when the event applies) and
`known_at` (when that revision was learned) as normalized UTC timestamps.
Explicit fixture timestamps make the demo deterministic. The fixture does not
claim a real source was available at those historical times.

The SQLite table gives `revision_id` a primary key and gives
`(event_id, known_at)` a uniqueness constraint. A trigger prevents updates and
deletes. Appending an identical revision is an acknowledged no-op; a conflicting
identity is an error. The first phase appends one revision at a time. Atomic
multi-record import is planned for Phase 2.

## Snapshot selection

For `(valid_through, known_through)`:

1. For each `event_id`, consider revisions with `known_at <= known_through`.
2. Select the revision with the maximum `known_at` for that event.
3. Include that selected revision only if its `valid_at <= valid_through`.

Omitting `known_through` uses current knowledge for the comparison view. The
valid-time filter comes after revision selection so an older revision cannot
reappear if a correction moves the event outside the window. Return all
selected records with revision IDs and both timestamps. A no-match query returns
an empty list. Use stable sorting in output so repeated runs compare exactly.

## Demo fixture

The fixture has two events initially known by the historical cutoff, one later
correction to the first event, and one later arrival. The demo uses one valid
cutoff and a knowledge cutoff before those later revisions. It prints both
snapshot counts and signal sums, and machine-readable JSON includes source
events and selected revisions. The current fixture's expected sums are 300 as
known then and 1400 with current knowledge.

## Error handling and limits

Reject missing fields, noninteger values, malformed timestamps, and ambiguous
revision identity. Catch absent or unreadable database paths with a useful
nonzero CLI exit. Phase 1 is local and single process. It makes no benchmark,
distributed recovery, or historical market accuracy claim. The digest, batch
atomicity, and injected crash corpus belong to Phase 2.
