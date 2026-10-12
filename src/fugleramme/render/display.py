"""An uploaded image as a page: fitted whole, or cropped to meet the frame.

The page is the panel's shape, so an image of another shape has to meet it one
of three ways. Two keep the frame's margin, so a mat that overlaps the panel
never covers part of the picture; "bleed" crops past it, edge to edge.
"""

from __future__ import annotations

import math

from PIL import Image

from ..display import Pin
from .page import NO_MARGIN, Edges, blank, fit

# The fits that crop rather than letterbox.
CROPS = frozenset({"fill", "bleed"})


def render_display(
    pin: Pin,
    resolution: tuple[int, int],
    textured: bool,
    margin: Edges,
) -> Image.Image:
    """The pinned image on an otherwise bare page."""
    image = Image.open(pin.path).convert("RGB")
    canvas = blank(resolution, textured)
    x0, y0, x1, y1 = (NO_MARGIN if pin.fit == "bleed" else margin).window(resolution)
    box = (x1 - x0, y1 - y0)
    placed = _cover(image, box) if pin.fit in CROPS else fit(image, box)
    canvas.paste(placed, (x0 + (box[0] - placed.width) // 2, y0 + (box[1] - placed.height) // 2))
    return canvas


def _cover(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Scale to cover `box`, then take the middle of it."""
    scale = max(box[0] / image.width, box[1] / image.height)
    width = max(box[0], math.ceil(image.width * scale))
    height = max(box[1], math.ceil(image.height * scale))
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    left, top = (width - box[0]) // 2, (height - box[1]) // 2
    return resized.crop((left, top, left + box[0], top + box[1]))
