from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from weather_agent.weather_client import (
    WeatherDataError,
    _unwrap_geocode_results,
    _unwrap_payload,
)

logger = logging.getLogger(__name__)


def redact_helper_output(output: str, limit: int = 6000) -> str:
    redacted = re.sub(r"(api\.telegram\.org/bot)[^/\s\"']+", r"\1<redacted>", output)
    redacted = re.sub(r"(code=)[^&\s\"']+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", redacted)
    redacted = re.sub(
        r"(?i)\b(access[_-]?key|private[_-]?key|secret|seed(?:[_-]?phrase)?|token|wallet[_-]?store|account)"
        r"([\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+",
        r"\1\2<redacted>",
        redacted,
    )
    redacted = re.sub(r"0x[a-fA-F0-9]{40}", "<redacted-address>", redacted)
    if len(redacted) > limit:
        return f"{redacted[:limit]}...<truncated>"
    return redacted


def _resolve_executable(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    if os.path.isabs(name):
        return name
    for candidate in ("/opt/homebrew/bin/npm", "/usr/local/bin/npm"):
        if name == "npm" and Path(candidate).exists():
            return candidate
    return name


@dataclass(frozen=True)
class MppxWeatherClient:
    helper_dir: str
    timeout_seconds: int
    npm_bin: str = "npm"

    def get_hanoi_weather(self, city_query: str, units: str, lang: str) -> dict[str, Any]:
        helper_path = Path(self.helper_dir)
        if not helper_path.exists():
            raise WeatherDataError(f"MPP helper directory does not exist: {helper_path}")

        env = os.environ.copy()
        npm_bin = _resolve_executable(self.npm_bin)
        npm_parent = str(Path(npm_bin).parent)
        env["PATH"] = f"{npm_parent}{os.pathsep}{env.get('PATH', '')}"
        env.update(
            {
                "WEATHER_CITY_QUERY": city_query,
                "WEATHER_UNITS": units,
                "WEATHER_LANG": lang,
            }
        )

        logger.info(
            "Calling Node mppx OpenWeather helper helper_dir=%s city=%s units=%s lang=%s",
            helper_path,
            city_query,
            units,
            lang,
        )
        try:
            completed = subprocess.run(
                [npm_bin, "run", "--silent", "weather:once"],
                cwd=helper_path,
                env=env,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise WeatherDataError(
                f"Unable to run {self.npm_bin!r}. Install Node.js/npm and run npm install in {helper_path}."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise WeatherDataError(
                f"Node mppx weather helper timed out after {self.timeout_seconds} seconds"
            ) from exc

        if completed.stderr:
            logger.info("Node mppx helper stderr=%s", redact_helper_output(completed.stderr.strip()))

        if completed.returncode != 0:
            safe_stderr = redact_helper_output(completed.stderr.strip())
            raise WeatherDataError(
                "Node mppx weather helper failed "
                f"exit_code={completed.returncode} stderr={safe_stderr!r}"
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            safe_stdout = redact_helper_output(completed.stdout.strip())
            raise WeatherDataError(
                f"Node mppx weather helper did not return clean JSON stdout={safe_stdout!r}"
            ) from exc

        if not isinstance(payload, dict) or payload.get("ok") is not True:
            safe_payload = redact_helper_output(json.dumps(payload, ensure_ascii=False, default=str))
            raise WeatherDataError(f"Node mppx weather helper returned an error payload={safe_payload}")

        run_payload = payload.get("run")
        if not isinstance(run_payload, dict):
            raise WeatherDataError("Node mppx weather helper response did not include run data")

        geocode_body = run_payload.get("geocode")
        weather_body = run_payload.get("currentWeather")

        locations = _unwrap_geocode_results(geocode_body)
        if not locations:
            raise WeatherDataError("Node mppx helper returned no geocode result")
        location = locations[0]
        if not isinstance(location, dict):
            raise WeatherDataError("Node mppx helper geocode result was not an object")

        weather = _unwrap_payload(weather_body)
        if not isinstance(weather, dict):
            raise WeatherDataError("Node mppx helper current weather was not an object")

        weather["_location"] = location
        logger.info("Node mppx OpenWeather helper completed")
        return weather
