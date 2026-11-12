"""
Cut the 3D film-reel photo out of its white background (one-time step).

  assets/ICON_vtw_reel_photo.jpg  ->  assets/ICON_vtw_reel.png  (RGBA, cropped)

tools/gen_icon.py then adds the pencil on top of the cutout.  Re-run this only if
the photo changes; it needs numpy and scipy (not app dependencies):

  python tools/cut_reel.py

How it works: background is light, unsaturated pixels connected to the image
border.  The silver reel is the same grey as its drop shadows, so the two reel
discs are protected by hand-fitted ellipses (photo pixel coordinates).  Inside them
only near-white is removed; outside them the grey shadows are removed as well.
Enclosed white pockets (e.g. under the film loop) are removed by size.
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, '..', 'assets'))
PHOTO = os.path.join(ASSETS, 'ICON_vtw_reel_photo.jpg')
CUTOUT = os.path.join(ASSETS, 'ICON_vtw_reel.png')

REEL_DISCS = [(243, 362, 208, 338),      # front disc  (cx, cy, rx, ry)
              (402, 330, 172, 338)]      # back disc
NEUTRAL_SAT = 16                         # max(RGB) - min(RGB) below this = grey
LUM_INSIDE, LUM_OUTSIDE = 228, 70        # background cut-off inside / outside the discs
POCKET_MIN = 400                         # enclosed white areas larger than this go


def cut(photo: Image.Image) -> Image.Image:
    img = photo.convert('RGB')
    a = np.asarray(img).astype(np.int16)
    sat = a.max(2) - a.min(2)
    lum = a.mean(2)

    prot = Image.new('L', img.size, 0)
    d = ImageDraw.Draw(prot)
    for cx, cy, rx, ry in REEL_DISCS:
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    prot = np.asarray(prot) > 0

    cand = (sat < NEUTRAL_SAT) & np.where(prot, lum > LUM_INSIDE, lum > LUM_OUTSIDE)
    lab, _ = ndimage.label(cand)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, edge[edge > 0])

    white = (sat < 10) & (lum > 238)
    wl, wn = ndimage.label(white)
    sizes = ndimage.sum(white, wl, range(1, wn + 1))
    bg |= np.isin(wl, 1 + np.nonzero(sizes > POCKET_MIN)[0])

    fg = ndimage.binary_opening(~bg, iterations=2)
    fl, fn = ndimage.label(fg)                       # drop specks
    sizes = ndimage.sum(fg, fl, range(1, fn + 1))
    fg = np.isin(fl, 1 + np.nonzero(sizes > 2000)[0])

    alpha = Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    out = img.convert('RGBA')
    out.putalpha(alpha)
    return out.crop(out.getbbox())


if __name__ == '__main__':
    out = cut(Image.open(PHOTO))
    out.save(CUTOUT, optimize=True)
    print(f'CUT  {CUTOUT}  {out.size}')
