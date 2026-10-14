"""Helpers shared by the scene builders: collections, mesh building, noise,
2D outline geometry and keyframing."""

import math
import random
import zlib

import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

from . import config


# ---------------------------------------------------------------- collections

def collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def source_collection(name):
    """A collection excluded from the view layer. Its objects are only used
    as sources for instancing."""
    root = collection("_sources")
    coll = collection(name, root)
    for layer in bpy.context.view_layer.layer_collection.children:
        if layer.collection == root:
            layer.exclude = True
    return coll


def link(obj, coll):
    coll.objects.link(obj)
    return obj


# ---------------------------------------------------------------- mesh building

class MeshBuilder:
    """Accumulates vertices, faces, per-corner UVs and material indices, then
    turns them into a single mesh object."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.uvs = []
        self.mats = []

    def vert(self, co):
        self.verts.append((co[0], co[1], co[2]))
        return len(self.verts) - 1

    def face(self, idx, uvs=None, mat=0):
        self.faces.append(tuple(idx))
        self.uvs.append(list(uvs) if uvs is not None else [(0.0, 0.0)] * len(idx))
        self.mats.append(mat)

    def extend(self, other, matrix=None):
        base = len(self.verts)
        for co in other.verts:
            v = Vector(co)
            if matrix is not None:
                v = matrix @ v
            self.verts.append((v.x, v.y, v.z))
        for f, uv, m in zip(other.faces, other.uvs, other.mats):
            self.faces.append(tuple(i + base for i in f))
            self.uvs.append(list(uv))
            self.mats.append(m)

    def box(self, lo, hi, mat=0, matrix=None):
        """Axis-aligned box between corners `lo` and `hi` (in the frame given
        by `matrix`). UVs are in metres, with U along the box's longest side so
        wood grain follows the beam."""
        lo, hi = Vector(lo), Vector(hi)
        size = hi - lo
        longest = max(range(3), key=lambda a: size[a])
        corners = [Vector((x, y, z)) for z in (lo.z, hi.z) for y in (lo.y, hi.y) for x in (lo.x, hi.x)]
        quads = [  # (corner indices, normal axis)
            ((0, 2, 3, 1), 2), ((4, 5, 7, 6), 2),
            ((0, 1, 5, 4), 1), ((2, 6, 7, 3), 1),
            ((0, 4, 6, 2), 0), ((1, 3, 7, 5), 0),
        ]
        for idx, axis in quads:
            others = [a for a in range(3) if a != axis]
            if longest in others:
                u_axis = longest
                v_axis = others[0] if others[1] == longest else others[1]
            else:
                u_axis, v_axis = others
            ids, uvs = [], []
            for i in idx:
                c = corners[i]
                world = matrix @ c if matrix is not None else c
                ids.append(self.vert(world))
                uvs.append((c[u_axis], c[v_axis]))
            self.face(ids, uvs, mat)

    def beam(self, p0, p1, width, height, mat=0, up=(0.0, 0.0, 1.0)):
        """A rectangular beam from p0 to p1 with the given cross-section."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        x = d.normalized()
        upv = Vector(up)
        if abs(x.dot(upv)) > 0.99:
            upv = Vector((0.0, 1.0, 0.0))
        y = upv.cross(x).normalized()
        z = x.cross(y)
        m = Matrix.Translation(p0) @ Matrix((x, y, z)).transposed().to_4x4()
        self.box((0.0, -width / 2, -height / 2), (d.length, width / 2, height / 2), mat, m)

    def ellipsoid(self, center, radii, matrix=None, rings=8, segments=14, mat=0):
        m = Matrix.Translation(Vector(center)) @ (matrix if matrix is not None else Matrix())
        rows = []
        for i in range(rings + 1):
            phi = math.pi * i / rings
            row = []
            for j in range(segments + 1):
                theta = 2 * math.pi * j / segments
                p = Vector((math.sin(phi) * math.cos(theta) * radii[0],
                            math.sin(phi) * math.sin(theta) * radii[1],
                            math.cos(phi) * radii[2]))
                row.append(self.vert(m @ p))
            rows.append(row)
        for i in range(rings):
            for j in range(segments):
                uv = [(j / segments, i / rings), (j / segments, (i + 1) / rings),
                      ((j + 1) / segments, (i + 1) / rings), ((j + 1) / segments, i / rings)]
                self.face((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]), uv, mat)

    def prism(self, outline, thickness, matrix, mat=0):
        """Extrude a 2D outline drawn in the local XZ plane by `thickness`
        along local Y. The outline should run counter-clockwise."""
        n = len(outline)
        front, back = [], []
        for x, z in outline:
            front.append(self.vert(matrix @ Vector((x, -thickness / 2, z))))
            back.append(self.vert(matrix @ Vector((x, thickness / 2, z))))
        uvs = [(x, z) for x, z in outline]
        self.face(front, uvs, mat)
        self.face(list(reversed(back)), list(reversed(uvs)), mat)
        for i in range(n):
            j = (i + 1) % n
            self.face((front[i], back[i], back[j], front[j]),
                      [(0, 0), (thickness, 0), (thickness, 0.05), (0, 0.05)], mat)

    def tube(self, points, radii, sides, mat=0, cap_end=True, u_scale=None, v_offset=0.0, v_scale=1.0):
        """Sweep a circle along `points` using parallel-transport frames.
        UV: U around the tube, V along it (metres times `v_scale`)."""
        n = len(points)
        if n < 2:
            return
        pts = [Vector(p) for p in points]
        tangents = []
        for i in range(n):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, n - 1)]
            tangents.append((b - a).normalized())
        t0 = tangents[0]
        ref = Vector((0, 0, 1)) if abs(t0.z) < 0.95 else Vector((1, 0, 0))
        normal = t0.cross(ref).normalized()
        circumference = u_scale if u_scale is not None else 2 * math.pi * radii[0]
        rings = []
        length = v_offset
        prev = t0
        for i in range(n):
            t = tangents[i]
            if i > 0:
                length += (pts[i] - pts[i - 1]).length
                axis = prev.cross(t)
                if axis.length > 1e-7:
                    normal = Matrix.Rotation(prev.angle(t), 3, axis.normalized()) @ normal
                prev = t
            binormal = t.cross(normal)
            ring = []
            for k in range(sides + 1):
                ang = 2 * math.pi * k / sides
                co = pts[i] + (normal * math.cos(ang) + binormal * math.sin(ang)) * radii[i]
                ring.append(self.vert(co))
            rings.append((ring, length))
        for i in range(n - 1):
            (r0, l0), (r1, l1) = rings[i], rings[i + 1]
            l0, l1 = l0 * v_scale, l1 * v_scale
            for k in range(sides):
                u0 = circumference * k / sides
                u1 = circumference * (k + 1) / sides
                self.face((r0[k], r0[k + 1], r1[k + 1], r1[k]),
                          [(u0, l0), (u1, l0), (u1, l1), (u0, l1)], mat)
        if cap_end:
            ring, l_end = rings[-1]
            tip = self.vert(pts[-1] + tangents[-1] * radii[-1] * 0.6)
            for k in range(sides):
                self.face((ring[k], ring[k + 1], tip),
                          [(0, l_end), (0.05, l_end), (0.025, l_end + 0.03)], mat)

    def to_object(self, name, coll, materials=(), smooth=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        uv_layer = me.uv_layers.new(name="UVMap")
        flat = [c for face in self.uvs for uv in face for c in uv]
        uv_layer.data.foreach_set("uv", flat)
        me.polygons.foreach_set("material_index", self.mats)
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(self.faces))
        for m in materials:
            me.materials.append(m)
        me.update()
        obj = bpy.data.objects.new(name, me)
        coll.objects.link(obj)
        return obj


def points_object(name, coll, positions, attributes=None):
    """A vertex-only mesh used as scatter points. `attributes` maps a name to
    (type, values) with type FLOAT, INT or FLOAT_VECTOR."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in positions], [], [])
    for attr_name, (kind, values) in (attributes or {}).items():
        attr = me.attributes.new(attr_name, kind, 'POINT')
        if kind == 'FLOAT_VECTOR':
            attr.data.foreach_set("vector", [c for v in values for c in v])
        else:
            attr.data.foreach_set("value", list(values))
    me.update()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    return obj


def set_smooth(obj):
    me = obj.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()


# ---------------------------------------------------------------- math & noise

def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def np_smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def fbm(x, y, z=0.0, octaves=4, seed=0.0):
    """Fractal noise in roughly [-1, 1]."""
    return noise.fractal(Vector((x + seed * 17.3, y - seed * 9.1, z)), 0.7, 2.0, octaves)


def rand_unit(rng):
    while True:
        v = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        if 0.01 < v.length <= 1.0:
            return v.normalized()


# ---------------------------------------------------------------- 2D outlines

def catmull_rom(points, samples=8, closed=True):
    """Smooth a list of 2D control points into a dense polyline."""
    pts = [np.array(p, dtype=float) for p in points]
    n = len(pts)
    out = []
    count = n if closed else n - 1
    for i in range(count):
        p0 = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed else pts[min(i + 2, n - 1)]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(pts[-1])
    return np.array(out)


def polyline_distance(px, py, poly, closed=True):
    """Distance from points (arrays) to a polyline, plus the arc length of the
    nearest point along it."""
    a = poly
    b = np.roll(poly, -1, axis=0) if closed else poly[1:]
    if not closed:
        a = poly[:-1]
    seg = b - a
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(seg_len)[:-1]])
    best = np.full(px.shape, np.inf)
    arc = np.zeros(px.shape)
    for i in range(len(a)):
        dx, dy = seg[i]
        l2 = dx * dx + dy * dy
        t = np.clip(((px - a[i, 0]) * dx + (py - a[i, 1]) * dy) / max(l2, 1e-12), 0.0, 1.0)
        qx = a[i, 0] + t * dx
        qy = a[i, 1] + t * dy
        d = np.hypot(px - qx, py - qy)
        closer = d < best
        best = np.where(closer, d, best)
        arc = np.where(closer, cum[i] + t * seg_len[i], arc)
    return best, arc


def inside_polygon(px, py, poly):
    inside = np.zeros(px.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        crosses = ((y1 > py) != (y2 > py)) & (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-12) + x1)
        inside ^= crosses
    return inside


def signed_distance(px, py, poly):
    """Negative inside the closed outline, positive outside."""
    d, _ = polyline_distance(px, py, poly, closed=True)
    return np.where(inside_polygon(px, py, poly), -d, d)


def polyline_point(poly, arc):
    """Position and unit tangent at arc length `arc` along an open polyline."""
    seg = poly[1:] - poly[:-1]
    lens = np.hypot(seg[:, 0], seg[:, 1])
    arc = min(max(arc, 0.0), lens.sum() - 1e-6)
    i = int(np.searchsorted(np.cumsum(lens), arc, side='right'))
    i = min(i, len(seg) - 1)
    start = arc - (np.cumsum(lens)[i] - lens[i])
    tangent = seg[i] / lens[i]
    return poly[i] + tangent * start, tangent


# ---------------------------------------------------------------- animation

def keyframe(target, path, frame, value, index=-1):
    if index >= 0:
        getattr(target, path)[index] = value
    else:
        setattr(target, path, value)
    target.keyframe_insert(data_path=path, frame=frame, index=index)


def time_driver(socket):
    """Drive a float socket with scene time in seconds."""
    fcurve = socket.driver_add("default_value")
    fcurve.driver.type = 'SCRIPTED'
    fcurve.driver.expression = f"(frame - 1) / {config.FPS}"
    return fcurve


def rng(seed):
    return random.Random(seed)


def seed_of(name):
    """A stable seed from a name (Python's hash() changes between runs)."""
    return zlib.crc32(name.encode())
