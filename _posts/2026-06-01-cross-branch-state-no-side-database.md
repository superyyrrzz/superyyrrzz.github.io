---
title: "Adding Cross-Branch State to a Content Repo Without a Side Database"
description: "When a CMS-on-git system needs extra state — opt-ins, regeneration tokens, moderation — putting it in a side database creates a reconciliation problem. Putting it in the module's own YAML doesn't."
date: 2026-06-01 10:00:00 +0800
categories: [Engineering, Microsoft Learn]
tags: [git, content-as-code, design]
image:
  path: /assets/og/cross-branch-state-no-side-database.png
  alt: "Adding Cross-Branch State to a Content Repo Without a Side Database"
---

[`MicrosoftDocs/learn`](https://github.com/MicrosoftDocs/learn) is the
public source repository behind a large chunk of Microsoft Learn's
training content. Modules are authored as Markdown plus YAML
front matter, contributors work on PR branches against `main`, and
what's on `main` at any moment is what the site renders. It's a
classic CMS-on-git shape.

This post is about a design problem that shows up the moment you
try to add *more* state to that shape — state that isn't content
itself but has to behave like content does: branch with branches,
merge with merges, get reviewed in the same PR. The concrete
trigger was AI-generated assessments — short quizzes generated
from each module's content so the author doesn't have to write
them by hand — but the design problem is general.

## The problem

Imagine adding AI-generated assessments to this system. For each
module that opts in, the publisher calls an LLM to produce a short
quiz from the module's content and renders it on the page. That
single feature drags three new pieces of *state about the module*
into the system, none of which are part of the prose itself:

1. **An opt-in flag** — does this module want an AI-generated
   assessment at all? Some modules already ship a hand-written
   quiz; some don't want one; only the rest opt in.
2. **A version token** — a way to say "the current canonical
   assessment for this module is *this* one; if the token changes,
   regenerate." Authors need a one-line nudge to force the
   generator to run again when the current generated output isn't
   good enough.
3. **A moderation channel** — a human reviewer needs to hide
   individual generated questions (low quality, off-topic,
   ambiguous) without re-running the generator to try for a
   better roll.

All three share a hard requirement: they have to ride along with
the module through branches, PRs, and merges.
If a contributor opts a module in on a feature branch, the opt-in
should be part of that branch's content. If two contributors hide
different questions on different branches, merging should compose
the hidden lists. If a moderator on `main` hides a question
*after* a feature branch was cut, the feature branch should still
see the un-hidden version until it merges.

## Three options that don't work

The instinct in a system that already has a database is to put the
new state there. Three flavors of that, all of which we considered
and rejected:

- **A backend database keyed by `(repository, branch, moduleId)`.**
  The database doesn't know about Git. When a branch is created,
  the rows don't exist on the new branch's key tuple — you'd have
  to copy them over. When a PR merges, you'd have to merge rows.
  Both are reconciliation steps that don't exist for content,
  because Git already handles them. You'd be writing a half-baked
  branch-aware data layer that duplicates work Git already does.
- **A parallel "moderation" repository.** Two repos to keep in
  sync, two PRs per change, doubled review surface. Worse, the
  moderation repo's branch graph has to mirror the content repo's
  branch graph, and "mirror" is a long-running source of bugs.
- **A moderation web UI writing straight to the database.**
  Moderation actions happen at human-time; commits happen at
  PR-merge time. The two streams diverge between every "approve"
  click and every merge, and you spend the rest of the project
  building reconciliation logic to glue them back together.

The common shape: each option treats the database (or a second
repo) as a *second* source of truth, and pays the cost of
reconciling two sources of truth forever after.

## The design we landed on

Put the state in the module's own YAML front matter — specifically,
on the assessment unit that the publisher already reads per module:

```yaml
---
title: "Knowledge check"
uid: learn.some-module.knowledge-check
metadata:
  ai_generated_module_assessment: true
  module_assessment_regen_label: 2026-q1-refresh
  hidden_question_numbers:
    - 7c9a3f_12
    - 7c9a3f_18
---
```

Three fields, each doing exactly one of the three jobs the previous
section called out:

- **`ai_generated_module_assessment`** — the opt-in flag. A boolean
  the publisher checks. Absent or `false` means the module isn't
  part of the feature; the publisher skips it.
- **`module_assessment_regen_label`** — an opaque string token. The
  publisher uses it as part of the cache bucket name for any
  generated artifact (more on this below). Bumping the label —
  changing it to anything new — guarantees a cache miss and forces
  fresh generation. The token has no intrinsic ordering: no "newer
  wins" comparison anywhere in the publisher to apply by reflex.
- **`hidden_question_numbers`** — a list of opaque question
  identifiers the moderator wants suppressed at render time. The
  generator still produces all the questions; the publisher
  filters this list before emitting the page. Hiding a question
  is one PR commit against the module's own file.

Because all three live in the module's own YAML, Git's existing
branching and merging do the work:

- Branching the module branches the state (correct default).
- A PR merge merges the state along with the content, with Git's
  normal three-way merge handling any conflicts.
- A reviewer sees the moderation change and the content change in
  the same diff, in the same PR.

The reconciliation layer that the database options would have
required is replaced by the merge semantics Git already has.

## Where the regen label actually lives: the cache bucket

The `module_assessment_regen_label` field is what ties the design
together.
The publisher caches AI output keyed by a hash of an embedding of
the module's content, so near-identical content reuses the same
generated assessment (semantic similarity, not byte-exact match —
but that's a detail for another post). The cache is partitioned
into buckets, and the bucket name is constructed roughly like:

```text
bucket = "<service>_<moduleId>_label_<regenLabel>"
```

The content hash is the key *within* a bucket; the regen label
picks the bucket. So bumping the label doesn't invalidate any
cache entries — it moves the lookup into a *new bucket that has
no entries yet*. That
makes the regeneration semantics implicit in the data:

- Same content, same label → exact cache hit, same output, no AI
  call, no review needed.
- New label → fresh bucket, no exact hit, generator runs, new
  output goes into the new bucket. Old bucket is left alone and
  remains valid for any branch still on the old label.

Branches that never touched the label keep hitting their own
bucket; branches that bumped it get their own fresh generation;
merging the YAML merges the label. The same primary key — content
plus regen label — is what makes the cache architecture and the
cross-branch state mechanism compose cleanly instead of fighting
each other.

## The question-ID trick

The hidden-questions field uses identifiers like `7c9a3f_12`, where
`7c9a3f` is a hash of the generated module assessment and `12` is
the question's per-generation ID. That structure isn't accidental.

If a moderator hides question `7c9a3f_12`, and later a regeneration
produces an entirely new assessment with hash `b40e1d`, the old
`7c9a3f_12` entry simply *stops applying* — none of the new
questions match it. The moderator's hidden list doesn't need to
be cleaned up; the staleness is self-evident.

Without the hash prefix, an entry like just `12` would silently
apply to whatever question happened to be numbered 12 in the new
generation, which is almost certainly not the question the
moderator originally objected to. The hash makes hiding *bind
to the specific generated output it was made against*, and
that's the only honest semantics for a moderation action.

## Moderators never see the YAML

One question this design raises immediately: do we really expect
moderators — content reviewers whose job is to read questions,
not edit YAML — to open `.yml` files and append entries to
`hidden_question_numbers`? No. The YAML is the *storage* format;
the *interface* is a web UI sitting next to the PR.

The reviewer sees the generated assessment rendered as a normal
preview, with a "hide" button next to each question. Clicking
hide doesn't mutate any database. Instead, the UI goes through a
GitHub OAuth flow on first use, gets a token scoped to the
content repo, and commits the YAML change directly to the
moderator's PR branch on their behalf. From the reviewer's
perspective it's a single button click; underneath, a real
commit lands on the branch and shows up in the PR diff like any
other change.

That commit-on-behalf flow is what makes the whole "state in
YAML" design tolerable in practice. The mechanism survives every
git operation cleanly, *and* the people generating the state
don't have to learn it exists. A web UI writing straight to a
side database would have given the reviewer the same one-click
experience but inherited all the reconciliation problems from
earlier. A web UI committing to git gives both: clean storage
semantics, and a UX moderators don't have to think about.

## What I'd tell someone designing similar state

Two principles I'd keep:

**1. On a Git-backed CMS, fight the database urge.** The source
of truth for "what does this branch contain" is already Git. Any
state you put in a second store needs a reconciliation layer to
stay aligned with Git, and that layer is where bugs hide. If the
new state has to ride along with content changes through PRs and
merges, put it where the content already lives.

**2. Opaque tokens beat structured values for merge-friendly
state.** A timestamp or a counter invites a "newer wins" heuristic
in any code that compares two values — and once that pattern lives
in the codebase, it's easy for someone resolving a merge conflict
to apply it by reflex, picking the larger number without thinking
about whether "larger" actually means "right." An opaque token (a
label, a UUID, a string) has no implicit ordering, so a merge
conflict surfaces to a human who has to make a real call about
which regeneration intent should win.

These aren't novel ideas — the second is folklore in distributed
systems and the first is what every Git-as-database pattern boils
down to. They just keep coming back as the right answer when the
question is "where does this new state live."
