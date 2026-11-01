"""Runs started again: on the same export, after a stop, from any computer."""

import json
import ssl
import subprocess
from pathlib import Path
from typing import Any

import pytest

from google_to_synology_photos.cli import main
from google_to_synology_photos.importer import run_import
from google_to_synology_photos.synology import SynologyError
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
URL_2 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
URL_3 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0003"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
PHOTO_2_PATH = "Photos/Google Photos/2013/IMG_0002__d7w7p6.JPG"
PHOTO_3_PATH = "Photos/Google Photos/2013/IMG_0003__hyyytz.JPG"
VIDEO_PATH = "Photos/Google Photos/2013/VID__d7w7p6.mp4"


@pytest.fixture
def export(tmp_path: Path) -> Path:
    """Two Albums with the same title, sharing a photo, with text everywhere."""
    takeout = TakeoutBuilder()
    first = takeout.album("Été", description="Chez mamie")
    second = takeout.album("Été", folder="Été(1)")
    shared = takeout.photo(first, "IMG_0001.JPG", URL, caption="La plage")
    takeout.photo(first, "IMG_0002.JPG", URL_2, caption="Le port")
    takeout.add_to_album(second, shared)
    takeout.photo(second, "IMG_0003.JPG", URL_3)
    return takeout.write(tmp_path / "export")


def library(nas: FakeSynologyPhotos) -> tuple[Any, ...]:
    """What the Household sees: files, Albums and Photo Descriptions."""
    texts = {path: nas.item(path).description for path in nas.paths()}
    return nas.paths(), nas.album_contents(), texts


def avi(folder: Path) -> bytes:
    """A tiny real AVI."""
    file = folder / "made.avi"
    picture = ("-f", "lavfi", "-i", "testsrc=size=64x48:rate=25:duration=0.2")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *picture, "-c:v", "mpeg4", str(file)],
        check=True,
    )
    return file.read_bytes()


def test_a_second_run_on_the_same_export_writes_nothing(export: Path) -> None:
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    nas.writes = 0

    report = run_import(export, nas)

    assert nas.writes == 0
    assert report.uploaded == 0
    assert report.already_on_nas == 3
    assert report.albums_created == 0
    assert report.descriptions_written == 0


def test_a_second_run_leaves_the_library_as_it_is(export: Path) -> None:
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    before = library(nas)

    run_import(export, nas)

    assert library(nas) == before


def test_a_run_stopped_at_any_write_ends_like_a_run_that_never_stopped(
    export: Path,
) -> None:
    whole = FakeSynologyPhotos()
    run_import(export, whole)
    assert whole.writes > 8

    for stop_at in range(whole.writes):
        nas = FakeSynologyPhotos()
        nas.writes_left = stop_at
        with pytest.raises(ConnectionError):
            run_import(export, nas)
        nas.writes_left = None

        run_import(export, nas)

        assert library(nas) == library(whole), f"stopped at write {stop_at}"


def test_a_run_stopped_twice_still_ends_like_a_run_that_never_stopped(
    export: Path,
) -> None:
    whole = FakeSynologyPhotos()
    run_import(export, whole)
    nas = FakeSynologyPhotos()

    for _ in range(2):
        nas.writes_left = 3
        with pytest.raises(ConnectionError):
            run_import(export, nas)
    nas.writes_left = None
    run_import(export, nas)

    assert library(nas) == library(whole)


def test_a_converted_video_is_found_from_its_path_and_not_converted_again(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, "VID.avi", URL_2, caption="La plage").data = avi(tmp_path)
    export = takeout.write(tmp_path / "export")
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    nas.writes = 0

    report = run_import(export, nas)

    assert nas.paths() == [VIDEO_PATH]
    assert report.videos_converted == 0
    assert report.already_on_nas == 1
    assert nas.writes == 0


def test_a_photo_missing_from_the_nas_is_sent_again(export: Path) -> None:
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    before = library(nas)
    nas.delete_item(nas.item(PHOTO_PATH).id)

    report = run_import(export, nas)

    assert library(nas) == before
    assert report.uploaded == 1
    assert report.already_on_nas == 2


def test_an_empty_album_left_by_a_stop_is_used_once_only(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    takeout.photo(takeout.album("Noël"), "IMG_0002.JPG", URL_2)
    nas = FakeSynologyPhotos()
    nas.create_album("Noël")

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert [name for name, _ in nas.album_contents()] == ["Noël", "Été"]
    assert report.albums_created == 1


def test_an_album_left_part_filled_by_a_stop_is_not_duplicated(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.photo(album, "IMG_0002.JPG", URL_2)
    takeout.photo(album, "IMG_0003.JPG", URL_3)
    export = takeout.write(tmp_path / "export")
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    first = nas.item_at(PHOTO_PATH)
    assert first is not None
    nas.delete_album(nas.albums()[0].id)
    nas.add_to_album(nas.create_album("Été"), [first])

    report = run_import(export, nas)

    assert nas.album_contents() == [("Été", [PHOTO_PATH, PHOTO_2_PATH, PHOTO_3_PATH])]
    assert report.albums_created == 0


def test_an_album_with_the_same_title_and_other_photos_is_left_alone(
    tmp_path: Path, export: Path
) -> None:
    nas = FakeSynologyPhotos()
    other = nas.upload("Photos/Google Photos/2013/other.jpg", b"other")
    held = nas.create_album("Été")
    nas.add_to_album(held, [other])

    run_import(export, nas)

    assert ("Été", ["Photos/Google Photos/2013/other.jpg"]) in nas.album_contents()
    assert len(nas.album_contents()) == 3


def test_a_run_leaves_no_file_behind(tmp_path: Path, export: Path) -> None:
    before = sorted(tmp_path.rglob("*"))

    run_import(export, FakeSynologyPhotos())

    assert sorted(tmp_path.rglob("*")) == before


def test_progress_shows_while_g2s_runs(
    export: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nas = FakeSynologyPhotos()

    main(["import", str(export)], connect=lambda ask_again: nas)

    shown = capsys.readouterr()
    assert "Photos and videos: 3/3" in shown.err
    assert "Albums: 2/2" in shown.err
    assert "Photo Descriptions: 3/3" in shown.err
    assert "/3" not in shown.out


def test_g2s_says_to_run_again_when_the_connection_is_lost(export: Path) -> None:
    nas = FakeSynologyPhotos()
    nas.writes_left = 1

    with pytest.raises(SystemExit) as stop:
        main(["import", str(export)], connect=lambda ask_again: nas)

    assert "Run g2s again" in str(stop.value)


@pytest.mark.parametrize(
    "error",
    [
        ssl.SSLEOFError("connection cut"),
        OSError("no route to host"),
        json.JSONDecodeError("not JSON", "", 0),
        SynologyError(119, "upload"),
    ],
)
def test_g2s_says_to_run_again_whatever_way_the_run_stops(
    export: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    nas = FakeSynologyPhotos()

    def cut(path: str, data: bytes) -> int:
        raise error

    monkeypatch.setattr(nas, "upload", cut)

    with pytest.raises(SystemExit) as stop:
        main(["import", str(export)], connect=lambda ask_again: nas)

    assert "Run g2s again" in str(stop.value)
