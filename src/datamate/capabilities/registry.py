from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from datamate.capabilities.contracts import CapabilityContext, CapabilitySpec
from datamate.load_business import read_config


class CapabilityError(ValueError):
    pass


@dataclass
class CapabilityRegistry:
    project_root: Path
    specs: dict[str, CapabilitySpec] = field(default_factory=dict)

    def register(self, spec: CapabilitySpec) -> None:
        if spec.name in self.specs:
            raise CapabilityError(f"duplicate capability: {spec.name}")
        self.specs[spec.name] = spec

    def build(self, split: str, business_id: str, name: str) -> Any:
        if name not in self.specs:
            raise CapabilityError(f"unknown capability: {name}")
        config = read_config(split, business_id, self.project_root / "configs/businesses")
        spec = self.specs[name]
        if config.get("archetype") != spec.archetype:
            raise CapabilityError("archetype mismatch")
        if config.get("capabilities", {}).get(name) is not True:
            raise CapabilityError(f"capability not enabled: {name}")
        semantic = config["sources"][config["monthly_sales"]["source"]]["semantic_columns"]
        missing = sorted(spec.required_roles - set(semantic))
        if missing:
            raise CapabilityError(f"missing semantic roles: {missing}")
        return spec.builder(CapabilityContext(self.project_root, split, business_id, config))
