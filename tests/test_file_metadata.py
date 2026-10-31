"""Dates and positions written, for real, into the files sent to the NAS.

The files are tiny real JPEGs and PNGs. They are read back with Pillow, so what
the tests see does not depend on the tool that writes the metadata.
"""

import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PIL import ExifTags, Image

from google_to_synology_photos.cli import main
from google_to_synology_photos.importer import run_import
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder, jpeg_bytes


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
PHOTO_PATH = "Photos/Google Photos/2016/IMG-20160809-WA0001__yxk3qp.jpg"
TAKEN = datetime(2016, 8, 9, 14, 30, 5, tzinfo=UTC)


def date_taken(data: bytes) -> str | None:
    """The DateTimeOriginal of a file, or None."""
    exif = Image.open(io.BytesIO(data)).getexif().get_ifd(ExifTags.IFD.Exif)
    return exif.get(ExifTags.Base.DateTimeOriginal)


def _gps(data: bytes) -> dict:
    """The GPS tags of a file."""
    return Image.open(io.BytesIO(data)).getexif().get_ifd(ExifTags.IFD.GPSInfo)


def position(data: bytes) -> tuple[float, float] | None:
    """The signed (latitude, longitude) of a file, or None."""
    gps = _gps(data)
    if ExifTags.GPS.GPSLatitude not in gps:
        return None
    return (
        _angle(gps[ExifTags.GPS.GPSLatitude], gps[ExifTags.GPS.GPSLatitudeRef]),
        _angle(gps[ExifTags.GPS.GPSLongitude], gps[ExifTags.GPS.GPSLongitudeRef]),
    )


def altitude(data: bytes) -> float | None:
    """The signed altitude of a file, or None."""
    gps = _gps(data)
    if ExifTags.GPS.GPSAltitude not in gps:
        return None
    below_sea_level = gps[ExifTags.GPS.GPSAltitudeRef] in (1, b"\x01")
    return float(gps[ExifTags.GPS.GPSAltitude]) * (-1 if below_sea_level else 1)


def _angle(parts: tuple, ref: str) -> float:
    """The signed angle of EXIF degrees, minutes, seconds and their reference."""
    degrees, minutes, seconds = (float(part) for part in parts)
    sign = -1 if ref in ("S", "W") else 1
    return sign * (degrees + minutes / 60 + seconds / 3600)


def sent_file(tmp_path: Path, **photo: Any) -> bytes:
    """Import one photo with these builder options; return the file on the NAS."""
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, "IMG-20160809-WA0001.jpg", URL, taken=TAKEN, **photo)
    nas = FakeSynologyPhotos()
    run_import(takeout.write(tmp_path / "export"), nas)
    return nas.item(PHOTO_PATH).data


def test_a_jpg_with_no_date_arrives_with_the_date_taken_from_google_photos(
    tmp_path: Path,
) -> None:
    assert date_taken(sent_file(tmp_path, exif_date=None)) == "2016:08:09 14:30:05"


def test_a_date_in_the_file_is_kept_and_the_file_is_sent_as_it_is(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    photo = takeout.photo(
        album,
        "IMG-20160809-WA0001.jpg",
        URL,
        taken=TAKEN,
        exif_date="2001:02:03 04:05:06",
    )
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).data == photo.data
    assert date_taken(photo.data) == "2001:02:03 04:05:06"


def test_a_position_from_google_photos_is_written_when_the_file_has_none(
    tmp_path: Path,
) -> None:
    data = sent_file(tmp_path, geo=(48.8584, 2.2945, 35.0))

    assert position(data) == pytest.approx((48.8584, 2.2945), abs=1e-5)


def test_a_position_in_the_south_and_west_keeps_its_signs(tmp_path: Path) -> None:
    data = sent_file(tmp_path, geo=(-33.4489, -70.6693, 0.0))

    assert position(data) == pytest.approx((-33.4489, -70.6693), abs=1e-5)


def test_the_altitude_comes_with_the_position(tmp_path: Path) -> None:
    assert altitude(sent_file(tmp_path, geo=(31.5, 35.4, -430.5))) == -430.5


def test_a_position_at_sea_level_has_no_altitude(tmp_path: Path) -> None:
    assert altitude(sent_file(tmp_path, geo=(43.3, 5.4, 0.0))) is None


def test_zeros_in_google_photos_mean_no_position(tmp_path: Path) -> None:
    data = sent_file(tmp_path, exif_date=None, geo=(0.0, 0.0, 0.0))

    assert position(data) is None


def test_a_position_in_the_file_is_kept_while_a_missing_date_is_written(
    tmp_path: Path,
) -> None:
    data = sent_file(
        tmp_path, exif_date=None, exif_position=(1.5, 2.5), geo=(48.8584, 2.2945, 35.0)
    )

    assert position(data) == (1.5, 2.5)
    assert date_taken(data) == "2016:08:09 14:30:05"


def test_a_date_in_the_file_is_kept_while_a_missing_position_is_written(
    tmp_path: Path,
) -> None:
    data = sent_file(
        tmp_path, exif_date="2001:02:03 04:05:06", geo=(48.8584, 2.2945, 35.0)
    )

    assert date_taken(data) == "2001:02:03 04:05:06"
    assert position(data) == pytest.approx((48.8584, 2.2945), abs=1e-5)


@pytest.mark.parametrize("no_date", ["0000:00:00 00:00:00", "    :  :     :  :  "])
def test_an_empty_date_in_the_file_counts_as_no_date(
    tmp_path: Path, no_date: str
) -> None:
    assert date_taken(sent_file(tmp_path, exif_date=no_date)) == "2016:08:09 14:30:05"


def test_an_empty_xmp_date_does_not_hide_a_date_in_the_exif(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    photo = takeout.photo(takeout.album("Été"), "IMG.jpg", URL, taken=TAKEN)
    photo.data = jpeg_bytes(URL, "2001:02:03 04:05:06", xmp_date="0000:00:00 00:00:00")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item("Photos/Google Photos/2016/IMG__yxk3qp.jpg").data == photo.data


def test_a_date_only_in_the_xmp_is_kept_and_the_exif_date_is_written(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    photo = takeout.photo(takeout.album("Été"), "IMG.jpg", URL, taken=TAKEN)
    photo.data = jpeg_bytes(URL, date=None, xmp_date="2001-02-03T04:05:06")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    sent = nas.item("Photos/Google Photos/2016/IMG__yxk3qp.jpg").data
    assert date_taken(sent) == "2016:08:09 14:30:05"
    assert b"2001-02-03T04:05:06" in sent


def test_writing_the_date_leaves_the_image_and_the_rest_of_the_file_as_they_are(
    tmp_path: Path,
) -> None:
    data = sent_file(tmp_path, exif_date=None)

    source = jpeg_bytes(URL, date=None)
    assert source[source.index(b"\xff\xda") :] == data[data.index(b"\xff\xda") :]
    assert URL.encode() in data


def test_no_text_is_written_into_the_file(tmp_path: Path) -> None:
    data = sent_file(tmp_path, exif_date=None, caption="Première baignade")

    assert b"baignade" not in data


def test_a_png_with_no_date_arrives_with_the_date_taken_from_google_photos(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    photo = takeout.photo(album, "Capture.png", URL, taken=TAKEN)
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, "PNG")
    photo.data = buffer.getvalue()
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    sent = nas.item("Photos/Google Photos/2016/Capture__yxk3qp.png").data
    assert date_taken(sent) == "2016:08:09 14:30:05"


def test_a_jpeg_named_png_arrives_with_the_date_taken_from_google_photos(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, "Capture.png", URL, taken=TAKEN, exif_date=None)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    sent = nas.item("Photos/Google Photos/2016/Capture__yxk3qp.png").data
    assert date_taken(sent) == "2016:08:09 14:30:05"
    assert report.metadata_not_written == []


def test_a_video_is_sent_as_it_is(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    video = takeout.photo(album, "VID.mp4", URL, taken=TAKEN, geo=(48.8, 2.3, 0.0))
    video.data = b"\x00\x00\x00\x18ftypmp42 not a real video"
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item("Photos/Google Photos/2016/VID__yxk3qp.mp4").data == video.data
    assert report.metadata_not_written == []


def test_a_file_that_cannot_be_written_is_sent_as_it_is_and_reported(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    photo = takeout.photo(album, "IMG-20160809-WA0001.jpg", URL, taken=TAKEN)
    photo.data = b"\xff\xd8\xff\xe0 a broken JPEG"
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).data == photo.data
    assert report.metadata_not_written == [PHOTO_PATH]
    assert PHOTO_PATH in report.render()
    assert report.failed_writes == []


def test_the_year_folder_comes_from_google_photos_and_not_from_the_file(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Été")
    takeout.photo(album, "IMG.jpg", URL, taken=TAKEN, exif_date="2001:02:03 04:05:06")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.paths() == ["Photos/Google Photos/2016/IMG__yxk3qp.jpg"]


def test_the_same_export_gives_the_same_bytes_at_every_run(tmp_path: Path) -> None:
    first = sent_file(tmp_path / "a", exif_date=None, geo=(48.8584, 2.2945, 35.0))
    second = sent_file(tmp_path / "b", exif_date=None, geo=(48.8584, 2.2945, 35.0))

    assert first == second


def test_g2s_says_so_when_exiftool_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Été"), "IMG.jpg", URL)
    export = takeout.write(tmp_path / "export")
    monkeypatch.setenv("PATH", "")
    nas = FakeSynologyPhotos()

    with pytest.raises(SystemExit) as stop:
        main(["import", str(export)], connect=lambda ask_again: nas)

    assert "ExifTool" in str(stop.value)
    assert nas.paths() == []
