"""
QUANTUM MODEL V1 — Original Bounded Magnitude Dynamics
═══════════════════════════════════════════════════════════════════════════════

Implements the dynamics exactly as specified in documentation/QNTUM-model.md:
one primitive — event magnitudes coupled through an influence matrix defined
at unit scale — with two mechanisms v2 does not have:

    1. RELATIVE-SCALE COUPLING. Before I acts, the current state is projected
       onto its own unit sphere (divided by its largest entry), so I_ij means
       "if j is at full relative strength and i is not, how much does i move"
       — a scale-free, mildly nonlinear coupling, not a fixed linear map.

    2. SELF-BOUNDING BY CONSTRUCTION. Instead of shrinking the influence gain
       until a spectral-radius cap holds on the linearized system (v2's
       approach — see quantum_v2.stabilize_beta), each step is scaled back to
       a declared magnitude bound the moment it overshoots, then clipped.
       Boundedness is a per-step property of the state itself, not a property
       of the linearized system checked once after fitting.

Enhancement over the literal doc: the bound is a declared constant (`clamp`)
rather than a hardcoded 1.0, because this implementation runs on robustly
standardized increments (median/MAD z-units — see data_preprocessor.py)
rather than raw levels pre-scaled to [-1, 1]. A z-unit magnitude of 1 is a
below-average move, not a saturation point, so the bound is expressed in the
same z-units. Everything else — the phase function, the memory term, the
influence store, pin-and-propagate, events — is shared with v2 unchanged.
"""

from __future__ import annotations
import numpy as np

DEFAULT_CLAMP = 4.0  # z-units ("four-sigma" ceiling); doc's literal bound is 1.0


def normalize_rows(M_history: np.ndarray) -> np.ndarray:
    """
    Project each historical state onto unit scale: M(t) / max_k|M_k(t)|.

    This is the doc's Φ-adjacent step (Section 2 of QNTUM-model.md) — the
    reason a linear influence matrix still produces nonlinear dynamics:
    coupling strength is read relative to the strongest currently-moving
    channel at that historical instant, not in absolute z-units. Rows whose
    max is ~0 are left as-is (no direction to normalize toward).
    """
    max_abs = np.max(np.abs(M_history), axis=-1, keepdims=True)
    safe = np.where(max_abs > 1e-12, max_abs, 1.0)
    return M_history / safe


def clamp_to_bound(M: np.ndarray, bound: float) -> np.ndarray:
    """
    Scale-then-clamp exactly as documented: if the largest entry exceeds the
    bound, rescale the whole vector so the largest entry lands exactly on the
    bound (direction preserved), then clip as a final safety net.

    With bound=1.0 this is byte-for-byte the doc's post-step rule; any other
    bound generalizes it to the magnitude units actually in use.
    """
    max_abs = float(np.max(np.abs(M))) if M.size else 0.0
    if max_abs > bound:
        M = M / max_abs * bound
    return np.clip(M, -bound, bound)
