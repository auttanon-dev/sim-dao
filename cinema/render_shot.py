"""Blender headless renderer for compiled shots.

Run inside Blender:
    blender -b -P cinema/render_shot.py -- --shots shots.json --out renders/

Reads shot.json produced by cinema/shotc.py and builds each shot deterministically:
identical input always yields an identical frame. Nothing here consults a
diffusion model - that is deliberate, because that is what keeps locations and
characters from drifting between shots.

Placeholder geometry only. Swap BLOCKING_RESOURCES for real assets once the style
guide is locked; everything else stays.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# ---------------------------------------------------------------- CLI
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) else True
    return default


# NOTE: Blender's CWD is its own executable dir, not the shell's, so pass
# ABSOLUTE paths for --shots and --out. These .resolve() calls normalise
# whatever you pass; they do not make a relative path relative to your shell.
SHOTS = Path(arg("--shots", "shots.json")).resolve()
OUT = Path(arg("--out", "renders")).resolve()
ONLY = arg("--only", None)          # render a single shot_id
DRAFT = bool(arg("--draft", False))  # half resolution, for fast iteration
ENGINE = arg("--engine", None)

# ---------------------------------------------------------------- style
# Art direction constants. Kept in sync with shotc.STYLE; both files are two
# views of the same style guide, so change them together.
BLOCKING_RESOURCES = Path("assets")
MATERIAL_COLORS = {
    "none": (0.75, 0.75, 0.78, 1.0),
    "pale_blue": (0.55, 0.72, 1.0, 1.0),
    "jade": (0.45, 0.95, 0.70, 1.0),
    "violet": (0.70, 0.50, 1.0, 1.0),
    "gold": (1.0, 0.82, 0.35, 1.0),
    "white": (1.0, 1.0, 1.0, 1.0),
}
ARCHETYPE_GROUND = {
    "sect_courtyard": (0.42, 0.40, 0.36),
    "town_street": (0.38, 0.34, 0.30),
    "market_stall": (0.44, 0.36, 0.28),
    "training_ground": (0.40, 0.42, 0.34),
    "wilderness": (0.30, 0.36, 0.28),
    "forbidden": (0.22, 0.16, 0.24),
    "realm_gate": (0.30, 0.28, 0.40),
    "border_pass": (0.40, 0.38, 0.34),
    "hidden_lair": (0.26, 0.22, 0.20),
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_world():
    world = bpy.data.worlds.new("film")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.07, 0.12, 1.0)
    bg.inputs[1].default_value = 1.0
    return world


def pick_engine(requested):
    """Resolve an engine name against what this Blender build actually has.

    Engine identifiers get renamed between releases (BLENDER_EEVEE_NEXT became
    BLENDER_EEVEE in 5.x), so match loosely instead of trusting one literal.
    """
    available = [i.identifier for i in
                 bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    want = (requested or "eevee").strip().lower()
    if want in available:
        return want
    if want in ("eevee", "eevee_next", "blender_eevee_next"):
        for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            if cand in available:
                return cand
    if want == "cycles":
        return "CYCLES"
    print(f"[cinema] engine '{requested}' unavailable, using {available[0]}")
    return available[0]


def setup_render(shot):
    scene = bpy.context.scene
    res = shot["render"]["resolution"]
    scene.render.engine = pick_engine(ENGINE or shot["render"].get("engine"))
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 50 if DRAFT else 100
    scene.render.fps = shot["render"]["fps"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    # EEVEE Next moved these; guard so a version bump degrades instead of failing.
    ee = getattr(scene, "eevee", None)
    if ee is not None:
        for attr, val in (("taa_render_samples", 32), ("use_gtao", True),
                          ("use_bloom", True), ("use_ssr", True)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:
                    pass


def apply_lighting(shot):
    light = shot["lighting"]
    scene = bpy.context.scene

    sun_data = bpy.data.lights.new("sun", type="SUN")
    sun_data.color = light["sun_color"]
    sun_data.energy = max(0.05, math.sin(math.radians(max(1.0, light["sun_elevation_deg"]))) * 3.0)
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)
    elev = math.radians(light["sun_elevation_deg"])
    azim = math.radians(light["sun_azimuth_deg"])
    sun.location = (math.cos(azim) * math.cos(elev) * 40,
                    math.sin(azim) * math.cos(elev) * 40,
                    math.sin(elev) * 40)
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(light["sun_azimuth_deg"] + 90))

    world = scene.world
    bg = world.node_tree.nodes["Background"]
    top, horizon = light["sky_top"], light["sky_horizon"]
    bg.inputs[0].default_value = (top[0], top[1], top[2], 1.0)
    bg.inputs[1].default_value = 1.2

    # Cool fill from the horizon so shadow sides stay readable, not black.
    fill_data = bpy.data.lights.new("fill", type="AREA")
    fill_data.color = (horizon[0] + 0.15, horizon[1] + 0.15, horizon[2] + 0.2)
    fill_data.energy = 60.0
    fill_data.size = 30.0
    fill = bpy.data.objects.new("fill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (0, -25, 14)
    fill.rotation_euler = (math.radians(55), 0, 0)


def build_ground(shot):
    loc = shot["location"]
    color = ARCHETYPE_GROUND.get(loc["archetype"], (0.35, 0.35, 0.35))
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    ground = bpy.context.object
    mat = bpy.data.materials.new(f"ground_{loc['archetype']}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    ground.data.materials.append(mat)
    return ground


def actor_position(actor):
    """Place an actor in world space from its framing offset.

    shotc emits screen_pos as a normalised frame offset: x is lateral position
    (-0.5 .. 0.5 across frame), y is depth stagger behind the subject. Convert
    it to a real ground position here, so the compiler stays free of Blender's
    coordinate conventions.
    """
    ox, oy = (actor.get("screen_pos") or [0.0, 0.0])[:2]
    return Vector((ox * 6.0, -oy * 8.0, 0.0))


def build_character(actor, is_subject):
    """Load the character's permanent model, or a stand-in block of its size.

    The size table is what makes this pipeline honest: a character is a fixed
    physical presence in every shot, not something re-rolled per shot.
    """
    model_id = actor["model_id"]
    pos = actor_position(actor)
    path = BLOCKING_RESOURCES / "chars" / f"{model_id}.glb"
    if path.exists():
        bpy.ops.import_scene.gltf(filepath=str(path))
        obj = bpy.context.selected_objects[0] if bpy.context.selected_objects else None
        if obj:
            obj.location = pos
            return obj
    height = 1.75 if actor["age_group"] == "adult" else 1.68
    if actor["is_beast"]:
        height *= 0.75
    bpy.ops.mesh.primitive_cube_add(location=pos + Vector((0, 0, height / 2)))
    obj = bpy.context.object
    obj.name = f"char_{actor['cid']}_{model_id}"
    obj.scale = (0.35, 0.25, height / 2)

    mat = bpy.data.materials.new(f"char_{model_id}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    base = (0.6, 0.55, 0.5, 1.0) if actor["gender"] == "หญิง" else (0.5, 0.5, 0.52, 1.0)
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Roughness"].default_value = 0.75
    obj.data.materials.append(mat)

    # Cultivation aura: a low-poly shell tinted by realm. Real VFX replaces this.
    aura = actor["aura"]
    if aura["power"] > 0:
        col = MATERIAL_COLORS.get(aura["name"], MATERIAL_COLORS["white"])
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=0.9, location=pos + Vector((0, 0, height / 2)))
        shell = bpy.context.object
        shell.name = f"aura_{actor['cid']}"
        shell.scale = (0.55, 0.55, height / 2 / 0.9)
        smat = bpy.data.materials.new(f"aura_{aura['name']}")
        smat.use_nodes = True
        sb = smat.node_tree.nodes["Principled BSDF"]
        sb.inputs["Base Color"].default_value = col
        sb.inputs["Emission Color"].default_value = col
        sb.inputs["Emission Strength"].default_value = aura["power"] * 2.0
        sb.inputs["Alpha"].default_value = 0.25
        if hasattr(smat, "blend_method"):
            smat.blend_method = "BLEND"
        shell.data.materials.append(smat)
    return obj


def place_camera(shot):
    cam = shot["camera"]
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = cam["lens_mm"]
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = cam["dof_fstop"]
    cam_obj = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Look at wherever the subject was actually placed, not at the world origin.
    subject_pos = Vector((0, 0, 0))
    for actor in shot["actors"]:
        if actor["cid"] == shot["subject_cid"]:
            subject_pos = actor_position(actor)
            break
    aim_at = subject_pos + Vector((0, 0, 1.5))

    dist = cam["distance_m"]
    theta = math.radians(cam["orbit_deg"])
    cam_obj.location = aim_at + Vector((math.cos(theta) * dist,
                                        -dist * math.sin(theta),
                                        cam["height_m"]))
    direction = aim_at - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    # Focus on the subject so depth of field reads as intentional.
    focus = bpy.data.objects.new("focus", None)
    focus.location = aim_at
    scene.collection.objects.link(focus)
    cam_data.dof.focus_object = focus
    return cam_obj


def render_shot(shot):
    reset_scene()
    setup_world()
    setup_render(shot)
    apply_lighting(shot)
    build_ground(shot)
    for actor in shot["actors"]:
        build_character(actor, actor["cid"] == shot["subject_cid"])
    place_camera(shot)

    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(OUT / shot["shot_id"])
    bpy.ops.render.render(write_still=True)
    return scene.render.filepath


def main():
    data = json.loads(SHOTS.read_text(encoding="utf-8"))
    shots = data["shots"]
    if ONLY:
        shots = [s for s in shots if s["shot_id"] == ONLY]
    print(f"[cinema] rendering {len(shots)} shots -> {OUT} "
          f"(draft={DRAFT}, engine={ENGINE or 'from shot'})")
    for shot in shots:
        path = render_shot(shot)
        print(f"[cinema] {shot['shot_id']} {shot['camera']['size']:9} "
              f"{shot['location']['place_name']} -> {path}.png")


main()
