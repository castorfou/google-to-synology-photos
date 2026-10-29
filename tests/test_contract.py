"""Contract of the Synology Photos client.

Runs against the in-memory fake always, and against the DS923 when
G2S_CONTRACT=1, with the test user of data/raw/nas-api-test.env. On the NAS it
works in its own folder of the Personal Space and removes what it created.
"""

import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from google_to_synology_photos.synology import SynologyError, SynologyPhotos
from tests.fake_synology import FakeSynologyPhotos


ENV_FILE = Path(__file__).parents[1] / "data" / "raw" / "nas-api-test.env"
UNKNOWN_ID = 999_999_999
TEXT = "Première baignade 🌊 — « été »\n\n💬 Alice : Trop beau !\n❤️ Alice, Bob"


@dataclass
class Media:
    photo: bytes
    other_photo: bytes
    video: bytes


@dataclass
class Nas:
    client: SynologyPhotos
    root: str
    media: Media

    def path(self, name: str) -> str:
        return f"{self.root}/{name}"


def _ffmpeg_media(tmp: Path) -> Media:
    """Tiny real media files, so that Synology Photos indexes them."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is needed to make media for the NAS")

    def make(name: str, *args: str) -> bytes:
        out = tmp / name
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", *args, str(out)], check=True
        )
        return out.read_bytes()

    def still(color: str) -> list[str]:
        return ["-f", "lavfi", "-i", f"color=c={color}", "-frames:v", "1"]

    return Media(
        photo=make("red.jpg", *still("red:s=64x48")),
        other_photo=make("blue.jpg", *still("blue:s=80x60")),
        video=make(
            "clip.mp4",
            *["-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=1"],
            *["-pix_fmt", "yuv420p"],
        ),
    )


def _real_nas(tmp: Path) -> Iterator[Nas]:
    if os.environ.get("G2S_CONTRACT") != "1":
        pytest.skip("contract test against the NAS: set G2S_CONTRACT=1")
    if not ENV_FILE.exists():
        pytest.skip(f"missing {ENV_FILE}")
    from google_to_synology_photos.dsm import DsmApi, unverified_tls
    from google_to_synology_photos.synology_client import SynologyPhotosClient

    env = dict(
        line.split("=", 1)
        for line in ENV_FILE.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    api = DsmApi(env["NAS_URL"], unverified_tls())
    api.login(env["NAS_USER"], env["NAS_PASSWORD"])
    client = SynologyPhotosClient(api)
    folder = f"g2s-contract-{uuid.uuid4().hex[:8]}"
    albums_before = {a.id for a in client.albums()}
    try:
        yield Nas(client, f"Photos/{folder}", _ffmpeg_media(tmp))
    finally:
        created = [a.id for a in client.albums() if a.id not in albums_before]
        if created:
            api.call("SYNO.Foto.Browse.Album", "delete", 1, id=created)
        api.call(
            "SYNO.FileStation.Delete",
            "start",
            2,
            plain={"path": f"/home/Photos/{folder}", "recursive": "true"},
        )
        api.logout()


@pytest.fixture(params=["fake", "real"])
def nas(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Nas]:
    if request.param == "fake":
        yield Nas(
            FakeSynologyPhotos(),
            "Photos/g2s-contract",
            Media(b"photo bytes", b"other photo bytes", b"video bytes"),
        )
    else:
        yield from _real_nas(tmp_path)


def test_upload_returns_the_id_of_the_item_at_its_path(nas: Nas) -> None:
    path = nas.path("2013/red.jpg")

    item_id = nas.client.upload(path, nas.media.photo)

    assert nas.client.item_at(path) == item_id


def test_item_at_an_empty_path_is_none(nas: Nas) -> None:
    assert nas.client.item_at(nas.path("nothing/here.jpg")) is None


def test_upload_to_a_taken_path_keeps_the_item(nas: Nas) -> None:
    path = nas.path("red.jpg")
    first = nas.client.upload(path, nas.media.photo)
    nas.client.set_description(first, TEXT)

    again = nas.client.upload(path, nas.media.other_photo)

    assert again == first
    assert nas.client.description(first) == TEXT


def test_overwrite_keeps_the_id_and_reads_the_description_from_the_new_file(
    nas: Nas,
) -> None:
    path = nas.path("red.jpg")
    item_id = nas.client.upload(path, nas.media.photo)
    nas.client.set_description(item_id, TEXT)

    replaced = nas.client.overwrite(path, nas.media.other_photo)

    assert replaced == item_id
    assert nas.client.description(item_id) == ""


def test_overwrite_of_an_empty_path_uploads(nas: Nas) -> None:
    path = nas.path("new.jpg")

    item_id = nas.client.overwrite(path, nas.media.photo)

    assert nas.client.item_at(path) == item_id


@pytest.mark.parametrize("kind", ["photo", "video"])
def test_description_is_read_back_exactly(nas: Nas, kind: str) -> None:
    name, data = (
        ("red.jpg", nas.media.photo) if kind == "photo" else ("c.mp4", nas.media.video)
    )
    item_id = nas.client.upload(nas.path(name), data)

    nas.client.set_description(item_id, TEXT)

    assert nas.client.description(item_id) == TEXT


def test_writes_on_unknown_items_answer_success_and_do_nothing(nas: Nas) -> None:
    nas.client.set_description(UNKNOWN_ID, TEXT)
    nas.client.delete_item(UNKNOWN_ID)

    assert nas.client.description(UNKNOWN_ID) is None


def test_album_holds_the_items_added_to_it(nas: Nas) -> None:
    photo = nas.client.upload(nas.path("red.jpg"), nas.media.photo)
    video = nas.client.upload(nas.path("c.mp4"), nas.media.video)
    album_id = nas.client.create_album("g2s contract Été")

    nas.client.add_to_album(album_id, [photo, video, UNKNOWN_ID])

    assert sorted(nas.client.album_items(album_id)) == sorted([photo, video])
    assert (album_id, "g2s contract Été") in [
        (a.id, a.name) for a in nas.client.albums()
    ]


def test_album_names_are_not_unique(nas: Nas) -> None:
    first = nas.client.create_album("g2s contract twin")
    second = nas.client.create_album("g2s contract twin")

    assert first != second
    names = [a.name for a in nas.client.albums() if a.id in (first, second)]
    assert names == ["g2s contract twin", "g2s contract twin"]


def test_album_rename(nas: Nas) -> None:
    album_id = nas.client.create_album("g2s contract old")

    nas.client.rename_album(album_id, "g2s contract new")

    assert (album_id, "g2s contract new") in [
        (a.id, a.name) for a in nas.client.albums()
    ]


def test_writes_on_an_unknown_album_fail(nas: Nas) -> None:
    item = nas.client.upload(nas.path("red.jpg"), nas.media.photo)

    with pytest.raises(SynologyError):
        nas.client.add_to_album(UNKNOWN_ID, [item])
    with pytest.raises(SynologyError):
        nas.client.rename_album(UNKNOWN_ID, "g2s contract ghost")


def test_deleted_item_leaves_its_path(nas: Nas) -> None:
    path = nas.path("red.jpg")
    item_id = nas.client.upload(path, nas.media.photo)

    nas.client.delete_item(item_id)

    assert nas.client.item_at(path) is None
    assert nas.client.description(item_id) is None
