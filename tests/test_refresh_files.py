"""Refresh: files that changed since the previous Takeout Export."""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import ExifTags, Image

from google_to_synology_photos.cli import main
from google_to_synology_photos.importer import run_import
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder, jpeg_bytes
from tests.test_video_conversion import AVI, H264, make_video


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
URL_2 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
PHOTO_2_PATH = "Photos/Google Photos/2013/IMG_0002__d7w7p6.JPG"
MOVED_PATH = "Photos/Google Photos/2016/IMG_0001__yxk3qp.JPG"
OWN_PATH = "Photos/Mobile/mine.jpg"
VIDEO_PATH = "Photos/Google Photos/2013/VID__yxk3qp.mp4"
MOVED_VIDEO_PATH = "Photos/Google Photos/2016/VID__yxk3qp.mp4"
KEPT_VIDEO_PATH = "Photos/Google Photos/2013/VID__yxk3qp.mov"
JANUARY_2013 = datetime(2013, 1, 5, 10, 0, 0, tzinfo=UTC)
AUGUST_2016 = datetime(2016, 8, 9, 14, 30, 5, tzinfo=UTC)


def test_a_new_edit_replaces_the_file_and_keeps_text_and_album(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    newer = TakeoutBuilder()
    edited = newer.photo(
        newer.album("Été"), "IMG_0001.JPG", URL, caption="La plage", edited=True
    )
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    item_id = nas.item(PHOTO_PATH).id

    report = run_import(second, nas, previous=first)

    assert nas.paths() == [PHOTO_PATH]
    assert nas.item(PHOTO_PATH).data == edited.edited
    assert nas.item(PHOTO_PATH).id == item_id
    assert nas.item(PHOTO_PATH).description == "La plage"
    assert nas.album_contents() == [("Été", [PHOTO_PATH])]
    assert report.replaced == 1
    assert report.uploaded == 0
    assert "Files replaced: 1" in report.render()


def test_a_changed_edit_replaces_the_file(tmp_path: Path) -> None:
    def export(folder: str, edit: bytes) -> Path:
        takeout = TakeoutBuilder()
        photo = takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL, edited=True)
        photo.edited = edit
        return takeout.write(tmp_path / folder)

    first = export("2024-01-01", jpeg_bytes("first edit"))
    second = export("2025-01-01", jpeg_bytes("second edit"))
    nas = FakeSynologyPhotos()
    run_import(first, nas)

    report = run_import(second, nas, previous=first)

    assert nas.item(PHOTO_PATH).data == jpeg_bytes("second edit")
    assert report.replaced == 1


def test_without_a_previous_export_nothing_is_overwritten(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    original = before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL, edited=True)
    nas = FakeSynologyPhotos()
    run_import(before.write(tmp_path / "2024-01-01"), nas)

    report = run_import(newer.write(tmp_path / "2025-01-01"), nas)

    assert nas.item(PHOTO_PATH).data == original.data
    assert report.replaced == 0
    assert report.already_on_nas == 1


def test_an_unchanged_file_is_not_sent_again(tmp_path: Path) -> None:
    def export(folder: str) -> Path:
        takeout = TakeoutBuilder()
        takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL, edited=True)
        return takeout.write(tmp_path / folder)

    first = export("2024-01-01")
    second = export("2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    nas.writes = 0

    report = run_import(second, nas, previous=first)

    assert nas.writes == 0
    assert report.replaced == 0
    assert report.already_on_nas == 1


def test_a_photo_stays_in_its_albums_when_its_item_id_changes(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    newer = TakeoutBuilder()
    newer.photo(
        newer.album("Été"), "IMG_0001.JPG", URL, caption="La plage", edited=True
    )
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    nas.overwrite_keeps_id = False

    report = run_import(second, nas, previous=first)

    assert nas.album_contents() == [("Été", [PHOTO_PATH])]
    assert nas.item(PHOTO_PATH).description == "La plage"
    assert report.albums_created == 0
    assert report.replaced == 1


def test_a_fixed_date_moves_the_photo_and_leaves_no_duplicate(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    newer = TakeoutBuilder()
    newer.photo(
        newer.album("Été"),
        "IMG_0001.JPG",
        URL,
        caption="La plage",
        taken=AUGUST_2016,
    )
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)

    report = run_import(second, nas, previous=first)

    assert nas.paths() == [MOVED_PATH]
    assert nas.album_contents() == [("Été", [MOVED_PATH])]
    assert nas.item(MOVED_PATH).description == "La plage"
    assert report.moved == 1
    assert report.uploaded == 0
    assert report.albums_created == 0
    assert "Files moved: 1" in report.render()


def test_a_moved_photo_stays_in_an_album_google_photos_took_it_out_of(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    photo = before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    before.add_to_album(before.album("Noël"), photo)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Noël"), "IMG_0001.JPG", URL, taken=AUGUST_2016)
    first = before.write(tmp_path / "2024-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)

    run_import(newer.write(tmp_path / "2025-01-01"), nas, previous=first)

    assert nas.album_contents() == [
        ("Noël", [MOVED_PATH]),
        ("Été", [MOVED_PATH]),
    ]


def test_a_moved_photo_stays_in_a_hand_made_album(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL, taken=AUGUST_2016)
    first = before.write(tmp_path / "2024-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    own = nas.upload(OWN_PATH, b"own photo")
    favourites = nas.create_album("Nos favoris")
    nas.add_to_album(favourites, [nas.item(PHOTO_PATH).id, own])

    run_import(newer.write(tmp_path / "2025-01-01"), nas, previous=first)

    assert nas.album_contents() == [
        ("Nos favoris", [MOVED_PATH, OWN_PATH]),
        ("Été", [MOVED_PATH]),
    ]


def test_a_date_fixed_within_its_year_reaches_the_file(tmp_path: Path) -> None:
    def export(folder: str, taken: datetime) -> Path:
        takeout = TakeoutBuilder()
        takeout.photo(
            takeout.album("Été"), "IMG_0001.JPG", URL, taken=taken, exif_date=None
        )
        return takeout.write(tmp_path / folder)

    first = export("2024-01-01", datetime(2013, 4, 13, 15, 0, 44, tzinfo=UTC))
    second = export("2025-01-01", JANUARY_2013)
    nas = FakeSynologyPhotos()
    run_import(first, nas)

    report = run_import(second, nas, previous=first)

    assert nas.paths() == [PHOTO_PATH]
    exif = Image.open(io.BytesIO(nas.item(PHOTO_PATH).data)).getexif()
    held = exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal]
    assert held == "2013:01:05 10:00:00"
    assert report.replaced == 1


def test_the_old_item_stays_when_the_moved_photo_could_not_join_its_album(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL, taken=AUGUST_2016)
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    monkeypatch.setattr(nas, "add_to_album", lambda album_id, item_ids: None)

    report = run_import(second, nas, previous=first)

    assert PHOTO_PATH in nas.paths()
    assert "Photos of Album 'Été'" in report.failed_writes
    assert report.moved == 0


def test_an_old_item_that_stays_is_listed_in_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL, taken=AUGUST_2016)
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    monkeypatch.setattr(nas, "delete_item", lambda item_id: None)

    report = run_import(second, nas, previous=first)

    assert report.failed_writes == [f"Removal of {PHOTO_PATH}"]
    assert report.moved == 0


def test_a_move_done_is_not_done_again(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL)
    newer = TakeoutBuilder()
    newer.photo(newer.album("Été"), "IMG_0001.JPG", URL, taken=AUGUST_2016)
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    run_import(second, nas, previous=first)
    nas.writes = 0

    report = run_import(second, nas, previous=first)

    assert nas.writes == 0
    assert report.moved == 0
    assert report.already_on_nas == 1


def test_a_refresh_run_again_ends_with_the_same_library(tmp_path: Path) -> None:
    before = TakeoutBuilder()
    before.photo(before.album("Été"), "IMG_0001.JPG", URL, caption="La plage")
    newer = TakeoutBuilder()
    edited = newer.photo(
        newer.album("Été"), "IMG_0001.JPG", URL, caption="La plage", edited=True
    )
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    run_import(second, nas, previous=first)

    run_import(second, nas, previous=first)

    assert nas.paths() == [PHOTO_PATH]
    assert nas.item(PHOTO_PATH).data == edited.edited
    assert nas.item(PHOTO_PATH).description == "La plage"
    assert nas.album_contents() == [("Été", [PHOTO_PATH])]


def test_a_refresh_stopped_at_any_write_ends_like_one_that_never_stopped(
    tmp_path: Path,
) -> None:
    before = TakeoutBuilder()
    album = before.album("Été")
    before.photo(album, "IMG_0001.JPG", URL, caption="La plage")
    before.photo(album, "IMG_0002.JPG", URL_2, caption="Le port")
    newer = TakeoutBuilder()
    album = newer.album("Été")
    newer.photo(album, "IMG_0001.JPG", URL, caption="La plage", taken=AUGUST_2016)
    newer.photo(album, "IMG_0002.JPG", URL_2, caption="Le port", edited=True)
    first = before.write(tmp_path / "2024-01-01")
    second = newer.write(tmp_path / "2025-01-01")

    def imported() -> FakeSynologyPhotos:
        nas = FakeSynologyPhotos()
        run_import(first, nas)
        nas.writes = 0
        return nas

    def library(nas: FakeSynologyPhotos) -> tuple[object, ...]:
        files = {p: (nas.item(p).data, nas.item(p).description) for p in nas.paths()}
        return files, nas.album_contents()

    whole = imported()
    run_import(second, whole, previous=first)
    assert whole.writes > 4

    for stop_at in range(whole.writes):
        nas = imported()
        nas.writes_left = stop_at
        with pytest.raises(ConnectionError):
            run_import(second, nas, previous=first)
        nas.writes_left = None

        run_import(second, nas, previous=first)

        assert library(nas) == library(whole), f"stopped at write {stop_at}"


def video_export(
    folder: Path,
    data: bytes,
    taken: datetime = datetime(2013, 4, 13, 15, 0, 44, tzinfo=UTC),
    name: str = "VID.avi",
) -> Path:
    """An export of one Album with one video."""
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), name, URL, taken=taken).data = data
    return takeout.write(folder)


def test_an_unchanged_video_is_not_converted_again(tmp_path: Path) -> None:
    data = make_video(tmp_path, *AVI)
    first = video_export(tmp_path / "2024-01-01", data)
    second = video_export(tmp_path / "2025-01-01", data)
    nas = FakeSynologyPhotos()
    run_import(first, nas)

    report = run_import(second, nas, previous=first)

    assert report.videos_converted == 0
    assert report.replaced == 0
    assert report.already_on_nas == 1


def test_a_changed_video_is_converted_and_replaced(tmp_path: Path) -> None:
    first = video_export(tmp_path / "2024-01-01", make_video(tmp_path, *AVI))
    picture = ("-f", "lavfi", "-i", "testsrc=size=80x60:rate=25:duration=0.2")
    other = make_video(tmp_path, *AVI, source=picture)
    second = video_export(tmp_path / "2025-01-01", other)
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    sent = nas.item(VIDEO_PATH).data

    report = run_import(second, nas, previous=first)

    assert nas.paths() == [VIDEO_PATH]
    assert nas.item(VIDEO_PATH).data != sent
    assert report.videos_converted == 1
    assert report.replaced == 1


def test_a_video_with_a_fixed_date_is_converted_at_its_new_path(tmp_path: Path) -> None:
    data = make_video(tmp_path, *AVI)
    first = video_export(tmp_path / "2024-01-01", data)
    second = video_export(tmp_path / "2025-01-01", data, taken=AUGUST_2016)
    nas = FakeSynologyPhotos()
    run_import(first, nas)

    report = run_import(second, nas, previous=first)

    assert nas.paths() == [MOVED_VIDEO_PATH]
    assert report.moved == 1
    assert report.videos_converted == 1


def test_a_changed_video_that_no_longer_needs_converting_leaves_no_duplicate(
    tmp_path: Path,
) -> None:
    hevc = make_video(tmp_path, "-c:v", "libx265", "-c:a", "aac", "-f", "mov")
    h264 = make_video(tmp_path, *H264, "-f", "mov")
    first = video_export(tmp_path / "2024-01-01", hevc, name="VID.mov")
    second = video_export(tmp_path / "2025-01-01", h264, name="VID.mov")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    assert nas.paths() == [VIDEO_PATH]

    report = run_import(second, nas, previous=first)

    assert nas.paths() == [KEPT_VIDEO_PATH]
    assert nas.album_contents() == [("Été", [KEPT_VIDEO_PATH])]
    assert report.replaced == 1


def test_such_a_video_stopped_at_any_write_leaves_no_duplicate(tmp_path: Path) -> None:
    hevc = make_video(tmp_path, "-c:v", "libx265", "-c:a", "aac", "-f", "mov")
    h264 = make_video(tmp_path, *H264, "-f", "mov")
    first = video_export(tmp_path / "2024-01-01", hevc, name="VID.mov")
    second = video_export(tmp_path / "2025-01-01", h264, name="VID.mov")

    def imported() -> FakeSynologyPhotos:
        nas = FakeSynologyPhotos()
        run_import(first, nas)
        nas.writes = 0
        return nas

    whole = imported()
    run_import(second, whole, previous=first)
    assert whole.writes == 3

    for stop_at in range(whole.writes):
        nas = imported()
        nas.writes_left = stop_at
        with pytest.raises(ConnectionError):
            run_import(second, nas, previous=first)
        nas.writes_left = None

        run_import(second, nas, previous=first)

        assert nas.paths() == [KEPT_VIDEO_PATH], f"stopped at write {stop_at}"
        assert nas.album_contents() == [("Été", [KEPT_VIDEO_PATH])]


def test_a_changed_video_that_fails_to_convert_stays_as_it_was(tmp_path: Path) -> None:
    first = video_export(tmp_path / "2024-01-01", make_video(tmp_path, *AVI))
    second = video_export(tmp_path / "2025-01-01", b"not a video")
    nas = FakeSynologyPhotos()
    run_import(first, nas)
    sent = nas.item(VIDEO_PATH).data

    report = run_import(second, nas, previous=first)

    assert nas.item(VIDEO_PATH).data == sent
    assert nas.album_contents() == [("Été", [VIDEO_PATH])]
    assert report.replaced == 0
    assert len(report.failed_conversions) == 1


def edited_export(folder: Path, edited: bool = False) -> Path:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG_0001.JPG", URL, edited=edited)
    return takeout.write(folder)


def test_g2s_compares_with_the_newest_older_export_next_to_it(tmp_path: Path) -> None:
    edited_export(tmp_path / "2023-01-01", edited=True)
    edited_export(tmp_path / "2024-01-01")
    export = edited_export(tmp_path / "2025-01-01", edited=True)
    edited_export(tmp_path / "2026-01-01")
    (tmp_path / "2024-06-01").mkdir()
    nas = FakeSynologyPhotos()
    run_import(tmp_path / "2024-01-01", nas)

    main(["import", str(export)], connect=lambda ask_again: nas)

    assert "Files replaced: 1" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_g2s_takes_only_a_dated_folder_for_an_older_export(tmp_path: Path) -> None:
    edited_export(tmp_path / "2024-backup")
    export = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    run_import(edited_export(tmp_path / "elsewhere" / "first"), nas)

    main(["import", str(export)], connect=lambda ask_again: nas)

    assert "Files replaced: 0" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_g2s_compares_with_the_export_it_is_given(tmp_path: Path) -> None:
    given = edited_export(tmp_path / "elsewhere" / "first")
    edited_export(tmp_path / "2024-01-01", edited=True)
    export = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    run_import(given, nas)

    main(
        ["import", str(export), "--previous", str(given)],
        connect=lambda ask_again: nas,
    )

    assert "Files replaced: 1" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_g2s_overwrites_nothing_without_an_older_export(tmp_path: Path) -> None:
    export = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    run_import(edited_export(tmp_path / "elsewhere" / "first"), nas)

    main(["import", str(export)], connect=lambda ask_again: nas)

    assert "Files replaced: 0" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_g2s_refuses_a_previous_export_that_does_not_exist(tmp_path: Path) -> None:
    export = edited_export(tmp_path / "2025-01-01")

    with pytest.raises(SystemExit) as stop:
        main(
            ["import", str(export), "--previous", str(tmp_path / "missing")],
            connect=lambda ask_again: FakeSynologyPhotos(),
        )

    assert stop.value.code != 0


def replaced_files(export: Path) -> str:
    """The line of the report next to export that counts the files replaced."""
    report = (export.parent / "report.md").read_text(encoding="utf-8")
    return next(line for line in report.splitlines() if "Files replaced" in line)


def test_g2s_does_nothing_on_an_export_it_finished(tmp_path: Path) -> None:
    first = edited_export(tmp_path / "2024-01-01")
    second = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    main(["import", str(first)], connect=lambda ask_again: nas)
    main(["import", str(second)], connect=lambda ask_again: nas)
    assert replaced_files(second) == "- Files replaced: 1"
    nas.writes = 0

    main(["import", str(second)], connect=lambda ask_again: nas)

    assert nas.writes == 0
    assert replaced_files(second) == "- Files replaced: 0"


def test_g2s_goes_on_replacing_after_a_stop(tmp_path: Path) -> None:
    first = edited_export(tmp_path / "2024-01-01")
    second = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    main(["import", str(first)], connect=lambda ask_again: nas)
    nas.writes_left = 0
    with pytest.raises(SystemExit):
        main(["import", str(second)], connect=lambda ask_again: nas)
    nas.writes_left = None

    main(["import", str(second)], connect=lambda ask_again: nas)

    assert replaced_files(second) == "- Files replaced: 1"


def test_a_change_of_an_export_left_unfinished_is_not_lost(tmp_path: Path) -> None:
    first = edited_export(tmp_path / "2024-01-01")
    unfinished = edited_export(tmp_path / "2024-07-01", edited=True)
    latest = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    main(["import", str(first)], connect=lambda ask_again: nas)
    nas.writes_left = 0
    with pytest.raises(SystemExit):
        main(["import", str(unfinished)], connect=lambda ask_again: nas)
    nas.writes_left = None

    main(["import", str(latest)], connect=lambda ask_again: nas)

    assert replaced_files(latest) == "- Files replaced: 1"


def test_an_export_with_a_failed_write_is_not_finished(tmp_path: Path) -> None:
    def export(folder: str, data: bytes) -> Path:
        return video_export(tmp_path / folder, data)

    first = export("2024-01-01", make_video(tmp_path, *AVI))
    second = export("2025-01-01", b"not a video")
    picture = ("-f", "lavfi", "-i", "testsrc=size=80x60:rate=25:duration=0.2")
    third = export("2026-01-01", make_video(tmp_path, *AVI, source=picture))
    nas = FakeSynologyPhotos()
    main(["import", str(first)], connect=lambda ask_again: nas)
    main(["import", str(second)], connect=lambda ask_again: nas)
    sent = nas.item(VIDEO_PATH).data

    main(["import", str(third)], connect=lambda ask_again: nas)

    assert nas.item(VIDEO_PATH).data != sent
    assert not (second / ".g2s-done").exists()
    assert (third / ".g2s-done").exists()


def test_a_previous_export_given_is_used_even_on_a_finished_export(
    tmp_path: Path,
) -> None:
    first = edited_export(tmp_path / "2024-01-01")
    second = edited_export(tmp_path / "2025-01-01", edited=True)
    nas = FakeSynologyPhotos()
    main(["import", str(first)], connect=lambda ask_again: nas)
    main(["import", str(second)], connect=lambda ask_again: nas)

    main(
        ["import", str(second), "--previous", str(first)],
        connect=lambda ask_again: nas,
    )

    assert replaced_files(second) == "- Files replaced: 1"
