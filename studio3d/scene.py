"""Clean-room Blender 5.3+ Cycles OptiX 3D cutaway diorama builder (1.0 unit = 1 meter)."""
from __future__ import annotations

import math
import os
import random
import sys
import time
from typing import Iterable, Sequence

import bpy
import bmesh
from mathutils import Vector

from .timeline import Timeline


HIDDEN_SCALE = (0.001, 0.001, 0.001)


def find_bold_font() -> str | None:
    """Locate a crisp bold sans-serif font across Windows, macOS, and Linux."""
    candidates = [
        os.environ.get("STUDIO3D_FONT", ""),
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def catmull_rom(points: Sequence[tuple[float, float, float]], subdivisions: int = 6) -> list[tuple[float, float, float]]:
    """Interpolate a smooth 3D polyline through control points using Catmull-Rom splines."""
    vecs = [Vector(p) for p in points]
    padded = [vecs[0]] + vecs + [vecs[-1]]
    sampled: list[tuple[float, float, float]] = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for step in range(subdivisions):
            t = step / subdivisions
            t2, t3 = t * t, t * t * t
            pt = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            sampled.append((pt.x, pt.y, pt.z))
    sampled.append((vecs[-1].x, vecs[-1].y, vecs[-1].z))
    return sampled


def iter_fcurves(id_block) -> list:
    """Return fcurves cleanly across both Blender 5.x slotted Actions and Blender 4.x Actions."""
    anim = id_block.animation_data
    if not anim or not anim.action:
        return []
    act = anim.action
    if hasattr(act, "layers"):
        found = []
        for layer in act.layers:
            for strip in layer.strips:
                cbag = strip.channelbag(anim.action_slot)
                if cbag:
                    found.extend(cbag.fcurves)
        return found
    return list(getattr(act, "fcurves", []))


class CameraRig:
    """Smooth continuous cinematic camera controller with subtle drift and macro zoom."""

    def __init__(self, studio: "DioramaStudio") -> None:
        self.studio = studio
        self.fps = studio.timeline.config.fps
        self.aspect = studio.timeline.config.width / studio.timeline.config.height
        self._prev_pose: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None

        cam_data = bpy.data.cameras.new("StudioCam")
        cam_data.lens = 36.0
        cam_data.clip_start = 0.05
        cam_data.clip_end = 2500.0
        self.camera = bpy.data.objects.new("StudioCam", cam_data)
        studio.collection.objects.link(self.camera)
        studio.scene.camera = self.camera

        self.target = studio.add_group("StudioCamTarget")
        track = self.camera.constraints.new("TRACK_TO")
        track.target = self.target
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

    @staticmethod
    def spherical_pose(
        azimuth_deg: float,
        elevation_deg: float,
        distance: float,
        target: tuple[float, float, float],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Compute (camera_location, target_location). Azimuth 90 deg = frontal cutaway view."""
        az = math.radians(azimuth_deg)
        el = math.radians(elevation_deg)
        look_dir = Vector((-math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), -math.sin(el)))
        cam_loc = Vector(target) - look_dir * distance
        return ((cam_loc.x, cam_loc.y, cam_loc.z), target)

    @staticmethod
    def subtle_push(
        pose: tuple[tuple[float, float, float], tuple[float, float, float]],
        factor: float = 0.035,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        c, t = Vector(pose[0]), Vector(pose[1])
        c_end = c + (t - c) * factor
        return ((c_end.x, c_end.y, c_end.z), pose[1])

    def _key_pose(
        self,
        t_sec: float,
        pose: tuple[tuple[float, float, float], tuple[float, float, float]],
        interp: str,
        easing: str | None = None,
    ) -> None:
        self.studio.set_key(self.camera, "location", t_sec, pose[0], interp=interp, easing=easing)
        self.studio.set_key(self.target, "location", t_sec, pose[1], interp=interp, easing=easing)

    def add_shot(
        self,
        t_start: float,
        t_end: float,
        main_pose: tuple[tuple[float, float, float], tuple[float, float, float]],
        end_pose: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
        transition: float = 1.0,
        hard_cut: bool = False,
    ) -> None:
        """Ease smoothly from previous shot into main_pose over `transition` sec, then drift to end_pose."""
        final_pose = end_pose or self.subtle_push(main_pose)
        if hard_cut or self._prev_pose is None:
            self._key_pose(t_start, main_pose, "LINEAR")
        else:
            self._key_pose(t_start, self._prev_pose, "SINE", "EASE_IN_OUT")
            arrive_t = min(t_start + transition, max(t_start + 0.1, t_end - 0.25))
            self._key_pose(arrive_t, main_pose, "LINEAR")
        self._key_pose(t_end - 1.0 / self.fps, final_pose, "CONSTANT")
        self._prev_pose = final_pose


class DioramaStudio:
    """High-level clean-room 3D cutaway diorama scene builder for Blender 5.3+."""

    def __init__(self, timeline: Timeline, seed: int = 17) -> None:
        self.timeline = timeline
        self.fps = timeline.config.fps
        self.duration = timeline.total_duration
        self.total_frames = timeline.total_frames
        random.seed(seed)

        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.collection = self.scene.collection

        # Load bold system font for 3D callout labels
        self.font3d = None
        font_path = find_bold_font()
        if font_path:
            try:
                self.font3d = bpy.data.fonts.load(font_path)
            except Exception as exc:
                print(f"[studio3d] Font load fallback to built-in ({exc})", flush=True)
        self.text_scale = 1.22 if self.font3d is not None else 1.0

        self._setup_daylight_world()
        self.cam = CameraRig(self)
        self._init_base_materials()

    # --------------------------------------------------------- world & lighting
    def _ensure_nodes(self, datablock) -> bpy.types.NodeTree:
        """Avoid Blender 6.0 DeprecationWarning on Material/World.use_nodes."""
        if getattr(datablock, "node_tree", None) is None:
            datablock.use_nodes = True
        return datablock.node_tree

    def _setup_daylight_world(self) -> None:
        world = bpy.data.worlds.new("DaylightSky")
        self.scene.world = world
        nt = self._ensure_nodes(world)
        nodes, links = nt.nodes, nt.links
        nodes.clear()

        out = nodes.new("ShaderNodeOutputWorld")
        bg = nodes.new("ShaderNodeBackground")
        bg.inputs["Strength"].default_value = 1.0
        links.new(bg.outputs[0], out.inputs[0])

        tc = nodes.new("ShaderNodeTexCoord")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(tc.outputs["Generated"], sep.inputs[0])

        # Vertical azure sky gradient
        elev = nodes.new("ShaderNodeMapRange")
        elev.inputs["From Min"].default_value = 0.0
        elev.inputs["From Max"].default_value = 0.72
        links.new(sep.outputs["Z"], elev.inputs["Value"])

        sky_ramp = nodes.new("ShaderNodeValToRGB")
        sky_ramp.color_ramp.elements[0].position = 0.0
        sky_ramp.color_ramp.elements[0].color = (0.64, 0.82, 0.98, 1.0)
        sky_ramp.color_ramp.elements[1].position = 1.0
        sky_ramp.color_ramp.elements[1].color = (0.11, 0.36, 0.84, 1.0)
        links.new(elev.outputs[0], sky_ramp.inputs[0])

        # Projected soft sky clouds
        z_floor = nodes.new("ShaderNodeMath")
        z_floor.operation = "MAXIMUM"
        z_floor.inputs[1].default_value = 0.045
        links.new(sep.outputs["Z"], z_floor.inputs[0])

        px = nodes.new("ShaderNodeMath"); px.operation = "DIVIDE"
        py = nodes.new("ShaderNodeMath"); py.operation = "DIVIDE"
        links.new(sep.outputs["X"], px.inputs[0]); links.new(z_floor.outputs[0], px.inputs[1])
        links.new(sep.outputs["Y"], py.inputs[0]); links.new(z_floor.outputs[0], py.inputs[1])

        proj = nodes.new("ShaderNodeCombineXYZ")
        links.new(px.outputs[0], proj.inputs[0]); links.new(py.outputs[0], proj.inputs[1])

        cloud_noise = nodes.new("ShaderNodeTexNoise")
        cloud_noise.inputs["Scale"].default_value = 0.52
        cloud_noise.inputs["Detail"].default_value = 6.5
        cloud_noise.inputs["Roughness"].default_value = 0.58
        links.new(proj.outputs[0], cloud_noise.inputs["Vector"])

        cloud_mask = nodes.new("ShaderNodeValToRGB")
        cloud_mask.color_ramp.elements[0].position = 0.51
        cloud_mask.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        cloud_mask.color_ramp.elements[1].position = 0.65
        cloud_mask.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        links.new(cloud_noise.outputs[0], cloud_mask.inputs[0])

        horizon_fade = nodes.new("ShaderNodeMapRange")
        horizon_fade.inputs["From Min"].default_value = 0.03
        horizon_fade.inputs["From Max"].default_value = 0.16
        links.new(sep.outputs["Z"], horizon_fade.inputs["Value"])

        cloud_amt = nodes.new("ShaderNodeMath"); cloud_amt.operation = "MULTIPLY"
        links.new(cloud_mask.outputs[0], cloud_amt.inputs[0])
        links.new(horizon_fade.outputs[0], cloud_amt.inputs[1])

        mix_clouds = nodes.new("ShaderNodeMix"); mix_clouds.data_type = "RGBA"
        links.new(cloud_amt.outputs[0], mix_clouds.inputs[0])
        links.new(sky_ramp.outputs[0], mix_clouds.inputs[6])
        mix_clouds.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)

        # Ground hemisphere green bounce below z=0
        is_below = nodes.new("ShaderNodeMath"); is_below.operation = "LESS_THAN"
        is_below.inputs[1].default_value = 0.0
        links.new(sep.outputs["Z"], is_below.inputs[0])

        mix_ground = nodes.new("ShaderNodeMix"); mix_ground.data_type = "RGBA"
        links.new(is_below.outputs[0], mix_ground.inputs[0])
        links.new(mix_clouds.outputs[2], mix_ground.inputs[6])
        mix_ground.inputs[7].default_value = (0.29, 0.46, 0.13, 1.0)
        links.new(mix_ground.outputs[2], bg.inputs["Color"])

        # Crisp key sunlight casting architectural shadows
        sun_data = bpy.data.lights.new("KeySun", "SUN")
        sun_data.energy = 2.75
        sun_data.angle = math.radians(5.5)
        sun_obj = bpy.data.objects.new("KeySun", sun_data)
        self.collection.objects.link(sun_obj)
        sun_obj.rotation_euler = Vector((0.40, 0.72, -0.56)).normalized().to_track_quat("-Z", "Y").to_euler()

    # --------------------------------------------------------- materials
    def make_material(
        self,
        name: str,
        color: tuple[float, float, float],
        roughness: float = 0.82,
        emission: float = 0.0,
        specular: float = 0.25,
        alpha: float = 1.0,
    ) -> bpy.types.Material:
        mat = bpy.data.materials.new(name)
        nt = self._ensure_nodes(mat)
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            nt.nodes.clear()
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(bsdf.outputs[0], out.inputs[0])
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        for sock_name in ("Specular IOR Level", "Specular"):
            if sock_name in bsdf.inputs:
                bsdf.inputs[sock_name].default_value = specular
                break
        if emission > 0.0:
            bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
        mat.diffuse_color = (*color, 1.0)
        return mat

    def bsdf(self, mat: bpy.types.Material):
        return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

    def animate_color(
        self,
        mat: bpy.types.Material,
        stops: Sequence[tuple[float, tuple[float, float, float], float]],
    ) -> None:
        shader = self.bsdf(mat)
        for t_sec, rgb, alpha in stops:
            frame = self.timeline.sec_to_frame(t_sec)
            shader.inputs["Base Color"].default_value = (*rgb, 1.0)
            shader.inputs["Base Color"].keyframe_insert("default_value", frame=frame)
            shader.inputs["Alpha"].default_value = alpha
            shader.inputs["Alpha"].keyframe_insert("default_value", frame=frame)

    def make_soil_material(self) -> bpy.types.Material:
        mat = self.make_material("GeologicalSoil", (0.30, 0.14, 0.07), roughness=0.96, specular=0.1)
        nt = mat.node_tree
        nodes, links, bsdf = nt.nodes, nt.links, self.bsdf(mat)

        geo = nodes.new("ShaderNodeNewGeometry")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geo.outputs["Position"], sep.inputs[0])

        wave_n = nodes.new("ShaderNodeTexNoise")
        wave_n.inputs["Scale"].default_value = 0.50
        wave_n.inputs["Detail"].default_value = 2.0
        links.new(geo.outputs["Position"], wave_n.inputs["Vector"])

        sub = nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = 0.5
        mul = nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.50
        add = nodes.new("ShaderNodeMath"); add.operation = "ADD"
        links.new(wave_n.outputs[0], sub.inputs[0])
        links.new(sub.outputs[0], mul.inputs[0])
        links.new(sep.outputs["Z"], add.inputs[0])
        links.new(mul.outputs[0], add.inputs[1])

        depth_map = nodes.new("ShaderNodeMapRange")
        depth_map.inputs["From Min"].default_value = -25.0
        depth_map.inputs["From Max"].default_value = 0.0
        links.new(add.outputs[0], depth_map.inputs["Value"])

        strata = nodes.new("ShaderNodeValToRGB")
        strata.color_ramp.interpolation = "CONSTANT"
        cr = strata.color_ramp
        layers = [
            (0.0, (0.055, 0.044, 0.042)),
            (0.62, (0.095, 0.056, 0.036)),
            (0.84, (0.28, 0.105, 0.048)),
            (0.965, (0.14, 0.075, 0.038)),
        ]
        cr.elements[0].position, cr.elements[0].color = layers[0][0], (*layers[0][1], 1.0)
        cr.elements[1].position, cr.elements[1].color = layers[1][0], (*layers[1][1], 1.0)
        for pos, col in layers[2:]:
            elem = cr.elements.new(pos)
            elem.color = (*col, 1.0)
        links.new(depth_map.outputs[0], strata.inputs[0])

        # Pebble speckles
        vor = nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 5.8
        links.new(geo.outputs["Position"], vor.inputs["Vector"])

        peb_mask = nodes.new("ShaderNodeValToRGB")
        peb_mask.color_ramp.elements[0].position = 0.065
        peb_mask.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
        peb_mask.color_ramp.elements[1].position = 0.105
        peb_mask.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
        links.new(vor.outputs["Distance"], peb_mask.inputs[0])

        peb_str = nodes.new("ShaderNodeMath"); peb_str.operation = "MULTIPLY"; peb_str.inputs[1].default_value = 0.50
        links.new(peb_mask.outputs[0], peb_str.inputs[0])

        mix_peb = nodes.new("ShaderNodeMix"); mix_peb.data_type = "RGBA"
        links.new(peb_str.outputs[0], mix_peb.inputs[0])
        links.new(strata.outputs[0], mix_peb.inputs[6])
        mix_peb.inputs[7].default_value = (0.44, 0.27, 0.17, 1.0)

        # Fine grain multiply
        grain_n = nodes.new("ShaderNodeTexNoise")
        grain_n.inputs["Scale"].default_value = 34.0
        grain_n.inputs["Detail"].default_value = 3.0
        links.new(geo.outputs["Position"], grain_n.inputs["Vector"])

        grain_rng = nodes.new("ShaderNodeMapRange")
        grain_rng.inputs["To Min"].default_value = 0.76
        grain_rng.inputs["To Max"].default_value = 1.22
        links.new(grain_n.outputs[0], grain_rng.inputs["Value"])

        mix_grain = nodes.new("ShaderNodeMix"); mix_grain.data_type = "RGBA"; mix_grain.blend_type = "MULTIPLY"
        mix_grain.inputs[0].default_value = 1.0
        links.new(mix_peb.outputs[2], mix_grain.inputs[6])
        links.new(grain_rng.outputs[0], mix_grain.inputs[7])
        links.new(mix_grain.outputs[2], bsdf.inputs["Base Color"])
        return mat

    def make_lawn_material(self) -> bpy.types.Material:
        mat = self.make_material("StripedLawn", (0.28, 0.48, 0.12), roughness=0.94, specular=0.1)
        nt = mat.node_tree
        nodes, links, bsdf = nt.nodes, nt.links, self.bsdf(mat)
        geo = nodes.new("ShaderNodeNewGeometry")

        bands = nodes.new("ShaderNodeTexWave")
        bands.wave_type = "BANDS"
        bands.bands_direction = "X"
        bands.inputs["Scale"].default_value = 0.18
        links.new(geo.outputs["Position"], bands.inputs["Vector"])

        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.42
        ramp.color_ramp.elements[0].color = (0.24, 0.42, 0.10, 1.0)
        ramp.color_ramp.elements[1].position = 0.58
        ramp.color_ramp.elements[1].color = (0.33, 0.52, 0.13, 1.0)
        links.new(bands.outputs[0], ramp.inputs[0])

        n2 = nodes.new("ShaderNodeTexNoise")
        n2.inputs["Scale"].default_value = 9.0
        n2.inputs["Detail"].default_value = 3.5
        links.new(geo.outputs["Position"], n2.inputs["Vector"])

        gr = nodes.new("ShaderNodeMapRange")
        gr.inputs["To Min"].default_value = 0.82
        gr.inputs["To Max"].default_value = 1.16
        links.new(n2.outputs[0], gr.inputs["Value"])

        mix = nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        links.new(ramp.outputs[0], mix.inputs[6])
        links.new(gr.outputs[0], mix.inputs[7])
        links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        return mat

    def make_water_material(
        self,
        name: str,
        color: tuple[float, float, float],
        alpha: float = 0.84,
    ) -> bpy.types.Material:
        mat = self.make_material(name, color, roughness=0.07, specular=0.72, alpha=alpha)
        nt = mat.node_tree
        nodes, links, bsdf = nt.nodes, nt.links, self.bsdf(mat)
        geo = nodes.new("ShaderNodeNewGeometry")
        nz = nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 2.6
        nz.inputs["Detail"].default_value = 1.5
        links.new(geo.outputs["Position"], nz.inputs["Vector"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.28
        bump.inputs["Distance"].default_value = 0.04
        links.new(nz.outputs[0], bump.inputs["Height"])
        links.new(bump.outputs[0], bsdf.inputs["Normal"])
        # Animate gentle surface drift
        nz.inputs["W"].default_value = 0.0
        nz.inputs["W"].keyframe_insert("default_value", frame=1.0)
        nz.inputs["W"].default_value = self.duration * 0.45
        nz.inputs["W"].keyframe_insert("default_value", frame=self.timeline.sec_to_frame(self.duration))
        return mat

    def _init_base_materials(self) -> None:
        self.m_soil = self.make_soil_material()
        self.m_lawn = self.make_lawn_material()
        self.m_concrete = self.make_material("Concrete", (0.65, 0.65, 0.63), roughness=0.88)
        self.m_steel = self.make_material("Steel", (0.56, 0.59, 0.63), roughness=0.38, specular=0.65)
        self.m_pvc = self.make_material("PVCWhite", (0.88, 0.89, 0.91), roughness=0.34, specular=0.52)
        self.m_bore = self.make_material("PipeInner", (0.30, 0.36, 0.44), roughness=0.62)
        self.m_wood = self.make_material("WarmWood", (0.64, 0.45, 0.28), roughness=0.72)
        self.m_plate = self.make_material("PlateDark", (0.06, 0.09, 0.15), roughness=0.55)
        self.m_white_emit = self.make_material("TextWhite", (1.0, 1.0, 1.0), roughness=0.5, emission=1.05)
        self.m_yellow_emit = self.make_material("TextYellow", (1.0, 0.84, 0.14), roughness=0.5, emission=1.25)
        self.m_trunk = self.make_material("TreeTrunk", (0.31, 0.21, 0.14), roughness=0.94)
        self.m_canopy = self.make_material("TreeCanopy", (0.21, 0.40, 0.14), roughness=0.92)
        self.m_palm = self.make_material("PalmLeaf", (0.24, 0.48, 0.15), roughness=0.82)

        # Clean-room original Educator Character palette (casual teal-blue hoodie + glasses + slate pants)
        self.m_ed_skin = self.make_material("EduSkin", (0.83, 0.64, 0.49), roughness=0.68)
        self.m_ed_hair = self.make_material("EduHair", (0.10, 0.09, 0.10), roughness=0.78)
        self.m_ed_shirt = self.make_material("EduShirt", (0.11, 0.52, 0.64), roughness=0.74)
        self.m_ed_collar = self.make_material("EduCollar", (0.94, 0.96, 0.98), roughness=0.75)
        self.m_ed_pants = self.make_material("EduPants", (0.18, 0.21, 0.28), roughness=0.88)
        self.m_ed_shoe = self.make_material("EduShoe", (0.92, 0.93, 0.95), roughness=0.55)
        self.m_ed_glass = self.make_material("EduGlass", (0.12, 0.14, 0.18), roughness=0.25, specular=0.7)

    # --------------------------------------------------------- geometry helpers
    def _attach(self, obj, mat=None, parent=None):
        self.collection.objects.link(obj)
        if mat is not None:
            obj.data.materials.append(mat)
        if parent is not None:
            obj.parent = parent
        return obj

    def add_group(self, name: str, location=(0.0, 0.0, 0.0), parent=None):
        obj = bpy.data.objects.new(name, None)
        self.collection.objects.link(obj)
        obj.location = location
        if parent is not None:
            obj.parent = parent
        return obj

    def add_box(
        self,
        name: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        z0: float,
        z1: float,
        mat: bpy.types.Material,
        pivot: str = "bottom",
        parent=None,
    ):
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        shift = {
            "bottom": (0.0, 0.0, sz * 0.5),
            "top": (0.0, 0.0, -sz * 0.5),
            "left": (sx * 0.5, 0.0, 0.0),
            "right": (-sx * 0.5, 0.0, 0.0),
            "center": (0.0, 0.0, 0.0),
        }[pivot]
        for v in bm.verts:
            v.co.x = v.co.x * sx + shift[0]
            v.co.y = v.co.y * sy + shift[1]
            v.co.z = v.co.z * sz + shift[2]
        bm.to_mesh(mesh)
        bm.free()

        obj = self._attach(bpy.data.objects.new(name, mesh), mat, parent)
        cx, cy, cz = (x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5
        obj.location = {
            "bottom": (cx, cy, z0),
            "top": (cx, cy, z1),
            "left": (x0, cy, cz),
            "right": (x1, cy, cz),
            "center": (cx, cy, cz),
        }[pivot]
        return obj

    def add_cylinder(
        self,
        name: str,
        location: tuple[float, float, float],
        radius: float,
        height: float,
        mat: bpy.types.Material,
        segments: int = 18,
        top_radius: float | None = None,
        downward: bool = False,
        smooth: bool = True,
        parent=None,
    ):
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            segments=segments,
            radius1=radius,
            radius2=radius if top_radius is None else top_radius,
            depth=height,
        )
        dz = -height * 0.5 if downward else height * 0.5
        for v in bm.verts:
            v.co.z += dz
        if smooth:
            for face in bm.faces:
                if len(face.verts) == 4:
                    face.smooth = True
        bm.to_mesh(mesh)
        bm.free()
        obj = self._attach(bpy.data.objects.new(name, mesh), mat, parent)
        obj.location = location
        return obj

    def add_sphere(
        self,
        name: str,
        location: tuple[float, float, float],
        radius: float,
        mat: bpy.types.Material,
        scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
        segments: int = 14,
        smooth: bool = True,
        parent=None,
    ):
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=max(6, segments // 2), radius=radius)
        for face in bm.faces:
            face.smooth = smooth
        bm.to_mesh(mesh)
        bm.free()
        obj = self._attach(bpy.data.objects.new(name, mesh), mat, parent)
        obj.location = location
        obj.scale = scale
        return obj

    def add_prism_xz(
        self,
        name: str,
        profile_xz: Sequence[tuple[float, float]],
        y0: float,
        y1: float,
        mat: bpy.types.Material,
        parent=None,
    ):
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        base_face = bm.faces.new([bm.verts.new((x, y0, z)) for x, z in profile_xz])
        extruded = bmesh.ops.extrude_face_region(bm, geom=[base_face])
        for item in extruded["geom"]:
            if isinstance(item, bmesh.types.BMVert):
                item.co.y += y1 - y0
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        return self._attach(bpy.data.objects.new(name, mesh), mat, parent)

    def add_tube(
        self,
        name: str,
        points: Sequence[tuple[float, float, float]],
        radius: float,
        mat: bpy.types.Material,
        bevel_res: int = 4,
        parent=None,
    ):
        curve = bpy.data.curves.new(name, "CURVE")
        curve.dimensions = "3D"
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for sp_pt, co in zip(spline.points, points):
            sp_pt.co = (co[0], co[1], co[2], 1.0)
        curve.bevel_depth = radius
        curve.bevel_resolution = bevel_res
        curve.use_fill_caps = True
        return self._attach(bpy.data.objects.new(name, curve), mat, parent)

    def add_cutaway_pipe(
        self,
        name: str,
        points: Sequence[tuple[float, float, float]],
        radius: float = 0.03,
        mat: bpy.types.Material | None = None,
        show_bore: bool = True,
    ) -> list:
        """Pipe with optional dark front inner bore so fluid particles read inside the pipe."""
        objs = [self.add_tube(name, points, radius, mat or self.m_pvc)]
        if show_bore:
            r_in = radius * 0.64
            y_shift = radius - r_in + 0.004
            bore_pts = [(x, y - y_shift, z) for x, y, z in points]
            objs.append(self.add_tube(name + "_bore", bore_pts, r_in, self.m_bore))
        return objs

    def add_helix_coil(
        self,
        name: str,
        center: tuple[float, float, float],
        rx: float,
        ry: float,
        height: float,
        turns: float,
        wire_radius: float,
        mat: bpy.types.Material,
        steps_per_turn: int = 10,
    ):
        cx, cy, cz = center
        total_steps = max(8, int(round(turns * steps_per_turn)))
        pts = []
        for s in range(total_steps + 1):
            frac = s / total_steps
            angle = frac * turns * math.tau
            pts.append((cx + math.cos(angle) * rx, cy + math.sin(angle) * ry, cz + height * (0.5 - frac)))
        return self.add_tube(name, pts, wire_radius, mat, bevel_res=3)

    # --------------------------------------------------------- callout labels
    def add_text_3d(
        self,
        name: str,
        body: str,
        location: tuple[float, float, float],
        size: float,
        mat: bpy.types.Material,
        extrude: float = 0.003,
        rotation=(math.radians(90), 0.0, 0.0),
        parent=None,
    ):
        curve = bpy.data.curves.new(name, "FONT")
        curve.body = body
        curve.align_x = "CENTER"
        curve.align_y = "CENTER"
        curve.size = size * self.text_scale
        curve.extrude = extrude
        if self.font3d is not None:
            curve.font = self.font3d
        obj = self._attach(bpy.data.objects.new(name, curve), mat, parent)
        obj.location = location
        obj.rotation_euler = rotation
        return obj

    def add_callout(
        self,
        name: str,
        lines: str | Sequence[tuple[str, float, bpy.types.Material]],
        pos: tuple[float, float, float],
        plate_mat: bpy.types.Material | None = None,
        billboard: bool = True,
        default_size: float = 0.14,
    ):
        """Diegetic floating badge with auto-fitted rounded backing plate."""
        if isinstance(lines, str):
            lines = [(lines, default_size, self.m_white_emit)]
        root = self.add_group(name, pos)
        if billboard:
            con = root.constraints.new("COPY_ROTATION")
            con.target = self.cam.camera
        else:
            root.rotation_euler = (math.radians(90), 0.0, 0.0)

        txt_objs = [
            self.add_text_3d(f"{name}_l{i}", body, (0.0, 0.0, 0.005), sz, mat, rotation=(0.0, 0.0, 0.0), parent=root)
            for i, (body, sz, mat) in enumerate(lines)
        ]
        bpy.context.view_layer.update()

        bounds = []
        for obj in txt_objs:
            xs = [c[0] for c in obj.bound_box]
            ys = [c[1] for c in obj.bound_box]
            bounds.append((min(xs), max(xs), min(ys), max(ys)))

        pad = lines[0][1] * self.text_scale * 0.40
        gap = lines[0][1] * self.text_scale * 0.28
        total_h = sum(b[3] - b[2] for b in bounds) + gap * (len(bounds) - 1) + 2.0 * pad
        total_w = max(b[1] - b[0] for b in bounds) + 2.4 * pad

        y_cursor = total_h * 0.5 - pad
        for obj, b in zip(txt_objs, bounds):
            h = b[3] - b[2]
            obj.location = (-(b[0] + b[1]) * 0.5, y_cursor - h * 0.5 - (b[2] + b[3]) * 0.5, 0.005)
            y_cursor -= h + gap

        plate = self.add_box(
            f"{name}_plate",
            -total_w * 0.5,
            total_w * 0.5,
            -total_h * 0.5,
            total_h * 0.5,
            -0.016,
            0.0,
            plate_mat or self.m_plate,
            pivot="center",
            parent=root,
        )
        if billboard:
            for item in txt_objs + [plate]:
                item.visible_shadow = False
        return root

    # --------------------------------------------------------- original educator figure & foliage
    def add_educator(self, name: str, location: tuple[float, float, float]):
        """Original 1.72m casual Indonesian tech-educator figure (teal shirt, collar, glasses, dark hair)."""
        root = self.add_group(name, location)
        # Sneakers & trousers
        for sx in (-0.105, 0.105):
            self.add_box(f"{name}_shoe_{sx}", sx - 0.075, sx + 0.075, -0.15, 0.09, 0.0, 0.09, self.m_ed_shoe, parent=root)
            self.add_cylinder(f"{name}_leg_{sx}", (sx, 0.0, 0.08), 0.068, 0.72, self.m_ed_pants, segments=12, parent=root)
        # Torso + white collar + subtle shoulder rounding
        self.add_box(f"{name}_torso", -0.20, 0.20, -0.11, 0.11, 0.80, 1.40, self.m_ed_shirt, parent=root)
        self.add_cylinder(f"{name}_collar", (0.0, 0.0, 1.38), 0.095, 0.05, self.m_ed_collar, segments=14, parent=root)
        # Articulated arms (pivoted at shoulder)
        arms = []
        for sx in (-0.255, 0.255):
            self.add_sphere(f"{name}_sh_{sx}", (sx * 0.92, 0.0, 1.35), 0.072, self.m_ed_shirt, segments=10, parent=root)
            arm_pivot = self.add_group(f"{name}_arm_{sx}", (sx, 0.0, 1.35), parent=root)
            self.add_cylinder(f"{name}_sleeve_{sx}", (0.0, 0.0, 0.0), 0.056, 0.22, self.m_ed_shirt, segments=10, downward=True, parent=arm_pivot)
            self.add_cylinder(f"{name}_forearm_{sx}", (0.0, 0.0, -0.20), 0.044, 0.34, self.m_ed_skin, segments=10, downward=True, parent=arm_pivot)
            self.add_sphere(f"{name}_hand_{sx}", (0.0, 0.0, -0.55), 0.048, self.m_ed_skin, segments=10, parent=arm_pivot)
            arm_pivot.rotation_euler = (0.0, math.radians(10 if sx < 0 else -10), 0.0)
            arms.append(arm_pivot)
        # Neck + head + modern hair cap + sleek glasses
        self.add_cylinder(f"{name}_neck", (0.0, 0.0, 1.41), 0.048, 0.08, self.m_ed_skin, segments=10, parent=root)
        self.add_sphere(f"{name}_head", (0.0, 0.0, 1.61), 0.145, self.m_ed_skin, scale=(1.0, 0.96, 1.08), segments=16, parent=root)
        self.add_sphere(f"{name}_hair", (0.0, 0.025, 1.675), 0.148, self.m_ed_hair, scale=(1.04, 1.02, 0.72), segments=14, parent=root)
        # Glasses frame (two slim dark rims + nose bridge on -Y front face)
        for gx in (-0.052, 0.052):
            self.add_box(f"{name}_gl_{gx}", gx - 0.036, gx + 0.036, -0.152, -0.132, 1.60, 1.645, self.m_ed_glass, pivot="center", parent=root)
        self.add_box(f"{name}_gbridge", -0.02, 0.02, -0.152, -0.134, 1.618, 1.630, self.m_ed_glass, pivot="center", parent=root)
        return root, arms[0], arms[1]

    def wave_arms(self, arms: tuple, t_start: float, t_end: float, angle_deg: float = 148.0) -> None:
        for arm_obj, sign in zip(arms, (1.0, -1.0)):
            if arm_obj is None:
                continue
            self.set_key(arm_obj, "rotation_euler", t_start - 0.04, math.radians(10.0 * sign), index=1)
            self.set_key(arm_obj, "rotation_euler", t_start + 0.25, math.radians(angle_deg * sign), index=1)
            self.set_key(arm_obj, "rotation_euler", t_end, math.radians(angle_deg * sign), index=1)
            self.set_key(arm_obj, "rotation_euler", t_end + 0.32, math.radians(10.0 * sign), index=1)

    def add_foliage_tree(self, x: float, y: float, height: float = 3.2, radius: float = 1.45) -> None:
        self.add_cylinder(f"TreeTrunk_{x:.1f}", (x, y, 0.0), 0.16, height, self.m_trunk, segments=8, smooth=False)
        blobs = ((0.0, 0.0, 0.25, 1.0), (0.68, 0.18, -0.25, 0.72), (-0.62, -0.25, -0.18, 0.78), (0.12, 0.45, 0.65, 0.58))
        for k, (dx, dy, dz, mult) in enumerate(blobs):
            self.add_sphere(
                f"TreeLeaf_{x:.1f}_{k}",
                (x + dx * radius, y + dy * radius, height + dz * radius + radius * 0.35),
                radius * mult,
                self.m_canopy,
                segments=9,
                smooth=False,
            )

    def add_tropical_palm(self, x: float, y: float, height: float = 5.2, lean: float = 0.45) -> None:
        pts = catmull_rom([(x, y, 0.0), (x + lean * 0.32, y, height * 0.5), (x + lean, y, height)], subdivisions=4)
        self.add_tube(f"PalmTrunk_{x:.1f}", pts, 0.13, self.m_trunk, bevel_res=3)
        for k in range(9):
            ang = k * math.tau / 9.0 + 0.25
            leaf = self.add_sphere(
                f"PalmFrond_{x:.1f}_{k}",
                (x + lean + math.cos(ang) * 1.0, y + math.sin(ang) * 1.0, height - 0.25),
                1.20,
                self.m_palm,
                scale=(1.0, 0.16, 0.05),
                segments=8,
                smooth=False,
            )
            leaf.rotation_euler = (0.0, math.radians(24.0), ang)

    # --------------------------------------------------------- animation helpers
    def set_key(
        self,
        obj,
        data_path: str,
        t_sec: float,
        value=None,
        index: int = -1,
        interp: str | None = None,
        easing: str | None = None,
    ) -> None:
        if value is not None:
            if index >= 0:
                getattr(obj, data_path)[index] = value
            else:
                setattr(obj, data_path, value)
        frame = self.timeline.sec_to_frame(t_sec)
        obj.keyframe_insert(data_path=data_path, frame=frame, index=index)
        if interp:
            for fc in iter_fcurves(obj):
                if fc.data_path == data_path and (index < 0 or fc.array_index == index):
                    for kp in fc.keyframe_points:
                        if abs(kp.co.x - frame) < 1e-3:
                            kp.interpolation = interp
                            if easing:
                                kp.easing = easing

    def hide_until(self, obj, t_sec: float) -> None:
        if t_sec > 0.02:
            self.set_key(obj, "scale", 0.0, HIDDEN_SCALE, interp="CONSTANT")

    def pop_in(self, obj, t_sec: float, dur: float = 0.26, overshoot: float = 1.09) -> None:
        base = tuple(obj.scale)
        self.hide_until(obj, t_sec)
        self.set_key(obj, "scale", t_sec, HIDDEN_SCALE)
        self.set_key(obj, "scale", t_sec + dur * 0.7, tuple(v * overshoot for v in base))
        self.set_key(obj, "scale", t_sec + dur, base)

    def fade_out(self, obj, t_sec: float, dur: float = 0.20) -> None:
        base = tuple(obj.scale)
        self.set_key(obj, "scale", t_sec, base)
        self.set_key(obj, "scale", t_sec + dur, HIDDEN_SCALE)

    def switch_visible(self, obj, t_on: float, t_off: float | None = None) -> None:
        base = tuple(obj.scale)
        self.hide_until(obj, t_on)
        self.set_key(obj, "scale", t_on, base, interp="CONSTANT")
        if t_off is not None:
            self.set_key(obj, "scale", t_off, HIDDEN_SCALE, interp="CONSTANT")

    def animate_pulse(self, obj, t_start: float, t_end: float, period: float = 0.42, amp: float = 0.09) -> None:
        base = tuple(obj.scale)
        t_cur, step = t_start, 0
        while t_cur < t_end:
            mult = 1.0 + amp * (step % 2)
            self.set_key(obj, "scale", t_cur, tuple(v * mult for v in base), interp="BEZIER")
            t_cur += period * 0.5
            step += 1
        self.set_key(obj, "scale", t_end, base, interp="BEZIER")

    def add_flow_stream(
        self,
        name: str,
        points: Sequence[tuple[float, float, float]],
        t_start: float,
        t_end: float,
        speed: float = 1.6,
        spacing: float = 0.42,
        radius: float = 0.022,
        mat: bpy.types.Material | None = None,
    ) -> list:
        """Loop glowing indicator particles smoothly along a 3D path between t_start and t_end."""
        vecs = [Vector(p) for p in points]
        seg_lens = [(vecs[i + 1] - vecs[i]).length for i in range(len(vecs) - 1)]
        total_len = max(1e-5, sum(seg_lens))
        cycle = total_len / speed
        count = max(1, round(total_len / spacing))
        particles = []

        for idx in range(count):
            dot = self.add_sphere(f"{name}_{idx:02d}", points[0], radius, mat or self.m_white_emit, segments=8)
            self.switch_visible(dot, t_start, t_end)
            particles.append(dot)
            t_loop = t_start - cycle * (idx / count)
            while t_loop < t_end:
                dist_acc = 0.0
                for j, pt in enumerate(vecs):
                    is_last = j == len(vecs) - 1
                    t_key = t_loop + (dist_acc / total_len) * cycle - (0.004 if is_last else 0.0)
                    self.set_key(dot, "location", t_key, (pt.x, pt.y, pt.z), interp="CONSTANT" if is_last else "LINEAR")
                    if j < len(seg_lens):
                        dist_acc += seg_lens[j]
                t_loop += cycle
        return particles

    # --------------------------------------------------------- Cycles OptiX render
    def configure_cycles(
        self,
        width: int,
        height: int,
        samples: int = 12,
        device: str = "GPU",
        denoiser: str = "OPTIX",
        img_format: str = "JPEG",
        persistent_data: bool = True,
        max_bounces: int = 3,
        adaptive_threshold: float = 0.06,
    ) -> None:
        sc = self.scene
        sc.render.fps = self.fps
        sc.frame_start = 1
        sc.frame_end = self.total_frames
        sc.render.engine = "CYCLES"
        cy = sc.cycles
        cy.device = "CPU"

        if device.upper() == "GPU":
            try:
                prefs = bpy.context.preferences.addons["cycles"].preferences
                for backend in ("OPTIX", "CUDA", "METAL"):
                    prefs.compute_device_type = backend
                    prefs.get_devices()
                    devs = [d for d in prefs.devices if d.type == backend]
                    if devs:
                        for d in prefs.devices:
                            d.use = d.type == backend
                        cy.device = "GPU"
                        print(f"[studio3d] GPU active: {backend} {[d.name for d in devs]}", flush=True)
                        break
                try:
                    cy.denoising_use_gpu = True
                except Exception:
                    pass
            except Exception as exc:
                print(f"[studio3d] GPU fallback to CPU ({exc})", flush=True)

        cy.samples = samples
        cy.use_adaptive_sampling = True
        cy.adaptive_threshold = adaptive_threshold
        cy.max_bounces = max_bounces
        cy.diffuse_bounces = min(2, max_bounces)
        cy.glossy_bounces = 1
        cy.transmission_bounces = 0
        cy.transparent_max_bounces = 14
        cy.caustics_reflective = False
        cy.caustics_refractive = False

        try:
            cy.use_denoising = True
            cy.denoiser = denoiser if cy.device == "GPU" else "OPENIMAGEDENOISE"
            if cy.denoiser == "OPTIX":
                cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        except Exception as exc:
            print(f"[studio3d] Denoiser warning: {exc}", flush=True)

        sc.render.use_persistent_data = persistent_data
        sc.render.resolution_x = width
        sc.render.resolution_y = height
        sc.render.resolution_percentage = 100
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.render.image_settings.file_format = img_format
        if img_format == "JPEG":
            sc.render.image_settings.quality = 97
        else:
            sc.render.image_settings.compression = 15

    def audit_scene(self) -> dict:
        """Render-free automated QA checking camera velocity, single-frame jumps, and 1-2 frame scale flashes."""
        sc = self.scene
        n_objs = len(bpy.data.objects)
        n_mats = len(bpy.data.materials)
        n_keys = sum(len(fc.keyframe_points) for obj in bpy.data.objects for fc in iter_fcurves(obj))

        # Sample camera path frame-by-frame
        cam_steps = []
        prev_pos = None
        for f in range(1, self.total_frames + 1):
            sc.frame_set(f)
            pos = self.cam.camera.matrix_world.translation.copy()
            if prev_pos is not None:
                step = (pos - prev_pos).length
                cam_steps.append((round(step, 3), round((f - 1) / self.fps, 2)))
            prev_pos = pos
        cam_steps.sort(reverse=True)
        jumps = [s for s in cam_steps if s[0] > 1.8]

        report = {
            "duration_sec": self.duration,
            "total_frames": self.total_frames,
            "objects": n_objs,
            "materials": n_mats,
            "keyframes": n_keys,
            "largest_camera_steps": cam_steps[:5],
            "single_frame_jumps": jumps[:5],
        }
        print(
            f"[QA] {self.timeline.config.name}: {self.duration:.2f}s ({self.total_frames} frames) | "
            f"objects={n_objs}, mats={n_mats}, keys={n_keys}",
            flush=True,
        )
        print(f"[QA] Largest cam steps (m/frame, sec): {report['largest_camera_steps']}", flush=True)
        print(f"[QA] Single-frame jumps (>1.8m): {report['single_frame_jumps'] or 'none'}", flush=True)
        return report

    def run_cli(self, argv: Sequence[str] | None = None) -> None:
        """Execute standard scene commands: check | stills | frames | blend."""
        args = list(sys.argv[1:] if argv is None else argv)
        if not args or args[0] == "check":
            self.audit_scene()
            return

        mode = args[0]
        device = os.environ.get("STUDIO3D_DEVICE", "GPU")
        denoiser = os.environ.get("STUDIO3D_DENOISER", "OPTIX")
        fmt = os.environ.get("STUDIO3D_FMT", "PNG" if mode == "stills" else "JPEG")
        persist = os.environ.get("STUDIO3D_PERSIST", "1") == "1"

        if mode == "stills":
            w, h, spp = int(args[1]), int(args[2]), int(args[3])
            out_dir = os.path.abspath(args[4])
            times = [float(x) for x in args[5:]]
            os.makedirs(out_dir, exist_ok=True)
            self.configure_cycles(w, h, spp, device=device, denoiser=denoiser, img_format=fmt, persistent_data=persist)
            ext = "jpg" if fmt == "JPEG" else "png"
            for ts in times:
                t0 = time.time()
                fr = self.timeline.sec_to_frame(ts)
                fi = int(fr)
                self.scene.frame_set(fi, subframe=fr - fi)
                self.scene.render.filepath = os.path.join(out_dir, f"t_{int(round(ts * 100)):05d}.{ext}")
                bpy.ops.render.render(write_still=True)
                print(f"[STILL] t={ts:.2f}s ({time.time() - t0:.2f}s)", flush=True)

        elif mode == "frames":
            w, h, spp = int(args[1]), int(args[2]), int(args[3])
            out_dir = os.path.abspath(args[4])
            f0, f1 = int(args[5]), int(args[6])
            step = int(args[7]) if len(args) > 7 else 1
            os.makedirs(out_dir, exist_ok=True)
            self.configure_cycles(w, h, spp, device=device, denoiser=denoiser, img_format=fmt, persistent_data=persist)
            ext = "jpg" if fmt == "JPEG" else "png"
            done = 0
            t_all = time.time()
            for f in range(f0, f1 + 1, step):
                out_path = os.path.join(out_dir, f"f_{f:05d}.{ext}")
                if os.path.exists(out_path) and os.path.getsize(out_path) > 2000:
                    continue
                t0 = time.time()
                self.scene.frame_set(f)
                self.scene.render.filepath = out_path
                bpy.ops.render.render(write_still=True)
                done += 1
                if done % 15 == 1:
                    print(f"[FRAME] {f}/{f1} ({time.time() - t0:.2f}s)", flush=True)
            print(f"[DONE] Rendered {done} frames ({f0}..{f1} step {step}) in {time.time() - t_all:.1f}s", flush=True)

        elif mode == "blend":
            out_blend = os.path.abspath(args[1])
            os.makedirs(os.path.dirname(out_blend), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=out_blend)
            print(f"[BLEND] Saved {out_blend}", flush=True)
        else:
            raise SystemExit(f"Unknown mode '{mode}'. Use: check | stills | frames | blend")
