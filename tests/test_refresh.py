"""Refresh: a newer Takeout Export brings the NAS Library up to date."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from google_to_synology_photos.importer import run_import
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
URL_2 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
URL_3 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0003"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
PHOTO_2_PATH = "Photos/Google Photos/2013/IMG_0002__d7w7p6.JPG"
PHOTO_3_PATH = "Photos/Google Photos/2013/IMG_0003__hyyytz.JPG"
PHOTO_2016_PATH = "Photos/Google Photos/2016/IMG_0002__d7w7p6.JPG"
OWN_PATH = "Photos/Mobile/mine.jpg"
AUGUST = datetime(2016, 8, 9, 14, 30, 5, tzinfo=UTC)
SEPTEMBER = datetime(2016, 9, 2, 8, 0, 0, tzinfo=UTC)


def test_an_album_renamed_in_google_photos_is_renamed_on_the_nas(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été à la mer"), "IMG_0001.JPG", URL)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    report = run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.album_contents() == [("Été à la mer", [PHOTO_PATH])]
    assert report.albums_renamed == 1
    assert report.albums_created == 0
    assert "Albums renamed: 1" in report.render()


def test_a_rename_that_does_not_stick_is_listed_in_the_report(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été à la mer"), "IMG_0001.JPG", URL)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)
    nas.album_names_stick = False

    report = run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert report.failed_writes == ["Name of Album 'Été à la mer'"]
    assert report.albums_renamed == 0


def test_two_albums_with_the_same_title_stay_separate_through_a_refresh(
    tmp_path: Path,
) -> None:
    def export(folder: str) -> Path:
        takeout = TakeoutBuilder()
        takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
        takeout.photo(takeout.album("Été", folder="Été(1)"), "IMG_0002.JPG", URL_2)
        return takeout.write(tmp_path / folder)

    nas = FakeSynologyPhotos()
    run_import(export("2024-01-01"), nas)

    report = run_import(export("2025-01-01"), nas)

    assert nas.album_contents() == [("Été", [PHOTO_PATH]), ("Été", [PHOTO_2_PATH])]
    assert report.albums_created == 0
    assert report.albums_renamed == 0


def test_one_of_two_albums_with_the_same_title_can_be_renamed(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    before.photo(before.album("Été", folder="Été(1)"), "IMG_0002.JPG", URL_2)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL)
    newer.photo(newer.album("Été à Nice"), "IMG_0002.JPG", URL_2)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.album_contents() == [
        ("Été", [PHOTO_PATH]),
        ("Été à Nice", [PHOTO_2_PATH]),
    ]


def test_new_albums_and_new_photos_of_an_album_appear(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    album = newer.album("Été")
    newer.photo(album, "IMG_0001.JPG", URL)
    newer.photo(album, "IMG_0002.JPG", URL_2)
    newer.photo(newer.album("Noël"), "IMG_0003.JPG", URL_3)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    report = run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.album_contents() == [
        ("Noël", [PHOTO_3_PATH]),
        ("Été", [PHOTO_PATH, PHOTO_2_PATH]),
    ]
    assert report.albums_created == 1
    assert report.uploaded == 2


def test_a_photo_removed_from_an_album_in_google_photos_stays_in_the_nas_album(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    album = before.album("Été")
    before.photo(album, "IMG_0001.JPG", URL)
    shared = before.photo(album, "IMG_0002.JPG", URL_2)
    other = before.album("Noël")
    before.add_to_album(other, shared)
    before.photo(other, "IMG_0003.JPG", URL_3)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL)
    other = newer.album("Noël")
    newer.photo(other, "IMG_0002.JPG", URL_2)
    newer.photo(other, "IMG_0003.JPG", URL_3)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.album_contents() == [
        ("Noël", [PHOTO_2_PATH, PHOTO_3_PATH]),
        ("Été", [PHOTO_PATH, PHOTO_2_PATH]),
    ]


def test_albums_and_photos_deleted_in_google_photos_stay_on_the_nas(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    before.photo(before.album("Noël"), "IMG_0002.JPG", URL_2)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Noël"), "IMG_0002.JPG", URL_2)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.album_contents() == [("Noël", [PHOTO_2_PATH]), ("Été", [PHOTO_PATH])]
    assert nas.item(PHOTO_PATH).description == "La plage"


def test_a_hand_made_album_with_a_photo_outside_the_library_is_untouched(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    own = nas.upload(OWN_PATH, b"own photo")
    favourites = nas.create_album("Nos favoris")
    nas.add_to_album(favourites, [nas.item(PHOTO_PATH).id, own])
    nas.delete_album(next(a.id for a in nas.albums() if a.name == "Été"))

    report = run_import(export, nas)

    assert nas.album_contents() == [
        ("Nos favoris", [PHOTO_PATH, OWN_PATH]),
        ("Été", [PHOTO_PATH]),
    ]
    assert report.albums_created == 1
    assert report.albums_renamed == 0


def test_an_album_with_a_library_photo_of_a_year_left_out_of_the_export_is_used(
    tmp_path: Path,
) -> None:
    """A photo deleted in Google Photos is still inside the NAS Library."""
    before = TakeoutBuilder()
    album = before.album("Été")
    before.photo(album, "IMG_0001.JPG", URL)
    before.photo(album, "IMG_0002.JPG", URL_2, taken=AUGUST)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été à la mer"), "IMG_0001.JPG", URL)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.album_contents() == [("Été à la mer", [PHOTO_PATH, PHOTO_2016_PATH])]


def test_text_follows_the_latest_export(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    album = before.album("Été")
    photo = before.photo(album, "IMG_0001.JPG", URL, caption="La plage")
    before.comment(album, photo, "Zoé", AUGUST, "Joli !")
    newer = TakeoutBuilder()
    album = newer.album("Été")
    photo = newer.photo(album, "IMG_0001.JPG", URL, caption="La plage de Nice")
    newer.comment(album, photo, "Théo", SEPTEMBER, "Quel beau séjour")
    newer.like(album, photo, "Zoé", SEPTEMBER)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    report = run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "La plage de Nice\n\nThéo, 2016-09-02: Quel beau séjour\n❤️ Zoé"
    )
    assert report.descriptions_rewritten == 1
    assert report.descriptions_written == 0
    assert "Photo Descriptions rewritten: 1" in report.render()


def test_a_caption_deleted_in_google_photos_is_cleared_on_the_nas(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    report = run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.item(PHOTO_PATH).description == ""
    assert report.descriptions_rewritten == 1


@pytest.fixture
def library(tmp_path: Path) -> tuple[Path, FakeSynologyPhotos]:
    """An export, with the NAS Library built from it."""
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, "IMG_0001.JPG", URL, caption="La plage")
    takeout.photo(album, "IMG_0002.JPG", URL_2)
    export = takeout.write(tmp_path / "2024-01-01")
    nas = FakeSynologyPhotos()
    run_import(export, nas)
    return export, nas


def test_a_description_changed_on_the_nas_is_put_back(
    library: tuple[Path, FakeSynologyPhotos],
) -> None:
    export, nas = library
    nas.set_description(nas.item(PHOTO_PATH).id, "Changed on the NAS")

    report = run_import(export, nas)

    assert nas.item(PHOTO_PATH).description == "La plage"
    assert report.descriptions_rewritten == 1


def test_a_photo_deleted_on_the_nas_comes_back_in_its_album_with_its_text(
    library: tuple[Path, FakeSynologyPhotos],
) -> None:
    export, nas = library
    nas.delete_item(nas.item(PHOTO_PATH).id)

    report = run_import(export, nas)

    assert nas.album_contents() == [("Été", [PHOTO_PATH, PHOTO_2_PATH])]
    assert nas.item(PHOTO_PATH).description == "La plage"
    assert report.uploaded == 1
    assert report.descriptions_written == 1


def test_an_album_deleted_on_the_nas_is_recreated(
    library: tuple[Path, FakeSynologyPhotos],
) -> None:
    export, nas = library
    nas.delete_album(nas.albums()[0].id)

    report = run_import(export, nas)

    assert nas.album_contents() == [("Été", [PHOTO_PATH, PHOTO_2_PATH])]
    assert report.albums_created == 1


def test_an_album_renamed_on_the_nas_is_renamed_back(
    library: tuple[Path, FakeSynologyPhotos],
) -> None:
    export, nas = library
    nas.rename_album(nas.albums()[0].id, "Changed on the NAS")

    report = run_import(export, nas)

    assert nas.album_contents() == [("Été", [PHOTO_PATH, PHOTO_2_PATH])]
    assert report.albums_renamed == 1
    assert report.albums_created == 0


def test_a_refresh_stopped_at_any_write_ends_like_a_refresh_that_never_stopped(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    newer = TakeoutBuilder()
    album = newer.album("Été à la mer")
    newer.photo(album, "IMG_0001.JPG", URL, caption="La plage de Nice")
    newer.photo(album, "IMG_0002.JPG", URL_2)
    newer.photo(newer.album("Noël"), "IMG_0003.JPG", URL_3)
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")

    def imported() -> FakeSynologyPhotos:
        nas = FakeSynologyPhotos()
        run_import(first, nas)
        nas.writes = 0
        return nas

    whole = imported()
    run_import(second, whole)
    assert whole.writes > 5

    for stop_at in range(whole.writes):
        nas = imported()
        nas.writes_left = stop_at
        with pytest.raises(ConnectionError):
            run_import(second, nas)
        nas.writes_left = None

        run_import(second, nas)

        assert nas.album_contents() == whole.album_contents(), f"write {stop_at}"
        assert nas.item(PHOTO_PATH).description == "La plage de Nice"
