"""Procedural materials. Every texture is built from shader nodes; the scene
uses no image files."""

import bpy

_cache = {}
_shared_nodes = {}


# ---------------------------------------------------------------- colour

def srgb(hex_code):
    """'#rrggbb' to a linear RGB tuple."""
    h = hex_code.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def scale_color(color, k):
    return tuple(min(c * k, 1.0) for c in color)


# ---------------------------------------------------------------- node helpers

def out_socket(n):
    for s in n.outputs:
        if s.enabled:
            return s
    return n.outputs[0]


def plug(nt, src, dst):
    if isinstance(src, bpy.types.NodeSocket):
        nt.links.new(src, dst)
    elif isinstance(src, bpy.types.Node):
        nt.links.new(out_socket(src), dst)
    else:
        cur = dst.default_value
        if hasattr(cur, '__len__'):
            val = tuple(src) if hasattr(src, '__len__') else (src,) * len(cur)
            if len(val) == 3 and len(cur) == 4:
                val = (*val, 1.0)
            dst.default_value = val
        else:
            dst.default_value = src


def node(nt, kind, inputs=None, **attrs):
    n = nt.nodes.new(kind)
    for key, value in attrs.items():
        setattr(n, key, value)
    for key, value in (inputs or {}).items():
        plug(nt, value, n.inputs[key])
    return n


def math(nt, op, a, b=None, c=None, clamp=False):
    n = node(nt, 'ShaderNodeMath', operation=op, use_clamp=clamp)
    plug(nt, a, n.inputs[0])
    if b is not None:
        plug(nt, b, n.inputs[1])
    if c is not None:
        plug(nt, c, n.inputs[2])
    return n.outputs[0]


def vmath(nt, op, a, b=None, scale=None):
    n = node(nt, 'ShaderNodeVectorMath', operation=op)
    plug(nt, a, n.inputs[0])
    if b is not None:
        plug(nt, b, n.inputs[1])
    if scale is not None:
        plug(nt, scale, n.inputs[3])
    if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE'):
        return n.outputs[1]
    return n.outputs[0]


def mix(nt, fac, a, b, blend='MIX'):
    n = node(nt, 'ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_factor=True)
    plug(nt, fac, n.inputs[0])
    plug(nt, a, n.inputs[6])
    plug(nt, b, n.inputs[7])
    return n.outputs[2]


def mixf(nt, fac, a, b):
    n = node(nt, 'ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
    plug(nt, fac, n.inputs[0])
    plug(nt, a, n.inputs[2])
    plug(nt, b, n.inputs[3])
    return n.outputs[0]


def ramp(nt, fac, stops, interpolation='LINEAR'):
    n = node(nt, 'ShaderNodeValToRGB')
    n.color_ramp.interpolation = interpolation
    elements = n.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for el, (pos, color) in zip(elements, stops):
        el.position = pos
        el.color = (*color, 1.0) if len(color) == 3 else color
    plug(nt, fac, n.inputs[0])
    return n.outputs[0]


def maprange(nt, value, a, b, c=0.0, d=1.0, clamp=True, interpolation='LINEAR'):
    n = node(nt, 'ShaderNodeMapRange', clamp=clamp, interpolation_type=interpolation)
    for i, v in enumerate((value, a, b, c, d)):
        plug(nt, v, n.inputs[i])
    return n.outputs[0]


def noise(nt, vec, scale, detail=3.0, rough=0.5, dims='3D', w=None, distortion=0.0):
    n = node(nt, 'ShaderNodeTexNoise', noise_dimensions=dims)
    plug(nt, vec, n.inputs['Vector'])
    plug(nt, scale, n.inputs['Scale'])
    plug(nt, detail, n.inputs['Detail'])
    plug(nt, rough, n.inputs['Roughness'])
    if 'Distortion' in n.inputs:
        plug(nt, distortion, n.inputs['Distortion'])
    if w is not None:
        plug(nt, w, n.inputs['W'])
    return n


def voronoi(nt, vec, scale, feature='F1', dims='3D', randomness=1.0):
    n = node(nt, 'ShaderNodeTexVoronoi', voronoi_dimensions=dims, feature=feature)
    plug(nt, vec, n.inputs['Vector'])
    plug(nt, scale, n.inputs['Scale'])
    plug(nt, randomness, n.inputs['Randomness'])
    return n


def wave(nt, vec, scale, distortion=0.0, detail=2.0, direction='X', profile='SIN'):
    n = node(nt, 'ShaderNodeTexWave', wave_type='BANDS', bands_direction=direction,
             wave_profile=profile)
    plug(nt, vec, n.inputs['Vector'])
    plug(nt, scale, n.inputs['Scale'])
    plug(nt, distortion, n.inputs['Distortion'])
    plug(nt, detail, n.inputs['Detail'])
    return n


def bump(nt, height, strength=1.0, distance=1.0, normal=None):
    n = node(nt, 'ShaderNodeBump', inputs={'Strength': strength, 'Distance': distance, 'Height': height})
    if normal is not None:
        plug(nt, normal, n.inputs['Normal'])
    return n.outputs[0]


def shared(nt, kind):
    key = (nt.as_pointer(), kind)
    if key not in _shared_nodes:
        _shared_nodes[key] = nt.nodes.new(kind)
    return _shared_nodes[key]


def coords(nt):
    return shared(nt, 'ShaderNodeTexCoord')


def geometry(nt):
    return shared(nt, 'ShaderNodeNewGeometry')


def object_random(nt):
    return shared(nt, 'ShaderNodeObjectInfo').outputs['Random']


def separate(nt, vec):
    n = node(nt, 'ShaderNodeSeparateXYZ')
    plug(nt, vec, n.inputs[0])
    return n.outputs


def combine(nt, x, y, z):
    n = node(nt, 'ShaderNodeCombineXYZ')
    for i, v in enumerate((x, y, z)):
        plug(nt, v, n.inputs[i])
    return n.outputs[0]


def attribute(nt, name):
    return node(nt, 'ShaderNodeAttribute', attribute_name=name).outputs['Factor']


def principled(nt, color, rough=0.5, normal=None, **extra):
    inputs = {'Base Color': color, 'Roughness': rough}
    if normal is not None:
        inputs['Normal'] = normal
    for key, value in extra.items():
        inputs[key.replace('_', ' ')] = value
    return node(nt, 'ShaderNodeBsdfPrincipled', inputs=inputs)


def mix_shader(nt, fac, a, b):
    n = node(nt, 'ShaderNodeMixShader')
    plug(nt, fac, n.inputs[0])
    plug(nt, a, n.inputs[1])
    plug(nt, b, n.inputs[2])
    return n


def new_material(name):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    output = nt.nodes.new('ShaderNodeOutputMaterial')
    return mat, nt, output


def finish(nt, output, shader):
    plug(nt, shader, output.inputs['Surface'])


def with_translucency(nt, bsdf, color, amount):
    """Mix in light passing through thin surfaces such as leaves and paper."""
    trans = node(nt, 'ShaderNodeBsdfTranslucent', inputs={'Color': color})
    return mix_shader(nt, amount, bsdf, trans)


# ---------------------------------------------------------------- registry

def get(name):
    if name not in _cache:
        _cache[name] = BUILDERS[name]()
    return _cache[name]


# ---------------------------------------------------------------- wood

def _wood(name, tones, weather):
    mat, nt, out = new_material(name)
    uv = coords(nt).outputs['UV']
    obj = coords(nt).outputs['Object']
    grain_vec = vmath(nt, 'MULTIPLY', uv, (1.5, 28.0, 1.0))
    grain = noise(nt, grain_vec, 1.0, detail=7.0, rough=0.6)
    lines = wave(nt, vmath(nt, 'MULTIPLY', uv, (0.6, 1.0, 1.0)), 55.0, distortion=7.0, detail=3.0,
                 direction='Y', profile='SAW')
    fac = math(nt, 'ADD', math(nt, 'MULTIPLY', grain.outputs[0], 0.7), math(nt, 'MULTIPLY', lines.outputs[1], 0.3))
    color = ramp(nt, fac, [(0.25, tones[0]), (0.55, tones[1]), (0.85, tones[2])])
    stain = noise(nt, obj, 1.3, detail=4.0)
    color = mix(nt, maprange(nt, stain.outputs[0], 0.45, 0.75, 0.0, weather), color, srgb('#5d5650'))
    rough = maprange(nt, grain.outputs[0], 0.3, 0.7, 0.55, 0.8)
    normal = bump(nt, fac, strength=0.25, distance=0.01)
    return mat, nt, out, color, rough, normal, uv


def wood_dark():
    mat, nt, out, color, rough, normal, _ = _wood(
        "Wood Dark", (srgb('#20160f'), srgb('#352519'), srgb('#4a3424')), 0.15)
    finish(nt, out, principled(nt, color, rough, normal))
    return mat


def wood_light():
    mat, nt, out, color, rough, normal, _ = _wood(
        "Wood Light", (srgb('#6a4f35'), srgb('#856546'), srgb('#9d7f5e')), 0.2)
    finish(nt, out, principled(nt, color, rough, normal))
    return mat


def wood_boards():
    mat, nt, out, color, rough, normal, uv = _wood(
        "Wood Boards", (srgb('#24190f'), srgb('#3a2a1c'), srgb('#4f3a28')), 0.18)
    v = separate(nt, uv)[1]
    seam = math(nt, 'FRACT', math(nt, 'DIVIDE', v, 0.23))
    gap = maprange(nt, seam, 0.0, 0.025, 1.0, 0.0)
    color = mix(nt, math(nt, 'MULTIPLY', gap, 0.8), color, srgb('#0e0906'))
    normal = bump(nt, math(nt, 'SUBTRACT', 1.0, gap), strength=0.4, distance=0.01, normal=normal)
    finish(nt, out, principled(nt, color, rough, normal))
    return mat


# ---------------------------------------------------------------- walls

def plaster():
    mat, nt, out = new_material("Plaster")
    obj = coords(nt).outputs['Object']
    n = noise(nt, obj, 6.0, detail=5.0)
    color = ramp(nt, n.outputs[0], [(0.3, srgb('#cbc4b4')), (0.7, srgb('#ddd7ca'))])
    fine = noise(nt, obj, 60.0, detail=3.0)
    finish(nt, out, principled(nt, color, 0.92, bump(nt, fine.outputs[0], 0.08, 0.01)))
    return mat


def shoji():
    mat, nt, out = new_material("Shoji Paper")
    obj = coords(nt).outputs['Object']
    fibre = noise(nt, vmath(nt, 'MULTIPLY', obj, (1.0, 1.0, 6.0)), 90.0, detail=4.0)
    color = ramp(nt, fibre.outputs[0], [(0.35, srgb('#e3dccb')), (0.65, srgb('#efe9da'))])
    bsdf = principled(nt, color, 0.9, bump(nt, fibre.outputs[0], 0.05, 0.01))
    finish(nt, out, with_translucency(nt, bsdf, srgb('#f6eedb'), 0.35))
    return mat


# ---------------------------------------------------------------- roof

def roof():
    mat, nt, out = new_material("Roof Shingles")
    uv = coords(nt).outputs['UV']
    obj = coords(nt).outputs['Object']
    bricks = node(nt, 'ShaderNodeTexBrick', offset=0.5, offset_frequency=2, inputs={
        'Vector': uv, 'Scale': 1.0, 'Brick Width': 0.17, 'Row Height': 0.032,
        'Mortar Size': 0.0015, 'Mortar Smooth': 0.4, 'Bias': 0.0,
        'Color1': srgb('#3b312a'), 'Color2': srgb('#272019'), 'Mortar': srgb('#100c09')})
    v = separate(nt, uv)[1]
    saw = math(nt, 'FRACT', math(nt, 'DIVIDE', v, 0.032))
    grain = noise(nt, vmath(nt, 'MULTIPLY', uv, (1.0, 20.0, 1.0)), 30.0, detail=4.0)
    weather = noise(nt, obj, 0.7, detail=4.0)
    lichen = noise(nt, obj, 3.5, detail=5.0)
    color = mix(nt, math(nt, 'MULTIPLY', grain.outputs[0], 0.3), bricks.outputs[0], srgb('#4a4038'), 'OVERLAY')
    color = mix(nt, maprange(nt, weather.outputs[0], 0.4, 0.7, 0.0, 0.45), color, srgb('#5c5650'))
    color = mix(nt, maprange(nt, lichen.outputs[0], 0.62, 0.72, 0.0, 0.5), color, srgb('#59613a'))
    height = math(nt, 'ADD', math(nt, 'MULTIPLY', saw, 0.7), math(nt, 'MULTIPLY', bricks.outputs[1], 0.3))
    height = math(nt, 'ADD', height, math(nt, 'MULTIPLY', grain.outputs[0], 0.2))
    finish(nt, out, principled(nt, color, 0.82, bump(nt, height, 0.5, 0.01)))
    return mat


def bronze():
    mat, nt, out = new_material("Bronze")
    obj = coords(nt).outputs['Object']
    n = noise(nt, obj, 7.0, detail=5.0)
    metal = principled(nt, srgb('#6b4a2a'), 0.38, Metallic=1.0)
    patina = principled(nt, srgb('#4a7563'), 0.75)
    finish(nt, out, mix_shader(nt, maprange(nt, n.outputs[0], 0.45, 0.65, 0.0, 0.75), metal, patina))
    return mat


# ---------------------------------------------------------------- stone

def _moss_mask(nt, obj, threshold=0.45):
    up = separate(nt, geometry(nt).outputs['Normal'])[2]
    patches = noise(nt, obj, 2.5, detail=5.0)
    mask = math(nt, 'MULTIPLY', maprange(nt, up, threshold, threshold + 0.35),
                maprange(nt, patches.outputs[0], 0.38, 0.62))
    return mask


def granite():
    mat, nt, out = new_material("Granite")
    obj = coords(nt).outputs['Object']
    base = noise(nt, obj, 3.0, detail=6.0)
    color = ramp(nt, base.outputs[0], [(0.3, srgb('#5f5b54')), (0.55, srgb('#76716a')), (0.8, srgb('#8a857b'))])
    speck = voronoi(nt, obj, 160.0)
    speck_fac = separate(nt, speck.outputs['Color'])[0]
    color = mix(nt, maprange(nt, speck_fac, 0.85, 0.9), color, srgb('#35322e'))
    color = mix(nt, maprange(nt, speck_fac, 0.08, 0.03), color, srgb('#d5d1c6'))
    lichen = noise(nt, obj, 9.0, detail=4.0)
    color = mix(nt, maprange(nt, lichen.outputs[0], 0.66, 0.74, 0.0, 0.7), color, srgb('#c7c4ad'))
    moss = _moss_mask(nt, obj, 0.5)
    moss_col = ramp(nt, noise(nt, obj, 30.0).outputs[0], [(0.3, srgb('#33461a')), (0.7, srgb('#5d7426'))])
    color = mix(nt, moss, color, moss_col)
    height = math(nt, 'ADD', base.outputs[0], math(nt, 'MULTIPLY', moss, 0.6))
    normal = bump(nt, noise(nt, obj, 40.0, detail=6.0).outputs[0], 0.25, 0.01)
    normal = bump(nt, height, 0.3, 0.02, normal)
    finish(nt, out, principled(nt, color, maprange(nt, moss, 0, 1, 0.7, 0.9), normal))
    return mat


def rock():
    mat, nt, out = new_material("Garden Rock")
    obj = coords(nt).outputs['Object']
    world_z = separate(nt, geometry(nt).outputs['Position'])[2]
    strata = wave(nt, obj, 2.2, distortion=4.0, detail=4.0, direction='Z')
    base = noise(nt, obj, 1.6, detail=8.0, rough=0.6)
    fac = math(nt, 'ADD', math(nt, 'MULTIPLY', base.outputs[0], 0.75), math(nt, 'MULTIPLY', strata.outputs[1], 0.25))
    color = ramp(nt, fac, [(0.3, srgb('#3d3a35')), (0.5, srgb('#58534b')), (0.7, srgb('#6f695e')), (0.85, srgb('#857d70'))])
    cracks = voronoi(nt, obj, 2.5, feature='DISTANCE_TO_EDGE')
    crack = maprange(nt, cracks.outputs['Distance'], 0.0, 0.035, 1.0, 0.0)
    color = mix(nt, math(nt, 'MULTIPLY', crack, 0.7), color, srgb('#1d1b18'))
    lichen = noise(nt, obj, 6.0, detail=4.0)
    color = mix(nt, maprange(nt, lichen.outputs[0], 0.68, 0.76, 0.0, 0.6), color, srgb('#b9b49c'))
    moss = _moss_mask(nt, obj, 0.35)
    moss_col = ramp(nt, noise(nt, obj, 25.0, detail=4.0).outputs[0],
                    [(0.3, srgb('#2c3f12')), (0.6, srgb('#4f6a1e')), (0.8, srgb('#6c8227'))])
    color = mix(nt, moss, color, moss_col)
    wet = maprange(nt, world_z, 0.08, 0.0)
    color = mix(nt, math(nt, 'MULTIPLY', wet, 0.6), color, (0.0, 0.0, 0.0))
    rough = mixf(nt, wet, maprange(nt, moss, 0, 1, 0.75, 0.9), 0.3)
    fine = noise(nt, obj, 22.0, detail=8.0, rough=0.65)
    height = math(nt, 'ADD', math(nt, 'MULTIPLY', fine.outputs[0], 0.5), math(nt, 'MULTIPLY', crack, -0.6))
    height = math(nt, 'ADD', height, math(nt, 'MULTIPLY', moss, 0.5))
    normal = bump(nt, height, 0.45, 0.02)
    finish(nt, out, principled(nt, color, rough, normal))
    return mat


# ---------------------------------------------------------------- ground

def terrain():
    mat, nt, out = new_material("Terrain")
    pos = geometry(nt).outputs['Position']
    z = separate(nt, pos)[2]
    gravel_mask = attribute(nt, "gravel")

    # Moss carpet with cushions and colour drift.
    drift = noise(nt, pos, 0.25, detail=4.0)
    moss_col = ramp(nt, drift.outputs[0], [(0.25, srgb('#1c300a')), (0.5, srgb('#2c4710')), (0.75, srgb('#45631a'))])
    patches = noise(nt, pos, 1.3, detail=6.0)
    moss_col = mix(nt, maprange(nt, patches.outputs[0], 0.35, 0.65, 0.0, 0.5), moss_col, srgb('#5a6e22'))
    cushions = voronoi(nt, pos, 16.0)
    fine = noise(nt, pos, 90.0, detail=3.0)
    moss_col = mix(nt, math(nt, 'MULTIPLY', fine.outputs[0], 0.35), moss_col, srgb('#7f9a32'), 'OVERLAY')
    soil = noise(nt, pos, 0.4, detail=5.0)
    soil_mask = maprange(nt, soil.outputs[0], 0.62, 0.7, 0.0, 0.85)
    color = mix(nt, soil_mask, moss_col, srgb('#4a3a28'))
    moss_height = math(nt, 'SUBTRACT', 1.0, cushions.outputs['Distance'])

    # Beyond the tended garden and in the bamboo grove: dark leaf litter.
    px, py, _ = separate(nt, pos)
    garden = vmath(nt, 'LENGTH', combine(nt, math(nt, 'DIVIDE', math(nt, 'SUBTRACT', px, 1.0), 27.0),
                                         math(nt, 'DIVIDE', math(nt, 'SUBTRACT', py, -0.5), 19.0), 0.0))
    grove = vmath(nt, 'LENGTH', combine(nt, math(nt, 'DIVIDE', math(nt, 'SUBTRACT', px, 27.0), 14.0),
                                        math(nt, 'DIVIDE', math(nt, 'SUBTRACT', py, 19.0), 12.0), 0.0))
    wild = math(nt, 'MAXIMUM', maprange(nt, garden, 0.8, 1.15), maprange(nt, grove, 1.05, 0.75))
    litter = noise(nt, pos, 3.0, detail=6.0)
    litter_col = ramp(nt, litter.outputs[0], [(0.25, srgb('#211d12')), (0.5, srgb('#3a3220')), (0.75, srgb('#5a4a2c'))])
    litter_col = mix(nt, maprange(nt, noise(nt, pos, 0.6, detail=3.0).outputs[0], 0.5, 0.7, 0.0, 0.6), litter_col, srgb('#33461a'))
    color = mix(nt, wild, color, litter_col)
    moss_height = mixf(nt, wild, moss_height, litter.outputs[0])

    # Raked gravel.
    pebbles = voronoi(nt, pos, 70.0)
    pebble_tone = separate(nt, pebbles.outputs['Color'])[0]
    gravel_col = ramp(nt, pebble_tone, [(0.0, srgb('#8f8775')), (0.5, srgb('#b3aa96')), (1.0, srgb('#cbc3b0'))])
    y = separate(nt, pos)[1]
    rake = math(nt, 'SINE', math(nt, 'MULTIPLY', y, 52.0))
    gravel_height = math(nt, 'ADD', math(nt, 'MULTIPLY', rake, 0.3),
                         math(nt, 'MULTIPLY', pebbles.outputs['Distance'], -0.6))
    color = mix(nt, gravel_mask, color, gravel_col)

    # Pond bed: mud fading into the dark with depth, pebbles at the margin.
    depth = math(nt, 'MULTIPLY', z, -1.0)
    mud = ramp(nt, noise(nt, pos, 1.5, detail=4.0).outputs[0], [(0.3, srgb('#2a2416')), (0.7, srgb('#3a321f'))])
    mud = mix(nt, maprange(nt, depth, 0.0, 0.5), mud, srgb('#0b110b'))
    shore_peb = voronoi(nt, pos, 18.0)
    peb_col = ramp(nt, separate(nt, shore_peb.outputs['Color'])[0],
                   [(0.0, srgb('#3a352d')), (0.6, srgb('#5a5245')), (1.0, srgb('#6e675a'))])
    margin = math(nt, 'MULTIPLY', maprange(nt, z, 0.12, 0.02), maprange(nt, z, -0.2, -0.05))
    under = maprange(nt, z, 0.02, -0.06)
    color = mix(nt, margin, color, peb_col)
    color = mix(nt, under, color, mud)
    wet = maprange(nt, z, 0.12, 0.0)
    color = mix(nt, math(nt, 'MULTIPLY', wet, 0.45), color, (0.0, 0.0, 0.0))

    rough = mixf(nt, gravel_mask, 0.88, 0.75)
    rough = mixf(nt, math(nt, 'MAXIMUM', wet, under), rough, 0.35)
    height = mixf(nt, gravel_mask, math(nt, 'ADD', moss_height, math(nt, 'MULTIPLY', fine.outputs[0], 0.4)), gravel_height)
    height = mixf(nt, margin, height, math(nt, 'SUBTRACT', 1.0, shore_peb.outputs['Distance']))
    normal = bump(nt, height, 0.35, 0.02)
    sheen = math(nt, 'MULTIPLY', math(nt, 'SUBTRACT', 1.0, gravel_mask), math(nt, 'SUBTRACT', 1.0, wet))
    sheen = math(nt, 'MULTIPLY', sheen, math(nt, 'SUBTRACT', 1.0, wild))
    finish(nt, out, principled(nt, color, rough, normal, Sheen_Weight=math(nt, 'MULTIPLY', sheen, 0.15),
                               Sheen_Tint=srgb('#b9c98a')))
    return mat


# ---------------------------------------------------------------- bark & bamboo

def bark_pine():
    mat, nt, out = new_material("Bark Pine")
    uv = coords(nt).outputs['UV']
    plates = voronoi(nt, vmath(nt, 'MULTIPLY', uv, (1.8, 0.8, 1.0)), 9.0, feature='DISTANCE_TO_EDGE')
    cells = voronoi(nt, vmath(nt, 'MULTIPLY', uv, (1.8, 0.8, 1.0)), 9.0)
    tone = separate(nt, cells.outputs['Color'])[0]
    color = ramp(nt, tone, [(0.0, srgb('#4f3326')), (0.5, srgb('#6e4a37')), (1.0, srgb('#83614c'))])
    crack = maprange(nt, plates.outputs['Distance'], 0.0, 0.06, 1.0, 0.0)
    flakes = noise(nt, vmath(nt, 'MULTIPLY', uv, (3.0, 1.0, 1.0)), 30.0, detail=6.0)
    color = mix(nt, math(nt, 'MULTIPLY', flakes.outputs[0], 0.4), color, srgb('#8f7d6c'), 'OVERLAY')
    color = mix(nt, crack, color, srgb('#1a120d'))
    height = math(nt, 'ADD', math(nt, 'MULTIPLY', crack, -1.0), math(nt, 'MULTIPLY', flakes.outputs[0], 0.3))
    finish(nt, out, principled(nt, color, 0.88, bump(nt, height, 0.7, 0.02)))
    return mat


def bark_smooth():
    mat, nt, out = new_material("Bark Smooth")
    uv = coords(nt).outputs['UV']
    base = noise(nt, vmath(nt, 'MULTIPLY', uv, (2.0, 0.6, 1.0)), 6.0, detail=5.0)
    color = ramp(nt, base.outputs[0], [(0.3, srgb('#4a463e')), (0.6, srgb('#625d53')), (0.8, srgb('#77715f'))])
    lenticel = noise(nt, vmath(nt, 'MULTIPLY', uv, (40.0, 3.0, 1.0)), 4.0, detail=2.0)
    color = mix(nt, maprange(nt, lenticel.outputs[0], 0.62, 0.7, 0.0, 0.5), color, srgb('#2e2a24'))
    lichen = noise(nt, uv, 5.0, detail=4.0)
    color = mix(nt, maprange(nt, lichen.outputs[0], 0.62, 0.72, 0.0, 0.6), color, srgb('#7f8a62'))
    finish(nt, out, principled(nt, color, 0.75, bump(nt, base.outputs[0], 0.2, 0.01)))
    return mat


def bamboo():
    mat, nt, out = new_material("Bamboo Culm")
    uv = coords(nt).outputs['UV']
    u, v, _ = separate(nt, uv)
    color = ramp(nt, object_random(nt), [(0.0, srgb('#2f4a17')), (0.45, srgb('#3d5a1c')),
                                         (0.75, srgb('#4f6a22')), (1.0, srgb('#6b7a30'))])
    streak = noise(nt, combine(nt, math(nt, 'MULTIPLY', u, 25.0), math(nt, 'MULTIPLY', v, 0.3), 0.0), 3.0, detail=3.0)
    color = mix(nt, math(nt, 'MULTIPLY', streak.outputs[0], 0.35), color, srgb('#a8ac6a'), 'OVERLAY')
    fr = math(nt, 'FRACT', v)
    powder = maprange(nt, fr, 0.0, 0.12, 0.55, 0.0)
    color = mix(nt, powder, color, srgb('#c4c9a4'))
    ring = math(nt, 'MAXIMUM', maprange(nt, fr, 0.975, 1.0), maprange(nt, fr, 0.012, 0.0))
    color = mix(nt, math(nt, 'MULTIPLY', ring, 0.6), color, srgb('#3d4a1c'))
    finish(nt, out, principled(nt, color, 0.32, bump(nt, ring, 0.2, 0.01), Coat_Weight=0.25))
    return mat


# ---------------------------------------------------------------- foliage

def foliage(name, colors, translucency=0.35, rough=0.5, vein_lobes=0.0, tip_color=None):
    """Leaf material whose colour varies per instance. `colors` is a list of
    hex codes spread across the per-instance random value."""
    mat, nt, out = new_material(name)
    uv = coords(nt).outputs['UV']
    stops = [(i / max(len(colors) - 1, 1), srgb(c)) for i, c in enumerate(colors)]
    color = ramp(nt, object_random(nt), stops)
    obj = coords(nt).outputs['Object']
    blotch = noise(nt, obj, 25.0, detail=3.0)
    color = mix(nt, math(nt, 'MULTIPLY', blotch.outputs[0], 0.3), color, (0.5, 0.5, 0.5), 'OVERLAY')
    u, v, _ = separate(nt, uv)
    if vein_lobes:
        ang = math(nt, 'ARCTAN2', u, math(nt, 'ADD', v, 0.08))
        vein = maprange(nt, math(nt, 'ABSOLUTE', math(nt, 'COSINE', math(nt, 'MULTIPLY', ang, vein_lobes))), 0.93, 1.0)
        color = mix(nt, math(nt, 'MULTIPLY', vein, 0.35), color, (1.0, 0.95, 0.6), 'OVERLAY')
    else:
        midrib = maprange(nt, math(nt, 'ABSOLUTE', u), 0.03, 0.0)
        color = mix(nt, math(nt, 'MULTIPLY', midrib, 0.4), color, (1.0, 1.0, 0.7), 'OVERLAY')
    if tip_color:
        color = mix(nt, math(nt, 'MULTIPLY', maprange(nt, v, 0.8, 1.0), 0.7), color, srgb(tip_color))
    bsdf = principled(nt, color, rough, None, Specular_IOR_Level=0.4)
    trans_color = mix(nt, 0.3, color, (1.0, 0.9, 0.3), 'SCREEN')
    finish(nt, out, with_translucency(nt, bsdf, trans_color, translucency))
    return mat


def needles():
    return foliage("Pine Needles", ['#1d3412', '#27411a', '#34521f'], translucency=0.25, rough=0.45)


def maple_leaf(variant):
    palettes = {
        "green": ['#3f6b17', '#557f1f', '#6b8f27'],
        "gold": ['#8f8d21', '#c79a1c', '#d8a826'],
        "orange": ['#d0721c', '#e05a16', '#c94313'],
        "red": ['#b8240f', '#9e150f', '#c2321a'],
        "crimson": ['#7d0c12', '#94111a', '#a8161c'],
    }
    return lambda: foliage(f"Maple Leaf {variant}", palettes[variant], translucency=0.4, rough=0.5, vein_lobes=3.5)


def bamboo_leaf():
    return foliage("Bamboo Leaf", ['#40651c', '#527a22', '#678b2a'], translucency=0.35, rough=0.45, tip_color='#a2a050')


def shrub_leaf():
    return foliage("Shrub Leaf", ['#21390f', '#2f4a15', '#3c5a1a', '#4a2c14'], translucency=0.2, rough=0.35)


def fern_leaf():
    return foliage("Fern", ['#3c6a1a', '#4f7f20', '#64912a'], translucency=0.35, rough=0.5)


def grass_blade():
    return foliage("Grass", ['#4f6d22', '#6a7f2c', '#8d8a42'], translucency=0.3, rough=0.55, tip_color='#b9a86a')


def pampas():
    mat, nt, out = new_material("Pampas Plume")
    uv = coords(nt).outputs['UV']
    streak = noise(nt, vmath(nt, 'MULTIPLY', uv, (30.0, 2.0, 1.0)), 5.0, detail=3.0)
    color = ramp(nt, streak.outputs[0], [(0.3, srgb('#b59a63')), (0.7, srgb('#e0cc9a'))])
    bsdf = principled(nt, color, 0.7, None, Sheen_Weight=1.0, Sheen_Tint=srgb('#fff2cc'))
    finish(nt, out, with_translucency(nt, bsdf, srgb('#f0dca8'), 0.45))
    return mat


# ---------------------------------------------------------------- creatures

def koi(pattern):
    def build():
        mat, nt, out = new_material(f"Koi {pattern}")
        obj = coords(nt).outputs['Object']
        n1 = noise(nt, obj, 9.0, detail=2.0, rough=0.4)
        n2 = noise(nt, vmath(nt, 'ADD', obj, (3.1, 7.7, 1.3)), 14.0, detail=2.0)
        white, red, black = srgb('#efebe2'), srgb('#d63d14'), srgb('#141210')
        if pattern == "kohaku":
            color = mix(nt, maprange(nt, n1.outputs[0], 0.48, 0.52), white, red)
        elif pattern == "sanke":
            color = mix(nt, maprange(nt, n1.outputs[0], 0.5, 0.54), white, red)
            color = mix(nt, maprange(nt, n2.outputs[0], 0.64, 0.67), color, black)
        elif pattern == "showa":
            color = mix(nt, maprange(nt, n1.outputs[0], 0.45, 0.49), black, red)
            color = mix(nt, maprange(nt, n2.outputs[0], 0.6, 0.63), color, white)
        elif pattern == "ogon":
            color = mix(nt, maprange(nt, n1.outputs[0], 0.3, 0.7), srgb('#e39a2c'), srgb('#f2c357'))
        else:  # asagi: blue-grey back, orange belly
            z = separate(nt, obj)[2]
            color = mix(nt, maprange(nt, z, -0.01, 0.02), srgb('#e05a1f'), srgb('#6d8091'))
        scales = voronoi(nt, vmath(nt, 'MULTIPLY', obj, (1.0, 1.6, 1.6)), 140.0)
        normal = bump(nt, scales.outputs['Distance'], 0.15, 0.003)
        metallic = 0.6 if pattern == "ogon" else 0.0
        finish(nt, out, principled(nt, color, 0.3, normal, Metallic=metallic, Coat_Weight=0.6,
                                   Subsurface_Weight=0.1))
        return mat
    return build


def bird(kind):
    def build():
        mat, nt, out = new_material(f"Bird {kind}")
        obj = coords(nt).outputs['Object']
        z = separate(nt, obj)[2]
        feathers = noise(nt, vmath(nt, 'MULTIPLY', obj, (1.0, 3.0, 1.0)), 60.0, detail=3.0)
        if kind == "dove":
            color = mix(nt, maprange(nt, z, 0.02, 0.05, 0.0, 0.3), srgb('#efede8'), srgb('#b8b8b6'))
        else:
            color = mix(nt, maprange(nt, z, -0.005, 0.015), srgb('#d8d0ae'), srgb('#6a6534'))
        color = mix(nt, math(nt, 'MULTIPLY', feathers.outputs[0], 0.3), color, (0.5, 0.5, 0.5), 'OVERLAY')
        finish(nt, out, principled(nt, color, 0.8, bump(nt, feathers.outputs[0], 0.1, 0.003),
                                   Sheen_Weight=0.4))
        return mat
    return build


def simple(name, hex_code, rough=0.5, **extra):
    def build():
        mat, nt, out = new_material(name)
        finish(nt, out, principled(nt, srgb(hex_code), rough, **extra))
        return mat
    return build


BUILDERS = {
    "wood_dark": wood_dark,
    "wood_light": wood_light,
    "wood_boards": wood_boards,
    "plaster": plaster,
    "shoji": shoji,
    "roof": roof,
    "bronze": bronze,
    "granite": granite,
    "rock": rock,
    "terrain": terrain,
    "bark_pine": bark_pine,
    "bark_smooth": bark_smooth,
    "bamboo": bamboo,
    "needles": needles,
    "maple_green": maple_leaf("green"),
    "maple_gold": maple_leaf("gold"),
    "maple_orange": maple_leaf("orange"),
    "maple_red": maple_leaf("red"),
    "maple_crimson": maple_leaf("crimson"),
    "bamboo_leaf": bamboo_leaf,
    "shrub_leaf": shrub_leaf,
    "fern": fern_leaf,
    "grass": grass_blade,
    "pampas": pampas,
    "koi_kohaku": koi("kohaku"),
    "koi_sanke": koi("sanke"),
    "koi_showa": koi("showa"),
    "koi_ogon": koi("ogon"),
    "koi_asagi": koi("asagi"),
    "koi_fin": simple("Koi Fin", '#e8ddd0', 0.4, Alpha=0.75),
    "bird_songbird": bird("songbird"),
    "bird_dove": bird("dove"),
    "eye": simple("Eye", '#050505', 0.08, Coat_Weight=1.0),
    "beak_dark": simple("Beak Dark", '#2b2520', 0.45),
    "beak_pink": simple("Beak Pink", '#c08a80', 0.5),
    "foliage_core": simple("Foliage Core", '#152a0c', 0.9),
    "dark_inside": simple("Dark Interior", '#070605', 0.9),
}
