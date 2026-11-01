"""Album Downloads: the photos other Contributors added to a shared Album."""

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from google_to_synology_photos.cli import main
from google_to_synology_photos.importer import run_import
from google_to_synology_photos.paths import content_hash
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder, jpeg_bytes, write_album_download


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
URL_2 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
PHOTO_2_PATH = "Photos/Google Photos/2013/IMG_0002__d7w7p6.JPG"
THEIRS = jpeg_bytes("a photo of another Contributor", date="2019:07:14 12:00:00")


def theirs_path(name: str = "theirs.jpg", data: bytes = THEIRS) -> str:
    stem, _, ext = name.rpartition(".")
    return f"Photos/Google Photos/2019/{stem}__{content_hash(data)[:6]}.{ext}"


def test_a_photo_missing_from_the_export_joins_its_album(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    mine = takeout.photo(album, "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"IMG_0001.JPG": mine.data, "theirs.jpg": THEIRS},
    )
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == sorted([PHOTO_PATH, theirs_path()])
    assert nas.album_contents() == [("Été", sorted([PHOTO_PATH, theirs_path()]))]
    assert nas.item(theirs_path()).data == THEIRS
    assert report.uploaded == 2
    assert report.failed_writes == []


def test_the_path_uses_6_chars_of_the_content_hash_and_the_date_in_the_name(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"IMG-20240829-WA0000.gif": b"GIF89a a synthetic file"},
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [
        PHOTO_PATH,
        "Photos/Google Photos/2024/IMG-20240829-WA0000__e4vsyb.gif",
    ]


def test_bytes_already_in_the_album_create_no_second_item(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    # Google can name the file otherwise: only its bytes count.
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"renamed.jpg": mine.data}
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH]


def test_an_original_of_an_edited_photo_creates_no_second_item(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL, edited=True)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0001.JPG": mine.data}
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH]
    assert nas.item(PHOTO_PATH).data == mine.edited


def test_a_photo_of_another_album_joins_this_one_with_no_second_item(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    other = takeout.photo(takeout.album("Hiver"), "IMG_0001.JPG", URL, caption="Neige")
    mine = takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"IMG_0001.JPG": other.data, "IMG_0002.JPG": mine.data},
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH, PHOTO_2_PATH]
    assert nas.album_contents() == [
        ("Hiver", [PHOTO_PATH]),
        ("Été", [PHOTO_PATH, PHOTO_2_PATH]),
    ]


def test_a_copy_saved_outside_albums_joins_the_album_with_its_caption(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    saved = takeout.loose_photo("IMG_0001.JPG", URL)
    saved.caption = "Sauvegardée"
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0001.JPG": saved.data}
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH, PHOTO_2_PATH]
    assert nas.album_contents() == [("Été", [PHOTO_PATH, PHOTO_2_PATH])]
    assert nas.item(PHOTO_PATH).description == "Sauvegardée"


def test_a_copy_in_the_album_wins_over_a_saved_copy_of_the_same_bytes(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    saved = takeout.loose_photo("IMG_0001.JPG", URL)
    saved.data = mine.data
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0002.JPG": mine.data}
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_2_PATH]


def test_running_again_with_the_same_album_download_adds_nothing(
    tmp_path: Path,
) -> None:
    export, downloads = _album_with_one_missing_photo(tmp_path)
    nas = FakeSynologyPhotos()
    run_import(export, nas, album_downloads=downloads)
    nas.writes = 0

    report = run_import(export, nas, album_downloads=downloads)

    assert nas.writes == 0
    assert report.uploaded == 0
    assert report.album_downloads == {"Été-1": 0}


def test_a_stopped_run_continues_with_no_second_item(tmp_path: Path) -> None:
    export, downloads = _album_with_one_missing_photo(tmp_path)
    finished = FakeSynologyPhotos()
    run_import(export, finished, album_downloads=downloads)

    for stop_after in range(finished.writes):
        nas = FakeSynologyPhotos()
        nas.writes_left = stop_after
        with pytest.raises(ConnectionError):
            run_import(export, nas, album_downloads=downloads)
        nas.writes_left = None

        run_import(export, nas, album_downloads=downloads)

        assert nas.paths() == finished.paths()
        assert nas.album_contents() == finished.album_contents()


def test_a_photo_stays_when_its_zip_is_no_longer_given(tmp_path: Path) -> None:
    export, downloads = _album_with_one_missing_photo(tmp_path)
    nas = FakeSynologyPhotos()
    run_import(export, nas, album_downloads=downloads)
    nas.writes = 0

    report = run_import(export, nas, album_downloads=tmp_path / "emptied")

    assert nas.writes == 0
    assert theirs_path() in nas.paths()
    assert nas.album_contents() == [("Été", sorted([PHOTO_PATH, theirs_path()]))]
    assert report.album_downloads == {}


def test_a_refresh_keeps_the_photo_of_a_zip_no_longer_given(tmp_path: Path) -> None:
    export, downloads = _album_with_one_missing_photo(tmp_path)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été 2013"), "IMG_0001.JPG", URL, caption="La plage")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(export, nas, album_downloads=downloads)

    run_import(second, nas, previous=export)

    assert nas.album_contents() == [("Été 2013", sorted([PHOTO_PATH, theirs_path()]))]


def test_a_photo_saved_after_its_album_download_becomes_the_export_item(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    first = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0001.JPG": THEIRS}
    )
    nas = FakeSynologyPhotos()
    run_import(first, nas, album_downloads=downloads)
    held_by_hand = nas.create_album("À nous")
    nas.add_to_album(held_by_hand, [nas.item(theirs_path("IMG_0001.JPG")).id])
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0002.JPG", URL_2)
    saved = newer.loose_photo("IMG_0001.JPG", URL)
    saved.caption, saved.data = "Sauvegardée", THEIRS
    second = newer.write(tmp_path / "2025-01-01")

    report = run_import(second, nas, previous=first, album_downloads=downloads)

    saved_path = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
    assert nas.paths() == [saved_path, PHOTO_2_PATH]
    assert nas.album_contents() == [
        ("À nous", [saved_path]),
        ("Été", [saved_path, PHOTO_2_PATH]),
    ]
    assert nas.item(saved_path).description == "Sauvegardée"
    assert report.moved == 1


def test_a_saved_copy_takes_over_after_a_stop_at_any_write(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    first = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0001.JPG": THEIRS}
    )
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0002.JPG", URL_2)
    newer.loose_photo("IMG_0001.JPG", URL).data = THEIRS
    second = newer.write(tmp_path / "2025-01-01")

    def first_run() -> FakeSynologyPhotos:
        nas = FakeSynologyPhotos()
        run_import(first, nas, album_downloads=downloads)
        nas.writes = 0
        return nas

    finished = first_run()
    run_import(second, finished, previous=first, album_downloads=downloads)

    for stop_after in range(finished.writes):
        nas = first_run()
        nas.writes_left = stop_after
        with pytest.raises(ConnectionError):
            run_import(second, nas, previous=first, album_downloads=downloads)
        nas.writes_left = None

        run_import(second, nas, previous=first, album_downloads=downloads)

        assert nas.paths() == finished.paths()
        assert nas.album_contents() == finished.album_contents()


def test_bytes_a_later_export_puts_in_the_album_take_over_after_a_stop(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    first = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0001.JPG": THEIRS}
    )
    newer = TakeoutBuilder()
    album = newer.album("Été")
    newer.photo(album, "IMG_0002.JPG", URL_2)
    newer.photo(album, "IMG_0001.JPG", URL).data = THEIRS
    second = newer.write(tmp_path / "2025-01-01")

    def first_run() -> FakeSynologyPhotos:
        nas = FakeSynologyPhotos()
        run_import(first, nas, album_downloads=downloads)
        nas.writes = 0
        return nas

    finished = first_run()
    run_import(second, finished, previous=first, album_downloads=downloads)
    assert finished.paths() == [PHOTO_PATH, PHOTO_2_PATH]

    for stop_after in range(finished.writes):
        nas = first_run()
        nas.writes_left = stop_after
        with pytest.raises(ConnectionError):
            run_import(second, nas, previous=first, album_downloads=downloads)
        nas.writes_left = None

        run_import(second, nas, previous=first, album_downloads=downloads)

        assert nas.paths() == [PHOTO_PATH, PHOTO_2_PATH]
        assert nas.album_contents() == finished.album_contents()


def test_a_taken_over_photo_still_follows_its_changed_file(tmp_path: Path) -> None:
    def export(folder: str, edit: bytes) -> Path:
        takeout = TakeoutBuilder()
        album = takeout.album("Été")
        takeout.photo(album, "IMG_0002.JPG", URL_2)
        photo = takeout.photo(album, "IMG_0001.JPG", URL, edited=True)
        photo.data, photo.edited = THEIRS, edit
        return takeout.write(tmp_path / folder)

    first = export("2024-01-01", jpeg_bytes("first edit"))
    second = export("2025-01-01", jpeg_bytes("second edit"))
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"IMG_0001.JPG": THEIRS}
    )
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    copy = nas.upload(theirs_path("IMG_0001.JPG"), THEIRS)
    album_id = nas.albums()[0].id
    nas.add_to_album(album_id, [copy])

    report = run_import(second, nas, previous=first, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH, PHOTO_2_PATH]
    assert nas.item(PHOTO_PATH).data == jpeg_bytes("second edit")
    assert report.failed_writes == []


def test_two_albums_of_one_title_are_told_apart_by_their_photos(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Vacances", folder="Vacances"), "IMG_0002.JPG", URL_2)
    second = takeout.photo(
        takeout.album("Vacances", folder="Vacances(1)"), "IMG_0001.JPG", URL
    )
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Vacances",
        {"IMG_0001.JPG": second.data, "theirs.jpg": THEIRS},
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.album_contents() == [
        ("Vacances", [PHOTO_PATH, theirs_path()]),
        ("Vacances", [PHOTO_2_PATH]),
    ]


def test_the_zips_of_two_albums_of_one_title_stay_apart(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    first = takeout.photo(
        takeout.album("Vacances", folder="Vacances"), "IMG_0002.JPG", URL_2
    )
    second = takeout.photo(
        takeout.album("Vacances", folder="Vacances(1)"), "IMG_0001.JPG", URL
    )
    export = takeout.write(tmp_path / "2024-01-01")
    folder = tmp_path / "album-downloads"
    write_album_download(
        folder,
        "Vacances",
        {"IMG_0002.JPG": first.data},
        zip_name="Vacances-1-001.zip",
    )
    write_album_download(
        folder,
        "Vacances",
        {"IMG_0001.JPG": second.data, "theirs.jpg": THEIRS},
        zip_name="Vacances-2-001.zip",
    )
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=folder)

    assert nas.album_contents() == [
        ("Vacances", [PHOTO_PATH, theirs_path()]),
        ("Vacances", [PHOTO_2_PATH]),
    ]
    assert report.album_downloads == {"Vacances-1": 0, "Vacances-2": 1}


def test_an_album_renamed_since_the_zip_is_found_by_its_photos(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été 2013"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"IMG_0001.JPG": mine.data, "theirs.jpg": THEIRS},
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.album_contents() == [("Été 2013", sorted([PHOTO_PATH, theirs_path()]))]


def test_an_album_with_no_photo_in_the_export_is_found_by_its_title(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Hiver"), "IMG_0001.JPG", URL)
    takeout.album("Été")
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Été", {"theirs.jpg": THEIRS}
    )
    nas = FakeSynologyPhotos()

    run_import(export, nas, album_downloads=downloads)

    assert nas.album_contents() == [
        ("Hiver", [PHOTO_PATH]),
        ("Été", [theirs_path()]),
    ]


def test_an_album_download_of_no_known_album_is_reported_and_adds_nothing(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads", "Inconnu", {"theirs.jpg": THEIRS}
    )
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH]
    assert "- Inconnu" in report.render()


def test_a_file_with_no_date_is_reported_and_not_added(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"IMG_0001.JPG": mine.data, "undated.jpg": jpeg_bytes("no date", date=None)},
    )
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=downloads)

    assert nas.paths() == [PHOTO_PATH]
    assert "- Été: undated.jpg" in report.render()
    assert report.finished


def test_the_report_says_how_many_photos_each_album_download_added(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    other = takeout.photo(takeout.album("Hiver"), "IMG_0001.JPG", URL)
    mine = takeout.photo(takeout.album("Été"), "IMG_0002.JPG", URL_2)
    export = takeout.write(tmp_path / "2024-01-01")
    folder = tmp_path / "album-downloads"
    # One new photo, and one photo of the export that joins the Album.
    write_album_download(
        folder,
        "Été",
        {"theirs.jpg": THEIRS, "IMG_0001.JPG": other.data, "IMG_0002.JPG": mine.data},
    )
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=folder)

    rendered = report.render()
    assert "- Album Downloads used: 1" in rendered
    assert "- Été-1 (photos added: 2)" in rendered


def test_a_photo_that_did_not_join_its_album_is_not_counted(tmp_path: Path) -> None:
    export, downloads = _album_with_one_missing_photo(tmp_path)
    nas = FakeSynologyPhotos()
    nas.album_items = lambda album_id: []  # type: ignore[method-assign]

    report = run_import(export, nas, album_downloads=downloads)

    assert report.album_downloads == {"Été-1": 0}
    assert report.failed_writes == ["Photos of Album 'Été'"]


def test_an_album_with_orphan_comments_is_a_sure_gap(tmp_path: Path) -> None:
    takeout = _album_with_orphan_comment()
    takeout.write(tmp_path / "2024-01-01")

    report = run_import(tmp_path / "2024-01-01", FakeSynologyPhotos())

    assert "- Été (Comments with no photo: 1)" in report.render()


def test_an_album_download_takes_its_album_off_the_list(tmp_path: Path) -> None:
    export = _album_with_orphan_comment().write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"theirs.jpg": THEIRS},
        made=datetime(2024, 3, 1, tzinfo=UTC),
    )

    report = run_import(export, FakeSynologyPhotos(), album_downloads=downloads)

    assert "Comments with no photo" not in report.render()


def test_a_new_orphan_comment_brings_the_album_back_to_the_list(
    tmp_path: Path,
) -> None:
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"theirs.jpg": THEIRS},
        made=datetime(2024, 3, 1, tzinfo=UTC),
    )
    takeout = _album_with_orphan_comment()
    takeout.root_comment("share1", datetime(2024, 6, 1, tzinfo=UTC), "Encore une")
    export = takeout.write(tmp_path / "2025-01-01")

    report = run_import(export, FakeSynologyPhotos(), album_downloads=downloads)

    assert "- Été (Comments with no photo: 1)" in report.render()


def test_an_album_download_of_no_known_album_covers_nothing(tmp_path: Path) -> None:
    export = _album_with_orphan_comment().write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Inconnu",
        {"theirs.jpg": THEIRS},
        made=datetime(2024, 3, 1, tzinfo=UTC),
    )

    report = run_import(export, FakeSynologyPhotos(), album_downloads=downloads)

    assert "- Été (Comments with no photo: 1)" in report.render()


def test_a_run_on_a_finished_export_still_takes_a_new_album_download(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    mine = takeout.photo(album, "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "takeout" / "2024-01-01")
    nas = FakeSynologyPhotos()
    main(["import", str(export)], connect=lambda ask_again: nas)
    write_album_download(
        tmp_path / "takeout" / "album-downloads",
        "Été",
        {"IMG_0001.JPG": mine.data, "theirs.jpg": THEIRS},
    )

    main(["import", str(export)], connect=lambda ask_again: nas)

    assert nas.album_contents() == [("Été", sorted([PHOTO_PATH, theirs_path()]))]
    assert "- Été-1 (photos added: 1)" in capsys.readouterr().out


def test_all_the_zips_of_an_album_make_one_album_download(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    folder = tmp_path / "album-downloads"
    write_album_download(folder, "Été", {"IMG_0001.JPG": mine.data})
    write_album_download(
        folder, "Été", {"theirs.jpg": THEIRS}, zip_name="Été-1-002.zip"
    )
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=folder)

    assert report.album_downloads == {"Été-1": 1}
    assert nas.album_contents() == [("Été", sorted([PHOTO_PATH, theirs_path()]))]


def test_a_zip_with_no_folder_is_one_album_download(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    folder = tmp_path / "album-downloads"
    folder.mkdir()
    with zipfile.ZipFile(folder / "Été.zip", "w") as zf:
        zf.writestr("IMG_0001.JPG", mine.data)
        zf.writestr("theirs.jpg", THEIRS)
    nas = FakeSynologyPhotos()

    report = run_import(export, nas, album_downloads=folder)

    assert report.album_downloads == {"Été": 1}


def _album_with_one_missing_photo(tmp_path: Path) -> tuple[Path, Path]:
    takeout = TakeoutBuilder()
    mine = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL)
    export = takeout.write(tmp_path / "2024-01-01")
    downloads = write_album_download(
        tmp_path / "album-downloads",
        "Été",
        {"IMG_0001.JPG": mine.data, "theirs.jpg": THEIRS},
    )
    return export, downloads


def _album_with_orphan_comment() -> TakeoutBuilder:
    """An Album whose Comment of January 2024 sits on a photo the export lacks."""
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    mine = takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.comment(album, mine, "Zoé", datetime(2023, 1, 1, tzinfo=UTC), "Joli")
    takeout.root_comment("share1", datetime(2023, 1, 1, tzinfo=UTC), "Joli")
    takeout.root_comment("share1", datetime(2024, 1, 15, tzinfo=UTC), "Et celle-ci ?")
    return takeout
