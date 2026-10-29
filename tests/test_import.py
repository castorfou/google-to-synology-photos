"""End-to-end import of synthetic Takeout Exports into a fake Synology Photos."""

from pathlib import Path

import pytest

from google_to_synology_photos.importer import run_import
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"


@pytest.fixture
def export(tmp_path: Path) -> Path:
    takeout = TakeoutBuilder()
    album = takeout.album("Vacances d'été 2013")
    takeout.photo(album, "IMG_0001.JPG", URL, caption="Première baignade 🌊")
    return takeout.write(tmp_path / "takeout" / "2024-01-01")


def test_photo_lands_at_its_deterministic_path(export: Path) -> None:
    nas = FakeSynologyPhotos()

    run_import(export, nas)

    assert nas.paths() == [PHOTO_PATH]


def test_album_exists_with_its_google_title_and_holds_the_photo(export: Path) -> None:
    nas = FakeSynologyPhotos()

    run_import(export, nas)

    assert nas.album_contents() == [("Vacances d'été 2013", [PHOTO_PATH])]


def test_photo_description_is_the_caption(export: Path) -> None:
    nas = FakeSynologyPhotos()

    run_import(export, nas)

    assert nas.item(PHOTO_PATH).description == "Première baignade 🌊"


def test_a_description_write_that_does_not_stick_is_listed_in_the_report(
    export: Path,
) -> None:
    nas = FakeSynologyPhotos()
    nas.descriptions_stick = False

    report = run_import(export, nas)

    assert report.failed_writes == [f"Photo Description of {PHOTO_PATH}"]
    assert f"Photo Description of {PHOTO_PATH}" in report.render()


def test_a_clean_run_reports_what_it_did_and_no_failed_write(export: Path) -> None:
    report = run_import(export, FakeSynologyPhotos())

    assert report.failed_writes == []
    text = report.render()
    assert "Photos and videos uploaded: 1" in text
    assert "Albums created: 1" in text
    assert "Photo Descriptions written: 1" in text


def test_a_photo_in_no_album_is_not_imported(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.loose_photo(
        "IMG_0003.JPG", "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0003"
    )
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == [PHOTO_PATH]
