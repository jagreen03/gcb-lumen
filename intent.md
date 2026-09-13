# Intent: gcb-lumen

## Scope

**One measurement, two deliverables, in order:**

1. A real insertion-loss / phase-noise extraction against the actual
   `gcb-pic-core/mmi_power_tree.py` MMI combiner geometry, at
   `N_INPUTS_SPEC=8` and `N_INPUTS_PHASE2=16`.
2. A measurement-backed answer to `optical.cell.fanin`
   (`gcb-wiki/DECISION_LEDGER.md`): 4:1 or 8:1 for the first physical
   reduction cell — this step does not start until (1) produces a real
   number.

## Out of scope

- Redesigning the combiner topology, the waveguide cross-section, or
  the MZI mesh architecture. This repo measures what already exists;
  it does not propose alternatives.
- The laser/modulator bank's spec (that's `gcb-lambda`).
- The analog Rx front-end's noise gate (that's `gcb-kelvin`).
- Any claim about real foundry manufacturability. ASAP7-class and
  academic-PDK caveats elsewhere in this program apply equally here —
  this is simulation/extraction work, not a tapeout input.

## Governing discipline

Orange-Team "Physical Reality First"
(`gcb-workspaces/backlog/TKT-000-orange-team-epoch-guidance.md`):
measure first, with a deliberately ugly/unoptimized first pass; the
*report* is the deliverable, not a polished layout. Interpret the
number next. Change the architecture (combiner topology, fan-in
choice) only from the measurement — never pre-emptively, never inside
the measurement pass itself.

## Relationship to the rest of the program

This repo **consumes** `gcb-pic-core`'s existing layout generator and
**feeds** a number back into `gcb-wiki/DECISION_LEDGER.md`'s
`optical.cell.fanin` entry. It does not fork or duplicate
`gcb-pic-core` — if the extraction pipeline needs new code, it
imports/calls `mmi_power_tree.py` rather than copying it.
