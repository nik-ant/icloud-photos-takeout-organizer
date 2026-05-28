# iCloud Photos Takeout Organizer

A Python script for organizing an iCloud Photos Takeout export into a clean local photo library.

The script reads iCloud Photos media files, embedded media metadata, and iCloud album CSV files. It creates a chronological folder structure while preserving albums. It is designed for exports that contain photos, videos, Live Photos, localized iCloud folder names, album CSV files, and split zip exports such as `iCloud Fotos Teil 1 von 2.zip`.

Original Takeout files are never modified. The script copies files into a new output folder.

## What The Script Does

- Organizes the main photo library into `Fotos/YYYY/`.
- Recreates iCloud Photos albums under `Albums/<album name>/`.
- Sorts files chronologically by prefixing output filenames with the capture timestamp.
- Keeps Live Photo videos next to the matching photo.
- Reads embedded media timestamps with `exiftool`.
- Places files with no usable embedded timestamp metadata into `Files Without Metadata/`.
- Corrects obvious wrong file extensions, for example JPEG data saved with the wrong extension.
- Embeds date metadata into copied files when `exiftool` is installed.
- Uses iCloud album CSV files only for album membership; CSV files are not copied to the output.
- Repairs common iCloud zip filename encoding problems in album names.
- Shows progress while extracting, scanning, and organizing.

## Output Structure

Example:

```text
Organized Photos/
  Fotos/
    2024/
      2024-05-01_13-25-10__IMG_1234.HEIC
      2024-05-01_13-25-10__IMG_1234__live.MOV
  Albums/
    Vacation/
      2024-05-01_13-25-10__IMG_1234.HEIC
      2024-05-01_13-25-10__IMG_1234__live.MOV
  Files Without Metadata/
    2026-05-19_11-57-07__UNKNOWN_VIDEO.MP4
```

`Fotos/` contains the general chronological library.

`Albums/` contains recreated iCloud Photos albums.

`Files Without Metadata/` contains only files where the script could not find a usable embedded capture timestamp.

The output contains photo and video files only. CSV files, AppleDouble `._*` files, and other non-media files are skipped.

## Metadata Behavior

The script chooses dates in this order:

1. Embedded media metadata via `exiftool`
2. Matching Live Photo still-image metadata for Live Photo videos
3. Filesystem modification time as a last fallback

Files using the last fallback are not placed into normal year folders. They are placed into `Files Without Metadata/` for manual review.

If `exiftool` is installed, the script also writes date metadata into copied media files. If `exiftool` is not installed, the script cannot reliably read iCloud capture dates, so many files may be treated as missing metadata.

iCloud album CSV files are used only to rebuild `Albums/<album name>/`. They are never copied to the organized output.

## Requirements

- Python 3.10 or newer
- Optional but strongly recommended: `exiftool`

Install requirements:

| System | Python | ExifTool |
| --- | --- | --- |
| macOS | `brew install python` | `brew install exiftool` |
| Linux, Debian/Ubuntu | `sudo apt install python3` | `sudo apt install libimage-exiftool-perl` |
| Linux, Fedora | `sudo dnf install python3` | `sudo dnf install perl-Image-ExifTool` |
| Windows, winget | `winget install Python.Python.3` | `winget install OliverBetz.ExifTool` |
| Windows, Chocolatey | `choco install python` | `choco install exiftool` |

After installation, verify:

| System | Command |
| --- | --- |
| macOS/Linux | `python3 --version` |
| Windows | `py --version` |
| All systems | `exiftool -ver` |

## Basic Usage

Download or clone this repository, then open a terminal in the project folder.

| System | Example project folder command |
| --- | --- |
| macOS/Linux | `cd ~/Projects/icloud-photos-takeout-organizer` |
| Windows PowerShell | `cd "$HOME\Projects\icloud-photos-takeout-organizer"` |

Run a dry run first. A dry run prints what would happen without copying files:

| System | Dry run command |
| --- | --- |
| macOS/Linux | `python3 organize_icloud_photos_takeout.py -i "/path/to/icloud-photos.zip" -o "/path/to/organized-output" --dry-run` |
| Windows PowerShell | `py organize_icloud_photos_takeout.py -i "C:\Path\To\icloud-photos.zip" -o "C:\Path\To\organized-output" --dry-run` |

Run the real copy:

| System | Real run command |
| --- | --- |
| macOS/Linux | `python3 organize_icloud_photos_takeout.py -i "/path/to/icloud-photos.zip" -o "/path/to/organized-output"` |
| Windows PowerShell | `py organize_icloud_photos_takeout.py -i "C:\Path\To\icloud-photos.zip" -o "C:\Path\To\organized-output"` |

You can also pass an already extracted iCloud Photos folder:

| System | Extracted folder command |
| --- | --- |
| macOS/Linux | `python3 organize_icloud_photos_takeout.py -i "/path/to/iCloud Photos" -o "/path/to/organized-output"` |
| Windows PowerShell | `py organize_icloud_photos_takeout.py -i "C:\Path\To\iCloud Photos" -o "C:\Path\To\organized-output"` |

## Multiple Zip Exports

iCloud may split large exports into several zip files. Pass all parts after `-i`:

```bash
python3 organize_icloud_photos_takeout.py \
  -i "/path/to/iCloud Fotos Teil 1 von 2.zip" \
     "/path/to/iCloud Fotos Teil 2 von 2.zip" \
  -o "/path/to/organized-output" \
  --dry-run
```

Then run the real copy without `--dry-run`:

```bash
python3 organize_icloud_photos_takeout.py \
  -i "/path/to/iCloud Fotos Teil 1 von 2.zip" \
     "/path/to/iCloud Fotos Teil 2 von 2.zip" \
  -o "/path/to/organized-output"
```

## Recommended Command For Large Zip Exports

For large zip files, use `--work-dir` so temporary extraction happens in a known folder with enough free disk space:

| System | Large zip command |
| --- | --- |
| macOS | `python3 organize_icloud_photos_takeout.py -i "/path/to/icloud-photos.zip" -o "/path/to/organized-output" --work-dir /tmp/icloud-takeout-work` |
| Linux | `python3 organize_icloud_photos_takeout.py -i "/path/to/icloud-photos.zip" -o "/path/to/organized-output" --work-dir /tmp/icloud-takeout-work` |
| Windows PowerShell | `py organize_icloud_photos_takeout.py -i "C:\Path\To\icloud-photos.zip" -o "C:\Path\To\organized-output" --work-dir "$env:TEMP\icloud-takeout-work"` |

Use a new output folder for each important run. This avoids mixing older test output with new results.

## Example Workflow On macOS

| Step | Command |
| --- | --- |
| Open project | `cd "/Users/nik-ant/Visual Studio Code Projects/iCloud Photos Takeout Organizer"` |
| Preview | `python3 organize_icloud_photos_takeout.py -i "/Volumes/LaCie/Yaroslava/Photos & Pictures/Apple Backup/iCloud Fotos Teil 1 von 2.zip" "/Volumes/LaCie/Yaroslava/Photos & Pictures/Apple Backup/iCloud Fotos Teil 2 von 2.zip" -o "/Volumes/LaCie/Yaroslava/Photos & Pictures/Organized Photos" --work-dir "/Volumes/LaCie/Yaroslava/Photos & Pictures/icloud-takeout-work" --dry-run` |
| Organize | `python3 organize_icloud_photos_takeout.py -i "/Volumes/LaCie/Yaroslava/Photos & Pictures/Apple Backup/iCloud Fotos Teil 1 von 2.zip" "/Volumes/LaCie/Yaroslava/Photos & Pictures/Apple Backup/iCloud Fotos Teil 2 von 2.zip" -o "/Volumes/LaCie/Yaroslava/Photos & Pictures/Organized Photos" --work-dir "/Volumes/LaCie/Yaroslava/Photos & Pictures/icloud-takeout-work"` |
| Organize already extracted folders | `python3 organize_icloud_photos_takeout.py -i "/Volumes/LaCie/Yaroslava/Photos & Pictures/icloud-takeout-work/iCloud Fotos Teil 1 von 2" "/Volumes/LaCie/Yaroslava/Photos & Pictures/icloud-takeout-work/iCloud Fotos Teil 2 von 2" -o "/Volumes/LaCie/Yaroslava/Photos & Pictures/Organized Photos" --work-dir "/Volumes/LaCie/Yaroslava/Photos & Pictures/icloud-takeout-work"` |

## Useful Options

| Option | Description |
| --- | --- |
| `--dry-run` | Preview the planned output without copying files. |
| `--work-dir /path/to/temp-folder` | Choose where zip archives are extracted temporarily. |
| `--no-albums` | Only create `Fotos/` and `Files Without Metadata/`. |
| `--include-memories` | Also recreate iCloud Memories CSVs under `Albums/`. |
| `--no-embed-metadata` | Do not write metadata into copied media files, even if `exiftool` is installed. |
| `--no-embedded-metadata` | Skip reading embedded media timestamps during scanning. Useful only for fast folder-layout tests. Do not use it for final runs, because iCloud files may be placed into `Files Without Metadata/` without embedded metadata. |
| `--verbose` | Print every planned or copied file path. |

## Live Photos

iCloud Photos may export an Apple Live Photo as an image plus a short video. The script detects pairs by matching files with the same base name.

Example:

```text
IMG_1234.HEIC
IMG_1234.MOV
```

Output:

```text
2024-05-01_13-25-10__IMG_1234.HEIC
2024-05-01_13-25-10__IMG_1234__live.MOV
```

The Live Photo video uses the still photo timestamp, so both files stay together in the same year folder and album folders.

## Albums

iCloud Photos Takeout stores album membership in CSV files inside the `Albums/` folder. The script reads those CSV files and creates media-only copies in:

```text
Albums/<album name>/
```

The same media file can appear in both `Fotos/YYYY/` and one or more album folders. This is intentional, because albums are separate copies for easy browsing.

## Troubleshooting

### `Input does not exist`

Check that the path exists:

| System | Command |
| --- | --- |
| macOS/Linux | `ls "/path/to/icloud-folder-or-zip"` |
| Windows PowerShell | `Test-Path "C:\Path\To\icloud-photos.zip"` |

### `PermissionError` while extracting a zip

Use `--work-dir`:

| System | Command |
| --- | --- |
| macOS/Linux | `python3 organize_icloud_photos_takeout.py -i "/path/to/icloud-photos.zip" -o "/path/to/organized-output" --work-dir /tmp/icloud-takeout-work` |
| Windows PowerShell | `py organize_icloud_photos_takeout.py -i "C:\Path\To\icloud-photos.zip" -o "C:\Path\To\organized-output" --work-dir "$env:TEMP\icloud-takeout-work"` |

### Many files appear in `Files Without Metadata`

Install `exiftool` and run again without `--no-embedded-metadata`:

| System | Command |
| --- | --- |
| macOS | `brew install exiftool` |
| Debian/Ubuntu | `sudo apt install libimage-exiftool-perl` |
| Fedora | `sudo dnf install perl-Image-ExifTool` |
| Windows, winget | `winget install OliverBetz.ExifTool` |

### Album names show strange symbols

Update to the current script and run again. The script repairs common iCloud zip filename encoding problems before creating album folders.

If output was already created with broken album names, rename those album folders or rerun into a fresh output folder.

### Warnings about invalid media files

Some exports contain media files with damaged metadata or unexpected file format data. The script still copies the file when possible, but `exiftool` may not be able to write metadata into that copied file.

## Safety Notes

- The script copies files. It does not delete or modify your original iCloud Photos Takeout export.
- Use `--dry-run` before a real run.
- Use a fresh output folder for each full run.
- Keep the original Takeout zip or folder until you have checked the organized output.
