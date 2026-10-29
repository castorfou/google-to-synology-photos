"""Interface of the Synology Photos client, as the NAS Account in its Personal Space.

Paths are NAS paths such as ``Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG``.
Writes answer success even when nothing changed, so callers read every write back.
Album names are not unique: Albums are only ever found by id.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NasAlbum:
    id: int
    name: str


class SynologyPhotos(Protocol):
    def upload(self, path: str, data: bytes) -> int:
        """Upload a file at path, keeping any file already there; return its id."""
        ...

    def item_at(self, path: str) -> int | None:
        """Return the id of the item at path, or None."""
        ...

    def set_description(self, item_id: int, text: str) -> None: ...

    def description(self, item_id: int) -> str | None:
        """Return the item's Photo Description, or None for an unknown item."""
        ...

    def create_album(self, name: str) -> int: ...

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None: ...

    def albums(self) -> list[NasAlbum]: ...

    def album_items(self, album_id: int) -> list[int]: ...
