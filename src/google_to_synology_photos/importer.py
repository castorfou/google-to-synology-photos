"""Import use case: turns a Takeout Export into the NAS Library.

Synology Photos answers success even when a write did nothing, so every write is
read back, and a write that did not stick goes to the report.
"""

from pathlib import Path

from google_to_synology_photos.description import comment_line, photo_descriptions
from google_to_synology_photos.media import ConversionFailedError, MediaPreparer
from google_to_synology_photos.paths import nas_path
from google_to_synology_photos.report import Report
from google_to_synology_photos.synology import SynologyPhotos
from google_to_synology_photos.takeout import read_export


def run_import(export_dir: Path, nas: SynologyPhotos) -> Report:
    """Build the NAS Library from the Takeout Export in export_dir.

    Uploads the photos, creates the Albums, sets the Photo Descriptions, and
    returns the report of the run.
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
        for url, photo in export.photos.items():
            try:
                prepared = media.prepare(photo)
            except ConversionFailedError:
                # Not sent as it is: its MP4 would land beside it at a later run.
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
        album_id = nas.create_album(album.title)
        wanted = [item_ids[url] for url in album.urls]
        nas.add_to_album(album_id, wanted)
        report.albums_created += 1
        if set(wanted) - set(nas.album_items(album_id)):
            report.failed_writes.append(f"Photos of Album {album.title!r}")

    descriptions = photo_descriptions(export)
    for url, item_id in item_ids.items():
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
