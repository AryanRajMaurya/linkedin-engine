<p align="center">
  <b>linkedin-engine</b><br>
  <i>Publish what you actually shipped — and keep your profile honest.</i>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <a href="https://github.com/AryanRajMaurya/linkedin-engine"><img src="https://img.shields.io/badge/deps-none-success" alt="No dependencies"></a>
  <a href="https://github.com/AryanRajMaurya/linkedin-engine"><img src="https://img.shields.io/badge/tests-passing-success" alt="Tests"></a>
</p>

---

## The problem

Every automated posting tool has the same failure mode. It produces
something that technically publishes and reads as though nobody wrote it.
People recognise the shape, scroll past, and stop trusting the account.

So this tool is built around one rule: **a post is only worth publishing if
it is about something that actually happened.**

The drafts are built from artefacts that exist — a pull request that merged,
a release that shipped, a repository that was created. Each draft cites the
artefact it came from. If there is no artefact, there is no draft, and no
opportunity to write something that sounds like work without being work.

And before anything is published, it has to pass a gate.

## The quality gate

The gate is the part that matters. It refuses the patterns that make a post
read like a generated one:

| Rule | What it catches |
| --- | --- |
| `banned-phrase` | "thrilled to announce", "game-changer", "in today's fast-paced world", "unlock the power", and thirty more |
| `weak-opening` | A first line that is a greeting rather than a claim |
| `emoji-run` | `🚀🚀🚀` — emoji used as punctuation |
| `emoji-count` | More than three emoji in a post |
| `exclamations` | Emphasis in punctuation |
| `no-link` | A post about something you built that does not let anyone reach it |
| `too-short` | Under 200 characters, which says nothing |
| `truncated` | Past the point where LinkedIn cuts it off mid-sentence |
| `filler` | "it's worth noting", "at the end of the day" |

Errors block the post. Warnings do not, but they are shown.

```
$ linkedin-engine check content/posts/pr-example-project-fix-the-streaming-proxy.md
[error] banned-phrase: Contains the announcement formula "thrilled to announce".
[error] weak-opening: Opens with "Hello everyone,".
[warning] emoji-count: 5 emoji in the post.
2 error(s), 1 warning(s)
```

## What else it does

- **Profile management.** The headline, the about section, the experience
  entries and the featured section live in one versionable file. The tool
  renders them, diffs them against the live profile, and applies the fields
  the API will accept.
- **Drafts from real activity.** `plan` reads your GitHub history and writes
  a draft per artefact, each one linked to what it came from.
- **Nothing publishes by accident.** Every command that writes to LinkedIn
  is a dry run unless you pass `--publish`.
- **No runtime dependencies.** The tool speaks LinkedIn's HTTP API directly.
  There is nothing to keep up to date and nothing to audit but this code.

## Setup

You need an application in the
[LinkedIn Developer Portal](https://www.linkedin.com/developers/apps/) and
two of its products.

### 1. The application

Create an app, then add the **Sign In With LinkedIn** product. It is
self-serve and is provisioned immediately.

The **Share on LinkedIn** product is what grants `w_member_social`, the
scope that lets you publish. It needs review, and the review is where most
of the waiting happens.

### 2. The redirect URL

Add a redirect URL to the application, for example
`https://localhost:8400/callback`. It has to match exactly what the tool
is configured with.

### 3. Configure

```bash
pip install -e .

linkedin-engine auth setup \
  --client-id "$LINKEDIN_CLIENT_ID" \
  --client-secret "$LINKEDIN_CLIENT_SECRET" \
  --redirect-uri "https://localhost:8400/callback"
```

The credentials are written to `~/.config/linkedin-engine/config.json` with
owner-only permissions. They are never written into the repository, and the
token is never printed.

### 4. Authorise

```bash
linkedin-engine auth login
```

It prints a URL. Open it, authorise the application, and paste the `code`
from the redirect back:

```bash
linkedin-engine auth login --code '<the code>'
```

The token lands in `~/.config/linkedin-engine/token.json`, also
owner-only.

If no refresh token comes back, the application has not been approved for
`w_member_social` yet. Reading the profile still works; publishing does
not.

### 5. Check what the token can do

```bash
linkedin-engine auth status
```

## Usage

```bash
# Turn recent GitHub activity into drafts.
linkedin-engine plan --username AryanRajMaurya --since 2026-10-01

# See the written profile, ready to paste.
linkedin-engine profile render

# Compare it with the live one.
linkedin-engine profile check

# Push it. A dry run unless you pass --publish.
linkedin-engine profile apply --publish

# Check a draft against the gate.
linkedin-engine check content/posts/pr-something.md

# Publish it. A dry run unless you pass --publish.
linkedin-engine publish content/posts/pr-something.md --publish
```

## How it talks to LinkedIn

The endpoints, headers and request shapes are taken from LinkedIn's own
client libraries —
[`linkedin-api-python-client`](https://github.com/linkedin-developers/linkedin-api-python-client)
and
[`linkedin-api-js-client`](https://github.com/linkedin-developers/linkedin-api-js-client) —
so nothing here is guesswork.

LinkedIn's APIs are built on Rest.li, where the method travels in a header
rather than in the HTTP verb. The client speaks that protocol directly.

| Call | Endpoint | Scope |
| --- | --- | --- |
| Read the member | `GET /me` | `r_liteprofile` |
| Update the member | `PATCH /me` | `w_member_social` |
| Publish a post | `POST /posts`, or `POST /ugcPosts` | `r_liteprofile`, `w_member_social` |

The tool tries the newer `/posts` endpoint and falls back to the legacy
`/ugcPosts`, which is the one that works for the widest range of granted
products.

## The profile file

`content/profile.json` is the source of truth. It is a versioned file, so a
change to the profile is a pull request rather than an edit in a form.

```json
{
  "headline": "AI/ML Engineer — Computer Vision, Real-Time Agents & Applied AI",
  "about": "I build AI systems that run in the real world — not notebooks.",
  "experience": [
    {
      "title": "Founder and Lead Engineer",
      "organisation": "IZGIV",
      "period": "2026 - Present",
      "highlights": ["Shipped shipfree, an open-source Agent Skill..."]
    }
  ]
}
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy
```

## License

MIT — see [LICENSE](LICENSE).

Built by [Aryan Raj Maurya](https://github.com/AryanRajMaurya).
