"""Timing, shot list and quality presets shared by every builder."""

FPS = 30
CROSSFADE = 24  # frames two neighbouring shots overlap during a dissolve
FADE_IN = 18    # frames of fade from black at the very start
FADE_OUT = 36   # frames of fade to black at the very end

# Lengths include the dissolve handles, so the finished film runs
# sum(lengths) - CROSSFADE * (len(SHOTS) - 1) = 600 frames = 20 seconds.
SHOTS = [
    {"name": "pond", "length": 186},
    {"name": "bamboo", "length": 165},
    {"name": "leaf", "length": 150},
    {"name": "pavilion", "length": 171},
]

# Each shot lives in its own block of the timeline so animation for one shot
# never leaks into another.
SHOT_BLOCK = 200

WATER_LEVEL = 0.0

QUALITY = {
    # Quick stills for checking layout.
    "draft": {
        "resolution": (640, 360), "samples": 8, "density": 0.25,
        "volumetrics": False, "motion_blur": False, "raytracing": True,
        "shadow_scale": 0.5,
    },
    # Low-resolution animation for judging pacing and camera moves.
    "preview": {
        "resolution": (960, 540), "samples": 16, "density": 0.4,
        "volumetrics": False, "motion_blur": False, "raytracing": True,
        "shadow_scale": 0.5,
    },
    # Full quality, meant for a machine with a graphics card.
    "final": {
        "resolution": (1920, 1080), "samples": 64, "density": 1.0,
        "volumetrics": True, "motion_blur": True, "raytracing": True,
        "shadow_scale": 1.0,
    },
}


def shot_range(index):
    """First and last timeline frame of shot `index`."""
    start = 1 + index * SHOT_BLOCK
    return start, start + SHOTS[index]["length"] - 1


def shot_frame(index, seconds):
    """Timeline frame `seconds` into shot `index`."""
    return shot_range(index)[0] + round(seconds * FPS)


def shot_seconds(index, seconds):
    """Scene time in seconds of a moment `seconds` into shot `index`."""
    return (shot_frame(index, seconds) - 1) / FPS
