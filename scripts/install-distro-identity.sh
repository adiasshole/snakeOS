#!/usr/bin/env bash
# Install snakeOS distribution identity files under a rootfs (os-release, lsb-release, issue/motd snippets).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOTFS="${1:?usage: install-distro-identity.sh /path/to/rootfs}"

export SNAKEOS_DEBIAN_CODENAME="${SNAKEOS_DEBIAN_CODENAME:-bookworm}"
export SNAKEOS_VARIANT_ID="${SNAKEOS_VARIANT_ID:-server}"
export SNAKEOS_BUILD_ID="${SNAKEOS_BUILD_ID:-$(date -u +%Y%m%d%H%M%S)}"

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" python3 -m snakeos.distinfo install "$ROOTFS"
