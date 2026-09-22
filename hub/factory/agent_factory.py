"""The Agent Factory: the workforce declared in ``agents/factory.yaml``.

Edit the YAML and you change who works on a build — no code changes, no
redeploy. Roles are matched to stages by ``STAGE_ROLES``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import config


class SwarmError(RuntimeError):
    pass


# which role owns which stage of the loop
STAGE_ROLES = {
    "research": "market_analyst",
    "reasoning": "product_manager",
    "build": "rapid_prototyper",
    "qa": "qa_engineer",
    "package": "release_engineer",
    "deliver": "release_engineer",
    "maintain": "maintainer",
}


@dataclass
class Agent:
    name: str
    role: str
    capabilities: list[str] = field(default_factory=list)
    target: list[str] = field(default_factory=list)
    human_gate: bool = False
    requires_evidence: bool = False
    gate: dict = field(default_factory=dict)

    @property
    def min_score(self) -> int:
        return int(self.gate.get("min_score", 0))

    def can(self, capability: str) -> bool:
        return capability in self.capabilities

    def __str__(self) -> str:
        flag = " [human gate]" if self.human_gate else ""
        return f"{self.name} · {self.role}{flag}"


@dataclass
class Swarm:
    name: str
    offline_model: str
    mission: str
    agents: list[Agent]

    def by_name(self, name: str) -> Agent | None:
        return next((a for a in self.agents if a.name.lower() == name.lower()), None)

    def by_role(self, role: str) -> Agent | None:
        return next((a for a in self.agents if a.role == role), None)

    def for_stage(self, stage: str) -> Agent | None:
        role = STAGE_ROLES.get(stage)
        return self.by_role(role) if role else None

    def gated(self) -> list[Agent]:
        return [a for a in self.agents if a.human_gate]

    def __len__(self) -> int:
        return len(self.agents)


def load_swarm(path: Path | str | None = None) -> Swarm:
    """Read the workforce definition. Raises ``SwarmError`` with the fix."""
    path = Path(path or config.SWARM_FILE)
    if not path.exists():
        raise SwarmError(
            f"swarm file not found: {path}. Set HOOLULU_SWARM or run "
            f"hoolulu-ecosystem-hub/ops/scaffold.sh"
        )
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SwarmError("PyYAML is required to read the swarm definition "
                         "(pip install pyyaml)") from exc
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    factory = raw.get("factory") or {}
    workforce = factory.get("workforce") or []
    if not workforce:
        raise SwarmError(f"{path} declares no workforce")

    agents = []
    for entry in workforce:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise SwarmError(f"{path}: every workforce entry needs a name")
        agents.append(Agent(
            name=str(entry["name"]),
            role=str(entry.get("role", "worker")),
            capabilities=list(entry.get("capabilities") or []),
            target=list(entry.get("target") or []),
            human_gate=bool(entry.get("human_gate", False)),
            requires_evidence=bool(entry.get("requires_evidence", False)),
            gate=dict(entry.get("gate") or {}),
        ))
    return Swarm(
        name=str(factory.get("name", "unnamed")),
        offline_model=str(factory.get("offline_model", config.OFFLINE_URL)),
        mission=" ".join(str(factory.get("mission", "")).split()),
        agents=agents,
    )


def format_swarm(swarm: Swarm) -> str:
    lines = [f"{swarm.name} — {len(swarm)} agents · brain {swarm.offline_model}"]
    if swarm.mission:
        lines.append(f"  mission: {swarm.mission}")
    for agent in swarm.agents:
        caps = ", ".join(agent.capabilities) or "—"
        lines.append(f"  {str(agent):<42} {caps}")
    return "\n".join(lines)
