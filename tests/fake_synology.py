"""In-memory fake Synology Photos, true to the behaviour measured on the DS923.

- Upload returns the item id at once; an upload to a taken path keeps the
  existing file (``duplicate="ignore"``) and returns its id.
- Overwrite keeps the item id and reads the Photo Description again from the
  new file; the fake's files carry none, so it becomes empty.
- Album names are not unique.
- ``writes`` counts the write calls, and ``writes_left`` cuts the connection when it
  reaches 0, so that a test can stop a run at any write.
- Writes on unknown items answer success and do nothing; writes on an unknown
  Album fail.

``tests/test_contract.py`` checks these claims against the DS923.
"""

from dataclasses import dataclass

from google_to_synology_photos.synology import NasAlbum, SynologyError


UNKNOWN_ALBUM = 609


@dataclass
class FakeItem:
    id: int
    path: str
    data: bytes
    description: str = ""


class FakeSynologyPhotos:
    def __init__(self) -> None:
        self._items: dict[int, FakeItem] = {}
        self._album_names: dict[int, str] = {}
        self._album_items: dict[int, list[int]] = {}
        self._next_id = 1
        # Set to False to make description writes silently not stick.
        self.descriptions_stick = True
        # Set to False to make Album renames silently not stick.
        self.album_names_stick = True
        # Set to False to make an overwrite give the item a new id, out of its
        # Albums. The DS923 keeps the id: the import does not rely on it.
        self.overwrite_keeps_id = True
        self.writes = 0
        self.writes_left: int | None = None

    def _write(self) -> None:
        """Count a write call, or cut the connection."""
        if self.writes_left == 0:
            raise ConnectionError("connection lost")
        if self.writes_left is not None:
            self.writes_left -= 1
        self.writes += 1

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    # SynologyPhotos interface

    def upload(self, path: str, data: bytes) -> int:
        self._write()
        existing = self.item_at(path)
        if existing is not None:
            return existing
        item = FakeItem(self._new_id(), path, data)
        self._items[item.id] = item
        return item.id

    def overwrite(self, path: str, data: bytes) -> int:
        item_id = self.upload(path, data)
        self._items[item_id].data = data
        self._items[item_id].description = ""
        if self.overwrite_keeps_id:
            return item_id
        item = self._items.pop(item_id)
        for held in self._album_items.values():
            if item_id in held:
                held.remove(item_id)
        item.id = self._new_id()
        self._items[item.id] = item
        return item.id

    def folder_items(self, folder: str) -> dict[str, int]:
        prefix = f"{folder}/"
        return {i.path: i.id for i in self._items.values() if i.path.startswith(prefix)}

    def item_at(self, path: str) -> int | None:
        return next((i.id for i in self._items.values() if i.path == path), None)

    def delete_item(self, item_id: int) -> None:
        self._write()
        self._items.pop(item_id, None)
        for held in self._album_items.values():
            if item_id in held:
                held.remove(item_id)

    def set_description(self, item_id: int, text: str) -> None:
        self._write()
        if item_id in self._items and self.descriptions_stick:
            self._items[item_id].description = text

    def description(self, item_id: int) -> str | None:
        item = self._items.get(item_id)
        return item.description if item else None

    def create_album(self, name: str) -> int:
        self._write()
        album_id = self._new_id()
        self._album_names[album_id] = name
        self._album_items[album_id] = []
        return album_id

    def rename_album(self, album_id: int, name: str) -> None:
        self._write()
        self._check_album(album_id, "rename_album")
        if self.album_names_stick:
            self._album_names[album_id] = name

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None:
        self._write()
        self._check_album(album_id, "add_to_album")
        held = self._album_items[album_id]
        held += [i for i in item_ids if i in self._items and i not in held]

    def albums(self) -> list[NasAlbum]:
        return [NasAlbum(i, name) for i, name in self._album_names.items()]

    def album_items(self, album_id: int) -> list[int]:
        return list(self._album_items.get(album_id, []))

    # What the Household can do on the NAS

    def delete_album(self, album_id: int) -> None:
        """Delete an Album: its photos stay."""
        del self._album_names[album_id]
        del self._album_items[album_id]

    def _check_album(self, album_id: int, call: str) -> None:
        if album_id not in self._album_names:
            raise SynologyError(UNKNOWN_ALBUM, call)

    # What the Household would see

    def paths(self) -> list[str]:
        """Paths of every item in the NAS Library."""
        return sorted(i.path for i in self._items.values())

    def item(self, path: str) -> FakeItem:
        """The item at path."""
        return next(i for i in self._items.values() if i.path == path)

    def album_contents(self) -> list[tuple[str, list[str]]]:
        """Each Album as (name, paths of its items), duplicate names kept."""
        return sorted(
            (name, sorted(self._items[i].path for i in self._album_items[album_id]))
            for album_id, name in self._album_names.items()
        )
