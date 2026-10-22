"""Tests for the profile management."""

from __future__ import annotations

import json
from pathlib import Path

from linkedin_engine import profile as profile_module

REPO_ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ profile


class _FakeClient:
    """A client that records what it was asked to write."""

    def __init__(self) -> None:
        self.sent = False

    def update_profile(self, fields):
        self.sent = True
        return {"ok": True}


def test_the_shipped_profile_file_is_valid() -> None:
    data = json.loads((REPO_ROOT / "content" / "profile.json").read_text())
    written = profile_module.Profile.from_dict(data)

    assert written.headline
    assert written.about
    assert len(written.experience) >= 4
    assert written.featured


def test_the_profile_renders_every_section() -> None:
    written = profile_module.Profile.from_dict(
        json.loads((REPO_ROOT / "content" / "profile.json").read_text())
    )
    rendered = profile_module.render_profile(written)

    assert "## Headline" in rendered
    assert "## About" in rendered
    assert "## Experience" in rendered
    assert "## Featured" in rendered
    assert "## Skills" in rendered


def test_the_diff_reports_a_changed_headline() -> None:
    written = profile_module.Profile(headline="New headline")
    differences = profile_module.diff_profile({"headline": "Old headline"}, written)
    assert differences
    assert "headline" in differences[0]


def test_the_diff_is_quiet_when_they_agree() -> None:
    written = profile_module.Profile(headline="Same", about="Also same")
    live = {"headline": "Same", "about": "Also same"}
    assert profile_module.diff_profile(live, written) == []


def test_applying_a_profile_is_a_dry_run_by_default() -> None:
    class FakeClient:
        def __init__(self):
            self.sent = False

        def update_profile(self, fields):
            self.sent = True
            return {"ok": True}

    client = FakeClient()
    written = profile_module.Profile(headline="New", about="About", location="Kanpur")
    result = profile_module.apply_profile(client, written)

    assert result["sent"] is False
    assert client.sent is False
    assert result["changed"]["headline"] == "New"


def test_the_links_section_renders() -> None:
    written = profile_module.Profile(
        websites=[
            {"label": "YouTube", "url": "https://www.youtube.com/@theizgiv"},
            {"url": "https://example.com/only-a-url"},
        ]
    )
    rendered = profile_module.render_profile(written)
    assert "## Links" in rendered
    assert "https://www.youtube.com/@theizgiv" in rendered
    assert "https://example.com/only-a-url" in rendered


def test_the_shipped_profile_lists_the_izgiv_channels() -> None:
    written = profile_module.load_profile(REPO_ROOT / "content" / "profile.json")
    urls = " ".join(item.get("url", "") for item in written.websites)
    assert "youtube.com/@theizgiv" in urls
    assert "instagram.com/theizgiv" in urls
    assert "facebook.com/theizgiv" in urls


def test_the_links_are_not_pushed_to_the_api() -> None:
    """The API does not accept a websites field, so it is never sent."""
    written = profile_module.Profile(
        headline="New",
        websites=[{"label": "YouTube", "url": "https://www.youtube.com/@theizgiv"}],
    )
    result = profile_module.apply_profile(_FakeClient(), written)
    assert "websites" not in result["changed"]


def test_the_content_suite_points_at_the_channel_not_a_repository() -> None:
    """The product's public face is the channel it publishes to."""
    written = profile_module.load_profile(REPO_ROOT / "content" / "profile.json")
    entry = next(
        e for e in written.experience if e.organisation == "Cross-Platform Content Automation Suite"
    )
    assert "youtube.com/@theizgiv" in entry.url
    assert "github.com" not in entry.url
    assert any("autonomous" in h.lower() for h in entry.highlights)


def test_the_izgiv_entry_reveals_the_autoposter() -> None:
    written = profile_module.load_profile(REPO_ROOT / "content" / "profile.json")
    entry = next(e for e in written.experience if e.organisation == "IZGIV")
    assert any("TheIZGIV" in h for h in entry.highlights)
