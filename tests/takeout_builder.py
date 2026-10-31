"""Builder for synthetic Takeout Exports, as Google Takeout writes them in French."""

import io
import json
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from PIL import ExifTags, Image, TiffImagePlugin


# Google writes a non-breaking space in these folder names.
ROOT = "Takeout/Google\xa0Photos"
SIDECAR_STEM = ".supplemental-metadata"
ALBUM_METADATA = "métadonnées.json"
ROOT_COMMENTS = "commentaires_albums_partagés.json"
XMP_PACKET = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
    'xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:DateTimeOriginal="{date}"/>'
    "</rdf:RDF></x:xmpmeta>"
)
# The date a camera writes in a file, unlike a WhatsApp image, which has none.
CAMERA_DATE = "2013:04:13 17:00:44"


@dataclass
class SyntheticPhoto:
    name: str
    url: str
    taken: datetime
    caption: str = ""
    data: bytes = b""
    # Bytes of the `-modifié` file next to the original, for an edited photo.
    edited: bytes | None = None
    # A Motion Photo also comes with its video parts, which have no sidecar.
    motion: bool = False
    # False when the export holds the sidecars of the photo, but never its file.
    has_file: bool = True
    # The sidecar's geoData: (latitude, longitude, altitude). Zeros mean no position.
    geo: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def sidecar(self, shared: list[dict] | None = None) -> dict:
        ts = str(int(self.taken.timestamp()))
        extra = {"sharedAlbumComments": shared} if shared else {}
        return {
            **extra,
            "title": self.name,
            "description": self.caption,
            "imageViews": "0",
            "creationTime": {"timestamp": ts, "formatted": ""},
            "photoTakenTime": {"timestamp": ts, "formatted": ""},
            "geoData": {
                "latitude": self.geo[0],
                "longitude": self.geo[1],
                "altitude": self.geo[2],
                "latitudeSpan": 0.0,
                "longitudeSpan": 0.0,
            },
            "url": self.url,
            "googlePhotosOrigin": {"mobileUpload": {}},
        }


@dataclass
class SyntheticAlbum:
    title: str
    photos: list[SyntheticPhoto] = field(default_factory=list)
    # True when the folder holds only sidecars: the media sit in year folders.
    sidecars_only: bool = False
    # The sharedAlbumComments of each photo's sidecar in this Album, by url.
    shared: dict[str, list[dict]] = field(default_factory=dict)
    description: str = ""
    # The sharedAlbumComments of the Album's métadonnées.json.
    album_shared: list[dict] = field(default_factory=list)
    # The folder name, when it differs from the title: two Albums can share one.
    folder: str = ""


class TakeoutBuilder:
    """Collects Albums and photos, then writes them as Takeout ZIPs."""

    def __init__(
        self, edited_suffix: str = "-modifié", root_comments: str = ROOT_COMMENTS
    ) -> None:
        self.albums: list[SyntheticAlbum] = []
        self.root_comments_name = root_comments
        self.root_comments: list[dict] = []
        # Photos in no Album: they sit only in their year folder.
        self.loose = SyntheticAlbum("")
        self.edited_suffix = edited_suffix

    def album(
        self,
        title: str,
        sidecars_only: bool = False,
        description: str = "",
        folder: str = "",
    ) -> SyntheticAlbum:
        """Add an Album folder with its métadonnées.json."""
        album = SyntheticAlbum(
            title, sidecars_only=sidecars_only, description=description, folder=folder
        )
        self.albums.append(album)
        return album

    def photo(
        self,
        album: SyntheticAlbum,
        name: str,
        url: str,
        taken: datetime = datetime(2013, 4, 13, 15, 0, 44, tzinfo=UTC),
        caption: str = "",
        edited: bool = False,
        motion: bool = False,
        has_file: bool = True,
        exif_date: str | None = CAMERA_DATE,
        exif_position: tuple[float, float] | None = None,
        geo: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> SyntheticPhoto:
        """Add a photo to an Album; it also sits in its year folder.

        exif_date and exif_position are what the file itself holds; geo is what
        the sidecar holds.
        """
        photo = SyntheticPhoto(
            name,
            url,
            taken,
            caption,
            data=jpeg_bytes(url, exif_date, exif_position),
            edited=jpeg_bytes(f"{url}-edited", exif_date) if edited else None,
            motion=motion,
            has_file=has_file,
            geo=geo,
        )
        album.photos.append(photo)
        return photo

    def add_to_album(self, album: SyntheticAlbum, photo: SyntheticPhoto) -> None:
        """Put a photo that already exists in one more Album."""
        album.photos.append(photo)

    def comment(
        self,
        album: SyntheticAlbum,
        photo: SyntheticPhoto,
        author: str,
        when: datetime,
        text: str,
    ) -> None:
        """Add a Comment on a photo, in the photo's sidecar of this Album."""
        album.shared.setdefault(photo.url, []).append(
            {"contentOwnerName": author, "creationTime": _time(when), "text": text}
        )

    def like(
        self, album: SyntheticAlbum, photo: SyntheticPhoto, author: str, when: datetime
    ) -> None:
        """Add a Like on a photo, in the photo's sidecar of this Album."""
        album.shared.setdefault(photo.url, []).append(
            {"contentOwnerName": author, "creationTime": _time(when), "liked": True}
        )

    def album_comment(
        self, album: SyntheticAlbum, author: str, when: datetime, text: str
    ) -> None:
        """Add a Comment on the Album itself, in its métadonnées.json."""
        album.album_shared.append(
            {"contentOwnerName": author, "creationTime": _time(when), "text": text}
        )

    def album_like(self, album: SyntheticAlbum, author: str, when: datetime) -> None:
        """Add a Like on the Album itself, in its métadonnées.json."""
        album.album_shared.append(
            {"contentOwnerName": author, "creationTime": _time(when), "liked": True}
        )

    def root_comment(self, share_id: str, when: datetime, text: str) -> None:
        """Add a Comment to the root file: it has a share link, but no author."""
        self.root_comments.append(
            {
                "text": text,
                "creationTime": _time(when),
                "contentUrl": f"https://photos.google.com/share/{share_id}",
            }
        )

    def root_like(self, share_id: str, when: datetime) -> None:
        """Add a Like to the root file: it has a share link, but no author."""
        self.root_comments.append(
            {
                "liked": True,
                "creationTime": _time(when),
                "contentUrl": f"https://photos.google.com/share/{share_id}",
            }
        )

    def loose_photo(self, name: str, url: str) -> SyntheticPhoto:
        """Add a photo that belongs to no Album."""
        return self.photo(self.loose, name, url)

    def write(self, export_dir: Path, zips: int = 1, year_folders: bool = True) -> Path:
        """Write the export as ZIPs in export_dir; return export_dir.

        With several ZIPs, members are dealt out in turn, so a media file and
        its sidecar sit in different ZIPs. An export of selected Albums has no
        year folders.
        """
        folders = _ExportFiles(self.edited_suffix)
        in_year_folder: set[str] = set()
        for album in self.albums:
            folder = f"{ROOT}/{album.folder or album.title}"
            folders.add_album(folder, album)
            for photo in album.photos:
                # An Album photo also sits in its year folder.
                folders.add_photo(
                    folder,
                    photo,
                    with_media=not album.sidecars_only,
                    shared=album.shared.get(photo.url),
                )
                if year_folders and photo.url not in in_year_folder:
                    in_year_folder.add(photo.url)
                    folders.add_photo(_year_folder(photo), photo)
        for photo in self.loose.photos:
            folders.add_photo(_year_folder(photo), photo)

        if self.root_comments:
            folders.files[f"{ROOT}/{self.root_comments_name}"] = json.dumps(
                {"sharedAlbumComments": self.root_comments}, ensure_ascii=False
            ).encode()

        export_dir.mkdir(parents=True, exist_ok=True)
        members = list(folders.files.items())
        for part in range(zips):
            zip_path = export_dir / f"takeout-20240101T000000Z-1-{part + 1:03}.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for member, data in members[part::zips]:
                    zf.writestr(member, data)
        return export_dir


class _ExportFiles:
    """The members of an export, with Google's `(1)` on repeated names."""

    def __init__(self, edited_suffix: str) -> None:
        self.files: dict[str, bytes] = {}
        self._edited_suffix = edited_suffix
        self._name_count: Counter[tuple[str, str]] = Counter()

    def add_album(self, folder: str, album: SyntheticAlbum) -> None:
        """Add the métadonnées.json of an Album folder."""
        metadata: dict = {"title": album.title}
        if album.description:
            metadata["description"] = album.description
        if album.album_shared:
            metadata["sharedAlbumComments"] = album.album_shared
        self.files[f"{folder}/{ALBUM_METADATA}"] = json.dumps(
            metadata, ensure_ascii=False
        ).encode()

    def add_photo(
        self,
        folder: str,
        photo: SyntheticPhoto,
        with_media: bool = True,
        shared: list[dict] | None = None,
    ) -> None:
        """Add the sidecar of a photo to folder and, with_media, its files."""
        repeat = self._name_count[folder, photo.name]
        self._name_count[folder, photo.name] += 1
        index = f"({repeat})" if repeat else ""
        self.files[f"{folder}/{photo.name}{SIDECAR_STEM}{index}.json"] = json.dumps(
            photo.sidecar(shared), ensure_ascii=False
        ).encode()
        if not (with_media and photo.has_file):
            return
        stem, dot, ext = photo.name.rpartition(".")
        self.files[f"{folder}/{stem}{index}{dot}{ext}"] = photo.data
        if photo.edited is not None:
            edited = f"{folder}/{stem}{self._edited_suffix}{index}{dot}{ext}"
            self.files[edited] = photo.edited
        if photo.motion:
            self.files[f"{folder}/{stem}"] = jpeg_bytes(f"{photo.url}-video")
            self.files[f"{folder}/{stem}~2"] = jpeg_bytes(f"{photo.url}-video-2")


def _time(when: datetime) -> dict:
    return {"timestamp": str(int(when.timestamp())), "formatted": ""}


def _year_folder(photo: SyntheticPhoto) -> str:
    return f"{ROOT}/Photos de\xa0{photo.taken.year}"


def jpeg_bytes(
    seed: str,
    date: str | None = CAMERA_DATE,
    position: tuple[float, float] | None = None,
    xmp_date: str | None = None,
) -> bytes:
    """A real 1x1 JPEG, unique per seed, holding only the given metadata."""
    exif = Image.Exif()
    if date is not None:
        exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = date
    if position is not None:
        latitude, longitude = position
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        gps[ExifTags.GPS.GPSLatitudeRef] = "N" if latitude >= 0 else "S"
        gps[ExifTags.GPS.GPSLatitude] = _degrees(latitude)
        gps[ExifTags.GPS.GPSLongitudeRef] = "E" if longitude >= 0 else "W"
        gps[ExifTags.GPS.GPSLongitude] = _degrees(longitude)
    buf = io.BytesIO()
    xmp = XMP_PACKET.format(date=xmp_date).encode() if xmp_date else b""
    Image.new("RGB", (1, 1), "white").save(
        buf, "JPEG", exif=exif, comment=seed.encode(), xmp=xmp
    )
    return buf.getvalue()


def _degrees(angle: float) -> tuple[TiffImagePlugin.IFDRational, ...]:
    """An angle as EXIF stores it: positive degrees, then zero minutes and seconds."""
    return (
        TiffImagePlugin.IFDRational(abs(angle)),
        TiffImagePlugin.IFDRational(0),
        TiffImagePlugin.IFDRational(0),
    )
