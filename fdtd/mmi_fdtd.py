"""mmi_fdtd.py - first real FDTD (MEEP) insertion-loss measurement of the
real mmi1x2 combiner geometry used by gcb-pic-core/mmi_power_tree.py.

Deliberately ugly first pass, default/coarse settings, per Orange-Team
doctrine - the goal is a real number, not a polished result.

REAL geometry, extracted directly from gdsfactory this session
(gf.components.mmi1x2(), default params, gf.gpdk PDK active):
  size: 25.5 x 2.5 um
  o1 (single port): x=-10.0, y=0.0,  facing left,  width 0.5 um
  o2:               x=15.5, y=+0.625, facing right, width 0.5 um
  o3:               x=15.5, y=-0.625, facing right, width 0.5 um
  width_taper=1.0, length_taper=10.0, length_mmi=5.5, width_mmi=2.5,
  gap_mmi=0.25 (all real defaults, from the real function signature)

2D effective-index approximation (a real, standard first-pass technique
for SOI photonics, not an invented shortcut): core index = n_eff =
2.684623, the REAL value this program's own femwell mode-solve already
computed for the 0.5x0.22um strip cross-section at 1.31um. Clad index
= 1.44 (SiO2), the same value already used in that same mode-solve.
This is an approximation (ignores vertical mode confinement details a
true 3D simulation would capture) - stated explicitly, not hidden.

Physics being tested, by reciprocity: the real device is used
BACKWARDS (2 inputs -> 1 output, a combiner). A lossless, linear,
reciprocal passive device has identical S-parameters in either
direction, so simulating it FORWARD (1 input -> 2 outputs, the way
gdsfactory's mmi1x2 is named) measures the same insertion loss that
matters for the combiner use.
"""
import meep as mp

um = 1.0  # meep's native length unit; we treat it as micrometers throughout
WAVELENGTH = 1.31
N_CORE = 2.684623   # [M]easured, this program's own femwell mode-solve, real part
N_CLAD = 1.44       # [A]ssumed, same textbook SiO2 value the mode-solve used

WIDTH_WG = 0.5
WIDTH_TAPER = 1.0
LENGTH_TAPER = 10.0
LENGTH_MMI = 5.5
WIDTH_MMI = 2.5
GAP_MMI = 0.25

RESOLUTION = 20  # pixels/um - coarse, first-pass (standard near-IR SOI runs use 20-40)
PML_THICKNESS = 1.0
PAD = 2.0  # extra straight waveguide before/after the component, inside the cell

# --- Geometry, built directly from the real extracted port/size data ---
sx = LENGTH_TAPER + LENGTH_MMI + LENGTH_TAPER + 2 * PAD
sy = WIDTH_MMI + 4 * PAD  # generous y-padding for the radiating field
cell = mp.Vector3(sx, sy, 0)

core = mp.Medium(index=N_CORE)
clad = mp.Medium(index=N_CLAD)

x0 = -sx / 2 + PAD  # left edge of the real component's bounding box, in sim coords

geometry = [
    # input straight section (pad + matches the real o1->taper-start run)
    mp.Block(
        center=mp.Vector3(x0 + (LENGTH_TAPER) / 2 - LENGTH_TAPER / 2 - PAD / 2, 0, 0),
        size=mp.Vector3(PAD, WIDTH_WG, mp.inf),
        material=core,
    ),
    # input taper: WIDTH_WG -> WIDTH_TAPER over LENGTH_TAPER (approximated as
    # a stack of trapezoids via mp.Prism would be more exact; first pass uses
    # a linear-taper approximation built from Block+Wedge is overkill for a
    # deliberately-ugly pass, so this uses a true linear taper via a Prism).
]

# Build the true linear tapers + MMI slab as polygons (Prism), which meep
# supports natively and which matches the real trapezoidal taper shape
# exactly, not a staircase approximation.
def taper_polygon(x_start, width_start, width_end, length, flip=False):
    x_end = x_start + length
    pts = [
        mp.Vector3(x_start, -width_start / 2, 0),
        mp.Vector3(x_start, width_start / 2, 0),
        mp.Vector3(x_end, width_end / 2, 0),
        mp.Vector3(x_end, -width_end / 2, 0),
    ]
    return pts

geometry = []

# input pad (straight WIDTH_WG)
x = x0 - PAD
geometry.append(mp.Block(
    center=mp.Vector3(x + PAD / 2, 0, 0),
    size=mp.Vector3(PAD, WIDTH_WG, mp.inf),
    material=core,
))
x = x0

# input taper (WIDTH_WG -> WIDTH_TAPER)
pts = taper_polygon(x, WIDTH_WG, WIDTH_TAPER, LENGTH_TAPER)
geometry.append(mp.Prism(pts, height=mp.inf, material=core))
x += LENGTH_TAPER

# MMI slab (constant WIDTH_MMI)
geometry.append(mp.Block(
    center=mp.Vector3(x + LENGTH_MMI / 2, 0, 0),
    size=mp.Vector3(LENGTH_MMI, WIDTH_MMI, mp.inf),
    material=core,
))
x += LENGTH_MMI

# two output tapers (WIDTH_TAPER -> WIDTH_WG), centered at +-GAP_MMI/2 offsets
# matching the real port y-centers (+-0.625 = +-(WIDTH_TAPER+GAP_MMI)/2)
y_off = (WIDTH_TAPER + GAP_MMI) / 2
for sign in (+1, -1):
    pts = [
        mp.Vector3(x, sign * y_off - WIDTH_TAPER / 2, 0),
        mp.Vector3(x, sign * y_off + WIDTH_TAPER / 2, 0),
        mp.Vector3(x + LENGTH_TAPER, sign * y_off + WIDTH_WG / 2, 0),
        mp.Vector3(x + LENGTH_TAPER, sign * y_off - WIDTH_WG / 2, 0),
    ]
    geometry.append(mp.Prism(pts, height=mp.inf, material=core))
    # output pad (straight WIDTH_WG)
    geometry.append(mp.Block(
        center=mp.Vector3(x + LENGTH_TAPER + PAD / 2, sign * y_off, 0),
        size=mp.Vector3(PAD, WIDTH_WG, mp.inf),
        material=core,
    ))
x_out = x + LENGTH_TAPER

fcen = 1 / WAVELENGTH
df = 0.2 * fcen

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
    resolution=RESOLUTION,
    boundary_layers=[mp.PML(PML_THICKNESS)],
    geometry=geometry,
    sources=sources,
    default_material=clad,
    dimensions=2,
)

mon_x_in = src_x + 0.5
mon_x_out = x_out - 0.3

flux_in = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(mon_x_in, 0, 0), size=mp.Vector3(0, WIDTH_MMI + 2, 0)))
flux_o2 = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(mon_x_out, y_off, 0), size=mp.Vector3(0, 1.5, 0)))
flux_o3 = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(mon_x_out, -y_off, 0), size=mp.Vector3(0, 1.5, 0)))

sim.run(until_after_sources=mp.stop_when_fields_decayed(
    50, mp.Ez, mp.Vector3(mon_x_out, y_off, 0), 1e-4))

p_in = mp.get_fluxes(flux_in)[0]
p_o2 = mp.get_fluxes(flux_o2)[0]
p_o3 = mp.get_fluxes(flux_o3)[0]

print(f"P_in  = {p_in:.6e}")
print(f"P_o2  = {p_o2:.6e}")
print(f"P_o3  = {p_o3:.6e}")
total_out = p_o2 + p_o3
print(f"P_o2+P_o3 = {total_out:.6e}")
print(f"Transmission (total_out / P_in) = {total_out / p_in:.4f}")
import math
il_db = -10 * math.log10(abs(total_out / p_in))
print(f"Insertion loss (excess, vs ideal 0 dB combine) = {il_db:.4f} dB")
print(f"Split ratio o2:o3 = {p_o2/total_out:.3f} : {p_o3/total_out:.3f}")
