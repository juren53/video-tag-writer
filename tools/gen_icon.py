"""
Generate the VideoTagWriter icon set.

Outputs
  assets/ICON_vtw_source.png     256 px master (GIMP-editable)
  assets/ICON_vtw.ico            multi-size Windows icon (EXE + window)
  resources/icons/app*.png/.ico  Icon Manager Module (IMM) set used at runtime

Design: a film reel with film unspooling along the bottom, and a pencil whose tip
rests on the film ("writing tags on video").  Drawn in the Tag Writer family style
— flat fills, heavy black outlines — reusing the ATW/TW pencil colours, with the
VTW indigo accent on the reel (ATW's accent is teal).

Usage
  python tools/gen_icon.py                 # draw from scratch
  python tools/gen_icon.py --from-source   # rebuild outputs from an edited
                                           # assets/ICON_vtw_source.png
"""

import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
ASSETS = os.path.join(ROOT, 'assets')
ICON_DIR = os.path.join(ROOT, 'resources', 'icons')
SOURCE = os.path.join(ASSETS, 'ICON_vtw_source.png')
ICO = os.path.join(ASSETS, 'ICON_vtw.ico')
SIZES = [16, 24, 32, 48, 64, 128, 256]

SS = 4                                   # supersampling factor
STROKE = 8                               # outline width in 256 px units (TW art ≈ 9)

INK = (0, 0, 0, 255)
PAPER = (255, 255, 255, 255)
INDIGO = (48, 63, 159, 255)              # VTW accent
INDIGO_LIGHT = (197, 202, 233, 255)
PENCIL_BODY = (255, 188, 83, 255)        # sampled from ATW pencil
PENCIL_SHADE = (240, 156, 52, 255)
ERASER = (253, 101, 98, 255)             # sampled from ATW eraser
FERRULE = (200, 200, 205, 255)
CONE = (255, 226, 178, 255)              # sharpened wood

# Layout, 256 px units
REEL_C, REEL_R = (98, 120), 86
STRIP_Y0, STRIP_Y1 = 190, 236            # film leaves the reel bottom, runs right
STRIP_X0, STRIP_X1 = 98, 246
PENCIL_ERASER_END = (231, 32)            # back of the pencil (upper right)
PENCIL_TIP = (168, 194)                  # point touching the film
PENCIL_W = 36


def S(*vals):
    """Scale 256-unit coordinates to the supersampled canvas."""
    return [v * SS for v in vals]


def pts(seq):
    return [(x * SS, y * SS) for x, y in seq]


# ----------------------------------------------------------------------
# Elements
# ----------------------------------------------------------------------

def draw_strip(d):
    x0, y0, x1, y1 = STRIP_X0, STRIP_Y0, STRIP_X1, STRIP_Y1
    d.rounded_rectangle(S(x0, y0, x1, y1), radius=4 * SS, fill=INK)
    # sprocket holes
    hole_w, hole_h, pitch = 7, 6, 14
    x = x0 + 8
    while x + hole_w <= x1 - 6:
        for hy in (y0 + 5, y1 - 5 - hole_h):
            d.rounded_rectangle(S(x, hy, x + hole_w, hy + hole_h), radius=1.5 * SS, fill=PAPER)
        x += pitch
    # frames
    fy0, fy1 = y0 + 15, y1 - 15
    fw, gap = 34, 8
    x = x0 + 10
    while x + fw <= x1 - 8:
        d.rounded_rectangle(S(x, fy0, x + fw, fy1), radius=2.5 * SS, fill=INDIGO_LIGHT)
        x += fw + gap


def draw_reel(d):
    cx, cy = REEL_C
    r = REEL_R
    d.ellipse(S(cx - r, cy - r, cx + r, cy + r), fill=INDIGO, outline=INK, width=STROKE * SS)
    # inner rim line (wound film edge)
    ri = r - 16
    d.ellipse(S(cx - ri, cy - ri, cx + ri, cy + ri), outline=(32, 42, 112, 255), width=3 * SS)
    # five spoke holes
    hole_r, orbit = 17, 44
    for k in range(5):
        a = math.radians(-90 + k * 72)
        hx, hy = cx + orbit * math.cos(a), cy + orbit * math.sin(a)
        d.ellipse(S(hx - hole_r, hy - hole_r, hx + hole_r, hy + hole_r),
                  fill=PAPER, outline=INK, width=int(STROKE * 0.75 * SS))
    # hub
    hub = 12
    d.ellipse(S(cx - hub, cy - hub, cx + hub, cy + hub), fill=PAPER, outline=INK, width=int(STROKE * 0.75 * SS))
    d.ellipse(S(cx - 4, cy - 4, cx + 4, cy + 4), fill=INK)


def draw_pencil(d):
    (ex, ey), (tx, ty) = PENCIL_ERASER_END, PENCIL_TIP
    length = math.hypot(tx - ex, ty - ey)
    ux, uy = (tx - ex) / length, (ty - ey) / length      # along the pencil, toward tip
    nx, ny = -uy, ux                                     # across
    hw = PENCIL_W / 2

    def P(u, v):
        return (ex + ux * u + nx * v, ey + uy * u + ny * v)

    eraser_end = length * 0.15
    ferrule_end = length * 0.24
    body_end = length * 0.74
    lead_start = length * 0.92
    w = STROKE * SS

    # eraser (rounded back) — a capsule clipped by drawing ferrule over it
    d.polygon(pts([P(6, -hw), P(eraser_end + 2, -hw), P(eraser_end + 2, hw), P(6, hw)]),
              fill=ERASER, outline=INK, width=w)
    cap = P(6, 0)
    d.ellipse(S(cap[0] - hw, cap[1] - hw, cap[0] + hw, cap[1] + hw), fill=ERASER, outline=INK, width=w)
    d.polygon(pts([P(6, -hw + STROKE / 2), P(eraser_end, -hw + STROKE / 2),
                   P(eraser_end, hw - STROKE / 2), P(6, hw - STROKE / 2)]), fill=ERASER)
    # ferrule
    d.polygon(pts([P(eraser_end, -hw), P(ferrule_end, -hw), P(ferrule_end, hw), P(eraser_end, hw)]),
              fill=FERRULE, outline=INK, width=w)
    # body with shaded half
    d.polygon(pts([P(ferrule_end, -hw), P(body_end, -hw), P(body_end, hw), P(ferrule_end, hw)]),
              fill=PENCIL_BODY, outline=INK, width=w)
    d.polygon(pts([P(ferrule_end + STROKE / 2, 2), P(body_end - STROKE / 2, 2),
                   P(body_end - STROKE / 2, hw - STROKE / 2), P(ferrule_end + STROKE / 2, hw - STROKE / 2)]),
              fill=PENCIL_SHADE)
    # sharpened wood cone
    d.polygon(pts([P(body_end, -hw), P(length, 0), P(body_end, hw)]), fill=CONE, outline=INK, width=w)
    # lead
    lead_hw = hw * (length - lead_start) / (length - body_end)
    d.polygon(pts([P(lead_start, -lead_hw), P(length, 0), P(lead_start, lead_hw)]), fill=INK)


def draw() -> Image.Image:
    canvas = Image.new('RGBA', (256 * SS, 256 * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    draw_strip(d)    # behind the reel
    draw_reel(d)
    draw_pencil(d)   # in front
    return canvas.resize((256, 256), Image.LANCZOS)


# ----------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------

def write_outputs(master: Image.Image):
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(ICON_DIR, exist_ok=True)
    master = master.convert('RGBA')

    frames = {s: master.resize((s, s), Image.LANCZOS) if s != 256 else master for s in SIZES}
    desc = [frames[s] for s in sorted(SIZES, reverse=True)]   # PIL uses the first as base
    for path in (ICO, os.path.join(ICON_DIR, 'app.ico')):
        desc[0].save(path, format='ICO', sizes=[f.size for f in desc], append_images=desc[1:])
        print(f'ICO  {path}')
    for s, img in frames.items():
        img.save(os.path.join(ICON_DIR, f'app_{s}x{s}.png'))
    master.save(os.path.join(ICON_DIR, 'app.png'))       # IMM Linux fallback name
    print(f'PNGs {ICON_DIR}  (app.png + {len(frames)} sizes)')


if __name__ == '__main__':
    if '--from-source' in sys.argv:
        if not os.path.isfile(SOURCE):
            raise SystemExit(f'{SOURCE} not found — run without --from-source first.')
        img = Image.open(SOURCE)
    else:
        img = draw()
        img.save(SOURCE)
        print(f'SRC  {SOURCE}')
    write_outputs(img)
