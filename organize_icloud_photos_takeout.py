#!/usr/bin/env python3
"""
Organize an iCloud Photos export into dated media folders and album folders.

Output contains media files only:
  output/Fotos/YYYY/
  output/Albums/<album name>/
  output/Files Without Metadata/

iCloud CSV files are used only to rebuild Albums/. They are never copied.
Original files are never modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEDIA_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".ari",
    ".arw",
    ".avi",
    ".cr2",
    ".cr3",
    ".dng",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".m4v",
    ".mov",
    ".mp4",
    ".mts",
    ".nef",
    ".orf",
    ".png",
    ".raf",
    ".rw2",
    ".tif",
    ".tiff",
    ".webp",
}

PHOTO_EXTENSIONS = {
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".nef",
    ".orf",
    ".png",
    ".raf",
    ".rw2",
    ".tif",
    ".tiff",
    ".webp",
}

VIDEO_EXTENSIONS = {".3g2", ".3gp", ".avi", ".m4v", ".mov", ".mp4", ".mts"}
ICLOUD_ROOT_MARKERS = {"photos", "albums", "memories", "recently deleted"}
MEDIA_COLLECTIONS = {"photos", "recently deleted"}
SAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class Progress:
    def __init__(self, label: str, total: int, enabled: bool = True) -> None:
        self.label = label
        self.total = max(total, 0)
        self.enabled = enabled
        self.current = 0
        self.started_at = time.monotonic()
        self.last_draw = 0.0

    def advance(self, step: int = 1) -> None:
        self.current += step
        self.draw()

    def draw(self, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and now - self.last_draw < 0.1 and self.current < self.total:
            return
        self.last_draw = now
        width = 28
        if self.total:
            ratio = min(self.current / self.total, 1)
            filled = int(width * ratio)
            percent = ratio * 100
            count = f"{self.current}/{self.total}"
        else:
            filled = 0
            percent = 0
            count = str(self.current)
        elapsed = max(now - self.started_at, 0.001)
        rate = self.current / elapsed
        bar = "#" * filled + "-" * (width - filled)
        print(f"\r{self.label}: [{bar}] {percent:6.2f}% {count} ({rate:,.1f}/s)", end="", flush=True)

    def finish(self) -> None:
        if not self.enabled:
            return
        self.current = max(self.current, self.total)
        self.draw(force=True)
        print()


class CountProgress:
    def __init__(self, label: str, enabled: bool = True) -> None:
        self.label = label
        self.enabled = enabled
        self.started_at = time.monotonic()
        self.last_draw = 0.0
        self.current = 0

    def update(self, current: int, force: bool = False) -> None:
        self.current = current
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and now - self.last_draw < 0.25:
            return
        self.last_draw = now
        elapsed = max(now - self.started_at, 0.001)
        rate = self.current / elapsed
        print(f"\r{self.label}: {self.current:,} ({rate:,.1f}/s)", end="", flush=True)

    def finish(self) -> None:
        if not self.enabled:
            return
        self.update(self.current, force=True)
        print()


@dataclass(frozen=True)
class Metadata:
    timestamp: int | None
    timestamp_source: str
    latitude: float | None
    longitude: float | None
    altitude: float | None


@dataclass(frozen=True)
class MediaItem:
    path: Path
    metadata: Metadata
    albums: tuple[str, ...]
    collection: str

    @property
    def taken_at(self) -> datetime:
        if self.metadata.timestamp is not None:
            return datetime.fromtimestamp(self.metadata.timestamp, tz=timezone.utc)
        return datetime.fromtimestamp(self.path.stat().st_mtime, tz=timezone.utc)

    @property
    def timestamp_source(self) -> str:
        return self.metadata.timestamp_source if self.metadata.timestamp is not None else "filesystem-mtime"

    @property
    def is_photo(self) -> bool:
        return self.path.suffix.lower() in PHOTO_EXTENSIONS

    @property
    def is_video(self) -> bool:
        return self.path.suffix.lower() in VIDEO_EXTENSIONS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organize iCloud Photos Takeout media into dated photo folders and album folders."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        type=Path,
        help="One or more iCloud Photos Takeout folders or .zip archives to scan.",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=Path,
        help="Destination folder. It will be created if needed.",
    )
    parser.add_argument("--no-albums", action="store_true", help="Only create Fotos/ and Files Without Metadata/.")
    parser.add_argument(
        "--include-memories",
        action="store_true",
        help="Also recreate iCloud Memories CSVs under Albums/. Normal album CSVs are included by default.",
    )
    parser.add_argument(
        "--no-embed-metadata",
        action="store_true",
        help="Do not call exiftool after copying, even when it is installed.",
    )
    parser.add_argument(
        "--no-embedded-metadata",
        action="store_true",
        help="Do not read embedded media timestamps. Files will use filesystem mtimes and go to Files Without Metadata/.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Scan and print a summary without writing output files.")
    parser.add_argument("--verbose", action="store_true", help="Print every planned or copied media file.")
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Temporary extraction folder for .zip inputs. Defaults to a temp folder beside the output.",
    )
    return parser.parse_args()


def normalized_folder_name(name: str) -> str:
    return " ".join(name.casefold().replace("_", " ").replace("-", " ").split())


def sanitize_name(name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("_", unicodedata.normalize("NFC", name)).strip().strip(".")
    return cleaned or "Untitled Album"


def repair_zip_mojibake(name: str) -> str:
    normalized = unicodedata.normalize("NFC", name)
    try:
        return unicodedata.normalize("NFC", normalized.encode("cp437").decode("utf-8"))
    except UnicodeError:
        return normalized


def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def parse_exif_datetime(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.startswith("0000:00:00"):
        return None
    match = re.match(
        r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:([+-]\d{2}):?(\d{2})|Z)?$",
        value,
    )
    if not match:
        return None
    year, month, day, hour, minute, second, offset_hour, offset_minute = match.groups()
    try:
        parsed = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None
    if offset_hour and offset_minute:
        sign = 1 if offset_hour.startswith("+") else -1
        offset_seconds = sign * (abs(int(offset_hour)) * 3600 + int(offset_minute) * 60)
        parsed = datetime.fromtimestamp(parsed.timestamp() - offset_seconds, tz=timezone.utc)
    return int(parsed.timestamp())


def number_from_geo(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value not in (0, 0.0):
        return float(value)
    return None


def embedded_metadata(path: Path) -> tuple[int | None, float | None, float | None, float | None]:
    if not exiftool_available():
        return None, None, None, None
    command = [
        "exiftool",
        "-json",
        "-n",
        "-api",
        "QuickTimeUTC=1",
        "-DateTimeOriginal",
        "-CreateDate",
        "-MediaCreateDate",
        "-TrackCreateDate",
        "-ContentCreateDate",
        "-GPSLatitude",
        "-GPSLongitude",
        "-GPSAltitude",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        parsed = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None, None, None, None
    if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], dict):
        return None, None, None, None

    data = parsed[0]
    timestamp = None
    for key in ("DateTimeOriginal", "ContentCreateDate", "MediaCreateDate", "CreateDate", "TrackCreateDate"):
        timestamp = parse_exif_datetime(data.get(key))
        if timestamp is not None:
            break
    latitude = number_from_geo(data.get("GPSLatitude"))
    longitude = number_from_geo(data.get("GPSLongitude"))
    altitude = data.get("GPSAltitude")
    altitude = float(altitude) if isinstance(altitude, (int, float)) else None
    return timestamp, latitude, longitude, altitude


def csv_media_names(path: Path) -> list[str]:
    rows: list[list[str]] | None = None
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                rows = [row for row in csv.reader(handle) if row]
            break
        except (OSError, UnicodeError, csv.Error):
            continue
    if not rows:
        return []

    names: list[str] = []
    for row in rows[1:]:
        value = row[0].strip().strip('"')
        if value:
            names.append(value)
    return names


def build_album_index(input_roots: list[Path], include_memories: bool, show_progress: bool) -> dict[str, set[str]]:
    album_by_filename: dict[str, set[str]] = {}
    progress = CountProgress("Indexing iCloud album CSVs", enabled=show_progress)
    count = 0
    for root in input_roots:
        for csv_path in root.rglob("*.csv"):
            if ignored_source_path(csv_path):
                continue
            parts = {normalized_folder_name(part) for part in csv_path.parts}
            if "albums" in parts:
                album_name = sanitize_name(repair_zip_mojibake(csv_path.stem))
            elif include_memories and "memories" in parts:
                album_name = sanitize_name(repair_zip_mojibake(csv_path.stem))
            else:
                continue
            for name in csv_media_names(csv_path):
                for candidate in {name, repair_zip_mojibake(name)}:
                    album_by_filename.setdefault(candidate.casefold(), set()).add(album_name)
            count += 1
            progress.update(count)
    progress.finish()
    return album_by_filename


def ignored_source_path(path: Path) -> bool:
    return any(part == "__MACOSX" or part.startswith("._") for part in path.parts)


def media_root_kind(path: Path, input_roots: list[Path]) -> str | None:
    for root in input_roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        for part in relative.parts[:-1]:
            normalized = normalized_folder_name(part)
            if normalized in ICLOUD_ROOT_MARKERS:
                return normalized
    return None


def scan_media(
    input_roots: list[Path],
    show_progress: bool,
    read_embedded_metadata: bool,
    include_albums: bool,
    include_memories: bool,
) -> list[MediaItem]:
    album_index = build_album_index(input_roots, include_memories, show_progress) if include_albums else {}
    items: list[MediaItem] = []
    progress = CountProgress("Scanning media files", enabled=show_progress)
    for root in input_roots:
        for path in root.rglob("*"):
            if not path.is_file() or ignored_source_path(path) or path.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            collection = media_root_kind(path, input_roots)
            if collection not in MEDIA_COLLECTIONS:
                continue

            timestamp = latitude = longitude = altitude = None
            timestamp_source = "missing"
            if read_embedded_metadata:
                timestamp, latitude, longitude, altitude = embedded_metadata(path)
                if timestamp is not None:
                    timestamp_source = "embedded-media"

            album_keys = {path.name.casefold(), repair_zip_mojibake(path.name).casefold()}
            albums = set().union(*(album_index.get(key, set()) for key in album_keys))
            metadata = Metadata(timestamp, timestamp_source, latitude, longitude, altitude)
            items.append(
                MediaItem(
                    path=path,
                    metadata=metadata,
                    albums=tuple(sorted(albums, key=str.casefold)),
                    collection=collection or "photos",
                )
            )
            progress.update(len(items))
    items.sort(key=lambda item: (item.taken_at, item.path.name.lower(), str(item.path)))
    progress.finish()
    return items


def has_icloud_layout(path: Path) -> bool:
    try:
        child_names = {normalized_folder_name(child.name) for child in path.iterdir() if child.is_dir()}
    except OSError:
        return False
    return "photos" in child_names and bool(child_names & {"albums", "memories", "recently deleted"})


def icloud_photos_roots(path: Path) -> list[Path]:
    if has_icloud_layout(path):
        return [path]
    found: list[Path] = []
    pending: list[tuple[Path, int]] = [(path, 0)]
    while pending:
        current, depth = pending.pop(0)
        if depth >= 4:
            continue
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        if has_icloud_layout(current):
            found.append(current)
            continue
        for child in children:
            if child.is_dir() and child.name != "__MACOSX":
                pending.append((child, depth + 1))
    return found or [path]


def prepare_inputs(
    inputs: list[Path],
    output: Path,
    work_dir: Path | None,
    show_progress: bool,
) -> tuple[list[Path], tempfile.TemporaryDirectory[str] | None]:
    folders: list[Path] = []
    zip_inputs: list[Path] = []
    for path in inputs:
        if path.is_dir():
            folders.extend(icloud_photos_roots(path))
        elif path.is_file() and path.suffix.lower() == ".zip":
            zip_inputs.append(path)
        else:
            print(f"Unsupported input. Use a folder or .zip archive: {path}", file=sys.stderr)
            raise SystemExit(2)

    temp_context: tempfile.TemporaryDirectory[str] | None = None
    if zip_inputs:
        if work_dir is None:
            output.parent.mkdir(parents=True, exist_ok=True)
            temp_context = tempfile.TemporaryDirectory(prefix=".icloud-extract-", dir=output.parent)
            extract_root = Path(temp_context.name)
        else:
            extract_root = work_dir.expanduser().resolve()
            extract_root.mkdir(parents=True, exist_ok=True)
        for archive in zip_inputs:
            archive_dir = extract_root / archive.stem
            archive_dir.mkdir(parents=True, exist_ok=True)
            print(f"Extracting {archive} to {archive_dir}")
            with zipfile.ZipFile(archive) as zip_file:
                members = [member for member in zip_file.infolist() if not member.filename.startswith("__MACOSX/")]
                progress = Progress("Extracting", len(members), enabled=show_progress)
                for member in members:
                    zip_file.extract(member, archive_dir)
                    progress.advance()
                progress.finish()
            folders.extend(icloud_photos_roots(archive_dir))
    return folders, temp_context


def live_photo_pairs(items: list[MediaItem]) -> dict[Path, MediaItem]:
    by_stem: dict[tuple[str, str], list[MediaItem]] = {}
    for item in items:
        by_stem.setdefault((item.collection, item.path.stem.lower()), []).append(item)

    pairs: dict[Path, MediaItem] = {}
    for group in by_stem.values():
        photos = [item for item in group if item.is_photo]
        videos = [item for item in group if item.is_video and item.path.suffix.lower() in {".mov", ".mp4"}]
        for photo in photos:
            best: MediaItem | None = None
            best_delta: float | None = None
            for video in videos:
                delta = abs((photo.taken_at - video.taken_at).total_seconds())
                if best_delta is None or delta < best_delta:
                    best = video
                    best_delta = delta
            if best is not None and (best.timestamp_source == "filesystem-mtime" or best_delta is None or best_delta <= 12 * 3600):
                pairs[photo.path] = best
    return pairs


def timestamp_prefix(item: MediaItem) -> str:
    return item.taken_at.astimezone(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def detected_image_suffix(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(64)
    except OSError:
        return None
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return ".tif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    if header[4:8] == b"ftyp" and header[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}:
        return ".heic"
    return None


def output_filename(item: MediaItem) -> str:
    suffix = item.path.suffix
    stem = repair_zip_mojibake(item.path.stem)
    if item.is_photo:
        detected_suffix = detected_image_suffix(item.path)
        if detected_suffix is not None and detected_suffix != suffix.lower():
            suffix = detected_suffix
    return f"{timestamp_prefix(item)}__{stem}{suffix}"


def unique_destination(directory: Path, filename: str, used: set[Path]) -> Path:
    destination = directory / filename
    if destination not in used and not destination.exists():
        used.add(destination)
        return destination
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}-{counter}{suffix}"
        if candidate not in used and not candidate.exists():
            used.add(candidate)
            return candidate
        counter += 1


def planned_destinations(
    items: list[MediaItem],
    output: Path,
    include_albums: bool,
    pairs: dict[Path, MediaItem],
) -> list[tuple[MediaItem, Path, str]]:
    operations: list[tuple[MediaItem, Path, str]] = []
    used: set[Path] = set()
    paired_video_paths = {video.path for video in pairs.values()}

    for item in items:
        if item.path in paired_video_paths:
            continue

        base_name = output_filename(item)
        if item.timestamp_source == "filesystem-mtime":
            primary_dir = output / "Files Without Metadata"
            operations.append((item, unique_destination(primary_dir, base_name, used), "without-metadata"))
        else:
            year = item.taken_at.astimezone(timezone.utc).strftime("%Y")
            primary_dir = output / "Fotos" / year
            operations.append((item, unique_destination(primary_dir, base_name, used), "chronological"))

        if include_albums and item.timestamp_source != "filesystem-mtime":
            for album in item.albums:
                album_dir = output / "Albums" / album
                operations.append((item, unique_destination(album_dir, base_name, used), "album"))

        paired_video = pairs.get(item.path)
        if paired_video is None:
            continue

        live_stem = repair_zip_mojibake(item.path.stem)
        live_name = f"{timestamp_prefix(item)}__{live_stem}__live{paired_video.path.suffix}"
        paired_output = replace(paired_video, metadata=item.metadata, albums=item.albums)
        operations.append((paired_output, unique_destination(primary_dir, live_name, used), "live-photo"))
        if include_albums and item.timestamp_source != "filesystem-mtime":
            for album in item.albums:
                album_dir = output / "Albums" / album
                operations.append((paired_output, unique_destination(album_dir, live_name, used), "album-live-photo"))

    return operations


def copy_media(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def set_mtime(item: MediaItem, dst: Path, dry_run: bool) -> None:
    if item.metadata.timestamp is None or dry_run:
        return
    os.utime(dst, (item.metadata.timestamp, item.metadata.timestamp))


def exif_datetime(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y:%m:%d %H:%M:%S")


def decimal_to_dms(value: float) -> str:
    absolute = abs(value)
    degrees = int(absolute)
    minutes_float = (absolute - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    return f"{degrees} deg {minutes}' {seconds:.6f}\""


def embed_metadata(item: MediaItem, dst: Path, dry_run: bool) -> bool:
    if dry_run:
        return False
    args = ["exiftool", "-overwrite_original", "-P"]
    if item.metadata.timestamp is not None:
        dt = exif_datetime(item.metadata.timestamp)
        args.extend(
            [
                f"-DateTimeOriginal={dt}",
                f"-CreateDate={dt}",
                f"-ModifyDate={dt}",
                f"-MediaCreateDate={dt}",
                f"-TrackCreateDate={dt}",
            ]
        )
    if item.metadata.latitude is not None and item.metadata.longitude is not None:
        args.extend(
            [
                f"-GPSLatitude={decimal_to_dms(item.metadata.latitude)}",
                f"-GPSLatitudeRef={'N' if item.metadata.latitude >= 0 else 'S'}",
                f"-GPSLongitude={decimal_to_dms(item.metadata.longitude)}",
                f"-GPSLongitudeRef={'E' if item.metadata.longitude >= 0 else 'W'}",
            ]
        )
        if item.metadata.altitude is not None:
            args.extend([f"-GPSAltitude={abs(item.metadata.altitude)}", f"-GPSAltitudeRef={0 if item.metadata.altitude >= 0 else 1}"])
    if len(args) == 3:
        return False
    args.append(str(dst))
    try:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() if error.stderr else "unknown exiftool error"
        print(f"Warning: could not embed metadata in {dst}: {message}", file=sys.stderr)
        return False
    return True


def run() -> int:
    args = parse_args()
    requested_inputs = [path.expanduser().resolve() for path in args.input]
    output = args.output.expanduser().resolve()

    missing = [path for path in requested_inputs if not path.exists()]
    if missing:
        for path in missing:
            print(f"Input does not exist: {path}", file=sys.stderr)
        return 2

    input_roots, temp_context = prepare_inputs(requested_inputs, output, args.work_dir, not args.verbose)
    try:
        can_read_embedded = not args.no_embedded_metadata and exiftool_available()
        if not can_read_embedded and not args.no_embedded_metadata:
            print(
                "exiftool was not found; files will use filesystem mtimes and be placed in "
                "Files Without Metadata. Install exiftool for correct iCloud capture dates."
            )

        items = scan_media(
            input_roots=input_roots,
            show_progress=not args.verbose,
            read_embedded_metadata=can_read_embedded,
            include_albums=not args.no_albums,
            include_memories=args.include_memories,
        )
        pairs = live_photo_pairs(items)
        operations = planned_destinations(items, output, not args.no_albums, pairs)
        can_embed = not args.no_embed_metadata and exiftool_available()

        copied = 0
        embedded = 0
        progress = Progress("Organizing", len(operations), enabled=not args.verbose and not args.dry_run)
        for item, destination, reason in operations:
            if args.verbose:
                print(f"{reason}: {item.path} -> {destination}")
            copy_media(item.path, destination, args.dry_run)
            set_mtime(item, destination, args.dry_run)
            if can_embed and embed_metadata(item, destination, args.dry_run):
                embedded += 1
            copied += 1
            progress.advance()
        progress.finish()

        albums = len({album for item in items for album in item.albums})
        files_without_metadata = sum(1 for _item, _destination, reason in operations if reason == "without-metadata")
        corrected_extensions = sum(
            1 for item, destination, _reason in operations if item.path.suffix.lower() != destination.suffix.lower()
        )
        print(
            f"{'Planned' if args.dry_run else 'Organized'} {len(items)} media files "
            f"into {copied} output files across {albums} albums. "
            f"Live Photo pairs detected: {len(pairs)}. "
            f"Metadata embedded with exiftool: {embedded} files. "
            f"Files without usable timestamp metadata: {files_without_metadata}. "
            f"Corrected file extensions: {corrected_extensions}."
        )
        return 0
    finally:
        if temp_context is not None:
            temp_context.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except BrokenPipeError:
        raise SystemExit(0)
