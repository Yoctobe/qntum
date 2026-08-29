# Forecasting when you know a few relationships — and need every one of them to stay editable

Most multivariate models give you a coefficient matrix. Useful for prediction. Hard to audit. Harder to edit.

In practice, you often know a handful of couplings with confidence and almost nothing about the rest. You need three things:

1. Readable structure — which variable affects which target, with what sign and lag  
2. Editable constraints — trusted edges stay fixed; impossible edges stay out  
3. Bounded recursion — stability checked on the lagged dynamics the model actually runs  

That is the gap QNTUM was built for.

---

## What QNTUM is

QNTUM (QUAntified Network of Temporal Unfolding Magnitudes) is an interpretable forecasting model for small coupled systems.

Relationships live in a named influence store: target, sources, lag, coefficient or formula, and a constraint state. You can pin fixed values, signs, bounds, or forbidden edges. Everything else is estimated jointly with sparse selection — not one independent fit per candidate.

Variables can carry event timing: inactive → formation → stable → decay. Incoming influence only fires when the envelope says so. Levels go in raw; the model converts them to robust standardized increments on the training window only. Linear lagged dynamics are assessed through their companion matrix; forecast intervals use chronological conformal calibration.

Same engine, different domains: US macro, glucose–insulin, predator–prey. You can pin a point on a chart and watch the network respond.

---

## What the paper actually shows

In 1,800 controlled sparse-system fits, correct pins improved structure recovery:

- At 80 observations, support F1 rose from 0.711 to 0.786 with 50% pin coverage  
- At 320 observations, from 0.817 to 0.905  

Six-step forecast error barely moved (under 1%). On two UCI panels, QNTUM sat alongside zero-increment and VAR baselines — not ahead of them across the board.

The takeaway is deliberate: the demonstrated benefit is structural recovery under correct partial knowledge, not a claim of general forecasting superiority. Wrong pins hurt coefficient quality. A companion-matrix gain cap stops sustained explosive growth in near-boundary tests.

---

## Who it is for

QNTUM fits when:

- the system is small and coupled  
- a few relationships can be defended  
- auditability and scenario editing matter as much as the point forecast  

It does not fit when accuracy alone is the scoreboard, lag structure is long and unknown, or no stable relationship store can be justified.

---

## Read / try

Paper: https://www.researchgate.net/publication/413753331_QNTUM_A_Quantified_Network_of_Temporal_Unfolding_Magnitudes_for_Interpretable_Editable_Multivariate_Forecasting  

Code and simulator: https://github.com/yoctobe/qntum/

If you work with sensor networks, lab systems, or scenario analysis where couplings must stay inspectable — I would welcome your thoughts.
