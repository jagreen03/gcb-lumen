# Findings, 2026-09-13 (sixth pass, same day) — a real, converged-enough number; fed into the system-level model

**Completes the resolution sweep.** Resolution 100 (the run started as
a background task in the prior pass) finished:

| Resolution (px/µm) | Insertion loss (excess) | Gap from previous | Gap ratio |
|---|---|---|---|
| 40 | 2.87 dB | — | — |
| 60 | 2.30 dB | −0.57 dB | — |
| 80 | 2.07 dB | −0.23 dB | 0.40 |
| **100** | **1.96 dB** | **−0.11 dB** | **0.48** |

Split ratio: exactly 0.5000 : 0.5000.

**This is now a clean, consistently-decaying geometric sequence** —
the gap ratios (0.40, then 0.48) are close enough to each other that a
geometric extrapolation is reasonable, not just hopeful curve-fitting:
average ratio `r ≈ 0.44`, remaining decrease `≈ 0.11 × r/(1−r) ≈ 0.088
dB`, **extrapolated limit ≈ 1.87 dB**. The res=100 value (1.96 dB) and
the extrapolated limit (1.87 dB) differ by under 0.1 dB — at this
point, further resolution increases would cost substantially more
compute (`res=100`'s junction run alone took 1451 s ≈ 24 minutes) for
a refinement smaller than the uncertainty in several of this program's
own other assumed/literature figures elsewhere. **Treated here as
converged enough for engineering use, not as mathematically exact.**

## Two real numbers, kept separate and clearly tagged

- **`EXCESS_LOSS_DB_MEASURED = 1.96`** — `[M]easured-in-sim`, the
  actual res=100 FDTD result. Real, reproducible, not an estimate.
- **`EXCESS_LOSS_DB_EXTRAPOLATED = 1.87`** — `[D]erived`, the
  geometric-series extrapolation. A reasonable estimate, not a
  measurement — kept as a separate constant in `sax_combiner_model.py`
  so neither number is silently conflated with the other.

## Fed into the real system-level model — actual numbers, not a plan

`sax_combiner_model.py` updated with both constants, run for real:

| | N=8 (3 stages) | N=16 (4 stages) |
|---|---|---|
| Literature optimistic (0.1 dB/stage) | 0.30 dB | 0.40 dB |
| External AI's upper guess (0.3 dB/stage) | 0.90 dB | 1.20 dB |
| **This session's measured value (1.96 dB/junction)** | **5.88 dB** | **7.84 dB** |
| This session's extrapolated value (1.87 dB/junction) | 5.61 dB | 7.48 dB |

**The real combiner-tree loss is roughly 15–20× worse than the
literature's original optimistic guess, and meaningfully worse than
the `~0.3 dB/stage` upper guess an external AI offered without
citation earlier today** — both of which this program had been using
as placeholders. Still comfortably better than the fully-incoherent
pessimistic bound (`10·log₁₀(N)`: 9.0 dB at N=8, 12.0 dB at N=16).

## What this means for `optical.cell.fanin` — a real recommendation, not a final decision

`bench_emulation_parameters.md`'s own framing ("likely 4:1 first, 8:1
once the loss regime is known") is no longer a guess with nothing
behind it — **the loss regime is now known, at least to within the
caveats above**. A 4:1 cell (2 stages) under this same per-junction
figure would cost roughly `2 × 1.96 ≈ 3.9 dB` — meaningfully less than
an 8:1 cell's 5.9 dB. **Whether that difference is acceptable depends
on this program's actual optical link/power budget, which is outside
this repo's scope to evaluate** — this finding supplies the real loss
number the decision needs, not the decision itself.

## What this does and does not close

**Does not claim to be a bench-measured or foundry-validated number.**
This is a 2D effective-index-method FDTD simulation — a real,
standard first-pass technique, but an approximation of the true 3D
device (it does not capture vertical mode confinement details a full
3D simulation would). `gcb-wiki/DECISION_LEDGER.md`'s
`optical.cell.combiner-loss` entry originally called for a bench
measurement specifically — this is not that, and should not be
represented as such.

**Does supply a real, reproducible, resolution-converged simulated
number** — the strongest evidence this specific question has had all
day, replacing an unsourced guess with a tagged, traceable result.
Recommended: update `DECISION_LEDGER.md`'s two relevant entries to
reflect this (as a real FDTD result, explicitly not a bench
measurement), for the Architect's review — not closing either entry
unilaterally, since one of them specifically asked for bench evidence
this isn't.

## Full arc, for anyone picking this repo up for the first time

1. External AI suggested SAX + an assumed loss (`FINDINGS-2026-09-13.md`).
2. Real FDTD access found; first simulation didn't converge
   (`FINDINGS-2026-09-13-fdtd.md`).
3. Suspected normalization fix tried, failed (`-v2.md`).
4. Suspected run-duration fix checked, also wrong; real cause found
   (under-resolution) at a 4th resolution (`-v3.md`).
5. Clean convergence confirmed at a 5th resolution (`-v4.md`).
6. **This file**: a 6th resolution completes a clean, low-uncertainty
   convergence; the result is fed into the real system-level model.

Five hypotheses were tried across this arc; three were wrong and
discarded with the reasoning kept, not hidden; two real findings (the
circuit-level rollup, and this convergence result) are real and used.
