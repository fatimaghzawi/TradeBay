
from __future__ import annotations

import re

_LETTER = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"[0-9]")

                                                                                     
PASSWORD_MAX_BYTES = 72

def validate_password(password: str) -> str:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be between 8 and 128 characters")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError("Password is too long. Please choose a shorter password.")
    if _LETTER.search(password) is None:
        raise ValueError("Password must include at least one letter")
    if _DIGIT.search(password) is None:
        raise ValueError("Password must include at least one number")
    return password
