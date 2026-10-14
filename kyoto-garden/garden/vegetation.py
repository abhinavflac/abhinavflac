"""Plants, all grown from code: cloud-pruned pines, Japanese maples in early
autumn colour, a bamboo grove, clipped shrubs, ferns, grass, pampas grass,
a wooded hill behind the garden, and fallen leaves on the moss and water.

Leaves and needles are instanced with geometry nodes, which also add a
gentle wind flutter."""

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

from . import layout, materials, terrain, util

UP = Vector((0.0, 0.0, 1.0))

MAPLE_COLOURS = ["green", "gold", "orange", "red", "crimson"]


# ---------------------------------------------------------------- helpers

def basis_euler(up, forward):
    z = Vector(up).normalized()
    y = Vector(forward)
    y = y - z * y.dot(z)
    if y.length < 1e-6:
        y = z.orthogonal()
    y.normalize()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed().to_euler()


def tilted(rnd, axis, amount):
    return (Vector(axis).normalized() + util.rand_unit(rnd) * amount).normalized()


_groups = {}


def scatter_group(source, flutter=0.0, sway=0.0):
    """Geometry nodes that put an instance from `source` on every point,
    using the point attributes rot, scale and variant, plus wind."""
    key = (source.name, round(flutter, 3), round(sway, 3))
    if key in _groups:
        return _groups[key]
    ng = bpy.data.node_groups.new(f"Scatter {source.name}", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new('NodeGroupInput'), n.new('NodeGroupOutput')
    info = n.new('GeometryNodeCollectionInfo')
    info.transform_space = 'ORIGINAL'
    info.inputs['Collection'].default_value = source
    info.inputs['Separate Children'].default_value = True
    info.inputs['Reset Children'].default_value = True

    def attr(name, kind):
        a = n.new('GeometryNodeInputNamedAttribute')
        a.data_type = kind
        a.inputs['Name'].default_value = name
        return a.outputs['Attribute']

    iop = n.new('GeometryNodeInstanceOnPoints')
    link(gin.outputs[0], iop.inputs['Points'])
    link(info.outputs[0], iop.inputs['Instance'])
    iop.inputs['Pick Instance'].default_value = True
    link(attr("variant", 'INT'), iop.inputs['Instance Index'])
    link(attr("rot", 'FLOAT_VECTOR'), iop.inputs['Rotation'])
    link(attr("scale", 'FLOAT'), iop.inputs['Scale'])
    geo = iop.outputs['Instances']

    if flutter > 0.0 or sway > 0.0:
        time = n.new('GeometryNodeInputSceneTime')
        pos = n.new('GeometryNodeInputPosition')
        scaled = n.new('ShaderNodeVectorMath')
        scaled.operation = 'SCALE'
        link(pos.outputs[0], scaled.inputs[0])
        scaled.inputs[3].default_value = 0.9
        wobble = n.new('ShaderNodeTexNoise')
        wobble.noise_dimensions = '4D'
        wobble.inputs['Scale'].default_value = 1.0
        wobble.inputs['Detail'].default_value = 1.0
        link(scaled.outputs[0], wobble.inputs['Vector'])
        speed = n.new('ShaderNodeMath')
        speed.operation = 'MULTIPLY'
        link(time.outputs['Seconds'], speed.inputs[0])
        speed.inputs[1].default_value = 0.6
        link(speed.outputs[0], wobble.inputs['W'])
        centred = n.new('ShaderNodeVectorMath')
        centred.operation = 'SUBTRACT'
        link(wobble.outputs['Color'], centred.inputs[0])
        centred.inputs[1].default_value = (0.5, 0.5, 0.5)
        if flutter > 0.0:
            angle = n.new('ShaderNodeVectorMath')
            angle.operation = 'SCALE'
            link(centred.outputs[0], angle.inputs[0])
            angle.inputs[3].default_value = flutter
            rotate = n.new('GeometryNodeRotateInstances')
            link(geo, rotate.inputs['Instances'])
            link(angle.outputs[0], rotate.inputs['Rotation'])
            geo = rotate.outputs['Instances']
        if sway > 0.0:
            offset = n.new('ShaderNodeVectorMath')
            offset.operation = 'MULTIPLY'
            link(centred.outputs[0], offset.inputs[0])
            offset.inputs[1].default_value = (sway, sway, sway * 0.3)
            move = n.new('GeometryNodeTranslateInstances')
            move.inputs['Local Space'].default_value = False
            link(geo, move.inputs['Instances'])
            link(offset.outputs[0], move.inputs['Translation'])
            geo = move.outputs['Instances']
    link(geo, gout.inputs[0])
    _groups[key] = ng
    return ng


def scatter(name, coll, source, points, rots, scales, variants, flutter=0.0, sway=0.0):
    if not points:
        return None
    obj = util.points_object(name, coll, points, {
        "rot": ('FLOAT_VECTOR', [tuple(r) for r in rots]),
        "scale": ('FLOAT', scales),
        "variant": ('INT', variants),
    })
    mod = obj.modifiers.new("Scatter", 'NODES')
    mod.node_group = scatter_group(source, flutter, sway)
    return obj


# ---------------------------------------------------------------- leaf shapes

def maple_leaf_builder(length, seed, steps=84):
    """A seven-lobed maple leaf in the XY plane, stalk at the origin,
    pointing along +Y, facing +Z."""
    rnd = util.rng(seed)
    mb = util.MeshBuilder()
    stalk = length * 0.35
    centre = Vector((0.0, stalk + length * 0.38, 0.0))
    lobes = [(0, 1.0), (40, 0.93), (-40, 0.93), (80, 0.74), (-80, 0.74), (122, 0.45), (-122, 0.45)]
    lobes = [(math.radians(a + rnd.uniform(-4, 4)), s * rnd.uniform(0.92, 1.05)) for a, s in lobes]
    hub = mb.vert(centre)
    ring = []
    for k in range(steps):
        th = -math.pi + 2 * math.pi * k / steps
        f = 0.0
        for ang, s in lobes:
            d = (th - ang + math.pi) % (2 * math.pi) - math.pi
            f = max(f, s * max(0.0, math.cos(d * 3.1)) ** 1.6)
        r = length * 0.62 * (0.3 + 0.7 * f) * (1 + 0.035 * math.sin(th * 46))
        x, y = math.sin(th) * r, math.cos(th) * r
        z = 0.12 * (r / length) ** 2 * length
        ring.append(mb.vert(centre + Vector((x, y, z))))
    uv_hub = (0.0, 0.0)
    for k in range(steps):
        j = (k + 1) % steps
        a, b = mb.verts[ring[k]], mb.verts[ring[j]]
        mb.face((hub, ring[k], ring[j]),
                [uv_hub, ((a[0] - centre.x) / length, (a[1] - centre.y) / length),
                 ((b[0] - centre.x) / length, (b[1] - centre.y) / length)])
    w = length * 0.012
    s0, s1, s2, s3 = (mb.vert((-w, 0, 0)), mb.vert((w, 0, 0)), mb.vert((w, stalk + 0.01, 0)), mb.vert((-w, stalk + 0.01, 0)))
    mb.face((s0, s1, s2, s3), [(0, -0.5)] * 4)
    return mb


def maple_cluster_builder(seed, steps=24, leaves=8, twig=True):
    """A twig tip carrying a spray of maple leaves, pointing along +Y and
    facing +Z. Instancing clusters fills a canopy with far fewer instances."""
    rnd = util.rng(seed)
    mb = util.MeshBuilder()
    if twig:
        mb.tube([(0, -0.02, 0), (0, 0.06, 0.005), (0, 0.12, 0.0)], [0.003, 0.0025, 0.002], 3, 0, cap_end=False)
    for k in range(leaves):
        leaf = maple_leaf_builder(rnd.uniform(0.07, 0.095), seed * 10 + k, steps)
        yaw = math.radians(util.lerp(-85, 85, k / max(leaves - 1, 1)) + rnd.uniform(-12, 12))
        pitch = math.radians(rnd.uniform(-18, 18))
        roll = math.radians(rnd.uniform(-20, 20))
        base = Vector((rnd.uniform(-0.01, 0.01), rnd.uniform(0.02, 0.12), rnd.uniform(-0.01, 0.015)))
        m = Matrix.Translation(base) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'X') @ \
            Matrix.Rotation(roll, 4, 'Y')
        mb.extend(leaf, m)
    return mb


def blade_builder(length, width, segments=4, curl=0.25, droop=0.0, pointed_base=True):
    """A narrow leaf along +Y, facing +Z, bending downward by `droop`."""
    mb = util.MeshBuilder()
    rows = []
    for i in range(segments + 1):
        t = i / segments
        half = width / 2 * math.sin(math.pi * min(t * 1.15, 1.0)) ** (0.6 if pointed_base else 0.3)
        if not pointed_base:
            half = width / 2 * (1 - t ** 1.5)
        y = length * t
        z = -droop * length * t * t
        cup = curl * half
        left = mb.vert((-half, y, z + cup))
        right = mb.vert((half, y, z + cup))
        mid = mb.vert((0.0, y, z))
        rows.append((left, mid, right, t))
    for i in range(segments):
        (l0, m0, r0, t0), (l1, m1, r1, t1) = rows[i], rows[i + 1]
        mb.face((l0, m0, m1, l1), [(-0.5, t0), (0, t0), (0, t1), (-0.5, t1)])
        mb.face((m0, r0, r1, m1), [(0, t0), (0.5, t0), (0.5, t1), (0, t1)])
    return mb


def needle_tuft_builder(seed, needles=26, twig=True):
    rnd = util.rng(seed)
    mb = util.MeshBuilder()
    for k in range(needles):
        ang = rnd.uniform(0, 2 * math.pi)
        spread = math.radians(rnd.uniform(15, 58))
        length = rnd.uniform(0.11, 0.17)
        d = Vector((math.sin(spread) * math.cos(ang), math.sin(spread) * math.sin(ang), math.cos(spread)))
        side = d.cross(UP if abs(d.z) < 0.99 else Vector((1, 0, 0))).normalized() * 0.0026
        p0 = Vector((0, 0, 0))
        p1 = d * length * 0.55 + Vector((0, 0, 0.008))
        p2 = d * length + Vector((0, 0, 0.012))
        ids = [mb.vert(p0 - side), mb.vert(p0 + side), mb.vert(p1 + side), mb.vert(p1 - side),
               mb.vert(p2 + side * 0.3), mb.vert(p2 - side * 0.3)]
        mb.face((ids[0], ids[1], ids[2], ids[3]), [(-0.1, 0), (0.1, 0), (0.1, 0.55), (-0.1, 0.55)])
        mb.face((ids[3], ids[2], ids[4], ids[5]), [(-0.1, 0.55), (0.1, 0.55), (0.05, 1), (-0.05, 1)])
    if twig:
        mb.tube([(0, 0, -0.06), (0, 0, 0.02)], [0.006, 0.004], 4, 0, cap_end=False)
    return mb


def source_from_builders(coll_name, builders):
    """`builders`: list of (name, MeshBuilder, material key). Object names are
    numbered so instance indices match the list order."""
    coll = util.source_collection(coll_name)
    for i, (name, mb, mat) in enumerate(builders):
        mb.to_object(f"{i:02d} {name}", coll, [materials.get(mat)], smooth=True)
    return coll


class Sources:
    """Instance sources shared by every plant."""

    def __init__(self):
        maple = []
        for c in MAPLE_COLOURS:
            for shape in range(2):
                maple.append((f"maple {c} {shape}", maple_leaf_builder(0.085, 11 + shape), f"maple_{c}"))
        self.maple = source_from_builders("Maple Leaves", maple)
        clusters, far = [], []
        for c in MAPLE_COLOURS:
            for shape in range(2):
                clusters.append((f"cluster {c} {shape}", maple_cluster_builder(70 + shape), f"maple_{c}"))
                far.append((f"far cluster {c} {shape}", maple_cluster_builder(90 + shape, steps=9, leaves=4, twig=False),
                            f"maple_{c}"))
        self.maple_clusters = source_from_builders("Maple Clusters", clusters)
        self.far_clusters = source_from_builders("Far Clusters", far)
        self.needles = source_from_builders(
            "Pine Tufts", [(f"tuft {i}", needle_tuft_builder(40 + i), "needles") for i in range(3)])
        self.far_needles = source_from_builders(
            "Far Tufts", [(f"far tuft {i}", needle_tuft_builder(60 + i, 9, False), "needles") for i in range(3)])
        self.shrub = source_from_builders(
            "Shrub Leaves", [(f"leaf {i}", blade_builder(0.04, 0.02, 3, 0.2, 0.1, False), "shrub_leaf") for i in range(2)])


def maple_variant(rnd, weights):
    c = rnd.choices(range(len(MAPLE_COLOURS)), weights=weights)[0]
    return c * 2 + rnd.randint(0, 1)


# ---------------------------------------------------------------- branching

class Axis:
    def __init__(self, points, radii, level):
        self.points, self.radii, self.level = points, radii, level

    def at(self, t):
        f = t * (len(self.points) - 1)
        i = min(int(f), len(self.points) - 2)
        a = f - i
        p = self.points[i].lerp(self.points[i + 1], a)
        d = (self.points[i + 1] - self.points[i]).normalized()
        r = util.lerp(self.radii[i], self.radii[i + 1], a)
        return p, d, r

    @property
    def tip(self):
        return self.points[-1]

    @property
    def direction(self):
        return (self.points[-1] - self.points[-2]).normalized()


def grow(start, direction, length, r0, r1, rnd, level=0, step=0.22, bend=0.12, gravity=0.0, rise=0.0,
         target=None, pull=0.0):
    pts = [Vector(start)]
    d = Vector(direction).normalized()
    n = max(2, int(length / step))
    seg = length / n
    for _ in range(n):
        d = d + util.rand_unit(rnd) * bend + Vector((0, 0, rise - gravity))
        if target is not None:
            d += (Vector(target) - pts[-1]).normalized() * pull
        d.normalize()
        pts.append(pts[-1] + d * seg)
    radii = [util.lerp(r0, r1, (i / n) ** 0.8) for i in range(n + 1)]
    return Axis(pts, radii, level)


def child_direction(parent_dir, angle_deg, azimuth):
    ref = UP if abs(parent_dir.dot(UP)) < 0.95 else Vector((1, 0, 0))
    side = parent_dir.cross(ref).normalized()
    side = Matrix.Rotation(azimuth, 3, parent_dir) @ side
    a = math.radians(angle_deg)
    return (parent_dir * math.cos(a) + side * math.sin(a)).normalized()


def axes_mesh(mb, axes, mat=0):
    for ax in axes:
        sides = 12 if ax.level == 0 else 8 if ax.level == 1 else 5
        if ax.radii[0] < 0.006:
            sides = 4
        mb.tube(ax.points, ax.radii, sides, mat, cap_end=True, u_scale=max(2 * math.pi * ax.radii[0], 0.05))


# ---------------------------------------------------------------- maples

def grow_maple(rnd, base, height, density, weights, reach=(), level2=(7, 11), twigs=(5, 9)):
    """Returns (axes, leaf placements). `reach` adds long branches aimed at
    given points: (height on trunk, target point, droop)."""
    base = Vector(base)
    axes = []
    trunk_r = 0.05 + 0.025 * height
    trunk_len = height * rnd.uniform(0.22, 0.32)
    trunk = grow(base - Vector((0, 0, 0.2)), tilted(rnd, UP, 0.15), trunk_len + 0.2, trunk_r * 1.25, trunk_r * 0.8,
                 rnd, 0, bend=0.06)
    axes.append(trunk)
    leaders = []
    count = rnd.randint(2, 4)
    for k in range(count):
        az = 2 * math.pi * k / count + rnd.uniform(-0.4, 0.4)
        d = child_direction(trunk.direction, rnd.uniform(28, 48), az)
        leaders.append(grow(trunk.tip, d, height * rnd.uniform(0.5, 0.65), trunk_r * 0.75, trunk_r * 0.2, rnd, 1,
                            bend=0.1, gravity=0.015, rise=0.01))
    for h, target, droop in reach:
        p, _, r = trunk.at(min(h / max(trunk_len, 0.1), 1.0))
        leaders.append(grow(p, (Vector(target) - p).normalized(), (Vector(target) - p).length * 1.05, trunk_r * 0.6,
                            0.012, rnd, 1, bend=0.06, gravity=droop, target=target, pull=0.25))
    axes += leaders
    leaves = []
    leaf_step = 0.03 / max(density, 0.05) ** 0.5
    for leader in leaders:
        n2 = rnd.randint(*level2)
        for k in range(n2):
            t = rnd.uniform(0.2, 1.0)
            p, d, r = leader.at(t)
            cd = child_direction(d, rnd.uniform(40, 70), k * 2.4 + rnd.uniform(-0.3, 0.3))
            cd = (cd + Vector((0, 0, -0.15))).normalized()
            length = rnd.uniform(0.6, 1.3) * (1.1 - 0.5 * t) * height / 5
            b2 = grow(p, cd, length, max(r * 0.55, 0.008), 0.006, rnd, 2, step=0.15, bend=0.12, gravity=0.06)
            axes.append(b2)
            for j in range(rnd.randint(*twigs)):
                t3 = rnd.uniform(0.2, 1.0)
                p3, d3, r3 = b2.at(t3)
                tw = grow(p3, child_direction(d3, rnd.uniform(35, 60), rnd.uniform(0, 6.28)),
                          rnd.uniform(0.18, 0.4), max(r3 * 0.6, 0.004), 0.003, rnd, 3, step=0.08, bend=0.15,
                          gravity=0.05)
                axes.append(tw)
                _leaves_along(tw, rnd, leaf_step, weights, leaves)
            _leaves_along(b2, rnd, leaf_step * 1.6, weights, leaves, start=0.6)
    return axes, leaves


def _leaves_along(axis, rnd, step, weights, out, start=0.2):
    length = sum((axis.points[i + 1] - axis.points[i]).length for i in range(len(axis.points) - 1))
    count = max(1, int(length * (1 - start) / step))
    for _ in range(count):
        p, d, _ = axis.at(rnd.uniform(start, 1.0))
        up = tilted(rnd, UP, 0.55)
        forward = (d + util.rand_unit(rnd) * 0.9)
        pos = p + util.rand_unit(rnd) * 0.03
        out.append((pos, basis_euler(up, forward), rnd.uniform(0.9, 1.35), maple_variant(rnd, weights)))


# ---------------------------------------------------------------- pines

def grow_pine(rnd, base, height, lean, density, reach=(), pad_scale=1.0):
    """Garden pine: a leaning, curving trunk with near-horizontal limbs ending
    in flat cloud-like pads of needles."""
    base = Vector(base)
    axes, pads = [], []
    lean_dir = Vector((math.sin(math.radians(lean[0])), math.cos(math.radians(lean[0])), 0.0))
    d0 = (UP + lean_dir * math.tan(math.radians(lean[1]))).normalized()
    trunk_r = 0.07 + 0.03 * height
    trunk = grow(base - Vector((0, 0, 0.25)), d0, height + 0.25, trunk_r * 1.3, trunk_r * 0.25, rnd, 0,
                 step=0.3, bend=0.13, rise=0.04)
    axes.append(trunk)
    count = rnd.randint(6, 9)
    limbs = []
    for k in range(count):
        t = util.lerp(0.38, 0.92, k / max(count - 1, 1)) + rnd.uniform(-0.03, 0.03)
        p, d, r = trunk.at(t)
        az = k * 2.4 + rnd.uniform(-0.3, 0.3)
        horizontal = Vector((math.cos(az), math.sin(az), rnd.uniform(-0.15, 0.2))).normalized()
        length = rnd.uniform(0.9, 1.6) * (1.25 - t * 0.7) * height / 5
        limbs.append(grow(p, horizontal, length, r * 0.6, 0.02, rnd, 1, step=0.2, bend=0.16, rise=0.02))
    for h_frac, bearing, length, rise in reach:
        p, d, r = trunk.at(h_frac)
        direction = Vector((math.sin(math.radians(bearing)), math.cos(math.radians(bearing)), rise)).normalized()
        limbs.append(grow(p, direction, length, r * 0.65, 0.025, rnd, 1, step=0.22, bend=0.1, rise=0.0))
    axes += limbs
    for limb in limbs:
        tips = [limb]
        for j in range(rnd.randint(1, 3)):
            p, d, r = limb.at(rnd.uniform(0.45, 0.85))
            side = child_direction(d, rnd.uniform(35, 60), rnd.uniform(0, 6.28))
            side = Vector((side.x, side.y, abs(side.z) * 0.3)).normalized()
            sub = grow(p, side, rnd.uniform(0.3, 0.7) * height / 5, r * 0.6, 0.012, rnd, 2, step=0.15, bend=0.15,
                       rise=0.05)
            axes.append(sub)
            tips.append(sub)
        for ax in tips:
            size = (0.45 if ax.level == 2 else 0.75) * rnd.uniform(0.85, 1.2) * pad_scale * height / 5
            pads.append((ax.tip + Vector((0, 0, 0.08)), Vector((size, size * rnd.uniform(0.8, 1.0), size * 0.42))))
    pads.append((trunk.tip + Vector((0, 0, 0.1)), Vector((0.8, 0.75, 0.42)) * pad_scale * height / 5))
    return axes, pads


def pad_points(rnd, pads, density, per_area=140, size=(1.3, 1.9)):
    points = []
    for centre, radii in pads:
        area = 2 * math.pi * radii.x * radii.y * 1.4
        count = max(12, int(area * per_area * density ** 0.5))
        for _ in range(count):
            v = util.rand_unit(rnd)
            if v.z < -0.35:
                v.z = -v.z * 0.5
            v.normalize()
            pos = centre + Vector((v.x * radii.x, v.y * radii.y, v.z * radii.z))
            normal = Vector((v.x / radii.x, v.y / radii.y, v.z / radii.z)).normalized()
            up = tilted(rnd, normal + UP * 0.4, 0.35)
            points.append((pos, basis_euler(up, util.rand_unit(rnd)), rnd.uniform(*size), rnd.randint(0, 2)))
    return points


def lumpy_ellipsoid(mb, centre, radii, seed, mat, rings=8, segments=14, amount=0.24, flat_base=0.55):
    """A clumpy foliage mass: an ellipsoid pushed in and out by noise, flatter
    underneath like a pruned pine pad."""
    offset = Vector((seed * 7.1, seed * 3.3, seed * 1.7))
    rows = []
    for i in range(rings + 1):
        phi = math.pi * i / rings
        row = []
        for j in range(segments + 1):
            th = 2 * math.pi * (j % segments) / segments
            d = Vector((math.sin(phi) * math.cos(th), math.sin(phi) * math.sin(th), math.cos(phi)))
            k = 1.0 + amount * noise.noise(d * 2.2 + offset) + 0.08 * noise.noise(d * 6.0 + offset)
            z = d.z * (flat_base if d.z < 0 else 1.0)
            row.append(mb.vert(centre + Vector((d.x * radii.x, d.y * radii.y, z * radii.z)) * k))
        rows.append(row)
    for i in range(rings):
        for j in range(segments):
            mb.face((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]), None, mat)


def pad_cores(mb, pads, mat, scale=0.72):
    for i, (centre, radii) in enumerate(pads):
        lumpy_ellipsoid(mb, centre - Vector((0, 0, radii.z * 0.1)), radii * scale, i, mat)


def conifer_crown(mb, height, radius, seed, mat, base=0.28):
    """A tiered, clumpy cone for a cedar. Returns surface samples (point,
    normal) for scattering needle tufts on it."""
    rings, segments = 22, 18
    offset = Vector((seed * 5.3, seed * 2.9, 0.0))
    grid, samples = [], []
    for i in range(rings + 1):
        t = i / rings
        z = height * util.lerp(base, 1.02, t)
        r = radius * (1 - t) ** 0.85 * (1 + 0.16 * math.sin(t * math.pi * 7)) + 0.05
        row = []
        for j in range(segments + 1):
            th = 2 * math.pi * (j % segments) / segments
            d = Vector((math.cos(th), math.sin(th), 0.0))
            k = 1.0 + 0.3 * noise.noise(Vector((d.x * 1.5, d.y * 1.5, z * 0.7)) + offset)
            p = Vector((d.x * r * k, d.y * r * k, z))
            row.append(mb.vert(p))
            if j < segments and 0 < i < rings:
                samples.append((p, (d + Vector((0, 0, 0.6))).normalized(), r))
        grid.append(row)
    for i in range(rings):
        for j in range(segments):
            mb.face((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]), None, mat)
    mb.face(list(reversed(grid[0][:-1])), None, mat)
    return samples


def grow_cedar(rnd, base, height):
    base = Vector(base)
    axes, pads = [], []
    trunk = grow(base - Vector((0, 0, 0.3)), tilted(rnd, UP, 0.04), height, 0.06 * height / 5 + 0.08, 0.03, rnd, 0,
                 step=0.5, bend=0.03, rise=0.05)
    axes.append(trunk)
    count = int(height * 2.2)
    for k in range(count):
        t = util.lerp(0.3, 0.97, k / count)
        p, d, r = trunk.at(t)
        az = k * 2.4
        length = (1.0 - t) * height * 0.28 + 0.3
        direction = Vector((math.cos(az), math.sin(az), -0.25)).normalized()
        limb = grow(p, direction, length, r * 0.4, 0.015, rnd, 1, step=0.3, bend=0.1, gravity=0.04)
        axes.append(limb)
        size = 0.45 + length * 0.4
        pads.append((limb.tip, Vector((size, size, size * 0.65))))
    pads.append((trunk.tip, Vector((0.5, 0.5, 0.9))))
    return axes, pads


# ---------------------------------------------------------------- plant objects

def maple_tree(coll, src, name, base, height, density, weights, reach=(), rnd=None):
    rnd = rnd or util.rng(util.seed_of(name))
    axes, leaves = grow_maple(rnd, base, height, density, weights, reach)
    mb = util.MeshBuilder()
    axes_mesh(mb, axes)
    trunk = mb.to_object(f"{name} wood", coll, [materials.get("bark_smooth")], smooth=True)
    scatter(f"{name} leaves", coll, src.maple_clusters, [l[0] for l in leaves], [l[1] for l in leaves],
            [l[2] for l in leaves], [l[3] for l in leaves], flutter=0.15, sway=0.015)
    return trunk, axes, leaves


def pine_tree(coll, src, name, base, height, lean, density, reach=(), pad_scale=1.0, rnd=None):
    rnd = rnd or util.rng(util.seed_of(name))
    axes, pads = grow_pine(rnd, base, height, lean, density, reach, pad_scale)
    mb = util.MeshBuilder()
    axes_mesh(mb, axes, 0)
    pad_cores(mb, pads, 1)
    trunk = mb.to_object(f"{name} wood", coll, [materials.get("bark_pine"), materials.get("needle_mass")],
                         smooth=True)
    pts = pad_points(rnd, pads, density)
    scatter(f"{name} needles", coll, src.needles, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts],
            [p[3] for p in pts], flutter=0.1, sway=0.008)
    return trunk


def shrub(coll, src, name, x, y, radius, height, density, rnd):
    ground = terrain.height(x, y)
    centre = Vector((x, y, ground + height * 0.35))
    seed = Vector((rnd.uniform(0, 100), rnd.uniform(0, 100), 0))

    def surface(v):
        k = 1.0 + 0.13 * noise.noise(v * 1.8 + seed) + 0.05 * noise.noise(v * 5.0 + seed)
        return centre + Vector((v.x * radius, v.y * radius * 0.92, v.z * height)) * k

    mb = util.MeshBuilder()
    rows = []
    for i in range(9):
        phi = math.pi * i / 8
        row = []
        for j in range(17):
            th = 2 * math.pi * j / 16
            v = Vector((math.sin(phi) * math.cos(th), math.sin(phi) * math.sin(th), math.cos(phi)))
            row.append(mb.vert(centre + (surface(v) - centre) * 0.9))
        rows.append(row)
    for i in range(8):
        for j in range(16):
            mb.face((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
    mb.to_object(f"{name} core", coll, [materials.get("foliage_core")], smooth=True)
    area = 4 * math.pi * (radius * radius * 2 + radius * height) / 3
    count = int(area * 700 * density)
    pts, rots, scales, variants = [], [], [], []
    for _ in range(count):
        v = util.rand_unit(rnd)
        if v.z < -0.4:
            continue
        p = surface(v)
        n = (p - centre).normalized()
        pts.append(p)
        rots.append(basis_euler(tilted(rnd, n, 0.5), util.rand_unit(rnd)))
        scales.append(rnd.uniform(0.8, 1.3))
        variants.append(rnd.randint(0, 1))
    scatter(f"{name} leaves", coll, src.shrub, pts, rots, scales, variants, flutter=0.06)


def fern_builder(rnd):
    mb = util.MeshBuilder()
    fronds = rnd.randint(8, 12)
    for f in range(fronds):
        az = 2 * math.pi * f / fronds + rnd.uniform(-0.2, 0.2)
        length = rnd.uniform(0.45, 0.75)
        out = Vector((math.cos(az), math.sin(az), 0))
        rachis = []
        for i in range(9):
            t = i / 8
            rachis.append(out * length * t * 0.9 + Vector((0, 0, length * (0.9 * t - 0.75 * t * t) + 0.02)))
        for i in range(1, 8):
            t = i / 8
            p = rachis[i]
            d = (rachis[i + 1] - rachis[i - 1]).normalized()
            side = d.cross(UP).normalized()
            pl = length * 0.22 * math.sin(math.pi * min(t * 1.1, 1.0)) + 0.02
            for s in (-1, 1):
                tip = p + side * s * pl + d * pl * 0.3 - Vector((0, 0, pl * 0.25))
                w = d * pl * 0.18
                a = mb.vert(p - w)
                b = mb.vert(p + w)
                c = mb.vert(tip)
                mb.face((a, b, c) if s > 0 else (b, a, c), [(0, 0), (0.2, 0), (0, 1)])
        mb.tube(rachis, [0.004] * len(rachis), 3, 0, cap_end=False)
    return mb


def grass_builder(rnd, blades=18, height=0.4):
    mb = util.MeshBuilder()
    for _ in range(blades):
        b = blade_builder(rnd.uniform(0.6, 1.0) * height, 0.012, 4, 0.1, rnd.uniform(0.2, 0.6), True)
        az = rnd.uniform(0, 2 * math.pi)
        tilt = math.radians(rnd.uniform(-75, -40))
        m = Matrix.Rotation(az, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'X')
        mb.extend(b, m)
    return mb


def pampas_clump(coll, x, y, rnd):
    ground = terrain.height(x, y)
    base = Vector((x, y, ground))
    leaves = util.MeshBuilder()
    for _ in range(45):
        b = blade_builder(rnd.uniform(0.9, 1.5), 0.016, 6, 0.1, rnd.uniform(0.35, 0.7), True)
        m = Matrix.Translation(base) @ Matrix.Rotation(rnd.uniform(0, 6.28), 4, 'Z') @ \
            Matrix.Rotation(math.radians(rnd.uniform(-80, -50)), 4, 'X')
        leaves.extend(b, m)
    leaves.to_object("Pampas Leaves", coll, [materials.get("grass")], smooth=True)
    plumes = util.MeshBuilder()
    for k in range(11):
        top = base + Vector((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35), rnd.uniform(1.6, 2.1)))
        plumes.tube([base, base.lerp(top, 0.6), top], [0.006, 0.005, 0.004], 4, 0)
        for s in range(30):
            d = Vector((rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), -1.0)).normalized()
            start = top - Vector((0, 0, rnd.uniform(0.0, 0.32)))
            strand = blade_builder(rnd.uniform(0.18, 0.32), 0.03, 3, 0.4, -0.2, True)
            m = Matrix.Translation(start) @ basis_euler(d.cross(Vector((1, 0, 0))), d).to_matrix().to_4x4()
            plumes.extend(strand, m)
    plumes.to_object("Pampas Plumes", coll, [materials.get("pampas")], smooth=True)


# ---------------------------------------------------------------- bamboo

def bamboo_culm(rnd, height, radius):
    mb = util.MeshBuilder()
    internode = 0.34
    lean = util.rand_unit(rnd) * 0.04
    pts, radii = [], []
    nodes = int(height / internode)
    pos = Vector((0, 0, -0.2))
    d = (UP + Vector((lean.x, lean.y, 0))).normalized()
    for i in range(nodes + 1):
        t = i / nodes
        r = radius * (1.0 - 0.55 * t)
        for f, bulge in ((0.0, 1.06), (0.08, 1.0), (0.92, 1.0)):
            pts.append(pos + d * internode * f)
            radii.append(r * bulge)
        pos = pos + d * internode
        d = (d + Vector((lean.x, lean.y, 0)) * 0.15 * t).normalized()
    mb.tube(pts, radii, 10, 0, cap_end=True, v_scale=1 / internode)
    leaf_mb = util.MeshBuilder()
    for i in range(int(nodes * 0.22), nodes):
        p = pts[i * 3]
        for k in range(rnd.randint(2, 4)):
            az = i * 2.1 + k * math.pi + rnd.uniform(-0.3, 0.3)
            twig_d = Vector((math.cos(az), math.sin(az), rnd.uniform(0.4, 0.9))).normalized()
            tw_len = rnd.uniform(0.35, 0.8) * (1.1 - (i / nodes) * 0.4)
            twig = [p + twig_d * tw_len * s + Vector((0, 0, -0.15 * tw_len * s * s)) for s in (0, 0.5, 1.0)]
            mb.tube(twig, [0.006, 0.004, 0.003], 3, 0, cap_end=False)
            for j in range(rnd.randint(11, 16)):
                s = rnd.uniform(0.15, 1.0)
                q = twig[0].lerp(twig[1], min(s * 2, 1)) if s < 0.5 else twig[1].lerp(twig[2], (s - 0.5) * 2)
                leaf = blade_builder(rnd.uniform(0.17, 0.25), rnd.uniform(0.03, 0.04), 4, 0.15,
                                     rnd.uniform(0.3, 0.8), True)
                out = Vector((twig_d.x, twig_d.y, 0)).normalized() + util.rand_unit(rnd) * 0.8
                out.z = -abs(out.z) * 0.5 - 0.2
                m = Matrix.Translation(q) @ basis_euler(tilted(rnd, UP, 0.4), out).to_matrix().to_4x4()
                leaf_mb.extend(leaf, m)
    return mb, leaf_mb


def bamboo_grove(coll, quality, rnd):
    src = util.source_collection("Bamboo Variants")
    for v in range(6):
        height = rnd.uniform(7.0, 11.5)
        radius = rnd.uniform(0.035, 0.06)
        culm, leaves = bamboo_culm(rnd, height, radius)
        leaves.mats = [1] * len(leaves.mats)
        culm.extend(leaves)
        culm.to_object(f"{v:02d} bamboo", src, [materials.get("bamboo"), materials.get("bamboo_leaf")], smooth=True)
    density = quality["density"]
    tip, post, _, _ = layout.spout_layout()
    pts, rots, scales, variants = [], [], [], []
    cx, cy = layout.BAMBOO_CENTRE
    spacing = 1.15 / math.sqrt(max(density, 0.05))
    for gx in np.arange(cx - 16, cx + 16, spacing):
        for gy in np.arange(cy - 14, cy + 14, spacing):
            x, y = gx + rnd.uniform(-0.45, 0.45) * spacing, gy + rnd.uniform(-0.45, 0.45) * spacing
            if not layout.in_bamboo_grove(x, y):
                continue
            ds, arc = util.polyline_distance(np.array([x]), np.array([y]), layout.STREAM, closed=False)
            if ds[0] < float(layout.stream_half_width(arc[0])) + 1.6:
                continue
            if math.hypot(x - post[0], y - post[1]) < 2.2:
                continue
            pts.append((x, y, terrain.height(x, y)))
            rots.append((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), rnd.uniform(0, 6.28)))
            scales.append(rnd.uniform(0.85, 1.15))
            variants.append(rnd.randint(0, 5))
    scatter("Bamboo Grove", coll, src, pts, rots, scales, variants, flutter=0.012)


# ---------------------------------------------------------------- background forest

def forest_variants(src_clusters, src_far_needles, density, rnd):
    """Collections holding a few tree designs used to fill the hills."""
    variants = []
    root = util.source_collection("Forest Trees")
    specs = [("broadleaf A", "broad", [6, 1, 0, 0, 0]), ("broadleaf B", "broad", [5, 2, 0.4, 0, 0]),
             ("broadleaf gold", "broad", [2, 5, 1, 0.2, 0]), ("broadleaf red", "broad", [2, 1, 2, 3, 1]),
             ("cedar A", "cedar", None), ("cedar B", "cedar", None), ("pine", "pine", None)]
    for name, kind, weights in specs:
        coll = util.collection(f"Forest {name}", root)
        if kind == "broad":
            axes, leaves = grow_maple(rnd, (0, 0, 0), rnd.uniform(9, 13), density * 0.04, weights,
                                      level2=(5, 8), twigs=(2, 4))
            mb = util.MeshBuilder()
            axes_mesh(mb, axes)
            mb.to_object(f"{name} wood", coll, [materials.get("bark_smooth")], smooth=True)
            scatter(f"{name} leaves", coll, src_clusters, [l[0] for l in leaves], [l[1] for l in leaves],
                    [l[2] * 4.5 for l in leaves], [l[3] for l in leaves], flutter=0.1)
        elif kind == "cedar":
            height = rnd.uniform(13, 18)
            mb = util.MeshBuilder()
            trunk = grow(Vector((0, 0, -0.3)), tilted(rnd, UP, 0.03), height * 0.9, 0.2 + height * 0.012, 0.04,
                         rnd, 0, step=0.6, bend=0.02, rise=0.05)
            axes_mesh(mb, [trunk], 0)
            samples = conifer_crown(mb, height, height * rnd.uniform(0.2, 0.25), len(variants), 1)
            mb.to_object(f"{name} wood", coll, [materials.get("bark_pine"), materials.get("needle_mass")],
                         smooth=True)
            pts = []
            for p, n, r in samples:
                for _ in range(max(1, int(r * 2.5 * density ** 0.5))):
                    q = p + util.rand_unit(rnd) * 0.25
                    pts.append((q, basis_euler(tilted(rnd, n, 0.4), util.rand_unit(rnd)), rnd.uniform(3.4, 4.6),
                                rnd.randint(0, 2)))
            scatter(f"{name} needles", coll, src_far_needles, [p[0] for p in pts], [p[1] for p in pts],
                    [p[2] for p in pts], [p[3] for p in pts], flutter=0.05)
        else:
            axes, pads = grow_pine(rnd, (0, 0, 0), rnd.uniform(8, 11), (rnd.uniform(0, 360), 6), density)
            mb = util.MeshBuilder()
            axes_mesh(mb, axes, 0)
            pad_cores(mb, pads, 1, 0.85)
            mb.to_object(f"{name} wood", coll, [materials.get("bark_pine"), materials.get("needle_mass")],
                         smooth=True)
            pts = pad_points(rnd, pads, 1.0, per_area=2.5 * density ** 0.5, size=(3.4, 4.6))
            scatter(f"{name} needles", coll, src_far_needles, [p[0] for p in pts], [p[1] for p in pts],
                    [p[2] for p in pts], [p[3] for p in pts], flutter=0.05)
        variants.append(coll)
    return variants


def forest(coll, variants, density, rnd):
    regions = [(-46, 22, 17, 62), (-58, -18, -40, 20), (-22, 32, -46, -17), (42, 78, -32, 50), (16, 44, 30, 60)]
    spacing = 5.5 / max(density, 0.1) ** 0.35
    count = 0
    for x0, x1, y0, y1 in regions:
        for gx in np.arange(x0, x1, spacing):
            for gy in np.arange(y0, y1, spacing):
                x = gx + rnd.uniform(-0.45, 0.45) * spacing
                y = gy + rnd.uniform(-0.45, 0.45) * spacing
                if layout.in_bamboo_grove(x, y):
                    continue
                if util.signed_distance(np.array([x]), np.array([y]), layout.POND)[0] < 4:
                    continue
                if math.hypot(x - layout.PAVILION[0], y - layout.PAVILION[1]) < 9:
                    continue
                pick = variants[rnd.choices(range(len(variants)), weights=[3, 3, 1.2, 0.8, 2, 2, 1.5])[0]]
                inst = bpy.data.objects.new(f"Forest tree {count:03d}", None)
                inst.instance_type = 'COLLECTION'
                inst.instance_collection = pick
                inst.location = (x, y, terrain.height(x, y))
                inst.rotation_euler.z = rnd.uniform(0, 6.28)
                s = rnd.uniform(0.8, 1.25)
                inst.scale = (s, s, s * rnd.uniform(0.9, 1.15))
                coll.objects.link(inst)
                count += 1
    print(f"[garden] forest trees: {count}")


# ---------------------------------------------------------------- ground cover

def scatter_ground_cover(coll, quality, rnd):
    density = quality["density"]
    ferns = util.source_collection("Ferns")
    for i in range(4):
        fern_builder(util.rng(500 + i)).to_object(f"{i:02d} fern", ferns, [materials.get("fern")], smooth=True)
    grass = util.source_collection("Grass Tufts")
    for i in range(3):
        grass_builder(util.rng(600 + i)).to_object(f"{i:02d} grass", grass, [materials.get("grass")], smooth=True)

    fern_pts, grass_pts = [], []
    # Along the stream banks and the edge of the bamboo grove.
    arc = 0.5
    while arc < layout.STREAM_LENGTH - 1:
        (x, y), tangent = util.polyline_point(layout.STREAM, arc)
        normal = np.array([-tangent[1], tangent[0]])
        w = float(layout.stream_half_width(arc))
        for side in (-1, 1):
            off = w + rnd.uniform(0.3, 1.6)
            p = np.array([x, y]) + normal * side * off
            (fern_pts if rnd.random() < 0.55 else grass_pts).append((p[0], p[1]))
        arc += 0.7 / max(density, 0.2) ** 0.5
    # Pond banks.
    poly = layout.POND
    for k in range(0, len(poly), 2):
        if rnd.random() < 0.5 * density + 0.2:
            a, b = poly[k], poly[(k + 1) % len(poly)]
            tangent = (b - a) / max(np.hypot(*(b - a)), 1e-6)
            outward = np.array([tangent[1], -tangent[0]])
            p = a + outward * rnd.uniform(0.6, 1.4)
            grass_pts.append((p[0], p[1]))
    # Bamboo floor.
    cx, cy = layout.BAMBOO_CENTRE
    for _ in range(int(80 * density)):
        x, y = cx + rnd.uniform(-14, 14), cy + rnd.uniform(-12, 12)
        if layout.in_bamboo_grove(x, y):
            fern_pts.append((x, y))

    # A light sprinkling of grass and ferns over the garden's moss.
    for _ in range(int(500 * density)):
        x, y = rnd.uniform(-19, 22), rnd.uniform(-17, 17)
        if util.signed_distance(np.array([x]), np.array([y]), layout.POND)[0] < 0.8:
            continue
        if layout.gravel_mask(np.array([x]), np.array([y]))[0] > 0.1:
            continue
        (grass_pts if rnd.random() < 0.7 else fern_pts).append((x, y))

    def place(points, source, name, size):
        pts, rots, scales, variants = [], [], [], []
        for x, y in points:
            if util.signed_distance(np.array([x]), np.array([y]), layout.POND)[0] < 0.2:
                continue
            pts.append((x, y, terrain.height(x, y) - 0.02))
            rots.append((rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), rnd.uniform(0, 6.28)))
            scales.append(rnd.uniform(0.7, 1.3) * size)
            variants.append(rnd.randint(0, len(source.objects) - 1))
        scatter(name, coll, source, pts, rots, scales, variants, flutter=0.05)

    place(fern_pts, ferns, "Ferns", 1.0)
    place(grass_pts, grass, "Grass", 1.0)


def fallen_leaves(coll, src, rnd):
    """Leaves on the moss under the maples and floating on the pond."""
    pts, rots, scales, variants = [], [], [], []
    for (x, y), n, weights in ((layout.LEAF_MAPLE, 120, [1, 2, 3, 3, 1]), ((-13.2, 9.5), 90, [0, 1, 2, 4, 3]),
                               ((12.5, -4.8), 70, [1, 4, 3, 1, 0])):
        for _ in range(n):
            r = 3.2 * math.sqrt(rnd.random())
            a = rnd.uniform(0, 6.28)
            px, py = x + r * math.cos(a), y + r * math.sin(a)
            inside = util.signed_distance(np.array([px]), np.array([py]), layout.POND)[0] < -0.3
            z = 0.004 if inside else terrain.height(px, py) + 0.01
            pts.append((px, py, z))
            rots.append(basis_euler(tilted(rnd, UP, 0.12 if inside else 0.3), util.rand_unit(rnd)))
            scales.append(rnd.uniform(0.85, 1.15))
            variants.append(maple_variant(rnd, weights))
    scatter("Fallen Leaves", coll, src.maple, pts, rots, scales, variants)


# ---------------------------------------------------------------- build

def build(coll, quality):
    rnd = util.rng(21)
    density = quality["density"]
    src = Sources()
    trees = util.collection("Trees", coll)

    # Garden pines: (name, position, height, lean bearing/angle, framing limbs, pad scale)
    pines = [
        ("Pine west", (-11.4, 5.6), 5.8, (110, 22), (), 1.0),
        ("Pine frame", (8.6, -12.9), 5.2, (320, 10), ((0.6, 318, 2.6, -0.04), (0.78, 335, 1.9, 0.0)), 0.7),
        ("Pine island", (4.9, -4.5), 2.6, (220, 18), (), 0.9),
        ("Pine back right", (1.9, 12.8), 7.0, (200, 8), (), 1.0),
        ("Pine back left", (-10.2, 13.8), 6.5, (150, 10), (), 1.0),
        ("Pine east", (14.4, -2.6), 5.0, (250, 14), (), 1.0),
        ("Pine shore", (-13.4, 2.9), 5.0, (100, 26), ((0.55, 95, 2.8, 0.05),), 1.0),
        ("Pine stream", (23.6, 3.2), 4.6, (300, 12), ((0.6, 300, 2.4, -0.02),), 0.9),
        ("Pine south", (-4.2, -14.6), 5.5, (10, 8), (), 1.0),
    ]
    for name, (x, y), h, lean, reach, pad in pines:
        pine_tree(trees, src, name, (x, y, terrain.height(x, y)), h, lean, density, reach, pad,
                  rnd=util.rng(util.seed_of(name)))

    lx, ly = layout.LEAF_LANDING
    mx, my = layout.LEAF_MAPLE
    maples = [
        ("Maple leaf shot", (mx, my), 4.6, [1, 3, 4, 3, 1],
         ((1.1, (lx + 0.55, ly + 0.45, 0.72), 0.03), (1.4, (lx - 0.1, ly + 1.3, 0.95), 0.02))),
        ("Maple red", (-13.4, 9.6), 5.0, [0.5, 0.5, 1, 4, 3], ()),
        ("Maple right", (5.8, 11.4), 5.2, [5, 1, 1, 0.3, 0], ()),
        ("Maple east", (12.6, -5.2), 4.4, [1, 4, 3, 1, 0], ()),
        ("Maple stream", (14.4, 6.4), 4.8, [6, 1, 0.5, 0.2, 0], ()),
        ("Maple back", (7.6, 14.6), 5.5, [0.5, 0.5, 1, 3, 2], ()),
        ("Maple gold", (-6.4, 15.6), 5.0, [1, 5, 2, 0.5, 0], ()),
        ("Maple south", (2.0, -14.0), 4.2, [3, 2, 2, 1, 0], ()),
    ]
    for name, (x, y), h, weights, reach in maples:
        maple_tree(trees, src, name, (x, y, terrain.height(x, y)), h, density, weights, reach,
                   rnd=util.rng(util.seed_of(name)))

    shrubs = [(-9.6, 6.9, 0.9, 0.55), (1.4, 6.1, 0.7, 0.45), (2.8, 13.6, 1.0, 0.6), (-11.0, 11.9, 1.1, 0.65),
              (3.2, -12.7, 0.95, 0.55), (0.2, -13.0, 0.7, 0.45), (-3.8, -13.7, 1.0, 0.6), (8.6, -10.9, 0.6, 0.4),
              (11.6, -8.0, 0.85, 0.5), (-15.8, -4.6, 0.8, 0.5), (-16.5, 1.8, 1.0, 0.6), (-14.2, 5.0, 0.7, 0.45),
              (13.8, -3.6, 0.8, 0.5), (12.9, 5.8, 0.7, 0.45), (15.6, 1.4, 0.9, 0.55), (4.2, -3.9, 0.45, 0.3),
              (17.8, 3.2, 0.6, 0.4), (-6.0, 6.6, 0.6, 0.4), (-1.2, 6.4, 0.55, 0.38), (6.4, 7.2, 0.8, 0.5)]
    shrubs_coll = util.collection("Shrubs", coll)
    for i, (x, y, r, h) in enumerate(shrubs):
        shrub(shrubs_coll, src, f"Shrub {i:02d}", x, y, r, h, density, rnd)

    bamboo_grove(util.collection("Bamboo", coll), quality, rnd)
    pampas_clump(util.collection("Pampas", coll), 0.9, 6.3, rnd)
    scatter_ground_cover(util.collection("Ground Cover", coll), quality, rnd)
    fallen_leaves(util.collection("Fallen Leaves", coll), src, rnd)
    variants = forest_variants(src.far_clusters, src.far_needles, density, rnd)
    forest(util.collection("Forest", coll), variants, density, rnd)
