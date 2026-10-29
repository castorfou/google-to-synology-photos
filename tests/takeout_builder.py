"""Builder for synthetic Takeout Exports, as Google Takeout writes them in French."""

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


# Google writes a non-breaking space in these folder names.
ROOT = "Takeout/Google\xa0Photos"
SIDECAR_SUFFIX = ".supplemental-metadata.json"
ALBUM_METADATA = "métadonnées.json"


@dataclass
class SyntheticPhoto:
    name: str
    url: str
    taken: datetime
    caption: str = ""
    data: bytes = b""

    def sidecar(self) -> dict:
        ts = str(int(self.taken.timestamp()))
        return {
            "title": self.name,
            "description": self.caption,
            "imageViews": "0",
            "creationTime": {"timestamp": ts, "formatted": ""},
            "photoTakenTime": {"timestamp": ts, "formatted": ""},
            "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
            "url": self.url,
            "googlePhotosOrigin": {"mobileUpload": {}},
        }


@dataclass
class SyntheticAlbum:
    title: str
    photos: list[SyntheticPhoto] = field(default_factory=list)


class TakeoutBuilder:
    """Collects Albums and photos, then writes them as one Takeout ZIP."""

    def __init__(self) -> None:
        self.albums: list[SyntheticAlbum] = []
        # Photos in no Album: they sit only in their year folder.
        self.loose = SyntheticAlbum("")

    def album(self, title: str) -> SyntheticAlbum:
        """Add an Album folder with its métadonnées.json."""
        album = SyntheticAlbum(title)
        self.albums.append(album)
        return album

    def photo(
        self,
        album: SyntheticAlbum,
        name: str,
        url: str,
        taken: datetime = datetime(2013, 4, 13, 15, 0, 44, tzinfo=UTC),
        caption: str = "",
    ) -> SyntheticPhoto:
        """Add a photo to an Album; it also sits in its year folder."""
        photo = SyntheticPhoto(name, url, taken, caption, data=_jpeg_bytes(url))
        album.photos.append(photo)
        return photo

    def loose_photo(self, name: str, url: str) -> SyntheticPhoto:
        """Add a photo that belongs to no Album."""
        return self.photo(self.loose, name, url)

    def write(self, export_dir: Path) -> Path:
        """Write the export as one ZIP in export_dir; return export_dir."""
        export_dir.mkdir(parents=True, exist_ok=True)
        zip_path = export_dir / "takeout-20240101T000000Z-1-001.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for album in self.albums:
                folder = f"{ROOT}/{album.title}"
                zf.writestr(
                    f"{folder}/{ALBUM_METADATA}",
                    json.dumps({"title": album.title}, ensure_ascii=False),
                )
                for photo in album.photos:
                    # An Album photo also sits in its year folder.
                    _write_photo(zf, folder, photo)
                    _write_photo(zf, _year_folder(photo), photo)
            for photo in self.loose.photos:
                _write_photo(zf, _year_folder(photo), photo)
        return export_dir


def _year_folder(photo: SyntheticPhoto) -> str:
    return f"{ROOT}/Photos de\xa0{photo.taken.year}"


def _write_photo(zf: zipfile.ZipFile, folder: str, photo: SyntheticPhoto) -> None:
    zf.writestr(f"{folder}/{photo.name}", photo.data)
    zf.writestr(
        f"{folder}/{photo.name}{SIDECAR_SUFFIX}",
        json.dumps(photo.sidecar(), ensure_ascii=False),
    )


def _jpeg_bytes(seed: str) -> bytes:
    """Tiny JPEG-looking bytes, unique per seed."""
    buf = io.BytesIO()
    buf.write(b"\xff\xd8\xff\xe0")
    buf.write(seed.encode())
    buf.write(b"\xff\xd9")
    return buf.getvalue()
