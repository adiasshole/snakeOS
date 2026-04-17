#!/bin/bash
# Runs inside the target chroot (as invoked by build-rootfs-debian.sh).
set -euo pipefail

if ! id -u snakeos >/dev/null 2>&1; then
  adduser --disabled-password --gecos '' snakeos
fi
usermod -aG audio,video,input,sudo snakeos || true
