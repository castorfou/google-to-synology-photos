"""How the Synology Photos client sorts the errors DSM answers during a send.

A stub stands in for the DSM Web API: each call answers what the test sets, or
fails with the DSM error code the test sets.
"""

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from google_to_synology_photos.dsm import DsmApi
from google_to_synology_photos.synology import (
    FileRefusedError,
    NotReindexedError,
    SynologyError,
)
from google_to_synology_photos.synology_client import SynologyPhotosClient


PATH = "Photos/Google Photos/2013/IMG_0001.JPG"
DATA = b"photo bytes"
MTIME = datetime(2013, 7, 14, 12, tzinfo=UTC)
ITEM_ID = 42
# DSM error codes as measured on the DS923.
UNSUPPORTED_FILE = 620
SESSION_GONE = 119
PERMISSION_DENIED = 105


class StubDsm:
    """Answers each call by its api.method name, or fails with a DSM error code."""

    def __init__(self, on_nas: bool) -> None:
        listed = [{"filename": "IMG_0001.JPG", "id": ITEM_ID}] if on_nas else []
        self.answers: dict[str, dict[str, Any]] = {
            "SYNO.Foto.Browse.Folder.get": {"folder": {"id": 7}},
            "SYNO.Foto.Browse.Item.list": {"list": listed},
            "SYNO.Foto.Browse.Item.get": {
                "list": [{"id": ITEM_ID, "filesize": len(DATA)}]
            },
            "SYNO.Foto.Index.get": {},
            "SYNO.Foto.Upload.Item.upload_to_folder": {"id": ITEM_ID, "action": "new"},
            "SYNO.FileStation.Upload.upload": {},
        }
        self.failing: dict[str, int] = {}

    def call(
        self, api: str, method: str, version: int, plain: Any = None, **params: Any
    ) -> dict[str, Any]:
        return self._answer(f"{api}.{method}")

    def upload(self, api: str, method: str, *args: Any) -> dict[str, Any]:
        return self._answer(f"{api}.{method}")

    def _answer(self, call: str) -> dict[str, Any]:
        if call in self.failing:
            raise SynologyError(self.failing[call], call)
        return self.answers[call]


def client(dsm: StubDsm, index_timeout: float = 600.0) -> SynologyPhotosClient:
    return SynologyPhotosClient(cast(DsmApi, dsm), index_timeout)


@pytest.mark.parametrize(
    ("on_nas", "call"),
    [
        (False, "SYNO.Foto.Upload.Item.upload_to_folder"),
        (True, "SYNO.FileStation.Upload.upload"),
    ],
)
def test_a_send_the_nas_answers_with_an_error_is_a_refused_file(
    on_nas: bool, call: str
) -> None:
    dsm = StubDsm(on_nas)
    dsm.failing[call] = UNSUPPORTED_FILE

    with pytest.raises(FileRefusedError) as refused:
        client(dsm).overwrite(PATH, DATA, MTIME)

    assert refused.value.code == UNSUPPORTED_FILE


@pytest.mark.parametrize(
    ("call", "code"),
    [
        ("SYNO.Foto.Browse.Item.list", PERMISSION_DENIED),
        ("SYNO.Foto.Browse.Folder.get", PERMISSION_DENIED),
        ("SYNO.Foto.Upload.Item.upload_to_folder", SESSION_GONE),
    ],
)
def test_a_read_or_a_lost_session_during_a_send_is_no_refused_file(
    call: str, code: int
) -> None:
    dsm = StubDsm(on_nas=False)
    dsm.failing[call] = code

    with pytest.raises(SynologyError) as stopped:
        client(dsm).upload(PATH, DATA, MTIME)

    assert not isinstance(stopped.value, FileRefusedError)
    assert stopped.value.code == code


def test_an_overwrite_not_read_again_in_time_keeps_its_item() -> None:
    dsm = StubDsm(on_nas=True)
    dsm.answers["SYNO.Foto.Index.get"] = {"metadata": 3}

    with pytest.raises(NotReindexedError) as late:
        client(dsm, index_timeout=0.0).overwrite(PATH, DATA, MTIME)

    assert late.value.item_id == ITEM_ID


def test_an_overwrite_whose_reindex_wait_fails_keeps_its_item() -> None:
    dsm = StubDsm(on_nas=True)
    dsm.failing["SYNO.Foto.Index.get"] = PERMISSION_DENIED

    with pytest.raises(NotReindexedError) as late:
        client(dsm).overwrite(PATH, DATA, MTIME)

    assert late.value.item_id == ITEM_ID


def test_a_session_lost_while_waiting_for_the_reindex_stops() -> None:
    dsm = StubDsm(on_nas=True)
    dsm.failing["SYNO.Foto.Index.get"] = SESSION_GONE

    with pytest.raises(SynologyError) as stopped:
        client(dsm).overwrite(PATH, DATA, MTIME)

    assert stopped.value.session_lost
