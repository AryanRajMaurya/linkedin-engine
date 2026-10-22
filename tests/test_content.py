"""Tests for draft generation and the publish gate."""

from __future__ import annotations

import pytest

from linkedin_engine import content
from linkedin_engine.publish import publish
from linkedin_engine.quality import Level

# ------------------------------------------------------------------ content


def test_a_draft_mentions_the_artefact_and_links_to_it() -> None:
    artefact = content.Artefact(
        kind="pr",
        title="Fix the streaming proxy",
        url="https://github.com/example/project/pull/12",
        repo="example/project",
        detail="The response is piped instead of buffered, which keeps it inside the CPU budget.",
        number=12,
    )
    draft = content.render_draft(artefact)

    assert "example/project" in draft
    assert "Fix the streaming proxy" in draft
    assert "https://github.com/example/project/pull/12" in draft


def test_a_release_draft_announces_the_tag() -> None:
    artefact = content.Artefact(
        kind="release",
        title="shipfree v0.2.0",
        url="https://github.com/example/project/releases/tag/v0.2.0",
        repo="example/project",
        detail="Adds the planner.",
    )
    draft = content.render_draft(artefact)
    assert "v0.2.0" in draft
    assert "is out" in draft


def test_the_first_paragraph_skips_templates_and_checklists() -> None:
    body = (
        "### Description\n\n"
        "- [x] I have read the contributing guide\n\n"
        "The real explanation of what changed and why.\n\n"
        "More text."
    )
    assert content._first_paragraph(body) == "The real explanation of what changed and why."


def test_the_first_paragraph_handles_a_body_with_nothing_in_it() -> None:
    assert content._first_paragraph("") == ""


def test_slugs_are_safe_for_filenames() -> None:
    assert content.slugify("Fix / the thing!") == "fix-the-thing"
    assert "/" not in content.slugify("a/b/c")


# ------------------------------------------------------------------ publish


class FakeClient:
    """A client that records what it was asked to publish."""

    def __init__(self):
        self.posted: list[str] = []

    def person_urn(self) -> str:
        return "urn:li:person:42"

    def create_post(self, text, author_urn, visibility="PUBLIC", extra=None):
        self.posted.append(text)
        return {"id": "urn:li:share:1"}


def test_a_draft_that_fails_the_gate_is_not_published() -> None:
    client = FakeClient()
    result = publish(client, "I'm thrilled to announce! https://example.com " + "x" * 300)

    assert result.published is False
    assert client.posted == []


def test_publishing_is_a_dry_run_by_default() -> None:
    client = FakeClient()
    good = (
        "I built a thing and here is what it does. "
        + ("More detail. " * 30)
        + "https://example.com/x"
    )
    result = publish(client, good, dry_run=True)

    assert result.published is False
    assert "dry run" in result.reason
    assert client.posted == []


def test_a_good_draft_publishes_when_asked() -> None:
    client = FakeClient()
    good = (
        "I built a thing and here is what it does. "
        + ("More detail. " * 30)
        + "https://example.com/x"
    )
    result = publish(client, good, dry_run=False)

    assert result.published is True
    assert result.post_id == "urn:li:share:1"
    assert len(client.posted) == 1


def test_warnings_do_not_block_publishing() -> None:
    client = FakeClient()
    good = (
        "I built a thing and here is what it does. "
        + ("More detail. " * 30)
        + "https://example.com/x"
    )
    result = publish(client, good, dry_run=False)

    assert not [f for f in result.findings if f.level is Level.ERROR]


def test_fetch_artefacts_surfaces_a_failure(monkeypatch) -> None:
    """A rate limit must not look like a quiet week.

    The GitHub API refuses unauthenticated requests over a shared address,
    and returning an empty list in that case makes the tool look like there
    was simply no activity. The caller has to be told which it was.
    """

    def boom(*args, **kwargs):
        raise RuntimeError("GitHub refused the request (403)")

    monkeypatch.setattr(content, "_get_json", boom)

    with pytest.raises(RuntimeError, match="403"):
        content.fetch_artefacts(username="someone", since="2026-01-01")
