#!/bin/bash
# Runs inside the target chroot after packages are installed (standard / systemd edition).
set -euo pipefail

if ! id -u snakeos >/dev/null 2>&1; then
  adduser --disabled-password --gecos '' snakeos
fi
usermod -aG audio,video,input,sudo snakeos || true

systemctl enable NetworkManager.service
systemctl enable ssh.service
systemctl enable greetd.service || true

if [[ -f /etc/greetd/config.toml ]]; then
  :
else
  echo "warn: /etc/greetd/config.toml missing; install config/greetd/config.example.toml" >&2
fi

update-initramfs -u -k all || true
