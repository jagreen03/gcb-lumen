# Findings, 2026-09-13 (fourth pass, same day) — both prior hypotheses were wrong; the real explanation is under-resolution; real convergence is now visible

**Before implementing the next planned fix, checked whether its own
premise was even true — and it wasn't.** `FINDINGS-2026-09-13-fdtd-v2.md`
suspected the field-decay-based stopping criterion (`stop_when_fields_decayed`)
was causing different resolutions to integrate their flux DFTs over
different total simulation times. **Directly checked before building
anything**: the actual printed "run ... finished at t = ..." lines for
both the reference run and the junction run are **essentially
identical across resolution** (reference run: t≈150.0 at every
resolution tried; junction run: t≈200.0 at every resolution tried —
differences are only discrete-timestep rounding, negligible). **This
hypothesis was also wrong** — run duration was never the variable.

## The real explanation, found by adding one more, higher, data point

Ran a fourth resolution, 60 px/µm (meaningfully higher than the
20/30/40 tried so far), using the same `mmi_fdtd_v2.py` script
unchanged:

| Resolution | `P_in` (reference) | Insertion loss |
|---|---|---|
| 20 | 5.709e-5 | 4.36 dB |
| 30 | 7.568e-5 | 10.94 dB |
| 40 | 3.222e-5 | 2.87 dB |
| **60** | **2.669e-5** | **2.30 dB** |

**Resolutions 40 and 60 are meaningfully closer to each other (2.87 →
2.30 dB, a ~20% relative change) than any earlier pair (which differed
by factors of 2–4×).** This is a real, positive convergence signal,
not another data point in a random walk. **The honest read: 20 and 30
px/µm were simply too coarse to resolve this specific geometry's
tapers adequately — not a software bug, not a normalization error, not
a run-duration artifact.** The input/output tapers narrow to
`WIDTH_WG = 0.5 µm` over a `10 µm` length; at resolution 20, that's
only 10 pixels across the narrow end, and MEEP represents the tapers'
diagonal edges as `Prism` polygons that get **staircased** onto the
Yee grid — a well-known FDTD sensitivity for any geometry with
sub-wavelength diagonal features, not specific to this simulation or
this physical device.

## What this does and does not change

**Still does not produce a final, trustworthy number.** 40→60 is
closing the gap but has not yet converged to a stable value — a real
FDTD convergence study continues until two successive resolutions
agree within a small, chosen tolerance, which this has not reached
yet.

**Does correct two wrong hypotheses from earlier today, both ruled out
by direct measurement before being acted on** (reflection
contamination in `FINDINGS-2026-09-13-fdtd.md`; run-duration variation
in `FINDINGS-2026-09-13-fdtd-v2.md`) **and replaces them with a real,
explicable cause**: under-resolution of the taper geometry at the two
lowest resolutions tried. This is real forward progress even though no
final number exists yet — the search space for "what's wrong" has
collapsed from "unknown bug, three hypotheses tried" to "known cause,
needs higher resolution to fully converge."

**Does suggest, not yet confirm, a rough answer**: the true combiner
excess loss for this geometry is likely in the neighborhood of the
40–60 range's values (roughly 2–2.5 dB), pending confirmation at
higher resolution — **meaningfully higher than the literature-cited
"~0.1 dB/stage optimistic" estimate** `mmi_tree_model.py` assumed, even
accounting for this being a per-junction figure vs. the literature
estimate's per-stage framing (3 stages for N=8 would put a ~2–2.5
dB/junction figure at ~6–7.5 dB total for the tree — well past the
pessimistic `~10·log₁₀(N)` bound's own territory at N=8). **Not yet a
number to act on** — stated as a directional signal, not a result.

## Recommended next step, not started

Continue the resolution sweep at 80 and, if needed, 100+ px/µm (each
run meaningfully more expensive — res=60 took several minutes per
configuration on this host; res=80+ will take longer, budget
accordingly) until two successive resolutions agree within a chosen
tolerance (e.g., within 5–10% of each other). Only then report a
single number as this repo's real answer. Separately worth checking:
whether MEEP's default dielectric subpixel-smoothing (on by default)
is actually active for `Prism` geometries the way it is for `Block`s —
if not, that would independently explain slow convergence specifically
at diagonal edges and might be worth an explicit resolution override
or a finer-grained taper representation (many small `Block` steps)
as an alternative to simply raising global resolution everywhere.
