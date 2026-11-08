"""The g2s command, run end to end against the fake Synology Photos."""

from pathlib import Path

import pytest

from google_to_synology_photos.cli import main
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder


def test_g2s_import_builds_the_library_and_writes_the_report_next_to_the_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Anniversaire")
    takeout.photo(
        album,
        "IMG_0002.JPG",
        "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002",
        caption="Les bougies",
    )
    export = takeout.write(tmp_path / "takeout" / "2024-01-01")
    nas = FakeSynologyPhotos()

    exit_code = main(["import", str(export)], connect=lambda ask_again: nas)

    assert exit_code == 0
    assert [name for name, _ in nas.album_contents()] == ["Anniversaire"]
    printed = capsys.readouterr().out
    assert "Photos and videos uploaded: 1" in printed
    report_file = tmp_path / "takeout" / "report.md"
    assert report_file.read_text(encoding="utf-8") in printed


def test_g2s_import_refuses_a_folder_that_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        main(
            ["import", str(tmp_path / "missing")],
            connect=lambda ask_again: FakeSynologyPhotos(),
        )

    assert stop.value.code != 0


def test_g2s_import_refuses_a_selected_albums_export_with_a_clear_message(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Anniversaire", sidecars_only=True)
    takeout.photo(
        album,
        "IMG_0002.JPG",
        "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002",
        has_file=False,
    )
    export = takeout.write(tmp_path / "takeout" / "2024-01-01", year_folders=False)
    nas = FakeSynologyPhotos()

    with pytest.raises(SystemExit) as stop:
        main(["import", str(export)], connect=lambda ask_again: nas)

    assert "full Takeout Export" in str(stop.value.code)
    assert "Anniversaire" in str(stop.value.code)
    assert nas.paths() == []
    assert not (tmp_path / "takeout" / "report.md").exists()


def test_g2s_login_asks_again_for_the_nas_details(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked_again: list[bool] = []

    def connect(ask_again: bool) -> FakeSynologyPhotos:
        asked_again.append(ask_again)
        return FakeSynologyPhotos()

    exit_code = main(["login"], connect=connect)

    assert exit_code == 0
    assert asked_again == [True]
    assert "Logged in" in capsys.readouterr().out


def _one_photo_export(tmp_path: Path) -> Path:
    """Write an export holding one photo, in one Album."""
    takeout = TakeoutBuilder()
    album = takeout.album("Anniversaire")
    takeout.photo(
        album,
        "IMG_0002.JPG",
        "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002",
        caption="Les bougies",
    )
    return takeout.write(tmp_path / "takeout" / "2024-01-01")


def test_g2s_import_logs_in_again_when_the_session_expired_while_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export = _one_photo_export(tmp_path)
    nas = FakeSynologyPhotos()
    asked_again: list[bool] = []

    def connect(ask_again: bool) -> FakeSynologyPhotos:
        asked_again.append(ask_again)
        nas.log_in()
        if len(asked_again) == 1:
            # Gone by the first call, made once the export is read.
            nas.end_session()
        return nas

    exit_code = main(["import", str(export)], connect=connect)

    assert exit_code == 0
    assert asked_again == [False, False]
    assert len(nas.paths()) == 1
    assert "Photos and videos uploaded: 1" in capsys.readouterr().out


def test_g2s_import_sends_again_an_upload_that_met_a_lost_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export = _one_photo_export(tmp_path)
    nas = FakeSynologyPhotos()
    nas.session_ends_at = "upload"

    def connect(ask_again: bool) -> FakeSynologyPhotos:
        nas.log_in()
        return nas

    exit_code = main(["import", str(export)], connect=connect)

    assert exit_code == 0
    assert len(nas.paths()) == 1
    printed = capsys.readouterr().out
    assert "Photos and videos uploaded: 1" in printed
    assert "## Files the NAS refused, not uploaded\n\nNone." in printed


def test_g2s_import_stops_with_a_clear_message_when_logging_in_again_fails(
    tmp_path: Path,
) -> None:
    export = _one_photo_export(tmp_path)
    nas = FakeSynologyPhotos()
    nas.session_ends_at = "upload"
    logins: list[bool] = []

    def connect(ask_again: bool) -> FakeSynologyPhotos:
        logins.append(ask_again)
        if len(logins) > 1:
            raise SystemExit("g2s: Wrong user name or password.")
        return nas

    with pytest.raises(SystemExit) as stop:
        main(["import", str(export)], connect=connect)

    message = str(stop.value.code)
    assert "session with the NAS was lost" in message
    assert "Wrong user name or password." in message
    assert nas.paths() == []
    assert not (tmp_path / "takeout" / "report.md").exists()


def test_g2s_import_stops_when_the_session_is_lost_again_after_logging_in_again(
    tmp_path: Path,
) -> None:
    export = _one_photo_export(tmp_path)
    nas = FakeSynologyPhotos()
    nas.end_session()

    with pytest.raises(SystemExit) as stop:
        # This login does not bring the session back.
        main(["import", str(export)], connect=lambda ask_again: nas)

    assert "Synology error 119" in str(stop.value.code)
    assert "Run g2s again" in str(stop.value.code)
