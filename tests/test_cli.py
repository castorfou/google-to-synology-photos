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
