# Application, fork, and upstream workflow

This workspace lets Zuko and Vixen consume coordinated framework and plugin
work without turning those dependencies into copied source trees. In this
document, **vendoring** means pinning a reviewed commit from a maintained fork.
It does not mean copying dependency files into either application or squashing
independent project histories into this repository.

## Ownership boundaries

- `apps/zuko` and `apps/vixen` are first-party products. Product behavior and
  app-specific integration belong in those repositories.
- `sdk/`, `packages/`, and `plugins/` are fork worktrees. Changes intended for a
  canonical project must remain reviewable independently of either app.
- The parent repository owns only coordination: exact pins, dependency intent,
  reproducible commands, and links between integration work and child PRs.
- A child repository's own formatter, analyzer, tests, release process, and
  license remain authoritative.

Do not commit application code, copied patches, generated child output, or
cross-project build logic at the parent root. Do not make a parent commit point
at uncommitted or unpublished child state.

## Remote convention

A forked child uses these remotes:

```text
origin    https://github.com/adonm/<fork>.git       # integration fork
upstream  https://github.com/<owner>/<project>.git  # canonical project
```

`submodules.json` records both URLs. A fresh submodule clone only needs
`origin`; add `upstream` when developing or refreshing a fork:

```sh
cd path/to/submodule
git remote add upstream <upstream-url>
git fetch --prune upstream
```

`origin` is writable by project maintainers and remains the stable public URL
validated by the parent. Contributors without access add their own writable
remote and open child PRs from there:

```sh
git remote add personal https://github.com/<user>/<fork>.git
git push personal <branch>
```

Before the parent accepts a pin, a maintainer mirrors the reviewed commit to
the branch recorded on `origin`. Never push to `upstream`. Never force-push a
branch pinned by a parent commit. Use a replacement branch when published
history must change.

## Branch classes

Use one branch for one review boundary:

| Class | Pattern | Base | Purpose |
|---|---|---|---|
| Upstream PR | `upstream/<issue>-<slug>` | Canonical default branch | Minimal change suitable for one canonical PR |
| Downstream overlay | `vendor/<app-or-shared>/<slug>` | Upstream PR branch or canonical commit | Necessary app integration that cannot be upstreamed |
| First-party feature | `feat/<issue>-<slug>` or `fix/<issue>-<slug>` | App `main` | Zuko/Vixen product work |
| Parent integration | `integration/<initiative>` | Parent `main` | Coordinated pin updates and documentation |

Existing long-lived branches such as `issue-94804-gtk4-linux` predate this
convention and may remain until their current upstreaming effort is complete.
New work should use the branch classes above.

A branch named `upstream/...` must not contain app branding, unrelated
refactors, generated parent files, or multiple projects' changes. A
`vendor/...` branch must clearly identify which commits are downstream-only and
why.

## Coordinated work for Zuko and Vixen

Start with a parent integration branch and a small component matrix:

```sh
git switch -c integration/<initiative>
```

For each affected child:

1. Identify the smallest owner of the behavior: app, package/plugin, Flutter
   package, or Flutter framework/engine.
2. Create an upstream PR branch directly from the canonical project's current
   default branch.
3. Implement only that project's coherent change and run its native checks.
4. Push the commit to `origin` and open a focused PR against `upstream`.
5. If either app needs temporary glue or policy that upstream should not own,
   add a separate `vendor/zuko/...`, `vendor/vixen/...`, or
   `vendor/shared/...` overlay branch on top.
6. Pin the exact published commit with `just pin <path>`.
7. Change each app in its own first-party branch and PR. Do not combine Zuko and
   Vixen product changes merely because they consume the same dependency pin.
8. Record all child branches/PRs and check results in the parent integration PR.

When both apps need the same dependency behavior, produce one shared upstream
change and pin it once. Do not maintain equivalent patches independently in
both app repositories. App-specific differences stay in the apps or in clearly
separate overlay commits.

## Making an app consume a vendored pin

A parent gitlink makes source available; it does not silently alter either
app's dependency resolution. The app integration PR must make consumption
explicit:

- For a Dart package or plugin, the committed app dependency uses a published
  package version or an immutable fork commit/tag. During coordinated local
  development, an ignored `pubspec_overrides.yaml` may point to the sibling
  checkout when supported; never commit an absolute workstation path.
- For Flutter framework or engine work, run the relevant compatibility build
  with `sdk/flutter/bin/flutter`, and record that exact command. The app's
  ordinary gate may keep its independently pinned release SDK.
- For generated platform files, keep the generator and generated output in the
  child repository that owns them. Do not patch generated app files from the
  parent.

`just check-maintained` runs independent maintained child gates and uses the
pinned Flutter checkout for libghostty. It is not a universal composed-build
claim. Each integration PR names and runs the focused app build that exercises
its changed dependency path.

## Making upstream PRs easy to review

Before opening a canonical PR:

- Rebase or rebuild the branch from the current canonical default branch.
- Keep one concern and one project per PR.
- Split mechanical changes, behavior changes, generated output, tests, and docs
  into logical commits when that improves review; every commit should build or
  have an explicit stack dependency.
- Include the failing behavior, the ownership rationale, focused tests, and the
  exact command/output proving the fix.
- Avoid references that require an upstream reviewer to understand Zuko,
  Vixen, or this meta-repository unless the app is the reproduction case.
- Avoid lockfile/dependency churn not required by the fix.
- Match the canonical repository's style, contribution guide, and branch base.
- Link the upstream issue and identify any dependent PRs without hiding stack
  order.

If an initiative spans repositories, open separate PRs and use a dependency
list such as:

```text
1. flutter/flutter#...          framework or engine contract
2. flutter/packages#...         package adaptation, based on or gated by 1
3. owner/plugin#...             plugin adaptation
4. adonm/zuko#...               product integration
5. adonm/vixen#...              product integration
6. adonm/flutter-dev#...        exact integration pins
```

The parent PR is the ledger and integration proof, not a substitute for the
child reviews.

## Parent integration PR contents

A parent PR should contain only:

- `.gitmodules` changes when a maintained branch or origin changes;
- `submodules.json` and matching gitlink updates;
- parent orchestration/documentation required by the integration; and
- links to child issues/PRs and measured validation results.

Use the repository PR template. For every pin, state whether it is:

- merged upstream;
- under upstream review;
- a temporary downstream overlay; or
- intentionally maintained in the fork.

Review `git diff --cached --submodule=log` after `just pin` so the parent PR
exposes every staged child commit, not just opaque SHA changes.

## After upstream merge

1. Fetch the canonical repository and confirm the merged commit.
2. Update the fork's default branch without rewriting any still-pinned branch.
3. Rebuild or rebase downstream overlays onto the canonical merged commit and
   drop commits that upstream now contains.
4. Run child checks again.
5. Pin the canonical merge/release commit, or the minimal remaining overlay,
   in a follow-up parent PR.
6. Remove obsolete overlay branches only after no supported parent revision or
   release points to them.
7. Close the integration ledger with links to the final upstream commits and
   releases.

## Emergency fixes

For a release-blocking fix, the fork may be pinned before upstream review
finishes, but the parent PR must include:

- the user-visible failure and urgency;
- a focused child commit with tests;
- the upstream issue/PR or a dated reason it cannot yet be filed;
- an owner for removing the overlay; and
- a follow-up condition, such as an upstream merge or package release.

Emergency does not permit dirty worktrees, unpublished pins, rewritten pinned
branches, or combining unrelated fixes.

## Validation and release safety

Run at least:

```sh
just check
just check-remotes
```

After creating the candidate parent commit, prove that exact revision rather
than a moving default branch. Before push, clone the local repository; after
push, use the default public URL:

```sh
just verify-clone-local "$(git rev-parse HEAD)"
just verify-clone "$(git rev-parse HEAD)"
```

Each destination must be new; failed or completed proof clones are removed
manually. Then run each affected child's own gate. Before publishing the parent:

- all child commits must be public;
- all child worktrees must be clean;
- manifest and gitlinks must match;
- root and child diffs must be reviewed independently; and
- a recursive clone must reproduce the exact workspace.

Keep old standalone worktrees and fork branches until the recursive clone and
relevant application builds pass from the published parent commit.
