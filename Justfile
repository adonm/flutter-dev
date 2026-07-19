# Parent-level submodule orchestration. Child build systems remain authoritative.
set shell := ["bash", "-euo", "pipefail", "-c"]

DEVBOX_NAME := env_var_or_default("DEVBOX_NAME", "flutter-dev")
DEVBOX_IMAGE := env_var_or_default("DEVBOX_IMAGE", "quay.io/toolbx/ubuntu-toolbox:24.04")
DEVBOX_PACKAGES := "at-spi2-core binutils build-essential cage clang cmake curl dbus-daemon flatpak flatpak-builder git gir1.2-atspi-2.0 ibus ibus-gtk4 ibus-mozc jq libegl-dev libgl-dev libgtk-4-dev libsecret-1-dev libwayland-dev mesa-vulkan-drivers ninja-build openjdk-17-jdk-headless ostree pkg-config python3 python3-gi ripgrep shellcheck unzip wayland-protocols wtype xz-utils"

default:
    @just --list --list-heading $'flutter-dev recipes:\n'

# Create the version-pinned Ubuntu development box if it does not exist.
[group('development')]
devbox-create:
    @command -v distrobox >/dev/null || { printf '%s\n' 'distrobox is required on the host; see docs/DEVELOPMENT.md' >&2; exit 1; }; image="$(distrobox list --no-color | awk -F '|' -v name='{{ DEVBOX_NAME }}' 'NR > 1 { box=$2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", box); if (box == name) { image=$4; gsub(/^[[:space:]]+|[[:space:]]+$/, "", image); print image } }')"; if [[ -n "$image" ]]; then [[ "$image" == '{{ DEVBOX_IMAGE }}' ]] || { printf '%s\n' "{{ DEVBOX_NAME }} uses $image, expected {{ DEVBOX_IMAGE }}" >&2; exit 1; }; printf '%s\n' "Distrobox {{ DEVBOX_NAME }} already exists"; else distrobox create --yes --name '{{ DEVBOX_NAME }}' --image '{{ DEVBOX_IMAGE }}'; fi

# Install Ubuntu packages and the parent/application Mise tools.
[group('development')]
devbox-setup: devbox-create
    @distrobox enter '{{ DEVBOX_NAME }}' -- bash -lc 'set -euo pipefail; test "${CONTAINER_ID:-}" = "{{ DEVBOX_NAME }}" || { printf "%s\n" "not inside {{ DEVBOX_NAME }}" >&2; exit 1; }; . /etc/os-release; test "$ID" = ubuntu && test "$VERSION_ID" = 24.04 || { printf "%s\n" "{{ DEVBOX_NAME }} must be Ubuntu 24.04" >&2; exit 1; }; command -v mise >/dev/null || { printf "%s\n" "mise is missing; install it on the shared host home first" >&2; exit 1; }; sudo apt-get update; sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends {{ DEVBOX_PACKAGES }}; cd "{{ justfile_directory() }}"; mise trust; mise install; (cd apps/zuko && mise trust && mise install); (cd apps/vixen && mise trust && mise install); printf "%s\n" "Ubuntu development environment is ready. Run: just devbox-enter"'

# Verify Ubuntu identity and the core workspace toolchains.
[group('development')]
devbox-check: devbox-create
    @distrobox enter '{{ DEVBOX_NAME }}' -- bash -lc 'set -euo pipefail; cd "{{ justfile_directory() }}"; command -v mise >/dev/null || { printf "%s\n" "mise is missing; run just devbox-setup" >&2; exit 1; }; eval "$(mise activate bash)"; test "${CONTAINER_ID:-}" = "{{ DEVBOX_NAME }}" || { printf "%s\n" "not inside {{ DEVBOX_NAME }}" >&2; exit 1; }; . /etc/os-release; test "$ID" = ubuntu && test "$VERSION_ID" = 24.04 || { printf "%s\n" "{{ DEVBOX_NAME }} must be Ubuntu 24.04" >&2; exit 1; }; command -v git mise just flutter dart clang cmake ninja pkg-config cage; git status --short --branch; flutter --version; (cd apps/zuko && mise exec -- rustc --version); (cd apps/vixen && mise exec -- rustc --version)'

# Enter the workspace in an interactive Mise-active shell.
[group('development')]
devbox-enter: devbox-create
    @distrobox enter '{{ DEVBOX_NAME }}' -- bash --rcfile '{{ justfile_directory() }}/scripts/devbox.bashrc' -i

# Launch OpenCode with a private service inside Ubuntu.
[group('development')]
devbox-opencode: devbox-create
    @distrobox enter '{{ DEVBOX_NAME }}' -- bash -lc 'set -euo pipefail; cd "{{ justfile_directory() }}"; command -v mise >/dev/null || { printf "%s\n" "mise is missing; run just devbox-setup" >&2; exit 1; }; eval "$(mise activate bash)"; test "${CONTAINER_ID:-}" = "{{ DEVBOX_NAME }}" || { printf "%s\n" "not inside {{ DEVBOX_NAME }}" >&2; exit 1; }; . /etc/os-release; test "$ID" = ubuntu && test "$VERSION_ID" = 24.04 || { printf "%s\n" "{{ DEVBOX_NAME }} must be Ubuntu 24.04" >&2; exit 1; }; command -v opencode2 >/dev/null || { printf "%s\n" "OpenCode V2 is not installed; it is optional" >&2; exit 1; }; opencode2 service stop || true; exec opencode2 --standalone'

[group('workspace')]
bootstrap:
    git submodule sync --recursive
    git submodule update --init --recursive
    just check

[group('workspace')]
status:
    git submodule status --recursive
    python3 scripts/submodules.py check

[group('workspace')]
check:
    git diff --check
    git diff --cached --check
    git diff --exit-code -- Justfile scripts/submodules.py
    python3 scripts/submodules.py check
    python3 scripts/flutter_sdk.py check-config
    python3 -m unittest scripts/test_flutter_sdk.py

[group('workspace')]
check-actions:
    actionlint .github/workflows/*.yml

[group('sdk')]
check-flutter-sdk:
    python3 scripts/flutter_sdk.py check-config
    python3 -m unittest scripts/test_flutter_sdk.py

[group('workspace')]
check-remotes:
    python3 scripts/submodules.py check --remote

[group('workspace')]
verify-clone reference destination='.tmp/ref/flutter-dev-public':
    python3 scripts/submodules.py clone "https://github.com/adonm/flutter-dev.git" "{{ reference }}" "{{ destination }}"

[group('workspace')]
verify-clone-local reference destination='.tmp/ref/flutter-dev-local':
    python3 scripts/submodules.py clone "." "{{ reference }}" "{{ destination }}"

[group('workspace')]
pin path:
    python3 scripts/submodules.py pin "{{ path }}"
    git add -- submodules.json "{{ path }}"
    python3 scripts/submodules.py check

[group('apps')]
check-zuko:
    cd apps/zuko && mise exec -- just check

[group('apps')]
check-vixen:
    cd apps/vixen && mise exec -- just test-r7

[group('apps')]
check-apps: check-zuko check-vixen

[group('dependencies')]
check-libghostty:
    cd packages/libghostty && mise exec -- flutter pub get --enforce-lockfile
    cd packages/libghostty && mise exec -- dart run melos run check

[group('quality')]
check-maintained: check check-remotes check-apps check-libghostty
