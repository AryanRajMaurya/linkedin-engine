# Writing posts that are worth reading

The tool refuses to publish a post that reads like a generated one. This
is what the rules are for, and why they exist.

## The rules, and what they are actually about

**A post must contain a link.** A post about something you built should let
people reach it. This is the rule that most improves the quality of a
developer's feed, and the one most often broken.

**The first line is the only line most people read.** It has to be a claim
or a number, not a greeting. "Hello everyone, I am excited to share" tells
a reader nothing and they leave.

**Say what the thing does, not how you feel about building it.** The
announcement formulas — "thrilled to announce", "game-changer", "unlock the
power" — are what makes a feed look automated. They are on the blocklist
because they are the tell.

**Emoji are punctuation, not emphasis.** A run of them reads as a template.
One, or none.

**Length.** Between 400 and 1,800 characters is the range where a post
actually gets read. Under 200 says nothing. Over 3,000 and LinkedIn cuts it
off mid-sentence, which is worse than being short.

## What a good post looks like

```
Merged a pull request in example/project: pipe the upstream response.

The response is piped instead of buffered, which is what keeps it inside a
10 ms CPU budget. Buffering a multi-megabyte response parses it, and parsing
is the expensive part.

The part that bit was the D1 query limit: 50 queries per invocation, which a
loop over twenty conversations blows through before it does anything else.

Details: https://github.com/example/project/pull/12
```

Three things it does: it says what happened, it says the interesting part
(the limit that bit, the gotcha), and it links the artefact. It does not say
how excited the author is.

## The loop

```bash
# 1. Drafts from what actually happened.
linkedin-engine plan --username you --since 2026-10-01

# 2. Edit the draft. This is the part that needs you.

# 3. Check it.
linkedin-engine check content/posts/pr-something.md

# 4. Publish it.
linkedin-engine publish content/posts/pr-something.md --publish
```

Step 2 is not optional. The tool can find the artefact and state the facts;
it cannot know which part was interesting. That is the part a human is
for, and it is the part that makes the post worth reading.
