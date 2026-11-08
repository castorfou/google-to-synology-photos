"""Interface of the Synology Photos client, writing as the NAS Account.

Paths are NAS paths such as ``Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG``.
Writes on unknown items answer success and do nothing, so callers read every
write back. Writes on an unknown Album fail.
Album names are not unique: Albums are only ever found by id.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


# DSM answers these when the session is gone: every later call would fail too.
# The DS923 answers 106 once the session has expired, and 119 to a call with no
# session, a wrong token or after a logout. 107, a session cut by another login,
# is Synology's documented code; it has not been seen.
SESSION_TIMEOUT = 106
SESSION_INTERRUPTED = 107
SESSION_MISSING = 119
SESSION_LOST = (SESSION_TIMEOUT, SESSION_INTERRUPTED, SESSION_MISSING)


class SynologyError(Exception):
    """A Synology Web API call failed."""

    def __init__(self, code: int, call: str) -> None:
        super().__init__(f"{call} failed with Synology error {code}")
        self.code = code

    @property
    def session_lost(self) -> bool:
        """Tell whether the call failed because the session is gone."""
        return self.code in SESSION_LOST


class FileRefusedError(SynologyError):
    """The NAS refused the file itself: the upload or overwrite call failed.

    It never stands for a lost session.
    """


class NotReindexedError(Exception):
    """An overwrite replaced the file, but Synology Photos did not read it again.

    The item keeps its id. Its Photo Description may still change to the one of
    the new file.
    """

    def __init__(self, item_id: int, reason: str) -> None:
        super().__init__(f"item {item_id} was not read again: {reason}")
        self.item_id = item_id


@dataclass(frozen=True)
class NasAlbum:
    """An Album of Synology Photos."""

    id: int
    name: str


class SynologyPhotos(Protocol):
    def upload(self, path: str, data: bytes, mtime: datetime) -> int:
        """Upload a file at path, keeping any file already there; return its id.

        mtime is the modification time of the file on the NAS: an item whose
        file holds no date shows it as its date. Raise FileRefusedError when the
        NAS refuses the file; any other error means the NAS cannot be used.
        """
        ...

    def overwrite(self, path: str, data: bytes, mtime: datetime) -> int:
        """Replace the file at path, or upload it; return its id.

        The item keeps its id. Its Photo Description is read again from the new
        file, and its date from the new file or mtime. Raise FileRefusedError as
        upload does, and NotReindexedError when the file was replaced but
        Synology Photos did not read it again.
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

    def date(self, item_id: int) -> datetime | None:
        """Return the date the item shows, or None for an unknown item."""
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


class LoggingInAgain:
    """SynologyPhotos that logs in again when the session is lost.

    A call that fails on a lost session is made once more, on the session that
    log_in_again opens. A second lost session, or a login that fails, stops the
    call. Every call may be made twice: the NAS keeps nothing of a call that
    failed on a lost session, and the client checks a path before it uploads.
    """

    def __init__(
        self, nas: SynologyPhotos, log_in_again: Callable[[], SynologyPhotos]
    ) -> None:
        self._nas = nas
        self._log_in_again = log_in_again

    def _call[T](self, call: Callable[[SynologyPhotos], T]) -> T:
        """Make call; on a lost session, log in again and make it once more."""
        try:
            return call(self._nas)
        except SynologyError as error:
            if not error.session_lost:
                raise
        self._nas = self._log_in_again()
        return call(self._nas)

    def upload(self, path: str, data: bytes, mtime: datetime) -> int:
        """Upload a file at path, keeping any file already there; return its id."""
        return self._call(lambda nas: nas.upload(path, data, mtime))

    def overwrite(self, path: str, data: bytes, mtime: datetime) -> int:
        """Replace the file at path, or upload it; return its id."""
        return self._call(lambda nas: nas.overwrite(path, data, mtime))

    def folder_items(self, folder: str) -> dict[str, int]:
        """Return the id of each item of a NAS folder and its subfolders, by path."""
        return self._call(lambda nas: nas.folder_items(folder))

    def item_at(self, path: str) -> int | None:
        """Return the id of the item at path, or None."""
        return self._call(lambda nas: nas.item_at(path))

    def delete_item(self, item_id: int) -> None:
        """Delete an item and its file."""
        self._call(lambda nas: nas.delete_item(item_id))

    def set_description(self, item_id: int, text: str) -> None:
        """Set the item's Photo Description."""
        self._call(lambda nas: nas.set_description(item_id, text))

    def description(self, item_id: int) -> str | None:
        """Return the item's Photo Description, or None for an unknown item."""
        return self._call(lambda nas: nas.description(item_id))

    def date(self, item_id: int) -> datetime | None:
        """Return the date the item shows, or None for an unknown item."""
        return self._call(lambda nas: nas.date(item_id))

    def create_album(self, name: str) -> int:
        """Create an empty Album named name; return its id."""
        return self._call(lambda nas: nas.create_album(name))

    def rename_album(self, album_id: int, name: str) -> None:
        """Rename an Album."""
        self._call(lambda nas: nas.rename_album(album_id, name))

    def add_to_album(self, album_id: int, item_ids: list[int]) -> None:
        """Add items to an Album; unknown items are skipped."""
        self._call(lambda nas: nas.add_to_album(album_id, item_ids))

    def albums(self) -> list[NasAlbum]:
        """Return every normal Album: only those can receive items."""
        return self._call(lambda nas: nas.albums())

    def album_items(self, album_id: int) -> list[int]:
        """Return the ids of the items in an Album."""
        return self._call(lambda nas: nas.album_items(album_id))
