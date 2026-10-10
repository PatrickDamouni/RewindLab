"""Point-in-time queries over immutable revisions of synthetic data."""

from .store import ConflictingRevisionError, Revision, RevisionStore

__all__ = ["ConflictingRevisionError", "Revision", "RevisionStore"]
