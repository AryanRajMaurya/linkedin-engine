# Setting up the LinkedIn application

## The Company Page

Creating an application asks for a Company Page, and the wording on that
screen is confusing enough to be worth spelling out.

**Individual developers have a default Company Page.** It already exists,
and it is associated with the API products you can request. Look for it in
the dropdown on that screen before typing anything new, and select it. That
is the path the screen is describing when it says you "must select that
default Company page to proceed".

**If there is no default page for you**, entering a company name that does
not exist creates one. The name becomes a LinkedIn Page with your name on
it, and you are its administrator — which is what matters, because:

> Verification can be done by a Page Admin.

You are the Page Admin of a page you just created, so you can verify the
application yourself. There is no waiting for anyone else.

**A member profile page will not work.** The screen says so explicitly,
and it is the reason a lot of people get stuck here: the obvious thing is
to paste your own profile URL, and it is refused.

**What to name it.** The app's name and the Company Page are public. They
show up on the application, which anyone can look at. Pick something that
looks deliberate — the same name you use everywhere else is the right
answer, not a throwaway.

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
