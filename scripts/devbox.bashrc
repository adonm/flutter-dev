# shellcheck shell=bash

if [[ -f $HOME/.bashrc ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.bashrc"
fi

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || return
cd "$root" || return
# shellcheck disable=SC1091
source /etc/os-release
if [[ $ID != ubuntu || $VERSION_ID != 24.04 ]]; then
  printf '%s\n' 'This development shell requires Ubuntu 24.04.' >&2
  return 1
fi
if ! command -v mise >/dev/null; then
  printf '%s\n' 'Mise is missing. Exit and run: just devbox-setup' >&2
  return 1
fi
eval "$(mise activate bash)"
unset root

printf 'Ubuntu 24.04 development shell (%s)\nWorkspace: %s\nRun just --list to see workspace commands.\n' "${CONTAINER_ID:-unknown}" "$PWD"
