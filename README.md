# RatScannerData

Automated release builder for the runtime data consumed by
[RatScanner](https://github.com/TarkovTracker-org/RatScanner).

This repository intentionally does **not** track generated item images. Its
workflow downloads authoritative upstream inputs, validates them, converts
transparent item base images to the PNG format expected by RatEye, and
publishes the result as a single `Data.zip` release asset.

Catalog entries that still point to tarkov.dev's generic unknown-item
placeholder are recorded in the manifest and omitted from template matching.
Publishing the same placeholder under many item IDs would create ambiguous,
incorrect scan results.

## Bundle contents

`Data.zip` preserves RatScanner's established package contract:

- `icons/{item-id}.png` generated from tarkov.dev `baseImageLink` assets;
- `maps.json` from the maintained tarkov.dev web application;
- `traineddata/*.traineddata` from `tesseract-ocr/tessdata_fast`;
- `unknown.png` generated from the tarkov.dev unknown-item base image;
- a source manifest and third-party license notices.

The builder code is MIT-licensed. Generated archives contain third-party,
game-derived images that are not covered by this repository's MIT license.
RatScanner and TarkovTracker do not claim ownership of those images. All
applicable rights remain with Battlestate Games and their respective owners.
RatScanner is not affiliated with or endorsed by Battlestate Games or
tarkov.dev.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for sources and license
details.

## Build locally

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff check scripts
.\.venv\Scripts\ruff format --check scripts
.\.venv\Scripts\python scripts\build_data.py
.\.venv\Scripts\python scripts\validate_archive.py build\release\Data.zip
```

Outputs are written under `build/` and remain untracked.

## Release automation

The `Build data bundle` workflow supports:

- `validate`: build and retain a workflow artifact without creating a release;
- `draft`: create a draft GitHub release for maintainer verification;
- `publish`: create the published `latest` release;
- a monthly schedule that publishes only when validated content changes.

The workflow also supports manual runs after major Escape from Tarkov patches.
Every build downloads from upstream once on the GitHub runner, allowing
RatScanner users to retain the existing single-request `Data.zip` setup.

## Source endpoints

| Data | Source |
| --- | --- |
| Item catalog | `https://json.tarkov.dev/regular/items` |
| Item base images | Item `baseImageLink` values hosted on `assets.tarkov.dev` |
| Interactive maps | `the-hideout/tarkov-dev/src/data/maps.json` |
| OCR models | `tesseract-ocr/tessdata_fast` release `4.1.0` |
