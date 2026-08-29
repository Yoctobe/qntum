"""Small declarative nonlinear feature libraries for controlled systems."""

from __future__ import annotations

import numpy as np


def product(target: int, source_a: int, source_b: int, lag_steps: int = 0) -> dict:
    return {
        "target": target,
        "sources": (source_a, source_b),
        "transform": lambda a, b: a * b,
        "name": "product",
        "lag_steps": lag_steps,
    }


def sine(target: int, source: int, lag_steps: int = 0) -> dict:
    return {
        "target": target,
        "sources": (source,),
        "transform": np.sin,
        "name": "sine",
        "lag_steps": lag_steps,
    }


def lotka_volterra_library(prey: int = 0, predator: int = 1) -> list[dict]:
    return [
        product(prey, prey, predator),
        product(predator, prey, predator),
    ]


def pendulum_library(angle: int = 0, angular_velocity: int = 1) -> list[dict]:
    return [sine(angular_velocity, angle)]
