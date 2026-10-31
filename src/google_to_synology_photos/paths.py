"""NAS path rule: where a photo sits in the NAS Library.

``Photos/Google Photos/<year taken>/<original name>__<6 chars>.<ext>``, where the
6 chars are the first base32 characters (lowercase) of the SHA-256 of the url.
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


def short_hash(url: str) -> str:
    """Return the 6 path characters derived from a photo's url."""
    digest = hashlib.sha256(url.encode()).digest()
    return base64.b32encode(digest).decode().lower()[:6]


def year_folder(photo: Photo) -> str:
    """Return the NAS folder of photo."""
    return f"{LIBRARY_ROOT}/{photo.taken.year}"


def identity_of_path(path: str) -> str:
    """Return the identity of the photo at a NAS path."""
    return EXTENSION_AFTER_HASH.sub(r"\1", path)


def nas_path(photo: Photo, extension: str | None = None) -> str:
    """Return the NAS path of photo; extension replaces the one of its name."""
    stem, dot, ext = photo.name.rpartition(".")
    if not dot:
        stem, ext = photo.name, ""
    if extension is not None:
        dot, ext = ".", extension
    stem, ext = UNSAFE.sub("_", stem), UNSAFE.sub("_", ext)
    return f"{year_folder(photo)}/{stem}__{short_hash(photo.url)}{dot}{ext}"
