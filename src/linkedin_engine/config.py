"""Configuration and credential storage for linkedin-engine.

Credentials never live in the repository. The client id and the redirect URI
are configuration, so they can live next to the token; the token itself is
written with owner-only permissions, outside the working tree, and is never
printed.

Resolution order for every setting:

1. An environment variable.
2. The configuration file in the platform config directory.
3. The built-in default, if there is one.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Where configuration and tokens are kept. Never inside the repository.
CONFIG_DIR = Path(
    os.environ.get("LINKEDIN_ENGINE_HOME", Path.home() / ".config" / "linkedin-engine")
)

CONFIG_PATH = CONFIG_DIR / "config.json"
TOKEN_PATH = CONFIG_DIR / "token.json"

#: LinkedIn's OAuth endpoints.
OAUTH_BASE = "https://www.linkedin.com/oauth/v2"
AUTHORIZE_URL = f"{OAUTH_BASE}/authorization"
ACCESS_TOKEN_URL = f"{OAUTH_BASE}/accessToken"
INTROSPECT_URL = f"{OAUTH_BASE}/introspectAccessToken"

#: LinkedIn's API hosts.
API_BASE = "https://api.linkedin.com/v2"
API_REST_BASE = "https://api.linkedin.com/rest"

#: The scopes the official client documents for member posting.
SCOPE_READ_PROFILE = "r_liteprofile"
SCOPE_WRITE_SOCIAL = "w_member_social"
SCOPE_OIDC = ["openid", "profile", "email"]
SCOPE_POSTING = [SCOPE_READ_PROFILE, SCOPE_WRITE_SOCIAL]

#: The API version the official client pins.
LINKEDIN_VERSION = "202302"
RESTLI_PROTOCOL_VERSION = "2.0.0"


@dataclass
class Config:
    """The application's configuration."""

    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scopes: list[str] = field(default_factory=lambda: list(SCOPE_POSTING))

    @classmethod
    def load(cls) -> Config:
        """Load the configuration, letting the environment win."""
        data: dict[str, Any] = {}
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"{CONFIG_PATH} is not valid JSON: {error}. Fix or delete it."
                ) from error

        return cls(
            client_id=os.environ.get("LINKEDIN_CLIENT_ID", data.get("client_id", "")),
            client_secret=os.environ.get("LINKEDIN_CLIENT_SECRET", data.get("client_secret", "")),
            redirect_uri=os.environ.get("LINKEDIN_REDIRECT_URI", data.get("redirect_uri", "")),
            scopes=list(
                os.environ.get("LINKEDIN_SCOPES", "").split() or data.get("scopes") or SCOPE_POSTING
            ),
        )

    def save(self) -> None:
        """Write the configuration with owner-only permissions."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "scopes": self.scopes,
        }
        _write_private(CONFIG_PATH, json.dumps(payload, indent=2) + "\n")

    def require(self) -> None:
        """Fail with a useful message if the configuration is incomplete."""
        missing = [
            name
            for name in ("client_id", "client_secret", "redirect_uri")
            if not getattr(self, name)
        ]
        if missing:
            raise RuntimeError(
                "Missing configuration: "
                + ", ".join(missing)
                + ". Run `linkedin-engine auth setup` or set the environment "
                "variables LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET and "
                "LINKEDIN_REDIRECT_URI."
            )


@dataclass
class Token:
    """An OAuth token and its metadata."""

    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0
    scope: str = ""

    @property
    def expired(self) -> bool:
        """Whether the access token has expired.

        A minute of slack avoids a race with the clock at the boundary.
        """
        import time

        return self.expires_at <= time.time() + 60

    @classmethod
    def load(cls) -> Token | None:
        """Read the stored token, or ``None`` if there is not one."""
        if not TOKEN_PATH.exists():
            return None
        try:
            data = json.loads(TOKEN_PATH.read_text())
        except json.JSONDecodeError:
            return None
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=float(data.get("expires_at", 0)),
            scope=data.get("scope", ""),
        )

    def save(self) -> None:
        """Write the token with owner-only permissions."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scope": self.scope,
        }
        _write_private(TOKEN_PATH, json.dumps(payload, indent=2) + "\n")

    def __repr__(self) -> str:
        """Never leak the token in a repr, a log line or a traceback."""
        return f"Token(expires_at={self.expires_at!r}, scope={self.scope!r})"


def _write_private(path: Path, content: str) -> None:
    """Write a file that only the owner can read."""
    path.write_text(content)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
