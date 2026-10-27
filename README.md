<div align="center">
  <h1>iCloud Photos Takeout Organizer</h1>
  <p><strong>Turn an iCloud Photos export into a browsable local library.</strong></p>
  <p>A small Python tool for photos, videos, Live Photos, and albums.</p>
  <p>
    <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776ab" />
    <img alt="Platforms: macOS, Linux, Windows" src="https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-2878e8" />
  </p>
</div>

---

## At a glance

The organizer copies media from iCloud Photos export folders or ZIP archives into a dated library. It rebuilds albums from Apple's CSV files and keeps the original export untouched.

- **Browse by year:** media with a usable capture date go into `Fotos/YYYY/`.
- **Keep albums:** album members are copied into `Albums/<album name>/`.
- **Keep Live Photos together:** matching image and video filenames share a capture date.
- **Review uncertain dates:** files without a usable embedded timestamp go into `Files Without Metadata/`.
- **Preview first:** `--dry-run` reports the planned work without copying files.

## Get started

Requires Python 3.10 or later. Install [ExifTool](https://exiftool.org/) to read capture dates from media and write date metadata into the copied files. Without it, files use filesystem modification times and go into `Files Without Metadata/`.

From the repository root, preview an export:

```bash
python3 organize_icloud_photos_takeout.py \
  -i "/path/to/iCloud Photos.zip" \
  -o "/path/to/Organized Photos" \
  --dry-run
```

Check the summary, then run the same command without `--dry-run` to create the output. On Windows, use `py` in place of `python3`. Pass multiple folders or ZIP files after `-i` when an export is split into parts.

See [Usage](docs/USAGE.md) for installation, all options, split exports, and troubleshooting.

## Output

```text
Organized Photos/
  Fotos/
    2024/
      2024-05-01_13-25-10__IMG_1234.HEIC
      2024-05-01_13-25-10__IMG_1234__live.MOV
  Albums/
    Vacation/
      2024-05-01_13-25-10__IMG_1234.HEIC
  Files Without Metadata/
    2024-05-01_13-25-10__UNKNOWN_VIDEO.MP4
```

Album folders contain separate media copies, so an item can appear both in `Fotos/` and in one or more albums. Output filenames are prefixed with a timestamp; a file without an embedded capture date uses its filesystem modification time for that prefix.

## File and metadata behavior

Source files are not modified. The organizer skips CSV, AppleDouble `._*`, and other non-media files in the output. It can correct an obvious image extension mismatch and, when ExifTool is available, embed date metadata into copied media. Read [Library behavior](docs/LIBRARY_BEHAVIOR.md) before processing a large export.

## Documentation

- [Usage](docs/USAGE.md) — setup, commands, options, and troubleshooting.
- [Library behavior](docs/LIBRARY_BEHAVIOR.md) — folder layout, dates, albums, Live Photos, and safety.

## Project status

This is a standalone Python script for iCloud Photos exports. Run a dry run and inspect the copied library before discarding any original export.
