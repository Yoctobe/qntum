"""Controlled intervention study for the optional event envelope."""

from __future__ import annotations

import numpy as np

from experiments.common import write_result
from quantum_model.quantum_v2 import Event, QuantumV2
from quantum_model.influence_matrix_v2 import InfluenceMatrixV2


def _phase_series(length: int, start: int, formation: int, plateau: int) -> np.ndarray:
    event = Event(float(start), float(formation), float(plateau), 0.0, "target")
    return np.asarray([event.phase(float(time)) for time in range(length)])


def run() -> dict:
    length = 120
    rng = np.random.default_rng(7)
    source = np.sin(np.arange(length) * 0.18)
    phase = _phase_series(length, 35, 10, 30)
    target = np.zeros(length)
    for time in range(length - 1):
        target[time + 1] = 0.4 * target[time] + phase[time] * 0.8 * source[time]
    target += rng.normal(0.0, 0.02, size=length)

    influence = InfluenceMatrixV2(2)
    influence.set_pair(1, 0, 0.8)
    model = QuantumV2(influence, alpha=0.4, beta=1.0)
    states = np.column_stack([source, target])

    declared_events = [
        Event(0.0, 0.0, 200.0, source[0], "source"),
        Event(35.0, 10.0, 30.0, target[0], "target"),
    ]
    always_on = [
        Event(0.0, 0.0, 200.0, source[0], "source"),
        Event(0.0, 0.0, 200.0, target[0], "target"),
    ]

    def predict(events):
        output = []
        for time in range(length - 1):
            model._history_buffer = states[:time].copy()
            output.append(model.step(float(time), states[time], events)[1])
        model.reset_history()
        return np.asarray(output)

    actual = target[1:]
    declared = predict(declared_events)
    unphased = predict(always_on)
    payload = {
        "study": "declared_event_envelope",
        "declared_phase_mae": float(np.mean(np.abs(declared - actual))),
        "always_on_mae": float(np.mean(np.abs(unphased - actual))),
        "onset": 35,
        "formation": 10,
        "plateau": 30,
        "seed": 7,
    }
    write_result("event_study.json", payload)
    return payload


if __name__ == "__main__":
    run()
