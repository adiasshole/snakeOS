from __future__ import annotations

import logging
import os
import socket
from pathlib import Path

from snakeos.config_loader import MountSpec

log = logging.getLogger(__name__)


def apply_mounts(mounts: list[MountSpec], *, pid1_only: bool = True) -> None:
    if pid1_only and os.getpid() != 1:
        log.debug("skip apply_mounts: not PID 1")
        return

    for m in mounts:
        try:
            Path(m.target).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.warning("mkdir %s: %s", m.target, e)

        try:
            os.mount(m.source, m.target, m.fstype, m.flags, m.options)
            log.info("mounted %s (%s) on %s", m.fstype, m.source, m.target)
        except OSError as e:
            log.warning("mount %s -> %s: %s", m.source, m.target, e)


def apply_hostname(name: str, *, pid1_only: bool = True) -> None:
    if pid1_only and os.getpid() != 1:
        log.debug("skip hostname: not PID 1")
        return

    name = name.strip()
    if not name:
        return

    try:
        socket.sethostname(name)
        log.info("hostname set to %r", name)
    except OSError as e:
        log.warning("sethostname: %s", e)

    try:
        Path("/etc/hostname").write_text(name + "\n")
    except OSError as e:
        log.debug("write /etc/hostname: %s", e)
