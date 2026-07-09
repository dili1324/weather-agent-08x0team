from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)


class TempoRequestError(RuntimeError):
    """Raised when Tempo CLI cannot complete an MPP request."""


def _redact_tempo_output(output: str, limit: int = 4000) -> str:
    redacted = re.sub(r"(api\.telegram\.org/bot)[^/\s\"']+", r"\1<redacted>", output)
    redacted = re.sub(r"(code=)[^&\s\"']+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", redacted)
    redacted = re.sub(
        r"(?i)\b(access[_-]?key|private[_-]?key|secret|seed(?:[_-]?phrase)?|token|wallet[_-]?store)"
        r"([\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+",
        r"\1\2<redacted>",
        redacted,
    )
    redacted = re.sub(r"0x[a-fA-F0-9]{40}", "<redacted-address>", redacted)
    if len(redacted) > limit:
        return f"{redacted[:limit]}...<truncated>"
    return redacted


def _extract_json_from_output(output: str) -> Any:
    stripped = output.strip()
    if not stripped:
        return {}

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end > object_start:
        try:
            return json.loads(stripped[object_start : object_end + 1])
        except json.JSONDecodeError:
            pass

    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if array_start != -1 and array_end > array_start:
        try:
            return json.loads(stripped[array_start : array_end + 1])
        except json.JSONDecodeError:
            pass

    # Tempo CLI may print helper lines before the actual response payload.
    for line in reversed(stripped.splitlines()):
        candidate = line.strip()
        if not candidate or candidate[0] not in "[{":
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return stripped


def _is_wallet_ready(output: str) -> bool:
    parsed = _extract_json_from_output(output)
    if isinstance(parsed, dict):
        return parsed.get("ready") is True

    normalized = output.replace(" ", "").lower()
    return "ready:true" in normalized or "ready=true" in normalized or '"ready":true' in normalized


@dataclass(frozen=True)
class TempoRequestClient:
    tempo_bin: str = "tempo"
    max_spend_usd: str = "0.05"

    def check_wallet_ready(self) -> None:
        command = [self.tempo_bin, "wallet", "--format", "json", "whoami"]
        start = perf_counter()
        logger.info("Checking Tempo Wallet readiness with `%s wallet whoami`", self.tempo_bin)
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        elapsed_ms = (perf_counter() - start) * 1000
        logger.info("Tempo wallet raw stdout=%s", _redact_tempo_output(result.stdout.strip()))
        if result.stderr.strip():
            logger.info("Tempo wallet raw stderr=%s", _redact_tempo_output(result.stderr.strip()))
        if result.returncode != 0:
            logger.error("Tempo Wallet readiness check failed duration_ms=%.2f", elapsed_ms)
            raise TempoRequestError(
                "Tempo Wallet is not ready. Run `tempo wallet login` and ensure the "
                "runner has a valid access key before scheduled execution."
            )
        if not _is_wallet_ready(result.stdout):
            logger.error("Tempo wallet readiness output did not contain ready=true")
            raise TempoRequestError(
                "Tempo Wallet is not ready. `tempo wallet whoami` did not report ready: true."
            )
        logger.info("Tempo Wallet readiness check completed duration_ms=%.2f", elapsed_ms)

    def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        command = [
            self.tempo_bin,
            "request",
            "-t",
            "--max-spend",
            self.max_spend_usd,
            "-X",
            "POST",
            "--json",
            json.dumps(payload, separators=(",", ":")),
            url,
        ]
        start = perf_counter()
        logger.info(
            "Calling MPP endpoint via Tempo CLI url=%s max_spend_usd=%s",
            url,
            self.max_spend_usd,
        )
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        elapsed_ms = (perf_counter() - start) * 1000
        if result.returncode != 0:
            logger.error("Tempo request failed url=%s duration_ms=%.2f", url, elapsed_ms)
            safe_output = _redact_tempo_output(result.stderr.strip() or result.stdout.strip())
            raise TempoRequestError(
                f"Tempo request failed for {url}: {safe_output}"
            )
        logger.info("Tempo request completed url=%s duration_ms=%.2f", url, elapsed_ms)

        output = result.stdout.strip()
        logger.info("Tempo raw stdout url=%s output=%s", url, _redact_tempo_output(output))
        if not output:
            return {}

        parsed = _extract_json_from_output(output)
        if isinstance(parsed, str):
            logger.debug("Tempo response was not parseable JSON; returning text output")
        return parsed
