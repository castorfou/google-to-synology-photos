"""Media preparer: produces the exact file to send for a photo.

A file keeps what it holds. Only what it lacks is written, from the sidecar, and
no text is ever written. ExifTool rewrites the metadata and leaves the image as
it is. It keeps running between files: starting it for each one would take hours
on a full Takeout Export.

A video Synology Photos cannot play becomes an H.264 + AAC MP4, with ffmpeg. Other
videos are sent as they are.
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

import exiftool
from exiftool.exceptions import ExifToolExecuteException

from google_to_synology_photos.takeout import Photo, Position


EXIF_DATE = "%Y:%m:%d %H:%M:%S"
# By content: Takeout has JPEGs named .png.
SUFFIX_OF_SIGNATURE = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}
# Only the EXIF group counts: it is what gets written, and an XMP value, which
# may be empty, stays as it is next to it.
DATE_TAG = "EXIF:DateTimeOriginal"
VIDEO_DATE_TAG = "QuickTime:CreateDate"
POSITION_TAG = "EXIF:GPSLatitude"
# By name: a HEIC photo looks like an HEVC video to ffprobe.
VIDEO_SUFFIXES = (
    ".3g2",
    ".3gp",
    ".asf",
    ".avi",
    ".divx",
    ".m2t",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mmv",
    ".mod",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".tod",
    ".wmv",
)
# What ffprobe calls the formats and codecs Synology Photos cannot play: ASF is WMV.
UNPLAYABLE_FORMATS = {"asf", "avi", "mpeg", "mpegvideo"}
UNPLAYABLE_CODECS = {"hevc", "mpeg1video", "mpeg2video"}
MP4_DATE = "%Y-%m-%dT%H:%M:%SZ"


class ExifToolMissingError(Exception):
    """ExifTool is not installed on the computer."""

    def __init__(self) -> None:
        super().__init__(
            "ExifTool was not found. g2s needs it to write missing dates and "
            "positions into photos. Install it from https://exiftool.org, then "
            "run g2s again. Nothing was uploaded."
        )


class FfmpegMissingError(Exception):
    """ffmpeg or its ffprobe is not installed on the computer."""

    def __init__(self) -> None:
        super().__init__(
            "ffmpeg was not found. g2s needs it to convert the videos Synology "
            "Photos cannot play. Install it from https://ffmpeg.org (with its "
            "ffprobe), then run g2s again. Nothing was uploaded."
        )


class ConversionFailedError(Exception):
    """A video Synology Photos may not play could not be read or converted."""


@dataclass(frozen=True)
class PreparedFile:
    """The bytes to send; complete is False if what they lack could not be written.

    extension replaces the one of the photo's name, for a converted video.
    """

    data: bytes
    complete: bool = True
    extension: str | None = None


class MediaPreparer:
    """Prepares the files of a run; use it as a context manager."""

    def __enter__(self) -> Self:
        try:
            self._exiftool = exiftool.ExifToolHelper(check_tag_names=False)
        except FileNotFoundError as error:
            raise ExifToolMissingError from error
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            self._exiftool.terminate()
            raise FfmpegMissingError
        self._folder = tempfile.TemporaryDirectory(prefix="g2s-")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._exiftool.terminate()
        self._folder.cleanup()

    def prepare(self, photo: Photo) -> PreparedFile:
        """Return the file to send for photo.

        A file ExifTool cannot handle is sent as it is: better a photo at the
        wrong date than no photo.

        Raises ConversionFailedError on a video that cannot be read or converted.
        """
        data = photo.read()
        suffix = next(
            (s for sign, s in SUFFIX_OF_SIGNATURE.items() if data.startswith(sign)),
            None,
        )
        if suffix is None:
            if Path(photo.name).suffix.lower() in VIDEO_SUFFIXES:
                return self._prepare_video(photo, data)
            return PreparedFile(data)
        file = Path(self._folder.name, f"media{suffix}")
        file.write_bytes(data)
        try:
            writes = self._missing_writes(photo, str(file))
            if not writes:
                return PreparedFile(data)
            # -m: a minor error, as in many old files, does not stop the write.
            self._exiftool.execute("-m", "-overwrite_original", *writes, str(file))
        except ExifToolExecuteException:
            return PreparedFile(data, complete=False)
        return PreparedFile(file.read_bytes())

    def date_in_file(self, name: str, data: bytes) -> datetime | None:
        """Return the date a file holds, read as UTC, or None."""
        file = Path(self._folder.name, f"held{Path(name).suffix}")
        file.write_bytes(data)
        try:
            held = self._exiftool.get_tags(str(file), [DATE_TAG, VIDEO_DATE_TAG])[0]
        except ExifToolExecuteException:
            return None
        for tag in (DATE_TAG, VIDEO_DATE_TAG):
            try:
                taken = datetime.strptime(str(held.get(tag)), EXIF_DATE)
            except ValueError:
                # None, or a date made of zeros or spaces.
                continue
            return taken.replace(tzinfo=UTC)
        return None

    def _prepare_video(self, photo: Photo, data: bytes) -> PreparedFile:
        """Return the file to send for a video, converted if it cannot play."""
        # Its own folder: a video can be large, and goes as soon as it is sent.
        with tempfile.TemporaryDirectory(dir=self._folder.name) as folder:
            source = Path(folder, "source")
            source.write_bytes(data)
            converted = Path(folder, "converted.mp4")
            try:
                if not _is_unplayable(source):
                    return PreparedFile(data)
                _convert(source, converted, photo.taken)
            except subprocess.CalledProcessError as error:
                raise ConversionFailedError(photo.name) from error
            return PreparedFile(converted.read_bytes(), extension="mp4")

    def _missing_writes(self, photo: Photo, file: str) -> list[str]:
        """Return the ExifTool arguments that write what file lacks."""
        held = self._exiftool.get_tags(file, [DATE_TAG, POSITION_TAG])[0]
        writes = []
        # Some cameras fill the date with zeros or spaces when they have none.
        if not str(held.get(DATE_TAG, "")).strip(" :0"):
            writes.append(f"-{DATE_TAG}={photo.taken.strftime(EXIF_DATE)}")
        if POSITION_TAG not in held and photo.position is not None:
            writes += _position_writes(photo.position)
        return writes


def _is_unplayable(video: Path) -> bool:
    """Tell by its content whether Synology Photos cannot play video."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams"]
        + ["-select_streams", "v:0", "-of", "json", str(video)],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    found = json.loads(probe.stdout)
    formats = set(found["format"]["format_name"].split(","))
    # ffprobe gives no name to a codec it does not know.
    codecs = {stream.get("codec_name") for stream in found["streams"]}
    return bool(formats & UNPLAYABLE_FORMATS or codecs & UNPLAYABLE_CODECS)


def _convert(source: Path, target: Path, taken: datetime) -> None:
    """Convert source to an H.264 + AAC MP4 that carries the date taken."""
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(source)]
        # H.264 for every player: 8-bit 4:2:0, which needs even dimensions.
        + ["-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p"]
        + ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:a", "aac", "-sn", "-dn"]
        + ["-metadata", f"creation_time={taken.strftime(MP4_DATE)}"]
        + ["-movflags", "+faststart", str(target)],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )


def _position_writes(position: Position) -> list[str]:
    """Return the ExifTool arguments that write position: EXIF angles have no sign."""
    writes = [
        f"-EXIF:GPSLatitude={abs(position.latitude)}",
        f"-EXIF:GPSLatitudeRef={'S' if position.latitude < 0 else 'N'}",
        f"-EXIF:GPSLongitude={abs(position.longitude)}",
        f"-EXIF:GPSLongitudeRef={'W' if position.longitude < 0 else 'E'}",
    ]
    if position.altitude:
        writes += [
            f"-EXIF:GPSAltitude={abs(position.altitude)}",
            f"-EXIF:GPSAltitudeRef#={1 if position.altitude < 0 else 0}",
        ]
    return writes
