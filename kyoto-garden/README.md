# Kyoto Garden

A 20-second, calm, game-style remake of a Kyoto temple garden in Blender: a
two-storey Zen pavilion over a koi pond, a bamboo grove with a spout, a maple
leaf falling onto the water, and the pavilion mirrored in the pond. Water is
in every shot.

Everything is generated from code. There are no downloaded models, textures
or sounds: the pavilion, rocks, lanterns, trees, bamboo, ferns, koi, birds,
sky, every material and the soundtrack are all made by the scripts here.

## Shots

| Time | Shot | Camera |
|---|---|---|
| 0:00–0:06 | Across the pond to the pavilion; koi glide by and one breaks the surface | Slow push forward, drifting down |
| 0:05–0:11 | Bamboo grove; the spout pours into the stream, a songbird on the pipe | Slow sideways glide |
| 0:10–0:15 | Close on the water as a maple leaf lands; ripples start on contact | Almost still, shallow focus |
| 0:14–0:20 | Low over the pond toward the pavilion and its reflection; a dove crosses; a bell rings; a breeze shimmers the water | Slow glide forward |

Shots overlap by 0.8 s for the dissolves.

## Requirements

- Blender 5.2 (tested with 5.2.2 LTS). EEVEE is used for rendering.
- A graphics card for the final render. A modern NVIDIA/AMD card renders the
  final film in roughly a few hours.
- Python 3 with numpy, and ffmpeg, for the soundtrack and final assembly.

## Making the film

Run these from the repository root.

```sh
# 1. Build the scene (saves kyoto-garden/renders/garden_final.blend)
blender -b -P kyoto-garden/build_scene.py -- --quality final

# 2. Render all four shots (resumable; run it again to continue)
blender -b kyoto-garden/renders/garden_final.blend -P kyoto-garden/render_shots.py

# 3. Make the soundtrack
python3 kyoto-garden/sound.py

# 4. Join shots, dissolves and sound into the film
python3 kyoto-garden/assemble.py --frames kyoto-garden/renders/final
```

The film is written to `kyoto-garden/renders/kyoto_garden.mp4`.

### Quicker checks

- `--quality draft` or `--quality preview` builds a lighter scene (fewer
  plants, fewer samples, lower resolution).
- `--still 4:2.5` renders a single frame from shot 4 at 2.5 seconds.
- `render_shots.py -- --engine BLENDER_WORKBENCH` renders a fast, flat-shaded
  animatic into `renders/animatic` for judging timing and camera moves.
- Open the `.blend` in Blender to look around; the timeline markers switch
  cameras between shots.

## Layout of the code

| File | What it makes |
|---|---|
| `garden/config.py` | Timing, shot lengths, quality presets |
| `garden/layout.py` | Positions of the pond, stream, island, pavilion and grove |
| `garden/terrain.py` | Ground with the pond basin, island and stream channel carved in |
| `garden/pavilion.py` | The two-storey pavilion, roofs, windows, screens and phoenix |
| `garden/water.py` | Pond, stream and spout water; ripple rings and wind on the water |
| `garden/props.py` | Rocks, stone lanterns, stepping stones, the bamboo spout |
| `garden/vegetation.py` | Pines, maples, bamboo, shrubs, ferns, grass, pampas, the wooded hill |
| `garden/creatures.py` | Koi, songbird, dove, the falling leaf |
| `garden/materials.py` | Every material, built from shader nodes |
| `garden/lighting.py` | Sky, clouds, sun, haze, render settings |
| `garden/cameras.py` | The four camera moves |
| `sound.py` | Synthesised soundtrack |
| `render_shots.py`, `assemble.py` | Rendering and assembly |
