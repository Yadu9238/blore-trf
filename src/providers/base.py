"""HTTP helpers shared by all upstream providers."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

TIMEOUT_S = 15
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 2


class ProviderError(RuntimeError):
    """Raised when an upstream call fails after all retries."""


def get_json(url: str, params: dict[str, Any] | None = None) -> dict:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_S)
            # 4xx other than rate limiting will not succeed on retry.
            if response.status_code == 429 or response.status_code >= 500:
                raise ProviderError(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ProviderError, ValueError) as exc:
            last_error = exc
            if attempt == MAX_ATTEMPTS:
                break
            sleep_s = BACKOFF_BASE_S ** attempt
            log.warning("Attempt %s/%s failed (%s); retrying in %ss", attempt, MAX_ATTEMPTS, exc, sleep_s)
            time.sleep(sleep_s)

    raise ProviderError(f"Request to {url} failed after {MAX_ATTEMPTS} attempts: {last_error}")
