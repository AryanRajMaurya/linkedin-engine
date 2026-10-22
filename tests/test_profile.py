"""Tests for the profile management."""

from __future__ import annotations

import json
from pathlib import Path

from linkedin_engine import profile as profile_module

REPO_ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ profile


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
