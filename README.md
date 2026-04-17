# snakeOS

snakeOS is a **Linux distribution** built around a **Python-first policy layer** (`snakeos` tooling, branding, and optional experimental init), while staying **feature-compatible with modern Linux systems** when you use the **recommended systemd-based edition**.

## Two editions (pick one)

### Standard edition (recommended): installable, mainstream-compatible

- **PID 1:** **systemd** (same service model, cgroups, logind, udev, journald, and dbus integration as Debian/Ubuntu/Fedora-style systems).
- **Kernel:** Debian’s **`linux-image-amd64`** metapackage (tracks new kernels as Debian moves). Defaults to **`DEBIAN_RELEASE=trixie`** (testing) for **newer kernels than stable** without pinning a custom mainline build. You can switch to **stable + backports** or change the metapackage (e.g. cloud kernel) with environment variables (see below).
- **Install:** build a rootfs, then run the **disk installer** from a live/rescue environment — same overall flow as many minimal distros (partition → rsync → `grub-install`).

```bash
sudo ./scripts/build-rootfs-debian-standard.sh
sudo ./scripts/live-install-to-disk.sh --disk /dev/nvme0n1 --source ./build/rootfs-standard --i-understand-this-will-erase
```

The `snakeOS` Python stack is still installed (`pip install -e /opt/snakeos`) for branding (`/etc/os-release`), future admin CLIs, systemd generators, or policy modules — **not** as `/sbin/init`. See `config/snakeos/systemd-edition.txt` on the built rootfs.

### Experimental edition: Python `snakeos init` as PID 1

- For containers, labs, or minimal environments where you explicitly want **`python -m snakeos init`** driving `services.toml`.
- **Not** feature-parity with full desktop Linux (udev/logind/cgroups integration is on you). Use the **standard edition** for a daily-driver that behaves like “every other distro”.

```bash
sudo ./scripts/build-rootfs-debian-desktop.sh   # Python PID1-oriented userspace stack
# boot with: init=/usr/bin/python3 -m snakeos init --config /etc/snakeos/services.toml
```

## What is included today

- **Init options**
  - **systemd rootfs builder** + **UEFI disk installer** (standard edition).
  - **Python PID 1** supervisor + declarative **`services.toml`** (experimental edition).
- **Declarative `services.toml`** (experimental init path):
  - **`[[mount]]`**, **`[meta]`**, **`[[service]]`** with `oneshot` / `simple`, `depends_on`, `restart`, `require_path`.
- **Example `services.toml` profiles** under `config/services*.toml` (experimental / container / bare metal / desktop-without-systemd).
- **Greeter template:** `config/greetd/config.example.toml`.
- **Distribution identity:** `distribution/` templates + `python -m snakeos.distinfo` / `snakeos distro …` (see Development).
- **Rootfs builders**
  - `scripts/build-rootfs-debian-standard.sh` — **systemd + udev + NetworkManager + Wayland stack + kernel + GRUB packages**.
  - `scripts/build-rootfs-debian.sh` / `scripts/build-rootfs-debian-desktop.sh` — smaller / Python-init-oriented images.
- **Disk install:** `scripts/live-install-to-disk.sh` (EFI + ext4 + rsync + `grub-install` + `/etc/fstab` by UUID).
- **Optional image skeleton:** `mkosi/` (expects `./build/rootfs-standard` by default).

## Kernel freshness (Debian metapackage model)

The standard edition installs **`linux-image-amd64`**, which tracks the **latest kernel in the Debian suite you selected**:

| Goal | Typical settings |
|------|------------------|
| Newer kernels without waiting for stable point releases | Default **`DEBIAN_RELEASE=trixie`** (testing). |
| Stable userspace + newer kernel | `DEBIAN_RELEASE=bookworm SNAKEOS_ENABLE_BACKPORTS=1` (pulls kernel from **bookworm-backports**). |
| VMs / cloud images | `SNAKEOS_LINUX_METAPACKAGE=linux-image-cloud-amd64`. |

“Latest **mainline** Linus tree” is a **different** product than “latest **Debian** kernel”; if you want true mainline, add your own kernel packages or DKMS flow — the repo intentionally stays on **Debian’s supported kernel ABI** for compatibility with Debian userspace and modules.

## Try it in a container (Python stack only)

```bash
docker build -t snakeos:dev .
docker run --rm -it snakeos:dev
```

## Distro vision (short)

1. **Standard path:** systemd rootfs + installer + (optional) apt archive + Calamares later.
2. **Experimental path:** Python init for research and embedded-style images.
3. **Hardening:** signed EFI, Secure Boot, automated QEMU tests, release channels.

## Customize `/etc/os-release` fields

See `snakeos/distinfo.py` for `SNAKEOS_*` environment variables (`VERSION`, URLs, `VARIANT_ID`, `BUILD_ID`, …).

```bash
PYTHONPATH=. python -m snakeos.distinfo print-os-release
# or
PYTHONPATH=. python -m snakeos distro print-os-release
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m snakeos init --config config/services.example.toml
```

Running `snakeos init` outside PID 1 is supported for development; full mounts apply on real PID 1 only (`snakeos/boot.py`).
