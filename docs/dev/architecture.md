# Architecture

`g2s import <export folder> [--previous <export folder>]` reads a Takeout Export from its ZIPs and builds the NAS Library in Synology Photos. Vocabulary: `CONTEXT.md` at the repository root.

## Modules

All code lives in `src/google_to_synology_photos/`.

| Module | Role |
|---|---|
| `cli.py` | The `g2s` command: `g2s login` and `g2s import <export folder>`. Finds the previous export, connects to the NAS, runs the import, shows progress, prints the report and writes `report.md`. |
| `login.py` | Login to the NAS as the NAS Account: what is asked, and what is kept where. |
| `dsm.py` | Transport to the DSM Web API: login, calls, multipart uploads, TLS. |
| `synology_client.py` | The real Synology Photos client, over the `SYNO.Foto.*` Web API. |
| `importer.py` | The import use case, `run_import(export_dir, nas, progress, previous) -> Report`. The only entry the CLI calls, and the test seam. Takes the snapshot of the NAS Library and pairs the Albums. |
| `takeout.py` | Takeout reader. Reads every ZIP of the export in place, picks the file of each photo, and returns the photos by `url`, the Albums with their Comments and Likes, and the orphan Comments. Refuses an export of selected Albums. Finds the export older than another. |
| `media.py` | Media preparer: writes into a photo the date and position it lacks, with ExifTool, and converts the videos Synology Photos cannot play, with ffmpeg. |
| `paths.py` | NAS path rule. |
| `description.py` | Photo Description builder. Pure. Holds the layout of the text. |
| `synology.py` | `SynologyPhotos`, the interface of the Synology Photos client, and `SynologyError`. |
| `report.py` | Counts and lists collected during a run, rendered as Markdown. |

## Reading a Takeout Export

The reader lists every ZIP before it pairs anything: a media file and its sidecar often sit in different ZIPs, and many Album folders hold only sidecars, with the media in other folders.

- Album folders are the folders holding a `métadonnées.json` (or `metadata.json`); its `title` is the Album title. An Album is defined by its sidecars.
- A photo is identified by its sidecar `url`. The same photo appears in its Album folders and in its year folder (`Photos de 2013`); it is read once, uploaded once, and added to each Album.
- A sidecar is named `<name>.supplemental-metadata.json`. When a name repeats in a folder, Google adds an index: `<name>.supplemental-metadata(1).json` goes with `IMG(1).JPG`. The index can differ from one folder to another, so a sidecar is only paired inside its own folder. Its `title` keeps the plain name.
- Only photos that belong to at least one Album are imported.
- The date taken is the sidecar `photoTakenTime.timestamp`, in UTC. The Caption is the sidecar `description`.
- The position is the sidecar `geoData`. Google writes zeros there when it has no position, so `0, 0` means none.
- Google writes a non-breaking space in `Google Photos` and in `Photos de <year>`.

### Comments and Likes

Comments and Likes sit in `sharedAlbumComments` lists. Each entry has `creationTime`, and either `text` or `liked: true`. The lists are not always in date order, so the reader sorts them, oldest first.

- **On a photo:** in its sidecar inside an Album folder, with `contentOwnerName`. Each Album has its own list, and the sidecars of year folders have none, so the reader keeps them per Album.
- **On an Album:** in its `métadonnées.json`, with `contentOwnerName`. The same file may hold a `description`.
- **Root file:** `commentaires_albums_partagés.json` (`shared_album_comments.json` in English), at the root of `Google Photos`. Its entries have no `contentOwnerName`. They have a `contentUrl`, the share link of their Album.

Most root entries repeat an entry of a sidecar or of a `métadonnées.json`, with the same text and timestamp. This repetition ties a share link to its Album, since nothing else in the export does.

An **orphan Comment** is a Comment with no photo to sit on. It joins the Album text, and the report lists it with its Album:

- A root entry that repeats nothing is an orphan of the Album its share link is tied to. When the link is tied to no Album, it has no known Album and only the report lists it.
- A Comment on a photo whose file is not in the export is an orphan of that Album.
- A Comment on an Album with no imported photo is an orphan too. It has no text to join, so only the report lists it.

A root entry with `liked: true` has no name to show, so an orphan one is kept as a Comment whose text is `❤️`.

### Which file is imported

- **Edited photo:** an edited file has no sidecar of its own. It sits next to its original, as `IMG-modifié.JPG` (`IMG-edited.JPG` in English), or `IMG-modifié(1).JPG` for a repeated name. When any folder holds it for a `url`, it is imported instead of the original, under the sidecar `title`, so the NAS path is the same as for an unedited photo.
- **Motion Photo:** only `IMG.MP.jpg` has a sidecar. The `IMG.MP` and `IMG.MP~2` video parts have none, so they are never imported.
- Media files with no sidecar are not imported.

### Files missing from the export

Two different photos can share a name and a year folder while the export holds only one file for them: `IMG.JPG` belongs to the first sidecar, and `IMG(1).JPG` does not exist. The second photo has no file anywhere. It is not paired with `IMG.JPG`, which is another photo, and the report lists it under *Album photos with no file in the export*, as `<Album title>: <name>`.

### Export of selected Albums

An export of selected Albums has no year folders, and it brings the sidecars of some photos without their media. When no folder of sidecars sits outside the Albums and at least one Album photo has no file, `read_export` raises `SelectedAlbumsExportError`. The run stops before any write, and the CLI prints the titles of those Albums and asks for a full Takeout Export.

A full export always has year folders, so a few missing files never stop it, even when they are all the photos of a small Album. A ZIP left out of the folder is not refused: its photos show in the report as photos with no file.

## Photo Description

`description.py` builds the text. It is made of blocks separated by one blank line:

1. On the oldest photo of an Album, the Album text: its description, then one block with its Comments, its Likes line and its orphan Comments.
2. The Caption.
3. The Comments, then the Likes line.

```text
Chez mamie

Théo, 2016-08-09: Quel beau séjour
❤️ Zoé
2017-01-02: A Comment that matches no photo

Le sapin

Zoé, 2016-08-10: Joli !
Théo, 2016-08-11: Two lines,
kept as they are
❤️ Théo, Zoé
```

- A Comment is `<author>, <YYYY-MM-DD>: <text>`, with the date in UTC. A Comment with no author starts at its date.
- The Likes line is `❤️ <name>, <name>`.
- When more than one Album brings Comments or Likes to a photo, each of these blocks starts with a line holding the Album title, and Albums come in folder order. Album texts on one photo follow the same rule.
- The oldest photo is chosen by date taken, then by `url`, at every run, so the Album text moves when an older photo joins the Album.

## Files sent to the NAS

`MediaPreparer` gives the exact bytes sent for a photo. The file keeps what it holds, and only what it lacks is written:

- `DateTimeOriginal` from the date taken, when the file has none. A date made of zeros or spaces counts as none. The value is in UTC: EXIF has no time zone here, and Synology Photos shows it as it is.
- `GPSLatitude`, `GPSLongitude` and their references from the position, when the file has no position. `GPSAltitude` and its reference follow when the altitude is not 0.

Only the EXIF group counts: a date or position in XMP stays as it is, and the EXIF one is still written. When a file lacks nothing, its bytes are sent untouched. No text is ever written into a file: Photo Descriptions go through the API. The year folder of the NAS path always comes from `photoTakenTime`, never from the file.

- **Formats.** JPEG and PNG, recognised by their content, because Takeout has JPEGs named `.png`. Videos follow the rules below. GIFs and any other file are sent untouched.
- **ExifTool.** It rewrites the metadata and leaves the image data as it is. One `exiftool -stay_open` process serves the whole run, through PyExifTool. Without ExifTool, `g2s` stops before any upload and says how to install it.
- **Failure.** A file ExifTool cannot read or write is sent untouched, and the report lists it under *Files sent without their missing date or position*.

### Videos

A file is a video when its extension says so: ffprobe would take a HEIC photo for an HEVC video. ffprobe then tells by content whether Synology Photos can play it, because Takeout has WMV files named `.avi`.

- **Converted:** the AVI, ASF (WMV) and MPEG formats, and HEVC, MPEG-1 and MPEG-2 video in any format.
- **Sent untouched:** every other video, H.264 MP4 and MOV among them.

A conversion gives an MP4 with H.264 video (CRF 20, 8-bit 4:2:0, even dimensions) and AAC audio, in place of the original, which stays in the ZIPs. The date taken goes into `creation_time`, in UTC, and replaces any date in the original. No text is written.

- **ffmpeg.** `ffmpeg` and `ffprobe` must be on the `PATH`. Without them, `g2s` stops before any upload and says how to install them.
- **Failure.** A video that ffprobe cannot read or ffmpeg cannot convert is not uploaded: sent as it is, later runs would find it on the NAS and never convert it. The report lists its ZIP member under *Videos that failed to convert, not uploaded*, and the run goes on. It is in no Album, its own Comments and Likes are not written, and the text of its Album goes to the next oldest photo. A later run tries it again.

## NAS path rule

A photo is stored at:

```
Photos/Google Photos/<year taken>/<original name>__<6 chars>.<ext>
```

- The 6 chars are the first 6 characters of the lowercase base32 encoding of the SHA-256 of the photo's `url`.
- The characters `\ / : * ? " < > |` and control characters in the name are replaced with `_`.
- A converted video keeps its original name and takes the extension `.mp4`.

The rule is deterministic: the same photo gets the same path in every export.

The **identity** of a photo on the NAS is its path without the extension, so a converted video is found without probing or converting it again.

## Order of a run

1. Read the export, and the previous export if there is one.
2. Take a snapshot of the NAS Library.
3. Prepare and upload every photo whose identity the snapshot lacks. An upload to a path that is already taken keeps the file there and returns its id. Replace and move the files that changed since the previous export (see [Files that changed](#files-that-changed)).
4. Pair the Albums, create those with no pair, give the others their Google Photos title, and add the photos each one lacks.
5. Set each Photo Description that differs from the text on the NAS. An empty text clears what is there.
6. Each write is read back right after it is made. A write that does not stick is listed in the report under *Writes that did not stick*.
7. The CLI prints the report and writes it to `report.md` in the folder that holds the export folder (`takeout/report.md` for `takeout/2024-01-01/`).

Progress goes to the standard error, one line per step, as `<step>: <number>/<total>`.

### Running again

A run keeps no state file. It writes only what the snapshot shows as missing, so a second run on the same export makes no write, and a run stopped at any point continues from any computer. When the connection is lost, the CLI says to run `g2s` again, and no report is written.

The snapshot holds every item under `Photos/Google Photos/`, and every normal Album made only of those items, with its items. An Album holding any other photo is the Household's own: a run never pairs, renames or grows it. The only exception is a photo that moves, whose new item takes the place of the old one there. An empty Album counts as made of NAS Library photos.

Each Album of the export is paired one to one with a NAS Album. The pair sharing the most photos goes first, and the same title settles a tie. An Album left over takes an empty NAS Album of its title, which is what a run stopped between creating and filling an Album leaves. An Album with no pair is created. A run only ever adds photos to a NAS Album, apart from the old item of a moved photo.

The report counts the photos found under *Already on the NAS*. Its lists cover the current run: a file sent without its date in an earlier run is not listed again. A failed conversion is tried again at each run.

### Refresh

A Refresh is a run on a newer Takeout Export, and it follows the same steps. The NAS Library ends as the export says, whatever was changed in Google Photos or on the NAS:

- **Album title.** A paired Album whose name differs from the Google Photos title is renamed. This follows a rename in Google Photos and undoes a rename on the NAS. Pairing goes by photos, so two Albums with the same title stay separate.
- **Album content.** New Albums are created and new photos join their Album. A photo removed from an Album in Google Photos stays in the NAS Album.
- **Deleted in Google Photos.** An Album or a photo missing from the export stays on the NAS, with its Photo Description. Pairing goes by shared photos only, so an Album of the export with no better pair takes over a NAS Album it shares a photo with, and renames it: this happens to the NAS Album of a deleted Album, and to the old Album when an Album is split in Google Photos.
- **Text.** A Photo Description that differs from the export is written again, which also covers a changed Caption, new Comments and Likes, deleted Comments and edits made on the NAS.
- **Deleted on the NAS.** A photo is sent again, joins its Albums and gets its text. An Album is recreated.
- **Files.** A file that changed is replaced or moved (see [Files that changed](#files-that-changed)).

The report counts *Albums renamed*, and *Photo Descriptions rewritten* apart from *Photo Descriptions written*: a Description is rewritten when the NAS held another text, and written when it held none. *Comments written* and *Likes written* count all those in the texts written, not only the new ones. A rename is read back from the list of Albums. A rename that does not stick goes under *Writes that did not stick*.

### Files that changed

A file on the NAS cannot be compared with the export: ExifTool adds the date, conversion changes everything, and Synology Photos writes the Photo Description back into JPGs. A Refresh therefore compares the export with the previous one, photo by photo, by `url`.

**Which previous export.** `--previous` gives it. By default it is the newest folder next to the export that holds ZIPs and is named `YYYY-MM-DD`, with a name that sorts before the export's. With no previous export, nothing is overwritten and nothing is removed: a photo whose date changed is uploaded at its new path, next to the old item.

**Replaced.** A photo whose chosen file changed (size or CRC in the ZIP, which also covers a new `-modifié` file) or whose date changed inside its year is prepared again and overwritten at its path. The date counts because it is written into the files that lack one. The overwrite clears the Photo Description, so the text step writes it again. Only these videos are converted again. If the overwrite gives the item a new id, the new item joins every Album of the old one.

**Moved.** A photo whose identity differs from the one in the previous export (the year of `photoTakenTime`, or its name) is uploaded at its new path. The new item then joins every NAS Album holding the old one, the Household's own Albums and those Google Photos took it out of included, and the old item is removed last. The old item stays if the new one could not join an Album, and that Album goes under *Writes that did not stick*. A changed video that no longer needs converting has a new extension, so it follows the same steps. A stop there leaves two items of one identity, and the snapshot keeps both, so the run started again finishes the job.

**Failure.** A changed video that fails to convert leaves the old file on the NAS, in its Albums and with its text.

**Running again.** A move is found from the NAS: the old item is gone, or the move goes on from where it stopped. A replacement cannot be seen on the NAS, so a run started again on the same pair of exports replaces the same files again, converts the same videos again and rewrites their Photo Descriptions. The Library ends the same. The next Refresh compares with this export, so these files are then unchanged. For the same reason, a change is only seen between the two exports compared: a Refresh that stopped has to be finished before the next export is imported.

The report counts *Files replaced* and *Files moved*.

## Synology Photos client

`SynologyPhotos` speaks NAS paths and item ids:

- `upload(path, data) -> id`, `overwrite(path, data) -> id`, `folder_items(folder) -> {path: id}` (subfolders included), `item_at(path) -> id | None`, `delete_item(id)`;
- `set_description(id, text)`, `description(id)`;
- `create_album(name) -> id`, `rename_album(album_id, name)`, `add_to_album(album_id, item_ids)`, `albums()`, `album_items(album_id)`.

Album names are not unique, so Albums are only found by id. Writes on unknown items answer success and do nothing, so the import reads every write back. Writes on an unknown Album raise `SynologyError`.

The real client, its API calls and the behaviour measured on the DS923 are described in [Synology Photos API](synology-photos-api.md).

## Login

`g2s import` logs in before it starts; `g2s login` asks everything again.

- The first run asks for the NAS address, the NAS Account user name and its password, plus a 2FA code when 2FA is on.
- The NAS address, the user name and a certificate the user trusted go to `settings.json` in the user config folder (`platformdirs.user_config_path("g2s")`).
- The password and the device token go to the OS keyring (service `g2s`). Nothing secret is written to a file.
- DSM always needs the password. The device token only spares the 2FA code, so later runs need the password from the keyring.
- A kept password that the NAS refuses is removed from the keyring, so the next run asks for it again. A failed `g2s login` leaves what was kept untouched.
- An unreachable NAS, or a certificate that no longer matches the pinned one, stops `g2s` with a message instead of a traceback.
- When the system does not trust the NAS certificate (a self-signed DSM certificate on a LAN address), the first run shows its SHA-256 fingerprint and asks the user to trust it. A trusted certificate is pinned: later runs accept that certificate only, and do not check the host name.

## Tests

Tests run the import use case, or the `g2s` CLI, on synthetic data only:

- `tests/takeout_builder.py` builds a synthetic Takeout Export with French names, in one or several ZIPs: Album folders with `métadonnées.json`, Album folders of sidecars only, year folders, sidecars, repeated names with their `(1)` index, `-modifié` files, Motion Photos, and photos with no file. Its media are real 1x1 JPEGs that hold a date by default, like a camera file, and the date and position in the file and in the sidecar can be set for each photo.
- `tests/test_file_metadata.py` runs ExifTool for real on tiny JPEGs and PNGs, and reads the sent files back with Pillow, so that the check does not depend on the tool that writes.
- `tests/test_video_conversion.py` runs ffmpeg for real on tiny videos, and reads the sent files back with ffprobe and ExifTool.
- `tests/test_resumable_runs.py` runs imports again on the same fake NAS, and stops a run at every possible write.
- `tests/test_refresh.py` chains runs on an older and a newer export, with changes made on the fake NAS in between.
- `tests/test_refresh_files.py` chains runs with a previous export: edits, changed videos and fixed dates.
- `tests/fake_synology.py` is an in-memory fake Synology Photos, true to the behaviour measured on the DS923 by default. Setting `descriptions_stick = False` or `album_names_stick = False` makes description writes or Album renames silently not stick, and `overwrite_keeps_id = False` gives an overwritten item a new id, out of its Albums. The DS923 keeps the id: that setting checks that the import does not rely on it. `writes` counts the write calls, and `writes_left` cuts the connection after that many.
- `tests/test_contract.py` is the contract of the client. It runs against the fake always, and against the DS923 with `G2S_CONTRACT=1` (see [Synology Photos API](synology-photos-api.md)).
- `tests/test_login.py` runs the login with an in-memory keyring and a fake NAS.

Tests assert on what the Household would see in the fake (paths, Albums, Photo Descriptions) and on the report.
