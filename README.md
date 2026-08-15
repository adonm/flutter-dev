# flutter-dev

`flutter-dev` is the integration workspace for the [Zuko](https://github.com/adonm/zuko)
and [Vixen](https://github.com/adonm/vixen) Flutter applications. It pins the
applications, the Flutter SDK work they currently require, and maintained
package/plugin forks as independent Git submodules.

This is a meta-repository, not a source-history merger. Each child repository
keeps its own issues, releases, build system, license, and upstream pull
requests. The parent records one reproducible combination of exact commits.

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
| `apps/zuko` | Private remote shell application and Flutter clients (official beta, GTK3) |
| `apps/vixen` | Flutter-hosted browser application and renderer (official beta) |
| `sdk/flutter` | Flutter framework fork (GTK4 integration, retained for reference) |
| `sdk/flutter-packages` | Flutter package fork, currently `url_launcher` (retained) |
| `packages/libghostty` | Ghostty terminal bindings and `flterm` widget |
| `plugins/gtk.dart` | GTK bindings (GTK4 work retained for reference) |
| `plugins/screen_retriever` | Screen discovery plugin (retained) |
| `plugins/window_manager` | Desktop window management plugin (retained) |
| `plugins/yaru_window.dart` | Yaru window integration (retained) |

`.gitmodules` defines clone URLs and maintenance branches. `submodules.json`
records the reviewed origins, canonical upstreams, and exact expected commits.
The parent gitlinks remain Git's authoritative checkout pins.

## GTK4 validation targets

Zuko now consumes the official Flutter beta (GTK3 embedder with Impeller) and
stock pub.dev plugins; the fork SDK, engine, and plugin pins below are
retained as reviewed history for the GTK4 work and any future re-adoption:

| App | Release commit |
|---|---|
| Zuko 0.10.13 | [`0cc8490`](https://github.com/adonm/zuko/commit/0cc8490d7d82) |
| Vixen 0.1.7 | [`24d9ed5`](https://github.com/adonm/vixen/commit/24d9ed5bf68294ac2ca3c373c957c2cd36484986) |

Vixen installs the official Google beta archive, and Zuko installs the same
official beta (3.48.0-0.1.pre) through Mise. Zuko resolves libghostty/flterm
to the exact public fork commits recorded here. Package gates reject debug
sections and JIT artifacts; extracted archives must report Impeller under a
headless compositor.

### CI-built Linux GTK4 engine

The manually dispatched [`Pinned GTK4 Flutter engine`](.github/workflows/gtk4-engine.yml)
workflow checks out the exact `sdk/flutter` gitlink, pins depot_tools, builds the
Linux x64 release engine on Ubuntu 24.04, runs the GTK4 engine tests under a
headless compositor, rejects GTK3/debug linkage, and uploads the library with
its SHA-256 and build metadata. The build job has read-only repository
permissions.

Publication is a separate, manually dispatched
[`Publish pinned GTK4 Flutter engine`](.github/workflows/publish-gtk4-engine.yml)
workflow. It accepts one reviewed Actions artifact ID and library SHA-256,
revalidates the artifact, and creates a checksummed GitHub Release whose tag and
assets become immutable when the draft is published. Downstream installers pin
the release tag, SDK revision, engine content hash, and library SHA-256 before
atomically adding the GTK4 library to Flutter's normal Linux release cache.

Published engine:

- Release: [`flutter-engine-gtk4-9351f0f780c…`](https://github.com/adonm/flutter-dev/releases/tag/flutter-engine-gtk4-9351f0f780c7936af1e9b5fef0d21e8b01ee7cb6)
- SDK revision: `9351f0f780c7936af1e9b5fef0d21e8b01ee7cb6`
- Engine build content hash: `e02e791b89b09022cb5d56ebc08600c2b9233ae9`
- Official precache content hash: `e723cb127ef0d4153cc41a0b390c837b47e5f573`
- Library SHA-256: `8afa69aebce8158f3dc4eef184d4bafb10e0de1e216f9d2678d37d47508a841a`
- Build: [GitHub Actions run 31864684343](https://github.com/adonm/flutter-dev/actions/runs/31864684343)
- Publication: [GitHub Actions run 31866380132](https://github.com/adonm/flutter-dev/actions/runs/31866380132)

### Mise-compatible host SDK archives

The manually dispatched
[`Pinned cross-platform Flutter SDK`](.github/workflows/flutter-sdk.yml) workflow
builds native Linux x64, macOS Arm64, macOS x64, and Windows x64 archives from
the exact framework pin. Each archive contains the matching Dart SDK and only
the host's reviewed precache set. Linux additionally contains the immutable
GTK4 engine above. The aggregate artifact includes per-archive SHA-256 files,
`flutter-sdk-manifest.json`, and a generated `flutter-sdk.mise.toml` platform
table for Mise's `http:flutter` backend.

Published SDK:

- Release: [`flutter-sdk-9351f0f780c…`](https://github.com/adonm/flutter-dev/releases/tag/flutter-sdk-9351f0f780c7936af1e9b5fef0d21e8b01ee7cb6)
- Build: [GitHub Actions run 31867127710](https://github.com/adonm/flutter-dev/actions/runs/31867127710)
- Framework: `3.47.0-1.0.pre-672` at `9351f0f780c7936af1e9b5fef0d21e8b01ee7cb6`
- Dart: `3.14.0-134.0.dev`

[`Publish pinned cross-platform Flutter SDK`](.github/workflows/publish-flutter-sdk.yml)
accepts only the aggregate artifact from that successful workflow, revalidates
its run and byte identities, and publishes an immutable release. Applications
therefore download one checksum-pinned archive through Mise instead of cloning,
deepening, and precaching Flutter independently in every CI job.

## Parent commands

```sh
just status          # show recursive status and validate local pins
just check           # deterministic local metadata/worktree checks
just check-remotes   # anonymously match every public branch tip to its pin
just check-flutter-sdk # validate the host SDK artifact contract
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
