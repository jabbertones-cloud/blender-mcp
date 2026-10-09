"""Tests for server.image_similarity — the golden-image compare behind
blender_product_shot's verdict. Stdlib-only, so these run anywhere."""
import struct
import zlib

import pytest

from server.image_similarity import (
    compare_luma,
    compare_png_bytes,
    decode_png_gray,
    encode_png_gray,
    resample_nearest,
)


def _chunk(ctype: bytes, body: bytes) -> bytes:
    out = struct.pack(">I", len(body)) + ctype + body
    out += struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
    return out


def _png(w, h, scanlines: bytes, *, bit_depth=8, color_type=0, palette=None):
    ihdr = struct.pack(">IIBBBBB", w, h, bit_depth, color_type, 0, 0, 0)
    parts = [b"\x89PNG\r\n\x1a\n", _chunk(b"IHDR", ihdr)]
    if palette:
        parts.append(_chunk(b"PLTE", palette))
    parts.append(_chunk(b"IDAT", zlib.compress(scanlines)))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)


def test_encode_decode_roundtrip():
    pixels = [0.0, 0.25, 0.5, 1.0, 0.1, 0.9]
    data = encode_png_gray(3, 2, pixels)
    w, h, decoded = decode_png_gray(data)
    assert (w, h) == (3, 2)
    assert decoded == pytest.approx(pixels, abs=1 / 255)


def test_identical_images_are_perfect_match():
    data = encode_png_gray(4, 4, [0.5] * 16)
    metrics = compare_png_bytes(data, data)
    assert metrics["psnr_db"] == float("inf")
    assert metrics["ssim"] == pytest.approx(1.0)
    assert metrics["mae"] == 0.0
    assert metrics["golden_resampled"] is False


def test_opposite_images_score_terribly():
    black = encode_png_gray(4, 4, [0.0] * 16)
    white = encode_png_gray(4, 4, [1.0] * 16)
    metrics = compare_png_bytes(white, black)
    assert metrics["psnr_db"] < 1.0
    assert metrics["ssim"] < 0.05
    assert metrics["mae"] == pytest.approx(1.0)


def test_subtle_change_scores_high_but_not_perfect():
    base = [0.5] * 64
    slightly_off = [0.52] * 64
    metrics = compare_luma(base, slightly_off)
    assert 25 < metrics["psnr_db"] < 40
    assert metrics["ssim"] > 0.99


def test_size_mismatch_resamples_and_reports_it():
    render = encode_png_gray(8, 8, [0.4] * 64)
    golden = encode_png_gray(4, 4, [0.4] * 16)
    metrics = compare_png_bytes(render, golden)
    assert metrics["golden_resampled"] is True
    assert metrics["render_size"] == [8, 8]
    assert metrics["golden_size"] == [4, 4]
    assert metrics["psnr_db"] == float("inf")  # same flat colour at any size


def test_decodes_filtered_scanlines():
    # 3x1 gray, filter=Sub: raw [10, 20, 30] stored as [10, 10, 10]
    data = _png(3, 1, bytes([1, 10, 10, 10]))
    _, _, px = decode_png_gray(data)
    assert px == pytest.approx([10 / 255, 20 / 255, 30 / 255])

    # 2x2 gray, row2 filter=Paeth: rows [100,100],[100,110]
    row1 = bytes([0, 100, 100])
    # Paeth with left/up/up-left all 100-ish predicts 100 for both pixels
    row2 = bytes([4, 0, 10])
    data = _png(2, 2, row1 + row2)
    _, _, px = decode_png_gray(data)
    assert px == pytest.approx([100 / 255, 100 / 255, 100 / 255, 110 / 255])


def test_decodes_rgb_and_16bit():
    # 1x1 RGB red
    data = _png(1, 1, bytes([0, 255, 0, 0]), color_type=2)
    _, _, px = decode_png_gray(data)
    assert px == pytest.approx([0.2126])

    # 2x1 16-bit gray: values 0x8000, 0xFF00 -> high bytes 0x80, 0xFF
    data = _png(2, 1, bytes([0, 0x80, 0x00, 0xFF, 0x00]), bit_depth=16)
    _, _, px = decode_png_gray(data)
    assert px == pytest.approx([0x80 / 255, 1.0])


def test_rejects_non_png_and_interlaced():
    with pytest.raises(ValueError, match="not a PNG"):
        decode_png_gray(b"definitely not a png")
    data = bytearray(encode_png_gray(2, 2, [0.0] * 4))
    data[28] = 1  # IHDR interlace byte
    with pytest.raises(ValueError, match="interlaced"):
        decode_png_gray(bytes(data))


def test_compare_requires_same_length():
    with pytest.raises(ValueError, match="mismatch"):
        compare_luma([0.1], [0.1, 0.2])


def test_resample_nearest_upscale():
    px = [0.0, 1.0, 1.0, 0.0]  # 2x2 checkerboard
    out = resample_nearest(px, 2, 2, 4, 4)
    assert out[0:4] == [0.0, 0.0, 1.0, 1.0]
    assert out[12:16] == [1.0, 1.0, 0.0, 0.0]
