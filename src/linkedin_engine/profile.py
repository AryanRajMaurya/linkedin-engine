"""Managing the member profile.

A profile is the one page on LinkedIn that a recruiter, a client and a
collaborator all read, and it is usually the least considered. This module
keeps the profile text in one file, renders it, checks the live profile
against it, and applies the fields the API will accept.

The live profile is read through ``GET /me``. The written profile is
rendered from a file, so the source of truth is versionable and reviewable
rather than living in a web form.

Which fields the API accepts depends on the products the application has
been granted. A field the API refuses comes back as a 403 with LinkedIn's
own explanation, which is passed straight through rather than swallowed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Profile",
    "Experience",
    "load_profile",
    "render_profile",
    "diff_profile",
    "apply_profile",
]


@dataclass
class Experience:
    """One entry on the experience list."""

    title: str
    organisation: str
    period: str = ""
    highlights: list[str] = field(default_factory=list)
    url: str = ""

    def to_text(self) -> str:
        """The entry as a block of text."""
        lines = [f"{self.title} — {self.organisation}"]
        if self.period:
            lines.append(self.period)
        lines.append("")
        lines.extend(f"• {highlight}" for highlight in self.highlights)
        if self.url:
            lines.append("")
            lines.append(self.url)
        return "\n".join(lines)


@dataclass
class Profile:
    """The whole written profile."""

    headline: str = ""
    about: str = ""
    location: str = ""
    experience: list[Experience] = field(default_factory=list)
    featured: list[dict[str, str]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    websites: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Build a profile from a mapping."""
        return cls(
            headline=data.get("headline", ""),
            about=data.get("about", ""),
            location=data.get("location", ""),
            experience=[
                Experience(
                    title=item.get("title", ""),
                    organisation=item.get("organisation", ""),
                    period=item.get("period", ""),
                    highlights=list(item.get("highlights", [])),
                    url=item.get("url", ""),
                )
                for item in data.get("experience", [])
            ],
            featured=list(data.get("featured", [])),
            skills=list(data.get("skills", [])),
            websites=list(data.get("websites", [])),
        )


def _read_document(path: Path) -> dict[str, Any]:
    """Read a profile document, JSON natively and YAML when PyYAML is there."""
    text = path.read_text()

    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as error:  # pragma: no cover - depends on the environment
            raise RuntimeError(
                "Reading YAML needs PyYAML. Install it with `pip install pyyaml`, "
                "or use a .json profile file instead."
            ) from error
        return yaml.safe_load(text) or {}

    return json.loads(text)


def load_profile(path: str | Path) -> Profile:
    """Load the written profile from a file."""
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"{path} does not exist")
    return Profile.from_dict(_read_document(path))


def render_profile(profile: Profile) -> str:
    """Render the profile as text, ready to be pasted into LinkedIn."""
    parts: list[str] = []

    if profile.headline:
        parts.append("## Headline")
        parts.append("")
        parts.append(profile.headline)
        parts.append("")

    if profile.about:
        parts.append("## About")
        parts.append("")
        parts.append(profile.about.strip())
        parts.append("")

    if profile.location:
        parts.append("## Location")
        parts.append("")
        parts.append(profile.location)
        parts.append("")

    if profile.experience:
        parts.append("## Experience")
        parts.append("")
        for entry in profile.experience:
            parts.append(entry.to_text())
            parts.append("")

    if profile.featured:
        parts.append("## Featured")
        parts.append("")
        for item in profile.featured:
            title = item.get("title", "")
            url = item.get("url", "")
            note = item.get("description", "")
            line = f"### {title}" if title else ""
            if line:
                parts.append(line)
                parts.append("")
            if note:
                parts.append(note)
                parts.append("")
            if url:
                parts.append(url)
                parts.append("")

    if profile.websites:
        parts.append("## Links")
        parts.append("")
        for item in profile.websites:
            label = item.get("label", "")
            url = item.get("url", "")
            if label and url:
                parts.append(f"- [{label}]({url})")
            elif url:
                parts.append(f"- {url}")
        parts.append("")

    if profile.skills:
        parts.append("## Skills")
        parts.append("")
        parts.append(", ".join(profile.skills))
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def diff_profile(live: dict[str, Any], written: Profile) -> list[str]:
    """Compare the live profile with the written one.

    Returns
    -------
    list[str]
        One line per difference. An empty list means they agree.
    """
    differences: list[str] = []

    live_headline = live.get("headline") or ""
    if written.headline and live_headline.strip() != written.headline.strip():
        differences.append(
            f"headline differs\n    live   : {live_headline or '(empty)'}\n"
            f"    written: {written.headline}"
        )

    live_about = live.get("about") or live.get("description") or ""
    if written.about and live_about.strip() != written.about.strip():
        differences.append(
            f"about differs\n    live   : {live_about[:120] or '(empty)'}\n"
            f"    written: {written.about[:120]}"
        )

    live_location = live.get("location") or ""
    if written.location and live_location.strip() != written.location.strip():
        differences.append(
            f"location differs\n    live   : {live_location or '(empty)'}\n"
            f"    written: {written.location}"
        )

    return differences


def apply_profile(client: Any, written: Profile, dry_run: bool = True) -> dict[str, Any]:
    """Push the written profile fields to LinkedIn.

    Parameters
    ----------
    client:
        A :class:`~linkedin_engine.client.LinkedInClient`.
    written:
        The profile to apply.
    dry_run:
        When true, report what would be sent without sending it.

    Returns
    -------
    dict
        ``{"changed": {...}, "sent": bool, "response": {...}}``
    """
    # The links are rendered but not sent. LinkedIn's member profile
    # endpoint does not take a websites field, and sending an unknown one
    # turns the whole update into a 400.
    fields: dict[str, Any] = {}
    if written.headline:
        fields["headline"] = written.headline
    if written.about:
        fields["about"] = written.about
    if written.location:
        fields["location"] = written.location

    if not fields:
        return {"changed": {}, "sent": False, "response": {}}

    if dry_run:
        return {"changed": fields, "sent": False, "response": {}}

    response = client.update_profile(fields)
    return {"changed": fields, "sent": True, "response": response}
