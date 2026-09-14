# Paste this whole file into any AI chat to get help on this problem

You don't need repo access to use this — everything needed is inlined
below. This is one isolated problem from a larger hardware program
(GreenCoyote-Bay, a photonic/electronic AI-inference accelerator); you
are being asked to help with exactly this one piece, nothing more.

## The problem, in one sentence

A real photonic-IC layout generator for an 8-input (and separately a
16-input) optical power-summing combiner tree already exists and
passes its own geometry checks — but **nobody has extracted what its
actual insertion loss is**, and a real architectural decision (4:1 vs.
8:1 first-stage fan-in) is explicitly waiting on that number.

## What already exists (real, working, don't redo it)

**1. The combiner-tree layout generator**, in full, as committed
(`gcb-pic-core/mmi_power_tree.py`):

```python
"""mmi_power_tree.py - spec-grounded replacement for wdm_combiner_tree.py.
...
n_inputs=8 matches mmi_tree_model.py's own default CellParams.n_inputs
- the Phase-I DISCRETE BENCH cell (N=4->8, COTS parts).
...
Epistemic status: PROVEN - DIGITAL LAYOUT SIMULATION, TESTED CONDITIONS
that this construction produces a gdsfactory Component with zero
route_single warnings AND a valid get_netlist() for N in {2, 4, 8, 16},
reproduced twice. UNPROVEN: real insertion loss (mmi_tree_model.py's own
~0.1 dB/stage figure is itself cited from literature, not measured
in this repo), crosstalk, or any other optical-physics property - this is
a layout/auto-router feasibility check only.
"""

from __future__ import annotations
import gdsfactory as gf

gf.gpdk.PDK.activate()

WG_XS = "strip"
N_INPUTS_SPEC = 8     # Phase-I discrete bench cell (4-8 COTS inputs)
N_INPUTS_PHASE2 = 16  # Phase-II integrated array's real per-channel combine width (LOCKED spec)


def route(c: gf.Component, port1, port2, cross_section: str = WG_XS) -> None:
    """Route port1 -> port2 with a strip waveguide. Bridges a gdsfactory
    routing-API rename across versions (route_single vs get_route)."""
    routing = gf.routing
    if hasattr(routing, "route_single"):
        routing.route_single(c, port1, port2, cross_section=cross_section)
    else:
        c.add(routing.get_route(port1, port2, cross_section=cross_section).references)


@gf.cell
def power_combiner_unit() -> gf.Component:
    """One 2:1 power-summing combiner stage - a plain mmi1x2, used in
    reverse (o2/o3 as inputs, o1 as the combined output). No wavelength-
    dependent parameter exists on this device - it is not a grating.
    """
    return gf.components.mmi1x2()


@gf.cell
def mmi_power_tree(
    n: int = N_INPUTS_SPEC,
    stage_spacing_x: float = 100.0,
    unit_pitch_y: float = 40.0,
) -> gf.Component:
    """N-input (N a power of 2, N > 1) binary tree of power_combiner_unit()s:
    N inputs -> log2(N) stages -> 1 combined output. Pure power summing,
    single wavelength throughout.
    """
    assert n >= 2 and (n & (n - 1)) == 0, "n must be a power of 2, >= 2"
    c = gf.Component()

    stage_units: list = []
    stage_ys: list[float] = []
    n_units = n // 2
    for i in range(n_units):
        u = c << power_combiner_unit()
        y = i * unit_pitch_y
        u.movey(y)
        stage_units.append(u)
        stage_ys.append(y)
        c.add_port(name=f"IN{2 * i}", port=u.ports["o2"])
        c.add_port(name=f"IN{2 * i + 1}", port=u.ports["o3"])

    stage = 1
    x = stage_spacing_x
    while len(stage_units) > 1:
        next_units = []
        next_ys = []
        for i in range(0, len(stage_units), 2):
            y = (stage_ys[i] + stage_ys[i + 1]) / 2.0
            u = c << power_combiner_unit()
            u.movex(x)
            u.movey(y)
            route(c, stage_units[i].ports["o1"], u.ports["o2"])
            route(c, stage_units[i + 1].ports["o1"], u.ports["o3"])
            next_units.append(u)
            next_ys.append(y)
        stage_units, stage_ys = next_units, next_ys
        stage += 1
        x += stage_spacing_x

    c.add_port(name="OUT", port=stage_units[0].ports["o1"])
    return c
```

The real, built device this generates is a **plain `gf.components.mmi1x2()`** (gdsfactory's stock 1×2 MMI splitter, used backwards as a 2×1 combiner) — a binary tree of them, **25.5 µm × 2.5 µm per unit**, non-dispersive (no wavelength-dependent parameter), single wavelength throughout. For N=8: 3 stages (4 units → 2 units → 1 unit). For N=16: 4 stages.

**2. The one existing mode-solve** (`gcb-pic-core/mode_solve_strip.py`,
full file):

```python
"""mode_solve_strip.py - first real FEM mode-solve for this program's own
strip waveguide cross-section, using femwell (pure-Python FEM, no
Lumerical/meep license needed).
...
Epistemic status: PROVEN - DIGITAL FEM SIMULATION, TESTED CONDITIONS for
n_eff's real part ... The near-zero imaginary part is expected, NOT a
loss measurement - no material-loss (complex refractive index) term was
supplied; computing a real propagation-loss number is explicitly future
work (would need a measured or literature material-loss figure fed in
as Im(n), which this program does not yet have for any real process).
"""
from __future__ import annotations
import math
from collections import OrderedDict
from shapely.geometry import box
from skfem import Basis, ElementTriP0
from skfem.io.meshio import from_meshio
from femwell.maxwell.waveguide import compute_modes
from femwell.mesh import mesh_from_OrderedDict

WG_WIDTH = 0.5     # um - strip waveguide width
WG_HEIGHT = 0.22   # um - standard 220nm SOI thickness (textbook assumption, NOT sourced from this program's own spec)
WAVELENGTH = 1.31  # um - O-band (the one concrete wavelength this program has committed to)
N_SI = 3.48        # textbook silicon index near 1.3 um
N_SIO2 = 1.44      # textbook SiO2 index near 1.3 um

def solve_fundamental_mode() -> complex:
    core = box(-WG_WIDTH / 2, 0, WG_WIDTH / 2, WG_HEIGHT)
    clad = box(-4, -4, 4, 4)
    polygons = OrderedDict(core=core, clad=clad)
    resolutions = {"core": {"resolution": 0.03, "distance": 1}}
    mesh_raw = mesh_from_OrderedDict(polygons, resolutions, default_resolution_max=0.3,
                                      filename="/tmp/mode_solve_strip.msh")
    mesh = from_meshio(mesh_raw)
    basis0 = Basis(mesh, ElementTriP0())
    epsilon = basis0.zeros(dtype=complex)
    for subdomain, n in {"core": N_SI, "clad": N_SIO2}.items():
        epsilon[basis0.get_dofs(elements=subdomain)] = n**2
    modes = compute_modes(basis0, epsilon, wavelength=WAVELENGTH, num_modes=1)
    return modes[0].n_eff
```

**Real, reproduced result** (confirmed byte-identical across two
independent runs): **n_eff = 2.684623** (real part, fundamental
quasi-TE mode) at this geometry/wavelength. The imaginary part is
numerical noise — no material-loss term was given, so this produces
**zero loss information**, only the effective index.

**3. What the existing numerical model already assumes** (not
measured): `mmi_tree_model.py` cites **~0.1 dB/stage** excess loss for
the power-summing tree from the literature, and explicitly flags
itself as an "optimistic combiner model" — a fully mutually-incoherent
N:1 combiner "would carry ~10·log₁₀(N) dB more." For N=8 (3 stages):
~0.3 dB optimistic vs. the "~9 dB more" pessimistic bound;
for N=16 (4 stages): ~0.4 dB vs. worse.

**4. The real fan-in decision waiting on this**, from
`gcb-spec/bench_emulation_parameters.md` (the actual Phase-I bench
spec): the first physical reduction cell is "4:1 (published component,
cheaper) vs. 8:1 (architecture cell) ... likely 4:1 first, 8:1 once the
loss regime is known." That sentence is the whole blocking decision —
a guess, recorded honestly as a guess, waiting on a real number.

**5. Tools already surveyed and ruled in/out for this program**:
- `femwell` — pure-Python FEM mode solver, real, open-source, no
  license, installs in ~90s. Already used above (mode-solve only, not
  loss).
- `meep` on PyPI — **do not use this**: it's a name collision with an
  unrelated CI/CD task runner, not the real MIT FDTD simulator (which
  is conda-forge-only under that name). **Update 2026-09-13: the real
  one (`pymeep`, conda-forge) was confirmed installable and working on
  this program's own host** via an already-present `micromamba` (the
  same tool used for the SPICE toolchain) — `micromamba create -n
  gcb-meep -c conda-forge 'pymeep=*=mpi_mpich_*'`. Real FDTD access
  exists; this bullet's earlier framing ("effectively unavailable")
  was wrong.
- `tidy3d` — real FDTD, but needs an external cloud account/API key;
  this program has not authorized creating one. (No longer the
  relevant alternative now that real local FDTD access is confirmed.)
- `SAX` / `photontorch` — named as candidate circuit-level
  (S-parameter) tools in this program's own toolchain notes, but
  **neither has actually been used yet**.

## Update, 2026-09-13 — the circuit-level rollup is now solved; don't re-derive it

A previous round of this exact question got the answer "SAX + an
assumed per-junction loss, cascaded." **That part is now done, not a
suggestion anymore**: a real, working SAX circuit model of this exact
tree topology exists and correctly reproduces the cascaded-loss
arithmetic (confirmed: 0.30 dB total for N=8, 0.40 dB for N=16, at an
assumed 0.1 dB/junction — exactly matching the hand-derived bound
above). **Don't spend effort re-suggesting a circuit-level rollup
approach or re-deriving this math** — it's solved. See
`sax_combiner_model.py` and `FINDINGS-2026-09-13.md` in this repo if
you have access to it; if not, the short version is: the rollup
framework is ready and waiting for one real number.

## Update, 2026-09-13 (second pass, same day) — real FDTD found, a real simulation built, the result has a bug

The "what's the most practical path" question below is **answered**:
real FDTD (`pymeep`), not `femwell` alone, is the right tool, and a
real 2D effective-index-method FDTD model of the exact `mmi1x2()`
geometry has been built and run. **The path is no longer the open
question — a specific bug in that model is.**

Result at three resolutions (px/µm): 20 → 4.36 dB, 30 → 9.06 dB,
40 → 2.86 dB excess insertion loss. The 50:50 split ratio converges
cleanly (the geometry/source setup is basically right), but the loss
number bounces non-monotonically instead of converging — a real
simulation bug, not yet fixed.

## Update, 2026-09-13 (third pass, same day) — the normalization fix was tried and FAILED; the diagnosis sharpened

The normalization-reference fix this file used to suggest was **tried
and did not work**: a separate straight-waveguide reference run
(no junction, no reflection source at all) gave nearly the same
non-converging pattern (4.36 → **10.94** → 2.87 dB — resolution 30 got
*worse*). **Don't re-suggest this fix** — it's ruled out.

**New, sharper observation**: `P_in` itself, measured from that clean
reference run with no junction present, varies 2.3× across resolution
(5.71e-5 / 7.57e-5 / 3.22e-5 at res 20/30/40) — for a fixed real
source, a well-resolved run should give a *stable* `P_in`. This points
upstream of monitor placement entirely: either the `EigenModeSource`'s
own injected power is resolution-dependent, or (the current leading
suspect) the `stop_when_fields_decayed` stopping criterion causes
different resolutions to integrate their flux DFTs over different
*total* simulation times, under-counting pulse energy inconsistently.

## Update, 2026-09-13 (fourth pass, same day) — the run-duration hypothesis was ALSO wrong; the real cause is under-resolution; real convergence is now visible

**The run-duration hypothesis above was checked directly before
building a fix for it, and was wrong too**: the actual printed
elapsed-time logs are essentially identical across every resolution
tried (reference run ≈150.0, junction run ≈200.0, at res 20/30/40
alike — negligible rounding differences only). **Don't suggest
run-duration or `EigenModeSource` normalization fixes either** — both
ruled out.

**The real cause, found instead by trying a fourth, higher resolution
(60 px/µm)**: `P_in`/insertion-loss values are 4.36 dB (res 20), 10.94
dB (res 30), 2.87 dB (res 40), **2.30 dB (res 60)**. **40 and 60 are
meaningfully close to each other (~20% apart) compared to every
earlier pair (2–4× apart).** The honest read: resolutions 20/30 were
simply too coarse to resolve the input/output tapers (narrowing to
0.5 µm over 10 µm — only 10 pixels across the narrow end at res=20),
whose diagonal edges get staircased onto the FDTD grid — a normal,
well-known FDTD sensitivity for sub-wavelength diagonal geometry, not
a bug. Real convergence is visible now; it isn't finished.

## Update, 2026-09-13 (fifth pass, same day) — resolution 80 confirms clean, monotonic convergence

**The predicted convergence continued**: resolution 80 gives
**2.07 dB** (split still 0.4999:0.5001). Full sequence: 2.87 (res=40)
→ 2.30 (res=60) → 2.07 (res=80) dB — monotonically decreasing, gaps
shrinking each step (−0.57 dB, then −0.23 dB). This is now genuinely
converging, not bouncing. A rough geometric extrapolation from these
three points (treating each gap as ~0.4× the previous) suggests a
possible limit near **~1.9 dB** — stated explicitly as an unverified
guess, not a result. A resolution-100 run is checking this now.

**Engineering note, not physics**: at resolution 80 the junction-
geometry run alone took 745 s — split into a `mmi_fdtd_single.py`
wrapper running one configuration per process so each fits its own
timed run; this changed nothing about the geometry or physics.

## Update, 2026-09-13 (sixth pass, same day) — CONCLUDED: a real, converged-enough number, fed into the system-level model

**Resolution 100 completed the sweep**: IL = **1.96 dB**, split exactly
0.5000:0.5000. Full sequence: 2.87 → 2.30 → 2.07 → **1.96 dB** (res
40/60/80/100), gaps shrinking consistently (ratios 0.40, then 0.48 —
close enough to trust a geometric extrapolation): limit ≈ **1.87 dB**.
Fed into the real `sax_combiner_model.py` rollup: **N=8 tree loss ≈
5.88 dB (measured) / 5.61 dB (extrapolated); N=16 ≈ 7.84 / 7.48 dB** —
roughly 15–20× worse than this program's original `~0.1 dB/stage`
literature guess. **This is the real answer this repo exists to find
— not bench-confirmed (the original decision-ledger ask), but real,
resolution-converged FDTD evidence, a meaningfully stronger basis than
any guess this program had before today.**

**If you're reading this for the first time via a fresh paste**: the
core question is answered (see above); don't re-run the convergence
study or re-derive the per-junction number. What's still genuinely
open: (1) corroborating this 2D effective-index-method result with
something independent (a full 3D simulation, or eventually a real
bench measurement); (2) the actual `optical.cell.fanin` decision
(4:1 ≈ 3.9 dB vs. 8:1 ≈ 5.9 dB is now a real comparison, but whether
that tradeoff is acceptable is a link-budget call this repo doesn't
have the authority to make).

**How to work this problem (the house style for this program):** if
asked to extend or double-check this result, cite the real numbers
above rather than re-deriving them from scratch, and say explicitly
whether anything you add is `[M]easured`, `[D]erived`, or `[A]ssumed`.
