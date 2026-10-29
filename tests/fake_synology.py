"""In-memory fake Synology Photos, true to the behaviour measured on the DS923.

- Upload returns the item id at once; an upload to a taken path keeps the
  existing file (``duplicate="ignore"``) and returns its id.
- Album names are not unique.
- Writes on unknown ids answer success and do nothing.
"""

from dataclasses import dataclass

from google_to_synology_photos.synology import NasAlbum


@dataclass
class FakeItem:
    id: int
    path: str
    data: bytes
    description: str = ""


class FakeSynologyPhotos:
    def __init__(self) -> None:
        self._items: dict[int, FakeItem] = {}
        self._albums: dict[int, NasAlbum] = {}
        self._album_items: dict[int, list[int]] = {}
        self._next_id = 1
        # Set to False to make description writes silently not stick.
        self.descriptions_stick = True

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    # SynologyPhotos interface

    def upload(self, path: str, data: bytes) -> int:
        existing = self.item_at(path)
        if existing is not None:
            return existing
        item = FakeItem(self._new_id(), path, data)
        self._items[item.id] = item
        return item.id

    def item_at(self, path: str) -> int | None:
        return next((i.id for i in self._items.values() if i.path == path), None)

    def set_description(self, item_id: int, text: str) -> None:
        if item_id in self._items and self.descriptions_stick:
            self._items[item_id].description = text

    def description(self, item_id: int) -> str | None:
        item = self._items.get(item_id)
        return item.description if item else None

    def create_album(self, name: str) -> int:
        album = NasAlbum(self._new_id(), name)
        self._albums[album.id] = album
        self._album_items[album.id] = []
        return album.id

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None:
        if album_id not in self._albums:
            return
        held = self._album_items[album_id]
        held += [i for i in item_ids if i in self._items and i not in held]

    def albums(self) -> list[NasAlbum]:
        return list(self._albums.values())

    def album_items(self, album_id: int) -> list[int]:
        return list(self._album_items.get(album_id, []))

    # What the Household would see

    def paths(self) -> list[str]:
        return sorted(i.path for i in self._items.values())

    def item(self, path: str) -> FakeItem:
        return next(i for i in self._items.values() if i.path == path)

    def album_contents(self) -> dict[str, list[str]]:
        """Album name -> paths of its items (names assumed unique in the test)."""
        return {
            a.name: sorted(self._items[i].path for i in self._album_items[a.id])
            for a in self._albums.values()
        }
