"""NAS path rule: where a photo sits in the NAS Library.

``Photos/Google Photos/<year taken>/<original name>__<6 chars>.<ext>``, where the
6 chars are the first base32 characters (lowercase) of the SHA-256 of the url. A
photo known only from an Album Download has no url of Google: the 6 chars come from its content.
A converted video has the extension of what it became.
The rule is deterministic, so a photo gets the same path in every export, and is
found on the NAS by its identity: its path without the extension, which a
conversion changes.
"""

import base64
import hashlib
import re

from google_to_synology_photos.takeout import Photo


LIBRARY_ROOT = "Photos/Google Photos"
UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
EXTENSION_AFTER_HASH = re.compile(r"(__[a-z2-7]{6})\.[^./]*$")


def content_hash(data: bytes) -> str:
    """Return the SHA-256 of data, in lowercase base32."""
    return base64.b32encode(hashlib.sha256(data).digest()).decode().lower()


def short_hash(photo: Photo) -> str:
    """Return the 6 path characters of a photo.

    The url of a photo from an Album Download already is its content hash.
    """
    return (photo.url if photo.album_download else content_hash(photo.url.encode()))[:6]


def year_folder(photo: Photo) -> str:
    """Return the NAS folder of photo."""
    return f"{LIBRARY_ROOT}/{photo.taken.year}"


def identity_of_path(path: str) -> str:
    """Return the identity of the photo at a NAS path."""
    return EXTENSION_AFTER_HASH.sub(r"\1", path)


def identity_of(photo: Photo) -> str:
    """Return the identity of photo."""
    return identity_of_path(nas_path(photo))


def name_of_identity(identity: str) -> str:
    """Return the name part of an identity, as name_stem gives it."""
    return identity.rpartition("/")[2].rpartition("__")[0]


def name_stem(name: str) -> str:
    """Return a file name as it sits in a NAS path, without its extension."""
    return UNSAFE.sub("_", name.rpartition(".")[0] or name)


def nas_path(photo: Photo, extension: str | None = None) -> str:
    """Return the NAS path of photo; extension replaces the one of its name."""
    stem, dot, ext = photo.name.rpartition(".")
    if not dot:
        stem, ext = photo.name, ""
    if extension is not None:
        dot, ext = ".", extension
    stem, ext = UNSAFE.sub("_", stem), UNSAFE.sub("_", ext)
    return f"{year_folder(photo)}/{stem}__{short_hash(photo)}{dot}{ext}"
