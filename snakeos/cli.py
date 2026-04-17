from __future__ import annotations

import argparse
import sys
from pathlib import Path

from snakeos import distinfo
from snakeos.pid1 import run_init


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="snakeos", description="Python-first Linux userspace helpers")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="Run snakeOS init/supervisor loop (intended for PID 1)")
    i.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/snakeos/services.toml"),
        help="Path to services.toml",
    )

    d = sub.add_parser("distro", help="Distribution metadata (os-release, rootfs identity)")
    d_sub = d.add_subparsers(dest="distro_cmd", required=True)
    d_sub.add_parser("print-os-release", help="Print rendered /etc/os-release to stdout")
    di = d_sub.add_parser(
        "install-identity",
        help="Install /etc/os-release and related files into a rootfs directory",
    )
    di.add_argument("rootfs", type=Path, help="Path to rootfs tree")

    args = p.parse_args(argv)
    if args.cmd == "init":
        return run_init(args.config)
    if args.cmd == "distro":
        if args.distro_cmd == "print-os-release":
            return distinfo.main(["print-os-release"])
        if args.distro_cmd == "install-identity":
            return distinfo.main(["install", str(args.rootfs)])

    raise AssertionError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
