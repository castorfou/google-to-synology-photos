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
PAGE = 1000
ALBUM_BATCH = 100
METADATA_JOBS = ("basic", "metadata", "metadata_updating")
RETRY_DELAYS = (0.0, 1.0, 2.0, 4.0, 8.0)


class SynologyPhotosClient:
    """The SynologyPhotos interface, on a logged-in DsmApi."""

    def __init__(self, api: DsmApi, index_timeout: float = 120.0) -> None:
        self._api = api
        self._folder_ids: dict[str, int] = {}
        # Folder -> {file name: item id}, as last listed or changed by this client.
        self._listings: dict[str, dict[str, int]] = {}
        self._index_timeout = index_timeout

    # Items

    def upload(self, path: str, data: bytes) -> int:
        # duplicate="ignore" skips only identical files: a different file under
        # a taken name is stored as a renamed copy. So a taken path is checked
        # here first.
        folder, name = _split(path)
        listing = self._listings.get(folder)
        if listing is None:
            self.item_at(path)
            listing = self._listings.get(folder, {})
        if name in listing:
            return listing[name]
        folder_id = self._folder_id(folder, create=True)
        assert folder_id is not None
        result = self._api.upload(
            {
                "api": "SYNO.Foto.Upload.Item",
                "method": "upload_to_folder",
                "version": "1",
                "target_folder_id": json.dumps(folder_id),
                "name": json.dumps(name, ensure_ascii=False),
                "duplicate": json.dumps("ignore"),
                "mtime": str(int(time.time())),
            },
            name,
            data,
        )
        item_id = int(result["id"])
        self._listings.setdefault(folder, {})[name] = item_id
        return item_id

    def overwrite(self, path: str, data: bytes) -> int:
        # Upload.Item has no overwrite; File Station has, and keeps the item id.
        item_id = self.item_at(path)
        if item_id is None:
            return self.upload(path, data)
        folder, name = _split(path)
        self._api.upload(
            {
                "api": "SYNO.FileStation.Upload",
                "method": "upload",
                "version": "2",
                "path": f"/home/{PHOTOS_ROOT}{folder}",
                "create_parents": "true",
                "overwrite": "true",
            },
            name,
            data,
        )
        self._wait_for_reindex(item_id, len(data))
        return item_id

    def item_at(self, path: str) -> int | None:
        folder, name = _split(path)
        folder_id = self._folder_id(folder, create=False)
        if folder_id is None:
            return None
        items = self._pages("SYNO.Foto.Browse.Item", 2, folder_id=folder_id)
        self._listings[folder] = {i["filename"]: int(i["id"]) for i in items}
        return self._listings[folder].get(name)

    def delete_item(self, item_id: int) -> None:
        self._api.call("SYNO.Foto.Browse.Item", "delete", 1, id=[item_id])
        for listing in self._listings.values():
            for name in [n for n, i in listing.items() if i == item_id]:
                del listing[name]

    def set_description(self, item_id: int, text: str) -> None:
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
        item = self._item(item_id, ["description"])
        return None if item is None else str(item["additional"]["description"])

    # Albums

    def create_album(self, name: str) -> int:
        data = self._api.call(
            "SYNO.Foto.Browse.NormalAlbum", "create", 1, name=name, item=[]
        )
        return int(data["album"]["id"])

    def rename_album(self, album_id: int, name: str) -> None:
        self._api.call("SYNO.Foto.Browse.Album", "set_name", 1, id=album_id, name=name)

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None:
        for start in range(0, len(item_ids), ALBUM_BATCH):
            batch = item_ids[start : start + ALBUM_BATCH]
            self._api.call(
                "SYNO.Foto.Browse.NormalAlbum", "add_item", 1, id=album_id, item=batch
            )

    def albums(self) -> list[NasAlbum]:
        return [
            NasAlbum(int(a["id"]), a["name"])
            for a in self._pages("SYNO.Foto.Browse.Album", 2)
        ]

    def album_items(self, album_id: int) -> list[int]:
        items = self._pages("SYNO.Foto.Browse.Item", 2, album_id=album_id)
        return [int(i["id"]) for i in items]

    # Helpers

    def _folder_id(self, folder: str, create: bool) -> int | None:
        """Return the id of the Synology Photos folder, creating it if asked."""
        if folder in self._folder_ids:
            return self._folder_ids[folder]
        try:
            data = self._api.call("SYNO.Foto.Browse.Folder", "get", 2, name=folder)
        except SynologyError as error:
            if error.code != FOLDER_MISSING or not create:
                if error.code == FOLDER_MISSING:
                    return None
                raise
            parent, _, name = folder.rpartition("/")
            parent_id = self._folder_id(parent or "/", create=True)
            try:
                data = self._api.call(
                    "SYNO.Foto.Browse.Folder",
                    "create",
                    1,
                    target_id=parent_id,
                    name=name,
                )
            except SynologyError as race:
                if race.code != FOLDER_EXISTS:
                    raise
                data = self._api.call("SYNO.Foto.Browse.Folder", "get", 2, name=folder)
        folder_id = int(data["folder"]["id"])
        self._folder_ids[folder] = folder_id
        return folder_id

    def _item(self, item_id: int, additional: list[str]) -> dict[str, Any] | None:
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
        found: list[dict[str, Any]] = []
        while True:
            data = self._api.call(
                api, "list", version, offset=len(found), limit=PAGE, **params
            )
            page: list[dict[str, Any]] = data.get("list", [])
            found += page
            if len(page) < PAGE:
                return found


def _split(path: str) -> tuple[str, str]:
    """Split a NAS path into its Synology Photos folder and file name."""
    root, _, rest = path.partition("/")
    if root != PHOTOS_ROOT or not rest:
        raise ValueError(f"not a path of the Personal Space: {path}")
    folder, _, name = rest.rpartition("/")
    return "/" + folder, name
