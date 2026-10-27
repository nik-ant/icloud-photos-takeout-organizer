# Usage

## Requirements

- Python 3.10 or newer.
- [ExifTool](https://exiftool.org/) is optional but strongly recommended for correct capture dates.
- Enough free space for ZIP extraction and the output copies, including copies for album membership.

Install Python and ExifTool with your system package manager. Examples:

```bash
# macOS with Homebrew
brew install python exiftool

# Debian or Ubuntu
sudo apt install python3 libimage-exiftool-perl

# Fedora
sudo dnf install python3 perl-Image-ExifTool
```

On Windows, install Python and ExifTool with `winget` or another trusted package manager. Use `py` instead of `python3` in the commands below.

## Run the organizer

Download or clone this repository and run commands from its root directory. Start with a dry run:

```bash
python3 organize_icloud_photos_takeout.py \
  -i "/path/to/iCloud Photos.zip" \
  -o "/path/to/Organized Photos" \
  --dry-run
```

After reviewing the summary, omit `--dry-run` to create the output. The input can also be an already extracted iCloud Photos folder.

For a split export, supply every part after `-i`:

```bash
python3 organize_icloud_photos_takeout.py \
  -i "/path/to/iCloud Photos Part 1.zip" "/path/to/iCloud Photos Part 2.zip" \
  -o "/path/to/Organized Photos" \
  --work-dir "/path/to/takeout-work" \
  --dry-run
```

`--work-dir` selects where ZIP files are extracted. If omitted, extraction uses a temporary directory beside the output. A specified work directory is not removed automatically; check its contents before reusing it. Choose a fresh output directory for each important run.

## Options

- `-i`, `--input`: one or more export folders or ZIP files; required.
- `-o`, `--output`: destination directory; required.
- `--dry-run`: scan and report without copying output files.
- `--work-dir PATH`: directory for temporary ZIP extraction.
- `--no-albums`: skip album copies.
- `--include-memories`: also create album folders from Memories CSV files.
- `--no-embed-metadata`: do not write date metadata into copied media.
- `--no-embedded-metadata`: skip reading embedded timestamps; files use filesystem times and go to `Files Without Metadata/`. Avoid this for a final run.
- `--verbose`: print each planned or copied file path.

Run `python3 organize_icloud_photos_takeout.py --help` for the current command reference.

## Troubleshooting

### Input does not exist

Check that every path after `-i` exists and is a folder or ZIP archive. Quote paths containing spaces.

### Extraction fails or the disk fills up

Use `--work-dir` on a disk with enough free space. ZIP extraction and album copies can require substantially more space than the archive itself.

### Many files appear in `Files Without Metadata`

Install ExifTool and rerun without `--no-embedded-metadata`. The script intentionally keeps files without an embedded capture timestamp separate for review.

### Album names contain strange characters

The script repairs common ZIP filename encoding problems. Use a fresh output directory when rerunning an export processed by an older version.

### ExifTool reports invalid media

The copy may still succeed, but embedded metadata cannot always be written into a damaged or unexpected file. Review the reported file and the copied output.
