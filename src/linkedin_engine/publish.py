"""Publishing, with the quality gate in front of it.

Publishing is the one irreversible thing this tool does. A post that goes
out is visible to everyone, and it cannot be un-posted, only edited. So
the sequence is always the same: check the draft, refuse it if it fails,
and only then send it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .client import LinkedInClient
from .quality import Level, check_post

__all__ = ["PublishResult", "publish"]


@dataclass
class PublishResult:
    """What happened when a draft was published."""

    published: bool
    reason: str = ""
    post_id: str = ""
    findings: list = field(default_factory=list)

    def __str__(self) -> str:
        if self.published:
            return f"published {self.post_id}"
        return f"not published: {self.reason}"


def publish(
    client: LinkedInClient,
    text: str,
    dry_run: bool = True,
    visibility: str = "PUBLIC",
    require_link: bool = True,
    author_urn: str | None = None,
) -> PublishResult:
    """Publish a draft, if it passes the quality gate.

    Parameters
    ----------
    client:
        The client to publish through.
    text:
        The body of the post.
    dry_run:
        When true, run every check and stop before sending. This is the
        default everywhere it is used.
    visibility:
        ``PUBLIC``, ``CONNECTIONS`` or ``PRIVATE``.
    require_link:
        Whether the post must contain a link.
    author_urn:
        The member URN. Resolved from ``/me`` when not given.
    """
    findings = check_post(text, require_link=require_link)
    errors = [f for f in findings if f.level is Level.ERROR]

    if errors:
        reasons = "; ".join(f.message for f in errors)
        return PublishResult(published=False, reason=reasons, findings=findings)

    if dry_run:
        return PublishResult(
            published=False,
            reason="dry run; pass --publish to send it",
            findings=findings,
        )

    urn = author_urn or client.person_urn()
    try:
        response = client.create_post(text, urn, visibility=visibility)
    except Exception as error:  # noqa: BLE001 - the API's own message matters
        # Fall back to the legacy endpoint, which is the one that works for
        # the widest range of granted products.
        if "ugcPosts" not in str(error):
            return PublishResult(published=False, reason=str(error), findings=findings)
        response = client.create_ugc_post(text, urn, visibility=visibility)

    post_id = ""
    if isinstance(response, dict):
        post_id = str(response.get("id") or response.get("entity_id") or "")

    return PublishResult(published=True, post_id=post_id, findings=findings)
