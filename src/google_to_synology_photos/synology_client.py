"""Synology Photos client over the undocumented ``SYNO.Foto.*`` Web API.

It works in the Personal Space of the logged-in NAS Account. A NAS path
``Photos/<folder>/<name>`` is the Synology Photos folder ``/<folder>``, and the
File Station path ``/home/Photos/<folder>/<name>``.
"""

import json
import time
from typing import Any

from google_to_synology_photos.dsm import DsmApi
from google_to_synology_photos.synology import NasAlbum, SynologyError


PHOTOS_ROOT = "Photos"
FOLDER_EXISTS = 641
FOLDER_MISSING = 642
PAGE_SIZE = 1000
ALBUM_BATCH = 100
METADATA_JOBS = ("basic", "metadata", "metadata_updating")
RETRY_DELAYS = (0.0, 1.0, 2.0, 4.0, 8.0)


class SynologyPhotosClient:
    """The SynologyPhotos interface, on a logged-in DsmApi."""

    def __init__(self, api: DsmApi, index_timeout: float = 600.0) -> None:
        self._api = api
        self._folder_ids: dict[str, int] = {}
        # Folder -> {file name: item id}, as last listed or changed by this client.
        self._listings: dict[str, dict[str, int]] = {}
        self._index_timeout = index_timeout

    # Items

    def upload(self, path: str, data: bytes) -> int:
        """Upload a file at path, keeping any file already there; return its id."""
        # duplicate="ignore" skips only identical files: a different file under
        # a taken name is stored as a renamed copy. So a taken path is checked
        # here first, on the folder listing this client keeps.
        folder, name = _split(path)
        listing = self._listings.get(folder)
        if listing is None:
            listing = self._list_folder(folder)
        if name in listing:
            return listing[name]
        result = self._api.upload(
            "SYNO.Foto.Upload.Item",
            "upload_to_folder",
            1,
            {
                "target_folder_id": json.dumps(self._make_folder(folder)),
                "name": json.dumps(name, ensure_ascii=False),
                "duplicate": json.dumps("ignore"),
                "mtime": str(int(time.time())),
            },
            name,
            data,
        )
        item_id = int(result["id"])
        if result.get("action") == "rename":
            # The path was taken after the listing: drop the copy, keep the item.
            self._api.call("SYNO.Foto.Browse.Item", "delete", 1, id=[item_id])
            existing = self._list_folder(folder).get(name)
            if existing is None:
                raise SynologyError(0, f"upload of {path}")
            return existing
        self._listings.setdefault(folder, {})[name] = item_id
        return item_id

    def overwrite(self, path: str, data: bytes) -> int:
        """Replace the file at path, or upload it; return its id."""
        # Upload.Item has no overwrite; File Station has, and keeps the item id.
        item_id = self.item_at(path)
        if item_id is None:
            return self.upload(path, data)
        folder, name = _split(path)
        self._api.upload(
            "SYNO.FileStation.Upload",
            "upload",
            2,
            {
                "path": f"/home/{PHOTOS_ROOT}{folder}",
                "create_parents": "true",
                "overwrite": "true",
            },
            name,
            data,
        )
        self._wait_for_reindex(item_id, len(data))
        return item_id

    def folder_items(self, folder: str) -> dict[str, int]:
        """Return the id of each item of a NAS folder, by path."""
        listing = self._list_folder("/" + folder.removeprefix(f"{PHOTOS_ROOT}/"))
        return {f"{folder}/{name}": item_id for name, item_id in listing.items()}

    def item_at(self, path: str) -> int | None:
        """Return the id of the item at path, or None."""
        folder, name = _split(path)
        return self._list_folder(folder).get(name)

    def delete_item(self, item_id: int) -> None:
        """Delete an item and its file."""
        self._api.call("SYNO.Foto.Browse.Item", "delete", 1, id=[item_id])
        for listing in self._listings.values():
            for name in [n for n, i in listing.items() if i == item_id]:
                del listing[name]

    def set_description(self, item_id: int, text: str) -> None:
        """Set the item's Photo Description, and write it again until it sticks.

        A description that still has not stuck after the last try is left to
        the caller's read-back.
        """
        # A write made just after the upload is sometimes dropped while still
        # answering success; written again a little later, it sticks.
        for delay in RETRY_DELAYS:
            time.sleep(delay)
            self._api.call(
                "SYNO.Foto.Browse.Item", "set", 2, id=[item_id], description=text
            )
            if self.description(item_id) in (text, None):
                return

    def description(self, item_id: int) -> str | None:
        """Return the item's Photo Description, or None for an unknown item."""
        item = self._item(item_id, ["description"])
        return None if item is None else str(item["additional"]["description"])

    # Albums

    def create_album(self, name: str) -> int:
        """Create an empty Album named name; return its id."""
        data = self._api.call(
            "SYNO.Foto.Browse.NormalAlbum", "create", 1, name=name, item=[]
        )
        return int(data["album"]["id"])

    def rename_album(self, album_id: int, name: str) -> None:
        """Rename an Album."""
        self._api.call("SYNO.Foto.Browse.Album", "set_name", 1, id=album_id, name=name)

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None:
        """Add items to an Album, in batches; unknown items are skipped."""
        for start in range(0, len(item_ids), ALBUM_BATCH):
            batch = item_ids[start : start + ALBUM_BATCH]
            self._api.call(
                "SYNO.Foto.Browse.NormalAlbum", "add_item", 1, id=album_id, item=batch
            )

    def albums(self) -> list[NasAlbum]:
        """Return every normal Album: only those can receive items."""
        return [
            NasAlbum(int(a["id"]), a["name"])
            for a in self._pages("SYNO.Foto.Browse.Album", 2)
            if a["type"] == "normal"
        ]

    def album_items(self, album_id: int) -> list[int]:
        """Return the ids of the items in an Album."""
        items = self._pages("SYNO.Foto.Browse.Item", 2, album_id=album_id)
        return [int(i["id"]) for i in items]

    # Helpers

    def _list_folder(self, folder: str) -> dict[str, int]:
        """List a folder as {file name: item id}, and keep that listing."""
        folder_id = self._find_folder(folder)
        items = (
            []
            if folder_id is None
            else self._pages("SYNO.Foto.Browse.Item", 2, folder_id=folder_id)
        )
        self._listings[folder] = {i["filename"]: int(i["id"]) for i in items}
        return self._listings[folder]

    def _find_folder(self, folder: str) -> int | None:
        """Return the id of a Synology Photos folder, or None if it is missing."""
        if folder not in self._folder_ids:
            try:
                data = self._api.call("SYNO.Foto.Browse.Folder", "get", 2, name=folder)
            except SynologyError as error:
                if error.code == FOLDER_MISSING:
                    return None
                raise
            self._folder_ids[folder] = int(data["folder"]["id"])
        return self._folder_ids[folder]

    def _make_folder(self, folder: str) -> int:
        """Return the id of a Synology Photos folder, creating it and its parents."""
        folder_id = self._find_folder(folder)
        if folder_id is not None:
            return folder_id
        parent, _, name = folder.rpartition("/")
        parent_id = self._make_folder(parent or "/")
        try:
            self._api.call(
                "SYNO.Foto.Browse.Folder", "create", 1, target_id=parent_id, name=name
            )
        except SynologyError as error:
            if error.code != FOLDER_EXISTS:
                raise
        folder_id = self._find_folder(folder)
        if folder_id is None:
            raise SynologyError(FOLDER_MISSING, f"creation of folder {folder}")
        return folder_id

    def _item(self, item_id: int, additional: list[str]) -> dict[str, Any] | None:
        """Return an item with the additional fields asked, or None if unknown."""
        data = self._api.call(
            "SYNO.Foto.Browse.Item", "get", 2, id=[item_id], additional=additional
        )
        items: list[dict[str, Any]] = data.get("list", [])
        return items[0] if items else None

    def _wait_for_reindex(self, item_id: int, size: int) -> None:
        """Wait until Synology Photos has read the new file of an item again.

        The new size shows first; the metadata, such as the Photo Description,
        follow once the index has no metadata work left.
        """
        deadline = time.monotonic() + self._index_timeout
        while time.monotonic() < deadline:
            item = self._item(item_id, [])
            queue = self._api.call("SYNO.Foto.Index", "get", 1)
            if (
                item is not None
                and item.get("filesize") == size
                and not any(queue.get(job) for job in METADATA_JOBS)
            ):
                return
            time.sleep(1)
        raise TimeoutError(f"item {item_id} was not indexed again in time")

    def _pages(self, api: str, version: int, **params: Any) -> list[dict[str, Any]]:
        """Call api.list page after page; return every entry."""
        found: list[dict[str, Any]] = []
        while True:
            data = self._api.call(
                api, "list", version, offset=len(found), limit=PAGE_SIZE, **params
            )
            page: list[dict[str, Any]] = data.get("list", [])
            found += page
            if len(page) < PAGE_SIZE:
                return found


def _split(path: str) -> tuple[str, str]:
    """Split a NAS path into its Synology Photos folder and file name."""
    root, _, rest = path.partition("/")
    if root != PHOTOS_ROOT or not rest:
        raise ValueError(f"not a path of the Personal Space: {path}")
    folder, _, name = rest.rpartition("/")
    return "/" + folder, name
