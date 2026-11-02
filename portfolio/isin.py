"""Validate ISIN format and its Luhn check digit without external services."""

import re


def is_valid_isin(value: str) -> bool:
    """Check syntax and checksum; this does not establish asset existence."""
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value, flags=re.ASCII):
        return False
    digits = "".join(str(ord(char) - ord("A") + 10) if char.isalpha() else char
                     for char in value)
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char) * (2 if index % 2 else 1)
        total += number // 10 + number % 10
    return total % 10 == 0
