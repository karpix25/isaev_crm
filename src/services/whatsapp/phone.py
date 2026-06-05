from __future__ import annotations

import re


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = normalize_phone_digits(value)
    if not digits:
        return None
    return f"+{digits}"


def normalize_phone_digits(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value)
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) < 10:
        return None
    return digits
