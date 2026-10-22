"""The three-legged OAuth flow.

LinkedIn's own client library documents the flow, and this follows it
exactly: an authorization URL, a code exchange, a refresh, and a token
introspection call.

The endpoints, the scope handling and the state parameter all come from the
official client, so nothing here is guesswork.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import (
    ACCESS_TOKEN_URL,
    AUTHORIZE_URL,
    INTROSPECT_URL,
    Config,
    Token,
)

__all__ = [
    "authorization_url",
    "exchange_code",
    "refresh_token",
    "introspect",
    "ensure_token",
]


def authorization_url(config: Config, state: str | None = None) -> str:
    """Build the URL the member visits to grant access.

    Parameters
    ----------
    config:
        The application configuration. ``redirect_uri`` and ``client_id`` must
        be set.
    state:
        An opaque value echoed back on the redirect. Used to detect a
        mismatch between the request and the response.

    Returns
    -------
    str
        The URL to open in a browser.
    """
    if not config.scopes:
        raise ValueError("at least one scope must be requested")

    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
    }
    if state:
        params["state"] = state

    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    """POST a form-encoded body and parse the JSON response."""
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "linkedin-engine/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LinkedIn returned {error.code}: {detail[:400]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"could not reach LinkedIn: {error.reason}") from error


def _token_from_response(payload: dict[str, Any]) -> Token:
    """Build a token from an OAuth response."""
    expires_in = float(payload.get("expires_in", 0))
    return Token(
        access_token=payload.get("access_token", ""),
        refresh_token=payload.get("refresh_token", ""),
        expires_at=time.time() + expires_in if expires_in else 0.0,
        scope=payload.get("scope", ""),
    )


def exchange_code(config: Config, code: str) -> Token:
    """Exchange an authorization code for a token.

    LinkedIn returns a refresh token only when the application is approved
    for the ``w_member_social`` scope, so a missing refresh token is not an
    error here -- it just means the token cannot be refreshed later.
    """
    payload = _post_form(
        ACCESS_TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
    )
    return _token_from_response(payload)


def refresh_token(config: Config, token: Token) -> Token:
    """Exchange a refresh token for a fresh access token."""
    if not token.refresh_token:
        raise RuntimeError(
            "There is no refresh token stored. That usually means the "
            "application has not been approved for the w_member_social "
            "scope, so LinkedIn did not issue one. Re-run the authorisation "
            "flow once the product access is granted."
        )

    payload = _post_form(
        ACCESS_TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
    )
    refreshed = _token_from_response(payload)
    # A refresh response does not always carry a new refresh token; keep the
    # one we have so the next refresh still works.
    if not refreshed.refresh_token:
        refreshed.refresh_token = token.refresh_token
    return refreshed


def introspect(token: Token) -> dict[str, Any]:
    """Ask LinkedIn what a token is good for.

    This is the honest way to find out whether a scope was actually
    granted, rather than finding out when a post comes back 403.
    """
    payload = _post_form(
        INTROSPECT_URL,
        {
            "client_id": token.access_token,
            "client_secret": "",
        },
    )
    return payload


def ensure_token(config: Config, token: Token | None = None) -> Token:
    """Return a usable token, refreshing it if it has expired."""
    if token is None:
        token = Token.load()
    if token is None:
        raise RuntimeError(
            "No token stored. Run `linkedin-engine auth login` to authorise the application first."
        )
    if not token.expired:
        return token
    return refresh_token(config, token)
