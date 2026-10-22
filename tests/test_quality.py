"""Tests for the quality gate.

The gate is the part of this tool that decides whether a post is allowed
near a feed, so it gets the most attention.
"""

from __future__ import annotations

from linkedin_engine.quality import BANNED_PHRASES, Level, check_post

A_GOOD_POST = """\
Built a streaming proxy for a model API and it stayed inside a 10 ms CPU budget.

The trick was to pipe the upstream response instead of buffering it. Time spent
waiting on a socket is not CPU time, so the request costs almost nothing. The
part that bit was the D1 query limit: 50 queries per invocation, which a loop
over twenty conversations blows through before it does anything else.

Details: https://github.com/example/project/pull/12
"""


def test_a_good_post_has_no_errors() -> None:
    findings = check_post(A_GOOD_POST)
    errors = [f for f in findings if f.level is Level.ERROR]
    assert not errors, [str(f) for f in errors]


def test_an_empty_post_is_an_error() -> None:
    findings = check_post("   ")
    assert any(f.rule == "empty" for f in findings)


def test_banned_phrases_are_caught() -> None:
    for phrase in BANNED_PHRASES[:6]:
        post = f"{phrase.capitalize()}. Here is what I built and why it matters.\n\n" + A_GOOD_POST
        findings = check_post(post)
        assert any(f.rule == "banned-phrase" for f in findings), phrase


def test_a_weak_opening_is_caught() -> None:
    post = "Hello everyone,\n\n" + A_GOOD_POST
    findings = check_post(post)
    assert any(f.rule == "weak-opening" for f in findings)


def test_a_post_with_no_link_is_an_error() -> None:
    post = A_GOOD_POST.replace("https://github.com/example/project/pull/12", "")
    findings = check_post(post)
    assert any(f.rule == "no-link" for f in findings)


def test_a_link_is_not_required_when_it_is_not_wanted() -> None:
    post = A_GOOD_POST.replace("https://github.com/example/project/pull/12", "")
    findings = check_post(post, require_link=False)
    assert not any(f.rule == "no-link" for f in findings)


def test_emoji_runs_are_caught() -> None:
    post = "Shipped it 🚀🚀🚀 and it works. " + A_GOOD_POST
    findings = check_post(post)
    assert any(f.rule == "emoji-run" for f in findings)


def test_too_many_emoji_is_a_warning() -> None:
    post = "Shipped 🚀 a thing ✨ today 🎉 and it works 🎁. " + A_GOOD_POST
    findings = check_post(post)
    assert any(f.rule == "emoji-count" for f in findings)


def test_exclamation_mark_spam_is_a_warning() -> None:
    post = "It works! It really works!! " + A_GOOD_POST
    findings = check_post(post)
    assert any(f.rule == "exclamations" for f in findings)


def test_a_very_short_post_is_a_warning() -> None:
    findings = check_post("Built it. https://example.com")
    assert any(f.rule == "too-short" for f in findings)


def test_an_over_long_post_is_an_error() -> None:
    post = A_GOOD_POST + ("x" * 3200)
    findings = check_post(post)
    assert any(f.rule == "truncated" for f in findings)


def test_filler_phrases_are_warnings_not_errors() -> None:
    post = "It is worth noting that this works. " + A_GOOD_POST
    findings = check_post(post)
    filler = [f for f in findings if f.rule == "filler"]
    assert filler
    assert all(f.level is Level.WARNING for f in filler)


def test_findings_carry_a_useful_hint() -> None:
    post = "I'm thrilled to announce something. " + A_GOOD_POST
    findings = check_post(post)
    banned = [f for f in findings if f.rule == "banned-phrase"]
    assert banned and banned[0].hint
