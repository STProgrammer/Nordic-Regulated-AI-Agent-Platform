"""Stable, safe errors raised by internal application services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class ServiceError(Exception):
    """Expected application failure with a stable code and safe message."""

    code: str
    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def as_dict(self) -> dict[str, str]:
        """Return data suitable for a future intentional API error adapter."""

        return {"code": self.code, "message": self.message}


class NotFoundError(ServiceError):
    """Requested resource is absent from the caller's explicit tenant scope."""

    def __init__(self, resource: str) -> None:
        super().__init__(code="not_found", message=f"{resource} was not found.")


class ConflictError(ServiceError):
    """A safe conflict caused by a known persistence constraint."""

    def __init__(self, resource: str) -> None:
        super().__init__(code="conflict", message=f"{resource} conflicts with existing data.")


class InvalidQueryError(ServiceError):
    """An internal list query used an unsupported bounded option."""

    def __init__(self, message: str = "The query options are invalid.") -> None:
        super().__init__(code="invalid_query", message=message)


class InvalidCommandError(ServiceError):
    """An internal command contains unsafe or internally inconsistent data."""

    def __init__(self, message: str = "The command is invalid.") -> None:
        super().__init__(code="invalid_command", message=message)


class AuthorizationDeniedError(ServiceError):
    """A valid principal lacks a required backend-enforced permission."""

    def __init__(self) -> None:
        super().__init__(code="forbidden", message="You are not allowed to perform this action.")
