"""NAS path rule: where a photo sits in the NAS Library.

``Photos/Google Photos/<year taken>/<original name>__<6 chars>.<ext>``, where the
6 chars are the first base32 characters (lowercase) of the SHA-256 of the url.
The rule is deterministic, so a photo gets the same path in every export.
"""

import base64
import hashlib
import re

from google_to_synology_photos.takeout import Photo


LIBRARY_ROOT = "Photos/Google Photos"
UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def short_hash(url: str) -> str:
    digest = hashlib.sha256(url.encode()).digest()
    return base64.b32encode(digest).decode().lower()[:6]


def nas_path(photo: Photo) -> str:
    stem, dot, ext = photo.name.rpartition(".")
    if not dot:
        stem, ext = photo.name, ""
    stem, ext = UNSAFE.sub("_", stem), UNSAFE.sub("_", ext)
    return (
        f"{LIBRARY_ROOT}/{photo.taken.year}/{stem}__{short_hash(photo.url)}{dot}{ext}"
    )
