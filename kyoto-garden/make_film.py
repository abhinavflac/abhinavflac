"""Make the whole film with one Blender command: build the scene, render
every frame, synthesise the soundtrack and cut the four shots together with
dissolves, fades and sound. Only Blender is needed.

    blender -b -P kyoto-garden/make_film.py -- --quality final

Rendering is resumable: run the same command again after an interruption
and it continues from the frames already on disk.

Options (after the `--`):
  --quality draft|preview|final   detail level and render settings (default final)
  --shots 1,2,3,4                 render only some shots
  --skip-render                   only (re)make the soundtrack and the film from frames on disk
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
    p = argparse.ArgumentParser(prog="make_film.py")
    p.add_argument("--quality", default="final", choices=sorted(config.QUALITY))
    p.add_argument("--shots", default="1,2,3,4")
    p.add_argument("--skip-render", action="store_true")
    return p.parse_args(argv)


def cut_film(quality_name, frames_root, audio_path, out_path):
    """Lay the shots out in Blender's video editor with cross dissolves,
    a fade in and out, and the soundtrack, then write an MP4."""
    quality = config.QUALITY[quality_name]
    film = bpy.data.scenes.new("Film")
    film.render.resolution_x, film.render.resolution_y = quality["resolution"]
    film.render.resolution_percentage = 100
    film.render.fps = config.FPS
    film.view_settings.view_transform = 'Standard'   # frames are already graded
    film.view_settings.look = 'None'
    film.render.use_compositing = False
    film.render.use_sequencer = True
    editor = film.sequence_editor_create()
    strips = editor.strips

    start = 1
    previous = None
    shots = []
    for i, shot in enumerate(config.SHOTS):
        folder = os.path.join(frames_root, f"shot{i + 1}")
        files = sorted(f for f in os.listdir(folder)
                       if f.endswith(".png") and os.path.getsize(os.path.join(folder, f)) > 0)
        if len(files) < shot["length"]:
            raise RuntimeError(f"{folder} has {len(files)} finished frames, expected {shot['length']}; "
                               "run the same command again to finish rendering")
        strip = strips.new_image(f"Shot {i + 1}", os.path.join(folder, files[0]), 1 + i % 2, start,
                                 fit_method='FIT')
        for name in files[1:shot["length"]]:
            strip.elements.append(name)
        if previous is not None:
            strips.new_effect(f"Dissolve {i}", 'CROSS', 3, start, length=config.CROSSFADE,
                              input1=previous, input2=strip)
        shots.append(strip)
        previous = strip
        start += shot["length"] - config.CROSSFADE
    total = start + config.CROSSFADE - 1

    first, last = shots[0], shots[-1]
    first.blend_alpha = 0.0
    first.keyframe_insert("blend_alpha", frame=1)
    first.blend_alpha = 1.0
    first.keyframe_insert("blend_alpha", frame=1 + config.FADE_IN)
    last.blend_alpha = 1.0
    last.keyframe_insert("blend_alpha", frame=total - config.FADE_OUT)
    last.blend_alpha = 0.0
    last.keyframe_insert("blend_alpha", frame=total)

    if os.path.exists(audio_path):
        strips.new_sound("Soundtrack", audio_path, 5, 1)

    film.frame_start, film.frame_end = 1, total
    settings = film.render.image_settings
    settings.media_type = 'VIDEO'
    settings.file_format = 'FFMPEG'
    ff = film.render.ffmpeg
    ff.format = 'MPEG4'
    ff.codec = 'H264'
    ff.constant_rate_factor = 'HIGH'
    ff.ffmpeg_preset = 'GOOD'
    ff.audio_codec = 'AAC'
    ff.audio_bitrate = 192
    ff.audio_channels = 'STEREO'
    ff.audio_mixrate = 48000
    film.render.filepath = out_path
    bpy.ops.render.render(animation=True, scene=film.name)
    return out_path


def main():
    args = parse_args()
    frames_root = os.path.join(HERE, "renders", args.quality)
    if not args.skip_render:
        import build_scene
        from render_shots import render_frames
        t = time.time()
        scene = build_scene.build(args.quality, set())
        blend = os.path.join(HERE, "renders", f"garden_{args.quality}.blend")
        os.makedirs(os.path.dirname(blend), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
        print(f"[film] scene built in {time.time() - t:.0f}s", flush=True)
        shots = [int(s) for s in args.shots.split(",") if s.strip()]
        render_frames(scene, shots, frames_root)

    import sound
    audio = os.path.join(HERE, "renders", "soundtrack.wav")
    sound.write(audio, sound.build())
    print(f"[film] soundtrack written to {audio}", flush=True)

    out = os.path.join(HERE, "renders", f"kyoto_garden_{args.quality}.mp4")
    cut_film(args.quality, frames_root, audio, out)
    print(f"[film] finished: {out}", flush=True)


if __name__ == "__main__":
    main()
