"""Media preparer: produces the exact file to send for a photo.

A file keeps what it holds. Only what it lacks is written, from the sidecar, and
no text is ever written. ExifTool rewrites the metadata and leaves the image as
it is. It keeps running between files: starting it for each one would take hours
on a full Takeout Export.
"""

import tempfile
from dataclasses import dataclass
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
POSITION_TAG = "EXIF:GPSLatitude"


class ExifToolMissingError(Exception):
    """ExifTool is not installed on the computer."""

    def __init__(self) -> None:
        super().__init__(
            "ExifTool was not found. g2s needs it to write missing dates and "
            "positions into photos. Install it from https://exiftool.org, then "
            "run g2s again. Nothing was uploaded."
        )


@dataclass(frozen=True)
class PreparedFile:
    """The bytes to send; complete is False if what they lack could not be written."""

    data: bytes
    complete: bool = True


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

    def prepare(self, photo: Photo) -> PreparedFile:
        """Return the file to send for photo.

        A file ExifTool cannot handle is sent as it is: better a photo at the
        wrong date than no photo.
        """
        data = photo.read()
        suffix = next(
            (s for sign, s in SUFFIX_OF_SIGNATURE.items() if data.startswith(sign)),
            None,
        )
        if suffix is None:
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
