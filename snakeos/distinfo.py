from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path


@dataclass(frozen=True)
class DistroIdentity:
    version: str
    variant: str
    variant_id: str
    snakeos_codename: str
    debian_codename: str
    build_id: str
    home_url: str
    documentation_url: str
    support_url: str
    bug_report_url: str


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _source_tree_root() -> Path:
    return _package_dir().parent


def template_dir() -> Path:
    bundled = _package_dir() / "dist_bundled"
    if bundled.is_dir() and (bundled / "os-release.in").is_file():
        return bundled
    return _source_tree_root() / "distribution"


def read_project_version(pyproject: Path | None = None) -> str:
    import tomllib

    if pyproject is not None:
        data = tomllib.loads(pyproject.read_bytes().decode())
        ver = data.get("project", {}).get("version")
        if isinstance(ver, str) and ver.strip():
            return ver.strip()
        raise ValueError("pyproject.toml missing [project].version")

    candidate = _source_tree_root() / "pyproject.toml"
    if candidate.is_file():
        return read_project_version(candidate)

    return metadata.version("snakeos")


def load_identity_from_environ() -> DistroIdentity:
    import os

    return DistroIdentity(
        version=os.environ.get("SNAKEOS_VERSION") or read_project_version(),
        variant=os.environ.get("SNAKEOS_VARIANT", "snakeOS"),
        variant_id=os.environ.get("SNAKEOS_VARIANT_ID", "generic"),
        snakeos_codename=os.environ.get("SNAKEOS_VERSION_CODENAME", "rolling"),
        debian_codename=os.environ.get("SNAKEOS_DEBIAN_CODENAME", "bookworm"),
        build_id=os.environ.get("SNAKEOS_BUILD_ID", "local"),
        home_url=os.environ.get("SNAKEOS_HOME_URL", "https://example.invalid/snakeos"),
        documentation_url=os.environ.get(
            "SNAKEOS_DOCUMENTATION_URL", "https://example.invalid/snakeos/docs"
        ),
        support_url=os.environ.get("SNAKEOS_SUPPORT_URL", "https://example.invalid/snakeos/support"),
        bug_report_url=os.environ.get("SNAKEOS_BUG_REPORT_URL", "https://example.invalid/snakeos/issues"),
    )


def render_os_release(ident: DistroIdentity) -> str:
    template = (template_dir() / "os-release.in").read_text(encoding="utf-8")
    return template.format(
        version=ident.version,
        variant=ident.variant,
        variant_id=ident.variant_id,
        snakeos_codename=ident.snakeos_codename,
        debian_codename=ident.debian_codename,
        build_id=ident.build_id,
        home_url=ident.home_url,
        documentation_url=ident.documentation_url,
        support_url=ident.support_url,
        bug_report_url=ident.bug_report_url,
    )


def render_lsb_release(ident: DistroIdentity) -> str:
    template = (template_dir() / "lsb-release.in").read_text(encoding="utf-8")
    return template.format(
        version=ident.version,
        variant=ident.variant,
        variant_id=ident.variant_id,
        snakeos_codename=ident.snakeos_codename,
        debian_codename=ident.debian_codename,
    )


def install_identity(rootfs: Path, ident: DistroIdentity | None = None) -> None:
    ident = ident or load_identity_from_environ()
    os_release = render_os_release(ident)
    lsb = render_lsb_release(ident)
    td = template_dir()

    (rootfs / "etc").mkdir(parents=True, exist_ok=True)
    (rootfs / "usr" / "lib").mkdir(parents=True, exist_ok=True)
    (rootfs / "etc" / "issue.d").mkdir(parents=True, exist_ok=True)
    (rootfs / "etc" / "motd.d").mkdir(parents=True, exist_ok=True)

    (rootfs / "etc" / "os-release").write_text(os_release + "\n", encoding="utf-8")
    (rootfs / "usr" / "lib" / "os-release").write_text(os_release + "\n", encoding="utf-8")
    (rootfs / "etc" / "lsb-release").write_text(lsb + "\n", encoding="utf-8")

    (rootfs / "etc" / "issue.d" / "snakeos.issue").write_bytes((td / "issue.snakeos").read_bytes())
    (rootfs / "etc" / "motd.d" / "10-snakeos").write_bytes((td / "motd.snakeos").read_bytes())


def _cmd_print() -> int:
    ident = load_identity_from_environ()
    text = render_os_release(ident)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    install_identity(Path(args.rootfs))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="snakeos-distinfo")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("print-os-release", help="Print rendered /etc/os-release to stdout")

    ins = sub.add_parser("install", help="Write distro identity files under a rootfs tree")
    ins.add_argument("rootfs", type=Path, help="Path to rootfs (e.g. ./build/rootfs-desktop)")

    args = p.parse_args(argv)
    if args.cmd == "print-os-release":
        return _cmd_print()
    if args.cmd == "install":
        return _cmd_install(args)
    raise AssertionError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
