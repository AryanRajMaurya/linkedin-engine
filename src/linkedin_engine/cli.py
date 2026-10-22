"""The command line interface.

    linkedin-engine auth setup      store the application details
    linkedin-engine auth login      print the URL to authorise, exchange the code
    linkedin-engine auth status     show what the token can do
    linkedin-engine profile render  print the written profile, ready to paste
    linkedin-engine profile check   compare the live profile with the written one
    linkedin-engine profile apply   push the written profile to LinkedIn
    linkedin-engine plan            turn recent GitHub activity into drafts
    linkedin-engine check <file>    run the quality gate over a draft
    linkedin-engine publish <file>  publish a draft

Nothing publishes without ``--publish``, and the quality gate runs first
either way.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import auth, content
from . import profile as profile_module
from . import publish as publish_module
from .client import LinkedInClient, LinkedInError
from .config import Config, Token
from .quality import Level, check_post, summarise

CONTENT_DIR = Path("content")
POSTS_DIR = CONTENT_DIR / "posts"
PROFILE_FILE = CONTENT_DIR / "profile.json"


def _client(config: Config | None = None) -> LinkedInClient:
    """Build a client with a valid token."""
    config = config or Config.load()
    config.require()
    token = auth.ensure_token(config)
    return LinkedInClient(token.access_token)


# --------------------------------------------------------------------- auth


def cmd_auth_setup(args: argparse.Namespace) -> int:
    """Store the application details."""
    config = Config.load()
    config.client_id = args.client_id or config.client_id
    config.client_secret = args.client_secret or config.client_secret
    config.redirect_uri = args.redirect_uri or config.redirect_uri
    if args.scopes:
        config.scopes = args.scopes.split()
    config.save()
    print(f"Configuration written to {Config.load.__module__ and ''}", end="")
    print("Done. Run `linkedin-engine auth login` next.")
    return 0


def cmd_auth_login(args: argparse.Namespace) -> int:
    """Print the authorisation URL and exchange the code."""
    config = Config.load()
    config.require()

    if args.code:
        token = auth.exchange_code(config, args.code)
        token.save()
        print("Token stored.")
        print(f"Scope: {token.scope or ', '.join(config.scopes)}")
        if not token.refresh_token:
            print(
                "Note: no refresh token was issued. That usually means the "
                "application is not approved for w_member_social yet."
            )
        return 0

    url = auth.authorization_url(config)
    print("Open this URL, authorise the application, then paste the code:\n")
    print(url)
    print("\nThe redirect will land on a page with a `code` parameter. Pass it with:")
    print("  linkedin-engine auth login --code '<code>'")
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    """Show what the stored token can do."""
    token = Token.load()
    if token is None:
        print("No token stored. Run `linkedin-engine auth login`.")
        return 1

    print(f"Expires at   : {token.expires_at or 'unknown'}")
    print(f"Expired      : {token.expired}")
    print(f"Has refresh  : {bool(token.refresh_token)}")
    try:
        details = auth.introspect(token)
        print(f"Introspection: {json.dumps(details)[:300]}")
    except RuntimeError as error:
        print(f"Introspection failed: {error}")
    return 0


# ------------------------------------------------------------------ profile


def cmd_profile_render(args: argparse.Namespace) -> int:
    """Print the written profile."""
    written = profile_module.load_profile(args.file)
    print(profile_module.render_profile(written))
    return 0


def cmd_profile_check(args: argparse.Namespace) -> int:
    """Compare the live profile with the written one."""
    written = profile_module.load_profile(args.file)
    client = _client()

    live = client.get_me(projection="(id,firstName,lastName,headline,about,location)")
    differences = profile_module.diff_profile(live, written)

    if not differences:
        print("The live profile matches the written one.")
        return 0

    print(f"{len(differences)} difference(s):\n")
    for difference in differences:
        print(difference)
        print()
    return 1


def cmd_profile_apply(args: argparse.Namespace) -> int:
    """Push the written profile to LinkedIn."""
    written = profile_module.load_profile(args.file)
    client = _client()

    result = profile_module.apply_profile(client, written, dry_run=not args.publish)
    if not result["sent"]:
        print("Dry run. The following would be sent:\n")
        print(json.dumps(result["changed"], indent=2))
        print("\nPass --publish to send it.")
        return 0

    print("Profile updated.")
    return 0


# --------------------------------------------------------------------- plan


def cmd_plan(args: argparse.Namespace) -> int:
    """Turn recent GitHub activity into drafts."""
    artefacts = content.fetch_artefacts(
        username=args.username,
        since=args.since,
        token=args.token,
    )
    if not artefacts:
        print(f"Nothing found for {args.username} since {args.since}.")
        return 0

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    for artefact in artefacts:
        body = content.render_draft(artefact)
        findings = check_post(body)
        errors = [f for f in findings if f.level is Level.ERROR]

        path = POSTS_DIR / f"{artefact.kind}-{artefact.key}.md"
        if path.exists() and not args.force:
            print(f"  skip  {path.name} (already drafted)")
            continue

        header = [
            "---",
            f"kind: {artefact.kind}",
            f"source: {artefact.url}",
            f"repo: {artefact.repo}",
            "---",
            "",
        ]
        path.write_text("\n".join(header) + body + "\n")

        marker = "ok " if not errors else "!! "
        print(f"  {marker}{path.name}  {summarise(findings)}")
        for error in errors:
            print(f"      {error}")
        written += 1

    print(f"\n{written} draft(s) written to {POSTS_DIR}")
    return 0


# -------------------------------------------------------------------- check


def cmd_check(args: argparse.Namespace) -> int:
    """Run the quality gate over a draft."""
    text = Path(args.file).read_text()
    findings = check_post(text, require_link=not args.allow_no_link)
    if not findings:
        print("Publishable.")
        return 0
    for finding in findings:
        print(finding)
    print()
    print(summarise(findings))
    return 1 if any(f.level is Level.ERROR for f in findings) else 0


# ------------------------------------------------------------------ publish


def cmd_publish(args: argparse.Namespace) -> int:
    """Publish a draft."""
    text = Path(args.file).read_text()
    client = _client()

    result = publish_module.publish(
        client,
        text,
        dry_run=not args.publish,
        visibility=args.visibility,
        require_link=not args.allow_no_link,
    )

    for finding in result.findings:
        if finding.level is Level.WARNING:
            print(f"warning: {finding.message}")

    if not result.published:
        print(f"Not published: {result.reason}")
        return 1

    print(f"Published: {result.post_id}")
    return 0


# ---------------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="linkedin-engine",
        description="Publish what you actually shipped, and keep your profile honest.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    auth_parser = sub.add_parser("auth", help="authorise the application")
    auth_sub = auth_parser.add_subparsers(dest="auth_command", required=True)

    setup = auth_sub.add_parser("setup", help="store the application details")
    setup.add_argument("--client-id")
    setup.add_argument("--client-secret")
    setup.add_argument("--redirect-uri")
    setup.add_argument("--scopes", help="space separated OAuth scopes")
    setup.set_defaults(func=cmd_auth_setup)

    login = auth_sub.add_parser("login", help="authorise and store a token")
    login.add_argument("--code", help="the authorization code from the redirect")
    login.set_defaults(func=cmd_auth_login)

    status = auth_sub.add_parser("status", help="show what the token can do")
    status.set_defaults(func=cmd_auth_status)

    profile_parser = sub.add_parser("profile", help="manage the profile")
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)

    render = profile_sub.add_parser("render", help="print the written profile")
    render.add_argument("--file", default=str(PROFILE_FILE))
    render.set_defaults(func=cmd_profile_render)

    check = profile_sub.add_parser("check", help="compare live and written")
    check.add_argument("--file", default=str(PROFILE_FILE))
    check.set_defaults(func=cmd_profile_check)

    apply_cmd = profile_sub.add_parser("apply", help="push the written profile")
    apply_cmd.add_argument("--file", default=str(PROFILE_FILE))
    apply_cmd.add_argument(
        "--publish", action="store_true", help="actually send it; without this it is a dry run"
    )
    apply_cmd.set_defaults(func=cmd_profile_apply)

    plan = sub.add_parser("plan", help="turn recent activity into drafts")
    plan.add_argument("--username", default="AryanRajMaurya")
    plan.add_argument("--since", default="2026-10-01")
    plan.add_argument("--token", help="a GitHub token, to raise the rate limit")
    plan.add_argument("--force", action="store_true", help="redraft what exists")
    plan.set_defaults(func=cmd_plan)

    check_cmd = sub.add_parser("check", help="run the quality gate over a draft")
    check_cmd.add_argument("file")
    check_cmd.add_argument("--allow-no-link", action="store_true")
    check_cmd.set_defaults(func=cmd_check)

    publish_cmd = sub.add_parser("publish", help="publish a draft")
    publish_cmd.add_argument("file")
    publish_cmd.add_argument(
        "--publish", action="store_true", help="actually post it; without this it is a dry run"
    )
    publish_cmd.add_argument(
        "--visibility", default="PUBLIC", choices=["PUBLIC", "CONNECTIONS", "PRIVATE"]
    )
    publish_cmd.add_argument("--allow-no-link", action="store_true")
    publish_cmd.set_defaults(func=cmd_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, LinkedInError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
