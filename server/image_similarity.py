"""Stdlib-only PNG comparison for render verification.

Computes PSNR and SSIM (global-statistics formulation) between two PNG
images using only the standard library (zlib/struct), so the MCP server
needs no Pillow/numpy dependency. This is the "test" half of the
product-shot outcome contract: a render is evidence only if it can be
compared against a golden image, deterministically.

Scope: 8/16-bit PNG, color types 0 (gray), 2 (RGB), 3 (palette),
4 (gray+alpha), 6 (RGBA). Non-interlaced files only; interlaced PNGs
raise ValueError so the caller can report "unsupported golden" instead
of guessing. Comparison is done on luma (grayscale), which is the right
signal for "did the shot change" checks.

SSIM here is the classic Wang et al. formula evaluated with global
image statistics (single window). It is not a sliding-window SSIM map;
for golden-image gating it is stable, deterministic, and honest about
what it measures.
"""
from __future__ import annotations

import math
import struct
import zlib

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# SSIM stabilisation constants for pixel range L=255 (Wang et al. 2004).
_K1 = 0.01
_K2 = 0.03


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png_gray(data: bytes) -> tuple[int, int, list[float]]:
    """Decode PNG bytes to (width, height, luma pixels in 0.0..1.0).

    Raises ValueError for anything outside the supported scope.
    """
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("not a PNG file (bad signature)")

    pos = len(_PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    interlace = 0
    palette: list[tuple[int, int, int]] = []
    trns: list[int] = []
    idat = bytearray()

    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("truncated PNG (chunk header)")
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if len(chunk) < length:
            raise ValueError("truncated PNG (chunk body)")
        pos += 12 + length  # header + body + CRC (CRC not verified)

        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif ctype == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk) - 2, 3)]
        elif ctype == b"tRNS":
            trns = list(chunk)
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break

    if width is None or height is None:
        raise ValueError("PNG missing IHDR")
    if interlace != 0:
        raise ValueError("interlaced PNG not supported; re-save the golden without interlacing")
    if bit_depth not in (8, 16):
        raise ValueError(f"unsupported PNG bit depth {bit_depth} (need 8 or 16)")
    if color_type not in (0, 2, 3, 4, 6):
        raise ValueError(f"unsupported PNG color type {color_type}")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    bytes_per_sample = 2 if bit_depth == 16 else 1
    bpp = channels * bytes_per_sample  # bytes per pixel (filter unit)
    stride = width * bpp
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise ValueError(f"corrupt PNG image data: {exc}") from exc
    expected = (stride + 1) * height
    if len(raw) < expected:
        raise ValueError(f"truncated PNG image data ({len(raw)} < {expected} bytes)")

    # Undo per-scanline filtering.
    pixels_raw = bytearray(stride * height)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        filt = raw[src]
        src += 1
        line = bytearray(raw[src:src + stride])
        src += stride
        if filt == 1:  # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif filt == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:  # Average
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:  # Paeth
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = prev[i]
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, up, up_left)) & 0xFF
        elif filt != 0:
            raise ValueError(f"unknown PNG filter type {filt}")
        pixels_raw[y * stride:(y + 1) * stride] = line
        prev = line

    # Convert to luma floats in 0..1.
    gray: list[float] = []
    if color_type == 3:
        for idx in pixels_raw:
            if idx >= len(palette):
                raise ValueError("palette index out of range")
            r, g, b = palette[idx]
            gray.append((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0)
        return width, height, gray

    step = bpp
    if bit_depth == 16:
        # Take the high byte; matches how Blender/viewers display 16-bit PNGs.
        samples = pixels_raw[0::2]
    else:
        samples = pixels_raw
    if color_type == 0 or color_type == 4:
        gray = [v / 255.0 for v in samples[0::channels]]
    else:  # RGB / RGBA
        for i in range(0, len(samples), channels):
            r, g, b = samples[i], samples[i + 1], samples[i + 2]
            gray.append((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0)
    return width, height, gray


def encode_png_gray(width: int, height: int, gray: list[float]) -> bytes:
    """Encode luma floats (0..1) as an 8-bit grayscale PNG. Used for fixtures."""
    if len(gray) != width * height:
        raise ValueError("pixel count does not match dimensions")
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        for x in range(width):
            v = gray[y * width + x]
            raw.append(max(0, min(255, int(round(v * 255)))))

    def chunk(ctype: bytes, body: bytes) -> bytes:
        out = struct.pack(">I", len(body)) + ctype + body
        out += struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def resample_nearest(
    pixels: list[float], src_w: int, src_h: int, dst_w: int, dst_h: int
) -> list[float]:
    """Nearest-neighbour resample of a luma buffer."""
    if (src_w, src_h) == (dst_w, dst_h):
        return list(pixels)
    out = []
    for y in range(dst_h):
        sy = min(src_h - 1, int(y * src_h / dst_h))
        base = sy * src_w
        for x in range(dst_w):
            sx = min(src_w - 1, int(x * src_w / dst_w))
            out.append(pixels[base + sx])
    return out


def compare_luma(
    a: list[float], b: list[float]
) -> dict:
    """PSNR / SSIM / MAE between two equal-length luma buffers (0..1 floats).

    PSNR is reported in dB against peak 1.0; identical images give
    psnr = inf and ssim = 1.0.
    """
    if len(a) != len(b):
        raise ValueError(f"pixel count mismatch ({len(a)} vs {len(b)})")
    n = len(a)
    if n == 0:
        raise ValueError("empty image")

    mse = 0.0
    mae = 0.0
    sum_a = 0.0
    sum_b = 0.0
    for x, y in zip(a, b):
        diff = x - y
        mse += diff * diff
        mae += abs(diff)
        sum_a += x
        sum_b += y
    mse /= n
    mae /= n
    mean_a = sum_a / n
    mean_b = sum_b / n

    var_a = 0.0
    var_b = 0.0
    cov = 0.0
    for x, y in zip(a, b):
        da = x - mean_a
        db = y - mean_b
        var_a += da * da
        var_b += db * db
        cov += da * db
    var_a /= n
    var_b /= n
    cov /= n

    psnr = float("inf") if mse == 0.0 else -10.0 * math.log10(mse)
    c1 = _K1 * _K1
    c2 = _K2 * _K2
    ssim = ((2 * mean_a * mean_b + c1) * (2 * cov + c2)) / (
        (mean_a * mean_a + mean_b * mean_b + c1) * (var_a + var_b + c2)
    )
    return {
        "psnr_db": psnr,
        "ssim": max(-1.0, min(1.0, ssim)),
        "mae": mae,
        "pixels_compared": n,
    }


def compare_png_bytes(render_png: bytes, golden_png: bytes) -> dict:
    """Compare two PNG byte strings; golden is resampled to the render's size.

    Returns compare_luma() metrics plus both dimensions and a flag noting
    whether resampling happened (a size mismatch is itself worth seeing).
    """
    rw, rh, rp = decode_png_gray(render_png)
    gw, gh, gp = decode_png_gray(golden_png)
    resampled = (gw, gh) != (rw, rh)
    if resampled:
        gp = resample_nearest(gp, gw, gh, rw, rh)
    metrics = compare_luma(rp, gp)
    metrics.update(
        {
            "render_size": [rw, rh],
            "golden_size": [gw, gh],
            "golden_resampled": resampled,
        }
    )
    return metrics
