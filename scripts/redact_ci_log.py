"""Redact sensitive wallet fields before printing CI diagnostic logs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = {
    "accesskey",
    "accesskeyid",
    "account",
    "accounts",
    "address",
    "handle",
    "key",
    "privatekey",
    "secret",
    "seed",
    "store",
    "token",
    "wallet",
    "walletaddress",
}


ETH_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
LONG_SECRET_RE = re.compile(
    r"(?i)\b(access[_-]?key|private[_-]?key|secret|seed|token|handle|address|account)s?"
    r"([\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"
)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _normalize_key(str(key)) in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_json(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        return ETH_ADDRESS_RE.sub("[REDACTED_ADDRESS]", value)
    return value


def redact_text(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        redacted = ETH_ADDRESS_RE.sub("[REDACTED_ADDRESS]", text)
        return LONG_SECRET_RE.sub(r"\1\2[REDACTED]", redacted)

    return json.dumps(_redact_json(parsed), ensure_ascii=False, indent=2)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: redact_ci_log.py <file>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        return 0

    print(redact_text(path.read_text(encoding="utf-8", errors="replace")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
