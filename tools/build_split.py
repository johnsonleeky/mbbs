#!/usr/bin/env python3
"""
Build the split, on-demand-figure version of the MBBS question bank.

The master stays a single self-contained HTML file. This script reads it and
writes the deployable site to the repository root:

    index.html          (~9 MB, no embedded images)
    figures/            (345 figure files, loaded only when shown)
    .nojekyll
    robots.txt

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
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path("/Users/johnson/Desktop/MBBS_QBank_AI_Answers.html")
DEFAULT_OUT = SITE_ROOT
DEFAULT_ZIP = SITE_ROOT / "MBBS_QBank_split.zip"

APP_DATA_RE = re.compile(
    r'(<script id="appData" type="application/json">)(.*?)(</script>)',
    re.S,
)

QUESTION_IMG_OLD = (
    '<div class="expl-fig"><img src="${src}" '
    'alt="Figure from question ${q.n} in the source document"></div>'
)
QUESTION_IMG_NEW = (
    '<div class="expl-fig"><img src="${src}" '
    'alt="Figure from question ${q.n} in the source document" '
    'loading="lazy" decoding="async"></div>'
)

EXPL_IMG_OLD = (
    '<img src="${u.t}" alt="Figure from the source document" loading="lazy">'
)
EXPL_IMG_NEW = (
    '<img src="${u.t}" alt="Figure from the source document" '
    'loading="lazy" decoding="async">'
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def extension_for(mime: str) -> str:
    return {
        "jpeg": "jpg",
        "svg+xml": "svg",
    }.get(mime, mime)


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
    if referenced != expected:
        missing = sorted(expected - referenced)
        extra = sorted(referenced - expected)
        fail(f"image references do not match assets (missing={missing[:10]}, extra={extra[:10]})")

    out.mkdir(parents=True, exist_ok=True)
    figures_dir = out / "figures"
    if figures_dir.exists():
        shutil.rmtree(figures_dir)
    figures_dir.mkdir()

    replacements: dict[str, str] = {}
    figure_bytes = 0
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

        extension = extension_for(mime)
        digest = hashlib.sha256(raw).hexdigest()[:10]
        filename = f"fig-{index:03d}-{digest}.{extension}"
        (figures_dir / filename).write_bytes(raw)
        figure_bytes += len(raw)
        replacements[uri] = f"figures/{filename}"

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

    if QUESTION_IMG_OLD not in split_html:
        fail("question image template not found; app markup may have changed")
    split_html = split_html.replace(QUESTION_IMG_OLD, QUESTION_IMG_NEW, 1)

    if EXPL_IMG_OLD not in split_html:
        fail("explanation image template not found; app markup may have changed")
    split_html = split_html.replace(EXPL_IMG_OLD, EXPL_IMG_NEW, 1)

    index_path = out / "index.html"
    index_path.write_bytes(split_html.encode("utf-8"))
    (out / ".nojekyll").write_bytes(b"")
    (out / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n",
        encoding="utf-8",
    )

    print(f"Split  : {index_path}")
    print(f"HTML   : {index_path.stat().st_size:,} bytes")
    print(f"Figures: {len(assets)} files, {figure_bytes / 1_000_000:.1f} MB")
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
