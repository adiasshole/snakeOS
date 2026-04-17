#!/usr/bin/env bash
# Copy a snakeOS rootfs tree onto a disk, create EFI + ext4, install GRUB for UEFI.
# Run from a Linux live/rescue environment with: parted dosfstools e2fsprogs rsync grub-efi-amd64 efibootmgr
set -euo pipefail

DISK=""
SOURCE=""
ASSUME_FIRST=false
ERASE_OK=0

usage() {
  sed -n '1,140p' <<'EOF'
Usage:
  sudo ./scripts/live-install-to-disk.sh --disk /dev/nvme0n1 --source /path/to/rootfs \\
      --i-understand-this-will-erase

Options:
  --disk DEV          Whole disk device (partition table will be replaced).
  --source DIR        Unpacked rootfs (e.g. ./build/rootfs-standard).
  --assume-first-disk Pick the first non-removable disk (VM convenience; still dangerous).
  --i-understand-this-will-erase   Required. You will be prompted to type ERASE.
EOF
}

confirm_erase() {
  echo "About to destroy the partition table on ${DISK} and copy ${SOURCE} onto it." >&2
  echo "Type ERASE to continue:" >&2
  read -r line
  if [[ "$line" != "ERASE" ]]; then
    echo "Aborted." >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --disk) DISK="${2:?}"; shift 2 ;;
    --source) SOURCE="${2:?}"; shift 2 ;;
    --assume-first-disk) ASSUME_FIRST=true; shift ;;
    --i-understand-this-will-erase) ERASE_OK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

if [[ "$ERASE_OK" != "1" ]]; then
  echo "Refusing to run without --i-understand-this-will-erase" >&2
  usage
  exit 2
fi

if [[ "$ASSUME_FIRST" == true ]]; then
  DISK="$(lsblk -dn -o NAME,TYPE,RM | awk '$2=="disk" && $3==0 {print "/dev/" $1; exit}')"
  if [[ -z "${DISK}" ]]; then
    echo "Could not auto-detect a non-removable disk." >&2
    exit 1
  fi
fi

if [[ -z "${DISK}" || -z "${SOURCE}" ]]; then
  usage
  exit 2
fi

if [[ ! -d "$SOURCE" ]]; then
  echo "source is not a directory: $SOURCE" >&2
  exit 2
fi

if ! [[ -b "$DISK" ]]; then
  echo "disk is not a block device: $DISK" >&2
  exit 2
fi

confirm_erase

command -v parted >/dev/null
command -v mkfs.fat >/dev/null
command -v mkfs.ext4 >/dev/null
command -v rsync >/dev/null

parted -s "$DISK" mklabel gpt
parted -s "$DISK" mkpart ESP fat32 1MiB 551MiB
parted -s "$DISK" set 1 esp on
parted -s "$DISK" mkpart snakeos-root ext4 551MiB 100%

if command -v partprobe >/dev/null 2>&1; then
  partprobe "$DISK" || true
fi
sleep 1

if [[ -b "${DISK}p1" ]]; then
  ESP="${DISK}p1"
  ROOT="${DISK}p2"
elif [[ -b "${DISK}1" ]]; then
  ESP="${DISK}1"
  ROOT="${DISK}2"
else
  echo "Could not find partitions on ${DISK} (expected ${DISK}1 or ${DISK}p1)." >&2
  exit 1
fi

mkfs.fat -F32 -n SNAKEEFI "$ESP"
mkfs.ext4 -F -L snakeos-root "$ROOT"

WORK="$(mktemp -d)"
cleanup() {
  mountpoint -q "$WORK/target/boot/efi" 2>/dev/null && umount "$WORK/target/boot/efi" || true
  mountpoint -q "$WORK/target/dev" 2>/dev/null && umount "$WORK/target/dev" || true
  mountpoint -q "$WORK/target/proc" 2>/dev/null && umount "$WORK/target/proc" || true
  mountpoint -q "$WORK/target/sys" 2>/dev/null && umount "$WORK/target/sys" || true
  mountpoint -q "$WORK/target" 2>/dev/null && umount "$WORK/target" || true
  rm -rf "$WORK"
}
trap cleanup EXIT

mkdir -p "$WORK/target"
mount "$ROOT" "$WORK/target"
mkdir -p "$WORK/target/boot/efi"
mount "$ESP" "$WORK/target/boot/efi"

rsync -aHAX --info=progress2 \
  --exclude /proc --exclude /sys --exclude /dev --exclude /run \
  "$SOURCE/" "$WORK/target/"

mkdir -p "$WORK/target/proc" "$WORK/target/sys" "$WORK/target/dev" "$WORK/target/run"

ROOT_UUID="$(blkid -s UUID -o value "$ROOT")"
ESP_UUID="$(blkid -s UUID -o value "$ESP" 2>/dev/null || true)"

{
  echo "UUID=${ROOT_UUID} / ext4 defaults 0 1"
  if [[ -n "${ESP_UUID}" ]]; then
    echo "UUID=${ESP_UUID} /boot/efi vfat umask=0077 0 1"
  else
    echo "LABEL=SNAKEEFI /boot/efi vfat umask=0077 0 1"
  fi
} >"$WORK/target/etc/fstab"

mount --bind /dev "$WORK/target/dev"
mount --bind /proc "$WORK/target/proc"
mount --bind /sys "$WORK/target/sys"

chroot "$WORK/target" grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=snakeOS --recheck --no-floppy
chroot "$WORK/target" update-grub

umount "$WORK/target/sys" "$WORK/target/proc" "$WORK/target/dev" || true
umount "$WORK/target/boot/efi"
umount "$WORK/target"

trap - EXIT
rm -rf "$WORK"

echo "Done. EFI + root installed on $DISK (UEFI entry: snakeOS)."
