#!/usr/bin/env python3
"""Validate a generated RatScanner Data.zip without extracting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath

SAFE_ICON = re.compile(r"^icons/[A-Za-z0-9_-]+\.png$")
REQUIRED = {
    "maps.json",
    "unknown.png",
    "traineddata/eng.traineddata",
    "manifest.json",
    "THIRD_PARTY_NOTICES.md",
    "licenses/tarkov-dev-MIT.txt",
    "licenses/tessdata-Apache-2.0.txt",
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_archive(path: str, minimum_icons: int) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        invalid = archive.testzip()
        if invalid:
            raise ValueError(f"Corrupt ZIP entry: {invalid}")

        names = archive.namelist()
        for name in names:
            archive_path = PurePosixPath(name)
            if archive_path.is_absolute() or ".." in archive_path.parts:
                raise ValueError(f"Unsafe ZIP entry: {name}")

        missing = REQUIRED.difference(names)
        if missing:
            raise ValueError(f"Missing required entries: {sorted(missing)}")

        icon_names = sorted(name for name in names if SAFE_ICON.fullmatch(name))
        if len(icon_names) < minimum_icons:
            raise ValueError(f"Only {len(icon_names)} icons; expected at least {minimum_icons}")
        unexpected_icon_entries = [
            name for name in names if name.startswith("icons/") and not SAFE_ICON.fullmatch(name)
        ]
        if unexpected_icon_entries:
            raise ValueError(f"Unexpected icon paths: {unexpected_icon_entries[:5]}")

        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schemaVersion") != 1:
            raise ValueError("Unsupported or missing manifest schemaVersion")
        if manifest.get("iconCount") != len(icon_names):
            raise ValueError(
                "Manifest iconCount does not match the archive: "
                f"{manifest.get('iconCount')} != {len(icon_names)}"
            )
        skipped_items = manifest.get("skippedItems")
        if not isinstance(skipped_items, list):
            raise ValueError("Manifest is missing skippedItems")
        if manifest.get("skippedItemCount") != len(skipped_items):
            raise ValueError("Manifest skippedItemCount is inconsistent")
        if manifest.get("catalogItemCount") != len(icon_names) + len(skipped_items):
            raise ValueError("Manifest catalogItemCount is inconsistent")

        entries = {
            entry["path"]: entry
            for entry in manifest.get("files", [])
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        }
        for icon_name in icon_names:
            content = archive.read(icon_name)
            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError(f"Icon is not PNG: {icon_name}")
            entry = entries.get(icon_name)
            if not entry:
                raise ValueError(f"Manifest is missing icon: {icon_name}")
            if sha256_bytes(content) != entry.get("sha256"):
                raise ValueError(f"Icon checksum mismatch: {icon_name}")
            width = entry.get("width")
            height = entry.get("height")
            if not isinstance(width, int) or width % 63 != 1:
                raise ValueError(f"Icon width is incompatible with RatEye: {icon_name}")
            if not isinstance(height, int) or height % 63 != 1:
                raise ValueError(f"Icon height is incompatible with RatEye: {icon_name}")

        maps = json.loads(archive.read("maps.json"))
        if not isinstance(maps, list) or not maps:
            raise ValueError("maps.json must be a non-empty array")

        print(f"Validated {path}: {len(icon_names)} icons, content {manifest['contentSha256']}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="Path to Data.zip")
    parser.add_argument(
        "--minimum-icons",
        type=int,
        default=4_000,
        help="Minimum accepted icon count (default: 4000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        arguments = parse_arguments()
        validate_archive(arguments.archive, arguments.minimum_icons)
    except Exception as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        raise
