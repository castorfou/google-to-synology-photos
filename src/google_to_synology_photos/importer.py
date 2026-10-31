"""Import use case: turns a Takeout Export into the NAS Library.

Synology Photos answers success even when a write did nothing, so every write is
read back, and a write that did not stick goes to the report.

A run starts from a snapshot of the NAS Library and writes only what it lacks, so
running again after a stop, from any computer, continues without a state file.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from google_to_synology_photos.description import comment_line, photo_descriptions
from google_to_synology_photos.media import ConversionFailedError, MediaPreparer
from google_to_synology_photos.paths import identity_of_path, nas_path, year_folder
from google_to_synology_photos.report import Report
from google_to_synology_photos.synology import NasAlbum, SynologyPhotos
from google_to_synology_photos.takeout import Album, Export, read_export


# Told the step, the number of the thing it starts, and how many there are.
Progress = Callable[[str, int, int], None]


@dataclass(frozen=True)
class Snapshot:
    """The NAS Library when the run starts.

    items holds the path and id of each item of the year folders of the export,
    by identity; albums holds the items of every Album.
    """

    items: dict[str, tuple[str, int]]
    albums: dict[NasAlbum, set[int]]


def take_snapshot(export: Export, nas: SynologyPhotos) -> Snapshot:
    """Read what the NAS Library holds of export."""
    items = {
        identity_of_path(path): (path, item_id)
        for folder in sorted({year_folder(p) for p in export.photos.values()})
        for path, item_id in nas.folder_items(folder).items()
    }
    albums = {album: set(nas.album_items(album.id)) for album in nas.albums()}
    return Snapshot(items, albums)


def pair_albums(
    albums: list[Album],
    wanted: list[set[int]],
    on_nas: dict[NasAlbum, set[int]],
) -> list[NasAlbum | None]:
    """Return the NAS Album of each Album, one to one; None if it has none.

    The pair sharing the most photos goes first, and the same title settles a
    tie. An Album left over takes an empty NAS Album of its title: a run stopped
    between creating an Album and filling it leaves one.
    """
    candidates = [
        (-len(items & held), album.title != nas_album.name, index, nas_album.id)
        for index, (album, items) in enumerate(zip(albums, wanted, strict=True))
        for nas_album, held in on_nas.items()
        if items & held
    ]
    by_id = {nas_album.id: nas_album for nas_album in on_nas}
    paired: list[NasAlbum | None] = [None] * len(albums)
    for _, _, index, nas_id in sorted(candidates):
        if paired[index] is None and by_id[nas_id] not in paired:
            paired[index] = by_id[nas_id]
    for index, album in enumerate(albums):
        if paired[index] is None:
            paired[index] = next(
                (
                    nas_album
                    for nas_album in sorted(on_nas, key=lambda a: a.id)
                    if nas_album.name == album.title
                    and not on_nas[nas_album]
                    and nas_album not in paired
                ),
                None,
            )
    return paired


def _no_progress(step: str, number: int, total: int) -> None:
    """Show nothing."""


def run_import(
    export_dir: Path, nas: SynologyPhotos, progress: Progress = _no_progress
) -> Report:
    """Build the NAS Library from the Takeout Export in export_dir.

    Uploads the photos the NAS lacks, creates or grows the Albums, sets the Photo
    Descriptions that differ, and returns the report of the run.
    """
    report = Report()
    export = read_export(export_dir)
    report.no_file = [
        f"{album.title}: {name}" for album in export.albums for name in album.no_file
    ]

    report.orphan_comments = [
        f"{album.title}: {comment_line(comment)}"
        for album in export.albums
        for comment in album.orphans
    ] + [f"No known Album: {comment_line(comment)}" for comment in export.orphans]

    item_ids: dict[str, int] = {}
    paths: dict[str, str] = {}
    with MediaPreparer() as media:
        snapshot = take_snapshot(export, nas)
        for number, (url, photo) in enumerate(export.photos.items(), start=1):
            progress("Photos and videos", number, len(export.photos))
            known = snapshot.items.get(identity_of_path(nas_path(photo)))
            if known is not None:
                paths[url], item_ids[url] = known
                report.already_on_nas += 1
                continue
            try:
                prepared = media.prepare(photo)
            except ConversionFailedError:
                # Not sent as it is: later runs would count it as on the NAS.
                report.failed_conversions.append(photo.member)
                continue
            path = paths[url] = nas_path(photo, prepared.extension)
            if not prepared.complete:
                report.metadata_not_written.append(path)
            item_id = nas.upload(path, prepared.data)
            if nas.item_at(path) != item_id:
                report.failed_writes.append(f"Upload of {path}")
                continue
            item_ids[url] = item_id
            report.uploaded += 1
            if prepared.extension is not None:
                report.videos_converted += 1

    for album in export.albums:
        # What is not on the NAS holds no Album text: it goes to the next photo.
        album.urls = [url for url in album.urls if url in item_ids]
    wanted = [[item_ids[url] for url in album.urls] for album in export.albums]
    paired = pair_albums(export.albums, [set(w) for w in wanted], snapshot.albums)
    for number, (album, items, nas_album) in enumerate(
        zip(export.albums, wanted, paired, strict=True), start=1
    ):
        progress("Albums", number, len(export.albums))
        if nas_album is None:
            album_id, held = nas.create_album(album.title), set[int]()
            report.albums_created += 1
        else:
            album_id, held = nas_album.id, snapshot.albums[nas_album]
        missing = [item for item in items if item not in held]
        if missing:
            nas.add_to_album(album_id, missing)
            if set(missing) - set(nas.album_items(album_id)):
                report.failed_writes.append(f"Photos of Album {album.title!r}")

    descriptions = photo_descriptions(export)
    for number, (url, item_id) in enumerate(item_ids.items(), start=1):
        progress("Photo Descriptions", number, len(item_ids))
        description = descriptions[url]
        # An empty text still clears what is there: the Album text can move away.
        if nas.description(item_id) == description.text:
            continue
        nas.set_description(item_id, description.text)
        if nas.description(item_id) == description.text:
            report.descriptions_written += 1
            report.comments_written += description.comments
            report.likes_written += description.likes
        else:
            report.failed_writes.append(f"Photo Description of {paths[url]}")

    return report
