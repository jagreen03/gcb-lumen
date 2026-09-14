"""mmi_fdtd_single.py - run just ONE configuration (reference-only or
full-junction) of mmi_fdtd_v2.py's model at a given resolution, as its
own process.

Why this exists: mmi_fdtd_v2.py's run_at() runs both configurations
sequentially in one process. That's fine at low resolution, but at
resolution 80 the junction-geometry run alone took 745s - too long to
fit alongside its reference run in a single bounded invocation. This
wrapper imports the same build() function (no reimplementation, no
duplicated geometry/physics) and runs exactly one configuration, so
each can be launched as its own separately-timed/backgrounded process.

Usage: python mmi_fdtd_single.py <resolution> <reference|junction>
"""
import importlib.util
import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mmi_fdtd_v2", script_dir / "mmi_fdtd_v2.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

resolution = int(sys.argv[1])
include_junction = sys.argv[2] == "junction"

p_in, p_o2, p_o3 = mod.build(resolution, include_junction=include_junction)
if include_junction:
    print(f"[single res={resolution} junction] P_in={p_in:.6e} P_o2={p_o2:.6e} P_o3={p_o3:.6e}")
else:
    print(f"[single res={resolution} reference] P_in_ref={p_in:.6e}")
