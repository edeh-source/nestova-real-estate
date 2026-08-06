#!/usr/bin/env python3
"""
==========================================================
HOPE FARM IBADAN — SOLAR PV PROJECT
Professional LibreCAD DXF Drawing Generator
==========================================================

Generates two professional engineering drawings in DXF format:
  1. HOPE_FARM_SITE_PLAN.dxf
     — Overall compound layout with zones and panel counts
  2. HOPE_FARM_INVERTER_DETAIL.dxf
     — Inverter Building: 64-panel layout, 6 strings,
       cable routing, Y-branches, MPPT connections

Compatible with LibreCAD, AutoCAD, BricsCAD, and all
DXF-compatible CAD software.

Project : Hope Farm Solar PV Installation (~544 panels)
Location: Hope Farm, Ibadan, Nigeria
System  : ~270 kWp (estimated)
"""

import ezdxf
from ezdxf.enums import TextEntityAlignment
import math
import os
import sys

# ============================================================
# OUTPUT DIRECTORY
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = SCRIPT_DIR

# ============================================================
# PANEL SPECIFICATIONS  (typical 500 W monocrystalline)
# All dimensions in millimetres (mm)
# ============================================================
PANEL_W  = 1134    # width
PANEL_H  = 2278    # height / length
PANEL_GAP = 30     # gap between adjacent panels

# ============================================================
# INVERTER BUILDING — GRID CONFIGURATION
# ============================================================
COLS_PER_HALF = 4          # columns each side of mid-roof
GRID_ROWS     = 9          # rows along building length
MID_ROOF_GAP  = 300        # gap at ridge line
WALKWAY_GAP   = 600        # extra gap for maintenance walkway (between row groups)
ROOF_OVERHANG = 600        # roof edge beyond outermost panels

# Calculated building envelope
HALF_WIDTH = COLS_PER_HALF * (PANEL_W + PANEL_GAP) - PANEL_GAP
TOTAL_PANEL_HEIGHT = GRID_ROWS * (PANEL_H + PANEL_GAP) - PANEL_GAP + WALKWAY_GAP
BUILDING_W = 2 * HALF_WIDTH + MID_ROOF_GAP + 2 * ROOF_OVERHANG
BUILDING_H = TOTAL_PANEL_HEIGHT + 2 * ROOF_OVERHANG

# Grid origin inside building
LEFT_X0  = ROOF_OVERHANG
RIGHT_X0 = ROOF_OVERHANG + HALF_WIDTH + MID_ROOF_GAP
GRID_Y0  = ROOF_OVERHANG

# ============================================================
# EXCLUDED POSITIONS  (X marks — structural obstructions)
# (row, col)  row 0 = south, row 8 = north
# Cols 0-3 = left half   Cols 4-7 = right half
# ============================================================
EXCLUDED = {
    (8, 0), (8, 1),         # NW corner — structural beam
    (7, 0),                 # below NW — vent stack
    (8, 6), (8, 7),         # NE corner — structural beam
    (7, 7),                 # below NE — vent stack
    (0, 0),                 # SW corner — gutter clash
    (0, 7),                 # SE corner — gutter clash
}
# 8 excluded ⇒ 72 − 8 = 64 active panels ✓

# ============================================================
# STRING ASSIGNMENTS
# ============================================================
def get_string(row, col):
    """Return string ID for position, or None if excluded."""
    if (row, col) in EXCLUDED:
        return None
    if col < COLS_PER_HALF:          # LEFT half
        if row >= 6:  return "S6"    # top (north) group
        if row >= 3:  return "S5"    # middle group
        return "S3"                  # bottom (south) group
    else:                            # RIGHT half
        if row >= 6:  return "S1"    # top group
        if row >= 3:  return "S2"    # middle group
        return "S4"                  # bottom group

# DXF colour indices
C_WHITE   = 7
C_RED     = 1
C_YELLOW  = 2
C_GREEN   = 3
C_CYAN    = 4
C_BLUE    = 5
C_MAGENTA = 6
C_GRAY    = 8

STRING_COLORS = {
    "S1": C_CYAN,
    "S2": C_GREEN,
    "S3": C_YELLOW,
    "S4": C_MAGENTA,
    "S5": C_BLUE,
    "S6": C_RED,
}

# Y-Branch → MPPT wiring table
YBRANCH = {
    "y1": {"strings": ("S1", "S2"), "mppt": "MPPT 1"},
    "y2": {"strings": ("S4", "S5"), "mppt": "MPPT 2"},
    "y3": {"strings": ("S3", "S6"), "mppt": "MPPT 3"},
}

# ============================================================
# HELPER: panel position → (x, y) in drawing coords
# ============================================================
def panel_xy(row, col, bldg_x, bldg_y):
    """Return lower-left corner of a panel at grid (row, col)."""
    if col < COLS_PER_HALF:
        px = bldg_x + LEFT_X0 + col * (PANEL_W + PANEL_GAP)
    else:
        adj = col - COLS_PER_HALF
        px = bldg_x + RIGHT_X0 + adj * (PANEL_W + PANEL_GAP)

    # Walkway gap inserted between row 2 and row 3
    if row < 3:
        py = bldg_y + GRID_Y0 + row * (PANEL_H + PANEL_GAP)
    elif row < 6:
        py = bldg_y + GRID_Y0 + row * (PANEL_H + PANEL_GAP) + WALKWAY_GAP // 2
    else:
        py = bldg_y + GRID_Y0 + row * (PANEL_H + PANEL_GAP) + WALKWAY_GAP
    return px, py


# ============================================================
# GENERIC DRAWING HELPERS
# ============================================================
def add_layer(doc, name, color=C_WHITE, lineweight=25):
    layer = doc.layers.add(name)
    layer.color = color
    layer.dxf.lineweight = lineweight


def setup_styles(doc):
    doc.styles.add("TITLE", font="Arial")
    doc.styles.add("LABEL", font="Arial")
    doc.styles.add("NOTES", font="Arial Narrow")


def rect(msp, x, y, w, h, layer="0", color=None):
    a = {"layer": layer}
    if color is not None:
        a["color"] = color
    msp.add_lwpolyline(
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
        dxfattribs=a,
        close=True,
    )


def txt(msp, text, x, y, h=100, layer="TEXT", color=None,
        rot=0, align="LEFT", style="LABEL"):
    a = {"layer": layer, "style": style, "rotation": rot}
    if color is not None:
        a["color"] = color
    t = msp.add_text(text, height=h, dxfattribs=a)
    if align == "CENTER":
        t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    elif align == "RIGHT":
        t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_RIGHT)
    else:
        t.set_placement((x, y))


def x_mark(msp, cx, cy, size, layer="PANELS_EXCLUDED", color=C_RED):
    s = size / 2
    a = {"layer": layer, "color": color}
    msp.add_line((cx - s, cy - s), (cx + s, cy + s), dxfattribs=a)
    msp.add_line((cx - s, cy + s), (cx + s, cy - s), dxfattribs=a)


def north_arrow(msp, x, y, size=500, layer="NORTH_ARROW"):
    a = {"layer": layer}
    # Shaft
    msp.add_line((x, y), (x, y + size), dxfattribs=a)
    # Head (filled triangle via polyline)
    hs = size * 0.22
    msp.add_lwpolyline(
        [(x, y + size), (x - hs / 2, y + size - hs), (x + hs / 2, y + size - hs)],
        dxfattribs=a, close=True,
    )
    # "N"
    txt(msp, "N", x, y + size + size * 0.18, h=size * 0.28,
        layer=layer, align="CENTER", style="TITLE")


def dashed_line(msp, x1, y1, x2, y2, dash=200, gap=120,
                layer="0", color=C_GRAY):
    """Draw a dashed line between two points."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0.0
    a = {"layer": layer, "color": color}
    while pos < length:
        end = min(pos + dash, length)
        msp.add_line(
            (x1 + ux * pos, y1 + uy * pos),
            (x1 + ux * end, y1 + uy * end),
            dxfattribs=a,
        )
        pos = end + gap


def dim_line(msp, x1, y1, x2, y2, text, offset=0,
             layer="DIMENSIONS", color=C_CYAN, text_h=120):
    """Draw a simple dimension line with ticks and text."""
    a = {"layer": layer, "color": color}
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    # Perpendicular unit vector for offset
    ux, uy = dx / length, dy / length
    px, py = -uy, ux  # perpendicular

    # Offset start/end
    sx = x1 + px * offset
    sy = y1 + py * offset
    ex = x2 + px * offset
    ey = y2 + py * offset

    # Main line
    msp.add_line((sx, sy), (ex, ey), dxfattribs=a)
    # Extension lines (from original points to offset)
    tick = 100
    if offset != 0:
        ext = 200  # extension beyond tick
        sign = 1 if offset > 0 else -1
        msp.add_line(
            (x1 + px * (offset - sign * ext), y1 + py * (offset - sign * ext)),
            (sx + px * sign * ext, sy + py * sign * ext),
            dxfattribs=a,
        )
        msp.add_line(
            (x2 + px * (offset - sign * ext), y2 + py * (offset - sign * ext)),
            (ex + px * sign * ext, ey + py * sign * ext),
            dxfattribs=a,
        )
    # Tick marks at ends
    msp.add_line((sx - py * tick, sy + px * tick),
                 (sx + py * tick, sy - px * tick), dxfattribs=a)
    msp.add_line((ex - py * tick, ey + px * tick),
                 (ex + py * tick, ey - px * tick), dxfattribs=a)
    # Text at midpoint
    mx = (sx + ex) / 2
    my = (sy + ey) / 2
    angle = math.degrees(math.atan2(dy, dx))
    txt(msp, text, mx + px * 200, my + py * 200,
        h=text_h, layer=layer, color=color, rot=angle, align="CENTER")


# ============================================================
#  DRAWING 1 — INVERTER BUILDING DETAIL
# ============================================================
def generate_inverter_detail():
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # mm
    setup_styles(doc)

    # Layers
    layer_defs = [
        ("BORDER",           C_WHITE,   70),
        ("TITLE_BLOCK",      C_WHITE,   35),
        ("BUILDING",         C_WHITE,   50),
        ("MID_ROOF",         C_GRAY,    25),
        ("WALKWAY",          C_GRAY,    18),
        ("PANELS_EXCLUDED",  C_RED,     35),
        ("CABLE_POS",        C_RED,     35),
        ("CABLE_NEG",        C_BLUE,    35),
        ("CABLE_ENTRY",      C_YELLOW,  50),
        ("YBRANCH",          C_YELLOW,  35),
        ("MPPT",             C_CYAN,    35),
        ("DIMENSIONS",       C_CYAN,    13),
        ("TEXT",             C_WHITE,   13),
        ("LEGEND",           C_WHITE,   18),
        ("NORTH_ARROW",      C_WHITE,   35),
        ("NOTES",            C_GRAY,    13),
    ]
    for s, clr in STRING_COLORS.items():
        layer_defs.append((f"STRING_{s}", clr, 25))
    for n, c, w in layer_defs:
        add_layer(doc, n, c, w)

    msp = doc.modelspace()

    # ─── placement ─────────────────────────────────────────
    MARGIN = 2000
    BLDG_X = MARGIN + 2500
    BLDG_Y = MARGIN + 4500

    # ─── border ────────────────────────────────────────────
    DWG_W = BUILDING_W + 18000
    DWG_H = BUILDING_H + 14000
    rect(msp, 0, 0, DWG_W, DWG_H, "BORDER")
    # Inner border
    rect(msp, MARGIN // 2, MARGIN // 2, DWG_W - MARGIN, DWG_H - MARGIN, "BORDER")

    # ─── title block (bottom strip) ───────────────────────
    tb_y = MARGIN
    txt(msp, "HOPE FARM IBADAN — SOLAR PV PROJECT",
        MARGIN + 1000, tb_y + 2800, 350, "TITLE_BLOCK", style="TITLE")
    txt(msp, "INVERTER BUILDING — PANEL LAYOUT & CABLE ROUTING DIAGRAM",
        MARGIN + 1000, tb_y + 2200, 250, "TITLE_BLOCK", style="TITLE")
    txt(msp, "TOTAL PANELS ON THIS BUILDING: 64   |   STRINGS: 6   |   INVERTER MPPT INPUTS: 3",
        MARGIN + 1000, tb_y + 1600, 160, "TITLE_BLOCK", style="LABEL")
    txt(msp, f"PANEL: {PANEL_W} x {PANEL_H} mm (~500 W)   |   UNITS: mm   |   SHEET 2 OF 2",
        MARGIN + 1000, tb_y + 1100, 140, "TITLE_BLOCK", color=C_GRAY, style="LABEL")
    txt(msp, "DWG NO: HF-SPV-002   |   REV: A   |   DATE: 2025",
        MARGIN + 1000, tb_y + 600, 130, "TITLE_BLOCK", color=C_GRAY, style="LABEL")

    # ─── building outline ─────────────────────────────────
    rect(msp, BLDG_X, BLDG_Y, BUILDING_W, BUILDING_H, "BUILDING")
    txt(msp, "INVERTER BUILDING — ROOF PLAN",
        BLDG_X + BUILDING_W / 2, BLDG_Y + BUILDING_H + 400,
        200, "BUILDING", align="CENTER", style="TITLE")

    # ─── mid-roof line (dashed) ───────────────────────────
    mid_x = BLDG_X + ROOF_OVERHANG + HALF_WIDTH + MID_ROOF_GAP / 2
    dashed_line(msp, mid_x, BLDG_Y - 300, mid_x, BLDG_Y + BUILDING_H + 300,
                layer="MID_ROOF")
    txt(msp, "MID-ROOF LINE (RIDGE)", mid_x, BLDG_Y - 600,
        130, "MID_ROOF", color=C_GRAY, align="CENTER")

    # ─── walkway indicator ────────────────────────────────
    # Between row-group 0-2 and row-group 3-5
    _, wy_top = panel_xy(3, 0, BLDG_X, BLDG_Y)
    _, wy_bot = panel_xy(2, 0, BLDG_X, BLDG_Y)
    wy_bot_top = wy_bot + PANEL_H
    walkway_center = (wy_top + wy_bot_top) / 2
    a_walk = {"layer": "WALKWAY", "color": C_GRAY}
    # Two dashed lines marking the walkway edges
    dashed_line(msp, BLDG_X, wy_bot_top, BLDG_X + BUILDING_W, wy_bot_top,
                dash=150, gap=80, layer="WALKWAY", color=C_GRAY)
    dashed_line(msp, BLDG_X, wy_top, BLDG_X + BUILDING_W, wy_top,
                dash=150, gap=80, layer="WALKWAY", color=C_GRAY)
    txt(msp, "MAINTENANCE ACCESS WALKWAY",
        BLDG_X + BUILDING_W + 300, walkway_center,
        120, "WALKWAY", color=C_GRAY)

    # Second walkway between row 5 and 6
    _, wy_top2 = panel_xy(6, 0, BLDG_X, BLDG_Y)
    _, wy_bot2_base = panel_xy(5, 0, BLDG_X, BLDG_Y)
    wy_bot2_top = wy_bot2_base + PANEL_H
    dashed_line(msp, BLDG_X, wy_bot2_top, BLDG_X + BUILDING_W, wy_bot2_top,
                dash=150, gap=80, layer="WALKWAY", color=C_GRAY)
    dashed_line(msp, BLDG_X, wy_top2, BLDG_X + BUILDING_W, wy_top2,
                dash=150, gap=80, layer="WALKWAY", color=C_GRAY)
    txt(msp, "MAINTENANCE ACCESS",
        BLDG_X + BUILDING_W + 300, (wy_top2 + wy_bot2_top) / 2,
        120, "WALKWAY", color=C_GRAY)

    # ─── draw panels ──────────────────────────────────────
    string_panels = {s: [] for s in STRING_COLORS}
    string_counter = {s: 0 for s in STRING_COLORS}
    panel_count = 0

    for row in range(GRID_ROWS):
        for col in range(COLS_PER_HALF * 2):
            px, py = panel_xy(row, col, BLDG_X, BLDG_Y)
            cx = px + PANEL_W / 2
            cy = py + PANEL_H / 2
            sid = get_string(row, col)

            if sid is None:
                # ── excluded position ──
                rect(msp, px, py, PANEL_W, PANEL_H, "PANELS_EXCLUDED", C_RED)
                x_mark(msp, cx, cy, min(PANEL_W, PANEL_H) * 0.5)
                txt(msp, "X", cx, cy, 300, "PANELS_EXCLUDED", C_RED, align="CENTER")
            else:
                # ── active panel ──
                panel_count += 1
                string_counter[sid] += 1
                num = string_counter[sid]
                lyr = f"STRING_{sid}"
                clr = STRING_COLORS[sid]

                rect(msp, px, py, PANEL_W, PANEL_H, lyr, clr)

                # Inner rectangle (mounting frame)
                inset = 40
                rect(msp, px + inset, py + inset,
                     PANEL_W - 2 * inset, PANEL_H - 2 * inset, lyr, clr)

                # Panel number
                txt(msp, str(num), cx, cy + 250, 200, lyr, clr, align="CENTER")
                # String label
                txt(msp, sid, cx, cy - 300, 140, lyr, clr, align="CENTER")

                string_panels[sid].append({
                    "row": row, "col": col,
                    "x": px, "y": py,
                    "cx": cx, "cy": cy,
                    "num": num,
                })

    print(f"  Active panels drawn: {panel_count}")

    # ─── cable entry point ────────────────────────────────
    ce_x = mid_x
    ce_y = BLDG_Y + BUILDING_H - ROOF_OVERHANG * 0.4
    ce_w, ce_h = 800, 500

    rect(msp, ce_x - ce_w / 2, ce_y - ce_h / 2, ce_w, ce_h, "CABLE_ENTRY", C_YELLOW)
    # Cross-hatch inside entry point
    a_ce = {"layer": "CABLE_ENTRY", "color": C_YELLOW}
    msp.add_line((ce_x - ce_w / 2, ce_y - ce_h / 2),
                 (ce_x + ce_w / 2, ce_y + ce_h / 2), dxfattribs=a_ce)
    msp.add_line((ce_x - ce_w / 2, ce_y + ce_h / 2),
                 (ce_x + ce_w / 2, ce_y - ce_h / 2), dxfattribs=a_ce)
    txt(msp, "CABLE ENTRY", ce_x, ce_y + ce_h / 2 + 300,
        160, "CABLE_ENTRY", C_YELLOW, align="CENTER", style="TITLE")
    txt(msp, "POINT", ce_x, ce_y + ce_h / 2 + 100,
        160, "CABLE_ENTRY", C_YELLOW, align="CENTER", style="TITLE")

    # ─── cable routing ────────────────────────────────────
    # For each string, find the cable exit panel (closest to cable entry)
    cable_exits = {}
    for sid, panels in string_panels.items():
        if not panels:
            continue
        best = max(panels, key=lambda p: p["y"])
        cable_exits[sid] = (best["cx"], best["y"] + PANEL_H)

    # Route cables from string exits → Y-branch → cable entry
    yb_positions = {}
    yb_spacing = 2800
    yb_base_y = ce_y - 1500
    yb_center_x = ce_x

    # Compute Y-branch horizontal positions (spread evenly)
    yb_x_offsets = {"y1": -yb_spacing, "y2": 0, "y3": yb_spacing}

    for yb_name, info in YBRANCH.items():
        s_a, s_b = info["strings"]
        mppt = info["mppt"]
        yb_x = yb_center_x + yb_x_offsets[yb_name]
        yb_y = yb_base_y
        yb_positions[yb_name] = (yb_x, yb_y)

        # ── positive cables (red) ──
        cable_sep = 60
        for idx, sid in enumerate([s_a, s_b]):
            if sid not in cable_exits:
                continue
            sx, sy = cable_exits[sid]
            sx_p = sx - cable_sep
            # Route up then across to Y-branch
            route_y = yb_y + (idx + 1) * 400
            pts = [
                (sx_p, sy),
                (sx_p, route_y),
                (yb_x - cable_sep, route_y),
                (yb_x - cable_sep, yb_y + 180),
            ]
            msp.add_lwpolyline(pts, dxfattribs={"layer": "CABLE_POS", "color": C_RED})
            # Label at exit
            txt(msp, f"{sid}P", sx_p - 250, sy + 100, 90,
                "CABLE_POS", C_RED, align="CENTER")

        # ── negative cables (blue) ──
        for idx, sid in enumerate([s_a, s_b]):
            if sid not in cable_exits:
                continue
            sx, sy = cable_exits[sid]
            sx_n = sx + cable_sep
            route_y = yb_y + (idx + 1) * 400 + 200
            pts = [
                (sx_n, sy),
                (sx_n, route_y),
                (yb_x + cable_sep, route_y),
                (yb_x + cable_sep, yb_y + 180),
            ]
            msp.add_lwpolyline(pts, dxfattribs={"layer": "CABLE_NEG", "color": C_BLUE})
            txt(msp, f"{sid}N", sx_n + 250, sy + 100, 90,
                "CABLE_NEG", C_BLUE, align="CENTER")

        # ── Y-branch symbol ──
        msp.add_circle((yb_x, yb_y), radius=180,
                       dxfattribs={"layer": "YBRANCH", "color": C_YELLOW})
        txt(msp, yb_name, yb_x, yb_y, 120, "YBRANCH", C_YELLOW,
            align="CENTER", style="TITLE")

        # ── Y-branch → cable entry ──
        msp.add_lwpolyline(
            [(yb_x, yb_y - 180), (yb_x, ce_y - 500),
             (ce_x, ce_y - 500), (ce_x, ce_y - ce_h / 2)],
            dxfattribs={"layer": "CABLE_ENTRY", "color": C_YELLOW},
        )

        # ── MPPT label ──
        txt(msp, f"→ {mppt}", yb_x + 250, yb_y - 100, 120,
            "MPPT", C_CYAN, style="TITLE")

    # ─── dimensions ───────────────────────────────────────
    # Building width
    dim_line(msp,
             BLDG_X, BLDG_Y, BLDG_X + BUILDING_W, BLDG_Y,
             f"{BUILDING_W:.0f}", offset=-1200)

    # Building height
    dim_line(msp,
             BLDG_X, BLDG_Y, BLDG_X, BLDG_Y + BUILDING_H,
             f"{BUILDING_H:.0f}", offset=-1200)

    # Panel width dimension (one example panel)
    p0x, p0y = panel_xy(0, 1, BLDG_X, BLDG_Y)
    dim_line(msp, p0x, p0y, p0x + PANEL_W, p0y,
             f"{PANEL_W}", offset=-500, text_h=90)

    # Panel height dimension
    dim_line(msp, p0x, p0y, p0x, p0y + PANEL_H,
             f"{PANEL_H}", offset=-500, text_h=90)

    # Half-width dimension
    dim_line(msp,
             BLDG_X + LEFT_X0, BLDG_Y + BUILDING_H,
             BLDG_X + LEFT_X0 + HALF_WIDTH, BLDG_Y + BUILDING_H,
             f"LEFT HALF: {HALF_WIDTH:.0f}", offset=600, text_h=100)
    dim_line(msp,
             BLDG_X + RIGHT_X0, BLDG_Y + BUILDING_H,
             BLDG_X + RIGHT_X0 + HALF_WIDTH, BLDG_Y + BUILDING_H,
             f"RIGHT HALF: {HALF_WIDTH:.0f}", offset=600, text_h=100)

    # ─── north arrow ──────────────────────────────────────
    north_arrow(msp,
                BLDG_X + BUILDING_W + 3000,
                BLDG_Y + BUILDING_H - 3000,
                size=1200, layer="NORTH_ARROW")

    # ─── legend / key ─────────────────────────────────────
    LX = BLDG_X + BUILDING_W + 2500
    LY = BLDG_Y + BUILDING_H / 2 + 6000

    txt(msp, "KEY / LEGEND", LX, LY, 220, "LEGEND", style="TITLE")
    # Underline
    msp.add_line((LX, LY - 100), (LX + 5000, LY - 100),
                 dxfattribs={"layer": "LEGEND"})

    legend_items = [
        ("S  = String (series-connected panels)", C_WHITE),
        ("P  = Positive (+) polarity (red cable)", C_RED),
        ("N  = Negative (−) polarity (blue cable)", C_BLUE),
        ("y  = Y-Branch connector", C_YELLOW),
        ("X  = Excluded position (obstruction)", C_RED),
        ("MPPT = Maximum Power Point Tracker", C_CYAN),
    ]
    for i, (label, clr) in enumerate(legend_items):
        txt(msp, label, LX, LY - (i + 1) * 300, 130, "LEGEND", clr)

    # ── string colour legend ──
    sly = LY - (len(legend_items) + 2) * 300
    txt(msp, "STRING COLOUR CODING:", LX, sly, 160, "LEGEND", style="TITLE")

    for i, (sid, clr) in enumerate(STRING_COLORS.items()):
        y = sly - (i + 1) * 300
        # Colour swatch
        rect(msp, LX, y - 60, 250, 120, "LEGEND", clr)
        count = len(string_panels.get(sid, []))
        txt(msp, f"{sid}  —  {count} panels", LX + 400, y, 130, "LEGEND", clr)

    # ── Y-branch wiring table ──
    ty = sly - (len(STRING_COLORS) + 2) * 300
    txt(msp, "Y-BRANCH → MPPT CONNECTIONS:", LX, ty, 160, "LEGEND", style="TITLE")

    for i, (ybn, info) in enumerate(YBRANCH.items()):
        s_a, s_b = info["strings"]
        mppt = info["mppt"]
        y_pos = ty - (i * 2 + 1) * 250
        circled = str(i + 1)
        txt(msp, f"({circled})  a) {s_a}P + {s_b}P  =  {ybn}+",
            LX, y_pos, 120, "LEGEND", C_RED)
        txt(msp, f"     b) {s_a}N + {s_b}N  =  {ybn}−   →  {mppt}",
            LX, y_pos - 200, 120, "LEGEND", C_BLUE)

    # ─── notes block ──────────────────────────────────────
    ny = BLDG_Y - 1800
    notes = [
        "NOTES:",
        f"1. All dimensions in millimetres (mm).",
        f"2. Panel spec: ~500 W monocrystalline, {PANEL_W} × {PANEL_H} mm.",
        "3. 'X' positions = structural obstructions — panels cannot be installed.",
        "4. Maintenance walkways provide safe access for cleaning & servicing.",
        "5. All cables route through the Cable Entry Point to inverter room below.",
        "6. Y-Branch connectors combine two string cables into one before MPPT input.",
        "7. MPPT = Maximum Power Point Tracker (smart optimisation input port).",
        f"8. Building subtotal: {panel_count} panels × ~500 W = ~{panel_count * 500 / 1000:.0f} kWp.",
        "9. Cable polarity: RED = Positive (+), BLUE = Negative (−).",
        "10. Drawing not to scale — refer to dimensions for exact measurements.",
    ]
    for i, note in enumerate(notes):
        h = 150 if i == 0 else 110
        clr = C_WHITE if i == 0 else C_GRAY
        txt(msp, note, MARGIN + 1200, ny - i * 220, h, "NOTES", clr)

    # ─── save ─────────────────────────────────────────────
    fp = os.path.join(OUTPUT_DIR, "HOPE_FARM_INVERTER_DETAIL.dxf")
    doc.saveas(fp)
    print(f"  ✅  Saved: {fp}")
    return fp


# ============================================================
#  DRAWING 2 — SITE LAYOUT PLAN
# ============================================================
def generate_site_plan():
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metres
    setup_styles(doc)

    layer_defs = [
        ("BORDER",          C_WHITE,   70),
        ("TITLE_BLOCK",     C_WHITE,   35),
        ("SITE_BOUNDARY",   C_GREEN,   70),
        ("BUILDINGS",       C_WHITE,   50),
        ("BLDG_HATCH",      C_GRAY,    13),
        ("ROADS",           C_GRAY,    35),
        ("LANDSCAPE",       C_GREEN,   25),
        ("ZONE_LABELS",     C_CYAN,    35),
        ("PANEL_COUNTS",    C_YELLOW,  25),
        ("TEXT",            C_WHITE,   13),
        ("DIMENSIONS",      C_CYAN,    13),
        ("NORTH_ARROW",     C_WHITE,   35),
        ("LEGEND",          C_WHITE,   18),
        ("NOTES",           C_GRAY,    13),
        ("ZONE_A",          C_CYAN,    35),
        ("ZONE_B",          C_GREEN,   35),
        ("ZONE_C",          C_YELLOW,  35),
        ("ZONE_D",          C_MAGENTA, 35),
    ]
    for n, c, w in layer_defs:
        add_layer(doc, n, c, w)

    msp = doc.modelspace()

    # ── compound boundary ─────────────────────────────────
    boundary = [
        (5, 0), (0, 8), (0, 48), (3, 53),
        (8, 56), (75, 56), (82, 51),
        (86, 42), (86, 5), (80, 0), (5, 0),
    ]
    msp.add_lwpolyline(boundary,
                       dxfattribs={"layer": "SITE_BOUNDARY", "color": C_GREEN},
                       close=True)
    txt(msp, "SITE BOUNDARY", 43, 58, 1.5, "SITE_BOUNDARY", C_GREEN,
        align="CENTER", style="TITLE")

    # ── Hope Road ─────────────────────────────────────────
    road_outer = [(-4, -2), (-7, 15), (-8, 48), (-3, 60)]
    road_inner = [(3, -2),  (-1, 15), (-2, 48), (3, 60)]
    msp.add_lwpolyline(road_outer,
                       dxfattribs={"layer": "ROADS", "color": C_GRAY})
    msp.add_lwpolyline(road_inner,
                       dxfattribs={"layer": "ROADS", "color": C_GRAY})
    txt(msp, "HOPE ROAD", -5, 32, 1.8, "ROADS", C_GRAY, rot=82, style="TITLE")

    # ── buildings ─────────────────────────────────────────
    # (label_lines, x, y, w, h, zone_lbl, panels, zone_layer)
    buildings = [
        (["INVERTER", "BUILDING"],     55, 42, 22, 12, "Zone A",  64,  "ZONE_A"),
        (["ZONE A", "BUILDING"],       64, 26, 18, 14, "Zone A",  64,  "ZONE_A"),
        (["ZONE B", "BUILDING 1"],     42, 2,  20, 18, "Zone B",  88,  "ZONE_B"),
        (["ZONE B", "BUILDING 2"],     64, 2,  18, 18, "Zone B",  88,  "ZONE_B"),
        (["ZONE C", "BUILDING"],       28, 6,  12, 12, "Zone C",  40,  "ZONE_C"),
        (["ZONE D", "BUILDING"],       5,  24, 28, 10, "Zone D",  104, "ZONE_D"),
        (["MAIZE STORAGE", "BUILDING"],5,  6,  18, 14, "",         64,  "ZONE_LABELS"),
        (["BLDG NEAR", "MOLASSES TANK"],32, 20, 12, 8, "",         32,  "ZONE_LABELS"),
    ]

    for bldg in buildings:
        labels, bx, by, bw, bh, zone, panels, zlyr = bldg

        # Outline
        rect(msp, bx, by, bw, bh, "BUILDINGS")

        cx = bx + bw / 2
        cy = by + bh / 2

        # Hatch lines (indicate roof / panels)
        spacing = 1.0
        for off in range(1, int(bw / spacing)):
            lx = bx + off * spacing
            msp.add_line((lx, by + 0.3), (lx, by + bh - 0.3),
                         dxfattribs={"layer": "BLDG_HATCH", "color": C_GRAY})

        # Zone label (above building)
        if zone:
            txt(msp, zone, cx, by + bh + 1.5, 1.2, zlyr,
                align="CENTER", style="TITLE")

        # Building name
        for j, line in enumerate(labels):
            txt(msp, line, cx, cy + 1.5 - j * 1.5, 0.9, zlyr,
                align="CENTER")

        # Panel count
        txt(msp, f"{panels} PANELS", cx, cy - len(labels) * 1.2,
            0.8, "PANEL_COUNTS", C_YELLOW, align="CENTER")

    # ── tree ──────────────────────────────────────────────
    tx, ty = 32, 40
    for r in [3.5, 2.0, 0.8]:
        msp.add_circle((tx, ty), radius=r,
                       dxfattribs={"layer": "LANDSCAPE", "color": C_GREEN})
    # Cross
    a_t = {"layer": "LANDSCAPE", "color": C_GREEN}
    msp.add_line((tx - 1.5, ty), (tx + 1.5, ty), dxfattribs=a_t)
    msp.add_line((tx, ty - 1.5), (tx, ty + 1.5), dxfattribs=a_t)
    txt(msp, "TREE", tx, ty + 5, 1.2, "LANDSCAPE", C_GREEN,
        align="CENTER", style="TITLE")
    txt(msp, "(Shadow Consideration)", tx, ty + 3.5, 0.7,
        "LANDSCAPE", C_GREEN, align="CENTER")

    # ── north arrow ───────────────────────────────────────
    north_arrow(msp, 92, 50, size=5, layer="NORTH_ARROW")

    # ── title block ───────────────────────────────────────
    txt(msp, "HOPE FARM IBADAN — SOLAR PV PROJECT",
        5, -6, 2.2, "TITLE_BLOCK", style="TITLE")
    txt(msp, "SITE LAYOUT PLAN — PANEL ZONE DISTRIBUTION",
        5, -9, 1.6, "TITLE_BLOCK", style="TITLE")
    txt(msp, "LOCATION: Hope Farm, Ibadan, Nigeria   |   TOTAL: ~544 Panels   |   ~270 kWp",
        5, -12, 0.9, "TITLE_BLOCK", color=C_GRAY, style="LABEL")
    txt(msp, "DWG NO: HF-SPV-001   |   REV: A   |   SHEET 1 OF 2   |   DATE: 2025",
        5, -14, 0.8, "TITLE_BLOCK", color=C_GRAY, style="LABEL")

    # ── summary table ─────────────────────────────────────
    stx = 5
    sty = -18
    txt(msp, "PANEL SUMMARY TABLE", stx, sty, 1.2, "LEGEND", style="TITLE")
    msp.add_line((stx, sty - 0.5), (stx + 40, sty - 0.5),
                 dxfattribs={"layer": "LEGEND"})

    summary = [
        ("Zone A  (Inverter Building area)", "64"),
        ("Zone B", "176"),
        ("Zone C", "40"),
        ("Zone D", "104"),
        ("Maize Storage Building", "64"),
        ("Inverter Building", "64"),
        ("Building near Molasses Tank", "32"),
    ]

    for i, (zone, count) in enumerate(summary):
        y = sty - (i + 1) * 1.8
        txt(msp, zone, stx, y, 0.8, "LEGEND")
        txt(msp, f"{count} panels", stx + 32, y, 0.8, "LEGEND", C_YELLOW)

    # Total row
    ty_total = sty - (len(summary) + 1) * 1.8
    msp.add_line((stx, ty_total + 0.5), (stx + 40, ty_total + 0.5),
                 dxfattribs={"layer": "LEGEND"})
    txt(msp, "TOTAL", stx, ty_total, 1.0, "LEGEND", C_YELLOW, style="TITLE")
    txt(msp, "~544 panels  (~270 kWp)", stx + 32, ty_total, 1.0,
        "LEGEND", C_YELLOW, style="TITLE")

    # ── notes ─────────────────────────────────────────────
    nx = 50
    nty = -18
    notes = [
        "NOTES:",
        "1. Drawing is schematic — not to precise scale.",
        "2. Panel counts subject to detailed roof survey.",
        "3. Tree may cause shading on adjacent buildings.",
        "4. Some zone counts marked TBC (To Be Confirmed).",
        "5. All buildings require structural assessment",
        "   before panel installation.",
        f"6. System estimate: ~544 panels × ~500 W = ~272 kWp.",
        "7. Refer to Sheet 2 for Inverter Building detail.",
    ]
    for i, n in enumerate(notes):
        h = 1.0 if i == 0 else 0.7
        c = C_WHITE if i == 0 else C_GRAY
        txt(msp, n, nx, nty - i * 1.8, h, "NOTES", c)

    # ── border ────────────────────────────────────────────
    rect(msp, -12, -40, 115, 105, "BORDER")
    rect(msp, -11, -39, 113, 103, "BORDER")

    # ── save ──────────────────────────────────────────────
    fp = os.path.join(OUTPUT_DIR, "HOPE_FARM_SITE_PLAN.dxf")
    doc.saveas(fp)
    print(f"  ✅  Saved: {fp}")
    return fp


# ============================================================
#  MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 62)
    print("  HOPE FARM IBADAN — SOLAR PV PROJECT")
    print("  Professional DXF Drawing Generator")
    print("=" * 62)
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("[1/2] Generating Inverter Building Detail Drawing...")
    f1 = generate_inverter_detail()
    print()

    print("[2/2] Generating Site Layout Plan...")
    f2 = generate_site_plan()
    print()

    print("=" * 62)
    print("  GENERATION COMPLETE")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"    1. {os.path.basename(f1)}")
    print(f"    2. {os.path.basename(f2)}")
    print("=" * 62)
    print()
    print("  Open in LibreCAD, AutoCAD, or any DXF-compatible")
    print("  CAD software. Use 'Zoom Extents' to see full drawing.")
