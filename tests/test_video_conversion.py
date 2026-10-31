"""Videos converted, for real, into the files sent to the NAS.

The videos are tiny real files made by ffmpeg. The sent files are read back with
ffprobe and ExifTool, so conversions are checked on what reaches the NAS.
"""

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from google_to_synology_photos.cli import main
from google_to_synology_photos.importer import run_import
from google_to_synology_photos.report import Report
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
FOLDER = "Photos/Google Photos/2016"
TAKEN = datetime(2016, 8, 9, 14, 30, 5, tzinfo=UTC)
AVI = ("-c:v", "mpeg4", "-c:a", "libmp3lame", "-f", "avi")
PICTURE = ("-f", "lavfi", "-i", "testsrc=size=64x48:rate=25:duration=0.2")
SOUND = ("-f", "lavfi", "-i", "sine=duration=0.2", "-shortest")
H264 = ("-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac")
UNPLAYABLE = {
    "xvid-avi": ("VID.AVI", "-c:v", "mpeg4", "-c:a", "libmp3lame", "-f", "avi"),
    "mjpeg-avi": ("VID.avi", "-c:v", "mjpeg", "-c:a", "pcm_s16le", "-f", "avi"),
    "wmv-named-avi": ("VID.avi", "-c:v", "wmv2", "-c:a", "wmav2", "-f", "asf"),
    "mpeg1": ("VID.mpg", "-c:v", "mpeg1video", "-c:a", "mp2", "-f", "mpeg"),
    "mpeg2": ("VID.MOD", "-c:v", "mpeg2video", "-c:a", "mp2", "-f", "vob"),
    "hevc": ("VID.mov", "-c:v", "libx265", "-c:a", "aac", "-f", "mov"),
}


def make_video(
    folder: Path, *args: str, source: tuple[str, ...] = PICTURE + SOUND
) -> bytes:
    """A tiny real video, encoded with these ffmpeg output arguments."""
    file = folder / "made.video"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *source, *args, str(file)], check=True
    )
    return file.read_bytes()


def streams(data: bytes, folder: Path) -> dict[str, str]:
    """The codec of each stream of a file, by kind."""
    file = folder / "sent.video"
    file.write_bytes(data)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(file)],
        check=True,
        capture_output=True,
    )
    found = json.loads(probe.stdout)["streams"]
    return {s["codec_type"]: s["codec_name"] for s in found}


@pytest.mark.parametrize(
    "name, args", [(a[0], a[1:]) for a in UNPLAYABLE.values()], ids=list(UNPLAYABLE)
)
def test_an_unplayable_video_arrives_as_an_h264_and_aac_mp4(
    tmp_path: Path, name: str, args: tuple[str, ...]
) -> None:
    takeout = TakeoutBuilder()
    video = takeout.photo(takeout.album("Été"), name, URL, taken=TAKEN)
    video.data = make_video(tmp_path, *args)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == [f"{FOLDER}/VID__yxk3qp.mp4"]
    sent = nas.item(f"{FOLDER}/VID__yxk3qp.mp4").data
    assert streams(sent, tmp_path) == {"video": "h264", "audio": "aac"}
    assert report.videos_converted == 1


def date_taken(data: bytes, folder: Path) -> str:
    """The creation date in the header of an MP4, in UTC."""
    file = folder / "dated.mp4"
    file.write_bytes(data)
    read = subprocess.run(
        [
            "exiftool",
            "-s3",
            "-QuickTime:CreateDate",
            str(file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return read.stdout.strip()


def import_video(
    tmp_path: Path, name: str, data: bytes, caption: str = ""
) -> tuple[FakeSynologyPhotos, Report]:
    """Import one video in one Album; return the NAS and the report."""
    takeout = TakeoutBuilder()
    video = takeout.photo(takeout.album("Été"), name, URL, TAKEN, caption)
    video.data = data
    nas = FakeSynologyPhotos()
    return nas, run_import(takeout.write(tmp_path / "export"), nas)


def test_a_converted_video_carries_the_date_taken(tmp_path: Path) -> None:
    nas, _ = import_video(tmp_path, "VID.avi", make_video(tmp_path, *AVI))

    sent = nas.item(f"{FOLDER}/VID__yxk3qp.mp4").data
    assert date_taken(sent, tmp_path) == "2016:08:09 14:30:05"


@pytest.mark.parametrize("name, muxer", [("VID.mp4", "mp4"), ("VID.MOV", "mov")])
def test_an_h264_video_is_sent_as_it_is(tmp_path: Path, name: str, muxer: str) -> None:
    data = make_video(tmp_path, *H264, "-f", muxer)

    nas, report = import_video(tmp_path, name, data)

    stem, _, ext = name.partition(".")
    assert nas.item(f"{FOLDER}/{stem}__yxk3qp.{ext}").data == data
    assert report.videos_converted == 0
    assert report.failed_conversions == []


def test_a_converted_video_gets_its_photo_description_and_its_album(
    tmp_path: Path,
) -> None:
    nas, _ = import_video(
        tmp_path, "VID.avi", make_video(tmp_path, *AVI), caption="La plage"
    )

    path = f"{FOLDER}/VID__yxk3qp.mp4"
    assert nas.item(path).description == "La plage"
    assert nas.album_contents() == [("Été", [path])]


def test_a_description_that_does_not_stick_names_the_path_of_the_mp4(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    video = takeout.photo(takeout.album("Été"), "VID.avi", URL, TAKEN, "La plage")
    video.data = make_video(tmp_path, *AVI)
    nas = FakeSynologyPhotos()
    nas.descriptions_stick = False

    report = run_import(takeout.write(tmp_path / "export"), nas)

    path = f"{FOLDER}/VID__yxk3qp.mp4"
    assert report.failed_writes == [f"Photo Description of {path}"]


def test_a_video_with_no_sound_is_converted(tmp_path: Path) -> None:
    data = make_video(tmp_path, "-c:v", "mpeg4", "-f", "avi", source=PICTURE)

    nas, _ = import_video(tmp_path, "VID.avi", data)

    sent = nas.item(f"{FOLDER}/VID__yxk3qp.mp4").data
    assert streams(sent, tmp_path) == {"video": "h264"}


def test_a_video_with_odd_dimensions_is_converted(tmp_path: Path) -> None:
    picture = ("-f", "lavfi", "-i", "testsrc=size=65x49:rate=25:duration=0.2")
    data = make_video(tmp_path, *AVI, source=picture + SOUND)

    nas, report = import_video(tmp_path, "VID.avi", data)

    assert nas.paths() == [f"{FOLDER}/VID__yxk3qp.mp4"]
    assert report.failed_conversions == []


def test_a_heic_photo_is_not_taken_for_a_video(tmp_path: Path) -> None:
    data = make_video(tmp_path, "-c:v", "libx265", "-c:a", "aac", "-f", "mov")

    nas, report = import_video(tmp_path, "IMG.HEIC", data)

    assert nas.item(f"{FOLDER}/IMG__yxk3qp.HEIC").data == data
    assert report.videos_converted == 0


@pytest.mark.parametrize("name", ["BROKEN.avi", "BROKEN.mp4"])
def test_a_failed_conversion_is_reported_and_the_run_goes_on(
    tmp_path: Path, name: str
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, name, URL, TAKEN).data = b"RIFF not a video"
    other = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
    takeout.photo(album, "GOOD.avi", other, TAKEN).data = make_video(tmp_path, *AVI)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert len(nas.paths()) == 1
    assert nas.paths()[0].endswith(".mp4")
    assert report.videos_converted == 1
    assert report.uploaded == 1
    assert len(report.failed_conversions) == 1
    assert name in report.failed_conversions[0]
    assert report.failed_conversions[0] in report.render()


def test_a_codec_ffprobe_does_not_know_is_a_failed_conversion(tmp_path: Path) -> None:
    data = make_video(tmp_path, "-c:v", "mpeg4", "-vtag", "XVID", "-f", "avi")

    nas, report = import_video(tmp_path, "VID.avi", data.replace(b"XVID", b"ZZZZ"))

    assert nas.paths() == []
    assert len(report.failed_conversions) == 1


def test_the_album_text_goes_to_the_oldest_photo_that_was_uploaded(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été", description="Chez mamie")
    older = datetime(2010, 1, 1, tzinfo=UTC)
    takeout.photo(album, "BROKEN.avi", URL, older).data = b"RIFF not a video"
    other = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
    takeout.photo(album, "IMG.jpg", other, TAKEN)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(nas.paths()[0]).description == "Chez mamie"


def test_the_report_counts_converted_videos(tmp_path: Path) -> None:
    _, report = import_video(tmp_path, "VID.avi", make_video(tmp_path, *AVI))

    assert "- Videos converted: 1\n" in report.render()


@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe"])
def test_g2s_says_so_when_ffmpeg_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG.jpg", URL)
    export = takeout.write(tmp_path / "export")
    tools = tmp_path / "bin"
    tools.mkdir()
    for tool in {"exiftool", "ffmpeg", "ffprobe", "perl"} - {missing}:
        (tools / tool).symlink_to(str(shutil.which(tool)))
    monkeypatch.setenv("PATH", str(tools))
    nas = FakeSynologyPhotos()

    with pytest.raises(SystemExit) as stop:
        main(["import", str(export)], connect=lambda ask_again: nas)

    assert "ffmpeg" in str(stop.value)
    assert nas.paths() == []
