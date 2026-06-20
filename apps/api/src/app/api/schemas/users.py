"""Typed administrator user and role-management API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.schemas.auth import _normalized_email
from app.services.auth.principal import RoleName


class UserCreateRequest(BaseModel):
    """Admin input for an organization-scoped user; no organization ID is accepted."""

    email: str = Field(max_length=320)
    display_name: str = Field(min_length=1, max_length=500)
    preferred_language: str = Field(min_length=2, max_length=16)
    password: str | None = Field(default=None, min_length=1, max_length=512)
    role_names: tuple[RoleName, ...] = Field(default=(), max_length=5)

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalized_email(value)

    @field_validator("display_name", "preferred_language")
    @classmethod
    def _require_content(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("This field must not be empty.")
        return trimmed

    @field_validator("role_names")
    @classmethod
    def _roles_are_unique(cls, value: tuple[RoleName, ...]) -> tuple[RoleName, ...]:
        if len(set(value)) != len(value):
            raise ValueError("Role names must not contain duplicates.")
        return value


class UserUpdateRequest(BaseModel):
    """Admin input for permitted identity changes; email/provider fields are immutable here."""

    display_name: str | None = Field(default=None, min_length=1, max_length=500)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=16)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=512)

    model_config = ConfigDict(extra="forbid")

    @field_validator("display_name", "preferred_language")
    @classmethod
    def _normalize_optional_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("This field must not be empty.")
        return trimmed

    @model_validator(mode="after")
    def _require_change(self) -> UserUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("At least one mutable field is required.")
        return self


class RolesReplaceRequest(BaseModel):
    """Complete replacement role set, constrained to the five canonical roles."""

    role_names: tuple[RoleName, ...] = Field(max_length=5)

    model_config = ConfigDict(extra="forbid")

    @field_validator("role_names")
    @classmethod
    def _roles_are_unique(cls, value: tuple[RoleName, ...]) -> tuple[RoleName, ...]:
        if len(set(value)) != len(value):
            raise ValueError("Role names must not contain duplicates.")
        return value


class UserData(BaseModel):
    """Safe identity view; password hashes and provider subjects are intentionally absent."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    email: str
    display_name: str
    preferred_language: str
    is_active: bool
    roles: tuple[RoleName, ...]


class UserListData(BaseModel):
    """Bounded user page with stable public metadata."""

    model_config = ConfigDict(frozen=True)

    items: tuple[UserData, ...]
    limit: int
    offset: int
    total: int
    has_more: bool


class RoleData(BaseModel):
    """Safe global role catalogue item."""

    model_config = ConfigDict(frozen=True)

    role_id: UUID
    name: RoleName
    description: str
