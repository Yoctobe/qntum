# QNTUM

**QUAntified Network of Temporal Unfolding Magnitudes**

A multivariate forecasting model that evolves **magnitudes** over time from an influence matrix and initial conditions. Couplings are named and editable; inactive factors contribute nothing; forecasts stay bounded.

![QNTUM Simulator](home.png)

---

## Idea

Two inputs drive the simulation:

1. **Influence matrix** \(I\) — how each variable / event affects every other  
2. **Initial magnitudes** at \(t_0\)

Levels go in raw (prices, rates, GDP, temperatures). Internally the model converts each series to a stationary increment (diff or log-diff), then a robust z-score (median / MAD). You do not pre-normalize.

An **inactive** event has magnitude \(0\). Active magnitudes update as memory of their own past plus a phase-gated network sum:

$$
M_i(t+1) = B_i + \alpha\, M_i(t) + \beta\, \Phi(E_i, t)\, \sum_{j} I_{ij}\, \tilde{M}_j(t)
$$

| Term | Role |
|------|------|
| `α · M_i(t)` | Memory — persistence of own magnitude |
| `β · Φ · ΣⱼIᵢⱼ M̃ⱼ(t)` | Network influence — weighted couplings, gated by phase |
| `Bᵢ` | Base / drift |

Full theory: [`documentation/QNTUM-model.md`](documentation/QNTUM-model.md).

---

## Events and phase \(\Phi\)

Each factor is wrapped in an event \(E_i\) with start \(t_0\), formation \(t_f\), and decay \(\tau\):

**Inactive → Formation → Stable → Decay**

$$
\Phi(E_i, t) =
\begin{cases}
0 & t < t_0 \\[4pt]
(t - t_0)/t_f & \text{formation} \\[4pt]
1 & \text{stable} \\[4pt]
e^{-(t - (t_0 + t_f + \tau))/\tau} & \text{decay}
\end{cases}
$$

When \(\Phi = 0\), the event does not participate in the network term.

---

## Dynamics modes

| Mode | Behavior |
|------|----------|
| **v1 — bounded (doc)** | Scale history by \(\max\|M\|\), then clamp after each step (original design) |
| **v2 — spectral (default)** | No per-step clamp; shrink global gain \(\beta\) so \(\rho(\alpha I + \beta W) < 1\) |

Both share the same fitted influence store. Compare them in the simulator tabs; they diverge when the fitted structure is genuinely unstable (Stress panel, §4.2).

---

## Influence matrix

- Square store: \(I_{ij}\) = effect of \(j\) on \(i\)
- **Pin** known linear (scalar) or nonlinear (formula) relationships; they are never overwritten by fitting
- Leave the rest for auto-discovery above a significance threshold
- Expandable when new channels / events are added

---

## Simulator

Interactive UI (`simulator/`) on top of the model:

- Timeline cursor over past → present → future  
- **Pin** any chart point — other channels react through \(I\)  
- **Event library** — shocks with formation / intensity / decay  
- Editable influence matrix heatmap  
- Live US macro panel + stress-test reproduction of the paper’s short-sample case  

### Run

```bash
# Backend
cd simulator/backend
pip install -r requirements.txt
uvicorn app:app --port 8000

# Frontend (separate terminal)
cd simulator/frontend
npm install
npm run dev   # → http://localhost:5173
```

Refresh macro data: `python3 simulator/backend/fetch_data.py`

---

## Repo layout

| Path | Contents |
|------|----------|
| `documentation/QNTUM-model.md` | Original model specification |
| `QUNTUM_draft.md` | Paper draft (incl. v1 vs v2 ablation) |
| `Model/quantum_model/` | Core library (`quantum_v1`, `quantum_v2`, influence store, scenario engine) |
| `simulator/` | FastAPI + React app |

---

## License / author

Ayoub Bensakhria
