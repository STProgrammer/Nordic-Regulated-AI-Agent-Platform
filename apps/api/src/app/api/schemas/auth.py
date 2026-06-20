"""Typed public request/response models for Phase 6 authentication endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.auth.principal import RoleName


def _normalized_email(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized or len(normalized) > 320 or "@" not in normalized or " " in normalized:
        raise ValueError("A valid email address is required.")
    return normalized


class LoginRequest(BaseModel):
    """Public local-password login input; passwords are write-only."""

    model_config = ConfigDict(str_strip_whitespace=False, extra="forbid")

    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=512)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalized_email(value)


class CurrentUserData(BaseModel):
    """Safe principal fields returned to the authenticated caller."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    organization_id: UUID
    display_name: str
    preferred_language: str
    roles: tuple[RoleName, ...]


class LogoutData(BaseModel):
    """A minimal logout confirmation without cookie/session material."""

    model_config = ConfigDict(frozen=True)

    logged_out: bool = True
