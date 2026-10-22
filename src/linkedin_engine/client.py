"""A small Rest.li client for the member APIs.

LinkedIn's APIs are built on Rest.li, which is a protocol layered over
ordinary HTTP: the method is a header rather than a verb, and responses
carry their identity in a header. The official client library exists, but
it is a beta and it pulls in a dependency tree; this module speaks the
same protocol in a few hundred lines of standard library, so the tool has
no runtime dependencies and nothing to keep up to date.

Every path, header and body shape here comes from the official client:
``linkedin-developers/linkedin-api-python-client`` and
``linkedin-developers/linkedin-api-js-client``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import (
    API_BASE,
    API_REST_BASE,
    LINKEDIN_VERSION,
    RESTLI_PROTOCOL_VERSION,
)

__all__ = ["LinkedInError", "LinkedInClient"]


class LinkedInError(RuntimeError):
    """A request to LinkedIn failed.

    The API's own message is kept, because LinkedIn is specific about what
    went wrong and the difference between "scope not granted" and "resource
    not found" matters.
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(f"LinkedIn returned {status}: {message}")
        self.status = status
        self.body = body


class LinkedInClient:
    """A client for the member endpoints linkedin-engine uses."""

    def __init__(self, access_token: str, version: str = LINKEDIN_VERSION) -> None:
        self.access_token = access_token
        self.version = version

    # ------------------------------------------------------------- plumbing

    #: Rest.li carries the method in a header, not in the HTTP verb. This
    #: maps the Rest.li method onto the HTTP verb that carries it.
    HTTP_VERBS = {
        "GET": "GET",
        "FINDER": "GET",
        "GET_ALL": "GET",
        "CREATE": "POST",
        "UPDATE": "PATCH",
        "PARTIAL_UPDATE": "PATCH",
        "DELETE": "DELETE",
    }

    def _headers(self, method: str) -> dict[str, str]:
        """The headers every Rest.li request needs."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-RestLi-Protocol-Version": RESTLI_PROTOCOL_VERSION,
            "X-RestLi-Method": method,
            "LinkedIn-Version": self.version,
            "User-Agent": "linkedin-engine/0.1",
        }

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a Rest.li request and return the parsed response.

        ``method`` is the Rest.li method, such as ``CREATE``. The HTTP verb
        is derived from it.
        """
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urllib.parse.urlencode(params)}"

        data = json.dumps(payload).encode() if payload is not None else None
        verb = self.HTTP_VERBS.get(method, "POST")
        request = urllib.request.Request(url, data=data, method=verb)  # noqa: S310
        # Assigned rather than passed to the constructor: urllib capitalises
        # header names, which would turn "X-RestLi-Protocol-Version" into
        # "X-restli-protocol-version". Header names are case-insensitive so
        # it works either way, but the exact documented spelling is clearer
        # in a trace.
        request.headers = self._headers(method)  # type: ignore[assignment]

        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                body = response.read().decode("utf-8", errors="replace")
                entity_id = response.headers.get("x-restli-id", "")
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            raise LinkedInError(error.code, _message_from(raw), raw) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"could not reach LinkedIn: {error.reason}") from error

        result: dict[str, Any] = {}
        if body:
            try:
                result = json.loads(body)
            except json.JSONDecodeError:
                result = {"raw": body}
        if entity_id:
            result["id"] = entity_id
        return result

    # -------------------------------------------------------------- profile

    def get_me(self, projection: str | None = None, fields: str | None = None) -> dict[str, Any]:
        """Fetch the authenticated member.

        Parameters
        ----------
        projection:
            A Rest.li projection, for example
            ``(id,firstName,lastName,headline)``.
        fields:
            A comma separated field list, an alternative to a projection.
        """
        params: dict[str, Any] = {}
        if projection:
            params["projection"] = projection
        if fields:
            params["fields"] = fields
        return self._request("GET", f"{API_BASE}/me", params=params or None)

    def update_profile(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Update the member's profile fields.

        Which fields the API accepts depends on the products the application
        has been granted. An unsupported field comes back as a 403 with
        LinkedIn's own explanation, which is passed straight through.
        """
        return self._request("UPDATE", f"{API_BASE}/me", payload=fields)

    # ---------------------------------------------------------------- posts

    def create_post(
        self,
        text: str,
        author_urn: str,
        visibility: str = "PUBLIC",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish a text post on the member's feed.

        Uses the newer versioned ``/posts`` endpoint, which the official
        client documents alongside the legacy ``/ugcPosts``.
        """
        payload: dict[str, Any] = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "visibility": "com.linkedin.ugc.MemberNetworkVisibility:" + visibility,
            "commentary": text,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
        }
        if extra:
            payload.update(extra)
        return self._request("CREATE", f"{API_REST_BASE}/posts", payload=payload)

    def create_ugc_post(
        self, text: str, author_urn: str, visibility: str = "PUBLIC"
    ) -> dict[str, Any]:
        """Publish a text post using the legacy ``/ugcPosts`` endpoint.

        The official client still ships this example, and it is the endpoint
        that works for the widest range of granted products.
        """
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
        }
        return self._request("CREATE", f"{API_BASE}/ugcPosts", payload=payload)

    def person_urn(self) -> str:
        """The URN of the authenticated member, for use as a post author."""
        me = self.get_me(fields="id")
        member_id = me.get("id")
        if not member_id:
            raise RuntimeError("LinkedIn did not return a member id for /me")
        return f"urn:li:person:{member_id}"


def _message_from(raw: str) -> str:
    """Pull a readable message out of a LinkedIn error body."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:300] or "no body"

    if isinstance(payload, dict):
        message = payload.get("message")
        if message:
            return str(message)
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    return raw[:300] or "no body"
