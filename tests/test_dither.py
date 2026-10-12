"""Panel colour reduction: the admin's three controls, and what the glass shows.

The controls only move the e-ink page - the browser view is full colour - so
these are about the quantizer's palette and the boost around it.
"""

from __future__ import annotations

from PIL import Image

from fugleramme.render.dither import (
    BRIGHTNESS_RANGE,
    CONTRAST_RANGE,
    DEFAULT_BRIGHTNESS,
    DEFAULT_CONTRAST,
    DEFAULT_SATURATION,
    SATURATION_RANGE,
    dither,
    panel_preview,
)


def _sample() -> Image.Image:
    """A varied patch, so the dither's choices - not one flat colour - move."""
    image = Image.new("RGB", (64, 48))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            pixels[x, y] = (x * 4 % 256, y * 5 % 256, (x + y) * 3 % 256)
    return image


def test_every_default_is_the_middle_of_its_range():
    for bounds, default in (
        (SATURATION_RANGE, DEFAULT_SATURATION),
        (CONTRAST_RANGE, DEFAULT_CONTRAST),
        (BRIGHTNESS_RANGE, DEFAULT_BRIGHTNESS),
    ):
        lo, hi = bounds
        assert default == (lo + hi) // 2, bounds


def test_each_colour_control_moves_the_page():
    page = _sample()
    base = dither(page).tobytes()
    assert dither(page, saturation=DEFAULT_SATURATION - 30).tobytes() != base
    assert dither(page, contrast=DEFAULT_CONTRAST + 25).tobytes() != base
    assert dither(page, brightness=DEFAULT_BRIGHTNESS + 30).tobytes() != base


def test_saturation_pushes_toward_the_pure_inks():
    """Higher is the intuitive way round: more of the inks, less of the muted mix."""
    page = _sample()
    vivid = dither(page, saturation=SATURATION_RANGE[1])
    muted = dither(page, saturation=SATURATION_RANGE[0])
    assert vivid.tobytes() != muted.tobytes()


def test_the_preview_paints_the_panel_s_own_tones():
    """Not the pure inks the driver is handed, nor the blend the quantizer measures
    against: the muted tones the glass actually shows."""
    palette = panel_preview(_sample()).getpalette()[:18]
    entries = [tuple(palette[i : i + 3]) for i in range(0, 18, 3)]
    assert (161, 164, 165) in entries  # the panel's white, not (255, 255, 255)
