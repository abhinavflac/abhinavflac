"""Water surfaces: the pond (with ripple rings that start exactly when
something touches it), the stream, and the spout's falling water."""

import math

import numpy as np

import bpy

from . import config, layout, materials as M, util
from .materials import srgb

# Ripple sources registered by animated things that touch the pond:
# (x, y, start time in seconds, amplitude in metres).
RIPPLES = []

# Overall wind ripple strength over time: (frame, strength).
WIND_KEYS = []


def add_ripple(x, y, start_seconds, amplitude=0.0025):
    RIPPLES.append((x, y, start_seconds, amplitude))


def set_wind(frame, strength):
    WIND_KEYS.append((frame, strength))


# ---------------------------------------------------------------- shading

def _time_socket(nt):
    value = M.node(nt, 'ShaderNodeValue')
    value.label = "Time (s)"
    util.time_driver(value.outputs[0])
    return value.outputs[0]


def _ring_packet(nt, pos, time, x, y, t0, amp):
    """Height of one expanding ripple packet: a few rings travelling outward
    from (x, y), starting at t0 and fading as they spread."""
    tau = M.math(nt, 'SUBTRACT', time, t0)
    active = M.math(nt, 'GREATER_THAN', tau, 0.0)
    offset = M.vmath(nt, 'SUBTRACT', pos, (x, y, 0.0))
    flat = M.vmath(nt, 'MULTIPLY', offset, (1.0, 1.0, 0.0))
    r = M.vmath(nt, 'LENGTH', flat)
    front = M.math(nt, 'MULTIPLY', tau, 0.24)
    d = M.math(nt, 'SUBTRACT', r, front)
    width = M.math(nt, 'MULTIPLY_ADD', tau, 0.07, 0.03)
    env = M.math(nt, 'EXPONENT', M.math(nt, 'MULTIPLY', M.math(nt, 'POWER', M.math(nt, 'DIVIDE', d, width), 2.0), -1.0))
    wavelength = M.math(nt, 'MULTIPLY_ADD', tau, 0.012, 0.035)
    osc = M.math(nt, 'SINE', M.math(nt, 'DIVIDE', M.math(nt, 'MULTIPLY', d, 2 * math.pi), wavelength))
    decay = M.math(nt, 'EXPONENT', M.math(nt, 'MULTIPLY', tau, -1.0 / 1.8))
    spread = M.math(nt, 'DIVIDE', 1.0, M.math(nt, 'MULTIPLY_ADD', r, 5.0, 1.0))
    h = M.math(nt, 'MULTIPLY', env, osc)
    h = M.math(nt, 'MULTIPLY', h, decay)
    h = M.math(nt, 'MULTIPLY', h, spread)
    h = M.math(nt, 'MULTIPLY', h, active)
    return M.math(nt, 'MULTIPLY', h, amp)


def _wind_height(nt, pos, time, strength):
    big = M.noise(nt, M.vmath(nt, 'MULTIPLY', pos, (1.0, 1.6, 0.0)), 2.2, detail=3.0, dims='4D',
                  w=M.math(nt, 'MULTIPLY', time, 0.25))
    small = M.noise(nt, M.vmath(nt, 'MULTIPLY', pos, (1.0, 1.3, 0.0)), 9.0, detail=2.0, dims='4D',
                    w=M.math(nt, 'MULTIPLY', time, 0.7))
    h = M.math(nt, 'ADD', M.math(nt, 'MULTIPLY', M.math(nt, 'SUBTRACT', big.outputs[0], 0.5), 0.004),
               M.math(nt, 'MULTIPLY', M.math(nt, 'SUBTRACT', small.outputs[0], 0.5), 0.0015))
    return M.math(nt, 'MULTIPLY', h, strength)


def _water_bsdf(nt, normal, opacity_near, opacity_far, tint):
    facing = M.node(nt, 'ShaderNodeLayerWeight', inputs={'Blend': 0.5, 'Normal': normal}).outputs['Facing']
    alpha = M.maprange(nt, facing, 0.0, 1.0, opacity_near, opacity_far)
    return M.principled(nt, tint, 0.035, normal, IOR=1.333, Alpha=alpha, Specular_IOR_Level=0.5)


def _water_settings(mat):
    mat.surface_render_method = 'DITHERED'
    mat.use_transparency_overlap = False


def _wind_socket(nt, control):
    value = M.node(nt, 'ShaderNodeValue')
    value.label = "Wind strength"
    fc = value.outputs[0].driver_add("default_value")
    fc.driver.type = 'AVERAGE'
    var = fc.driver.variables.new()
    var.name = "s"
    var.type = 'SINGLE_PROP'
    var.targets[0].id = control
    var.targets[0].data_path = '["strength"]'
    return value.outputs[0]


def pond_material(control):
    mat, nt, out = M.new_material("Pond Water")
    pos = M.geometry(nt).outputs['Position']
    time = _time_socket(nt)
    height = _wind_height(nt, pos, time, _wind_socket(nt, control))
    for x, y, t0, amp in RIPPLES:
        height = M.math(nt, 'ADD', height, _ring_packet(nt, pos, time, x, y, t0, amp))
    normal = M.bump(nt, height, 1.0, 1.0)
    M.finish(nt, out, _water_bsdf(nt, normal, 0.62, 1.0, srgb('#08130f')))
    _water_settings(mat)
    M.set_display_color(mat, '#3f6670')
    return mat


def stream_material():
    mat, nt, out = M.new_material("Stream Water")
    uv = M.coords(nt).outputs['UV']
    time = _time_socket(nt)
    u, v, _ = M.separate(nt, uv)
    flow_v = M.math(nt, 'SUBTRACT', v, M.math(nt, 'MULTIPLY', time, 0.55))
    vec = M.combine(nt, M.math(nt, 'MULTIPLY', u, 2.5), M.math(nt, 'MULTIPLY', flow_v, 1.0), 0.0)
    ripples = M.noise(nt, vec, 6.0, detail=4.0, dims='3D')
    fine = M.noise(nt, M.combine(nt, M.math(nt, 'MULTIPLY', u, 6.0), M.math(nt, 'MULTIPLY', flow_v, 3.0), 0.0),
                   10.0, detail=2.0)
    foam_mask = M.attribute(nt, "foam")
    height = M.math(nt, 'ADD', M.math(nt, 'MULTIPLY', ripples.outputs[0], 0.006),
                    M.math(nt, 'MULTIPLY', fine.outputs[0], 0.002))
    height = M.math(nt, 'MULTIPLY', height, M.math(nt, 'ADD', 1.0, M.math(nt, 'MULTIPLY', foam_mask, 2.0)))
    normal = M.bump(nt, height, 1.0, 1.0)
    water = _water_bsdf(nt, normal, 0.3, 0.95, srgb('#0d1a12'))
    foam_noise = M.noise(nt, M.combine(nt, M.math(nt, 'MULTIPLY', u, 4.0), M.math(nt, 'MULTIPLY', flow_v, 1.5), 0.0),
                         9.0, detail=5.0)
    foam_amount = M.math(nt, 'MULTIPLY', foam_mask, M.maprange(nt, foam_noise.outputs[0], 0.45, 0.65))
    foam = M.principled(nt, srgb('#e8eeea'), 0.6, normal, Alpha=0.9)
    M.finish(nt, out, M.mix_shader(nt, foam_amount, water, foam))
    _water_settings(mat)
    M.set_display_color(mat, '#4f7680')
    return mat


def falling_water_material():
    mat, nt, out = M.new_material("Falling Water")
    uv = M.coords(nt).outputs['UV']
    time = _time_socket(nt)
    u, v, _ = M.separate(nt, uv)
    vec = M.combine(nt, M.math(nt, 'MULTIPLY', u, 20.0), M.math(nt, 'SUBTRACT', M.math(nt, 'MULTIPLY', v, 8.0),
                                                             M.math(nt, 'MULTIPLY', time, 14.0)), 0.0)
    streaks = M.noise(nt, vec, 1.5, detail=4.0)
    alpha = M.maprange(nt, streaks.outputs[0], 0.3, 0.7, 0.35, 0.85)
    color = M.mix(nt, streaks.outputs[0], srgb('#a9bab3'), srgb('#f2f7f5'))
    bsdf = M.principled(nt, color, 0.05, M.bump(nt, streaks.outputs[0], 0.3, 0.01), IOR=1.333, Alpha=alpha)
    M.finish(nt, out, bsdf)
    _water_settings(mat)
    M.set_display_color(mat, '#e6eeee')
    return mat


# ---------------------------------------------------------------- geometry

def _plane(name, coll, x0, y0, x1, y1, z, material):
    mb = util.MeshBuilder()
    ids = [mb.vert((x0, y0, z)), mb.vert((x1, y0, z)), mb.vert((x1, y1, z)), mb.vert((x0, y1, z))]
    mb.face(ids, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return mb.to_object(name, coll, [material])


def _stream_mesh(coll, material):
    mb = util.MeshBuilder()
    step = 0.2
    arcs = np.arange(-1.5, layout.STREAM_LENGTH - 0.5, step)
    across = np.linspace(-1.0, 1.0, 7)
    rows = []
    foam = []
    tip, _, _, _ = layout.spout_layout()
    for arc in arcs:
        (x, y), tangent = util.polyline_point(layout.STREAM, max(arc, 0.0))
        if arc < 0.0:
            x, y = np.array([x, y]) + tangent * arc
        normal = np.array([-tangent[1], tangent[0]])
        w = float(layout.stream_half_width(max(arc, 0.0))) + 0.25
        level = float(layout.stream_level(max(arc, 0.0)))
        row = []
        for a in across:
            p = np.array([x, y]) + normal * a * w
            row.append(mb.vert((p[0], p[1], level)))
            cascade = math.exp(-((arc - layout.CASCADE_ARC - 0.35) / 0.6) ** 2)
            dist_spout = math.hypot(p[0] - tip[0], p[1] - tip[1])
            splash = math.exp(-(dist_spout / 0.35) ** 2)
            foam.append(min(1.0, cascade * 0.9 + splash))
        rows.append((row, arc, w))
    for i in range(len(rows) - 1):
        (r0, a0, w0), (r1, a1, w1) = rows[i], rows[i + 1]
        for k in range(len(across) - 1):
            mb.face((r0[k], r0[k + 1], r1[k + 1], r1[k]),
                    [(across[k] * w0, a0), (across[k + 1] * w0, a0), (across[k + 1] * w1, a1), (across[k] * w1, a1)])
    obj = mb.to_object("Stream Water", coll, [material], smooth=True)
    attr = obj.data.attributes.new("foam", 'FLOAT', 'POINT')
    attr.data.foreach_set("value", foam)
    return obj


def falling_water(coll, start, end, drop):
    """A falling stream of water from `start`, landing at `end`, shaped like a
    gentle arc."""
    start, end = np.array(start, dtype=float), np.array(end, dtype=float)
    points, radii = [], []
    count = 18
    for i in range(count + 1):
        t = i / count
        p = start + (end - start) * t
        p[2] = start[2] + (end[2] - start[2]) * t * t   # parabola: slow start, fast fall
        points.append(tuple(p))
        radii.append(0.011 + 0.008 * t)
    mb = util.MeshBuilder()
    mb.tube(points, radii, 10, cap_end=False, u_scale=0.25)
    obj = mb.to_object("Spout Water", coll, [falling_water_material()], smooth=True)
    obj.visible_shadow = False
    return obj


def build(coll):
    wind = bpy.data.objects.new("Wind Control", None)
    coll.objects.link(wind)
    wind["strength"] = 0.5
    for frame, strength in sorted(WIND_KEYS) or [(1, 0.5)]:
        wind["strength"] = strength
        wind.keyframe_insert(data_path='["strength"]', frame=frame)

    mat = pond_material(wind)

    xs, ys = layout.POND[:, 0], layout.POND[:, 1]
    pond = _plane("Pond Water", coll, xs.min() - 1.5, ys.min() - 1.5, xs.max() + 1.5, ys.max() + 1.5,
                  config.WATER_LEVEL, mat)
    pond.visible_shadow = False

    stream = _stream_mesh(coll, stream_material())
    stream.visible_shadow = False
    return pond, stream
