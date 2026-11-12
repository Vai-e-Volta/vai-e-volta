from __future__ import annotations

import re

from argon2 import PasswordHasher


class RegistrationSecurity:
    """CPF, password and hashing helpers defined by H001-4."""

    def __init__(self) -> None:
        self._password_hasher = PasswordHasher()

    @staticmethod
    def normalize_cpf(cpf: str) -> str | None:
        if re.fullmatch(r"[0-9]{11}", cpf):
            digits = cpf
        elif re.fullmatch(r"[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}", cpf):
            digits = re.sub(r"\D", "", cpf)
        else:
            return None

        if len(set(digits)) == 1:
            return None

        numbers = [int(digit) for digit in digits]
        first_check = sum(number * weight for number, weight in zip(numbers[:9], range(10, 1, -1)))
        first_check = 0 if first_check % 11 < 2 else 11 - first_check % 11
        second_check = sum(
            number * weight for number, weight in zip(numbers[:9] + [first_check], range(11, 1, -1))
        )
        second_check = 0 if second_check % 11 < 2 else 11 - second_check % 11
        if numbers[-2:] != [first_check, second_check]:
            return None
        return digits

    @staticmethod
    def validate_password(password: str) -> bool:
        return (
            8 <= len(password) <= 128
            and any(character.isupper() for character in password)
            and any(character.isdigit() for character in password)
            and any(not character.isalnum() and not character.isspace() for character in password)
        )

    @staticmethod
    def normalize_phone(phone: str) -> str | None:
        accepted_formats = (
            r"[0-9]{11}",
            r"\([0-9]{2}\) ?[0-9]{5}-?[0-9]{4}",
            r"[0-9]{2} ?[0-9]{5}-[0-9]{4}",
        )
        if not any(re.fullmatch(pattern, phone) for pattern in accepted_formats):
            return None
        digits = re.sub(r"\D", "", phone)
        return digits if len(digits) == 11 and digits[2] == "9" else None

    def hash_password(self, password: str) -> str:
        return self._password_hasher.hash(password)


registration_security = RegistrationSecurity()
