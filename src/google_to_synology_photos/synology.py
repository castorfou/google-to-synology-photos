"""Interface of the Synology Photos client, writing as the NAS Account.

Paths are NAS paths such as ``Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG``.
Writes on unknown items answer success and do nothing, so callers read every
write back. Writes on an unknown Album fail.
Album names are not unique: Albums are only ever found by id.
"""

from dataclasses import dataclass
from typing import Protocol


class SynologyError(Exception):
    """A Synology Web API call failed."""

    def __init__(self, code: int, call: str) -> None:
        super().__init__(f"{call} failed with Synology error {code}")
        self.code = code


@dataclass(frozen=True)
class NasAlbum:
    """An Album of Synology Photos."""

    id: int
    name: str


class SynologyPhotos(Protocol):
    def upload(self, path: str, data: bytes) -> int:
        """Upload a file at path, keeping any file already there; return its id."""
        ...

    def overwrite(self, path: str, data: bytes) -> int:
        """Replace the file at path, or upload it; return its id.

        The item keeps its id. Its Photo Description is read again from the new
        file.
        """
        ...

    def folder_items(self, folder: str) -> dict[str, int]:
        """Return the id of each item of a NAS folder and its subfolders, by path.

        A folder that does not exist has no items.
        """
        ...

    def item_at(self, path: str) -> int | None:
        """Return the id of the item at path, or None."""
        ...

    def delete_item(self, item_id: int) -> None:
        """Delete an item and its file."""
        ...

    def set_description(self, item_id: int, text: str) -> None:
        """Set the item's Photo Description."""
        ...

    def description(self, item_id: int) -> str | None:
        """Return the item's Photo Description, or None for an unknown item."""
        ...

    def create_album(self, name: str) -> int:
        """Create an empty Album named name; return its id."""
        ...

    def rename_album(self, album_id: int, name: str) -> None:
        """Rename an Album."""
        ...

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None:
        """Add items to an Album; unknown items are skipped."""
        ...

    def albums(self) -> list[NasAlbum]:
        """Return every normal Album: only those can receive items."""
        ...

    def album_items(self, album_id: int) -> list[int]:
        """Return the ids of the items in an Album."""
        ...
