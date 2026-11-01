"""Album Download reader: the "Download all" ZIPs of shared Albums.

A ZIP holds one folder named after its Album, and every file of the Album, with
no sidecars. It is compared with the Takeout Export by size and CRC, read from
the ZIPs: most of its files are byte-identical to files of the export.
"""

import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from google_to_synology_photos.paths import content_hash
from google_to_synology_photos.takeout import Album, Export, FileKey, Photo


# In the folder that holds the export folders.
ALBUM_DOWNLOADS_FOLDER = "album-downloads"
# 299 of 345 JPGs of a measured Album hold no date, and all have one in their name.
# Google numbers the ZIPs of one Album Download: Été-1-001.zip, Été-1-002.zip.
ZIP_PART = re.compile(r"-\d+$")
DATE_IN_NAME = re.compile(r"(?<!\d)(?:19|20)\d{6}(?!\d)")


@dataclass(frozen=True)
class DownloadedFile:
    """A file of an Album Download, in its ZIP."""

    zip_path: Path
    member: str
    key: FileKey

    @property
    def name(self) -> str:
        """Return the file name, without its folder."""
        return self.member.rpartition("/")[2]

    def read(self) -> bytes:
        """Return the bytes of the file, read from its ZIP."""
        with zipfile.ZipFile(self.zip_path) as zf:
            return zf.read(self.member)


@dataclass
class AlbumDownload:
    """The files of one "Download all", from all its ZIPs.

    name is that of its ZIPs, without their number: two Albums can share a title.
    folder is the folder inside them, named after the Album.
    made is the date of the newest file: Google dates them when it makes the ZIP.
    """

    name: str
    folder: str
    made: datetime
    files: list[DownloadedFile] = field(default_factory=list)


def read_album_downloads(folder: Path) -> list[AlbumDownload]:
    """Read the ZIPs of folder into their Album Downloads, without unzipping."""
    downloads: dict[str, AlbumDownload] = {}
    for zip_path in sorted(folder.glob("*.zip")):
        name = ZIP_PART.sub("", zip_path.stem)
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                inside, slash, _ = info.filename.partition("/")
                made = datetime(*info.date_time, tzinfo=UTC)
                download = downloads.setdefault(
                    name, AlbumDownload(name, inside if slash else name, made)
                )
                download.made = max(download.made, made)
                download.files.append(
                    DownloadedFile(zip_path, info.filename, (info.file_size, info.CRC))
                )
    return list(downloads.values())


def paired_album(download: AlbumDownload, export: Export) -> Album | None:
    """Return the Album of download; None if it shares nothing with any Album.

    The Album sharing the most photos with it goes first, and its folder name
    settles a tie, or finds an Album with none of its photos in the export.
    """

    def closeness(album: Album) -> tuple[int, bool]:
        """Return how many files album shares, and whether its title matches."""
        urls = set(album.urls)
        shared = sum(
            bool(urls.intersection(export.urls_of_file.get(file.key, [])))
            for file in download.files
        )
        return shared, album.title == download.folder

    best = max(export.albums, key=closeness, default=None)
    return best if best is not None and any(closeness(best)) else None


def _date_in_name(name: str) -> datetime | None:
    """Return the date in a file name like IMG-20240829-WA0000.jpg, or None."""
    found = DATE_IN_NAME.search(name)
    try:
        return found and datetime.strptime(found[0], "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def photo_of_file(
    file: DownloadedFile,
    date_in_file: Callable[[str, bytes], datetime | None],
) -> Photo | None:
    """Return a file as a photo known by its content; None if it has no date.

    It has no sidecar, so the date comes from the file, or else from its name.
    The date of the ZIP will not do: the path would change with each download.
    """
    data = file.read()
    taken = date_in_file(file.name, data) or _date_in_name(file.name)
    if taken is None:
        return None
    return Photo(
        url=content_hash(data),
        name=file.name,
        taken=taken,
        position=None,
        caption="",
        zip_path=file.zip_path,
        member=file.member,
        size=file.key[0],
        crc=file.key[1],
        album_download=True,
    )
