"""Password handling primitives for local password authentication.

This module is deliberately narrow: it knows how to validate, hash, and verify
passwords with Argon2id. It does not log credentials, expose hashes, or make
authorization decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from argon2 import PasswordHasher, Type, exceptions


class PasswordInputError(ValueError):
    """A password violates the configured input policy."""


@dataclass(frozen=True)
class PasswordVerification:
    """The safe outcome of one password-hash verification."""

    verified: bool
    needs_rehash: bool = False


def _build_hasher() -> PasswordHasher:
    """Create the one Argon2id parameter profile used by this application."""

    return PasswordHasher(
        time_cost=3,
        memory_cost=65_536,
        parallelism=4,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )


# Computing one dummy hash at import avoids a per-login hash operation while
# preserving the verification work for unknown/non-password accounts.
_DUMMY_HASH = _build_hasher().hash("nordic-auth-dummy-verification-value")


class PasswordSecurity:
    """Argon2id adapter with a small, explicit password-input policy."""

    def __init__(self, *, minimum_length: int, maximum_length: int) -> None:
        self.minimum_length = minimum_length
        self.maximum_length = maximum_length
        self._hasher = _build_hasher()

    def validate_input(self, password: str) -> None:
        """Reject ambiguous, too-short, or unbounded password input.

        Passwords are never silently trimmed because that turns a credential a
        user supplied into a different credential. API schemas enforce the broad
        maximum too; this method keeps service callers equally safe.
        """

        if password != password.strip():
            raise PasswordInputError("Password must not start or end with whitespace.")
        if len(password) < self.minimum_length:
            raise PasswordInputError("Password does not meet the minimum length.")
        if len(password) > self.maximum_length:
            raise PasswordInputError("Password exceeds the maximum length.")

    def hash(self, password: str) -> str:
        """Validate and create a non-reversible Argon2id password hash."""

        self.validate_input(password)
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> PasswordVerification:
        """Safely verify a password, treating malformed hashes as a mismatch."""

        try:
            verified = self._hasher.verify(password_hash, password)
        except (exceptions.InvalidHashError, exceptions.VerificationError):
            return PasswordVerification(verified=False)
        if not verified:  # ``verify`` normally raises for mismatch; keep total behavior explicit.
            return PasswordVerification(verified=False)
        return PasswordVerification(
            verified=True,
            needs_rehash=self._hasher.check_needs_rehash(password_hash),
        )

    def verify_dummy(self, password: str) -> None:
        """Perform equivalent Argon2id work without reporting an account outcome."""

        # A dummy verification must accept every syntactically supplied password
        # so short/wrong passwords do not become a timing oracle for email lookup.
        self.verify(password, _DUMMY_HASH)
