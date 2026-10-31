"""Takeout reader: reads a Takeout Export from its ZIPs, without unzipping."""

import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


# Google numbers a repeated name in a folder: the sidecar of IMG(1).JPG is
# IMG.JPG.supplemental-metadata(1).json.
SIDECAR = re.compile(r"(?P<name>.+)\.supplemental-metadata(?P<index>\(\d+\))?\.json")
# An edited photo has no sidecar of its own: it shares the original's.
EDITED_SUFFIXES = ("-modifié", "-edited")
ALBUM_METADATA_NAMES = ("métadonnées.json", "metadata.json")


class SelectedAlbumsExportError(Exception):
    """The Takeout Export holds only some Albums, so it cannot be imported."""

    def __init__(self, titles: list[str]) -> None:
        super().__init__(
            "this looks like an export of selected Albums, not a full Takeout "
            f"Export: no photo file of {', '.join(repr(t) for t in titles)} is in "
            "it. Nothing was imported. Request a full Takeout Export of Google "
            "Photos, and check that every ZIP is in the folder."
        )


@dataclass(frozen=True)
class Photo:
    """A photo or video of the export, identified by its sidecar url."""

    url: str
    name: str
    taken: datetime
    caption: str
    zip_path: Path
    member: str

    def read(self) -> bytes:
        """Return the bytes of the media file, read from its ZIP."""
        with zipfile.ZipFile(self.zip_path) as zf:
            return zf.read(self.member)


@dataclass
class Album:
    """An Album of the export: its Google title and the urls of its photos.

    no_file holds the names of its photos whose file is not in the export.
    """

    title: str
    urls: list[str] = field(default_factory=list)
    no_file: list[str] = field(default_factory=list)


@dataclass
class Export:
    """The Albums of a Takeout Export, and the photos that belong to them."""

    photos: dict[str, Photo]
    albums: list[Album]


def _media_name(name: str, index: str, edited_suffix: str = "") -> str:
    """Return the file name of a media file, from the name in its sidecar."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    return f"{stem}{edited_suffix}{index}{dot}{ext}"


def read_export(export_dir: Path) -> Export:
    """Read every ZIP of export_dir into the Albums and their photos (by url).

    A media file and its sidecar may sit in different ZIPs, and an Album folder
    may hold only sidecars, so all the ZIPs are listed before anything is paired.
    Photos that belong to no Album are left out.

    Raises SelectedAlbumsExportError when an Album has none of its files.
    """
    zip_of: dict[str, Path] = {}
    album_folders: dict[str, str] = {}
    sidecars: list[tuple[str, re.Match[str], dict]] = []

    for zip_path in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            for member in sorted(zf.namelist()):
                folder, _, filename = member.rpartition("/")
                if filename in ALBUM_METADATA_NAMES:
                    album_folders[folder] = json.loads(zf.read(member))["title"]
                elif name := SIDECAR.fullmatch(filename):
                    sidecars.append((folder, name, json.loads(zf.read(member))))
                else:
                    zip_of[member] = zip_path

    sidecar_of: dict[str, dict] = {}
    original_of: dict[str, str] = {}
    edited_of: dict[str, str] = {}
    urls_by_folder: dict[str, list[str]] = {}
    for folder, name, sidecar in sidecars:
        url = sidecar["url"]
        sidecar_of.setdefault(url, sidecar)
        urls_by_folder.setdefault(folder, []).append(url)
        index = name["index"] or ""
        original = f"{folder}/{_media_name(name['name'], index)}"
        if original in zip_of:
            original_of.setdefault(url, original)
        for suffix in EDITED_SUFFIXES:
            edited = f"{folder}/{_media_name(name['name'], index, suffix)}"
            if edited in zip_of:
                edited_of.setdefault(url, edited)

    photos: dict[str, Photo] = {}
    for url, sidecar in sidecar_of.items():
        media = edited_of.get(url) or original_of.get(url)
        if media is not None:
            photos[url] = Photo(
                url=url,
                name=sidecar["title"],
                taken=datetime.fromtimestamp(
                    int(sidecar["photoTakenTime"]["timestamp"]), UTC
                ),
                caption=sidecar.get("description", ""),
                zip_path=zip_of[media],
                member=media,
            )

    albums = []
    for folder, title in album_folders.items():
        urls = urls_by_folder.get(folder, [])
        no_file = [sidecar_of[url]["title"] for url in urls if url not in photos]
        albums.append(Album(title, [u for u in urls if u in photos], no_file))

    # A full export can miss a few files, but never all those of an Album.
    without_files = [a.title for a in albums if a.no_file and not a.urls]
    if without_files:
        raise SelectedAlbumsExportError(without_files)

    in_albums = {url for album in albums for url in album.urls}
    return Export({u: p for u, p in photos.items() if u in in_albums}, albums)
