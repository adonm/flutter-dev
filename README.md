# flutter-dev

`flutter-dev` is the integration workspace for the [Zuko](https://github.com/adonm/zuko)
and [Vixen](https://github.com/adonm/vixen) Flutter applications. It pins the
applications, the Flutter SDK work they currently require, and maintained
package/plugin forks as independent Git submodules.

This is a meta-repository, not a source-history merger. Each child repository
keeps its own issues, releases, build system, license, and upstream pull
requests. The parent records one reproducible combination of exact commits.

## Clone and bootstrap

```sh
git clone --recurse-submodules https://github.com/adonm/flutter-dev.git
cd flutter-dev
mise trust       # after reviewing mise.toml
mise install
just check
```

For an existing non-recursive checkout:

```sh
mise trust       # after reviewing mise.toml
mise install
just bootstrap
```

Normal bootstrap always checks out the exact gitlinks committed by this
repository. Do not use `git submodule update --remote` for builds or CI: branch
names are maintenance metadata, not floating dependencies.

## Repository map

| Path | Role |
|---|---|
| `apps/zuko` | Private remote shell application and Flutter clients |
| `apps/vixen` | Flutter-hosted browser application and renderer |
| `sdk/flutter` | Flutter framework/engine fork for GTK4 integration |
| `sdk/flutter-packages` | Flutter package fork, currently `url_launcher` |
| `packages/libghostty` | Ghostty terminal bindings and `flterm` widget |
| `plugins/gtk.dart` | GTK bindings |
| `plugins/screen_retriever` | Screen discovery plugin |
| `plugins/window_manager` | Desktop window management plugin |
| `plugins/yaru_window.dart` | Yaru window integration |

`.gitmodules` defines clone URLs and maintenance branches. `submodules.json`
records the reviewed origins, canonical upstreams, and exact expected commits.
The parent gitlinks remain Git's authoritative checkout pins.

## Parent commands

```sh
just status          # show recursive status and validate local pins
just check           # deterministic local metadata/worktree checks
just check-remotes   # anonymously match every public branch tip to its pin
just check-zuko      # run Zuko's own gate
just check-vixen     # run Vixen's R7 gate
just check-libghostty
just check-maintained # parent, remote, app, and libghostty gates
just verify-clone <parent-commit> # isolated recursive-clone release proof
```

Each child repository remains authoritative for its complete platform and
release checks. The parent does not replace Flutter, plugin, or application CI.
`check-maintained` collects independent child gates; it does not rewrite app
dependency manifests or by itself prove a composed cross-repository build. An
integration PR must record the app-specific command that consumed the changed
SDK, package, or plugin pin.
Review and trust a child's Mise configuration before running its Mise-backed
gate, for example:

```sh
mise trust apps/zuko/mise.toml
mise trust apps/vixen/.mise.toml
```

## Updating a pin

Work and commit inside the child repository first. Push the child commit before
recording it here, then update the parent from its root:

```sh
just pin path/to/submodule
just check-remotes
git diff --cached --submodule=log
git commit
```

`just pin` refuses dirty child worktrees, writes the checked-out commit to
`submodules.json`, stages that manifest and the gitlink, and reruns local
validation. Review the staged diff before committing.

For branch layout, downstream patches, coordinated work across both apps, and
upstream pull requests, see [`docs/WORKFLOW.md`](docs/WORKFLOW.md).

## Pin policy

A parent pin is accepted only when:

1. the child commit is committed and pushed to the configured public fork;
2. the child worktree is clean;
3. the manifest, `.gitmodules`, index gitlink, checkout, and origin agree;
4. focused child checks pass; and
5. upstreamable work has a focused upstream issue or pull request, or the root
   integration PR explains why a commit must remain downstream.

At parent review time, `just check-remotes` requires each anonymously visible
fork branch tip to equal the manifest pin. A later branch advance does not
change an existing parent checkout, but the next integration PR must review and
record the new tip deliberately.

Never rewrite a branch while a released parent commit pins it. Add commits or
publish a replacement branch, update the parent, and retire the old branch only
after no supported parent revision depends on it.

## Licenses

The parent orchestration and documentation are Apache-2.0 licensed. Every
submodule retains and is distributed under its own license.
