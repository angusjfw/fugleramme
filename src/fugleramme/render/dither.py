"""Panel colour reduction.

The Inky Impression (Spectra 6) shows only 6 colours. The kiosk collage is full
colour; for the panel it is reduced here rather than in the driver, because
`inky.set_image` re-dithers anything that is not already a 6-colour "P" image -
dithering an already-dithered image smears it. Handing it a "P" image with
exactly 6 palette entries makes it skip its own dither and just remap indices,
so this module owns the reduction and the saved frame matches the glass.

Index order below is the driver's (`inky.inky_el133uf1`), which the remap
depends on. The palette is a blend of the driver's two: the "desaturated" set is
what it writes, the "saturated" set is nearer what the panel actually shows, so
dithering against the blend measures colour distance in roughly panel space.

The three whole-number controls are the admin's, each defaulting to the middle
of its range. Saturation is inverted on purpose: dithering toward the driver's
pure inks puts more of them on the page, which reads more saturated, while the
blend toward the panel's muted tones flattens it. Lower `_SATURATION`, more ink.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from .paper import PANEL_PAPER, _reach

# Driver index order: black, white, yellow, red, blue, green.
_DESATURATED = [(0, 0, 0), (255, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 0)]
_SATURATED = [(0, 0, 0), (161, 164, 165), (208, 190, 71), (156, 72, 75), (61, 59, 94), (58, 91, 70)]

# The admin's Panel colour controls, and where "Reset" sends each of them. Every
# default is the middle of its range, so a fresh frame and a reset agree.
SATURATION_RANGE = (0, 100)
CONTRAST_RANGE = (85, 145)
BRIGHTNESS_RANGE = (-40, 40)
DEFAULT_SATURATION = 50
DEFAULT_CONTRAST = 115
DEFAULT_BRIGHTNESS = 0

_LIFT = np.array([0.887, 0.906, 0.950])
_PIVOT = 182
_FADE = 4
_HALO = 12
_HALO_REACH = 32


def _palette(saturation: float) -> list[tuple[int, int, int]]:
    """The blend the quantizer measures against. `saturation` is the admin's,
    0-100: 100 dithers against the pure inks, 0 against the panel's own tones."""
    blend = 1.0 - saturation / 100.0
    return [
        tuple(int(s * blend + d * (1.0 - blend)) for s, d in zip(sat, desat, strict=True))
        for sat, desat in zip(_SATURATED, _DESATURATED, strict=True)
    ]


def _palette_image(saturation: float) -> Image.Image:
    pal = Image.new("P", (1, 1))
    flat: list[int] = []
    for colour in _palette(saturation):
        flat += list(colour)
    # Pad with black, already index 0, so the palette still reads as 6 unique colours.
    flat += [0, 0, 0] * (256 - len(_SATURATED))
    pal.putpalette(flat)
    return pal


def _boost(rgb: np.ndarray, contrast: float, brightness: float) -> np.ndarray:
    return _PIVOT + (rgb * _LIFT - _PIVOT) * contrast + brightness


def _pop(image: Image.Image, contrast: float, brightness: float) -> Image.Image:
    """Darken the birds so pale plumage takes ink. The paper and the halos keep
    their tone, or the halos would ring the birds."""
    rgb = np.asarray(image.convert("RGB"), np.float64)
    paper = np.array(PANEL_PAPER, np.float64)
    dist = np.linalg.norm(rgb - paper, axis=2)
    halo = _reach(dist <= 1, dist <= _HALO, _HALO_REACH) > 0
    keep = np.maximum(np.exp(-dist / _FADE), halo)[..., None]
    out = _boost(rgb, contrast, brightness) + keep * (paper - _boost(paper, contrast, brightness))
    return Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8))


def dither(
    image: Image.Image,
    saturation: float = DEFAULT_SATURATION,
    contrast: float = DEFAULT_CONTRAST,
    brightness: float = DEFAULT_BRIGHTNESS,
) -> Image.Image:
    """Quantize an RGB image to the 6-colour panel palette (returns mode "P"),
    under the admin's whole-number Panel colour controls."""
    return _pop(image, contrast / 100.0, brightness).quantize(
        palette=_palette_image(saturation), dither=Image.Dither.FLOYDSTEINBERG
    )


# The panel's own tones as the glass renders them. The driver is handed the pure
# inks and these are nearer what the eye gets, so the admin preview paints the
# quantized page with them - the panel look, not the file's palette.
_SHOWN = [c for colour in _SATURATED for c in colour] + [0, 0, 0] * (256 - len(_SATURATED))


def panel_preview(
    image: Image.Image,
    saturation: float = DEFAULT_SATURATION,
    contrast: float = DEFAULT_CONTRAST,
    brightness: float = DEFAULT_BRIGHTNESS,
) -> Image.Image:
    """The dithered page as the panel would show it, for the admin's preview."""
    page = dither(image, saturation, contrast, brightness)
    page.putpalette(_SHOWN)
    return page
