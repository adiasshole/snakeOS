#!/usr/bin/env bash
# Build a Debian rootfs that can boot with snakeOS as PID 1 (kernel + bootloader still required).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DEBIAN_RELEASE="${DEBIAN_RELEASE:-bookworm}"
ROOTFS_DIR="${ROOTFS_DIR:-./build/rootfs}"
MIRROR="${MIRROR:-http://deb.debian.org/debian}"
SNAKEOS_SERVICES_TEMPLATE="${SNAKEOS_SERVICES_TEMPLATE:-config/services.baremetal.example.toml}"
SNAKEOS_EXTRA_PKGS="${SNAKEOS_EXTRA_PKGS:-}"
SNAKEOS_INSTALL_GREETD_CONFIG="${SNAKEOS_INSTALL_GREETD_CONFIG:-0}"
SNAKEOS_CHROOT_POST_SCRIPT="${SNAKEOS_CHROOT_POST_SCRIPT:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (debootstrap + chroot)." >&2
  exit 1
fi

mkdir -p "$(dirname "$ROOTFS_DIR")"
debootstrap --variant=minbase --merged-usr "$DEBIAN_RELEASE" "$ROOTFS_DIR" "$MIRROR"

install_pkgs="ca-certificates iproute2 openssh-server python3 python3-pip util-linux"
if [[ -n "${SNAKEOS_EXTRA_PKGS// }" ]]; then
  install_pkgs="${install_pkgs} ${SNAKEOS_EXTRA_PKGS}"
fi

chroot "$ROOTFS_DIR" /bin/bash -c "
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends ${install_pkgs}
"

install -d -m0755 "$ROOTFS_DIR/opt/snakeos"
rsync -a --delete \
  --exclude build --exclude .venv --exclude .git \
  ./ "$ROOTFS_DIR/opt/snakeos/"

chroot "$ROOTFS_DIR" /bin/bash -c "
  set -euo pipefail
  pip3 install --no-cache-dir --break-system-packages -e /opt/snakeos
"

export SNAKEOS_DEBIAN_CODENAME="${SNAKEOS_DEBIAN_CODENAME:-$DEBIAN_RELEASE}"
export SNAKEOS_VARIANT_ID="${SNAKEOS_VARIANT_ID:-server}"
export SNAKEOS_BUILD_ID="${SNAKEOS_BUILD_ID:-$(date -u +%Y%m%d%H%M%S)}"
PYTHONPATH="$REPO_ROOT" python3 -m snakeos.distinfo install "$ROOTFS_DIR"

install -D -m0644 "$SNAKEOS_SERVICES_TEMPLATE" "$ROOTFS_DIR/etc/snakeos/services.toml"

if [[ "$SNAKEOS_INSTALL_GREETD_CONFIG" == "1" ]] && [[ -f "config/greetd/config.example.toml" ]]; then
  install -D -m0644 "config/greetd/config.example.toml" "$ROOTFS_DIR/etc/greetd/config.toml"
fi

if [[ -n "${SNAKEOS_CHROOT_POST_SCRIPT}" ]]; then
  install -m0755 "$SNAKEOS_CHROOT_POST_SCRIPT" "$ROOTFS_DIR/tmp/snakeos-chroot-post.sh"
  chroot "$ROOTFS_DIR" /bin/bash /tmp/snakeos-chroot-post.sh
  rm -f "$ROOTFS_DIR/tmp/snakeos-chroot-post.sh"
fi

echo "Rootfs ready at $ROOTFS_DIR"
echo "Experimental (Python PID 1): install kernel + bootloader, then boot with:"
echo "  init=/usr/bin/python3 -m snakeos init --config /etc/snakeos/services.toml"
echo "For a mainstream installable system (systemd + installer), use scripts/build-rootfs-debian-standard.sh instead."
