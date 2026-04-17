from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

from snakeos.boot import apply_hostname, apply_mounts
from snakeos.config_loader import load_services_toml
from snakeos.supervisor import Supervisor, basic_mounts_if_root

log = logging.getLogger(__name__)


def run_init(config_path: Path) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    is_pid1 = os.getpid() == 1
    if is_pid1:
        log.info("snakeOS init: running as PID 1")
        # PID 1 should not get a default SIGINT handler that kills the box accidentally.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    else:
        log.warning("not PID 1 (pid=%s): running in dev mode", os.getpid())

    cfg = load_services_toml(config_path)

    if cfg.mounts:
        apply_mounts(cfg.mounts)
    else:
        basic_mounts_if_root()

    if cfg.hostname:
        apply_hostname(cfg.hostname)

    if cfg.wait_for_path:
        _wait_for_path(cfg.wait_for_path)

    sup = Supervisor(cfg.services)

    stop = False

    def _on_term(_signum: int, _frame: object | None) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _on_term)

    sup.start_eligible()

    while not stop:
        sup.reap_and_maybe_restart()
        sup.start_eligible()
        time.sleep(0.2)

    sup.shutdown_all()
    return 0


def _wait_for_path(path: str, timeout_s: float = 300.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if os.path.exists(path):
            return
        time.sleep(0.1)
    raise TimeoutError(f"timed out waiting for {path!r}")
