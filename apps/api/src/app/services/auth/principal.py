"""Trusted authenticated principal and canonical platform roles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class RoleName(StrEnum):
    """The five global roles mandated by the product requirements."""

    ADMIN = "Admin"
    COMPLIANCE_REVIEWER = "Compliance Reviewer"
    CASE_WORKER = "Case Worker"
    MANAGER = "Manager"
    READ_ONLY_AUDITOR = "Read-only Auditor"


@dataclass(frozen=True)
class Principal:
    """An immutable identity built only from server-side state and PostgreSQL."""

    user_id: UUID
    organization_id: UUID
    display_name: str
    preferred_language: str
    roles: frozenset[RoleName]


def canonical_roles(role_names: tuple[str, ...]) -> frozenset[RoleName]:
    """Keep only recognized global roles when materializing a principal."""

    recognized: set[RoleName] = set()
    for role_name in role_names:
        try:
            recognized.add(RoleName(role_name))
        except ValueError:
            # A future/global non-product role must not implicitly grant access.
            continue
    return frozenset(recognized)
