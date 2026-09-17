"""Password composition rules for register, reset, and authenticated change."""

from __future__ import annotations

import re

_LETTER = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"[0-9]")


def validate_password(password: str) -> str:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be between 8 and 128 characters")
    if _LETTER.search(password) is None:
        raise ValueError("Password must include at least one letter")
    if _DIGIT.search(password) is None:
        raise ValueError("Password must include at least one number")
    return password
