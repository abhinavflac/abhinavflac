"""Stones and garden structures: faceted rocks along every shore, stone
lanterns, stepping stones, and the bamboo spout feeding the stream."""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

from . import layout, materials, terrain, util, water

# Set during build so the songbird can perch on the spout.
SPOUT_PERCH = None


# ---------------------------------------------------------------- rocks

def rock_mesh(name, seed, squash=(1.0, 0.8, 0.6), subdivisions=3):
    """A garden stone: an icosphere cut by a few random planes (giving the
    flat faces of split rock), roughened with noise, flattened underneath."""
    rnd = util.rng(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
    planes = [(util.rand_unit(rnd), rnd.uniform(0.55, 0.85)) for _ in range(rnd.randint(5, 9))]
    offset = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    sx, sy, sz = (s * rnd.uniform(0.85, 1.15) for s in squash)
    for v in bm.verts:
        p = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
        for n, d in planes:
            k = p.dot(n) - d * max(sx, sy, sz) * 0.8
            if k > 0:
                p -= n * k * 0.85
        bumpy = noise.fractal(p * 1.4 + offset, 0.6, 2.0, 4) * 0.11 + noise.noise(p * 5.0 + offset) * 0.025
        p += p.normalized() * bumpy
        floor = -0.45 * sz
        if p.z < floor:
            p.z = floor + (p.z - floor) * 0.15
        v.co = p
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.materials.append(materials.get("rock"))
    me.update()
    return me


class RockSet:
    def __init__(self, count=10):
        self.meshes = []
        for i in range(count):
            squash = (1.0, util.lerp(0.65, 0.95, (i * 0.37) % 1), util.lerp(0.45, 0.85, (i * 0.61) % 1))
            self.meshes.append(rock_mesh(f"Rock {i}", 100 + i, squash, 3))
        self.flat = [rock_mesh(f"Flat Stone {i}", 300 + i, (1.0, 0.85, 0.22), 3) for i in range(4)]
        self.count = 0

    def place(self, coll, x, y, size, rnd, sink=0.3, flat=False, z=None, tilt=8.0):
        mesh = rnd.choice(self.flat if flat else self.meshes)
        obj = bpy.data.objects.new(f"{mesh.name}.{self.count:03d}", mesh)
        self.count += 1
        ground = terrain.height(x, y) if z is None else z
        obj.location = (x, y, ground - sink * size * (0.45 if flat else 0.6))
        obj.rotation_euler = (math.radians(rnd.uniform(-tilt, tilt)), math.radians(rnd.uniform(-tilt, tilt)),
                              rnd.uniform(0, 2 * math.pi))
        obj.scale = (size, size, size)
        coll.objects.link(obj)
        return obj


def shoreline_rocks(rocks, coll, quality, rnd):
    poly = layout.POND
    seg = np.hypot(*(np.roll(poly, -1, axis=0) - poly).T)
    total = seg.sum()
    mouth = np.array(layout.STREAM_CONTROL[0])
    arc = 0.0
    while arc < total:
        i = int(np.searchsorted(np.cumsum(seg), arc))
        i = min(i, len(poly) - 1)
        a, b = poly[i], poly[(i + 1) % len(poly)]
        t = 1.0 - (np.cumsum(seg)[i] - arc) / seg[i]
        p = a + (b - a) * t
        tangent = (b - a) / seg[i]
        outward = np.array([tangent[1], -tangent[0]])
        if np.hypot(*(p - mouth)) > 2.0:
            size = rnd.uniform(0.3, 0.65) if rnd.random() < 0.8 else rnd.uniform(0.8, 1.25)
            q = p + outward * rnd.uniform(-0.25, 0.35)
            rocks.place(coll, q[0], q[1], size, rnd, sink=0.45)
            if rnd.random() < 0.35:   # a smaller companion stone
                q2 = q + tangent * rnd.uniform(-0.5, 0.5) + outward * rnd.uniform(-0.4, 0.2)
                rocks.place(coll, q2[0], q2[1], size * rnd.uniform(0.35, 0.6), rnd, sink=0.4)
        arc += rnd.uniform(0.9, 1.5) / max(quality["density"], 0.6) ** 0.3


def stream_rocks(rocks, coll, rnd):
    arc = 0.6
    while arc < layout.STREAM_LENGTH - 1.0:
        (x, y), tangent = util.polyline_point(layout.STREAM, arc)
        normal = np.array([-tangent[1], tangent[0]])
        w = float(layout.stream_half_width(arc))
        for side in (-1, 1):
            if rnd.random() < 0.8:
                q = np.array([x, y]) + normal * side * (w + rnd.uniform(-0.15, 0.25))
                rocks.place(coll, q[0], q[1], rnd.uniform(0.22, 0.5), rnd, sink=0.4)
        arc += rnd.uniform(0.6, 1.0)
    # A low step of stones the stream tumbles over.
    (x, y), tangent = util.polyline_point(layout.STREAM, layout.CASCADE_ARC)
    normal = np.array([-tangent[1], tangent[0]])
    w = float(layout.stream_half_width(layout.CASCADE_ARC))
    level = float(layout.stream_level(layout.CASCADE_ARC - 0.3))
    for k in np.linspace(-1.1, 1.1, 6):
        q = np.array([x, y]) + normal * k * w - tangent * 0.15
        rocks.place(coll, q[0], q[1], rnd.uniform(0.28, 0.38), rnd, sink=0.1, z=level, tilt=4.0)


def feature_rocks(rocks, coll, rnd):
    ix, iy = layout.ISLAND
    for dx, dy, s in ((-0.6, -0.4, 0.9), (0.7, -0.2, 0.7), (0.1, 0.8, 0.6), (-1.2, 0.5, 0.45)):
        rocks.place(coll, ix + dx, iy + dy, s, rnd, sink=0.35)
    # Standing stones in the water in front of the pavilion, and on the banks.
    for x, y, s in ((-7.8, 3.2, 0.75), (-6.6, 2.6, 0.5), (-1.6, 3.4, 0.6), (2.6, 2.9, 0.55),
                    (8.6, -11.6, 1.3), (-12.4, -7.6, 0.9), (13.4, 0.2, 1.0), (-13.6, 3.6, 0.85)):
        obj = rocks.place(coll, x, y, s, rnd, sink=0.25)
        obj.scale.z *= 1.35
    # Stepping stones along the gravel path.
    path = layout.GRAVEL_PATH
    lengths = np.hypot(*(path[1:] - path[:-1]).T)
    for d in np.arange(0.3, lengths.sum(), 0.72):
        (x, y), _ = util.polyline_point(path, d)
        rocks.place(coll, x + rnd.uniform(-0.12, 0.12), y + rnd.uniform(-0.12, 0.12), rnd.uniform(0.28, 0.36),
                    rnd, sink=0.15, flat=True, tilt=2.0)


# ---------------------------------------------------------------- lanterns

def _ngon_prism(mb, sides, r0, r1, z0, z1, mat, rot=0.0):
    ring0, ring1 = [], []
    for k in range(sides):
        a = rot + 2 * math.pi * k / sides
        ring0.append(mb.vert((r0 * math.cos(a), r0 * math.sin(a), z0)))
        ring1.append(mb.vert((r1 * math.cos(a), r1 * math.sin(a), z1)))
    for k in range(sides):
        j = (k + 1) % sides
        mb.face((ring0[k], ring0[j], ring1[j], ring1[k]),
                [(k * 0.3, z0), ((k + 1) * 0.3, z0), ((k + 1) * 0.3, z1), (k * 0.3, z1)], mat)
    mb.face(list(reversed(ring0)), None, mat)
    mb.face(ring1, None, mat)


def _lantern_roof(mb, sides, radius, z0, height, upturn, mat, top_radius=0.06):
    rings = 8
    grid = []
    for r in range(rings + 1):
        t = r / rings
        row = []
        for k in range(sides * 4 + 1):
            a = 2 * math.pi * k / (sides * 4)
            corner = abs(math.cos(sides * a / 2)) ** 8
            rad = util.lerp(radius, top_radius, t) * (1.0 + 0.08 * corner * (1 - t))
            z = z0 + height * t ** 1.6 + upturn * corner * (1 - t) ** 3
            row.append(mb.vert((rad * math.cos(a), rad * math.sin(a), z)))
        grid.append(row)
    for r in range(rings):
        for k in range(sides * 4):
            mb.face((grid[r][k], grid[r][k + 1], grid[r + 1][k + 1], grid[r + 1][k]), None, mat)
    under = []
    for k in range(sides * 4):
        a = 2 * math.pi * k / (sides * 4)
        under.append(mb.vert((radius * 0.9 * math.cos(a), radius * 0.9 * math.sin(a), z0 + 0.02)))
    edge = grid[0][:-1]
    for k in range(sides * 4):
        j = (k + 1) % (sides * 4)
        mb.face((edge[j], edge[k], under[k], under[j]), None, mat)
    mb.face(list(reversed(under)), None, mat)


def kasuga_lantern(coll, name, x, y, scale=1.0, rot=0.0):
    mb = util.MeshBuilder()
    stone, dark = 0, 1
    _ngon_prism(mb, 6, 0.34, 0.3, 0.0, 0.14, stone)
    _ngon_prism(mb, 6, 0.26, 0.16, 0.14, 0.22, stone)
    mb.tube([(0, 0, 0.2), (0, 0, 0.62), (0, 0, 1.0)], [0.09, 0.085, 0.08], 14, stone, cap_end=False)
    mb.tube([(0, 0, 0.58), (0, 0, 0.66)], [0.105, 0.105], 14, stone, cap_end=False)
    _ngon_prism(mb, 6, 0.16, 0.3, 0.98, 1.1, stone)
    _ngon_prism(mb, 6, 0.3, 0.29, 1.1, 1.16, stone)
    _ngon_prism(mb, 6, 0.19, 0.19, 1.16, 1.46, stone)
    for k in (0, 3):
        a = math.pi / 6 + k * math.pi / 3
        c, s = math.cos(a), math.sin(a)
        m = Matrix.Translation((0.165 * c, 0.165 * s, 1.31)) @ Matrix.Rotation(a + math.pi / 2, 4, 'Z')
        mb.box((-0.08, -0.02, -0.1), (0.08, 0.02, 0.1), dark, m)
    _lantern_roof(mb, 6, 0.47, 1.46, 0.24, 0.07, stone)
    mb.ellipsoid((0, 0, 1.76), (0.075, 0.075, 0.09), None, 8, 12, stone)
    mb.tube([(0, 0, 1.72), (0, 0, 1.75)], [0.08, 0.06], 12, stone, cap_end=False)
    obj = mb.to_object(name, coll, [materials.get("granite"), materials.get("dark_inside")])
    obj.location = (x, y, terrain.height(x, y) - 0.05)
    obj.rotation_euler.z = rot
    obj.scale = (scale, scale, scale)
    return obj


def yukimi_lantern(coll, name, x, y, z=None, scale=1.0, rot=0.0):
    mb = util.MeshBuilder()
    stone = 0
    for k in range(3):
        a = rot + 2 * math.pi * k / 3
        c, s = math.cos(a), math.sin(a)
        pts = [(0.42 * c, 0.42 * s, 0.0), (0.36 * c, 0.36 * s, 0.25), (0.26 * c, 0.26 * s, 0.42),
               (0.18 * c, 0.18 * s, 0.5)]
        mb.tube(pts, [0.06, 0.055, 0.05, 0.05], 10, stone)
    _ngon_prism(mb, 6, 0.28, 0.3, 0.48, 0.56, stone)
    _ngon_prism(mb, 6, 0.2, 0.2, 0.56, 0.82, stone)
    for k in (0, 3):
        a = math.pi / 6 + k * math.pi / 3
        m = Matrix.Translation((0.175 * math.cos(a), 0.175 * math.sin(a), 0.69)) @ Matrix.Rotation(a + math.pi / 2, 4, 'Z')
        mb.box((-0.08, -0.02, -0.09), (0.08, 0.02, 0.09), 1, m)
    _lantern_roof(mb, 6, 0.62, 0.82, 0.18, 0.05, stone, top_radius=0.08)
    mb.ellipsoid((0, 0, 1.06), (0.07, 0.07, 0.08), None, 8, 12, stone)
    obj = mb.to_object(name, coll, [materials.get("granite"), materials.get("dark_inside")])
    obj.location = (x, y, (terrain.height(x, y) if z is None else z) - 0.03)
    obj.scale = (scale, scale, scale)
    return obj


# ---------------------------------------------------------------- spout

def bamboo_spout(coll):
    """A bamboo pipe on crossed supports pouring into the stream."""
    global SPOUT_PERCH
    tip, post, level, normal = layout.spout_layout()
    ground = terrain.height(post[0], post[1])
    tip3 = Vector((tip[0], tip[1], level + 0.42))
    post3 = Vector((post[0], post[1], ground))
    back = Vector((post[0] + normal[0] * 1.6, post[1] + normal[1] * 1.6, ground + 0.35))
    support = post3 + Vector((0, 0, 0.62))
    mb = util.MeshBuilder()
    pipe = [back, support, tip3]
    pts = [back.lerp(support, t) for t in np.linspace(0, 1, 6)] + [support.lerp(tip3, t) for t in np.linspace(0, 1, 6)[1:]]
    mb.tube(pts, [0.038] * len(pts), 12, 0, cap_end=False, v_scale=1 / 0.38)
    side = Vector((-normal[1], normal[0], 0.0))
    for s in (-1, 1):   # crossed support poles
        foot = post3 + side * 0.22 * s - Vector((0, 0, 0.1))
        head = post3 + Vector((0, 0, 0.62)) - side * 0.12 * s + Vector((0, 0, 0.12))
        mb.tube([foot, foot.lerp(head, 0.5), head], [0.026, 0.025, 0.024], 10, 0, v_scale=1 / 0.3)
    mb.tube([post3 - Vector((0, 0, 0.1)), post3 + Vector((0, 0, 0.52))], [0.03, 0.028], 10, 0, v_scale=1 / 0.3)
    obj = mb.to_object("Bamboo Spout", coll, [materials.get("bamboo")], smooth=True)
    direction = (tip3 - support).normalized()
    mouth = tip3 + direction * 0.02 - Vector((0, 0, 0.02))
    landing = Vector((mouth.x, mouth.y, level)) + Vector((direction.x, direction.y, 0)).normalized() * 0.16
    water.falling_water(coll, tuple(mouth), tuple(landing), mouth.z - level)
    SPOUT_PERCH = (support + (tip3 - support) * 0.35 + Vector((0, 0, 0.04)), direction)
    return obj


# ---------------------------------------------------------------- build

def build(coll, quality):
    rnd = util.rng(7)
    rocks = RockSet()
    shoreline_rocks(rocks, util.collection("Rocks", coll), quality, rnd)
    stream_rocks(rocks, util.collection("Rocks", coll), rnd)
    feature_rocks(rocks, util.collection("Rocks", coll), rnd)
    kasuga_lantern(coll, "Lantern East", 3.4, 7.2, 1.0, 0.3)
    kasuga_lantern(coll, "Lantern Stream", 17.2, 2.6, 0.85, 0.8)
    yukimi_lantern(coll, "Snow Lantern", 10.6, -1.1, z=0.18, scale=1.0, rot=0.4)
    rocks.place(util.collection("Rocks", coll), 10.6, -1.1, 0.75, rnd, sink=0.2, flat=True, z=0.05)
    bamboo_spout(coll)
