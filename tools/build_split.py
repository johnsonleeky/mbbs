#!/usr/bin/env python3
"""
Build the split, on-demand-figure version of the MBBS question bank.

The master stays a single self-contained HTML file. This script reads it and
writes the deployable site to the repository root:

    index.html          (~9 MB, no embedded images)
    figures/            (WebP figures, loaded only when shown)
    .nojekyll
    robots.txt

Figures are resized and re-encoded at build time; the master keeps the
original images. Requires Pillow (`python3 -m pip install Pillow`).

Usage:
    python3 tools/build_split.py
    python3 tools/build_split.py "/path/to/MBBS_QBank_AI_Answers.html"
    python3 tools/build_split.py --zip

Run from anywhere; paths are resolved relative to this file.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "Pillow is required for image optimisation. "
        "Install it with: python3 -m pip install Pillow"
    ) from exc

SITE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path("/Users/johnson/Desktop/MBBS_QBank_AI_Answers.html")
DEFAULT_OUT = SITE_ROOT
DEFAULT_ZIP = SITE_ROOT / "MBBS_QBank_split.zip"

APP_DATA_RE = re.compile(
    r'(<script id="appData" type="application/json">)(.*?)(</script>)',
    re.S,
)

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def extension_for(mime: str) -> str:
    return {
        "jpeg": "jpg",
        "svg+xml": "svg",
    }.get(mime, mime)


# The question card is at most about 960 CSS pixels wide, so 1920 px is a
# full 2x image on a retina display without shipping print-sized scans.
MAX_IMAGE_SIDE = 1920
VARIANT_WIDTH = 960
WEBP_QUALITY = 95


def optimize_image(raw: bytes, mime: str) -> tuple[bytes, str, bool, int, int]:
    """Return (payload, extension, was_optimised, width, height).

    Converts static raster figures to high-quality WebP and caps their longest
    side. Already-efficient WebP files, animated images, SVGs and anything that
    would grow are shipped byte-for-byte, so quality never regresses.
    """
    if mime in ("svg+xml", "gif"):
        return raw, extension_for(mime), False, 0, 0

    try:
        with Image.open(io.BytesIO(raw)) as image:
            source_format = (image.format or "").upper()
            if getattr(image, "is_animated", False) and getattr(image, "n_frames", 1) > 1:
                return raw, extension_for(mime), False, 0, 0

            icc_profile = image.info.get("icc_profile")
            image = ImageOps.exif_transpose(image)

            if image.mode in ("P", "LA"):
                has_alpha = image.mode == "LA" or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
            elif image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")

            original_width, original_height = image.size
            width, height = original_width, original_height
            scale = min(1.0, MAX_IMAGE_SIDE / max(width, height))
            resized = scale < 1.0
            if resized:
                image = image.resize(
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    Image.Resampling.LANCZOS,
                )
                width, height = image.size

            # Re-encoding a WebP that is already an efficient delivery size only
            # adds a generation of loss, so leave it untouched.
            if source_format == "WEBP" and not resized:
                return raw, "webp", False, width, height

            buffer = io.BytesIO()
            save_options = {
                "format": "WEBP",
                "quality": WEBP_QUALITY,
                "method": 6,
                "alpha_quality": 100,
            }
            if icc_profile:
                save_options["icc_profile"] = icc_profile
            image.save(buffer, **save_options)
            optimized = buffer.getvalue()

            if len(optimized) >= len(raw):
                return raw, extension_for(mime), False, original_width, original_height
            return optimized, "webp", True, width, height
    except Exception as exc:
        print(
            f"WARNING: figure could not be optimised ({exc}); keeping original",
            file=sys.stderr,
        )
        return raw, extension_for(mime), False, 0, 0


def make_variant(payload: bytes, target_width: int) -> bytes | None:
    """Build a smaller WebP for narrow screens, or return None."""
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image = ImageOps.exif_transpose(image)
            if image.width <= target_width:
                return None
            if image.mode in ("P", "LA"):
                has_alpha = image.mode == "LA" or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
            elif image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            height = max(1, round(image.height * target_width / image.width))
            image = image.resize((target_width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(
                buffer,
                format="WEBP",
                quality=WEBP_QUALITY,
                method=6,
                alpha_quality=100,
            )
            variant = buffer.getvalue()
            return variant if len(variant) < len(payload) else None
    except Exception as exc:
        print(
            f"WARNING: responsive figure could not be created ({exc})",
            file=sys.stderr,
        )
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help=f"master HTML file (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"output folder (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help=f"also write {DEFAULT_ZIP.name} for sharing",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if not source.is_file():
        fail(f"master not found: {source}")

    source_bytes = source.read_bytes()
    html = source_bytes.decode("utf-8")
    print(f"Master : {source}")
    print(f"Size   : {len(source_bytes):,} bytes")

    matches = list(APP_DATA_RE.finditer(html))
    if len(matches) != 1:
        fail(f"expected exactly one appData block, found {len(matches)}")
    match = matches[0]

    try:
        data = json.loads(match.group(2))
    except json.JSONDecodeError as exc:
        fail(f"appData is not valid JSON: {exc}")

    assets = data.get("imageAssets")
    if not isinstance(assets, list) or not assets:
        fail("appData.imageAssets is missing or empty")

    # Verify every image reference points at an asset. This catches a malformed
    # build before anything is written.
    referenced: set[int] = set()
    for area in data.get("areas", []):
        for part in area.get("parts", []):
            for question in part.get("questions", []):
                for ref in question.get("images") or []:
                    referenced.add(int(ref))
                for block in question.get("expl") or []:
                    if block.get("k") == "img":
                        referenced.add(int(block.get("t")))
    expected = set(range(len(assets)))
    extra = sorted(referenced - expected)
    if extra:
        fail(f"image references point at missing assets (extra={extra[:10]})")
    unused = sorted(expected - referenced)
    if unused:
        print(f"Unused image assets: {len(unused)} (kept in figures/)")

    out.mkdir(parents=True, exist_ok=True)
    figures_dir = out / "figures"
    figures_tmp = out / "figures.tmp"
    if figures_tmp.exists():
        shutil.rmtree(figures_tmp)
    figures_tmp.mkdir()

    replacements: dict[str, str] = {}
    image_meta: dict[str, dict[str, object]] = {}
    figure_bytes = 0
    original_figure_bytes = 0
    optimized_count = 0
    kept_count = 0
    variant_count = 0
    for index, uri in enumerate(assets):
        if not isinstance(uri, str) or not uri.startswith("data:image/"):
            fail(f"asset {index} is not a data:image URI")
        if "," not in uri:
            fail(f"asset {index} has no data payload")
        header, payload = uri.split(",", 1)
        if ";base64" not in header:
            fail(f"asset {index} is not base64-encoded")
        mime = header.split(";", 1)[0].split("/", 1)[1]
        try:
            raw = base64.b64decode(payload, validate=True)
        except Exception as exc:
            fail(f"asset {index} could not be decoded: {exc}")

        output, extension, optimized, width, height = optimize_image(raw, mime)
        original_figure_bytes += len(raw)
        figure_bytes += len(output)
        optimized_count += int(optimized)
        kept_count += int(not optimized)
        digest = hashlib.sha256(output).hexdigest()[:10]
        filename = f"fig-{index:03d}-{digest}.{extension}"
        (figures_tmp / filename).write_bytes(output)
        relative_path = f"figures/{filename}"
        replacements[uri] = relative_path

        meta: dict[str, object] = {"w": width, "h": height}
        if width > VARIANT_WIDTH and extension in ("webp", "jpg", "png"):
            variant = make_variant(output, VARIANT_WIDTH)
            if variant:
                variant_name = f"{Path(filename).stem}-{VARIANT_WIDTH}.webp"
                (figures_tmp / variant_name).write_bytes(variant)
                figure_bytes += len(variant)
                variant_count += 1
                meta["s"] = (
                    f"figures/{variant_name} {VARIANT_WIDTH}w, "
                    f"{relative_path} {width}w"
                )
        image_meta[relative_path] = meta

    # Swap the generated figures into place only after the whole batch succeeds.
    if figures_dir.exists():
        shutil.rmtree(figures_dir)
    figures_tmp.rename(figures_dir)

    # Replace each complete data URI textually. No JSON re-serialisation, so
    # every other byte of the app data (and the HTML) is preserved.
    app_json = match.group(2)
    for uri, relative_path in replacements.items():
        count = app_json.count(uri)
        if count != 1:
            fail(f"expected one occurrence of asset data, found {count}")
        app_json = app_json.replace(uri, relative_path)

    if "data:image/" in app_json:
        fail("image data still present after replacing assets")

    split_html = html[: match.start(2)] + app_json + html[match.end(2) :]

    if "function imageAttrs(" not in split_html:
        fail("imageAttrs helper not found; master markup may have changed")

    app_marker = '<script>\n"use strict";'
    if split_html.count(app_marker) != 1:
        fail("application script marker not found; master markup may have changed")
    meta_json = json.dumps(image_meta, separators=(",", ":"))
    split_html = split_html.replace(
        app_marker,
        f"<script>window.IMAGE_META={meta_json};</script>\n{app_marker}",
        1,
    )

    index_path = out / "index.html"
    index_path.write_bytes(split_html.encode("utf-8"))
    (out / ".nojekyll").write_bytes(b"")
    (out / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n",
        encoding="utf-8",
    )

    saved_pct = 100 * (1 - figure_bytes / original_figure_bytes) if original_figure_bytes else 0
    print(f"Split  : {index_path}")
    print(f"HTML   : {index_path.stat().st_size:,} bytes")
    print(
        f"Figures: {len(assets)} files + {variant_count} responsive variants, "
        f"{figure_bytes / 1_000_000:.1f} MB "
        f"(from {original_figure_bytes / 1_000_000:.1f} MB, {saved_pct:.0f}% smaller)"
    )
    print(f"Images : {optimized_count} optimised, {kept_count} kept original")
    print(f"Total  : {(index_path.stat().st_size + figure_bytes) / 1_000_000:.1f} MB")

    if args.zip:
        zip_path = DEFAULT_ZIP
        if zip_path.exists():
            zip_path.unlink()
        # Zip only the published site, never tools/README/.git or the zip itself.
        site_files = [index_path, out / ".nojekyll", out / "robots.txt"]
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in site_files:
                archive.write(
                    path,
                    arcname=str(Path("MBBS_QBank_Split") / path.relative_to(out)),
                )
            for path in sorted(figures_dir.rglob("*")):
                if path.is_file():
                    archive.write(
                        path,
                        arcname=str(Path("MBBS_QBank_Split") / path.relative_to(out)),
                    )
        print(f"Zip    : {zip_path} ({zip_path.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
