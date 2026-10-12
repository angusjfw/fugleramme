"""One uploaded image taking over the frame until it is cleared.

Not a mode: the frame's mode and every presentation setting are left alone, so
clearing the image returns the birds exactly as they were. Kept as files beside
the settings rather than in settings.json, because a takeover is temporary and
that file is the frame's own configuration (and tracked).

Read from disk each time so the render loop and the HTTP server agree with no
shared state, and so the image survives a restart.
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

FILENAME = "display.png"
META = "display.json"
MAX_SIDE = 2400  # stored long edge; the panel is 1600 wide, the kiosk at most 2160
# A 32 MB body can still decode to something far bigger. Checked from the header,
# before the pixels are loaded, so a decompression bomb costs nothing to refuse.
MAX_PIXELS = 50_000_000
# What a POST body may hold: generous for a phone photo, bounded so a stray
# upload cannot fill the Pi.
MAX_UPLOAD = 32 * 1024 * 1024

# How the image meets a page of another shape. "fit" shows all of it with paper
# at the edges; the crops cut it down to the frame, and "bleed" past the margin.
FITS = {
    "fit": "Fit (whole image)",
    "fill": "Crop to the frame",
    "bleed": "Crop edge to edge (no border)",
}
DEFAULT_FIT = "fit"


@dataclass(frozen=True)
class Pin:
    """The image being shown, its identity, and how it sits on the page."""

    token: str
    path: Path
    fit: str


class Display:
    """The one pinned image, as files in the frame's data directory."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.path = self.directory / FILENAME
        self.meta_path = self.directory / META

    def current(self) -> Pin | None:
        """The image on show, or None. `token` moves with the file, so it is
        what tells the render loop and the kiosk the picture changed."""
        try:
            stat = self.path.stat()
        except OSError:
            return None
        # The fit is part of the identity: the image is written before the choice,
        # so a reader landing between the two must still see the page move.
        fit = self._fit()
        return Pin(f"{stat.st_mtime_ns}:{stat.st_size}:{fit}", self.path, fit)

    def _fit(self) -> str:
        try:
            raw = json.loads(self.meta_path.read_text())
        except (OSError, ValueError):
            return DEFAULT_FIT
        fit = raw.get("fit") if isinstance(raw, dict) else None
        return fit if fit in FITS else DEFAULT_FIT

    def store(self, data: bytes, fit: str) -> None:
        """Normalise and save an upload, replacing whatever was shown. Raises on
        anything unreadable (PIL's UnidentifiedImageError among them)."""
        opened = Image.open(io.BytesIO(data))
        if opened.width * opened.height > MAX_PIXELS:
            raise ValueError(f"image is {opened.width}×{opened.height}, too large to decode")
        image = ImageOps.exif_transpose(opened).convert("RGB")
        # thumbnail only ever shrinks, so a small image is stored as it is.
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        image.save(tmp, format="PNG")
        os.replace(tmp, self.path)
        self._write_meta(fit if fit in FITS else DEFAULT_FIT)

    def clear(self) -> None:
        for path in (self.path, self.meta_path):
            try:
                path.unlink()
            except OSError:
                pass

    def _write_meta(self, fit: str) -> None:
        tmp = self.meta_path.with_name(self.meta_path.name + ".tmp")
        tmp.write_text(json.dumps({"fit": fit}) + "\n")
        os.replace(tmp, self.meta_path)
