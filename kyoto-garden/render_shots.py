"""Render every frame of the four shots from a built scene.

    blender -b renders/garden_final.blend -P kyoto-garden/render_shots.py -- --shots 1,2,3,4

Frames go to renders/<quality>/shot<N>/####.png. Frames that already exist
are skipped, so an interrupted render can be resumed by running it again,
and several Blender processes can share the work.

Options (after the `--`):
  --shots 1,2,3,4      which shots to render (default all)
  --step N             render every Nth frame, for quick timing checks
  --engine NAME        override the engine, e.g. BLENDER_WORKBENCH for a fast animatic
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402

from garden import config  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="render_shots.py")
    p.add_argument("--shots", default="1,2,3,4")
    p.add_argument("--step", type=int, default=1)
    p.add_argument("--engine", default=None)
    p.add_argument("--out", default=None)
    return p.parse_args(argv)


def claim(path, stale_after=900):
    """Reserve a frame by creating an empty file. Returns False if the frame
    is finished or another process is rendering it right now; an empty file
    older than `stale_after` seconds is treated as an abandoned frame."""
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL))
        return True
    except FileExistsError:
        st = os.stat(path)
        if st.st_size == 0 and time.time() - st.st_mtime > stale_after:
            os.utime(path)
            return True
        return False


def setup_workbench(scene):
    scene.render.engine = 'BLENDER_WORKBENCH'
    shading = scene.display.shading
    shading.light = 'STUDIO'
    shading.color_type = 'MATERIAL'
    shading.show_shadows = True
    shading.show_cavity = True
    scene.display.render_aa = '8'


def main():
    args = parse_args()
    scene = bpy.context.scene
    quality = scene.get("quality", "preview")
    out_root = args.out or os.path.join(HERE, "renders", quality)
    if args.engine == 'BLENDER_WORKBENCH':
        setup_workbench(scene)
        out_root = args.out or os.path.join(HERE, "renders", "animatic")
    elif args.engine:
        scene.render.engine = args.engine
    shots = [int(s) for s in args.shots.split(",") if s.strip()]
    render_frames(scene, shots, out_root, args.step)


def render_frames(scene, shots, out_root, step=1):
    """Render the given shots (1-4) into out_root/shot<N>/####.png."""
    markers = {m.name: m.camera for m in scene.timeline_markers}
    for shot in shots:
        index = shot - 1
        name = config.SHOTS[index]["name"]
        scene.camera = markers[name]
        start, end = config.shot_range(index)
        folder = os.path.join(out_root, f"shot{shot}")
        os.makedirs(folder, exist_ok=True)
        t0 = time.time()
        done = 0
        for frame in range(start, end + 1, step):
            path = os.path.join(folder, f"{frame - start:04d}.png")
            if not claim(path):
                continue
            scene.frame_set(frame)
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            done += 1
            elapsed = time.time() - t0
            print(f"[render] shot {shot} frame {frame - start + 1}/{end - start + 1} "
                  f"({elapsed / done:.1f}s per frame)", flush=True)
        print(f"[render] shot {shot} finished in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
