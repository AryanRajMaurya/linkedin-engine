"""Turning real work into post drafts.

The point of this module is that a post is only worth publishing if it is
about something that actually happened. So the drafts are built from
artefacts that exist: a pull request that merged, a release that shipped, a
repository that was created, a paper that was published.

Each draft cites the artefact it came from. If there is no artefact, there
is no draft, and no opportunity to write something that sounds like work
without being work.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Artefact",
    "ArtefactKind",
    "fetch_artefacts",
    "render_draft",
    "slugify",
]

USER_AGENT = "linkedin-engine/0.1"


class ArtefactKind(str):
    """The kind of thing that happened."""


@dataclass
class Artefact:
    """One real thing that happened, and the facts needed to write about it."""

    kind: str
    title: str
    url: str
    repo: str = ""
    detail: str = ""
    number: int | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """A stable identifier for the artefact."""
        parts = [self.kind, self.repo or "self", str(self.number or self.title)]
        return slugify("-".join(parts))


def slugify(text: str) -> str:
    """Turn a title into something safe for a filename."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return cleaned[:80] or "item"


def _get_json(url: str, token: str | None = None) -> Any:
    """GET a URL and parse the JSON response."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"GitHub returned {error.code} for {url}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"could not reach GitHub: {error.reason}") from error


def _first_paragraph(body: str) -> str:
    """The first real paragraph of a body of text.

    Pull request bodies often start with a checklist or a heading. Those
    paragraphs are dropped, and so are the HTML comment blocks that GitHub
    uses for templates.
    """
    if not body:
        return ""

    text = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            continue
        if re.match(r"^\s*[-*]\s*\[[ xX]\]", paragraph):
            continue
        if paragraph.lower() in {"description", "checklist", "what does this pr do?"}:
            continue
        return re.sub(r"\s+", " ", paragraph)
    return ""


def fetch_artefacts(
    username: str,
    since: str,
    token: str | None = None,
    repos: Iterable[str] | None = None,
) -> list[Artefact]:
    """Find the things that happened in a window.

    Parameters
    ----------
    username:
        The GitHub user whose activity to look at.
    since:
        An ISO date. Only activity after it is returned.
    token:
        An optional GitHub token, which raises the rate limit and lets
        private activity be seen.
    repos:
        Limit the search to these repositories.

    Returns
    -------
    list[Artefact]
        Merged pull requests, published releases and new repositories,
        newest first.
    """
    artefacts: list[Artefact] = []

    # Merged pull requests.
    query = f"is:pr is:merged author:{username} merged:>={since}" + (
        f" {' OR '.join(f'repo:{r}' for r in repos)}" if repos else ""
    )
    try:
        results = _get_json(
            "https://api.github.com/search/issues"
            f"?q={_quote(query)}&sort=updated&order=desc&per_page=25",
            token,
        )
        for item in results.get("items", []):
            repo = item.get("repository_url", "").split("/")[-2:]
            artefacts.append(
                Artefact(
                    kind="pr",
                    title=item.get("title", ""),
                    url=item.get("html_url", ""),
                    repo="/".join(repo),
                    detail=_first_paragraph(item.get("body") or ""),
                    number=item.get("number"),
                )
            )
    except RuntimeError:
        pass

    # Published releases.
    try:
        releases = _get_json(
            f"https://api.github.com/users/{username}/repos?per_page=100&sort=pushed",
            token,
        )
        for repo in releases:
            if repos and repo.get("full_name") not in repos:
                continue
            try:
                tags = _get_json(
                    f"https://api.github.com/repos/{repo['full_name']}/releases?per_page=5",
                    token,
                )
            except RuntimeError:
                continue
            for release in tags:
                if release.get("published_at", "")[:10] < since:
                    continue
                artefacts.append(
                    Artefact(
                        kind="release",
                        title=f"{repo['name']} {release.get('tag_name', '')}".strip(),
                        url=release.get("html_url", ""),
                        repo=repo.get("full_name", ""),
                        detail=_first_paragraph(release.get("body") or ""),
                        tags=list(repo.get("topics") or []),
                    )
                )
    except RuntimeError:
        pass

    # New repositories.
    try:
        repos_list = _get_json(
            f"https://api.github.com/users/{username}/repos?per_page=100&sort=created",
            token,
        )
        for repo in repos_list:
            if repo.get("created_at", "")[:10] < since:
                continue
            if repo.get("fork"):
                continue
            if repos and repo.get("full_name") not in repos:
                continue
            artefacts.append(
                Artefact(
                    kind="repo",
                    title=repo.get("name", ""),
                    url=repo.get("html_url", ""),
                    repo=repo.get("full_name", ""),
                    detail=repo.get("description") or "",
                    tags=list(repo.get("topics") or []),
                )
            )
    except RuntimeError:
        pass

    artefacts.sort(key=lambda a: a.url)
    return artefacts


def _quote(text: str) -> str:
    """Percent-encode a query string fragment."""
    import urllib.parse

    return urllib.parse.quote(text)


def render_draft(artefact: Artefact, author: str = "") -> str:
    """Render a post draft for an artefact.

    The draft is deliberately plain. It states what happened, gives the
    detail that makes it interesting, and links the artefact. The quality
    gate then decides whether it is worth publishing.
    """
    lines: list[str] = []

    if artefact.kind == "pr":
        lines.append(f"Merged a pull request in {artefact.repo}: {artefact.title}.")
    elif artefact.kind == "release":
        lines.append(f"{artefact.title} is out.")
    elif artefact.kind == "repo":
        lines.append(f"Published {artefact.repo}.")
    else:
        lines.append(artefact.title)

    if artefact.detail:
        detail = artefact.detail.rstrip(".")
        if not detail.endswith((".", "!", "?")):
            detail += "."
        lines.append("")
        lines.append(detail)

    if artefact.tags:
        lines.append("")
        lines.append("Built with: " + ", ".join(artefact.tags[:6]) + ".")

    lines.append("")
    lines.append(artefact.url)

    return "\n".join(lines).strip()
