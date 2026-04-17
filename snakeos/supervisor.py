from __future__ import annotations

import errno
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field

from snakeos.config_loader import ServiceSpec
from snakeos.graph import topo_sort_services

log = logging.getLogger(__name__)


@dataclass
class _Running:
    spec: ServiceSpec
    popen: subprocess.Popen[str]
    restarts: int = 0


@dataclass
class Supervisor:
    """Supervise long-running services; run declarative oneshots with depends_on ordering."""

    services: list[ServiceSpec]
    services_ordered: list[ServiceSpec] = field(init=False)
    by_name: dict[str, ServiceSpec] = field(init=False)
    running: dict[str, _Running] = field(default_factory=dict)
    oneshot_ok: set[str] = field(default_factory=set)
    oneshot_failed: set[str] = field(default_factory=set)
    shutting_down: bool = False
    _logged_blocked: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.services_ordered = topo_sort_services(self.services)
        self.by_name = {s.name: s for s in self.services}

    def start_eligible(self) -> None:
        if self.shutting_down:
            return

        for spec in self.services_ordered:
            if spec.kind == "oneshot":
                if spec.name in self.oneshot_ok or spec.name in self.oneshot_failed:
                    continue
                if not self._deps_ready(spec):
                    self._maybe_log_blocked(spec)
                    continue
                if not self._require_ok(spec):
                    log.error("oneshot %s: missing require_path %r", spec.name, spec.require_path)
                    self.oneshot_failed.add(spec.name)
                    continue
                self._run_oneshot(spec)
                continue

            if spec.name in self.running:
                continue
            if not self._deps_ready(spec):
                self._maybe_log_blocked(spec)
                continue
            if not self._require_ok(spec):
                log.info("skip %s: missing %s", spec.name, spec.require_path)
                continue
            self._spawn(spec)

    def _maybe_log_blocked(self, spec: ServiceSpec) -> None:
        for dep in spec.depends_on:
            ds = self.by_name.get(dep)
            if ds and ds.kind == "oneshot" and dep in self.oneshot_failed:
                if spec.name not in self._logged_blocked:
                    log.error("service %s blocked: dependency %s failed", spec.name, dep)
                    self._logged_blocked.add(spec.name)
                return

    def _deps_ready(self, spec: ServiceSpec) -> bool:
        for dep in spec.depends_on:
            ds = self.by_name[dep]
            if ds.kind == "oneshot":
                if dep not in self.oneshot_ok:
                    return False
            elif dep not in self.running:
                return False
        return True

    def _require_ok(self, spec: ServiceSpec) -> bool:
        if not spec.require_path:
            return True
        return os.path.exists(spec.require_path)

    def _run_oneshot(self, spec: ServiceSpec) -> None:
        log.info("oneshot %s: %s", spec.name, " ".join(spec.command))
        rc = subprocess.call(spec.command, stdin=subprocess.DEVNULL)
        if rc == 0:
            self.oneshot_ok.add(spec.name)
            log.info("oneshot %s: ok", spec.name)
        else:
            self.oneshot_failed.add(spec.name)
            log.error("oneshot %s: failed rc=%s", spec.name, rc)

    def _spawn(self, spec: ServiceSpec, restarts: int = 0) -> None:
        log.info("start %s: %s", spec.name, " ".join(spec.command))
        popen = subprocess.Popen(
            spec.command,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            start_new_session=True,
        )
        self.running[spec.name] = _Running(spec=spec, popen=popen, restarts=restarts)

    def reap_and_maybe_restart(self) -> None:
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break

            name = self._name_for_pid(pid)
            if name is None:
                log.warning("reaped unknown pid %s status=%s", pid, status)
                continue

            entry = self.running.pop(name)
            spec = entry.spec
            if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                rc = os.waitstatus_to_exitcode(status)
            else:
                rc = status
            log.info("exit %s pid=%s rc=%s restarts=%s", spec.name, pid, rc, entry.restarts)

            if spec.restart == "always" and not self.shutting_down:
                next_restarts = entry.restarts + 1
                delay = min(30, 0.25 * (2 ** min(next_restarts, 10)))
                log.info("restart %s in %.2fs", spec.name, delay)
                time.sleep(delay)
                self._spawn(spec, restarts=next_restarts)
            else:
                if self.shutting_down:
                    log.info("shutdown: not restarting %s", spec.name)
                else:
                    log.info("not restarting %s (restart=no)", spec.name)

    def _name_for_pid(self, pid: int) -> str | None:
        for name, entry in self.running.items():
            if entry.popen.pid == pid:
                return name
        return None

    def shutdown_all(self, grace: float = 2.0) -> None:
        self.shutting_down = True
        if not self.running:
            return
        log.info("shutdown: sending SIGTERM to %s children", len(self.running))
        for entry in self.running.values():
            try:
                if entry.popen.pid:
                    os.killpg(os.getpgid(entry.popen.pid), signal.SIGTERM)
            except ProcessLookupError:
                continue

        deadline = time.monotonic() + grace
        while self.running and time.monotonic() < deadline:
            self.reap_and_maybe_restart()
            time.sleep(0.05)

        for entry in list(self.running.values()):
            if entry.popen.poll() is None and entry.popen.pid:
                try:
                    os.killpg(os.getpgid(entry.popen.pid), signal.SIGKILL)
                except ProcessLookupError:
                    continue

        while True:
            try:
                os.waitpid(-1, 0)
            except ChildProcessError as e:
                if e.errno == errno.ECHILD:
                    break
                raise

        self.running.clear()


def basic_mounts_if_root() -> None:
    """Best-effort mounts when running as PID 1 on a real Linux rootfs."""
    if os.getpid() != 1:
        return
    mounts = [
        ("proc", "/proc", "proc", "nosuid,noexec,nodev"),
        ("sysfs", "/sys", "sysfs", "nosuid,noexec,nodev"),
        ("devtmpfs", "/dev", "devtmpfs", "mode=0755"),
    ]
    for source, target, fstype, options in mounts:
        try:
            os.makedirs(target, exist_ok=True)
        except OSError:
            pass
        try:
            os.mount(source, target, fstype, 0, options)
        except OSError as e:
            log.debug("mount %s -> %s: %s", fstype, target, e)
