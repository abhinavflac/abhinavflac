"""Join the four rendered shots into the finished film with soft dissolves,
a fade in and out, and the soundtrack.

    python3 kyoto-garden/assemble.py --frames renders/final --out renders/kyoto_garden.mp4

Each shot folder (shot1 ... shot4) holds numbered PNG frames from
render_shots.py. If frames were rendered with --step N, pass the same --step
here and frames are held to keep the timing.
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from garden import config  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--frames", default=os.path.join(HERE, "renders", "final"))
    p.add_argument("--out", default=os.path.join(HERE, "renders", "kyoto_garden.mp4"))
    p.add_argument("--audio", default=os.path.join(HERE, "renders", "soundtrack.wav"))
    p.add_argument("--step", type=int, default=1)
    p.add_argument("--crf", type=int, default=16)
    args = p.parse_args()

    fps = config.FPS
    fade = config.CROSSFADE / fps
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for i in range(len(config.SHOTS)):
        cmd += ["-framerate", f"{fps / args.step}", "-pattern_type", "glob",
                "-i", os.path.join(args.frames, f"shot{i + 1}", "*.png")]
    has_audio = os.path.exists(args.audio)
    if has_audio:
        cmd += ["-i", args.audio]

    parts = []
    for i, shot in enumerate(config.SHOTS):
        seconds = shot["length"] / fps
        parts.append(f"[{i}:v]fps={fps},trim=duration={seconds:.4f},setpts=PTS-STARTPTS,format=yuv420p[s{i}]")
    offset = 0.0
    last = "s0"
    for i in range(1, len(config.SHOTS)):
        offset += config.SHOTS[i - 1]["length"] / fps - fade
        parts.append(f"[{last}][s{i}]xfade=transition=fade:duration={fade:.4f}:offset={offset:.4f}[x{i}]")
        last = f"x{i}"
    total = (sum(s["length"] for s in config.SHOTS) - (len(config.SHOTS) - 1) * config.CROSSFADE) / fps
    parts.append(f"[{last}]fade=t=in:st=0:d={config.FADE_IN / fps:.3f},"
                 f"fade=t=out:st={total - config.FADE_OUT / fps:.3f}:d={config.FADE_OUT / fps:.3f},"
                 f"vignette=angle=PI/6,format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]"]
    if has_audio:
        cmd += ["-map", f"{len(config.SHOTS)}:a", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-movflags", "+faststart",
            "-t", f"{total:.3f}", args.out]
    subprocess.run(cmd, check=True)
    print(f"wrote {args.out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
