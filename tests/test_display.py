"""The pinned image's store: what an upload becomes, and what the frame is told.

The image itself is the source of truth here, not the request that carried it:
the loop, the kiosk and the admin all read `Display.current()`, so what it
reports has to survive a restart and move the page when it changes.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from fugleramme.display import DEFAULT_FIT, Display


def _png(size: tuple[int, int] = (120, 80), colour=(10, 120, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def test_nothing_is_shown_until_something_is_uploaded(tmp_path):
    assert Display(tmp_path).current() is None


def test_an_upload_is_stored_and_reported(tmp_path):
    display = Display(tmp_path)
    display.store(_png(), "fill")

    pin = display.current()
    assert pin is not None
    assert pin.fit == "fill"
    assert Image.open(pin.path).size == (120, 80)


def test_the_token_moves_when_a_new_image_takes_the_slot(tmp_path):
    display = Display(tmp_path)
    display.store(_png(colour=(10, 120, 200)), "fit")
    first = display.current().token

    display.store(_png(colour=(200, 10, 10)), "fit")
    assert display.current().token != first


def test_a_large_upload_is_scaled_to_the_stored_edge(tmp_path):
    display = Display(tmp_path)
    display.store(_png(size=(6000, 3000)), "fit")

    assert Image.open(display.path).size == (2400, 1200)


def test_an_unknown_fit_falls_back_to_the_default(tmp_path):
    display = Display(tmp_path)
    display.store(_png(), "sideways")

    assert display.current().fit == DEFAULT_FIT


def test_clearing_takes_the_image_and_its_choice_with_it(tmp_path):
    display = Display(tmp_path)
    display.store(_png(), "fit")

    display.clear()

    assert display.current() is None
    assert list(tmp_path.glob("display.*")) == []


def test_an_image_too_big_to_decode_is_refused_before_it_is_read(tmp_path):
    """The header's size is checked before the pixels load, so a body within the
    upload limit cannot still be a decompression bomb."""
    display = Display(tmp_path)
    with pytest.raises(ValueError):
        display.store(_oversized_png(), "fit")
    assert display.current() is None


def _oversized_png() -> bytes:
    """A 1×1 PNG whose header claims 9000×9000 (81 MP, over the pixel cap but
    under Pillow's own bomb guard)."""
    import struct
    import zlib

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(buffer, format="PNG")
    data = bytearray(buffer.getvalue())
    struct.pack_into(">II", data, 16, 9000, 9000)  # IHDR width, height
    struct.pack_into(">I", data, 29, zlib.crc32(bytes(data[12:29])) & 0xFFFFFFFF)
    return bytes(data)
