"""sax_combiner_model.py - a real, working SAX circuit-level model of
gcb-pic-core/mmi_power_tree.py's combiner-tree topology, at both real
target sizes (N=8 Phase-I bench, N=16 Phase-II integrated array).

Origin: an external AI chat (pasted through EXTERNAL_AI_BRIEFING.md's
prompt) suggested "SAX + an assumed per-junction excess loss, cascaded"
as the practical path to a system-level loss number without a
commercial/cloud tool. See FINDINGS-2026-09-13.md for the full
evaluation of that response, including what checked out and what
didn't. This file is the part that checked out: SAX (pip: `sax`) is
real, installs cleanly, and this model is real, runnable, verified
code - not a description of a plan.

**What this file DOES NOT do**: it does not know the real per-junction
excess loss. EXCESS_LOSS_DB below is an ASSUMED placeholder (the
literature figure mmi_tree_model.py already cites, ~0.1 dB, plus a
second, more pessimistic guess at 0.3 dB for comparison) - swap in a
real extracted or measured number the moment one exists (from a
femwell-based extraction against this exact geometry, a literature
value with a real citation, or a bench measurement) and every result
below updates automatically.

Physics, checked against gcb-rtl/sim/mmi_tree_model.py's own
description ("a POWER-SUMMING combiner with excess loss ONLY"): a
coherent 2:1 combiner used this way is a balanced coupler in reverse -
two in-phase, equal-amplitude inputs combine LOSSLESSLY in the ideal
case (out = (in1+in2)/sqrt(2), which conserves power when in1=in2).
Only the "excess loss" beyond that ideal behavior is unknown.

Real bug found and fixed while writing this (recorded here, not
silently corrected, per this program's own discipline): the first
version of this script compared the tree's real output amplitude
against an "ideal" reference of N (treating amplitudes as simply
additive) instead of sqrt(N) (the correct reference for N coherent
unit-amplitude inputs combining losslessly into ONE output port, by
energy conservation: ideal output POWER = N, so ideal output
AMPLITUDE = sqrt(N)). The bug manifested as a spurious extra
~10*log10(N) dB of "loss" that was actually just a wrong reference
point, not a real physical loss - caught by hand-deriving the 3-stage
N=8 cascade algebraically and finding the script's number didn't
match. Fixed; the numbers below are post-fix.

Run: python sax_combiner_model.py
Requires: pip install -r requirements-sax.txt (installs sax, jax, and
their dependencies - a much lighter/faster install than gdsfactory or
femwell, no native build, ~30s).

Epistemic status: PROVEN - DIGITAL CIRCUIT-MODEL SIMULATION, TESTED
CONDITIONS that this SAX model correctly reproduces the expected
cascaded-loss arithmetic for this exact tree topology (confirmed: at
EXCESS_LOSS_DB=0.1, N=8 gives exactly 0.30 dB and N=16 gives exactly
0.40 dB, matching 0.1 dB/stage * 3 and * 4 stages exactly, and matching
the existing literature-cited estimate this repo already assumed).
UNPROVEN: the real EXCESS_LOSS_DB value for the real fabricated
geometry - that is still the open question this repo exists to answer.
"""
import sax
import jax.numpy as jnp

EXCESS_LOSS_DB_OPTIMISTIC = 0.1  # mmi_tree_model.py's own literature-cited estimate
EXCESS_LOSS_DB_UPPER = 0.3       # the external AI's suggested upper end - also unsourced, tested for comparison only
# [M]easured-in-sim, 2026-09-13: real FDTD (pymeep) of the actual mmi1x2()
# geometry, resolution-converged through res=100 px/um (FINDINGS-2026-09-13-fdtd-v4/v5.md):
# 2.87 (res=40) -> 2.30 (60) -> 2.07 (80) -> 1.96 dB (100), shrinking gaps
# (ratio ~0.44 each step) extrapolating to ~1.87 dB at full convergence.
# Using the last real data point (1.96 dB), NOT the extrapolation, as the
# tagged [M]easured value - the extrapolation is a derived estimate, kept
# separate and clearly labeled.
EXCESS_LOSS_DB_MEASURED = 1.96      # [M] res=100, not yet at the true asymptote
EXCESS_LOSS_DB_EXTRAPOLATED = 1.87  # [D] geometric extrapolation from 4 points, NOT measured

def mmi2x1_combiner(excess_loss_db: float = 0.1):
    """A 2-input, 1-output coherent power combiner with a given excess
    loss (the ONLY unknown loss mechanism - the ideal 1/sqrt(2) combine
    is lossless by construction, matching this program's own physics)."""
    amp = 10 ** (-excess_loss_db / 20.0)  # amplitude multiplier from dB power loss

    def model(wl=1.31):
        s = amp / jnp.sqrt(2.0)
        return sax.reciprocal({
            ("in1", "out"): s,
            ("in2", "out"): s,
        })
    return model


def build_tree_netlist(n_inputs: int, excess_loss_db: float):
    """Build a SAX circuit netlist for an n_inputs binary combiner tree
    (n_inputs a power of 2), matching mmi_power_tree.py's own topology:
    n/2 leaf units -> .. -> 1 final unit."""
    n_stages = n_inputs.bit_length() - 1  # log2(n_inputs)
    instances = {}
    connections = {}
    ports = {}

    stage_names = [f"u{i}" for i in range(n_inputs // 2)]
    for name in stage_names:
        instances[name] = "mmi2x1"

    stage = 0
    cur = stage_names
    leaf_idx = 0
    for u in cur:
        ports[f"in{leaf_idx}"] = f"{u},in1"
        leaf_idx += 1
        ports[f"in{leaf_idx}"] = f"{u},in2"
        leaf_idx += 1

    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur), 2):
            name = f"s{stage}_{i // 2}"
            instances[name] = "mmi2x1"
            connections[f"{cur[i]},out"] = f"{name},in1"
            connections[f"{cur[i+1]},out"] = f"{name},in2"
            nxt.append(name)
        cur = nxt
        stage += 1

    ports["out"] = f"{cur[0]},out"
    return {"instances": instances, "connections": connections, "ports": ports}, n_stages


for n_inputs, label in ((8, "Phase-I bench"), (16, "Phase-II integrated array")):
    print(f"--- N={n_inputs} ({label}) ---")
    for excess_loss_db in (
        EXCESS_LOSS_DB_OPTIMISTIC,
        EXCESS_LOSS_DB_UPPER,
        EXCESS_LOSS_DB_MEASURED,
        EXCESS_LOSS_DB_EXTRAPOLATED,
    ):
        netlist, n_stages = build_tree_netlist(n_inputs, excess_loss_db)
        circuit, _ = sax.circuit(
            netlist=netlist,
            models={"mmi2x1": mmi2x1_combiner(excess_loss_db)},
        )
        s = circuit(wl=1.31)
        # All N inputs driven in-phase, equal amplitude 1.0 - ideal case for
        # this coherent-summing architecture (matches the balanced-homodyne
        # "constructive interference" physics this program's whole compute
        # mechanism depends on).
        total_amp_out = sum(abs(s[(f"in{i}", "out")]) for i in range(n_inputs))
        # CORRECTED after a first wrong pass: for N coherent, equal-amplitude,
        # in-phase inputs combining losslessly into ONE output port, energy
        # conservation gives ideal OUTPUT POWER = N (not amplitude = N) - so
        # ideal amplitude = sqrt(N), not N. Using N here was a real bug in
        # this script's first run; caught by hand-deriving the 3-stage
        # cascade algebraically and finding it didn't match.
        ideal_amp_out = float(n_inputs) ** 0.5
        insertion_loss_db = -20 * jnp.log10(total_amp_out / ideal_amp_out)
        per_stage_db = float(insertion_loss_db) / n_stages
        print(
            f"  assumed excess_loss/junction={excess_loss_db:.2f} dB -> "
            f"{n_stages} stages, total insertion loss vs ideal = {float(insertion_loss_db):.4f} dB "
            f"({per_stage_db:.4f} dB/stage, should equal the assumed value exactly for a linear cascade)"
        )
