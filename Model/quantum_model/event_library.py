"""
EVENT LIBRARY for the QNTUM simulator
═══════════════════════════════════════════════════════════════════════════════

Templates for latent shock events. A template stores:
    - phase defaults (formation / tau, in time steps)
    - first-hop couplings: forcing weight in z-units per step at intensity 1,
      only onto channels the event affects DIRECTLY. Second-hop effects
      (e.g. war → oil → CPI) propagate through the fitted influence matrix.
    - analogues: the historical episodes the weights were calibrated from,
      kept for provenance and for the ranges shown in the UI.

Templates live in a YAML file so users can add their own via the wizard.
"""

from __future__ import annotations
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from .simulator import EventInstance


@dataclass
class EventTemplate:
    name: str
    description: str = ""
    formation: int = 1
    tau: int = 4
    first_hop: dict[str, float] = field(default_factory=dict)
    ranges: dict[str, list[float]] = field(default_factory=dict)
    analogues: list[str] = field(default_factory=list)

    def instantiate(
        self,
        t0_idx: int,
        intensity: float = 1.0,
        name: Optional[str] = None,
        formation: Optional[int] = None,
        tau: Optional[int] = None,
        first_hop_overrides: Optional[dict[str, float]] = None,
    ) -> EventInstance:
        hops = dict(self.first_hop)
        if first_hop_overrides:
            hops.update(first_hop_overrides)
        return EventInstance(
            name=name or self.name,
            t0_idx=t0_idx,
            intensity=intensity,
            formation=self.formation if formation is None else formation,
            tau=self.tau if tau is None else tau,
            first_hop=hops,
        )


class EventLibrary:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.templates: dict[str, EventTemplate] = {}
        if self.path.exists():
            self.load()

    def load(self):
        raw = yaml.safe_load(self.path.read_text()) or []
        self.templates = {
            entry["name"]: EventTemplate(**entry) for entry in raw
        }

    def save(self):
        entries = [asdict(t) for t in self.templates.values()]
        self.path.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True))

    def add(self, template: EventTemplate):
        self.templates[template.name] = template
        self.save()

    def get(self, name: str) -> EventTemplate:
        if name not in self.templates:
            raise KeyError(f"Unknown event template: {name}")
        return self.templates[name]
