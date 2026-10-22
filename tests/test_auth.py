"""Tests for the OAuth flow and the request shaping.

The endpoints and headers here are the ones the official client documents,
so the tests check the shape rather than the network.
"""

from __future__ import annotations

import json
import urllib.parse

import pytest

from linkedin_engine import auth
from linkedin_engine.client import LinkedInClient, LinkedInError
from linkedin_engine.config import Config, Token


def test_the_authorisation_url_has_the_right_shape() -> None:
    config = Config(
        client_id="abc123",
        client_secret="secret",
        redirect_uri="https://example.com/callback",
        scopes=["r_liteprofile", "w_member_social"],
    )
    url = auth.authorization_url(config, state="xyz")

    assert url.startswith("https://www.linkedin.com/oauth/v2/authorization?")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["abc123"]
    assert query["redirect_uri"] == ["https://example.com/callback"]
    assert query["scope"] == ["r_liteprofile w_member_social"]
    assert query["state"] == ["xyz"]


def test_the_authorisation_url_omits_an_empty_state() -> None:
    config = Config(client_id="a", client_secret="b", redirect_uri="c")
    url = auth.authorization_url(config)
    assert "state=" not in url


def test_the_authorisation_url_needs_a_scope() -> None:
    config = Config(client_id="a", client_secret="b", redirect_uri="c", scopes=[])
    with pytest.raises(ValueError):
        auth.authorization_url(config)


def test_a_token_never_prints_itself() -> None:
    token = Token(access_token="super-secret-value")
    assert "super-secret-value" not in repr(token)


def test_a_token_is_expiring_before_it_expires() -> None:
    import time

    assert Token(access_token="x", expires_at=time.time() + 30).expired
    assert not Token(access_token="x", expires_at=time.time() + 3600).expired


def test_the_client_sends_the_restli_headers(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        headers = {"x-restli-id": "urn:li:share:123"}

        def read(self) -> bytes:
            return b'{"id": "urn:li:person:42"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = LinkedInClient("token-abc")
    result = client.create_post("hello", "urn:li:person:42")

    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["authorization"] == "Bearer token-abc"
    assert headers["x-restli-protocol-version"] == "2.0.0"
    assert headers["x-restli-method"] == "CREATE"
    assert headers["linkedin-version"] == "202302"

    body = json.loads(captured["body"])
    assert body["author"] == "urn:li:person:42"
    assert body["lifecycleState"] == "PUBLISHED"
    assert body["commentary"] == "hello"
    assert "PUBLIC" in body["visibility"]

    assert result["id"] == "urn:li:share:123"


def test_the_client_asks_for_the_member_id(monkeypatch) -> None:
    class FakeResponse:
        headers: dict = {}

        def read(self) -> bytes:
            return b'{"id": "42"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse())

    client = LinkedInClient("token")
    assert client.person_urn() == "urn:li:person:42"


def test_an_api_error_carries_linkedin_own_message(monkeypatch) -> None:
    import urllib.error

    class FakeError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("https://api.linkedin.com/v2/me", 403, "Forbidden", {}, None)

        def read(self) -> bytes:
            return b'{"message": "scope not granted"}'

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(FakeError())
    )

    client = LinkedInClient("token")
    with pytest.raises(LinkedInError) as caught:
        client.get_me()
    assert "scope not granted" in str(caught.value)
    assert caught.value.status == 403
