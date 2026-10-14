"""Where everything in the garden sits. All positions are in metres, Z up,
with the pond surface at Z = 0. North is +Y; the pavilion faces south across
the pond."""

import math

import numpy as np

from . import util

PAVILION = (-4.0, 9.6)          # centre of the building footprint
PAVILION_GROUND = 0.22          # height of the levelled ground under it

POND_CONTROL = [
    (-9.5, 4.6), (-5.0, 4.9), (-1.0, 4.7), (1.5, 4.0), (3.8, 5.4), (6.8, 6.0), (9.6, 4.8),
    (11.6, 3.4), (12.4, 1.0), (11.0, -2.5), (12.0, -6.0), (10.0, -9.5), (6.0, -11.0),
    (1.5, -10.2), (-2.5, -12.0), (-7.0, -11.2), (-11.0, -9.5), (-14.0, -6.5), (-15.0, -2.0),
    (-13.5, 1.5), (-12.0, 3.8),
]
POND = util.catmull_rom(POND_CONTROL, samples=8, closed=True)

ISLAND = (4.8, -4.6)

# The maple on the west shore whose leaf falls in shot 3, and where it lands.
LEAF_MAPLE = (-15.6, -0.4)
LEAF_LANDING = (-12.9, -1.3)

# The stream runs from its mouth in the pond up into the bamboo grove.
STREAM_CONTROL = [
    (10.4, 3.1), (13.2, 4.0), (16.2, 4.9), (19.0, 6.3), (21.8, 8.2), (24.2, 10.9),
    (26.3, 14.2), (28.8, 17.6), (32.0, 21.0), (36.0, 24.5), (41.0, 27.5),
]
STREAM = util.catmull_rom(STREAM_CONTROL, samples=6, closed=False)
STREAM_LENGTH = float(np.hypot(*(STREAM[1:] - STREAM[:-1]).T).sum())

CASCADE_ARC = 11.5   # a small step in the stream just upstream of the spout
SPOUT_ARC = 9.2      # where the bamboo spout pours into the stream


def stream_half_width(arc):
    return 0.75 + 0.22 * np.sin(np.asarray(arc) * 0.37) + 0.1 * np.sin(np.asarray(arc) * 1.3)


def stream_level(arc):
    """Height of the stream's water surface at arc length `arc`."""
    arc = np.asarray(arc, dtype=float)
    level = 0.018 * np.clip(arc, 0.0, None)
    level = level + 0.16 * util.np_smoothstep(CASCADE_ARC - 0.15, CASCADE_ARC + 0.15, arc)
    return level


def stream_point(arc):
    (x, y), tangent = util.polyline_point(STREAM, arc)
    return x, y, float(stream_level(arc)), tangent


def spout_layout():
    """Spout tip position (over the stream) and the base of its support post on
    the north bank."""
    x, y, level, tangent = stream_point(SPOUT_ARC)
    normal = np.array([-tangent[1], tangent[0]])  # left of the flow direction = north bank
    tip = np.array([x, y]) + normal * 0.25
    post = np.array([x, y]) + normal * 1.35
    return tip, post, level, normal


# Bamboo grove: a soft region north of the stream.
BAMBOO_CENTRE = (27.0, 19.0)


def in_bamboo_grove(x, y):
    dx = (x - BAMBOO_CENTRE[0]) / 15.0
    dy = (y - BAMBOO_CENTRE[1]) / 13.0
    return dx * dx + dy * dy < 1.0


# Gravel: the yard around the pavilion and a path to the stream.
GRAVEL_PATH = np.array([(1.6, 7.2), (4.6, 7.9), (7.6, 7.6), (10.0, 6.6), (11.9, 6.0)])


def gravel_mask(x, y):
    px, py = PAVILION
    yard = (util.np_smoothstep(6.6, 5.8, np.abs(x - px)) *
            util.np_smoothstep(5.1, 4.3, np.abs(y - (py + 0.2))))
    d, _ = util.polyline_distance(x, y, GRAVEL_PATH, closed=False)
    path = util.np_smoothstep(0.75, 0.45, d)
    return np.clip(np.maximum(yard, path), 0.0, 1.0)


def deg(a):
    return math.radians(a)
