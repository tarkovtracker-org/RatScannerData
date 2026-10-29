"""Offline checks for the pinned decoder and RatEye's generated data contract."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import PIL
from PIL import Image

from scripts import build_data, validate_archive

ROOT = Path(__file__).resolve().parent.parent


def image_bytes(mode: str, color: tuple[int, ...], image_format: str = "PNG") -> bytes:
    output = io.BytesIO()
    Image.new(mode, (64, 64), color).save(output, format=image_format, lossless=True)
    return output.getvalue()


class DecoderTests(unittest.TestCase):
    def test_runtime_and_development_use_the_patched_pillow_pin(self) -> None:
        requirement = (ROOT / "requirements.txt").read_text()
        match = re.search(r"^pillow==(\d+\.\d+\.\d+)\s", requirement, re.MULTILINE)
        self.assertIsNotNone(match)
        assert match is not None
        version = match.group(1)
        self.assertGreaterEqual(tuple(map(int, version.split("."))), (13, 0, 0))
        self.assertEqual(PIL.__version__, version)
        self.assertIn("-r requirements.txt", (ROOT / "requirements-dev.txt").read_text())

    def test_png_and_webp_preserve_pixels_dimensions_and_transparency(self) -> None:
        for image_format in ("PNG", "WEBP"):
            with self.subTest(image_format=image_format):
                png, width, height, transparent = build_data.png_from_image(
                    image_bytes("RGBA", (10, 20, 30, 128), image_format), "fixture"
                )
                self.assertEqual((width, height, transparent), (64, 64, True))
                with Image.open(io.BytesIO(png)) as rendered:
                    self.assertEqual(rendered.format, "PNG")
                    self.assertEqual(rendered.mode, "RGBA")
                    self.assertEqual(rendered.getpixel((0, 0)), (10, 20, 30, 128))

    def test_opaque_rgb_is_not_reported_as_transparent(self) -> None:
        _, width, height, transparent = build_data.png_from_image(
            image_bytes("RGB", (10, 20, 30)), "fixture"
        )
        self.assertEqual((width, height, transparent), (64, 64, False))

    def test_invalid_image_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Could not decode image"):
            build_data.png_from_image(b"not an image", "fixture")

    def test_offline_bundle_remains_deterministic_and_independently_valid(self) -> None:
        icon_url = "https://assets.tarkov.dev/test-item.webp"
        catalog = {
            "data": {
                "items": [
                    {"id": "test-item", "baseImageLink": icon_url, "width": 1, "height": 1},
                    {"id": "placeholder", "baseImageLink": build_data.UNKNOWN_IMAGE_URL},
                ]
            }
        }
        sources = {
            build_data.CATALOG_URL: json.dumps(catalog).encode(),
            icon_url: image_bytes("RGBA", (10, 20, 30, 128), "WEBP"),
            build_data.UNKNOWN_IMAGE_URL: image_bytes("RGBA", (0, 0, 0, 0)),
            build_data.MAPS_URL: json.dumps([{"normalizedName": "customs", "maps": []}]).encode(),
            f"{build_data.TESSDATA_BASE_URL}/eng.traineddata": b"x" * 100_000,
            build_data.TARKOV_DEV_LICENSE_URL: b"MIT fixture",
            build_data.TESSDATA_LICENSE_URL: b"Apache fixture",
        }
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(build_data, "fetch_bytes", side_effect=lambda url, **_: sources[url]),
            patch.object(build_data, "OCR_LANGUAGES", {"eng": "eng"}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            output = Path(temporary) / "bundle"
            arguments = argparse.Namespace(
                output=output, catalog_url=build_data.CATALOG_URL, workers=1, minimum_icons=1
            )
            archive = build_data.build(arguments)
            first = archive.read_bytes()
            validate_archive.validate_archive(str(archive), minimum_icons=1)
            with zipfile.ZipFile(archive) as bundle:
                manifest = json.loads(bundle.read("manifest.json"))
                self.assertEqual(manifest["schemaVersion"], 1)
                self.assertEqual(manifest["iconCount"], 1)
                self.assertEqual(manifest["skippedItemCount"], 1)
                icon = next(
                    entry for entry in manifest["files"] if entry["path"].startswith("icons/")
                )
                self.assertEqual(icon["renderedSlots"], {"width": 1, "height": 1})
                self.assertTrue(icon["slotDimensionsMatch"])
            self.assertEqual(build_data.build(arguments).read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
