"""Media preparer: produces the exact file to send for a photo.

A file keeps what it holds. Only what it lacks is written, from the sidecar, and
no text is ever written. ExifTool rewrites the metadata and leaves the image as
it is. It keeps running between files: starting it for each one would take hours
on a full Takeout Export.
"""

import tempfile
from pathlib import Path
from types import TracebackType
from typing import Self

import exiftool
from exiftool.exceptions import ExifToolExecuteException

from google_to_synology_photos.takeout import Photo, Position


EXIF_DATE = "%Y:%m:%d %H:%M:%S"
# By content: Takeout has JPEGs named .png.
FORMATS = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}


class ExifToolMissingError(Exception):
    """ExifTool is not installed on the computer."""

    def __init__(self) -> None:
        super().__init__(
            "ExifTool was not found. g2s needs it to write missing dates and "
            "positions into photos. Install it from https://exiftool.org, then "
            "run g2s again. Nothing was uploaded."
        )


class MetadataError(Exception):
    """ExifTool could not read or write the metadata of a file."""


class MediaPreparer:
    """Prepares the files of a run; use it as a context manager."""

    def __enter__(self) -> Self:
        try:
            self._exiftool = exiftool.ExifToolHelper(check_tag_names=False)
        except FileNotFoundError as error:
            raise ExifToolMissingError from error
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

    def prepare(self, photo: Photo) -> bytes:
        """Return the bytes to send for photo.

        Raises MetadataError when what the file lacks cannot be written.
        """
        data = photo.read()
        suffix = next((s for sig, s in FORMATS.items() if data.startswith(sig)), None)
        if suffix is None:
            return data
        file = Path(self._folder.name, f"media{suffix}")
        file.write_bytes(data)
        try:
            writes = self._missing(photo, str(file))
            if not writes:
                return data
            # -m: a minor error, as in many old files, does not stop the write.
            self._exiftool.execute("-m", "-overwrite_original", *writes, str(file))
        except ExifToolExecuteException as error:
            raise MetadataError(str(error)) from error
        return file.read_bytes()

    def _missing(self, photo: Photo, file: str) -> list[str]:
        """Return the ExifTool arguments that write what file lacks."""
        tags = self._exiftool.get_tags(file, ["DateTimeOriginal", "GPSLatitude"])[0]
        held = {tag.rpartition(":")[2]: value for tag, value in tags.items()}
        writes = []
        # Some cameras fill the date with zeros or spaces when they have none.
        if not str(held.get("DateTimeOriginal", "")).strip(" :0"):
            writes.append(f"-EXIF:DateTimeOriginal={photo.taken.strftime(EXIF_DATE)}")
        if "GPSLatitude" not in held and photo.position is not None:
            writes += _position_writes(photo.position)
        return writes


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
