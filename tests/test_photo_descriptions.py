"""Photo Descriptions and the report, after an import into a fake Synology Photos."""

from datetime import UTC, datetime
from pathlib import Path

from google_to_synology_photos.importer import run_import
from tests.fake_synology import FakeSynologyPhotos
from tests.takeout_builder import TakeoutBuilder


URL = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0001"
URL_2 = "https://photos.google.com/photo/AF1QipSyntheticPhotoUrl0002"
PHOTO_PATH = "Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG"
NEWER_PATH = "Photos/Google Photos/2014/IMG_0002__d7w7p6.JPG"
TAKEN_2014 = datetime(2014, 4, 13, 15, 0, 44, tzinfo=UTC)
DAY_1 = datetime(2016, 8, 9, 10, 0, tzinfo=UTC)
DAY_2 = datetime(2016, 8, 10, 10, 0, tzinfo=UTC)
DAY_3 = datetime(2017, 1, 2, 10, 0, tzinfo=UTC)


def test_description_is_the_caption_then_comments_then_a_likes_line(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "IMG_0001.JPG", URL, caption="Première baignade 🌊")
    # Google does not always write them oldest first.
    takeout.comment(album, photo, "Zoé", DAY_2, "Trop bien !\nÀ refaire 😀")
    takeout.like(album, photo, "Théo", DAY_3)
    takeout.comment(album, photo, "Théo", DAY_1, "Où est-ce ?")
    takeout.like(album, photo, "Zoé", DAY_3)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "Première baignade 🌊\n"
        "\n"
        "Théo, 2016-08-09: Où est-ce ?\n"
        "Zoé, 2016-08-10: Trop bien !\n"
        "À refaire 😀\n"
        "❤️ Théo, Zoé"
    )


def test_reactions_are_grouped_by_album_title_when_two_albums_bring_some(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    noel = takeout.album("Noël")
    photo = takeout.photo(noel, "IMG_0001.JPG", URL, caption="Le sapin")
    famille = takeout.album("Famille", sidecars_only=True)
    takeout.add_to_album(famille, photo)
    takeout.comment(noel, photo, "Zoé", DAY_2, "Joli !")
    takeout.like(noel, photo, "Théo", DAY_3)
    takeout.like(famille, photo, "Zoé", DAY_1)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export", zips=2), nas)

    assert nas.item(PHOTO_PATH).description == (
        "Le sapin\n\nFamille\n❤️ Zoé\n\nNoël\nZoé, 2016-08-10: Joli !\n❤️ Théo"
    )


def test_no_album_title_when_only_one_of_the_albums_brings_reactions(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    noel = takeout.album("Noël")
    photo = takeout.photo(noel, "IMG_0001.JPG", URL)
    takeout.add_to_album(takeout.album("Famille"), photo)
    takeout.like(noel, photo, "Théo", DAY_1)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == "❤️ Théo"


def test_the_oldest_photo_of_an_album_starts_with_the_album_text(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", description="Chez mamie\nen Bretagne 🎄")
    newer = takeout.photo(album, "IMG_0002.JPG", URL_2, taken=TAKEN_2014)
    oldest = takeout.photo(album, "IMG_0001.JPG", URL, caption="Le sapin")
    takeout.album_like(album, "Zoé", DAY_3)
    takeout.album_comment(album, "Théo", DAY_1, "Quel beau séjour")
    takeout.comment(album, oldest, "Zoé", DAY_2, "Joli !")
    takeout.comment(album, newer, "Zoé", DAY_2, "Encore !")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "Chez mamie\n"
        "en Bretagne 🎄\n"
        "\n"
        "Théo, 2016-08-09: Quel beau séjour\n"
        "❤️ Zoé\n"
        "\n"
        "Le sapin\n"
        "\n"
        "Zoé, 2016-08-10: Joli !"
    )
    assert nas.item(NEWER_PATH).description == "Zoé, 2016-08-10: Encore !"


def test_a_photo_oldest_of_two_albums_shows_both_album_texts_under_their_titles(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    noel = takeout.album("Noël", description="Chez mamie")
    photo = takeout.photo(noel, "IMG_0001.JPG", URL, caption="Le sapin")
    famille = takeout.album("Famille", sidecars_only=True, description="Tout le monde")
    takeout.add_to_album(famille, photo)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "Famille\nTout le monde\n\nNoël\nChez mamie\n\nLe sapin"
    )


def test_the_album_text_moves_when_an_older_photo_joins_the_album(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", description="Chez mamie")
    takeout.photo(album, "IMG_0002.JPG", URL_2, taken=TAKEN_2014)
    nas = FakeSynologyPhotos()
    run_import(takeout.write(tmp_path / "2024-01-01"), nas)
    assert nas.item(NEWER_PATH).description == "Chez mamie"

    takeout.photo(album, "IMG_0001.JPG", URL)
    run_import(takeout.write(tmp_path / "2024-07-01"), nas)

    assert nas.item(PHOTO_PATH).description == "Chez mamie"
    assert nas.item(NEWER_PATH).description == ""


def test_a_root_comment_matching_no_photo_goes_to_the_text_of_its_album(
    tmp_path: Path,
) -> None:
    # The root file repeats Comments of the sidecars: that is what ties a share
    # link to its Album.
    takeout = TakeoutBuilder()
    album = takeout.album("Noël", description="Chez mamie")
    photo = takeout.photo(album, "IMG_0001.JPG", URL, caption="Le sapin")
    takeout.album_like(album, "Zoé", DAY_1)
    takeout.comment(album, photo, "Zoé", DAY_2, "Joli !")
    takeout.root_comment("SHARE1", DAY_2, "Joli !")
    takeout.root_comment("SHARE1", DAY_3, "Elle est passée où,\ncette photo ?")
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "Chez mamie\n"
        "\n"
        "❤️ Zoé\n"
        "2017-01-02: Elle est passée où,\n"
        "cette photo ?\n"
        "\n"
        "Le sapin\n"
        "\n"
        "Zoé, 2016-08-10: Joli !"
    )
    assert "- Noël: 2017-01-02: Elle est passée où, cette photo ?" in report.render()
    assert "Joli" not in report.render()


def test_a_root_comment_on_an_album_ties_its_share_link_to_that_album(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.album_comment(album, "Zoé", DAY_1, "Quel séjour")
    takeout.root_comment("SHARE1", DAY_1, "Quel séjour")
    takeout.root_comment("SHARE1", DAY_2, "Orpheline")
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "Zoé, 2016-08-09: Quel séjour\n2016-08-10: Orpheline"
    )


def test_a_root_comment_with_no_known_album_is_only_reported(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.root_comment("UNKNOWN", DAY_1, "Perdue")
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == ""
    assert "- No known Album: 2016-08-09: Perdue" in report.render()


def test_a_clean_run_reports_no_orphan_comment(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Noël"), "IMG_0001.JPG", URL)

    report = run_import(takeout.write(tmp_path / "export"), FakeSynologyPhotos())

    assert "## Comments that match no photo\n\nNone.\n" in report.render()


def test_a_root_like_matching_no_photo_has_no_name_but_keeps_its_heart(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.comment(album, photo, "Zoé", DAY_1, "Joli !")
    takeout.root_comment("SHARE1", DAY_1, "Joli !")
    takeout.root_like("SHARE1", DAY_2)
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == (
        "2016-08-10: ❤️\n\nZoé, 2016-08-09: Joli !"
    )
    assert "- Noël: 2016-08-10: ❤️" in report.render()


def test_an_english_root_comments_file_is_read_like_a_french_one(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder(root_comments="shared_album_comments.json")
    takeout.photo(takeout.album("Christmas"), "IMG_0001.JPG", URL)
    takeout.root_comment("UNKNOWN", DAY_1, "Lost")

    report = run_import(takeout.write(tmp_path / "export"), FakeSynologyPhotos())

    assert "- No known Album: 2016-08-09: Lost" in report.render()


def _takeout_with_every_kind_of_comment_and_like() -> TakeoutBuilder:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    photo = takeout.photo(album, "IMG_0001.JPG", URL)
    takeout.comment(album, photo, "Zoé", DAY_1, "Joli !")
    takeout.like(album, photo, "Théo", DAY_1)
    takeout.like(album, photo, "Zoé", DAY_1)
    takeout.album_comment(album, "Théo", DAY_2, "Quel séjour")
    takeout.album_like(album, "Théo", DAY_2)
    takeout.root_comment("SHARE1", DAY_1, "Joli !")
    takeout.root_comment("SHARE1", DAY_3, "Orpheline")
    takeout.root_comment("UNKNOWN", DAY_3, "Perdue")
    return takeout


def test_the_report_counts_the_comments_and_likes_written(tmp_path: Path) -> None:
    takeout = _takeout_with_every_kind_of_comment_and_like()

    report = run_import(takeout.write(tmp_path / "export"), FakeSynologyPhotos())

    assert "- Comments written: 3\n" in report.render()
    assert "- Likes written: 3\n" in report.render()


def test_comments_and_likes_of_a_write_that_did_not_stick_are_not_counted(
    tmp_path: Path,
) -> None:
    takeout = _takeout_with_every_kind_of_comment_and_like()
    nas = FakeSynologyPhotos()
    nas.descriptions_stick = False

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert "- Comments written: 0\n" in report.render()
    assert "- Likes written: 0\n" in report.render()


def test_a_comment_on_a_photo_with_no_file_becomes_an_orphan_of_its_album(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    takeout.photo(album, "IMG_0001.JPG", URL)
    missing = takeout.photo(album, "IMG_0002.JPG", URL_2, has_file=False)
    takeout.comment(album, missing, "Zoé", DAY_2, "Où est-elle ?")
    takeout.root_comment("SHARE1", DAY_2, "Où est-elle ?")
    nas = FakeSynologyPhotos()

    report = run_import(takeout.write(tmp_path / "export"), nas)

    assert nas.item(PHOTO_PATH).description == "Zoé, 2016-08-10: Où est-elle ?"
    assert report.orphan_comments == ["Noël: Zoé, 2016-08-10: Où est-elle ?"]
    assert report.comments_written == 1


def test_a_comment_on_an_album_with_no_imported_photo_is_reported(
    tmp_path: Path,
) -> None:
    takeout = TakeoutBuilder()
    takeout.photo(takeout.album("Noël"), "IMG_0001.JPG", URL)
    album = takeout.album("Pâques", sidecars_only=True)
    takeout.photo(album, "IMG_0002.JPG", URL_2, has_file=False)
    takeout.album_comment(album, "Zoé", DAY_1, "Quel séjour")

    report = run_import(takeout.write(tmp_path / "export"), FakeSynologyPhotos())

    assert report.orphan_comments == ["Pâques: Zoé, 2016-08-09: Quel séjour"]


def test_a_video_gets_comments_and_likes_like_a_photo(tmp_path: Path) -> None:
    takeout = TakeoutBuilder()
    album = takeout.album("Noël")
    video = takeout.photo(album, "MOV_0001.mp4", URL, caption="Le sapin")
    takeout.like(album, video, "Zoé", DAY_1)
    nas = FakeSynologyPhotos()

    run_import(takeout.write(tmp_path / "export"), nas)

    path = "Photos/Google Photos/2013/MOV_0001__yxk3qp.mp4"
    assert nas.item(path).description == "Le sapin\n\n❤️ Zoé"
