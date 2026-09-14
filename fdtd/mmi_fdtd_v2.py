"""mmi_fdtd.py (v2) - fixes the normalization bug found in v1
(FINDINGS-2026-09-13-fdtd.md): P_in was measured 0.5um after the
source, in the SAME run as the MMI junction, so any power reflected
back from the junction travels back through that monitor plane and
contaminates the net flux there - a resolution-dependent effect (the
taper's reflection coefficient is itself resolution-sensitive), which
is exactly the kind of thing that produces a non-monotonic, not-merely-
biased swing across resolutions, matching what v1 actually showed
(4.36 -> 9.06 -> 2.86 dB, not a consistent offset).

Fix: measure P_in from a SEPARATE reference run containing ONLY the
input waveguide + taper (no MMI, no outputs) - a clean run with no
reflection source at all, same resolution, same source. This is the
standard MEEP pattern for quantitative transmission/insertion-loss
measurements (the "normalize against a straight-waveguide reference
run" pattern), not done in v1.
"""
import math
import meep as mp

WAVELENGTH = 1.31
N_CORE = 2.684623
N_CLAD = 1.44

WIDTH_WG = 0.5
WIDTH_TAPER = 1.0
LENGTH_TAPER = 10.0
LENGTH_MMI = 5.5
WIDTH_MMI = 2.5
GAP_MMI = 0.25

PML_THICKNESS = 1.0
PAD = 2.0

fcen = 1 / WAVELENGTH
df = 0.2 * fcen
y_off = (WIDTH_TAPER + GAP_MMI) / 2


def taper_polygon(x_start, width_start, width_end, length):
    x_end = x_start + length
    return [
        mp.Vector3(x_start, -width_start / 2, 0),
        mp.Vector3(x_start, width_start / 2, 0),
        mp.Vector3(x_end, width_end / 2, 0),
        mp.Vector3(x_end, -width_end / 2, 0),
    ]


def build(resolution, include_junction):
    core = mp.Medium(index=N_CORE)
    clad = mp.Medium(index=N_CLAD)

    if include_junction:
        sx = LENGTH_TAPER + LENGTH_MMI + LENGTH_TAPER + 2 * PAD
    else:
        # reference run: just the input taper + enough run-out to avoid
        # a reflection off the cell boundary itself mattering (PML handles
        # that, but keep it geometrically simple and short - only the
        # input side is under test here).
        sx = LENGTH_TAPER + 2 * PAD
    sy = WIDTH_MMI + 4 * PAD
    cell = mp.Vector3(sx, sy, 0)
    x0 = -sx / 2 + PAD

    geometry = []
    x = x0 - PAD
    geometry.append(mp.Block(
        center=mp.Vector3(x + PAD / 2, 0, 0),
        size=mp.Vector3(PAD, WIDTH_WG, mp.inf),
        material=core,
    ))
    x = x0
    geometry.append(mp.Prism(taper_polygon(x, WIDTH_WG, WIDTH_TAPER, LENGTH_TAPER), height=mp.inf, material=core))
    x += LENGTH_TAPER

    if include_junction:
        geometry.append(mp.Block(
            center=mp.Vector3(x + LENGTH_MMI / 2, 0, 0),
            size=mp.Vector3(LENGTH_MMI, WIDTH_MMI, mp.inf),
            material=core,
        ))
        x += LENGTH_MMI
        for sign in (+1, -1):
            pts = [
                mp.Vector3(x, sign * y_off - WIDTH_TAPER / 2, 0),
                mp.Vector3(x, sign * y_off + WIDTH_TAPER / 2, 0),
                mp.Vector3(x + LENGTH_TAPER, sign * y_off + WIDTH_WG / 2, 0),
                mp.Vector3(x + LENGTH_TAPER, sign * y_off - WIDTH_WG / 2, 0),
            ]
            geometry.append(mp.Prism(pts, height=mp.inf, material=core))
            geometry.append(mp.Block(
                center=mp.Vector3(x + LENGTH_TAPER + PAD / 2, sign * y_off, 0),
                size=mp.Vector3(PAD, WIDTH_WG, mp.inf),
                material=core,
            ))
        x_out = x + LENGTH_TAPER
    else:
        # reference run: add a plain straight run-out of the same taper
        # end-width, just to give the field somewhere clean to settle
        # before the PML, mirroring the real run's far-field behavior.
        geometry.append(mp.Block(
            center=mp.Vector3(x + PAD / 2, 0, 0),
            size=mp.Vector3(PAD, WIDTH_TAPER, mp.inf),
            material=core,
        ))
        x_out = x

    src_x = x0 - PAD + 0.3
    sources = [
        mp.EigenModeSource(
            src=mp.GaussianSource(fcen, fwidth=df),
            center=mp.Vector3(src_x, 0, 0),
            size=mp.Vector3(0, WIDTH_MMI + 2, 0),
            eig_band=1,
            eig_match_freq=True,
        )
    ]

    sim = mp.Simulation(
        cell_size=cell,
        resolution=resolution,
        boundary_layers=[mp.PML(PML_THICKNESS)],
        geometry=geometry,
        sources=sources,
        default_material=clad,
        dimensions=2,
    )

    mon_x_in = src_x + 0.5
    flux_in = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(mon_x_in, 0, 0), size=mp.Vector3(0, WIDTH_MMI + 2, 0)))

    if include_junction:
        mon_x_out = x_out - 0.3
        flux_o2 = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(mon_x_out, y_off, 0), size=mp.Vector3(0, 1.5, 0)))
        flux_o3 = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(mon_x_out, -y_off, 0), size=mp.Vector3(0, 1.5, 0)))
        decay_pt = mp.Vector3(mon_x_out, y_off, 0)
    else:
        flux_o2 = flux_o3 = None
        decay_pt = mp.Vector3(x_out - 0.3, 0, 0)

    sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, decay_pt, 1e-4))

    p_in = mp.get_fluxes(flux_in)[0]
    if include_junction:
        return p_in, mp.get_fluxes(flux_o2)[0], mp.get_fluxes(flux_o3)[0]
    return p_in, None, None


def run_at(resolution):
    p_in_ref, _, _ = build(resolution, include_junction=False)
    mp.all_wait()
    _, p_o2, p_o3 = build(resolution, include_junction=True)
    total_out = p_o2 + p_o3
    il_db = -10 * math.log10(abs(total_out / p_in_ref))
    split = (p_o2 / total_out, p_o3 / total_out)
    print(f"[res={resolution}] P_in_ref={p_in_ref:.6e} P_o2={p_o2:.6e} P_o3={p_o3:.6e} "
          f"transmission={total_out/p_in_ref:.4f} IL={il_db:.4f} dB split={split[0]:.3f}:{split[1]:.3f}")
    return il_db


if __name__ == "__main__":
    import sys
    res = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    run_at(res)
