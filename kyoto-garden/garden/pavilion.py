"""The pavilion: a two-storey Zen temple hall with sliding paper screens on
the ground floor, bell-shaped windows upstairs, curved shingle roofs with
upturned corners, and a bronze phoenix on the peak. Built in local
coordinates (front facing -Y) and placed on the levelled yard."""

import math

from mathutils import Matrix, Vector

from . import layout, materials, util

WOOD, LIGHT, BOARDS, PLASTER, PAPER, STONE, ROOF, BRONZE, DARK = range(9)
MATERIALS = ["wood_dark", "wood_light", "wood_boards", "plaster", "shoji", "granite", "roof", "bronze",
             "dark_inside"]

UP = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------- walls

def wall_frame(origin, normal):
    """Local frame for a wall: X runs along the wall, Y points out of the
    building, Z is up."""
    n = Vector(normal)
    along = n.cross(UP)
    return Matrix.Translation(Vector(origin)) @ Matrix((along, n, UP)).transposed().to_4x4()


def shoji_bay(mb, frame, a0, a1, z0, z1):
    """Two overlapping sliding paper screens filling a bay."""
    overlap = 0.03
    width = (a1 - a0) / 2 + overlap / 2
    for i in range(2):
        s0 = a0 + i * (width - overlap)
        s1 = s0 + width
        y = 0.022 if i == 0 else -0.022
        stile, depth, kick = 0.042, 0.034, 0.22
        lo_y, hi_y = y - depth / 2, y + depth / 2
        mb.box((s0, lo_y, z0), (s0 + stile, hi_y, z1), LIGHT, frame)
        mb.box((s1 - stile, lo_y, z0), (s1, hi_y, z1), LIGHT, frame)
        mb.box((s0 + stile, lo_y, z1 - 0.045), (s1 - stile, hi_y, z1), LIGHT, frame)
        mb.box((s0 + stile, lo_y + 0.004, z0), (s1 - stile, hi_y - 0.004, z0 + kick), BOARDS, frame)
        p0, p1 = z0 + kick, z1 - 0.045
        mb.box((s0 + stile, y - 0.002, p0), (s1 - stile, y + 0.002, p1), PAPER, frame)
        inner = (s1 - stile) - (s0 + stile)
        bar = 0.016
        for k in (1, 2):
            a = s0 + stile + inner * k / 3
            mb.box((a - bar / 2, y - 0.012, p0), (a + bar / 2, y + 0.012, p1), LIGHT, frame)
        rows = max(int((p1 - p0) / 0.27), 2)
        for k in range(1, rows):
            z = p0 + (p1 - p0) * k / rows
            mb.box((s0 + stile, y - 0.012, z - bar / 2), (s1 - stile, y + 0.012, z + bar / 2), LIGHT, frame)


def solid_bay(mb, frame, a0, a1, z0, z1, mat, thickness=0.06):
    mb.box((a0, -thickness / 2, z0), (a1, thickness / 2, z1), mat, frame)


def katomado_outline(width, height, samples=22):
    """Outline of a bell-shaped window, counter-clockwise from the bottom
    right, in (x, z) with the base at z = 0."""
    side = 0.5 * height
    right = [(width / 2, 0.0), (width / 2, side)]
    for i in range(1, samples + 1):
        s = i / samples
        f = (1 - s) ** 1.3 * (1 + 1.3 * s) + 0.11 * math.sin(math.pi * min(s / 0.35, 1.0))
        right.append((width / 2 * f, side + (height - side) * s))
    left = [(-x, z) for x, z in reversed(right[:-1])]
    return right + left


def window_bay(mb, frame, a0, a1, z0, z1, sill=0.45, height=1.15):
    solid_bay(mb, frame, a0, a1, z0, z1, BOARDS, 0.07)
    centre = (a0 + a1) / 2
    width = min(0.82, (a1 - a0) * 0.55)
    outline = katomado_outline(width, height)
    base = z0 + sill
    front = 0.04
    # Paper, as a fan from the centre so the curved top stays clean.
    # The frame's Y axis points out of the wall, so reverse the outline to face out.
    pts = [Vector((centre + x, front, base + z)) for x, z in outline]
    cx = sum(p.x for p in pts) / len(pts)
    cz = sum(p.z for p in pts) / len(pts)
    hub = mb.vert(frame @ Vector((cx, front, cz)))
    ids = [mb.vert(frame @ p) for p in pts]
    n = len(ids)
    for i in range(n):
        j = (i + 1) % n
        mb.face((hub, ids[j], ids[i]), None, PAPER)
    # Frame ring around the outline.
    ring_w, ring_d = 0.065, 0.045
    outer, inner = [], []
    for i, (x, z) in enumerate(outline):
        px, pz = outline[i - 1]
        nx_, nz_ = outline[(i + 1) % n]
        tx, tz = nx_ - px, nz_ - pz
        length = math.hypot(tx, tz) or 1.0
        ox, oz = tz / length, -tx / length   # outward normal of a CCW outline
        inner.append((centre + x, base + z))
        outer.append((centre + x + ox * ring_w, base + z + oz * ring_w))
    def v(p, y):
        return mb.vert(frame @ Vector((p[0], y, p[1])))
    fi = [v(p, front + ring_d) for p in inner]
    fo = [v(p, front + ring_d) for p in outer]
    bo = [v(p, 0.0) for p in outer]
    bi = [v(p, front) for p in inner]
    for i in range(n):
        j = (i + 1) % n
        mb.face((fi[i], fi[j], fo[j], fo[i]), None, WOOD)
        mb.face((fo[i], fo[j], bo[j], bo[i]), None, WOOD)
        mb.face((bi[i], bi[j], fi[j], fi[i]), None, WOOD)
    # Lattice bars behind the paper's outer face.
    for k in (-1, 0, 1):
        x = k * width / 4
        top = max(z for (px, z) in outline if abs(px - x) < width / 10) - 0.02
        mb.box((centre + x - 0.008, front - 0.012, base), (centre + x + 0.008, front + 0.006, base + top), LIGHT, frame)
    for z in (0.3, 0.6):
        zz = height * z
        mb.box((centre - width / 2, front - 0.012, base + zz - 0.008), (centre + width / 2, front + 0.006, base + zz + 0.008),
               LIGHT, frame)


def door_bay(mb, frame, a0, a1, z0, z1):
    solid_bay(mb, frame, a0, a1, z0, z1, BOARDS, 0.07)
    mid = (a0 + a1) / 2
    top = z0 + min(1.9, z1 - z0 - 0.05)
    for s0, s1 in ((a0 + 0.06, mid - 0.005), (mid + 0.005, a1 - 0.06)):
        mb.box((s0, 0.035, z0 + 0.04), (s1, 0.06, top), BOARDS, frame)
        for x in (s0, s1 - 0.06):
            mb.box((x, 0.06, z0 + 0.04), (x + 0.06, 0.08, top), WOOD, frame)
        for k in range(5):
            z = z0 + 0.08 + (top - z0 - 0.16) * k / 4
            mb.box((s0, 0.06, z - 0.03), (s1, 0.08, z + 0.03), WOOD, frame)


# ---------------------------------------------------------------- roofs

class Roof:
    """A hip roof lofted from an eave rectangle up to an inner rectangle,
    with a concave profile and corners that sweep upward."""

    def __init__(self, outer, inner, z_eave, z_top, upturn, power, thickness):
        self.outer, self.inner = outer, inner
        self.z_eave, self.z_top = z_eave, z_top
        self.upturn, self.power, self.thickness = upturn, power, thickness

    @staticmethod
    def _rect_point(rect, side, a):
        x0, y0, x1, y1 = rect
        if side == 0:
            return Vector((util.lerp(x0, x1, a), y0))
        if side == 1:
            return Vector((x1, util.lerp(y0, y1, a)))
        if side == 2:
            return Vector((util.lerp(x1, x0, a), y1))
        return Vector((x0, util.lerp(y1, y0, a)))

    def point(self, side, a, t):
        o = self._rect_point(self.outer, side, a)
        i = self._rect_point(self.inner, side, a)
        xy = o.lerp(i, t)
        corner = abs(2 * a - 1) ** 6
        z = self.z_eave + (self.z_top - self.z_eave) * t ** self.power
        z += self.upturn * corner * (1 - t) ** 2.5
        return Vector((xy.x, xy.y, z))

    def build(self, name, coll, per_side=30, rings=22):
        mb = util.MeshBuilder()
        columns = [(side, k / per_side) for side in range(4) for k in range(per_side)]
        columns.append((0, 0.0))
        grid = []
        slope = [0.0] * len(columns)
        for r in range(rings + 1):
            t = r / rings
            row = []
            for c, (side, a) in enumerate(columns):
                p = self.point(side, a, t)
                if r > 0:
                    slope[c] += (p - self.point(side, a, (r - 1) / rings)).length
                row.append((mb.vert(p), slope[c]))
            grid.append(row)
        perimeter_u = []
        u = 0.0
        prev = None
        for side, a in columns:
            p = self.point(side, a, 0.0)
            if prev is not None:
                u += (p - prev).length
            perimeter_u.append(u)
            prev = p
        for r in range(rings):
            for c in range(len(columns) - 1):
                (a0, s0), (b0, t0) = grid[r][c], grid[r][c + 1]
                (a1, s1), (b1, t1) = grid[r + 1][c], grid[r + 1][c + 1]
                shrink0 = 1.0 - 0.6 * r / rings
                shrink1 = 1.0 - 0.6 * (r + 1) / rings
                mb.face((a0, b0, b1, a1),
                        [(perimeter_u[c] * shrink0, s0), (perimeter_u[c + 1] * shrink0, t0),
                         (perimeter_u[c + 1] * shrink1, t1), (perimeter_u[c] * shrink1, s1)], 0)
        top = [grid[rings][c][0] for c in range(len(columns) - 1)]
        mb.face(top, None, 0)
        obj = mb.to_object(name, coll, [materials.get("roof"), materials.get("wood_dark")], smooth=True)
        mod = obj.modifiers.new("Thickness", 'SOLIDIFY')
        mod.thickness = self.thickness
        mod.offset = -1.0
        mod.use_even_offset = True
        mod.material_offset = 1
        mod.material_offset_rim = 1
        return obj

    def rafters(self, mb, wall_t, spacing=0.27):
        """Exposed rafters under the eaves, from the eave edge back to the wall."""
        drop = self.thickness + 0.045
        for side in range(4):
            a_vals = []
            o0 = self._rect_point(self.outer, side, 0.0)
            o1 = self._rect_point(self.outer, side, 1.0)
            count = int((o1 - o0).length / spacing)
            for k in range(1, count):
                a = k / count
                if a < 0.07 or a > 0.93:
                    continue
                a_vals.append(a)
            for a in a_vals:
                p0 = self.point(side, a, 0.015) - Vector((0, 0, drop))
                p1 = self.point(side, a, wall_t[side]) - Vector((0, 0, drop))
                mb.beam(p0, p1, 0.06, 0.075, WOOD)


# ---------------------------------------------------------------- phoenix

def phoenix(mb, base):
    """A stylised bronze phoenix about 0.9 m tall, facing -Y."""
    def m(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        return base @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rz), 4, 'Z') @ \
            Matrix.Rotation(math.radians(ry), 4, 'Y') @ Matrix.Rotation(math.radians(rx), 4, 'X')

    mb.box((-0.07, -0.07, 0.0), (0.07, 0.07, 0.08), BRONZE, base)
    for x in (-0.035, 0.035):
        mb.beam(base @ Vector((x, 0.0, 0.07)), base @ Vector((x, -0.01, 0.24)), 0.025, 0.025, BRONZE)
    mb.ellipsoid((0, 0, 0), (0.085, 0.2, 0.105), m(0, 0, 0.32, rx=-25), mat=BRONZE)
    mb.ellipsoid((0, 0, 0), (0.042, 0.05, 0.11), m(0, -0.17, 0.48, rx=-35), mat=BRONZE)
    mb.ellipsoid((0, 0, 0), (0.042, 0.07, 0.045), m(0, -0.23, 0.6, rx=10), mat=BRONZE)
    mb.beam(base @ Vector((0, -0.28, 0.6)), base @ Vector((0, -0.35, 0.58)), 0.02, 0.022, BRONZE)
    crest = [(0.0, 0.0), (0.05, 0.02), (0.13, 0.1), (0.1, 0.11), (0.06, 0.07), (0.0, 0.05)]
    mb.prism(crest, 0.012, m(0, -0.2, 0.64, rz=90), BRONZE)
    wing = [(0.0, 0.0), (0.06, 0.0), (0.12, 0.08), (0.2, 0.2), (0.3, 0.4), (0.36, 0.58), (0.33, 0.6),
            (0.3, 0.5), (0.27, 0.52), (0.23, 0.4), (0.2, 0.42), (0.16, 0.3), (0.12, 0.32), (0.08, 0.2),
            (0.04, 0.2), (0.0, 0.1)]
    for sx in (1, -1):
        outline = wing if sx > 0 else [(-x, z) for x, z in reversed(wing)]
        mb.prism(outline, 0.016, m(0.06 * sx, 0.02, 0.36, rx=-28, rz=-12 * sx), BRONZE)
    plume = [(0.0, 0.0), (0.06, 0.03), (0.2, 0.1), (0.38, 0.24), (0.55, 0.45), (0.62, 0.6),
             (0.57, 0.62), (0.52, 0.5), (0.46, 0.42), (0.3, 0.24), (0.14, 0.11), (0.0, 0.05)]
    for k, sx in enumerate((-0.04, 0.0, 0.04)):
        mb.prism(plume, 0.014, m(sx, 0.14, 0.28, rz=90 + (k - 1) * 9, ry=0), BRONZE)


# ---------------------------------------------------------------- building

def build(coll):
    mb = util.MeshBuilder()
    hx, hy = 4.0, 3.2          # half size of the ground floor
    floor_z, sill_z = 0.62, 0.42
    head_z, beam_z, top_z = 2.32, 3.05, 3.25

    # Stone base, front steps and stepping stone.
    mb.box((-4.6, -4.6, -0.2), (4.6, 3.75, sill_z), STONE)
    mb.box((-0.95, -5.25, -0.2), (0.95, -4.6, 0.24), STONE)
    mb.box((-0.55, -5.75, -0.2), (0.55, -5.2, 0.1), STONE)

    # Interior volume so the screens glow against darkness, not the sky.
    mb.box((-hx + 0.12, -hy + 0.1, floor_z), (hx - 0.12, hy - 0.12, top_z), DARK)

    # Sills, veranda deck and its edge beam.
    for (x0, y0, x1, y1) in ((-hx, -hy - 0.1, hx, -hy + 0.1), (-hx, hy - 0.1, hx, hy + 0.1),
                             (-hx - 0.1, -hy, -hx + 0.1, hy), (hx - 0.1, -hy, hx + 0.1, hy)):
        mb.box((x0, y0, sill_z), (x1, y1, floor_z), WOOD)
    mb.box((-hx - 0.1, -4.15, 0.54), (hx + 0.1, -hy, floor_z), BOARDS)
    mb.box((-hx - 0.1, -4.2, 0.44), (hx + 0.1, -4.05, 0.56), WOOD)

    # Posts.
    xs = [-4.0, -2.0, 0.0, 2.0, 4.0]
    ys = [-3.2, -1.07, 1.07, 3.2]
    posts = set()
    for x in xs:
        posts.add((x, -hy))
        posts.add((x, hy))
    for y in ys:
        posts.add((-hx, y))
        posts.add((hx, y))
    for x, y in posts:
        mb.box((x - 0.1, y - 0.1, sill_z), (x + 0.1, y + 0.1, top_z), WOOD)
    for x in xs:   # slimmer veranda posts carrying the eave
        mb.box((x - 0.075, -4.12, 0.6), (x + 0.075, -3.97, 3.0), WOOD)
    mb.box((-hx - 0.15, -4.13, 2.86), (hx + 0.15, -3.96, 3.08), WOOD)

    # Beams ringing the ground floor.
    for z0, z1, out in ((head_z, head_z + 0.13, 0.03), (beam_z, top_z, 0.02), (top_z, top_z + 0.22, 0.05)):
        mb.box((-hx - out, -hy - 0.1 - out, z0), (hx + out, -hy + 0.1, z1), WOOD)
        mb.box((-hx - out, hy - 0.1, z0), (hx + out, hy + 0.1 + out, z1), WOOD)
        mb.box((-hx - 0.1 - out, -hy, z0), (-hx + 0.1, hy, z1), WOOD)
        mb.box((hx - 0.1, -hy, z0), (hx + 0.1 + out, hy, z1), WOOD)

    # Ground-floor walls.
    walls = {
        "front": (wall_frame((hx, -hy, 0), (0, -1, 0)), 2 * hx, ["shoji"] * 4),
        "east": (wall_frame((hx, hy, 0), (1, 0, 0)), 2 * hy, ["boards", "boards", "shoji"]),
        "back": (wall_frame((-hx, hy, 0), (0, 1, 0)), 2 * hx, ["boards"] * 4),
        "west": (wall_frame((-hx, -hy, 0), (-1, 0, 0)), 2 * hy, ["shoji", "shoji", "boards"]),
    }
    for frame, length, bays in walls.values():
        n = len(bays)
        for i, kind in enumerate(bays):
            a0 = length * i / n + 0.1
            a1 = length * (i + 1) / n - 0.1
            if kind == "shoji":
                shoji_bay(mb, frame, a0, a1, floor_z, head_z)
            else:
                solid_bay(mb, frame, a0, a1, floor_z, head_z, BOARDS)
            solid_bay(mb, frame, a0, a1, head_z + 0.13, beam_z, PLASTER, 0.08)

    # Lower roof.
    lower = Roof((-5.35, -5.25, 5.35, 4.25), (-3.05, -2.55, 3.05, 2.55), 2.98, 3.95, 0.24, 1.45, 0.17)
    lower_obj = lower.build("Pavilion Roof Lower", coll)
    lower.rafters(mb, [0.76, 0.587, 0.56, 0.587])

    # Upper floor: balcony, railing, walls, windows and doors.
    ux, uy, uz = 2.9, 2.4, 3.95
    mb.box((-3.45, -2.95, uz - 0.05), (3.45, 2.95, uz + 0.05), BOARDS)
    mb.box((-3.47, -2.97, uz - 0.28), (3.47, 2.97, uz - 0.05), WOOD)
    rail_z = (uz + 0.1, uz + 0.42, uz + 0.74)
    corners = [(-3.38, -2.88), (3.38, -2.88), (3.38, 2.88), (-3.38, 2.88)]
    for i in range(4):
        p0, p1 = Vector(corners[i]), Vector(corners[(i + 1) % 4])
        count = max(int((p1 - p0).length / 0.85), 1)
        for k in range(count + 1):
            p = p0.lerp(p1, k / count)
            mb.box((p.x - 0.045, p.y - 0.045, uz + 0.05), (p.x + 0.045, p.y + 0.045, uz + 0.78), WOOD)
        for z, size in zip(rail_z, (0.05, 0.04, 0.075)):
            mb.beam((p0.x, p0.y, z), (p1.x, p1.y, z), size, size, WOOD)
    mb.box((-ux + 0.1, -uy + 0.1, uz), (ux - 0.1, uy - 0.1, 6.2), DARK)
    upper_posts = [(-ux, -uy), (-0.97, -uy), (0.97, -uy), (ux, -uy), (-ux, uy), (-0.97, uy), (0.97, uy),
                   (ux, uy), (-ux, 0.0), (ux, 0.0)]
    for x, y in upper_posts:
        mb.box((x - 0.09, y - 0.09, uz), (x + 0.09, y + 0.09, 6.35), WOOD)
    upper_walls = {
        "front": (wall_frame((ux, -uy, 0), (0, -1, 0)), 2 * ux, ["window", "door", "window"]),
        "east": (wall_frame((ux, uy, 0), (1, 0, 0)), 2 * uy, ["window", "window"]),
        "back": (wall_frame((-ux, uy, 0), (0, 1, 0)), 2 * ux, ["window", "door", "window"]),
        "west": (wall_frame((-ux, -uy, 0), (-1, 0, 0)), 2 * uy, ["window", "window"]),
    }
    for frame, length, bays in upper_walls.values():
        n = len(bays)
        for i, kind in enumerate(bays):
            a0 = length * i / n + 0.09
            a1 = length * (i + 1) / n - 0.09
            if kind == "window":
                window_bay(mb, frame, a0, a1, uz + 0.05, 5.95)
            else:
                door_bay(mb, frame, a0, a1, uz + 0.05, 5.95)
    for z0, z1, out in ((5.95, 6.12, 0.02), (6.15, 6.35, 0.03), (6.42, 6.6, 0.12), (6.62, 6.8, 0.3)):
        mb.box((-ux - out, -uy - 0.09 - out, z0), (ux + out, -uy + 0.09, z1), WOOD)
        mb.box((-ux - out, uy - 0.09, z0), (ux + out, uy + 0.09 + out, z1), WOOD)
        mb.box((-ux - 0.09 - out, -uy, z0), (-ux + 0.09, uy, z1), WOOD)
        mb.box((ux - 0.09, -uy, z0), (ux + 0.09 + out, uy, z1), WOOD)
    for x, y in upper_posts:   # bracket blocks capping each post
        mb.box((x - 0.14, y - 0.14, 6.35), (x + 0.14, y + 0.14, 6.44), WOOD)

    # Upper roof, its rafters and the phoenix finial.
    upper = Roof((-4.25, -3.75, 4.25, 3.75), (-0.2, -0.2, 0.2, 0.2), 6.55, 9.35, 0.34, 1.75, 0.18)
    upper_obj = upper.build("Pavilion Roof Upper", coll)
    upper.rafters(mb, [0.38, 0.333, 0.38, 0.333])
    mb.box((-0.26, -0.26, 9.2), (0.26, 0.26, 9.42), BRONZE)
    mb.tube([(0, 0, 9.42), (0, 0, 9.62)], [0.1, 0.07], 12, BRONZE, cap_end=False)
    phoenix(mb, Matrix.Translation((0.0, 0.0, 9.6)))

    body = mb.to_object("Pavilion", coll, [materials.get(m) for m in MATERIALS])
    px, py = layout.PAVILION
    for obj in (body, lower_obj, upper_obj):
        obj.location = (px, py, layout.PAVILION_GROUND - 0.04)
    return body
