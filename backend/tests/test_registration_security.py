from __future__ import annotations

import pytest
from argon2 import PasswordHasher

from app.security.registration import RegistrationSecurity


@pytest.fixture
def security() -> RegistrationSecurity:
    return RegistrationSecurity()


@pytest.mark.parametrize(
    ("cpf", "expected"),
    [
        ("11144477735", "11144477735"),
        ("111.444.777-35", "11144477735"),
        ("12345678909", "12345678909"),
    ],
)
def test_UT_REG_02_normalizes_valid_cpf(
    security: RegistrationSecurity, cpf: str, expected: str
) -> None:
    assert security.normalize_cpf(cpf) == expected


@pytest.mark.parametrize("cpf", ["11111111111", "12345678900", "123.456789-09", "abc"])
def test_UT_REG_02_rejects_invalid_cpf(security: RegistrationSecurity, cpf: str) -> None:
    assert security.normalize_cpf(cpf) is None


def test_UT_REG_03_password_policy_boundaries(security: RegistrationSecurity) -> None:
    assert not security.validate_password("Aa1!aaa")
    assert security.validate_password("Aa1!aaaa")
    assert security.validate_password("Aa1!" + "a" * 124)
    assert not security.validate_password("Aa1!" + "a" * 125)
    assert not security.validate_password("Aa1 aaaa")
    assert not security.validate_password("lowercase1!")
    assert not security.validate_password("NoDigits!!")
    assert not security.validate_password("NoSymbol123")


@pytest.mark.parametrize(
    ("phone", "expected"),
    [("51999990000", "51999990000"), ("(51) 99999-0000", "51999990000")],
)
def test_UT_REG_04_normalizes_mobile_phone(
    security: RegistrationSecurity, phone: str, expected: str
) -> None:
    assert security.normalize_phone(phone) == expected


@pytest.mark.parametrize("phone", ["1234567890", "+55 51 99999-0000", "5199999abcd", "51888880000"])
def test_UT_REG_04_rejects_invalid_phone(security: RegistrationSecurity, phone: str) -> None:
    assert security.normalize_phone(phone) is None


def test_UT_REG_04_argon2id_hash_is_salted_and_verifiable(security: RegistrationSecurity) -> None:
    password = "SenhaForte1!"

    first_hash = security.hash_password(password)
    second_hash = security.hash_password(password)

    assert first_hash.startswith("$argon2id$")
    assert second_hash.startswith("$argon2id$")
    assert first_hash != second_hash
    assert PasswordHasher().verify(first_hash, password)
