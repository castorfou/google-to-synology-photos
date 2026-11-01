"""End-to-end import of synthetic Takeout Exports into a fake Synology Photos."""

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from google_to_synology_photos.importer import run_import
from google_to_synology_photos.takeout import SelectedAlbumsExportError
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import ROOT, TakeoutBuilder
from tests.test_video_conversion import AVI, make_video


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
URL_2 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
URL_3 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0003"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
PHOTO_2_PATH = "Photos/Google Photos/2013/IMG_0001__d7w7p6.JPG"


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
    takeout.loose_photo("IMG_0003.JPG", URL_3)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == [PHOTO_PATH]


def test_an_export_in_several_zips_imports_with_album_folders_of_sidecars_only(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Mariage", sidecars_only=True)
    photo = takeout.photo(album, "IMG_0001.JPG", URL, caption="Le gâteau")
    takeout.loose_photo("IMG_0003.JPG", URL_3)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export", zips=3), nas)

    assert nas.album_contents() == [("Mariage", [PHOTO_PATH])]
    assert nas.item(PHOTO_PATH).description == "Le gâteau"
    assert nas.item(PHOTO_PATH).data == photo.data


def test_a_photo_in_two_albums_is_one_nas_item_in_both(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    photo = takeout.photo(takeout.album("Noël"), "IMG_0001.JPG", URL)
    takeout.add_to_album(takeout.album("Famille", sidecars_only=True), photo)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export", zips=2), nas)

    assert nas.paths() == [PHOTO_PATH]
    assert nas.album_contents() == [
        ("Famille", [PHOTO_PATH]),
        ("Noël", [PHOTO_PATH]),
    ]
    assert report.uploaded == 1


def test_two_photos_sharing_a_name_get_distinct_paths(tmp_path: Path) -> None:
    # The second one is IMG_0001(1).JPG in the year folder, but has the plain
    # name in its Album folder.
    takeout = TakeoutBuilder()
    first = takeout.photo(takeout.album("Noël"), "IMG_0001.JPG", URL, caption="Un")
    second = takeout.photo(
        takeout.album("Pâques"), "IMG_0001.JPG", URL_2, caption="Deux"
    )
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.album_contents() == [("Noël", [PHOTO_PATH]), ("Pâques", [PHOTO_2_PATH])]
    assert nas.item(PHOTO_PATH).data == first.data
    assert nas.item(PHOTO_2_PATH).data == second.data


def test_a_repeated_name_pairs_each_sidecar_with_its_own_indexed_file(
    tmp_path: Path,
) -> None:
    # The Album folder holds only sidecars, so both photos have their file only
    # in the year folder, as IMG_0001.JPG and IMG_0001(1).JPG.
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", sidecars_only=True)
    first = takeout.photo(album, "IMG_0001.JPG", URL)
    second = takeout.photo(album, "IMG_0001.JPG", URL_2)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == [PHOTO_2_PATH, PHOTO_PATH]
    assert nas.item(PHOTO_PATH).data == first.data
    assert nas.item(PHOTO_2_PATH).data == second.data


def test_only_the_edited_file_of_an_edited_photo_is_uploaded_at_the_original_path(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "IMG_0001.JPG", URL, edited=True)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export", zips=2), nas)

    assert nas.paths() == [PHOTO_PATH]
    assert nas.item(PHOTO_PATH).data == photo.edited


def test_an_edited_photo_is_found_through_a_sidecar_only_album(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", sidecars_only=True)
    photo = takeout.photo(album, "IMG_0001.JPG", URL, edited=True)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).data == photo.edited


def test_an_edited_photo_with_a_repeated_name_keeps_its_own_edited_file(
    tmp_path: Path,
) -> None:
    # Google writes IMG_0001-modifié(1).JPG for the second photo.
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    first = takeout.photo(album, "IMG_0001.JPG", URL)
    second = takeout.photo(album, "IMG_0001.JPG", URL_2, edited=True)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).data == first.data
    assert nas.item(PHOTO_2_PATH).data == second.edited


def test_a_motion_photo_is_imported_as_its_jpg_without_its_video_parts(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "PXL_0001.MP.jpg", URL, motion=True)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    path = "Photos/Google Photos/2013/PXL_0001.MP__yxk3qp.jpg"
    assert nas.paths() == [path]
    assert nas.item(path).data == photo.data
    assert report.uploaded == 1


def test_a_photo_whose_sidecar_has_no_extension_joins_its_album(
    tmp_path: Path,
) -> None:
    # IMG_0001.jpg sits next to IMG_0001.supplemental-metadata.json.
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", sidecars_only=True)
    photo = takeout.photo(
        album,
        "IMG_0001",
        URL,
        taken=datetime(2016, 8, 9, 14, 30, 5, tzinfo=UTC),
        caption="Le sapin",
        file_extension=".jpg",
    )
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    path = "Photos/Google Photos/2016/IMG_0001__yxk3qp.jpg"
    assert nas.album_contents() == [("Noël", [path])]
    assert nas.item(path).data == photo.data
    assert nas.item(path).description == "Le sapin"
    assert "Noël: IMG_0001" not in report.render()


def test_a_video_whose_sidecar_has_no_extension_is_converted_like_any_video(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    photo = takeout.photo(takeout.album("Noël"), "VID", URL, file_extension=".avi")
    photo.data = make_video(tmp_path, *AVI)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == ["Photos/Google Photos/2013/VID__yxk3qp.mp4"]
    assert report.videos_converted == 1


def test_an_edited_photo_whose_sidecar_has_no_extension_sends_its_edited_file(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "IMG_0001", URL, edited=True, file_extension=".jpg")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    path = "Photos/Google Photos/2013/IMG_0001__yxk3qp.jpg"
    assert nas.paths() == [path]
    assert nas.item(path).data == photo.edited


def test_a_repeated_name_with_no_extension_pairs_each_sidecar_with_its_own_file(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", sidecars_only=True)
    first = takeout.photo(album, "IMG_0001", URL, file_extension=".jpg")
    second = takeout.photo(album, "IMG_0001", URL_2, file_extension=".jpg")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item("Photos/Google Photos/2013/IMG_0001__yxk3qp.jpg").data == first.data
    assert (
        nas.item("Photos/Google Photos/2013/IMG_0001__d7w7p6.jpg").data == second.data
    )


def test_a_second_run_writes_nothing_new_for_a_sidecar_with_no_extension(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001", URL, caption="Le sapin", file_extension=".jpg")
    export = takeout.write(tmp_path / "export")
    nas = FakeSynologyPhotos()
    run_import(export, nas)

    report = run_import(export, nas)

    assert report.uploaded == 0
    assert report.replaced == 0
    assert report.descriptions_written == 0
    assert report.descriptions_rewritten == 0
    assert report.failed_writes == []


def test_a_sidecar_with_no_extension_leaves_the_file_of_another_sidecar_alone(
    tmp_path: Path,
) -> None:
    # IMG_0001.jpg has its own sidecar, and the other photo has no file.
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001.jpg", URL)
    takeout.photo(album, "IMG_0001", URL_2, has_file=False)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == ["Photos/Google Photos/2013/IMG_0001__yxk3qp.jpg"]
    assert "- Noël: IMG_0001\n" in report.render()


def test_a_sidecar_with_an_extension_does_not_match_another_extension(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001.jpg", URL, has_file=False)
    takeout.photo(album, "IMG_0001.mp4", URL_2)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == ["Photos/Google Photos/2013/IMG_0001__d7w7p6.mp4"]
    assert "- Noël: IMG_0001.jpg" in report.render()


def test_a_sidecar_with_no_extension_skips_the_video_parts_of_a_motion_photo(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "PXL_0001", URL, motion=True, file_extension=".jpg")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    path = "Photos/Google Photos/2013/PXL_0001__yxk3qp.jpg"
    assert nas.paths() == [path]
    assert nas.item(path).data == photo.data


def test_a_sidecar_with_no_extension_takes_no_file_when_two_could_be_its_own(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001", URL, file_extension=".jpg")
    export = takeout.write(tmp_path / "export")
    with zipfile.ZipFile(next(export.glob("*.zip")), "a") as zf:
        zf.writestr(f"{ROOT}/Noël/IMG_0001.mov", b"video")
        zf.writestr(f"{ROOT}/Photos de\xa02013/IMG_0001.mov", b"video")
    nas = FakeSynologyPhotos()

    report = run_import(export, nas)

    assert nas.paths() == []
    assert "- Noël: IMG_0001\n" in report.render()


def test_a_file_with_the_exact_name_of_a_sidecar_stays_its_file(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "IMG_0001", URL, file_extension=".jpg")
    export = takeout.write(tmp_path / "export")
    with zipfile.ZipFile(next(export.glob("*.zip")), "a") as zf:
        zf.writestr(f"{ROOT}/Noël/IMG_0001", b"exact")
        zf.writestr(f"{ROOT}/Photos de\xa02013/IMG_0001", b"exact")
    nas = FakeSynologyPhotos()

    run_import(export, nas)

    assert nas.paths() == ["Photos/Google Photos/2013/IMG_0001__yxk3qp"]
    assert nas.item("Photos/Google Photos/2013/IMG_0001__yxk3qp").data != photo.data


def test_an_album_photo_whose_file_is_not_in_the_export_is_reported(
    tmp_path: Path,
) -> None:
    # Google can leave out a file: the name in the year folder is another photo's.
    takeout = TakeoutBuilder()
    other = takeout.photo(takeout.album("Pâques"), "IMG_0001.JPG", URL)
    album = takeout.album("Noël", sidecars_only=True)
    takeout.photo(album, "IMG_0001.JPG", URL_2, has_file=False)
    takeout.photo(album, "IMG_0003.JPG", URL_3)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).data == other.data
    assert PHOTO_2_PATH not in nas.paths()
    assert "- Noël: IMG_0001.JPG" in report.render()


def test_a_small_album_with_no_file_at_all_does_not_stop_a_full_export(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Noël"), "IMG_0001.JPG", URL)
    album = takeout.album("Pâques", sidecars_only=True)
    takeout.photo(album, "IMG_0002.JPG", URL_2, has_file=False)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.album_contents() == [("Noël", [PHOTO_PATH]), ("Pâques", [])]
    assert "- Pâques: IMG_0002.JPG" in report.render()


def test_a_selected_albums_export_stops_the_run_before_any_write(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Noël"), "IMG_0001.JPG", URL)
    album = takeout.album("Pâques", sidecars_only=True)
    takeout.photo(album, "IMG_0002.JPG", URL_2, has_file=False)
    takeout.photo(album, "IMG_0003.JPG", URL_3, has_file=False)
    nas = FakeSynologyPhotos()

    with pytest.raises(SelectedAlbumsExportError, match="Pâques"):
        run_import(takeout.write(tmp_path / "export", year_folders=False), nas)

    assert nas.paths() == []
    assert nas.album_contents() == []


def test_a_selected_albums_export_is_refused_when_each_album_has_some_files(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Pâques")
    takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.photo(album, "IMG_0002.JPG", URL_2, has_file=False)
    nas = FakeSynologyPhotos()

    with pytest.raises(SelectedAlbumsExportError, match="Pâques"):
        run_import(takeout.write(tmp_path / "export", year_folders=False), nas)

    assert nas.paths() == []


def test_an_english_export_is_read_like_a_french_one(tmp_path: Path) -> None:
    takeout = TakeoutBuilder(edited_suffix="-edited")
    album = takeout.album("Christmas")
    photo = takeout.photo(album, "IMG_0001.JPG", URL, edited=True)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).data == photo.edited
