from __future__ import annotations

import pytest
from app.core.security import PasswordInputError, PasswordSecurity


@pytest.fixture
def passwords() -> PasswordSecurity:
    return PasswordSecurity(minimum_length=12, maximum_length=128)


def test_argon2id_hashes_and_verifies_passwords(passwords: PasswordSecurity) -> None:
    password_hash = passwords.hash("Synthetic test password 42")

    assert password_hash.startswith("$argon2id$")
    assert passwords.verify("Synthetic test password 42", password_hash).verified is True
    assert passwords.verify("incorrect synthetic password", password_hash).verified is False


def test_malformed_hash_is_a_safe_verification_failure(passwords: PasswordSecurity) -> None:
    assert passwords.verify("Synthetic test password 42", "not-a-password-hash").verified is False


@pytest.mark.parametrize("password", [" short ", "too short", "x" * 129])
def test_password_input_policy_is_bounded(passwords: PasswordSecurity, password: str) -> None:
    with pytest.raises(PasswordInputError):
        passwords.hash(password)


def test_dummy_verification_accepts_unknown_account_input(passwords: PasswordSecurity) -> None:
    # This assertion deliberately contains no credential/hash output.
    passwords.verify_dummy("any submitted value")
