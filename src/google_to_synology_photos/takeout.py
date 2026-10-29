"""Takeout reader: reads a Takeout Export from its ZIPs, without unzipping."""

import json
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


SIDECAR_SUFFIX = ".supplemental-metadata.json"
ALBUM_METADATA_NAMES = ("métadonnées.json", "metadata.json")


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
    """An Album of the export: its Google title and the urls of its photos."""

    title: str
    urls: list[str] = field(default_factory=list)


@dataclass
class Export:
    """The Albums of a Takeout Export, and the photos that belong to them."""

    photos: dict[str, Photo]
    albums: list[Album]


def read_export(export_dir: Path) -> Export:
    """Read every ZIP of export_dir into the Albums and their photos (by url).

    Photos that belong to no Album are left out.
    """
    photos: dict[str, Photo] = {}
    album_folders: dict[str, str] = {}
    urls_by_folder: dict[str, list[str]] = {}

    for zip_path in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            members = set(zf.namelist())
            for member in sorted(members):
                folder, _, filename = member.rpartition("/")
                if filename in ALBUM_METADATA_NAMES:
                    album_folders[folder] = json.loads(zf.read(member))["title"]
                elif filename.endswith(SIDECAR_SUFFIX):
                    media = member.removesuffix(SIDECAR_SUFFIX)
                    if media not in members:
                        continue
                    sidecar = json.loads(zf.read(member))
                    url = sidecar["url"]
                    urls_by_folder.setdefault(folder, []).append(url)
                    photos.setdefault(
                        url,
                        Photo(
                            url=url,
                            name=sidecar["title"],
                            taken=datetime.fromtimestamp(
                                int(sidecar["photoTakenTime"]["timestamp"]), UTC
                            ),
                            caption=sidecar.get("description", ""),
                            zip_path=zip_path,
                            member=media,
                        ),
                    )

    albums = [
        Album(title, urls_by_folder.get(folder, []))
        for folder, title in album_folders.items()
    ]
    in_albums = {url for album in albums for url in album.urls}
    return Export({u: p for u, p in photos.items() if u in in_albums}, albums)
