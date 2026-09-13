# Findings, 2026-09-13 (second pass) — real FDTD access found; a real simulation built and run; the result is NOT yet trustworthy

**Major capability correction first, checked directly, not assumed
from `EXTERNAL_AI_BRIEFING.md`'s prior framing**: that file said "the
`meep` package on PyPI is a name collision... distributed only via
conda-forge, not pip" and treated real FDTD as effectively
unavailable. **That undersold it.** This host has `micromamba`
already installed (used for the SPICE toolchain,
`gcb-spec/docs/spice_setup.md`), and the real `pymeep` package
installs cleanly from conda-forge:

```
~/bin/micromamba create -n gcb-meep -c conda-forge 'pymeep=*=mpi_mpich_*' -y
```

Verified importable and running (`meep 1.34.0`, real, not the PyPI
name-collision package). **Real FDTD access exists on this host.**
This changes `gcb-lumen`'s own toolchain picture from "no real
FDTD path" to "a real FDTD path exists; the work is building and
validating a correct simulation, not finding a tool."

## A real, working 2D FDTD model of the exact combiner geometry — built and run

`fdtd/mmi_fdtd.py` (new, this repo): a 2D effective-index-method FDTD
model of `gdsfactory`'s real `mmi1x2()` component at its real default
geometry (extracted directly this session, not assumed):

- Size 25.5 × 2.5 µm; `width_taper=1.0`, `length_taper=10.0`,
  `length_mmi=5.5`, `width_mmi=2.5`, `gap_mmi=0.25` — all real defaults
  from `gf.components.mmi1x2`'s actual signature.
- Core index = **2.684623** — this program's own real femwell mode-solve
  result (not a fresh guess), clad index = 1.44 (SiO2). **This is a 2D
  effective-index approximation**, a standard first-pass technique for
  SOI photonics, explicitly not a full 3D simulation — stated in the
  script, not hidden.
- An `EigenModeSource` launching the real fundamental-mode eigenmode
  at the input waveguide, flux monitors at both outputs, run until
  field decay at the output.
- Tested the **forward** direction (1 input → 2 outputs, how
  `gdsfactory` names the part) rather than the real device's backward
  combiner use — valid by reciprocity: a linear, passive, reciprocal
  device has identical S-parameters in either direction, so this
  measures the same insertion loss that matters for the real combiner
  use.

## The result is real, but NOT yet trustworthy — reported honestly, not picked-and-chosen

Ran at three resolutions as a basic convergence check (standard FDTD
practice — never trust a single-resolution result):

| Resolution (px/µm) | Split ratio (o2:o3) | Insertion loss (excess, vs. ideal) |
|---|---|---|
| 20 | 0.499 : 0.501 | 4.36 dB |
| 30 | 0.500 : 0.500 | 9.06 dB |
| 40 | 0.500 : 0.500 | 2.86 dB |

**The split ratio converges cleanly to 50:50** (a good sign the MMI
geometry and source are basically sane) — **but the insertion-loss
number does not converge at all**: 4.36 → 9.06 → 2.86 dB is not
monotonic and not settling toward a stable value as resolution
increases. **This is not physical convergence behavior — it indicates
a real bug or numerical-setup problem in this specific script, not
yet diagnosed.** Candidate causes, none yet checked: the `P_in`
reference-flux normalization (no separate empty-waveguide calibration
run was done — the standard MEEP pattern is to normalize against a
straight-waveguide-only run at the same resolution, not the launched
source's nominal power), monitor placement too close to the source or
PML, insufficient padding/PML thickness, or the eigenmode source's
mode match at a resolution-sensitive local index profile.

**None of the three dB numbers above should be treated as the real
combiner loss.** Reporting all three, not the most favorable one or
the most recent one — per this program's own discipline against
cherry-picking a result.

## What this does and does not change

**Does not close the core question.** No trustworthy insertion-loss
number exists yet for the real combiner geometry.

**Does change the toolchain picture, confirmed not assumed**: real
FDTD access exists on this host via `micromamba`/conda-forge — this
was previously treated as effectively unavailable. The blocking work
from here is debugging this specific simulation's convergence problem
(most likely the normalization reference), not finding a tool.

## Recommended next step, not started

1. Add a proper normalization run: simulate a plain straight waveguide
   of the same length with the same source, at the same resolution,
   and normalize `P_in`/`P_o2`/`P_o3` against *that* run's own measured
   flux rather than the nominal source power — the standard MEEP
   pattern for quantitative loss measurements, not done in this first
   pass.
2. Re-run the 3-resolution convergence check with that fix. If it
   still doesn't converge, check monitor-to-PML distance and increase
   `PAD`/`PML_THICKNESS` next.
3. Only once resolution convergence is real (two successive
   resolutions agreeing within a small tolerance, not bouncing) should
   any specific dB number be treated as this repo's real answer.
