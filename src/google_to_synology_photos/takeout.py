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
HEART = "❤️"
ROOT_COMMENTS_NAMES = (
    "commentaires_albums_partagés.json",
    "shared_album_comments.json",
)


class SelectedAlbumsExportError(Exception):
    """The Takeout Export holds only some Albums, so it cannot be imported."""

    def __init__(self, titles: list[str]) -> None:
        super().__init__(
            "this looks like an export of selected Albums, not a full Takeout "
            "Export: it has no year folders, and photos of "
            f"{', '.join(repr(t) for t in titles)} have no file in it. Nothing "
            "was imported. Request a full Takeout Export of Google Photos."
        )


@dataclass(frozen=True)
class Position:
    """Where a photo was taken, from its sidecar. Altitude 0 means unknown."""

    latitude: float
    longitude: float
    altitude: float


@dataclass(frozen=True)
class Photo:
    """A photo or video of the export, identified by its sidecar url."""

    url: str
    name: str
    taken: datetime
    position: Position | None
    caption: str
    zip_path: Path
    member: str

    def read(self) -> bytes:
        """Return the bytes of the media file, read from its ZIP."""
        with zipfile.ZipFile(self.zip_path) as zf:
            return zf.read(self.member)


@dataclass(frozen=True)
class Comment:
    """A Comment, as text. The root Comments file gives no author: it is empty."""

    author: str
    when: datetime
    text: str


@dataclass(frozen=True)
class Reactions:
    """The Comments, oldest first, and the names of the Likes on one thing."""

    comments: list[Comment]
    likes: list[str]

    def __bool__(self) -> bool:
        return bool(self.comments or self.likes)


@dataclass
class Album:
    """An Album of the export: its Google title and the urls of its photos.

    no_file holds the names of its photos whose file is not in the export.
    photo_reactions holds the Comments and Likes on its photos, by url, only for
    the photos that have some: a photo in two Albums has different ones in each.
    reactions holds the Comments and Likes on the Album itself.
    orphans holds its Comments that have no photo to sit on, oldest first.
    """

    title: str
    urls: list[str] = field(default_factory=list)
    no_file: list[str] = field(default_factory=list)
    photo_reactions: dict[str, Reactions] = field(default_factory=dict)
    description: str = ""
    reactions: Reactions = field(default_factory=lambda: Reactions([], []))
    orphans: list[Comment] = field(default_factory=list)


@dataclass
class Export:
    """The Albums of a Takeout Export, and the photos that belong to them.

    orphans holds the root Comments that match no photo and no known Album.
    """

    photos: dict[str, Photo]
    albums: list[Album]
    orphans: list[Comment] = field(default_factory=list)


def _media_name(name: str, index: str, edited_suffix: str = "") -> str:
    """Return the file name of a media file, from the name in its sidecar."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    return f"{stem}{edited_suffix}{index}{dot}{ext}"


def _position(sidecar: dict) -> Position | None:
    """Return the geoData of a sidecar; Google writes zeros when it has none."""
    geo = sidecar.get("geoData", {})
    latitude, longitude = geo.get("latitude", 0.0), geo.get("longitude", 0.0)
    if not (latitude or longitude):
        return None
    return Position(latitude, longitude, geo.get("altitude", 0.0))


# What the same Comment shares in the root file and elsewhere.
EntryKey = tuple[str, bool, str]


def _timestamp(entry: dict) -> int:
    return int(entry["creationTime"]["timestamp"])


def _reactions(entries: list[dict]) -> Reactions:
    """Return the sharedAlbumComments of a JSON file, oldest first."""
    entries = sorted(entries, key=_timestamp)
    return Reactions(
        [_comment(e) for e in entries if "text" in e],
        [e["contentOwnerName"] for e in entries if e.get("liked")],
    )


def _comment(entry: dict) -> Comment:
    """Return an entry as a Comment.

    A Like read as a Comment comes from the root file: it has no name to show.
    """
    return Comment(
        entry.get("contentOwnerName", ""),
        datetime.fromtimestamp(_timestamp(entry), UTC),
        entry.get("text", HEART),
    )


def _entry_key(entry: dict) -> EntryKey:
    timestamp = entry["creationTime"]["timestamp"]
    return entry.get("text", ""), entry.get("liked", False), timestamp


def _place_root_comments(
    root_comments: list[dict], album_of_entry: dict[EntryKey, Album]
) -> list[Comment]:
    """Add the root Comments that match no photo to the orphans of their Album.

    A root Comment points to a share link, not to a photo or an Album. Most of
    them repeat a Comment of a sidecar or an Album: that ties the link to the
    Album. Return the orphans whose link stays unknown.
    """
    album_of_link: dict[str, Album] = {}
    for entry in root_comments:
        if album := album_of_entry.get(_entry_key(entry)):
            album_of_link.setdefault(entry["contentUrl"], album)

    unknown: list[Comment] = []
    for entry in sorted(root_comments, key=_timestamp):
        if _entry_key(entry) not in album_of_entry:
            album = album_of_link.get(entry["contentUrl"])
            (unknown if album is None else album.orphans).append(_comment(entry))
    return unknown


def read_export(export_dir: Path) -> Export:
    """Read every ZIP of export_dir into the Albums and their photos (by url).

    A media file and its sidecar may sit in different ZIPs, and an Album folder
    may hold only sidecars, so all the ZIPs are listed before anything is paired.
    Photos that belong to no Album are left out.

    Raises SelectedAlbumsExportError on an export of selected Albums.
    """
    zip_of: dict[str, Path] = {}
    album_folders: dict[str, dict] = {}
    sidecars: list[tuple[str, re.Match[str], dict]] = []
    root_comments: list[dict] = []

    for zip_path in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            for member in sorted(zf.namelist()):
                folder, _, filename = member.rpartition("/")
                if filename in ALBUM_METADATA_NAMES:
                    album_folders[folder] = json.loads(zf.read(member))
                elif match := SIDECAR.fullmatch(filename):
                    sidecars.append((folder, match, json.loads(zf.read(member))))
                elif filename in ROOT_COMMENTS_NAMES:
                    root_comments = json.loads(zf.read(member))["sharedAlbumComments"]
                else:
                    zip_of[member] = zip_path

    sidecar_of: dict[str, dict] = {}
    original_of: dict[str, str] = {}
    edited_of: dict[str, str] = {}
    urls_by_folder: dict[str, list[str]] = {}
    for folder, match, sidecar in sidecars:
        url = sidecar["url"]
        sidecar_of.setdefault(url, sidecar)
        urls_by_folder.setdefault(folder, []).append(url)
        name, index = match["name"], match["index"] or ""
        original = f"{folder}/{_media_name(name, index)}"
        if original in zip_of:
            original_of.setdefault(url, original)
        for suffix in EDITED_SUFFIXES:
            edited = f"{folder}/{_media_name(name, index, suffix)}"
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
                position=_position(sidecar),
                caption=sidecar.get("description", ""),
                zip_path=zip_of[media],
                member=media,
            )

    photo_reactions: dict[str, dict[str, Reactions]] = {}
    for folder, _, sidecar in sidecars:
        if reactions := _reactions(sidecar.get("sharedAlbumComments", [])):
            photo_reactions.setdefault(folder, {})[sidecar["url"]] = reactions

    # Sorted, so that the ZIP a file landed in changes nothing in the text.
    albums: dict[str, Album] = {}
    for folder, metadata in sorted(album_folders.items()):
        urls = urls_by_folder.get(folder, [])
        no_file = [sidecar_of[url]["title"] for url in urls if url not in photos]
        reactions_by_url = photo_reactions.get(folder, {})
        kept = [u for u in urls if u in photos]
        album_reactions = _reactions(metadata.get("sharedAlbumComments", []))
        # Comments with nothing to sit on: a photo with no file, an empty Album.
        orphans = [
            comment
            for url, reactions in reactions_by_url.items()
            if url not in photos
            for comment in reactions.comments
        ]
        if not kept:
            orphans += album_reactions.comments
        albums[folder] = Album(
            title=metadata["title"],
            urls=kept,
            no_file=no_file,
            photo_reactions={u: r for u, r in reactions_by_url.items() if u in photos},
            description=metadata.get("description", ""),
            reactions=album_reactions,
            orphans=orphans,
        )

    # A full export also misses a few files, but it always has year folders:
    # any folder of sidecars that is not an Album.
    if album_folders.keys() >= urls_by_folder.keys():
        without_files = [a.title for a in albums.values() if a.no_file]
        if without_files:
            raise SelectedAlbumsExportError(without_files)

    album_of_entry: dict[EntryKey, Album] = {}
    for folder, json_file in [
        *((folder, sidecar) for folder, _, sidecar in sidecars),
        *album_folders.items(),
    ]:
        if folder in albums:
            for entry in json_file.get("sharedAlbumComments", []):
                album_of_entry[_entry_key(entry)] = albums[folder]
    unknown_album = _place_root_comments(root_comments, album_of_entry)
    for album in albums.values():
        album.orphans.sort(key=lambda comment: comment.when)

    in_albums = {url for album in albums.values() for url in album.urls}
    return Export(
        {u: p for u, p in photos.items() if u in in_albums},
        list(albums.values()),
        unknown_album,
    )
