import re
from typing import Final

EMAIL_MARKER: Final = "[REDACTED_EMAIL]"
PHONE_MARKER: Final = "[REDACTED_PHONE]"
CN_ID_MARKER: Final = "[REDACTED_CN_ID]"
PAYMENT_CARD_MARKER: Final = "[REDACTED_PAYMENT_CARD]"

_EMAIL_PATTERN: Final = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])"
)
_PHONE_PATTERN: Final = re.compile(
    r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d(?:[- ]?\d){8}(?!\d)"
)
_CN_ID_PATTERN: Final = re.compile(
    r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])"
    r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![\dXx])"
)
_PAYMENT_CARD_PATTERN: Final = re.compile(
    r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
)


def redact_sensitive_text(text: str) -> str:
    redacted = _EMAIL_PATTERN.sub(EMAIL_MARKER, text)
    redacted = _PHONE_PATTERN.sub(PHONE_MARKER, redacted)
    redacted = _CN_ID_PATTERN.sub(CN_ID_MARKER, redacted)
    return _PAYMENT_CARD_PATTERN.sub(_redact_payment_card, redacted)


def _redact_payment_card(candidate: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", candidate.group())
    if _passes_luhn(digits):
        return PAYMENT_CARD_MARKER
    return candidate.group()


def _passes_luhn(digits: str) -> bool:
    if len(digits) < 13 or len(digits) > 19 or len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
