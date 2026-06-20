"""Server-owned opaque raw-document storage key generation."""

from uuid import UUID


def document_storage_key(*, organization_id: UUID, case_id: UUID, document_id: UUID) -> str:
    """Return a key derived only from trusted durable identifiers.

    The key intentionally excludes titles, filenames, MIME types, checksums, and
    all client-controlled data. It remains a private persistence detail and is
    never returned through an API or audit event.
    """

    return f"v1/organizations/{organization_id}/cases/{case_id}/documents/{document_id}"
