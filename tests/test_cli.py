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

    exit_code = main(["import", str(export)], connect=lambda: nas)

    assert exit_code == 0
    assert list(nas.album_contents()) == ["Anniversaire"]
    printed = capsys.readouterr().out
    assert "Photos and videos uploaded: 1" in printed
    report_file = tmp_path / "takeout" / "report.md"
    assert report_file.read_text(encoding="utf-8") in printed


def test_g2s_import_refuses_a_folder_that_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["import", str(tmp_path / "missing")], connect=FakeSynologyPhotos)

    assert stop.value.code != 0
