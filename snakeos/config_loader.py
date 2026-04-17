from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class MountSpec:
    source: str
    target: str
    fstype: str
    options: str
    flags: int


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    kind: Literal["simple", "oneshot"]
    command: list[str]
    restart: str  # "no" | "always"
    require_path: str | None
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class InitConfig:
    hostname: str | None
    wait_for_path: str | None
    mounts: list[MountSpec]
    services: list[ServiceSpec]


def load_services_toml(path: Path) -> InitConfig:
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    meta = data.get("meta") or {}

    hostname = meta.get("hostname")
    if hostname is not None and not isinstance(hostname, str):
        raise ValueError("meta.hostname must be a string")

    wait_for_path = meta.get("wait_for_path")
    if wait_for_path is not None and not isinstance(wait_for_path, str):
        raise ValueError("meta.wait_for_path must be a string")

    mounts = _parse_mount_tables(data.get("mount"))

    services_raw = data.get("service")
    if services_raw is None:
        raise ValueError("config must contain [[service]] entries")

    if isinstance(services_raw, dict):
        service_list = [services_raw]
    elif isinstance(services_raw, list):
        service_list = services_raw
    else:
        raise ValueError("`service` must be a table or array of tables")

    services: list[ServiceSpec] = []
    for item in service_list:
        services.append(_parse_service_table(item))

    hostname_clean: str | None = None
    if isinstance(hostname, str):
        hostname_clean = hostname.strip() or None

    wait_clean: str | None = None
    if isinstance(wait_for_path, str):
        wait_clean = wait_for_path.strip() or None

    return InitConfig(
        hostname=hostname_clean,
        wait_for_path=wait_clean,
        mounts=mounts,
        services=services,
    )


def _parse_mount_tables(raw: Any) -> list[MountSpec]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        rows = [raw]
    elif isinstance(raw, list):
        rows = raw
    else:
        raise ValueError("`mount` must be a table or array of tables")

    out: list[MountSpec] = []
    for item in rows:
        out.append(_parse_mount_table(item))
    return out


def _parse_mount_table(item: Any) -> MountSpec:
    if not isinstance(item, dict):
        raise ValueError("each [[mount]] entry must be a table")

    source = item.get("source")
    target = item.get("target")
    fstype = item.get("fstype")
    if not isinstance(source, str) or not isinstance(target, str) or not isinstance(fstype, str):
        raise ValueError("mount entries need string source, target, fstype")
    if not target.startswith("/"):
        raise ValueError(f"mount target must be absolute: {target!r}")

    options = item.get("options", "")
    if not isinstance(options, str):
        raise ValueError("mount.options must be a string")

    read_only = item.get("read_only", False)
    if not isinstance(read_only, bool):
        raise ValueError("mount.read_only must be a boolean")

    flags = 0
    if read_only:
        flags |= int(getattr(os, "MS_RDONLY", 1))

    return MountSpec(source=source, target=target, fstype=fstype, options=options, flags=flags)


def _parse_service_table(item: Any) -> ServiceSpec:
    if not isinstance(item, dict):
        raise ValueError("each [[service]] entry must be a table")

    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("each service needs a non-empty string `name`")

    kind = item.get("kind", "simple")
    if kind not in ("simple", "oneshot"):
        raise ValueError(f"service {name!r}: `kind` must be 'simple' or 'oneshot'")

    command = item.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError(f"service {name!r}: `command` must be a non-empty array of strings")
    if not all(isinstance(x, str) for x in command):
        raise ValueError(f"service {name!r}: `command` must be an array of strings")

    restart = item.get("restart", "always" if kind == "simple" else "no")
    if restart not in ("no", "always"):
        raise ValueError(f"service {name!r}: `restart` must be 'no' or 'always'")

    if kind == "oneshot" and restart != "no":
        raise ValueError(f"service {name!r}: oneshot services must use restart = 'no'")

    require_path = item.get("require_path")
    if require_path is not None and not isinstance(require_path, str):
        raise ValueError(f"service {name!r}: `require_path` must be a string or omitted")

    depends = item.get("depends_on", [])
    if depends is None:
        depends = []
    if isinstance(depends, str):
        depends = [depends]
    if not isinstance(depends, list) or not all(isinstance(x, str) for x in depends):
        raise ValueError(f"service {name!r}: `depends_on` must be a string or array of strings")

    if name in depends:
        raise ValueError(f"service {name!r}: depends_on cannot include itself")

    return ServiceSpec(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        command=list(command),
        restart=str(restart),
        require_path=require_path,
        depends_on=tuple(depends),
    )
