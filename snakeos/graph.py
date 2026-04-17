from __future__ import annotations

from collections import defaultdict, deque

from snakeos.config_loader import ServiceSpec


def topo_sort_services(services: list[ServiceSpec]) -> list[ServiceSpec]:
    """Dependency order: dependencies appear before dependents. Raises on unknown dep or cycle."""

    by_name: dict[str, ServiceSpec] = {s.name: s for s in services}
    if len(by_name) != len(services):
        raise ValueError("duplicate service name")

    for s in services:
        for d in s.depends_on:
            if d not in by_name:
                raise ValueError(f"service {s.name!r} depends on unknown service {d!r}")

    # Edge: dep -> dependent (dep must run before dependent)
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {s.name: 0 for s in services}

    for s in services:
        for dep in s.depends_on:
            if s.name not in outgoing[dep]:
                outgoing[dep].add(s.name)
                indegree[s.name] += 1

    q: deque[str] = deque(name for name, deg in indegree.items() if deg == 0)
    order_names: list[str] = []

    while q:
        n = q.popleft()
        order_names.append(n)
        for m in outgoing[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                q.append(m)

    if len(order_names) != len(services):
        raise ValueError("cycle in service depends_on graph")

    return [by_name[n] for n in order_names]
