"""Standalone clean-room example scene: Cara Kerja AC Split 1 PK Realistis (studio3d engine).

Demonstrates:
  - 1.0 unit = 1 meter true-to-life 1 PK AC proportions (0.98x0.34x0.28m indoor, 0.88x0.62x0.36m outdoor)
  - Original casual Indonesian educator figure (add_educator)
  - Everyday Indonesian terminology ('freon', 'pipa tembaga', 'evaporator', 'kompresor', 'kondensor', 'katup ekspansi')
  - Smooth macro zoom camera choreography -> isometric hero diorama pullback
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from studio3d.scene import DioramaStudio, catmull_rom
from studio3d.timeline import Timeline


def build_scene() -> DioramaStudio:
    tl = Timeline(HERE)
    st = DioramaStudio(tl, seed=21)
    T = tl.cue
    DUR = tl.total_duration

    # 1. Word-synced cues
    t_s01, t_es = T("S01"), T("S01", "es")
    t_s02 = T("S02")
    t_s03, t_freon = T("S03"), T("S03", "freon")
    t_s04, t_evap, t_serap = T("S04"), T("S04", "evaporator"), T("S04", "menyerap")
    t_s05, t_blow, t_sejuk = T("S05"), T("S05", "blower"), T("S05", "sejuk")
    t_s06, t_komp = T("S06"), T("S06", "kompresor")
    t_s07, t_kipas = T("S07"), T("S07", "kipas")
    t_s08, t_eksp = T("S08"), T("S08", "ekspansi")
    t_s09 = T("S09")

    # 2. Scene Materials
    m_wall_in  = st.make_material("WallIn", (0.95, 0.91, 0.83), roughness=0.86)
    m_wall_out = st.make_material("WallOut", (0.87, 0.85, 0.79), roughness=0.88)
    m_wall_cut = st.make_material("WallCut", (0.75, 0.73, 0.69), roughness=0.90)
    m_floor_in = st.make_material("FloorIn", (0.86, 0.82, 0.74), roughness=0.64, specular=0.4)
    m_terrace  = st.make_material("Terrace", (0.68, 0.67, 0.64), roughness=0.88)
    m_roof     = st.make_material("RoofTile", (0.66, 0.26, 0.14), roughness=0.78)
    m_glass    = st.make_material("WinGlass", (0.50, 0.80, 0.98), roughness=0.10, specular=0.85)
    m_bed      = st.make_material("BedWood", (0.54, 0.35, 0.19), roughness=0.72)
    m_blanket  = st.make_material("Blanket", (0.24, 0.52, 0.80), roughness=0.90)
    m_pillow   = st.make_material("Pillow", (0.96, 0.97, 0.98), roughness=0.88)
    m_lamp     = st.make_material("LampShade", (0.98, 0.90, 0.68), roughness=0.60, emission=0.35)
    m_cord     = st.make_material("PowerCord", (0.14, 0.14, 0.16), roughness=0.60)

    m_ac_w     = st.make_material("ACWhite", (0.96, 0.97, 0.99), roughness=0.25, specular=0.60)
    m_ac_in    = st.make_material("ACInner", (0.18, 0.22, 0.28), roughness=0.75)
    m_out_box  = st.make_material("OutBox", (0.85, 0.84, 0.80), roughness=0.52, specular=0.42)
    m_out_in   = st.make_material("OutInner", (0.24, 0.26, 0.30), roughness=0.78)
    m_comp     = st.make_material("Compressor", (0.08, 0.09, 0.11), roughness=0.30, specular=0.68)
    m_copper   = st.make_material("Copper", (0.86, 0.45, 0.22), roughness=0.26, specular=0.78)
    m_brass    = st.make_material("Brass", (0.92, 0.74, 0.24), roughness=0.24, specular=0.80)
    m_fan_in   = st.make_material("FanIn", (0.32, 0.76, 0.94), roughness=0.32, specular=0.50)
    m_fan_out  = st.make_material("FanOut", (0.24, 0.34, 0.48), roughness=0.36, specular=0.50)
    m_fin      = st.make_material("AluFin", (0.72, 0.76, 0.80), roughness=0.32, specular=0.62)

    m_evap = st.make_material("EvapCoil", (0.80, 0.44, 0.22), roughness=0.26, specular=0.75)
    st.animate_color(m_evap, [(0.0, (0.80, 0.44, 0.22), 1.0), (t_s04 - 0.2, (0.80, 0.44, 0.22), 1.0), (t_evap + 0.4, (0.12, 0.82, 1.00), 1.0)])
    m_cond = st.make_material("CondCoil", (0.85, 0.46, 0.22), roughness=0.26, specular=0.75)
    st.animate_color(m_cond, [(0.0, (0.85, 0.46, 0.22), 1.0), (t_s06 - 0.1, (0.85, 0.46, 0.22), 1.0), (t_komp + 0.5, (1.00, 0.26, 0.08), 1.0)])

    m_cold = st.make_material("ColdGlow", (0.12, 0.88, 1.00), roughness=0.18, emission=1.30)
    m_hot  = st.make_material("HotGlow", (1.00, 0.28, 0.08), roughness=0.22, emission=1.35)
    m_warm = st.make_material("WarmGlow", (1.00, 0.62, 0.12), roughness=0.22, emission=1.15)
    m_pcold = st.make_material("PipeCold", (0.28, 0.78, 0.96), roughness=0.28, specular=0.62)
    m_phot  = st.make_material("PipeHot", (0.92, 0.34, 0.16), roughness=0.28, specular=0.62)
    m_red_p  = st.make_material("PlateRed", (0.82, 0.16, 0.12), roughness=0.5)
    m_blue_p = st.make_material("PlateBlue", (0.08, 0.44, 0.82), roughness=0.5)
    m_orng_p = st.make_material("PlateOrng", (0.86, 0.38, 0.08), roughness=0.5)
    m_cyan_p = st.make_material("PlateCyan", (0.06, 0.54, 0.66), roughness=0.5)

    # 3. Ground, Terrace, Lawn & Foliage
    st.add_box("SoilMain", -45.0, 55.0, 0.0, 55.0, -14.0, -0.32, st.m_soil)
    st.add_box("HouseSlab", -4.55, 2.35, 0.0, 3.45, -0.32, 0.00, st.m_concrete)
    st.add_box("SoilL", -45.0, -4.55, 0.0, 55.0, -0.32, 0.00, st.m_soil)
    st.add_box("SoilR", 2.35, 55.0, 0.0, 55.0, -0.32, 0.00, st.m_soil)
    st.add_box("LawnL", -45.0, -4.55, 0.0, 50.0, 0.00, 0.03, st.m_lawn)
    st.add_box("LawnR", 2.35, 55.0, 0.0, 50.0, 0.00, 0.03, st.m_lawn)
    st.add_box("LawnBk", -4.55, 2.35, 3.45, 50.0, 0.00, 0.03, st.m_lawn)
    st.add_box("Terrace", 0.00, 2.35, 0.0, 3.45, 0.00, 0.06, m_terrace)

    for tx, ty, th, tr in ((-7.2, 6.8, 3.1, 1.4), (4.6, 5.8, 3.1, 1.4), (8.2, 8.8, 3.5, 1.6), (12.0, 7.5, 3.3, 1.5)):
        st.add_foliage_tree(tx, ty, th, tr)
    for px, py, ph, pl in ((-5.8, 10.5, 5.2, -0.4), (6.5, 10.4, 5.4, 0.5), (10.5, 9.8, 5.0, 0.4)):
        st.add_tropical_palm(px, py, ph, pl)

    # 4. Realistic 4.4m x 3.25m x 3.05m Indonesian Bedroom Cutaway
    st.add_box("RoomFloor", -4.40, 0.00, 0.00, 3.25, 0.00, 0.08, m_floor_in)
    st.add_box("RoomBack", -4.40, 0.00, 3.08, 3.26, 0.08, 3.08, m_wall_in)
    st.add_box("RoomLeft", -4.40, -4.22, 0.00, 3.26, 0.08, 3.08, m_wall_cut)
    st.add_box("RoomCeil", -4.40, 0.04, 0.00, 3.26, 3.02, 3.16, m_wall_cut)
    st.add_box("DivIn", -0.20, -0.09, 0.00, 3.08, 0.08, 3.02, m_wall_in)
    st.add_box("DivOut", -0.09, 0.02, 0.00, 3.08, 0.08, 3.02, m_wall_out)
    st.add_box("YardWall", 0.00, 2.20, 3.08, 3.26, 0.06, 2.75, m_wall_out)
    st.add_box("YardCap", 0.00, 2.24, 3.04, 3.30, 2.75, 2.83, st.m_concrete)

    st.add_prism_xz("RoofGable", [(-4.40, 3.14), (-2.18, 4.18), (0.04, 3.14)], 3.08, 3.26, m_wall_out)
    st.add_prism_xz("RoofPitch", [(-4.82, 3.10), (-2.18, 4.40), (0.46, 3.10), (0.26, 3.00), (-2.18, 4.18), (-4.62, 3.00)], -0.25, 3.60, m_roof)

    # Window + Bed + Nightstand + Lamp
    st.add_box("WinFrame", -3.88, -2.52, 3.02, 3.09, 1.32, 2.28, m_ac_w)
    st.add_box("WinGlass", -3.80, -2.60, 3.00, 3.05, 1.40, 2.20, m_glass)
    st.add_box("WinBarV", -3.23, -3.17, 2.98, 3.05, 1.40, 2.20, m_ac_w)
    st.add_box("WinBarH", -3.80, -2.60, 2.98, 3.05, 1.77, 1.83, m_ac_w)
    st.add_box("BedBase", -4.08, -2.52, 1.15, 3.04, 0.08, 0.38, m_bed)
    st.add_box("BedHead", -4.08, -2.52, 2.94, 3.06, 0.38, 0.96, m_bed)
    st.add_box("Mattress", -4.03, -2.57, 1.20, 2.92, 0.38, 0.56, m_pillow)
    st.add_box("Blanket", -4.05, -2.55, 1.18, 2.42, 0.42, 0.60, m_blanket)
    st.add_box("Pillow", -3.78, -2.82, 2.50, 2.88, 0.56, 0.72, m_pillow)
    st.add_box("Nightstand", -2.44, -1.96, 2.56, 3.04, 0.08, 0.54, m_bed)
    st.add_cylinder("LampBase", (-2.20, 2.80, 0.54), 0.06, 0.16, st.m_steel, segments=12)
    st.add_cylinder("LampShade", (-2.20, 2.80, 0.68), 0.12, 0.18, m_lamp, segments=14, top_radius=0.07)

    # Original 1.72m Educator Figure
    _, arm_l, arm_r = st.add_educator("Educator", (-1.55, 1.55, 0.08))
    st.wave_arms((arm_l, arm_r), t_s01 + 0.3, t_es + 0.5, angle_deg=135)
    st.wave_arms((arm_l, arm_r), t_sejuk, t_s06 - 0.2, angle_deg=152)
    st.wave_arms((arm_l, arm_r), t_s09 + 0.2, DUR - 0.25, angle_deg=152)

    tag_hot = st.add_callout("TagHot", [("35°C", 0.18, st.m_yellow_emit), ("PANAS!", 0.14, st.m_white_emit)], (-2.82, 1.35, 2.48), m_red_p)
    st.pop_in(tag_hot, t_s01 + 0.2); st.fade_out(tag_hot, t_blow - 0.1)
    tag_cool = st.add_callout("TagCool", [("20°C", 0.18, st.m_white_emit), ("SEJUK!", 0.14, st.m_yellow_emit)], (-2.82, 1.35, 2.48), m_blue_p)
    st.pop_in(tag_cool, t_sejuk - 0.15); st.fade_out(tag_cool, t_s06 - 0.1)

    # 5. True-to-Life 1 PK Indoor AC Split (0.98m x 0.34m x 0.28m flush on back wall)
    st.add_box("ACInTop", -1.32, -0.34, 2.80, 3.08, 2.67, 2.70, m_ac_w)
    st.add_box("ACInBot", -1.32, -0.34, 2.80, 3.08, 2.36, 2.39, m_ac_w)
    st.add_box("ACInL", -1.32, -1.28, 2.80, 3.08, 2.39, 2.67, m_ac_w)
    st.add_box("ACInR", -0.38, -0.34, 2.80, 3.08, 2.39, 2.67, m_ac_w)
    st.add_box("ACInBack", -1.28, -0.38, 3.04, 3.08, 2.39, 2.67, m_ac_in)
    louver = st.add_box("ACLouver", -1.26, -0.40, 2.78, 2.86, 2.35, 2.37, m_ac_w, pivot="center")
    louver.rotation_euler = (math.radians(-30), 0.0, 0.0)
    st.add_box("ACSocket", -0.30, -0.22, 3.05, 3.08, 2.14, 2.22, m_ac_w)
    st.add_tube("ACCord", [(-0.36, 3.05, 2.40), (-0.28, 3.05, 2.32), (-0.26, 3.05, 2.18)], 0.008, m_cord, bevel_res=3)

    for i in range(4):
        c = st.add_cylinder(f"EvapTube_{i}", (-1.26, 2.91, 2.52 + i * 0.036), 0.013, 0.86, m_evap, segments=14)
        c.rotation_euler = (0.0, math.radians(90), 0.0)
    for fx in (-1.20, -1.08, -0.96, -0.84, -0.72, -0.60, -0.48):
        st.add_box(f"EvapFin_{fx}", fx - 0.005, fx + 0.005, 2.85, 2.97, 2.50, 2.66, m_fin)

    blower = st.add_group("BlowerRoot", (-0.83, 2.94, 2.44))
    bc = st.add_cylinder("BlowerCore", (-0.42, 0.0, 0.0), 0.026, 0.84, m_fan_in, segments=14, parent=blower)
    bc.rotation_euler = (0.0, math.radians(90), 0.0)
    for k in range(6):
        ang = k * math.tau / 6.0
        bl = st.add_box(f"BlowerBl_{k}", -0.41, 0.41, -0.004, 0.004, 0.024, 0.048, m_ac_w, pivot="center", parent=blower)
        bl.location = (0.0, math.sin(ang) * 0.034, math.cos(ang) * 0.034)
        bl.rotation_euler = (ang, 0.0, 0.0)
    st.set_key(blower, "rotation_euler", 0.0, 0.0, index=0, interp="LINEAR")
    st.set_key(blower, "rotation_euler", DUR, math.radians(360.0 * 3.2 * DUR), index=0, interp="LINEAR")

    for k, hx in enumerate((-1.15, -0.83, -0.52)):
        st.add_flow_stream(f"RoomHeat_{k}", [(hx, 2.65, 1.35), (hx + 0.05, 2.75, 2.05), (hx, 2.82, 2.58)], t_s01 + 0.2 + k * 0.12, t_s05 - 0.1, speed=1.15, spacing=0.58, radius=0.028, mat=m_hot)
    for k, cx in enumerate((-1.18, -0.95, -0.72, -0.48)):
        cpts = catmull_rom([(cx, 2.78, 2.36), (cx - 0.25, 2.45, 2.02), (cx - 0.65, 1.95, 1.62), (cx - 1.05, 1.55, 1.15)], subdivisions=5)
        st.add_flow_stream(f"ColdAir_{k}", cpts, t_serap + k * 0.10, DUR, speed=1.65, spacing=0.58, radius=0.028, mat=m_cold)

    # 6. Twin Copper Freon Pipes through Wall Sleeve
    slv = st.add_cylinder("WallSleeve", (-0.23, 2.98, 2.50), 0.068, 0.28, st.m_pvc, segments=14)
    slv.rotation_euler = (0.0, math.radians(90), 0.0)
    for cz in (2.22, 1.85):
        st.add_box(f"Clamp_{cz}", 0.14, 0.34, 2.93, 3.08, cz - 0.02, cz + 0.02, st.m_steel)

    hot_pts = [(-0.35, 2.98, 2.56), (0.18, 2.98, 2.56), (0.18, 2.98, 1.54), (1.14, 2.98, 1.54), (1.14, 2.94, 1.48)]
    st.add_cutaway_pipe("FreonHotPipe", hot_pts, radius=0.024, mat=m_phot)
    st.add_flow_stream("FreonHotFlow", [(x, 2.93, z) for x, _, z in hot_pts], t_s02, DUR, speed=1.55, spacing=0.40, radius=0.018, mat=m_hot)

    cold_pts = [(0.56, 2.94, 1.24), (0.28, 2.94, 1.24), (0.28, 2.94, 2.46), (-0.35, 2.94, 2.46)]
    st.add_cutaway_pipe("FreonColdPipe", cold_pts, radius=0.024, mat=m_pcold)
    st.add_flow_stream("FreonColdFlow", [(x, 2.89, z) for x, _, z in cold_pts], t_s02, DUR, speed=1.55, spacing=0.40, radius=0.018, mat=m_cold)

    # 7. True-to-Life 1 PK Outdoor AC Condenser (0.88m x 0.62m x 0.36m bolted on steel L-brackets)
    for bx in (0.58, 1.22):
        st.add_box(f"BrkArm_{bx}", bx - 0.02, bx + 0.02, 2.74, 3.08, 1.11, 1.15, st.m_steel)
        st.add_box(f"BrkWall_{bx}", bx - 0.02, bx + 0.02, 3.04, 3.08, 0.78, 1.11, st.m_steel)
        st.add_tube(f"BrkDiag_{bx}", [(bx, 2.82, 1.11), (bx, 3.06, 0.82)], 0.015, st.m_steel, bevel_res=3)

    st.add_box("OutTop", 0.46, 1.34, 2.72, 3.08, 1.74, 1.77, m_out_box)
    st.add_box("OutBot", 0.46, 1.34, 2.72, 3.08, 1.15, 1.18, m_out_box)
    st.add_box("OutL", 0.46, 0.49, 2.72, 3.08, 1.18, 1.74, m_out_box)
    st.add_box("OutR", 1.31, 1.34, 2.72, 3.08, 1.18, 1.74, m_out_box)
    st.add_box("OutBack", 0.49, 1.31, 3.04, 3.08, 1.18, 1.74, m_out_in)
    st.add_box("OutMid", 0.96, 0.99, 2.76, 3.04, 1.18, 1.74, m_out_in)

    comp = st.add_group("CompRoot", (1.14, 2.91, 1.18))
    st.add_cylinder("CompBody", (0.0, 0.0, 0.0), 0.105, 0.26, m_comp, segments=22, parent=comp)
    st.add_sphere("CompDome", (0.0, 0.0, 0.26), 0.105, m_comp, scale=(1.0, 1.0, 0.45), segments=20, parent=comp)
    st.add_cylinder("CompAccum", (-0.095, -0.02, 0.04), 0.038, 0.15, m_comp, segments=14, parent=comp)
    disc_pts = [(1.14, 2.88, 1.48), (1.14, 2.88, 1.68), (0.92, 2.88, 1.68)]
    st.add_cutaway_pipe("DiscPipe", disc_pts, radius=0.018, mat=m_hot, show_bore=False)
    st.add_flow_stream("DiscFlow", [(x, 2.84, z) for x, _, z in disc_pts], t_s06 - 0.1, DUR, speed=1.1, spacing=0.18, radius=0.018, mat=m_hot)
    st.animate_pulse(comp, t_s06, t_s07 - 0.1, period=0.38, amp=0.08)

    for i in range(6):
        ct = st.add_cylinder(f"CondTube_{i}", (0.51, 3.00, 1.24 + i * 0.084), 0.013, 0.43, m_cond, segments=14)
        ct.rotation_euler = (0.0, math.radians(90), 0.0)
    for fx in (0.56, 0.67, 0.78, 0.89):
        st.add_box(f"CondFin_{fx}", fx - 0.005, fx + 0.005, 2.95, 3.03, 1.21, 1.71, m_fin)

    fan = st.add_group("OutFanRoot", (0.73, 2.84, 1.48))
    hub = st.add_cylinder("OutFanHub", (0.0, 0.02, 0.0), 0.048, 0.045, m_comp, segments=18, parent=fan)
    hub.rotation_euler = (math.radians(90), 0.0, 0.0)
    for k in range(3):
        piv = st.add_group(f"BladePiv_{k}", parent=fan)
        piv.rotation_euler = (0.0, k * math.tau / 3.0, 0.0)
        bl = st.add_box(f"Blade_{k}", -0.048, 0.048, -0.008, 0.008, 0.035, 0.185, m_fan_out, pivot="bottom", parent=piv)
        bl.rotation_euler = (0.0, 0.0, math.radians(22))
    st.set_key(fan, "rotation_euler", 0.0, 0.0, index=1, interp="LINEAR")
    st.set_key(fan, "rotation_euler", DUR, math.radians(360.0 * 3.4 * DUR), index=1, interp="LINEAR")

    for k, ez in enumerate((1.34, 1.49, 1.64)):
        ex_pts = catmull_rom([(0.76, 2.72, ez), (1.12, 2.48, ez + 0.06), (1.68, 2.38, ez + 0.16), (2.25, 2.38, ez + 0.28)], subdivisions=5)
        st.add_flow_stream(f"Exhaust_{k}", ex_pts, t_s07 - 0.2 + k * 0.10, DUR, speed=1.45, spacing=0.38, radius=0.028, mat=m_hot)

    exp = st.add_group("ExpRoot", (0.56, 2.78, 1.30))
    st.add_cylinder("ExpValve", (0.0, 0.0, -0.04), 0.032, 0.075, m_brass, segments=16, parent=exp)
    st.add_helix_coil("ExpCoil", (0.56, 2.78, 1.31), rx=0.048, ry=0.030, height=0.15, turns=4.0, wire_radius=0.009, mat=m_copper)
    st.add_flow_stream("ExpIn", [(0.62, 2.72, 1.42), (0.56, 2.72, 1.35)], t_s08 - 0.2, DUR, speed=0.65, spacing=0.09, radius=0.017, mat=m_warm)
    st.add_flow_stream("ExpOut", [(0.56, 2.72, 1.26), (0.56, 2.72, 1.22), (0.40, 2.72, 1.24)], t_s08 - 0.1, DUR, speed=0.75, spacing=0.09, radius=0.019, mat=m_cold)
    st.animate_pulse(exp, t_s08, t_s09 - 0.1, period=0.45, amp=0.14)

    # 8. Diegetic Callout Labels
    labels = [
        ("TagFreon", [("FREON", 0.11, st.m_yellow_emit), ("PIPA TEMBAGA", 0.085, st.m_white_emit)], (0.68, 2.62, 2.38), st.m_plate, t_freon - 0.15, t_s04 - 0.1),
        ("TagEvap",  [("EVAPORATOR", 0.075, st.m_yellow_emit), ("SERAP PANAS", 0.060, st.m_white_emit)], (-0.83, 2.68, 2.86), m_blue_p, t_evap - 0.15, t_s05 - 0.1),
        ("TagBlow",  [("KIPAS BLOWER", 0.095, st.m_white_emit), ("UDARA SEJUK", 0.075, st.m_yellow_emit)], (-0.88, 2.58, 2.85), m_cyan_p, t_blow - 0.15, t_s06 - 0.1),
        ("TagComp",  [("KOMPRESOR", 0.072, st.m_yellow_emit), ("TEKANAN TINGGI", 0.054, st.m_white_emit)], (1.05, 2.62, 1.96), m_red_p, t_komp - 0.15, t_s07 - 0.1),
        ("TagCond",  [("KONDENSOR", 0.082, st.m_yellow_emit), ("BUANG PANAS", 0.064, st.m_white_emit)], (0.90, 2.62, 1.99), m_orng_p, t_kipas - 0.15, t_s08 - 0.1),
        ("TagExp",   [("KATUP EKSPANSI", 0.062, st.m_yellow_emit), ("DINGIN LAGI!", 0.052, st.m_white_emit)], (0.68, 2.62, 1.92), m_blue_p, t_eksp - 0.15, t_s09 - 0.1),
    ]
    for nm, lines, pos, mat, t_on, t_off in labels:
        obj = st.add_callout(nm, lines, pos, mat)
        st.pop_in(obj, t_on); st.fade_out(obj, t_off)

    tag_in = st.add_callout("TagInEnd", [("INDOOR", 0.18, st.m_white_emit), ("SEJUK 20°C", 0.14, st.m_yellow_emit)], (-2.18, 2.20, 4.75), m_blue_p)
    tag_out = st.add_callout("TagOutEnd", [("OUTDOOR", 0.18, st.m_white_emit), ("BUANG PANAS", 0.14, st.m_yellow_emit)], (1.10, 2.20, 2.45), m_red_p)
    st.pop_in(tag_in, t_s09 + 0.1); st.pop_in(tag_out, t_s09 + 0.25)

    # 9. Smooth Camera Choreography (Wide Real-Scale -> Macro Cutaway -> Isometric Hero Outro)
    pose = st.cam.spherical_pose
    st.cam.add_shot(0.0,         t_s02 - 0.1, pose(88, 5, 7.6, (-2.15, 2.4, 1.55)), hard_cut=True)
    st.cam.add_shot(t_s02 - 0.1, t_s03 - 0.1, pose(90, 5, 10.6, (-1.20, 2.5, 1.62)), transition=1.1)
    st.cam.add_shot(t_s03 - 0.1, t_s04 - 0.1, pose(84, 4, 4.4, (0.56, 2.8, 1.92)), transition=1.0)
    st.cam.add_shot(t_s04 - 0.1, t_s05 - 0.1, pose(90, 2, 2.25, (-0.83, 2.85, 2.55)), transition=0.9)
    st.cam.add_shot(t_s05 - 0.1, t_s06 - 0.1, pose(89, 5, 7.3, (-2.00, 2.4, 1.62)), transition=0.9)
    st.cam.add_shot(t_s06 - 0.1, t_s07 - 0.1, pose(90, 3, 2.10, (1.00, 2.82, 1.50)), transition=1.0)
    st.cam.add_shot(t_s07 - 0.1, t_s08 - 0.1, pose(87, 4, 2.85, (0.96, 2.82, 1.52)), transition=0.9)
    st.cam.add_shot(t_s08 - 0.1, t_s09 - 0.1, pose(90, 2, 1.88, (0.68, 2.78, 1.44)), transition=0.9)
    st.cam.add_shot(t_s09 - 0.1, DUR, pose(75, 16, 11.8, (-1.05, 2.4, 1.70)), end_pose=pose(68, 18, 13.0, (-1.20, 2.4, 1.70)), transition=1.4)
    return st


if __name__ == "__main__":
    build_scene().run_cli()
