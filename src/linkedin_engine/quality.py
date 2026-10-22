"""The quality gate.

Every automated posting tool has the same failure mode: it produces
something that technically publishes and reads like it was written by a
generative model. People read it, recognise the shape, and stop trusting
the account.

So the drafts are checked before they are allowed anywhere near the feed.
The rules below are not taste. They are the specific patterns that make a
post read as though nobody wrote it:

- the announcement formulas ("thrilled to announce", "game-changer")
- emoji used as punctuation, in runs
- a post with no concrete artefact in it
- an opening line that is a greeting rather than a claim
- exclamation marks used for emphasis
- a length that says nothing

Errors block a post. Warnings do not, but they are shown.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

__all__ = ["Level", "Finding", "check_post", "BANNED_PHRASES"]


class Level(str, Enum):
    """How serious a finding is."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One thing wrong with a draft."""

    level: Level
    rule: str
    message: str
    hint: str = ""

    def __str__(self) -> str:
        arrow = f" -> {self.hint}" if self.hint else ""
        return f"[{self.level.value}] {self.rule}: {self.message}{arrow}"


#: Phrases that mark a post as a formula rather than a piece of writing.
#:
#: Matched case-insensitively against the whole post.
BANNED_PHRASES: tuple[str, ...] = (
    "thrilled to announce",
    "delighted to share",
    "humbled to announce",
    "excited to share",
    "proud to announce",
    "game-changer",
    "game changer",
    "in today's fast-paced",
    "in today's world",
    "in the ever-evolving",
    "in the rapidly evolving",
    "buckle up",
    "let's dive in",
    "let's dive into",
    "here's the thing",
    "this isn't just",
    "this is not just",
    "the future of",
    "revolutionizing",
    "revolutionising",
    "unlock the power",
    "unleash the power",
    "take your .? to the next level",
    "whether you're a",
    "i'm not just",
    "a testament to",
    "elevate your",
    "supercharge your",
    "seamlessly integrate",
    "seamlessly integrates",
    "seamless integration with",
    "in the realm of",
    "it's not just a tool",
    "i believe that",
    "i'm convinced that",
)

#: Openings that waste the first line, which is the only line most people
#: will read.
BANNED_OPENERS: tuple[str, ...] = (
    "hello",
    "hi ",
    "hey ",
    "good morning",
    "good evening",
    "greetings",
    "i hope you're doing well",
    "i hope this finds you well",
    "excited to share",
    "thrilled",
    "delighted",
    "in a world",
    "imagine",
    "picture this",
)

#: Words that read as filler in a technical post.
FILLER_PHRASES: tuple[str, ...] = (
    "it's important to note",
    "it is important to note",
    "it's worth noting",
    "it is worth noting",
    "at the end of the day",
    "needless to say",
    "in a nutshell",
    "the bottom line is",
    "last but not least",
    "a testament to",
)

#: Matches a URL.
URL_RE = re.compile(r"https?://\S+")

#: Matches a run of emoji.
EMOJI_RE = re.compile("[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]+")

#: Matches a sentence-case word in the middle of a sentence, which is how
#: the announcement formulas usually look.
SHAOUTY_RE = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")

MIN_CHARS = 200
MAX_CHARS = 3000
IDEAL_MIN = 400
IDEAL_MAX = 1800
MAX_EMOJI = 3
MAX_EXCLAMATIONS = 1
MAX_EMOJI_RUN = 1


def _count_emoji(text: str) -> int:
    """Count emoji characters in the text."""
    return sum(1 for char in text if unicodedata.category(char) == "So" or _is_emoji_block(char))


def _is_emoji_block(char: str) -> bool:
    """Whether a character is in one of the emoji blocks."""
    code = ord(char)
    return (
        0x1F000 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x1F1E6 <= code <= 0x1F1FF
        or 0xFE00 <= code <= 0xFE0F
    )


def _first_line(text: str) -> str:
    """The first non-empty line of the post."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def check_post(text: str, require_link: bool = True) -> list[Finding]:
    """Check a draft and return everything wrong with it.

    Parameters
    ----------
    text:
        The body of the post.
    require_link:
        Whether the post must contain a link. A post about something you
        built should let people reach it.

    Returns
    -------
    list[Finding]
        Errors first, then warnings. An empty list means the post is
        publishable.
    """
    findings: list[Finding] = []
    stripped = text.strip()
    lowered = stripped.lower()

    if not stripped:
        return [Finding(Level.ERROR, "empty", "The post is empty.")]

    # --- formula language -------------------------------------------------

    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            findings.append(
                Finding(
                    Level.ERROR,
                    "banned-phrase",
                    f'Contains the announcement formula "{phrase}".',
                    "Write what happened and why it matters instead.",
                )
            )

    for phrase in FILLER_PHRASES:
        if phrase in lowered:
            findings.append(
                Finding(
                    Level.WARNING,
                    "filler",
                    f'Contains the filler phrase "{phrase}".',
                    "Cut it.",
                )
            )

    # --- the opening line -------------------------------------------------

    opening = _first_line(stripped)
    opening_lower = opening.lower()
    for opener in BANNED_OPENERS:
        if opening_lower.startswith(opener):
            findings.append(
                Finding(
                    Level.ERROR,
                    "weak-opening",
                    f'Opens with "{opening[:40]}".',
                    "Open with the claim or the number, not a greeting.",
                )
            )
            break

    if len(opening) > 140:
        findings.append(
            Finding(
                Level.WARNING,
                "long-opening",
                f"The first line is {len(opening)} characters.",
                "Most people read the first line and stop. Keep it short.",
            )
        )

    # --- emoji ------------------------------------------------------------

    emoji_total = _count_emoji(stripped)
    if emoji_total > MAX_EMOJI:
        findings.append(
            Finding(
                Level.WARNING,
                "emoji-count",
                f"{emoji_total} emoji in the post.",
                f"More than {MAX_EMOJI} reads as decoration rather than emphasis.",
            )
        )

    for run in EMOJI_RE.findall(stripped):
        if len(run) > MAX_EMOJI_RUN:
            findings.append(
                Finding(
                    Level.ERROR,
                    "emoji-run",
                    f"A run of {len(run)} emoji in a row.",
                    "One emoji, or none.",
                )
            )
            break

    # --- punctuation ------------------------------------------------------

    exclamations = stripped.count("!")
    if exclamations > MAX_EXCLAMATIONS:
        findings.append(
            Finding(
                Level.WARNING,
                "exclamations",
                f"{exclamations} exclamation marks.",
                "Emphasis in punctuation reads as noise.",
            )
        )

    if "  " in stripped:
        findings.append(Finding(Level.WARNING, "spacing", "Contains a double space."))

    # --- substance --------------------------------------------------------

    if require_link and not URL_RE.search(stripped):
        findings.append(
            Finding(
                Level.ERROR,
                "no-link",
                "The post has no link in it.",
                "A post about something you built should point at it.",
            )
        )

    length = len(stripped)
    if length < MIN_CHARS:
        findings.append(
            Finding(
                Level.WARNING,
                "too-short",
                f"{length} characters.",
                f"A post under {MIN_CHARS} characters rarely says anything.",
            )
        )
    elif length < IDEAL_MIN:
        findings.append(
            Finding(
                Level.WARNING,
                "short",
                f"{length} characters.",
                f"Most posts that get read land between {IDEAL_MIN} and {IDEAL_MAX}.",
            )
        )
    elif length > IDEAL_MAX:
        findings.append(
            Finding(
                Level.WARNING,
                "long",
                f"{length} characters.",
                f"LinkedIn truncates around {MAX_CHARS} characters.",
            )
        )

    if length > MAX_CHARS:
        findings.append(
            Finding(
                Level.ERROR,
                "truncated",
                f"{length} characters is past the {MAX_CHARS} character limit.",
                "LinkedIn will cut it off mid-sentence.",
            )
        )

    return findings


def summarise(findings: Iterable[Finding]) -> str:
    """A one-line summary of the findings."""
    findings = list(findings)
    if not findings:
        return "publishable"
    errors = sum(1 for f in findings if f.level is Level.ERROR)
    warnings = len(findings) - errors
    return f"{errors} error(s), {warnings} warning(s)"
