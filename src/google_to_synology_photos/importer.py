"""Import use case: turns a Takeout Export into the NAS Library.

Synology Photos answers success even when a write did nothing, so every write is
read back, and a write that did not stick goes to the report.

A run starts from a snapshot of the NAS Library and writes only what it lacks, so
running again after a stop, from any computer, continues without a state file.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from google_to_synology_photos.album_download import (
    AlbumDownload,
    paired_album,
    photo_of_file,
    read_album_downloads,
)
from google_to_synology_photos.description import comment_line, photo_descriptions
from google_to_synology_photos.media import ConversionFailedError, MediaPreparer
from google_to_synology_photos.paths import (
    LIBRARY_ROOT,
    identity_of,
    identity_of_path,
    name_of_identity,
    name_stem,
    nas_path,
)
from google_to_synology_photos.report import Report
from google_to_synology_photos.synology import NasAlbum, SynologyPhotos
from google_to_synology_photos.takeout import Album, Export, Photo, read_export


# Told the step, the number of the thing it starts, and how many there are.
Progress = Callable[[str, int, int], None]


@dataclass(frozen=True)
class Snapshot:
    """The NAS Library when the run starts.

    items holds the path and id of each item of the NAS Library, by identity;
    albums holds the items of every Album made only of NAS Library photos: the
    others are the Household's own, and own_albums holds their items.
    twins holds the second item of an identity: a stop can leave one when a
    changed video takes another extension.
    """

    items: dict[str, tuple[str, int]]
    albums: dict[NasAlbum, set[int]]
    own_albums: dict[NasAlbum, set[int]]
    twins: dict[str, tuple[str, int]]


@dataclass
class AddedPhotos:
    """What an Album Download brought to its Album.

    urls holds the photos that joined the Album. items_to_replace holds, by url,
    the item its bytes got when only an Album Download knew them: the export item
    takes its place.
    """

    album: Album
    urls: set[str] = field(default_factory=set)
    items_to_replace: dict[str, tuple[str, int]] = field(default_factory=dict)


def take_snapshot(nas: SynologyPhotos) -> Snapshot:
    """Read what the NAS holds of the NAS Library."""
    listing = nas.folder_items(LIBRARY_ROOT)
    items: dict[str, tuple[str, int]] = {}
    twins: dict[str, tuple[str, int]] = {}
    for path, item_id in listing.items():
        identity = identity_of_path(path)
        (twins if identity in items else items)[identity] = (path, item_id)
    library = set(listing.values())
    albums = {album: set(nas.album_items(album.id)) for album in nas.albums()}
    in_library = {album: held for album, held in albums.items() if held <= library}
    own = {album: held for album, held in albums.items() if album not in in_library}
    return Snapshot(items, in_library, own, twins)


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


def _send(
    photo: Photo,
    media: MediaPreparer,
    nas: SynologyPhotos,
    report: Report,
    overwriting: str | None,
) -> tuple[str, int] | None:
    """Send photo; return its path and id, or None if it did not reach the NAS.

    Only a file sent to the path overwriting is overwritten.
    """
    try:
        prepared = media.prepare(photo)
    except ConversionFailedError:
        # Not sent as it is: later runs would count it as on the NAS.
        report.failed_conversions.append(photo.member)
        return None
    path = nas_path(photo, prepared.extension)
    if not prepared.complete:
        report.metadata_not_written.append(path)
    send = nas.overwrite if path == overwriting else nas.upload
    item_id = send(path, prepared.data)
    if nas.item_at(path) != item_id:
        report.failed_writes.append(f"Upload of {path}")
        return None
    if prepared.extension is not None:
        report.videos_converted += 1
    return path, item_id


def _add_to_album(
    album_id: int,
    name: str,
    item_ids: list[int],
    nas: SynologyPhotos,
    report: Report,
) -> bool:
    """Add items to an Album and read it back; tell whether they all joined it."""
    nas.add_to_album(album_id, item_ids)
    if set(item_ids) - set(nas.album_items(album_id)):
        report.failed_writes.append(f"Photos of Album {name!r}")
        return False
    return True


def _take_over(
    old: tuple[str, int],
    new: tuple[str, int],
    snapshot: Snapshot,
    nas: SynologyPhotos,
    report: Report,
) -> bool:
    """Put the new item in the Albums of the old one, then remove the old one.

    Only this adds to the Household's own Albums: they would lose the photo. The
    old item goes last and only if all went well, so that a stop loses nothing.
    Tells whether all went well.
    """
    (old_path, old_id), (path, item_id) = old, new
    stuck = True
    for album, held in (snapshot.albums | snapshot.own_albums).items():
        if old_id == item_id or old_id not in held:
            continue
        if item_id not in held:
            if not _add_to_album(album.id, album.name, [item_id], nas, report):
                stuck = False
                continue
            held.add(item_id)
        held.discard(old_id)
    if not stuck or old_path == path:
        return stuck
    nas.delete_item(old_id)
    if nas.item_at(old_path) is not None:
        report.failed_writes.append(f"Removal of {old_path}")
        return False
    return True


def _add_album_download(
    download: AlbumDownload,
    export: Export,
    snapshot: Snapshot,
    media: MediaPreparer,
    report: Report,
) -> AddedPhotos | None:
    """Put the photos of download in its Album; the export knows only some.

    Bytes the export holds count as its photo, which brings its Caption: a copy
    saved outside the Albums joins this one. Return what it added, or None if it
    has no Album.
    """
    album = paired_album(download, export)
    if album is None:
        report.unknown_album_downloads.append(download.name)
        return None
    album.downloaded = max(album.downloaded or download.made, download.made)
    report.album_downloads[download.name] = 0
    added = AddedPhotos(album)
    held_names: dict[str, set[str]] = {}
    for identity in snapshot.items:
        held_names.setdefault(name_of_identity(identity), set()).add(identity)
    for file in download.files:
        url = min(
            export.urls_of_file.get(file.key, []),
            key=lambda u: (u not in album.urls, u not in export.photos),
            default=None,
        )
        if url is not None:
            photo = export.photos.get(url) or export.outside_albums[url]
            # The bytes may sit on the NAS as a photo known by its content. Only
            # reading the file tells, and most files of an Album have no such item.
            if held_names.get(name_stem(file.name), set()) - {identity_of(photo)}:
                as_download = photo_of_file(file, media.date_in_file)
                if as_download is not None:
                    item = snapshot.items.get(identity_of(as_download))
                    if item is not None:
                        added.items_to_replace[url] = item
        else:
            as_download = photo_of_file(file, media.date_in_file)
            if as_download is None:
                report.undated_files.append(f"{download.folder}: {file.name}")
                continue
            photo = as_download
        export.photos.setdefault(photo.url, photo)
        if photo.url not in album.urls:
            album.urls.append(photo.url)
            added.urls.add(photo.url)
    return added


def _sure_gaps(export: Export) -> list[str]:
    """List the Albums whose orphan Comments are newer than their Album Download."""
    gaps = []
    for album in export.albums:
        downloaded = album.downloaded
        new = [c for c in album.orphans if downloaded is None or c.when > downloaded]
        if new:
            gaps.append(f"{album.title} (Comments with no photo: {len(new)})")
    return gaps


def run_import(
    export_dir: Path,
    nas: SynologyPhotos,
    progress: Progress = _no_progress,
    previous: Path | None = None,
    album_downloads: Path | None = None,
) -> Report:
    """Build the NAS Library from the Takeout Export in export_dir.

    Uploads the photos the NAS lacks, replaces the files that differ from the
    previous Takeout Export and moves those it put elsewhere, creates, renames or
    grows the Albums, sets the Photo Descriptions that differ, and returns the
    report of the run. The ZIPs in album_downloads add the photos the export lacks
    to their Albums.
    """
    report = Report()
    export = read_export(export_dir)
    earlier_photos = {} if previous is None else read_export(previous).photos
    downloads = [] if album_downloads is None else read_album_downloads(album_downloads)
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
        snapshot = take_snapshot(nas)
        added_by = {
            download.name: added
            for download in downloads
            if (added := _add_album_download(download, export, snapshot, media, report))
        }
        items_to_replace = {
            url: item
            for added in added_by.values()
            for url, item in added.items_to_replace.items()
        }
        report.sure_gaps = _sure_gaps(export)
        for number, (url, photo) in enumerate(export.photos.items(), start=1):
            progress("Photos and videos", number, len(export.photos))
            identity = identity_of(photo)
            known = snapshot.items.get(identity)
            earlier = earlier_photos.get(url)
            earlier_identity = identity if earlier is None else identity_of(earlier)
            # Still there after a move stopped halfway: the move goes on.
            left_behind = (
                None
                if earlier_identity == identity
                else snapshot.items.get(earlier_identity)
            )
            replacing = (
                known is not None
                and earlier is not None
                and earlier_identity == identity
                and photo.needs_new_file(earlier)
            )
            if known is None or replacing:
                sent = _send(photo, media, nas, report, known[0] if known else None)
                if sent is None:
                    # What is on the NAS stays, in its Albums and with its text.
                    if kept := known or left_behind or items_to_replace.get(url):
                        paths[url], item_ids[url] = kept
                    continue
            else:
                sent = known
            paths[url], item_ids[url] = sent
            replaced = [left_behind, items_to_replace.get(url)]
            if replacing:
                replaced += [known, snapshot.twins.get(identity)]
            taken_over = [
                _take_over(old, sent, snapshot, nas, report)
                for old in replaced
                if old is not None and old != sent
            ]
            if not all(taken_over):
                continue
            if left_behind is not None or url in items_to_replace:
                report.moved += 1
            elif replacing:
                report.replaced += 1
            elif known is not None:
                report.already_on_nas += 1
            else:
                report.uploaded += 1

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
            if nas_album.name != album.title:
                nas.rename_album(album_id, album.title)
                if NasAlbum(album_id, album.title) in nas.albums():
                    report.albums_renamed += 1
                else:
                    report.failed_writes.append(f"Name of Album {album.title!r}")
        missing = [item for item in items if item not in held]
        if missing and _add_to_album(album_id, album.title, missing, nas, report):
            for name, added in added_by.items():
                if added.album is album:
                    joined = {item_ids[url] for url in added.urls if url in item_ids}
                    report.album_downloads[name] += len(joined & set(missing))

    descriptions = photo_descriptions(export)
    for number, (url, item_id) in enumerate(item_ids.items(), start=1):
        progress("Photo Descriptions", number, len(item_ids))
        description = descriptions[url]
        # An empty text still clears what is there: the Album text can move away.
        current = nas.description(item_id)
        if current == description.text:
            continue
        nas.set_description(item_id, description.text)
        if nas.description(item_id) == description.text:
            if current:
                report.descriptions_rewritten += 1
            else:
                report.descriptions_written += 1
            report.comments_written += description.comments
            report.likes_written += description.likes
        else:
            report.failed_writes.append(f"Photo Description of {paths[url]}")

    return report
