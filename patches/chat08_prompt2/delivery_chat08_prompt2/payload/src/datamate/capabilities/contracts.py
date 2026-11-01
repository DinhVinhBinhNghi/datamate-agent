from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class CapabilityContext:
    project_root: Path
    split: str
    business_id: str
    config: dict[str, Any]


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    archetype: str
    required_roles: frozenset[str]
    builder: Callable[[CapabilityContext], Any]
