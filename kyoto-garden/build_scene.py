"""Build the Kyoto garden scene from scratch inside Blender.

    blender -b -P kyoto-garden/build_scene.py -- --quality preview
    blender -b -P kyoto-garden/build_scene.py -- --quality draft --still 1:2.0 --still 4:3.0

Options (after the `--`):
  --quality draft|preview|final   detail level and render settings (default preview)
  --save PATH                     where to write the .blend (default renders/garden_<quality>.blend)
  --still SHOT:SECONDS            render a still from a shot (1-4) at a moment; repeatable
  --out DIR                       folder for stills (default renders/stills)
  --skip NAMES                    comma-separated parts to leave out while testing
                                  (vegetation, props, creatures)
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
    p = argparse.ArgumentParser(prog="build_scene.py")
    p.add_argument("--quality", default="preview", choices=sorted(config.QUALITY))
    p.add_argument("--save", default=None)
    p.add_argument("--still", action="append", default=[])
    p.add_argument("--out", default=os.path.join(HERE, "renders", "stills"))
    p.add_argument("--skip", default="")
    return p.parse_args(argv)


def build(quality_name, skip):
    from garden import cameras, lighting, pavilion, terrain, util, water

    quality = config.QUALITY[quality_name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Kyoto Garden"
    scene["quality"] = quality_name
    scene.frame_start = 1
    scene.frame_end = config.shot_range(len(config.SHOTS) - 1)[1]

    steps = []

    def step(label, fn, *args):
        t = time.time()
        result = fn(*args)
        steps.append((label, time.time() - t))
        print(f"[garden] {label}: {time.time() - t:.1f}s", flush=True)
        return result

    lighting.configure_render(quality)
    step("sky", lighting.build_world, quality)
    step("sun", lighting.build_sun, util.collection("Lighting"))
    if quality["volumetrics"]:
        step("haze", lighting.build_haze, util.collection("Lighting"))
    step("terrain", terrain.build, util.collection("Terrain"))
    step("pavilion", pavilion.build, util.collection("Pavilion"))
    if "props" not in skip:
        from garden import props
        step("props", props.build, util.collection("Props"), quality)
    if "vegetation" not in skip:
        from garden import vegetation
        step("vegetation", vegetation.build, util.collection("Vegetation"), quality)
    if "creatures" not in skip:
        from garden import creatures
        step("creatures", creatures.build, util.collection("Creatures"))
    step("water", water.build, util.collection("Water"))
    step("cameras", cameras.build, util.collection("Cameras"))
    return scene


def render_still(scene, shot, seconds, out_dir, quality_name):
    index = shot - 1
    cam = [m for m in scene.timeline_markers if m.name == config.SHOTS[index]["name"]][0].camera
    scene.camera = cam
    scene.frame_set(config.shot_frame(index, seconds))
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, f"{quality_name}_shot{shot}_{seconds:.1f}s.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[garden] still shot {shot} at {seconds}s: {time.time() - t:.1f}s -> {scene.render.filepath}", flush=True)


def main():
    args = parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    scene = build(args.quality, skip)
    save = args.save or os.path.join(HERE, "renders", f"garden_{args.quality}.blend")
    os.makedirs(os.path.dirname(save), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=save, compress=True)
    print(f"[garden] saved {save}", flush=True)
    for spec in args.still:
        shot, seconds = spec.split(":")
        render_still(scene, int(shot), float(seconds), args.out, args.quality)


if __name__ == "__main__":
    main()
