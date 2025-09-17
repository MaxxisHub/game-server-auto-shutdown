"""AMP REST API client."""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util import retry

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5


class AMPAPIError(RuntimeError):
    """Raised when the AMP API returns an unexpected response."""


class AMPClient:
    """Thin AMP REST client with retry and timeout support."""

    INSTANCES_ENDPOINT = "/API/Core/GetInstances"
    PLAYER_COUNTS_ENDPOINT = "/API/Core/GetPlayerCounts"

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        verify_ssl: bool = True,
        session: Optional[Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = session or requests.Session()
        self._configure_session()

    def _configure_session(self) -> None:
        retries = retry.Retry(
            total=MAX_RETRIES,
            read=MAX_RETRIES,
            connect=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=(500, 502, 503, 504),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        if self.api_key:
            self.session.headers.update({"Authorization": f"AMP {self.api_key}"})
        self.session.headers.setdefault("Accept", "application/json")

    def _request(self, method: str, path: str, **kwargs) -> Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify_ssl)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:  # pragma: no cover - network failure path
            LOGGER.error("Failed to reach AMP API: %s", exc)
            raise AMPAPIError(str(exc)) from exc
        if response.status_code >= 400:
            LOGGER.error("AMP API error (%s): %s", response.status_code, response.text)
            raise AMPAPIError(f"{response.status_code}: {response.text}")
        return response

    def test_connection(self) -> bool:
        try:
            instances = self.list_instances()
            return isinstance(instances, list)
        except AMPAPIError:
            return False

    def list_instances(self) -> List[Dict[str, object]]:
        response = self._request("GET", self.INSTANCES_ENDPOINT)
        payload = response.json()
        instances = payload.get("instances") if isinstance(payload, dict) else payload
        if not isinstance(instances, list):
            raise AMPAPIError("Unexpected response structure when listing instances")
        normalised = []
        for item in instances:
            if isinstance(item, dict):
                normalised.append(item)
            elif isinstance(item, str):
                normalised.append({"name": item, "id": item})
        return normalised

    def get_player_counts(self, instances: Iterable[str]) -> Dict[str, int]:
        instance_list = list(instances)
        if not instance_list:
            return {}
        response = self._request(
            "POST",
            self.PLAYER_COUNTS_ENDPOINT,
            json={"instances": instance_list},
        )
        data = response.json()
        if not isinstance(data, dict):
            raise AMPAPIError("Unexpected response when reading player counts")
        results: Dict[str, int] = {}
        for name in instance_list:
            value = data.get(name)
            if isinstance(value, dict) and "players" in value:
                value = value.get("players")
            try:
                results[name] = int(value)
            except (TypeError, ValueError):
                LOGGER.debug("Defaulting missing player count for %s to 0", name)
                results[name] = 0
        return results
