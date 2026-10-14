"""Sky with drifting clouds, the sun, haze and render settings."""

import math

import bpy
from mathutils import Vector

from . import config, materials as M, util
from .materials import srgb

SUN_BEARING = 215.0    # degrees clockwise from north: a south-west afternoon sun
SUN_ELEVATION = 38.0   # degrees above the horizon
CLOUD_COVER = (0.57, 0.69)   # noise range over which clouds fade in; higher = fewer clouds
# Blender's physical sky is far brighter than the sun lamp's units; scale it so
# the sun-to-sky ratio is like a clear afternoon (roughly 20:1).
SKY_STRENGTH = 0.05


def sun_vector():
    b, e = math.radians(SUN_BEARING), math.radians(SUN_ELEVATION)
    return Vector((math.sin(b) * math.cos(e), math.cos(b) * math.cos(e), math.sin(e)))


def build_world(quality):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Garden Sky")
    scene.world = world
    world.color = (0.32, 0.5, 0.78)   # background for the Workbench animatic
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')

    sky = M.node(nt, 'ShaderNodeTexSky', sky_type='MULTIPLE_SCATTERING', sun_disc=False,
                 sun_elevation=math.radians(SUN_ELEVATION), sun_rotation=math.radians(SUN_BEARING),
                 altitude=60.0, air_density=1.0, aerosol_density=0.8, ozone_density=1.0)

    # Clouds: fractal noise projected onto a flat layer high above the garden.
    direction = M.coords(nt).outputs['Generated']
    dx, dy, dz = M.separate(nt, direction)
    lift = M.math(nt, 'MAXIMUM', dz, 0.035)
    time = M.node(nt, 'ShaderNodeValue')
    util.time_driver(time.outputs[0])
    px = M.math(nt, 'ADD', M.math(nt, 'DIVIDE', dx, lift), M.math(nt, 'MULTIPLY', time.outputs[0], 0.006))
    py = M.math(nt, 'DIVIDE', dy, lift)
    layer = M.combine(nt, px, py, 0.0)
    puffs = M.noise(nt, layer, 1.1, detail=9.0, rough=0.62, dims='4D', w=M.math(nt, 'MULTIPLY', time.outputs[0], 0.01))
    masses = M.noise(nt, layer, 0.28, detail=2.0)
    shape = M.math(nt, 'ADD', puffs.outputs[0], M.math(nt, 'MULTIPLY', M.math(nt, 'SUBTRACT', masses.outputs[0], 0.5), 0.55))
    density = M.maprange(nt, shape, CLOUD_COVER[0], CLOUD_COVER[1])
    horizon = M.maprange(nt, dz, 0.02, 0.22)
    cover = M.math(nt, 'MULTIPLY', density, horizon)
    thick = M.maprange(nt, shape, CLOUD_COVER[1], CLOUD_COVER[1] + 0.2)
    # Sunlit tops are several times brighter than the blue sky; thick bases go grey.
    lit_scale = M.node(nt, 'ShaderNodeVectorMath', operation='SCALE')
    M.plug(nt, M.mix(nt, thick, srgb('#ffffff'), srgb('#aab3c0')), lit_scale.inputs[0])
    M.plug(nt, M.maprange(nt, thick, 0.0, 1.0, 1.5, 0.55), lit_scale.inputs[3])
    sky_col = M.node(nt, 'ShaderNodeVectorMath', operation='SCALE')
    M.plug(nt, sky.outputs[0], sky_col.inputs[0])
    M.plug(nt, SKY_STRENGTH, sky_col.inputs[3])
    color = M.mix(nt, cover, sky_col.outputs[0], lit_scale.outputs[0])
    bg = M.node(nt, 'ShaderNodeBackground', inputs={'Color': color, 'Strength': 1.0})
    M.plug(nt, bg, out.inputs['Surface'])

    return world


def build_haze(coll):
    """Light atmospheric haze in a large box around the garden. EEVEE treats a
    world volume as infinitely deep, which blocks all sun and sky light, so
    the haze must be a bounded object instead."""
    mat, nt, out = M.new_material("Haze")
    haze = M.node(nt, 'ShaderNodeVolumePrincipled', inputs={
        'Color': srgb('#dfe6ee'), 'Density': 0.0016, 'Anisotropy': 0.55})
    M.plug(nt, haze, out.inputs['Volume'])
    M.set_display_color(mat, '#dfe6ee')
    mb = util.MeshBuilder()
    mb.box((-70.0, -60.0, -5.0), (90.0, 90.0, 60.0))
    obj = mb.to_object("Haze", coll, [mat])
    obj.display_type = 'BOUNDS'
    obj.visible_shadow = False
    return obj


def build_sun(coll):
    light = bpy.data.lights.new("Sun", 'SUN')
    light.energy = 5.0
    light.angle = math.radians(0.8)
    light.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("Sun", light)
    sun.rotation_euler = (-sun_vector()).to_track_quat('-Z', 'Y').to_euler()
    coll.objects.link(sun)
    return sun


def _set(obj, attr, value):
    if hasattr(obj, attr):
        setattr(obj, attr, value)
    else:
        print(f"[garden] setting {attr} is not available in this Blender version")


def configure_render(quality):
    scene = bpy.context.scene
    render = scene.render
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'BLENDER_EEVEE_NEXT'
    render.resolution_x, render.resolution_y = quality["resolution"]
    render.resolution_percentage = 100
    render.fps = config.FPS
    render.use_motion_blur = quality["motion_blur"]
    render.motion_blur_shutter = 0.5
    render.film_transparent = False
    render.image_settings.file_format = 'PNG'
    render.image_settings.color_depth = '8'
    render.image_settings.compression = 15

    ee = scene.eevee
    _set(ee, "taa_render_samples", quality["samples"])
    _set(ee, "use_raytracing", quality["raytracing"])
    _set(ee, "ray_tracing_method", 'SCREEN')
    _set(ee, "use_fast_gi", True)
    _set(ee, "fast_gi_method", 'GLOBAL_ILLUMINATION')
    _set(ee, "fast_gi_distance", 2.0)
    _set(ee, "use_shadows", True)
    _set(ee, "shadow_ray_count", 2 if quality["samples"] >= 32 else 1)
    _set(ee, "shadow_step_count", 8)
    _set(ee, "shadow_resolution_scale", quality["shadow_scale"])
    _set(ee, "use_volumetric_shadows", quality["volumetrics"])
    _set(ee, "volumetric_tile_size", '8')
    _set(ee, "volumetric_end", 120.0)
    _set(ee, "bokeh_max_size", 60.0)

    view = scene.view_settings
    view.view_transform = 'AgX'
    view.look = 'AgX - Medium High Contrast'
    view.exposure = 0.0
    view.gamma = 1.0
