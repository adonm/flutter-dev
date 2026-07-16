# Parent-level submodule orchestration. Child build systems remain authoritative.
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list --list-heading $'flutter-dev recipes:\n'

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
