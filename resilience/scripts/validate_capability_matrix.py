from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: str) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Capability matrix must be a mapping")
    return data


def validate_matrix(path: str) -> list[str]:
    config = _load_yaml(path)
    errors: list[str] = []

    agents = config.get("agents", [])
    if not isinstance(agents, list):
        return ["agents must be a list"]
    known_agents = {agent.get("id") for agent in agents if isinstance(agent, dict)}

    task_types = config.get("task_types", {})
    if not isinstance(task_types, dict):
        return ["task_types must be a mapping"]
    if not task_types:
        return ["task_types must not be empty"]

    for task_type, definition in task_types.items():
        if not isinstance(definition, dict):
            errors.append(f"{task_type}: definition must be a mapping")
            continue

        capable_agents = definition.get("capable_agents")
        if not isinstance(capable_agents, list) or not capable_agents:
            errors.append(f"{task_type}: requires at least one capable agent")
            continue

        for agent_id in capable_agents:
            if agent_id not in known_agents:
                errors.append(f"{task_type}: unknown agent '{agent_id}'")

    return errors


if __name__ == "__main__":
    result = validate_matrix("config/agent-capability-matrix.yaml")
    if result:
        for error in result:
            print(error)
        raise SystemExit(1)
    print("Capability matrix valid")
