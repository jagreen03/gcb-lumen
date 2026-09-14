# Findings, 2026-09-13 (fifth pass, same day) — clean, monotonic convergence at resolution 80

**Continuing the resolution sweep `FINDINGS-2026-09-13-fdtd-v3.md`
called for.** That finding showed 40→60 px/µm closing the gap (2.87 →
2.30 dB) after two earlier hypotheses about a "bug" were ruled out —
the real cause was under-resolution of the taper geometry, a normal
FDTD sensitivity, not an error. This pass adds resolution 80.

## A real engineering note, not a science finding: single-process runs got too expensive to fit one bounded call

At resolution 80, the junction-geometry run alone took **745 s**
(the reference-only run took 290 s) — too long for a single foreground
tool invocation together with its reference run. Split the two
configurations (`build(resolution, include_junction)`) into separate
process invocations (`fdtd/mmi_fdtd_single.py`, new — a thin wrapper
around the same `build()` function already in `mmi_fdtd_v2.py`, not a
reimplementation) so each could run as its own tracked background
task. This is purely an execution-mechanics fix, not a change to the
physics or geometry of the simulation itself.

## The result — clean, monotonic, decelerating convergence

| Resolution (px/µm) | Insertion loss (excess) | Change from previous |
|---|---|---|
| 40 | 2.87 dB | — |
| 60 | 2.30 dB | −0.57 dB |
| **80** | **2.07 dB** | **−0.23 dB** |

Split ratio at res=80: **0.4999 : 0.5001** — essentially exact 50:50,
consistent with every resolution tried so far and a continued sign the
underlying geometry/source setup is sound.

**This is now a real, clean convergence sequence** — monotonically
decreasing, with the gap between successive resolutions shrinking
(0.57 dB → 0.23 dB), the expected shape for a genuinely converging
FDTD result (unlike the earlier 20/30/40 sequence, which bounced
non-monotonically because those resolutions were too coarse to be in
the convergent regime at all for this taper geometry).

## A rough, explicitly-labeled extrapolation — not a final answer

Treating the shrinking gaps as roughly geometric (each ~0.4× the
previous: 0.23/0.57 ≈ 0.40), the remaining decrease from here would
sum to roughly `0.23 × 0.40/(1-0.40) ≈ 0.15` dB further, suggesting a
possible limiting value in the neighborhood of **~1.9 dB**. **Stated
explicitly as a rough, unverified extrapolation from three points on a
non-uniform resolution grid — not a converged result.** A resolution-
100 run is in progress (background) to check whether the actual next
gap matches this rough prediction before treating any specific number
as final.

## What this means for the real fan-in decision, stated cautiously

If a value in the ~1.9–2.1 dB/junction range holds up: for `N=8`
(3 stages) the tree's total excess loss would be roughly **6.2 dB**
(`3 × ~2.07`, using the not-yet-final res=80 value) — for `N=16`
(4 stages), roughly **8.3 dB**. Both are **meaningfully worse than the
`~0.1 dB/stage` literature-cited optimistic guess** `mmi_tree_model.py`
assumed, and closer to (though still better than) the `~10·log₁₀(N)`
pessimistic bound (9.0 dB at N=8, 12.0 dB at N=16). **This is not yet
a number to make the `optical.cell.fanin` decision from** — it is a
real, still-refining signal that the optimistic literature estimate
this program was using is probably too optimistic for this specific
combiner-tree implementation, which is itself a genuine, useful thing
to know even before the exact figure is nailed down.

## Recommended next step, in progress

Resolution 100 (reference + junction) is running as a background task
started this session. If it lands close to the ~1.9 dB rough
extrapolation above, that's real evidence of true convergence, and a
value in that neighborhood could reasonably be adopted (with the
usual [M]easured-in-sim tag and this whole convergence history cited)
for feeding into `sax_combiner_model.py` and the fan-in decision. If it
doesn't, the extrapolation was wrong and more resolutions are needed
before trusting any specific figure.
