# flutter-dev

`flutter-dev` is the integration workspace for the [Zuko](https://github.com/adonm/zuko)
and [Vixen](https://github.com/adonm/vixen) Flutter applications. It pins the
applications and the shared libghostty/flterm fork as independent Git
submodules.

This is a meta-repository, not a source-history merger. Each child repository
keeps its own issues, releases, build system, license, and upstream pull
requests. The parent records one reproducible combination of exact commits.

Both applications install the official Flutter beta (`3.48.0-0.1.pre`) through
Mise and build with the stock GTK3 embedder and Impeller. The custom GTK4
framework/engine pipeline that this workspace previously coordinated was
retired when the applications moved to the official beta; its history is
summarized in [docs/WORKFLOW.md](docs/WORKFLOW.md).

## Clone and bootstrap

The supported Linux development baseline is an x86_64 Ubuntu 24.04 Distrobox.
Clone the workspace on the host, then create and provision the box using
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md):

```sh
git clone --recurse-submodules https://github.com/adonm/flutter-dev.git
cd flutter-dev
just devbox-setup  # first run only
just devbox-enter  # daily development shell
just check         # now inside Ubuntu with Mise active
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

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution loop and
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for first-time setup, common tasks,
and troubleshooting.

## Repository map

| Path | Role |
|---|---|
| `apps/zuko` | Private remote shell application and Flutter clients |
| `apps/vixen` | Flutter-hosted browser application and renderer |
| `packages/libghostty` | Ghostty terminal bindings and `flterm` widget fork |

`.gitmodules` defines clone URLs and maintenance branches. `submodules.json`
records the reviewed origins, canonical upstreams, and exact expected commits.
The parent gitlinks remain Git's authoritative checkout pins.

## Application pins

| App | Release commit |
|---|---|
| Zuko 0.10.14 | [`ea1f40a`](https://github.com/adonm/zuko/commit/ea1f40a) |
| Vixen 0.1.7 | [`3b2e460`](https://github.com/adonm/vixen/commit/3b2e46039ee661e4cc44b7636114ad9fcd5d4f2d) |

Zuko resolves libghostty/flterm to the exact public fork commits recorded here;
its terminal accessibility semantics and App-Store-compatible iOS packaging
depend on the fork's downstream commits. Package gates reject debug sections
and JIT artifacts; extracted archives must report Impeller under a headless
compositor.

## Parent commands

```sh
just status          # show recursive status and validate local pins
just check           # deterministic local metadata/worktree checks
just check-remotes   # anonymously match every public branch tip to its pin
just check-zuko      # run Zuko's own gate
just check-vixen     # run Vixen's R7 gate
just check-libghostty
just check-maintained # parent, remote, app, and libghostty gates
just verify-clone <parent-commit> # isolated public recursive-clone proof
```

Each child repository remains authoritative for its complete platform and
release checks. The parent does not replace Flutter, plugin, or application CI.
`check-maintained` collects independent child gates; it does not rewrite app
dependency manifests or by itself prove a composed cross-repository build. An
integration PR must record the app-specific command that consumed the changed
package pin.
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
