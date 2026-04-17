#!/usr/bin/env bash
# Debian rootfs aimed at a daily-driver Wayland desktop (snakeOS remains PID 1).
# Many desktop packages assume logind/PAM integration; read README “Distro vision” before relying on this in production.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export ROOTFS_DIR="${ROOTFS_DIR:-./build/rootfs-desktop}"
export SNAKEOS_SERVICES_TEMPLATE="${SNAKEOS_SERVICES_TEMPLATE:-config/services.desktop.example.toml}"
export SNAKEOS_INSTALL_GREETD_CONFIG="${SNAKEOS_INSTALL_GREETD_CONFIG:-1}"
export SNAKEOS_CHROOT_POST_SCRIPT="${SNAKEOS_CHROOT_POST_SCRIPT:-$SCRIPT_DIR/chroot-post-desktop.sh}"

export SNAKEOS_EXTRA_PKGS="${SNAKEOS_EXTRA_PKGS:-bluez dbus fonts-dejavu-core foot greetd libegl-mesa0 mesa-vulkan-drivers network-manager pipewire polkitd sudo sway wireplumber seatd}"
export SNAKEOS_VARIANT_ID="${SNAKEOS_VARIANT_ID:-desktop}"

exec "$SCRIPT_DIR/build-rootfs-debian.sh"
