"""Animated life: koi gliding under the pond surface (one rises and breaks
it), a songbird on the bamboo spout, a white dove crossing the pavilion
shot, and the maple leaf that falls in shot 3. Anything that touches the
pond registers a ripple that starts at that exact moment."""

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import cameras, config, layout, materials, props, util, water
from .vegetation import maple_leaf_builder

UP = Vector((0.0, 0.0, 1.0))


def _linear_keys(enabled):
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = 'LINEAR' if enabled else 'BEZIER'


def _seconds(shot, t):
    return config.shot_seconds(shot, t)


# ---------------------------------------------------------------- koi

def koi_builder(length=0.55):
    mb = util.MeshBuilder()
    body, fin, eye = 0, 1, 2
    ts = [0.0, 0.06, 0.16, 0.3, 0.45, 0.62, 0.78, 0.9, 0.97, 1.0]
    widths = [0.012, 0.014, 0.03, 0.052, 0.064, 0.062, 0.052, 0.036, 0.018, 0.0]
    heights = [0.018, 0.02, 0.045, 0.068, 0.078, 0.074, 0.06, 0.042, 0.022, 0.0]
    scale = length / 0.55
    sides = 14
    rings = []
    for t, w, h in zip(ts, widths, heights):
        x = (t - 0.5) * length
        ring = []
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            z = math.sin(a) * h * scale
            if z < 0:
                z *= 0.8
            ring.append(mb.vert((x, math.cos(a) * w * scale, z)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            mb.face((rings[i][k], rings[i + 1][k], rings[i + 1][k + 1], rings[i][k + 1]), None, body)
    mb.face(list(reversed(rings[0][:-1])), None, body)
    tail_x = -0.5 * length
    tail = [(0.0, 0.016), (-0.06, 0.06), (-0.15, 0.11), (-0.12, 0.03), (-0.09, 0.0), (-0.12, -0.03),
            (-0.15, -0.1), (-0.06, -0.055), (0.0, -0.016)]
    tail = [(x * scale, z * scale) for x, z in tail]
    mb.prism(list(reversed(tail)), 0.003, Matrix.Translation((tail_x + 0.01, 0, 0)), fin)
    dorsal = [(-0.12, 0.0), (0.06, 0.0), (0.05, 0.03), (-0.02, 0.045), (-0.13, 0.02)]
    mb.prism([(x * scale, z * scale) for x, z in dorsal], 0.003, Matrix.Translation((0, 0, 0.07 * scale)), fin)
    for s in (-1, 1):
        pec = [(0.0, 0.0), (-0.07, -0.01), (-0.085, -0.035), (-0.03, -0.03)]
        m = Matrix.Translation((0.12 * scale, s * 0.045 * scale, -0.03 * scale)) @ \
            Matrix.Rotation(math.radians(30 * s), 4, 'X') @ Matrix.Rotation(math.radians(20 * s), 4, 'Z')
        mb.prism([(x * scale, z * scale) for x, z in pec], 0.002, m, fin)
        mb.ellipsoid((0.21 * scale, s * 0.03 * scale, 0.02 * scale), (0.008, 0.008, 0.008), None, 4, 8, eye)
    return mb


def swim_group(name, amplitude, wavelength, frequency, phase, length):
    """Geometry nodes that bend the body in a wave travelling head to tail."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new('NodeGroupInput'), n.new('NodeGroupOutput')

    def math_node(op, a, b=None):
        m = n.new('ShaderNodeMath')
        m.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                link(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    pos = n.new('GeometryNodeInputPosition')
    sep = n.new('ShaderNodeSeparateXYZ')
    link(pos.outputs[0], sep.inputs[0])
    x = sep.outputs['X']
    time = n.new('GeometryNodeInputSceneTime').outputs['Seconds']
    weight = math_node('POWER', math_node('MINIMUM', math_node('MAXIMUM',
                       math_node('DIVIDE', math_node('SUBTRACT', length * 0.35, x), length), 0.0), 1.0), 1.4)
    arg = math_node('ADD', math_node('MULTIPLY', x, 2 * math.pi / wavelength),
                    math_node('ADD', math_node('MULTIPLY', time, 2 * math.pi * frequency), phase))
    dy = math_node('MULTIPLY', math_node('MULTIPLY', math_node('SINE', arg), weight), amplitude)
    comb = n.new('ShaderNodeCombineXYZ')
    link(dy, comb.inputs['Y'])
    setp = n.new('GeometryNodeSetPosition')
    link(gin.outputs[0], setp.inputs['Geometry'])
    link(comb.outputs[0], setp.inputs['Offset'])
    link(setp.outputs[0], gout.inputs[0])
    return ng


def animate_along(obj, shot, points, depths, start, end, step=2):
    """Move `obj` (facing +X) along a smooth path between two moments."""
    path = util.catmull_rom(points, samples=16, closed=False)
    seg = np.hypot(*(path[1:] - path[:-1]).T)
    total = seg.sum()
    f0, f1 = config.shot_frame(shot, start), config.shot_frame(shot, end)
    _linear_keys(True)
    for f in range(f0, f1 + 1, step):
        u = (f - f0) / max(f1 - f0, 1)
        eased = u * u * (3 - 2 * u) * 0.25 + u * 0.75
        (x, y), tangent = util.polyline_point(path, eased * total)
        z = float(np.interp(u, np.linspace(0, 1, len(depths)), depths))
        util.keyframe(obj, "location", f, (x, y, z))
        util.keyframe(obj, "rotation_euler", f, (0.0, 0.0, math.atan2(tangent[1], tangent[0])))
    _linear_keys(False)


def koi_school(coll):
    mats = [materials.get(k) for k in ("koi_kohaku", "koi_ogon", "koi_sanke", "koi_showa", "koi_asagi")]
    fin, eye = materials.get("koi_fin"), materials.get("eye")
    fish = [
        # pattern, length, path, depth profile, start, end
        (0, 0.6, [(3.6, -8.7), (2.7, -8.0), (1.8, -7.5), (0.6, -7.2), (-0.6, -6.6)],
         [-0.14, -0.05, -0.02, -0.05, -0.12], 0.0, 6.2),
        (1, 0.5, [(4.4, -7.6), (3.3, -7.0), (2.4, -6.1), (1.4, -5.7)], [-0.12, -0.1, -0.1, -0.12], 0.0, 6.2),
        (2, 0.55, [(0.4, -8.9), (1.6, -8.6), (2.8, -8.8), (3.9, -8.4)], [-0.16, -0.15, -0.15, -0.16], 0.0, 6.2),
        (3, 0.5, [(-1.4, -7.8), (-0.4, -8.4), (0.7, -8.0)], [-0.2, -0.2, -0.2], 0.0, 6.2),
        (4, 0.45, [(5.0, -9.4), (4.0, -9.0), (3.4, -8.1)], [-0.18, -0.16, -0.16], 0.0, 6.2),
    ]
    for i, (pattern, length, points, depths, start, end) in enumerate(fish):
        mb = koi_builder(length)
        obj = mb.to_object(f"Koi {i}", coll, [mats[pattern], fin, eye], smooth=True)
        mod = obj.modifiers.new("Swim", 'NODES')
        mod.node_group = swim_group(f"Swim {i}", 0.022 * length / 0.55, length * 1.15, 0.9 + 0.15 * i, i * 1.7,
                                    length)
        animate_along(obj, 0, points, depths, start, end)
    # The lead koi breaks the surface about two seconds in.
    x, y = 1.9, -7.55
    water.add_ripple(x, y, _seconds(0, 2.05), 0.0032)
    water.add_ripple(x - 0.25, y + 0.1, _seconds(0, 2.45), 0.0018)
    water.add_ripple(x - 0.6, y + 0.2, _seconds(0, 2.9), 0.0012)


# ---------------------------------------------------------------- birds

def songbird(coll):
    perch, pipe_dir = props.SPOUT_PERCH or (Vector((20, 7, 0.8)), Vector((0, -1, 0)))
    spec = cameras.shot_specs()[1]
    cam = Vector(spec["keys"][0][1])
    to_cam = Vector((cam.x - perch.x, cam.y - perch.y, 0)).normalized()
    side = Vector((pipe_dir.x, pipe_dir.y, 0)).normalized()
    forward = (to_cam * 0.55 + side * 0.85).normalized()   # three-quarter view toward the camera

    body_mb = util.MeshBuilder()
    plumage, beak, eye = 0, 1, 2
    tilt = Matrix.Rotation(math.radians(-18), 4, 'X')
    body_mb.ellipsoid((0, 0, 0.042), (0.03, 0.058, 0.032), tilt, 8, 12, plumage)
    body_mb.prism([(-0.012, 0.0), (0.012, 0.0), (0.016, -0.075), (-0.016, -0.075)], 0.006,
                  Matrix.Translation((0, -0.045, 0.035)) @ Matrix.Rotation(math.radians(90), 4, 'Z') @
                  Matrix.Rotation(math.radians(-22), 4, 'Y'), plumage)
    for s in (-1, 1):
        wing = [(0.0, 0.0), (0.05, -0.004), (0.02, -0.03), (-0.045, -0.025)]
        m = Matrix.Translation((s * 0.028, -0.005, 0.055)) @ Matrix.Rotation(math.radians(90), 4, 'Z') @ \
            Matrix.Rotation(math.radians(8 * s), 4, 'Y')
        body_mb.prism(wing, 0.008, m, plumage)
        body_mb.tube([(s * 0.012, 0.0, 0.016), (s * 0.012, 0.004, -0.002)], [0.0025, 0.002], 4, beak, cap_end=False)
    body = body_mb.to_object("Songbird", coll, [materials.get("bird_songbird"), materials.get("beak_dark"),
                                                materials.get("eye")], smooth=True)
    head_mb = util.MeshBuilder()
    head_mb.ellipsoid((0, 0.012, 0.012), (0.021, 0.024, 0.021), None, 8, 12, plumage)
    head_mb.tube([(0, 0.032, 0.01), (0, 0.048, 0.008)], [0.0045, 0.0005], 6, beak, cap_end=False)
    for s in (-1, 1):
        head_mb.ellipsoid((s * 0.016, 0.022, 0.017), (0.0045, 0.0045, 0.0045), None, 4, 8, eye)
    head = head_mb.to_object("Songbird head", coll, [materials.get("bird_songbird"), materials.get("beak_dark"),
                                                     materials.get("eye")], smooth=True)
    head.parent = body
    head.location = (0, 0.042, 0.068)
    body.location = perch
    body.scale = (1.5, 1.5, 1.5)   # a bulbul-sized bird, easier to read on screen
    body.rotation_euler = (0.0, 0.0, math.atan2(-forward.x, forward.y))
    # Quick, bird-like head turns with pauses in between.
    turns = [(0.0, 0), (0.9, 0), (1.05, 38), (2.0, 38), (2.12, -25), (3.3, -25), (3.45, 12), (4.4, 12),
             (4.55, -10), (5.5, -10)]
    for t, deg in turns:
        util.keyframe(head, "rotation_euler", config.shot_frame(1, t), (math.radians(-6), 0.0, math.radians(deg)))
    for t, dz in ((0.0, 0.0), (2.6, 0.0), (2.7, 0.006), (2.8, 0.0)):
        util.keyframe(body, "location", config.shot_frame(1, t), tuple(perch + Vector((0, 0, dz))))
    return body


def dove(coll):
    mb = util.MeshBuilder()
    white, beak, eye = 0, 1, 2
    mb.ellipsoid((0, 0, 0), (0.05, 0.14, 0.055), None, 8, 12, white)
    mb.ellipsoid((0, 0.13, 0.03), (0.032, 0.04, 0.032), None, 8, 12, white)
    mb.tube([(0, 0.165, 0.026), (0, 0.19, 0.02)], [0.006, 0.001], 6, beak, cap_end=False)
    for s in (-1, 1):
        mb.ellipsoid((s * 0.026, 0.145, 0.04), (0.006, 0.006, 0.006), None, 4, 8, eye)
    tail = [(-0.035, 0.0), (0.035, 0.0), (0.06, -0.12), (0.0, -0.13), (-0.06, -0.12)]
    mb.prism(tail, 0.008, Matrix.Translation((0, -0.1, 0.01)) @ Matrix.Rotation(math.radians(90), 4, 'Z') @
             Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Rotation(math.radians(-90), 4, 'Z'), white)
    body = mb.to_object("Dove", coll, [materials.get("bird_dove"), materials.get("beak_pink"),
                                       materials.get("eye")], smooth=True)
    wings = []
    for s in (-1, 1):
        w = util.MeshBuilder()
        outline = [(0.0, 0.05), (0.12, 0.06), (0.24, 0.04), (0.33, 0.0), (0.3, -0.04), (0.25, -0.06),
                   (0.2, -0.05), (0.15, -0.07), (0.08, -0.06), (0.0, -0.05)]
        if s < 0:
            outline = [(-x, z) for x, z in reversed(outline)]
        w.prism(outline, 0.01, Matrix.Rotation(math.radians(90), 4, 'X'), white)
        wing = w.to_object(f"Dove wing {'L' if s < 0 else 'R'}", coll, [materials.get("bird_dove")], smooth=True)
        wing.parent = body
        wing.location = (s * 0.04, 0.03, 0.03)
        wings.append((wing, s))

    # Flight path across the front of the pavilion, its reflection in the water below.
    # Starts and ends outside the frame so it never pops in or out.
    start, end = 0.2, 5.7
    path = [Vector(p) for p in ((-16.0, -3.0, 3.9), (-10.0, -0.8, 4.1), (-4.6, 0.8, 4.4), (1.0, 1.9, 4.8),
                                (6.5, 2.6, 5.3), (12.0, 3.0, 5.8))]
    pts = util.catmull_rom([(p.x, p.y) for p in path], samples=12, closed=False)
    zs = np.interp(np.linspace(0, 1, len(pts)), np.linspace(0, 1, len(path)), [p.z for p in path])
    seg = np.hypot(*(pts[1:] - pts[:-1]).T)
    total = seg.sum()
    f0, f1 = config.shot_frame(3, start), config.shot_frame(3, end)
    _linear_keys(True)
    shot_start, shot_end = config.shot_range(3)
    for f in range(shot_start, shot_end + 1):
        u = min(max((f - f0) / (f1 - f0), 0.0), 1.0)
        (x, y), tangent = util.polyline_point(pts, u * total)
        z = float(np.interp(u * (len(zs) - 1), np.arange(len(zs)), zs))
        t = (f - f0) / config.FPS
        gliding = (t % 1.6) > 1.0
        flap = 0.15 if gliding else math.sin(t * 2 * math.pi * 3.2)
        bob = 0.0 if gliding else -0.03 * math.sin(t * 2 * math.pi * 3.2)
        util.keyframe(body, "location", f, (x, y, z + bob))
        heading = math.atan2(-tangent[0], tangent[1])
        util.keyframe(body, "rotation_euler", f, (math.radians(-6), math.radians(-8), heading))
        for wing, s in wings:
            util.keyframe(wing, "rotation_euler", f, (0.0, -s * math.radians(10 + 42 * flap), 0.0))
    _linear_keys(False)
    return body


# ---------------------------------------------------------------- the falling leaf

def falling_leaf(coll):
    lx, ly = layout.LEAF_LANDING
    mb = maple_leaf_builder(0.12, 77)
    leaf = mb.to_object("Falling Leaf", coll, [materials.get("maple_red")], smooth=True)
    t_start, t_land, t_end = 0.0, 2.35, 5.0
    height = 1.3
    _linear_keys(True)
    f0, f_land, f_end = (config.shot_frame(2, t) for t in (t_start, t_land, t_end))
    for f in range(f0, f_land + 1):
        u = (f - f0) / (f_land - f0)
        t = (f - f0) / config.FPS
        swing = 0.16 * (1 - u) ** 0.7
        x = lx + swing * math.sin(t * 3.4) + 0.06 * (1 - u)
        y = ly + swing * 0.6 * math.cos(t * 2.3) + 0.08 * (1 - u)
        z = 0.004 + height * (1 - u) ** 1.15
        roll = math.radians(32 * math.cos(t * 3.4) * (1 - u) + 4 * u)
        pitch = math.radians(18 * math.sin(t * 2.3) * (1 - u))
        util.keyframe(leaf, "location", f, (x, y, z))
        util.keyframe(leaf, "rotation_euler", f, (pitch, roll, math.radians(40) + t * 0.5))
    landed = Vector(leaf.location)
    yaw0 = leaf.rotation_euler.z
    for f in range(f_land + 1, f_end + 2, 3):
        t = (f - f_land) / config.FPS
        drift = Vector((0.018, 0.012, 0)) * t
        bob = 0.0015 * math.exp(-t * 1.2) * math.sin(t * 9)
        util.keyframe(leaf, "location", f, tuple(landed + drift + Vector((0, 0, bob))))
        util.keyframe(leaf, "rotation_euler", f, (0.0, 0.0, yaw0 + 0.06 * t))
    _linear_keys(False)
    water.add_ripple(landed.x, landed.y, _seconds(2, t_land), 0.0028)
    water.add_ripple(landed.x + 0.01, landed.y, _seconds(2, t_land + 0.55), 0.0012)
    return leaf


# ---------------------------------------------------------------- wind over the water

def wind():
    f = config.shot_frame
    for frame, strength in ((f(0, 0.0), 0.55), (f(0, 6.2), 0.55),
                            (f(1, 0.0), 0.4), (f(1, 5.5), 0.4),
                            (f(2, 0.0), 0.12), (f(2, 5.0), 0.12),
                            (f(3, 0.0), 0.3), (f(3, 3.4), 0.3), (f(3, 5.6), 1.3)):
        water.set_wind(frame, strength)


def build(coll):
    koi_school(util.collection("Koi", coll))
    songbird(coll)
    dove(coll)
    falling_leaf(coll)
    wind()
