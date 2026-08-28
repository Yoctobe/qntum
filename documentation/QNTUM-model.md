# QUAntified Network of Temporal Unfolding Magnitudes (QNTUM)

This model simulates **magnitudes** at future time points from two inputs:

- **Influence matrix** $I$, defined at fixed magnitude 1
- **Initial magnitudes** at $t_0$

**Data requirement:** Use **level values** for your time series (e.g. raw temperature, volume, prices, GDP levels). Do not pre-normalize — the normalization layer is applied internally: each variable is converted to a stationary increment (first difference by default; log-difference for strictly positive multiplicative series such as prices), then standardized by a robust z-score (median / MAD). Forecast stability is guaranteed by capping the spectral radius of the linearized dynamics $\rho(\alpha\,\mathbb{1} + \beta W) < 1$, not by clamping the data.

An event that is **inactive** has magnitude $0$. The magnitude of event $i$ is the **sum of weighted magnitudes** of other events, modulated by a phase function and updated over time.

---

## 1. Event definition

Each event $E_i$ is defined by:

| Symbol | Meaning |
|--------|--------|
| $t_0$ | Start time |
| $t_f$ | Formation duration |
| $\tau$ | Decay constant |
| $B_i$ | Base level (constant offset) |
| $M_i(t_0)$ | Initial magnitude at $t_0$ |

**Phase function** $\Phi(E_i, t)$ (temporal activation):

$$
\Phi(E_i, t) =
\begin{cases}
0 & t < t_0 \quad \text{(Inactive)} \\
\dfrac{t - t_0}{t_f} & t_0 \le t < t_0 + t_f \quad \text{(Formation)} \\
1 & t_0 + t_f \le t < t_0 + t_f + \tau \quad \text{(Stable)} \\
e^{-(t - (t_0 + t_f + \tau))/\tau} & \text{otherwise} \quad \text{(Decay)}
\end{cases}
$$

States: **Inactive** → **Formation** → **Stable** → **Decay**.

---

## 2. Magnitude dynamics

**Default (bounded) mode**

1. **Influence input:** scale current magnitudes so the vector passed to $I$ has fixed scale (max 1):
   $$\tilde{M}_j(t) = \frac{M_j(t)}{\max_k |M_k(t)|} \quad \text{(if } \max_k |M_k(t)| > 0 \text{; else } \tilde{M} = M \text{)}.$$

2. **Update:**
   $$M_i(t+1) = B_i + \alpha\, M_i(t) + \beta\, \Phi(E_i, t)\, \sum_{j} I_{ij}\, \tilde{M}_j(t).$$

3. **Post-step:** if $\max_i |M_i(t+1)| > 1$, scale $M(t+1) \leftarrow M(t+1) / \max_i |M_i(t+1)|$; then clamp each $M_i$ to $[-1, 1]$.

**Linear dynamics mode** (for deterministic systems, e.g. $M(t+1) = B + I\,M(t)$):

- No scaling of $M$ before the sum; use $M_j(t)$ directly in $\sum_j I_{ij}\, M_j(t)$.
- No post-step scaling or clamping.
- So $M(t+1) = B + \alpha M(t) + \beta\,\Phi\, (I\,M(t))$. With $\alpha=0$, $\beta=1$, $\Phi=1$: $M(t+1) = B + I\,M(t)$.

**Terms:**

| Term | Meaning |
|------|--------|
| $B_i$ | Base level of event $i$ |
| $\alpha$ | Stability factor (memory persistence) |
| $\alpha\, M_i(t)$ | **Memory** (persistence of own magnitude) |
| $\beta$ | Global scaling factor for influence |
| $I_{ij}$ | Influence of event $j$ on $i$ (from matrix $I$) |
| $\tilde{M}_j(t)$ | In default mode: $M_j(t)$ normalised by $\max_k |M_k(t)|$ for fixed-scale interactions |
| $\beta\, \Phi(E_i, t)\, \sum_j I_{ij}\, \tilde{M}_j(t)$ (or $M_j$) | **Network influence** (weighted sum, gated by $\Phi$) |

---

## 3. Influence matrix $I$

- **Structure:** square matrix; $I_{ij}$ is the effect of event $j$ on event $i$.
- **Pinning known relationships:** You can **pin** linear and nonlinear relationships in $I_{\mathrm{known}}$ and let the model **guess the rest** from data: pin **linear** with a finite scalar, **nonlinear** with a callable (e.g. formula), and leave **NaN** where the package should auto-detect and fit. See the influence-matrix documentation for the full three-mode setup.
- **Expansion:** when adding a new event, add a new row and column; off-diagonal entries set mutual influences; diagonal $I_{ii}$ is self-influence (e.g. stabilisation/destabilisation).
- **Role:** $I$ is the central object that couples events; it can be updated by future events so that interactions are time-varying.

---

## 4. Simulation workflow

1. **Initialisation:** define events (parameters above), set $I$, set $M_i(t_0)$; choose default (bounded) or linear dynamics.
2. **Time stepping:** for each $t$:
   - compute $\Phi(E_i, t)$ for all events;
   - form $\tilde{M}(t)$ (default: $M/\max|M|$; linear: use $M$);
   - update $M_i(t+1) = B_i + \alpha M_i(t) + \beta\,\Phi \sum_j I_{ij}\, \tilde{M}_j$ (or $M_j$ in linear mode);
   - default only: if $\max|M(t+1)| > 1$ scale then clamp to $[-1, 1]$; linear: no post-step.
3. **Analysis:** track peaks, correlations, and temporal evolution.

---

## 5. Phase-driven modulation and implementation notes

- **Phase-driven modulation:** $\Phi$ ensures events only contribute to the network term during **active** phases (formation/stable/decay); when $\Phi = 0$ the event is inactive and its magnitude is treated as 0 in that role.
- **Influence matrix:** $I$ is central to coupling events.
- **Default mode:** influence term uses $\tilde{M} = M/\max|M|$; after update, scale (if needed) and clamp to $[-1, 1]$ for bounded dynamics.
- **Linear mode:** use $M$ in $I\,M$; no scaling or clamping (for deterministic systems $M(t+1) = B + I\,M(t)$).
- **Dynamic $I$:** future events can change $I$, giving time-varying interactions.

---

## Key equation recap

**Default (bounded):** $\tilde{M} = M / \max_k |M_k|$, then

$$\boxed{M_i(t+1) = B_i + \alpha\, M_i(t) + \beta\, \Phi(E_i, t)\, \sum_{j} I_{ij}\, \tilde{M}_j(t)}$$

then scale if $\max_i |M_i(t+1)| > 1$ and clamp to $[-1, 1]$.

**Linear dynamics:** $M(t+1) = B + \alpha\, M(t) + \beta\,\Phi\, (I\,M(t))$ (no normalisation, no clamp). With $\alpha=0$, $\beta=1$, $\Phi=1$: $M(t+1) = B + I\,M(t)$.

- **Memory:** $\alpha\, M_i(t)$
- **Network influence (default):** $\beta\, \Phi\, \sum_j I_{ij}\, \tilde{M}_j(t)$
- **Network influence (linear):** $\beta\, \Phi\, \sum_j I_{ij}\, M_j(t)$
