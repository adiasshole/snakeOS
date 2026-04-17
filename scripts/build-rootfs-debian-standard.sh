#!/usr/bin/env bash
# "Standard edition" Debian rootfs: systemd PID 1, udev, typical desktop stack, and a Debian
# kernel metapackage (tracks new kernels as you move Debian releases / backports).
#
# Defaults:
#   DEBIAN_RELEASE=trixie        (Debian testing — newer kernels than stable)
#   SNAKEOS_LINUX_METAPACKAGE=linux-image-amd64
#
# Stable users who want newer kernels without moving the whole OS:
#   DEBIAN_RELEASE=bookworm SNAKEOS_ENABLE_BACKPORTS=1 ./scripts/build-rootfs-debian-standard.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DEBIAN_RELEASE="${DEBIAN_RELEASE:-trixie}"
ROOTFS_DIR="${ROOTFS_DIR:-./build/rootfs-standard}"
MIRROR="${MIRROR:-http://deb.debian.org/debian}"
SNAKEOS_LINUX_METAPACKAGE="${SNAKEOS_LINUX_METAPACKAGE:-linux-image-amd64}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (debootstrap + chroot)." >&2
  exit 1
fi

mkdir -p "$(dirname "$ROOTFS_DIR")"
debootstrap --merged-usr "$DEBIAN_RELEASE" "$ROOTFS_DIR" "$MIRROR"

if [[ "${SNAKEOS_ENABLE_NONFREE_FIRMWARE:-1}" == "1" ]]; then
  install -d -m0755 "$ROOTFS_DIR/etc/apt/sources.list.d"
  echo "deb ${MIRROR} ${DEBIAN_RELEASE} main contrib non-free-firmware" \
    >"$ROOTFS_DIR/etc/apt/sources.list.d/snakeos-extra-components.list"
fi

if [[ "${SNAKEOS_ENABLE_BACKPORTS:-0}" == "1" ]] && [[ "$DEBIAN_RELEASE" == "bookworm" ]]; then
  echo "deb http://deb.debian.org/debian bookworm-backports main contrib non-free-firmware" \
    >"$ROOTFS_DIR/etc/apt/sources.list.d/bookworm-backports.list"
fi

chroot "$ROOTFS_DIR" /bin/bash -c "
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends \
    apparmor \
    bluez \
    chrony \
    dbus \
    dbus-user-session \
    efibootmgr \
    firmware-linux-free \
    fonts-dejavu-core \
    foot \
    grub-efi-amd64 \
    greetd \
    initramfs-tools \
    iproute2 \
    libegl-mesa0 \
    mesa-vulkan-drivers \
    network-manager \
    openssh-server \
    pipewire \
    polkitd \
    python3 \
    python3-pip \
    rsync \
    sudo \
    sway \
    systemd \
    systemd-sysv \
    udev \
    util-linux \
    wireplumber
"

kernel_install_cmd="apt-get install -y --no-install-recommends ${SNAKEOS_LINUX_METAPACKAGE}"
if [[ "${SNAKEOS_ENABLE_BACKPORTS:-0}" == "1" ]] && [[ "$DEBIAN_RELEASE" == "bookworm" ]]; then
  kernel_install_cmd="apt-get install -y -t bookworm-backports --no-install-recommends ${SNAKEOS_LINUX_METAPACKAGE}"
fi

chroot "$ROOTFS_DIR" /bin/bash -c "
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  ${kernel_install_cmd}
"

install -d -m0755 "$ROOTFS_DIR/opt/snakeos"
rsync -a --delete \
  --exclude build --exclude .venv --exclude .git \
  ./ "$ROOTFS_DIR/opt/snakeos/"

chroot "$ROOTFS_DIR" /bin/bash -c "
  set -euo pipefail
  pip3 install --no-cache-dir --break-system-packages -e /opt/snakeos
"

if [[ -f "config/greetd/config.example.toml" ]]; then
  install -D -m0644 "config/greetd/config.example.toml" "$ROOTFS_DIR/etc/greetd/config.toml"
fi

install -D -m0644 "config/snakeos/systemd-edition.txt" "$ROOTFS_DIR/etc/snakeos/execution-model.txt"

export SNAKEOS_DEBIAN_CODENAME="${SNAKEOS_DEBIAN_CODENAME:-$DEBIAN_RELEASE}"
export SNAKEOS_VARIANT_ID="${SNAKEOS_VARIANT_ID:-standard-desktop}"
export SNAKEOS_BUILD_ID="${SNAKEOS_BUILD_ID:-$(date -u +%Y%m%d%H%M%S)}"
PYTHONPATH="$REPO_ROOT" python3 -m snakeos.distinfo install "$ROOTFS_DIR"

install -m0755 "$SCRIPT_DIR/chroot-post-standard-desktop.sh" "$ROOTFS_DIR/tmp/snakeos-chroot-post.sh"
chroot "$ROOTFS_DIR" /bin/bash /tmp/snakeos-chroot-post.sh
rm -f "$ROOTFS_DIR/tmp/snakeos-chroot-post.sh"

echo
echo "Standard rootfs ready at $ROOTFS_DIR"
echo "- Init: systemd (/sbin/init) with udev, logind, cgroups, NetworkManager — mainstream Linux userspace."
echo "- Kernel package: ${SNAKEOS_LINUX_METAPACKAGE} (from ${DEBIAN_RELEASE}; enable SNAKEOS_ENABLE_BACKPORTS=1 on bookworm for a newer kernel)."
echo "- Install to disk from a live/rescue environment:"
echo "    sudo ./scripts/live-install-to-disk.sh --disk /dev/DISK --i-understand-this-will-erase --source \"$ROOTFS_DIR\""
