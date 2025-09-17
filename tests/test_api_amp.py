from unittest.mock import Mock

import pytest

from amp_autoshutdown.api_amp import AMPAPIError, AMPClient


def build_client(response):
    session = Mock()
    session.request.return_value = response
    return AMPClient("https://example.com", "secret", session=session, verify_ssl=False)


def test_list_instances_normalises_string_entries():
    response = Mock()
    response.status_code = 200
    response.json.return_value = ["mc", {"id": "satisfactory", "name": "Satisfactory"}]
    client = build_client(response)
    instances = client.list_instances()
    assert instances[0]["id"] == "mc"
    assert instances[0]["name"] == "mc"
    assert any(item.get("id") == "satisfactory" for item in instances)


def test_get_player_counts_defaults_missing_to_zero(monkeypatch):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "mc": {"players": "2"},
        "satisfactory": 1,
    }
    client = build_client(response)
    counts = client.get_player_counts(["mc", "satisfactory", "valheim"])
    assert counts["mc"] == 2
    assert counts["satisfactory"] == 1
    assert counts["valheim"] == 0


def test_request_raises_on_error_status():
    response = Mock()
    response.status_code = 503
    response.text = "Service Unavailable"
    session = Mock()
    session.request.return_value = response
    client = AMPClient("https://example.com", "secret", session=session)
    with pytest.raises(AMPAPIError):
        client._request("GET", "/broken")
