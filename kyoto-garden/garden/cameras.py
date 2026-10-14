"""The four shot cameras. Each one makes a single slow move that eases in and
out, so the dissolves between shots stay calm."""

import bpy
import numpy as np

from . import config, layout, util


def shot_specs():
    tip, _, level, normal = layout.spout_layout()
    spout = np.array([tip[0], tip[1]])
    # Shot 2 looks across the stream at the spout from the south bank.
    across = -normal
    side = np.array([normal[1], -normal[0]])
    cam2_a = spout + across * 3.7 - side * 1.1
    cam2_b = cam2_a + side * 1.0
    lx, ly = layout.LEAF_LANDING
    return [
        {"name": "pond", "lens": 28.0, "fstop": 8.0, "keys": [
            (0.0, (6.0, -15.2, 2.1), (-1.2, 9.0, 3.5)),
            (6.2, (5.3, -12.8, 1.8), (-1.4, 9.0, 3.1)),
        ]},
        {"name": "bamboo", "lens": 32.0, "fstop": 4.0, "keys": [
            (0.0, (cam2_a[0], cam2_a[1], level + 1.1), (spout[0] + 0.2, spout[1] + 0.9, level + 0.95)),
            (5.5, (cam2_b[0], cam2_b[1], level + 1.15), (spout[0] + 0.6, spout[1] + 1.1, level + 1.0)),
        ]},
        {"name": "leaf", "lens": 42.0, "fstop": 2.8, "keys": [
            (0.0, (lx + 1.75, ly - 1.75, 0.82), (lx, ly, 0.08)),
            (5.0, (lx + 1.6, ly - 1.62, 0.8), (lx, ly, 0.06)),
        ]},
        {"name": "pavilion", "lens": 18.0, "fstop": 8.0, "keys": [
            (0.0, (-6.6, -9.4, 0.48), (-4.0, 9.6, 1.0)),
            (5.7, (-6.15, -7.2, 0.42), (-4.0, 9.6, 1.25)),
        ]},
    ]


def build(coll):
    scene = bpy.context.scene
    cams = []
    for index, spec in enumerate(shot_specs()):
        data = bpy.data.cameras.new(f"Camera {spec['name']}")
        data.lens = spec["lens"]
        data.sensor_width = 36.0
        data.clip_start = 0.05
        data.clip_end = 600.0
        cam = bpy.data.objects.new(f"Shot {index + 1} {spec['name']}", data)
        target = bpy.data.objects.new(f"Shot {index + 1} target", None)
        target.empty_display_size = 0.3
        coll.objects.link(cam)
        coll.objects.link(target)
        con = cam.constraints.new('TRACK_TO')
        con.target = target
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        data.dof.use_dof = True
        data.dof.focus_object = target
        data.dof.aperture_fstop = spec["fstop"]
        for seconds, pos, aim in spec["keys"]:
            frame = config.shot_frame(index, seconds)
            util.keyframe(cam, "location", frame, pos)
            util.keyframe(target, "location", frame, aim)
        start, _ = config.shot_range(index)
        marker = scene.timeline_markers.new(spec["name"], frame=start)
        marker.camera = cam
        cams.append(cam)
    scene.camera = cams[0]
    return cams
