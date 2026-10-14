"""Ground mesh: rolling moss-covered ground with the pond basin, island,
stream channel and levelled pavilion yard carved into it."""

import numpy as np
from mathutils import Vector, noise

import bpy

from . import layout, materials, util


def _axis(lo, hi, fine_lo, fine_hi, fine_step, coarse_step):
    """Grid coordinates that are dense between fine_lo and fine_hi."""
    left = np.arange(lo, fine_lo, coarse_step)
    mid = np.arange(fine_lo, fine_hi, fine_step)
    right = np.arange(fine_hi, hi + coarse_step * 0.5, coarse_step)
    return np.concatenate([left, mid, right])


def _noise_field(x, y, scale, octaves=4, seed=0.0):
    out = np.empty(x.shape)
    flat_x, flat_y, flat_o = x.ravel(), y.ravel(), out.ravel()
    for i in range(flat_x.size):
        flat_o[i] = noise.fractal(Vector((flat_x[i] * scale + seed, flat_y[i] * scale - seed, seed * 0.37)),
                                  0.7, 2.0, octaves)
    return out


def natural_ground(x, y):
    """Ground height before the water features are carved."""
    z = 0.2 + 0.22 * _noise_field(x, y, 1 / 9.0, 4, 3.0)
    # Garden mounds.
    for mx, my, h, r in ((-15.5, 9.0, 1.4, 4.5), (11.0, -15.0, 0.9, 4.0), (-17.0, -12.0, 1.0, 5.0),
                         (16.0, -6.0, 0.8, 4.5), (4.0, 15.5, 0.9, 4.0)):
        z += h * np.exp(-((x - mx) ** 2 + (y - my) ** 2) / (r * r))
    hills = 1.0 + 0.35 * _noise_field(x, y, 1 / 14.0, 3, 11.0)
    z += 9.0 * util.np_smoothstep(19.0, 50.0, y) * hills          # wooded hill to the north
    z += 6.0 * util.np_smoothstep(22.0, 48.0, -x) * hills         # west
    z += 3.5 * util.np_smoothstep(16.0, 42.0, -y) * hills         # south
    z += 0.03 * np.clip(x - 9.0, 0.0, None)                       # the stream valley climbs east
    z += 5.0 * util.np_smoothstep(45.0, 72.0, x) * hills
    return z


def height(x, y):
    """Final terrain height. Works on scalars or numpy arrays."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    scalar = x.ndim == 0
    x, y = np.atleast_1d(x), np.atleast_1d(y)
    z = natural_ground(x, y)

    # Levelled yard for the pavilion.
    px, py = layout.PAVILION
    yard = (util.np_smoothstep(7.2, 5.6, np.abs(x - px)) * util.np_smoothstep(5.6, 4.4, np.abs(y - (py + 0.4))))
    z = util.lerp(z, layout.PAVILION_GROUND, yard)

    # Stream channel and its banks.
    ds, arc = util.polyline_distance(x, y, layout.STREAM, closed=False)
    w = layout.stream_half_width(arc)
    level = layout.stream_level(arc)
    bank_top = level + 0.2 + 0.35 * util.np_smoothstep(w, w + 4.0, ds)
    z = np.where(ds < w + 6.0, util.lerp(bank_top, z, util.np_smoothstep(w + 2.0, w + 6.0, ds)), z)
    inside = np.clip(ds / w, 0.0, 1.0)
    bed = level - 0.04 - 0.2 * (1.0 - inside ** 2)
    edge = util.np_smoothstep(w, w + 0.7, ds)
    stream_z = util.lerp(bed, z, edge)
    upstream = arc > 0.3
    z = np.where(upstream & (ds < w + 0.7), stream_z, z)

    # Pond basin.
    d = util.signed_distance(x, y, layout.POND)
    wobble = 0.05 * _noise_field(x, y, 0.6, 2, 5.0)
    bed = -0.12 - 0.62 * util.np_smoothstep(0.0, 3.5, -d) + wobble
    shore = util.lerp(-0.12, z, util.np_smoothstep(0.0, 1.0, d))
    z = np.where(d < 0.0, bed, np.minimum(z, shore))

    # The island.
    ix, iy = layout.ISLAND
    r2 = (x - ix) ** 2 + (y - iy) ** 2
    z = np.maximum(z, 0.62 * np.exp(-r2 / (1.5 ** 2)) - 0.18)
    return float(z[0]) if scalar else z


def build(coll):
    xs = _axis(-60.0, 80.0, -22.0, 44.0, 0.3, 1.6)
    ys = _axis(-50.0, 78.0, -18.0, 32.0, 0.3, 1.6)
    gx, gy = np.meshgrid(xs, ys)
    gz = height(gx, gy)
    nx, ny = len(xs), len(ys)

    verts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], axis=-1).reshape(-1, 4)

    me = bpy.data.meshes.new("Terrain")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4))
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), dtype=bool))
    me.update(calc_edges=True)

    gravel = layout.gravel_mask(gx.ravel(), gy.ravel())
    attr = me.attributes.new("gravel", 'FLOAT', 'POINT')
    attr.data.foreach_set("value", gravel)
    me.materials.append(materials.get("terrain"))

    obj = bpy.data.objects.new("Terrain", me)
    coll.objects.link(obj)
    return obj
