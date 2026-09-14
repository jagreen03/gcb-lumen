# Findings, 2026-09-13 (third pass, same day) — the normalization fix was tried; it did NOT converge the result; the diagnosis sharpened

**Continuing directly from `FINDINGS-2026-09-13-fdtd.md`'s recommended
next step.** That finding suspected the missing piece was a separate
straight-waveguide reference run to normalize `P_in` against, rather
than measuring it in the same run as the MMI junction (where a
reflection traveling back through the monitor could contaminate it).
**Built and tried that fix** (`fdtd/mmi_fdtd_v2.py`). **It did not
work — reported honestly, not hidden or re-tried until something
looked better.**

## The fix, and the result

`mmi_fdtd_v2.py` runs two simulations per resolution: a clean
reference (input taper only, no MMI, no reflection source at all) to
get `P_in`, then the full structure for `P_o2`/`P_o3`, normalizing
against the clean reference instead of a same-run monitor.

| Resolution | `P_in` (reference run) | Insertion loss | (v1, same-run `P_in`, for comparison) |
|---|---|---|---|
| 20 | 5.709e-5 | 4.36 dB | 4.36 dB |
| 30 | 7.568e-5 | **10.94 dB** | 9.06 dB |
| 40 | 3.222e-5 | 2.87 dB | 2.86 dB |

**The fix changed almost nothing, and at resolution 30 the result got
worse (9.06 → 10.94 dB), not better.** This rules out the specific
hypothesis in the prior findings file: reflection contamination of a
same-run input monitor was **not** the dominant cause of the
non-convergence.

## A sharper diagnosis, from a new observation

**`P_in` itself — measured from a clean run with no junction, no
reflection source of any kind — varies wildly across resolution**:
5.71e-5, 7.57e-5, 3.22e-5 (res 20/30/40). For a fixed physical source
launching the same real power, a well-resolved simulation should give
a *stable* `P_in` once resolution is adequate — this 2.3× spread with
no junction present at all means **the bug is upstream of any
monitor-placement or reflection issue — most likely in how much power
the `EigenModeSource` itself injects at different resolutions, or in
how much of the pulse's total energy the flux DFT has actually
captured by the time each run's decay-based stopping criterion fires.**

The second possibility is concrete and checkable: `sim.run` uses
`mp.stop_when_fields_decayed(...)`, and flux monitors integrate (via
DFT) continuously from `t=0` — if different resolutions hit their own
decay criterion at different *total* elapsed simulation times (very
plausible, since decay timing depends on the simulation's own
resolution-dependent group velocity and damping), a run that stops
"too early" relative to its own pulse's spectral content would
under-report flux at every monitor in that run, input and output
alike — consistent with `P_in` itself (not just the loss ratio)
varying this much.

## What this does and does not change

**Still does not close the core question.** Still no trustworthy
insertion-loss number.

**Does rule out one real hypothesis and sharpen the next one** — this
is real progress, not a wasted pass: the next debugging step should
check run-duration/DFT-completeness (e.g., a fixed, generously long
`until=` run time instead of a field-decay stopping criterion, so
every resolution integrates the same total simulation time) **before**
trying anything else, rather than guessing at a third unrelated fix.

## Recommended next step, not started

Replace the `stop_when_fields_decayed` criterion with a fixed,
generously long `until=` (e.g., several multiples of the cell's
longest dimension divided by the slowest expected group velocity,
picked once and held constant across all resolutions) so every
resolution's flux monitors integrate over directly comparable total
simulation time. Re-run the same three-resolution check. If `P_in`
from the clean reference run is still unstable after that, the next
suspect is the `EigenModeSource`'s own mode-normalization at different
resolutions specifically (worth an isolated test: run *only* the
reference configuration across many resolutions and plot `P_in` alone,
before ever reintroducing the junction).

**Stopping active debugging here for this pass** — this needs
careful, patient, dedicated FDTD-methodology work (checking one
variable at a time), not a third rushed guess stacked on two already
negative results today.
