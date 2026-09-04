# Develop on Linux

Ubuntu 24.04 is the CI and release baseline for this workspace; a Distrobox is
not required. Install Zuko's native Linux packages and run its recipes
directly on the host. An optional Distrobox gives Zuko one predictable set of
compilers, headers, desktop libraries, and test utilities
while retaining normal access to your checkout, editor, display, GPU, and
devices.

Debian, Fedora, and newer Ubuntu releases are useful compatibility checks, but
do not replace the CI baseline. Native macOS and Windows gates still run on
those operating systems, and release recipes keep their own pinned builders
where reproducibility requires one.

Distrobox is a convenience environment, not a security boundary.

## Before you start

Install these on the host:

- [Mise](https://mise.jdx.dev/) for pinned project tools;
- [Just](https://just.systems/) to run workspace recipes; and
- the native Linux packages Zuko documents in
  `apps/zuko/docs/building-clients.md`.

Review the repository's `mise.toml` and each application Mise file before
trusting them. For an exact CI replica, optionally install
[Distrobox](https://distrobox.it/) with Podman or Docker; it shares your home
directory, so one host installation of Mise and Just is available inside it.

## First-time setup

Clone on the host, install the pinned tools, and check the workspace:

```sh
git clone --recurse-submodules https://github.com/adonm/flutter-dev.git
cd flutter-dev
mise trust && mise install
(cd apps/zuko && mise trust && mise install)
eval "$(mise activate bash)"
just status
just check
```

Install Zuko's native package list before running its Linux build
or smoke recipes.

The optional `just devbox-setup` creates `flutter-dev` from the versioned
`quay.io/toolbx/ubuntu-toolbox:24.04` image, installs the shared Linux packages,
and installs the pinned parent and Zuko tools. It can take a while on
the first run; rerunning it is safe.

The prompt opened by `devbox-enter` starts in the workspace with Mise active.
Confirm the checkout before making changes:

```sh
just status
just check
```

For an existing clone without initialized submodules, run `just bootstrap`
from the workspace. It checks out the exact commits recorded by this repository;
do not use `git submodule update --remote` for a reproducible build.

## Daily development

From the host, with Mise active:

```sh
cd /path/to/flutter-dev
eval "$(mise activate bash)"
```

You do not need to rerun setup each day. Move to the project you
are changing and use its own Justfile:

```sh
# Parent pins and orchestration
just check

# Zuko
cd apps/zuko
just check
just build-flutter-linux
cd ../..
```

Start with the narrowest relevant check. Before handing work off, run the owning
child's full documented gate and record the exact command that passed. The
parent's `just check-maintained` collects independent child checks, but it does
not prove every composed SDK or plugin build.

Useful entry points:

| Work | Start with | Broader evidence |
|---|---|---|
| Parent pins or workflows | `just check` | `just check-remotes` |
| Zuko Rust or shared Flutter | `cd apps/zuko && just check` | `just preflight` |
| Zuko Linux client | `cd apps/zuko && just build-flutter-linux` | documented `container-*` compile gate |
| libghostty | `just check-libghostty` | the child repository's own checks |

## What setup owns

Keep configuration in the layer that owns it:

- **APT** provides system compilers, headers, desktop libraries, and utilities.
- **Mise** pins Flutter, Dart, Rust, Just, and other project tools.
- **Justfiles** define supported build, test, package, and release actions.
- **Pinned builders and hosted CI** remain authoritative when a recipe names a
  hermetic release environment.

The shared package set is defined once as `DEVBOX_PACKAGES` in the root
`Justfile`. Android SDK platforms, build-tools, NDK, and Android CMake versions
remain application-owned; follow `apps/zuko/docs/building-clients.md` before an
Android build.

Use a child's bootstrap only when you need its additional one-time setup:

```sh
(cd apps/zuko && mise bootstrap)
```

Mise activation follows directory changes, so the correct child tools become
active when you `cd` into that child.

## Confirm or repair the environment

From the host, verify the core tools and OS identity:

```sh
command -v mise just
grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release
mise current
```

Inside the optional box, `just devbox-check` verifies Ubuntu identity and core
tool resolution without opening a shell:

```sh
just devbox-check
printenv CONTAINER_ID
```

Common fixes:

- **A native package is missing:** install the owning application's package
  list, or provision the box (`just devbox-setup`).
- **A project tool is missing:** rerun the Mise installs, then activate the
  shell again.
- **`distrobox` is missing:** run the `devbox-*` recipes on the host, not from
  inside the box.
- **The box has the wrong image:** the recipe fails rather than silently using
  it. Use a different `DEVBOX_NAME`, or deliberately replace the old box.
- **NVIDIA integration is required:** create the same named, version-pinned box
  manually with Distrobox's `--nvidia` option before running setup.
- **A release builder cannot find Docker:** make the host engine and CLI
  reachable, then follow that application's release guide. Do not replace a
  pinned release builder merely to make a local command shorter.

`DEVBOX_NAME` and `DEVBOX_IMAGE` can deliberately override the defaults. Do not
replace the versioned image with `latest`.

## Optional: OpenCode

Any editor or terminal works. If OpenCode V2 is installed, this host-side
convenience command starts it in the workspace with a private service inside
Ubuntu:

```sh
just devbox-opencode
```

The recipe stops the shared OpenCode service first and uses standalone mode so
the private service exits with the TUI. OpenCode is not required for setup,
builds, tests, or contributions.

## Optional Distrobox recipes

The following recipes remain available but are not required for development:

| Recipe | Purpose |
|---|---|
| `just devbox-setup` | Create and provision the Ubuntu box; run once and after dependency changes |
| `just devbox-enter` | Open the daily Mise-active development shell |
| `just devbox-check` | Check Ubuntu identity and core tool resolution |
| `just devbox-create` | Create only the pinned box |
| `just devbox-opencode` | Optionally launch standalone OpenCode inside the box |
