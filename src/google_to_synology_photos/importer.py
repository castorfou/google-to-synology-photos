"""Import use case: turns a Takeout Export into the NAS Library.

Synology Photos answers success even when a write did nothing, so every write is
read back, and a write that did not stick goes to the report.
"""

from pathlib import Path

from google_to_synology_photos.description import photo_description
from google_to_synology_photos.paths import nas_path
from google_to_synology_photos.report import Report
from google_to_synology_photos.synology import SynologyPhotos
from google_to_synology_photos.takeout import read_export


def run_import(export_dir: Path, nas: SynologyPhotos) -> Report:
    report = Report()
    export = read_export(export_dir)

    item_ids: dict[str, int] = {}
    for url, photo in export.photos.items():
        path = nas_path(photo)
        item_id = nas.upload(path, photo.read())
        if nas.item_at(path) != item_id:
            report.failed_writes.append(f"Upload of {path}")
            continue
        item_ids[url] = item_id
        report.uploaded += 1

    for album in export.albums:
        album_id = nas.create_album(album.title)
        wanted = [item_ids[url] for url in album.urls if url in item_ids]
        nas.add_to_album(album_id, wanted)
        report.albums_created += 1
        if set(wanted) - set(nas.album_items(album_id)):
            report.failed_writes.append(f"Photos of Album {album.title!r}")

    for url, item_id in item_ids.items():
        text = photo_description(export.photos[url])
        if not text:
            continue
        nas.set_description(item_id, text)
        if nas.description(item_id) == text:
            report.descriptions_written += 1
        else:
            report.failed_writes.append(
                f"Photo Description of {nas_path(export.photos[url])}"
            )

    return report
