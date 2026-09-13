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
  is conda-forge-only under that name).
- `tidy3d` — real FDTD, but needs an external cloud account/API key;
  this program has not authorized creating one.
- `SAX` / `photontorch` — named as candidate circuit-level
  (S-parameter) tools in this program's own toolchain notes, but
  **neither has actually been used yet**.

## The actual question to help with

**Given an `mmi1x2`-based binary power-combiner tree (geometry above,
3 stages for N=8 / 4 stages for N=16, single wavelength ~1.31 µm,
strip waveguide 0.5 µm × 0.22 µm, Si/SiO2), what's the most practical
open-source path to a real insertion-loss number** — per-junction
mode-mismatch loss from a femwell-class mode solver, a circuit-level
S-parameter roll-up (SAX/photontorch), a simpler analytic/empirical
estimate, or something else? And: **once that number exists, how would
you actually decide 4:1 vs. 8:1 from it** — what's the right
loss-vs-fan-in tradeoff framing, given the existing "~0.1 dB/stage
optimistic vs. ~10·log₁₀(N) dB/stage pessimistic" bounds above?

**How to work this problem (the house style for this program):**
measure first with default/unoptimized settings — a bad loss number is
a *useful* result, not a failure. Don't hand-tune anything to make the
number look good. Say explicitly what loss mechanism any estimate
actually captures (mode mismatch? material absorption? none of the
above?) and what it doesn't.
