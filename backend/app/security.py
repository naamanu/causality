from __future__ import annotations

import hashlib
import re
import secrets
from typing import Any


SENSITIVE_KEY = re.compile(r"(^|[._-])(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)($|[._-])", re.I)
SENSITIVE_VALUE = re.compile(r"(?i)(bearer\s+|sk[-_][a-z]*|api[_-]?key[=:]\s*)[A-Za-z0-9._-]{8,}")


def redact_attributes(attrs: dict[str, Any]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in attrs.items():
        clean[str(key)] = "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact_text(str(value))
    return clean


def redact_text(value: str) -> str:
    return SENSITIVE_VALUE.sub(lambda m: m.group(1) + "[REDACTED]", value)[:16_384]


def issue_ingestion_key() -> tuple[str, str, str]:
    prefix = f"cly_ing_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    raw = f"{prefix}.{secret}"
    return raw, prefix, hashlib.sha256(raw.encode()).hexdigest()


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def constant_time_key_matches(raw: str, expected_hash: str) -> bool:
    return secrets.compare_digest(hash_key(raw), expected_hash)
