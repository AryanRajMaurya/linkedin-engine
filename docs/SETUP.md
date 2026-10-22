# Setting up the LinkedIn application

## The products, and why there are two

| Product | What it grants | How you get it |
| --- | --- | --- |
| **Sign In With LinkedIn** | `r_liteprofile`, and `openid`/`profile`/`email` with OpenID Connect | Self-serve. Provisioned immediately. |
| **Share on LinkedIn** | `w_member_social`, which is what lets you publish | Needs review. |

You want both. The first lets the tool read your profile so it can diff it
against the written one. The second lets it publish.

## The redirect URL

Add it to the application under **Auth → Redirect URLs**. It has to match
the `--redirect-uri` you configure, exactly, including the scheme and the
trailing slash.

`https://localhost:8400/callback` works for local use. Anything you set
must be registered with LinkedIn before you use it.

## The scopes

The tool requests:

```
r_liteprofile w_member_social
```

for posting, and `openid profile email` if you want the OpenID Connect
sign-in flow instead.

A scope that was not granted shows up as a 403 with LinkedIn's own message,
which the tool passes straight through rather than swallowing.

## If no refresh token comes back

LinkedIn only issues a refresh token when the application is approved for
`w_member_social`. Without one, the access token still works until it
expires, but the tool cannot refresh it, and it will not be able to
publish.

`linkedin-engine auth status` tells you which of the two you are in.

## Where the credentials live

```
~/.config/linkedin-engine/
├── config.json    client id, secret, redirect URI
└── token.json     the access token, its refresh token and its expiry
```

Both are written with owner-only permissions. Neither is ever written into
the repository, and the token is never printed — its `repr` is redacted so
it cannot leak through a traceback or a log line.

Set `LINKEDIN_ENGINE_HOME` to move them somewhere else.
