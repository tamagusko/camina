"""Shared httpx client with retries, backoff, and Bearer auth.

Single place to configure TLS, connection pooling, and the retry policy.
Retries are manually driven so we can honour ``Retry-After`` on 429 and
avoid retrying on unrecoverable 4xx (which would just burn bandwidth).
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

import httpx


logger = logging.getLogger(__name__)


RETRIABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

_LOCALHOST_HOSTS = {"localhost", "127.0.0.1"}


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    jitter: float = 0.2


class HttpClient:
    """Thin wrapper around httpx.Client with the project's retry policy.

    Args:
        base_url: Absolute URL prefix for all requests (e.g. ``https://…/api``).
        token: Bearer token sent in the ``Authorization`` header.
        timeout_s: Per-request total timeout.
        retry: Retry policy.
        transport: Optional httpx transport — useful for tests
            (``httpx.MockTransport``) to avoid real network calls.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout_s: float = 10.0,
        retry: Optional[RetryPolicy] = None,
        transport: Optional[httpx.BaseTransport] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._validate_scheme(base_url)
        self._retry = retry or RetryPolicy()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "camina-sensor/0.2",
            },
            timeout=timeout_s,
            transport=transport,
        )

    # ---------- Public API ----------

    def request(
        self,
        method: str,
        path: str,
        *,
        content: Optional[bytes] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Send a request with the project's retry policy.

        Raises:
            httpx.HTTPStatusError: after retries are exhausted on 5xx/429.
            httpx.TransportError: after retries are exhausted on network errors.
            httpx.HTTPStatusError: immediately (no retry) on 4xx other than 408/429.
        """
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        last_exc: Optional[BaseException] = None
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                response = self._client.request(
                    method, path, content=content, headers=headers or None
                )
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError,
                    httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                delay = self._backoff(attempt)
                logger.warning(
                    "HTTP %s %s failed (%s); attempt %d/%d; sleeping %.1fs",
                    method, path, exc.__class__.__name__,
                    attempt, self._retry.max_attempts, delay,
                )
                if attempt == self._retry.max_attempts:
                    raise
                time.sleep(delay)
                continue

            if response.status_code < 400:
                return response

            if response.status_code in RETRIABLE_STATUS:
                if attempt == self._retry.max_attempts:
                    response.raise_for_status()
                delay = self._delay_for_response(response, attempt)
                logger.warning(
                    "HTTP %s %s -> %d; attempt %d/%d; sleeping %.1fs",
                    method, path, response.status_code,
                    attempt, self._retry.max_attempts, delay,
                )
                time.sleep(delay)
                continue

            # 4xx non-retriable: fail fast.
            response.raise_for_status()

        # Should be unreachable, but satisfies the type checker.
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("HttpClient.request exited retry loop without response")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ---------- Internal ----------

    @staticmethod
    def _validate_scheme(base_url: str) -> None:
        """Reject non-HTTPS base URLs, except plain HTTP to localhost/127.0.0.1
        (used by local dev servers and tests)."""
        parts = urlsplit(base_url)
        if parts.scheme == "https":
            return
        if parts.scheme == "http" and parts.hostname in _LOCALHOST_HOSTS:
            return
        raise ValueError(
            f"HttpClient base_url must use https:// (got {base_url!r}); "
            "http:// is only allowed for localhost/127.0.0.1"
        )

    def _backoff(self, attempt: int) -> float:
        base = min(
            self._retry.max_delay_s,
            self._retry.base_delay_s * (2 ** (attempt - 1)),
        )
        return base * (1 + random.uniform(-self._retry.jitter, self._retry.jitter))

    def _delay_for_response(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(self._retry.max_delay_s, float(retry_after))
            except ValueError:
                # HTTP-date form — not supporting that for now.
                pass
        return self._backoff(attempt)


__all__ = ["HttpClient", "RetryPolicy", "RETRIABLE_STATUS"]
