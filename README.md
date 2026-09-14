# gcb-lumen

**Want to explore this with another AI chat (ChatGPT, Gemini, etc.)
that has no access to this repo?** Paste
[`EXTERNAL_AI_BRIEFING.md`](EXTERNAL_AI_BRIEFING.md) — it's
self-contained, no repo access required.

**Progress, 2026-09-13 — the core question below is now substantially
answered.** A real day-long arc (`FINDINGS-2026-09-13.md` through
`-v5.md`, each kept in full — three real hypotheses tried and ruled
out before the actual cause was found) ended with a resolution-
converged FDTD result: **per-junction excess loss ≈ 1.96 dB
`[M]easured-in-sim`** (extrapolating to ~1.87 dB at full convergence),
giving a real system-level figure via `sax_combiner_model.py`: **N=8
tree loss ≈ 5.88 dB, N=16 ≈ 7.84 dB** — roughly 15–20× worse than the
literature's original `~0.1 dB/stage` guess this program had been
using, still better than the fully-incoherent pessimistic bound. See
[`FINDINGS-2026-09-13-fdtd-v5.md`](FINDINGS-2026-09-13-fdtd-v5.md) for
the full arc and the real `optical.cell.fanin` comparison this now
supports (4:1 ≈ 3.9 dB vs. 8:1 ≈ 5.9 dB — a real number, not yet a
decision). **Not a bench measurement** — `DECISION_LEDGER.md`
originally asked for one; this is 2D effective-index FDTD, a real but
approximate technique. Flagged for Architect review, not represented
as bench-equivalent.

**One isolated problem: what does the real MMI power-summing combiner
actually cost in insertion loss — and is the first cell 4:1 or 8:1?**

Not a new architecture. Not a new repo for GreenCoyote-Bay's compute
path. This repo exists to grind on one real, currently-blocking
measurement that the rest of the program is waiting on, in isolation,
with both a human-readable framing (this file) and an AI-consumable
context (`ai-agents/ORANGE_TEAM.md`) so a focused session — human or
AI — can pick it up without re-deriving the whole GCB program first.

## The question, stated plainly

`gcb-pic-core/mmi_power_tree.py` already generates a real `gdsfactory`
layout for the power-summing MMI combiner tree, at both real target
sizes (`N_INPUTS_SPEC=8`, Phase-I bench; `N_INPUTS_PHASE2=16`,
Phase-II per-channel). **Nobody has extracted what that layout's
insertion loss and phase-noise actually are.** The toolchain to do it
(`gdsfactory` + `femwell`) is confirmed working — but only on a generic
strip-waveguide mode-solve, not on this specific combiner geometry.

Downstream of that number sits a second, smaller, genuinely open
decision: the first physical reduction cell is **4:1 (cheaper,
published component) or 8:1 (the architecture's real target)** —
[`gcb-spec/bench_emulation_parameters.md`](https://github.com/jagreen03/gcb-spec/blob/main/bench_emulation_parameters.md)
says "likely 4:1 first, 8:1 once the loss regime is known." That's
this repo's second deliverable, strictly downstream of the first.

## What already exists (do not redo this)

- `gcb-pic-core/mmi_power_tree.py` — the real layout generator, both
  target sizes, already passing its own `check()` geometry sanity
  test.
- `gcb-pic-core/mode_solve_strip.py` — the **first real FEM mode-solve**
  this program has ever run: `femwell` on a generic strip waveguide
  (`wg_width=0.5 µm`, `wg_height=0.22 µm` — the textbook 220 nm SOI
  thickness, **not sourced from any GCB spec, flagged as such in the
  script itself**), at `1.31 µm` (O-band, per
  `gcb-spec/bench_emulation_parameters.md`). **Important limit, not a
  loss number:** this script solves for the mode's real effective
  index only — it has no imaginary-index input, so its own comment
  block says plainly its imaginary part is "numerical noise, NOT a
  loss measurement." Nothing in this program has extracted a real
  insertion-loss figure from anything yet.
- The FDTD/EME tooling survey (`TKT-033`) that chose `femwell` over the
  alternatives, and why: the `meep` PyPI package is a name collision
  with an unrelated CI/CD tool (confirmed by unzipping its wheel);
  `tidy3d` needs an external cloud account/API key, not authorized;
  `femwell` is real, open-source, pure-Python, installs in ~90s, no
  license.

## What this repo needs to actually produce

1. An S-parameter / insertion-loss extraction pipeline against the
   **real `mmi_power_tree.py` geometry** — not a generic waveguide —
   at both `N_INPUTS_SPEC=8` and `N_INPUTS_PHASE2=16`. `femwell` alone
   may not be sufficient (it's a mode solver, not a full S-parameter
   circuit tool) — the existing toolchain survey already flagged
   SAX/photontorch as the circuit-level candidate; evaluating whether
   either is actually usable here is part of this repo's job, not
   assumed.
2. A **deliberately ugly first measurement** — Orange-Team doctrine
   (`gcb-workspaces/backlog/TKT-000`): default settings, no geometry
   hand-tuning, report whatever loss number comes out, even if it's
   bad. The bad number is the point; it's silicon-photonics feedback
   this architecture has never had.
3. Only *after* that number exists: revisit `optical.cell.fanin` in
   `gcb-wiki/DECISION_LEDGER.md` with an actual measurement behind the
   choice, instead of the current "likely 4:1 first" guess.

## Not the source of truth

`gcb-spec` is. Every real fact cited above traces to a file in
`gcb-spec`, `gcb-pic-core`, or `gcb-workspaces` — this repo's job is to
produce ONE new real measurement those repos don't have yet, not to
re-describe them.

See [`intent.md`](intent.md) for this repo's formal scope boundary, and
[`ai-agents/ORANGE_TEAM.md`](ai-agents/ORANGE_TEAM.md) for the dense,
AI-session-ready context (paste as a system prompt).
