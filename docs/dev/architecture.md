# Architecture

`g2s import <export folder>` reads a Takeout Export from its ZIPs and builds the NAS Library in Synology Photos. Vocabulary: `CONTEXT.md` at the repository root.

## Modules

All code lives in `src/google_to_synology_photos/`.

| Module | Role |
|---|---|
| `cli.py` | The `g2s` command: `g2s login` and `g2s import <export folder>`. Connects to the NAS, runs the import, prints the report and writes `report.md`. |
| `login.py` | Login to the NAS as the NAS Account: what is asked, and what is kept where. |
| `dsm.py` | Transport to the DSM Web API: login, calls, multipart uploads, TLS. |
| `synology_client.py` | The real Synology Photos client, over the `SYNO.Foto.*` Web API. |
| `importer.py` | The import use case, `run_import(export_dir, nas) -> Report`. The only entry the CLI calls, and the test seam. |
| `takeout.py` | Takeout reader. Reads every ZIP of the export in place, picks the file of each photo, and returns the photos by `url`, the Albums with their Comments and Likes, and the orphan Comments. Refuses an export of selected Albums. |
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
- Google writes a non-breaking space in `Google Photos` and in `Photos de <year>`.

### Comments and Likes

Comments and Likes sit in `sharedAlbumComments` lists. Each entry has `creationTime`, and either `text` or `liked: true`. The lists are not always in date order, so the reader sorts them, oldest first.

- **On a photo:** in its sidecar inside an Album folder, with `contentOwnerName`. Each Album has its own list, and the sidecars of year folders have none, so the reader keeps them per Album.
- **On an Album:** in its `métadonnées.json`, with `contentOwnerName`. The same file may hold a `description`.
- **Root file:** `commentaires_albums_partagés.json` (`shared_album_comments.json` in English), at the root of `Google Photos`. Its entries have no `contentOwnerName`. They have a `contentUrl`, the share link of their Album.

Most root entries repeat an entry of a sidecar or of a `métadonnées.json`, with the same text and timestamp. This repetition ties a share link to its Album, since nothing else in the export does. A root entry that repeats nothing is an **orphan Comment**:

- When its share link is tied to an Album, it joins the orphan Comments of that Album.
- Otherwise it has no known Album.

A root entry with `liked: true` has no name to show, so an orphan one is kept as a Comment whose text is `❤️`.

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

### Which file is imported

- **Edited photo:** an edited file has no sidecar of its own. It sits next to its original, as `IMG-modifié.JPG` (`IMG-edited.JPG` in English), or `IMG-modifié(1).JPG` for a repeated name. When any folder holds it for a `url`, it is imported instead of the original, under the sidecar `title`, so the NAS path is the same as for an unedited photo.
- **Motion Photo:** only `IMG.MP.jpg` has a sidecar. The `IMG.MP` and `IMG.MP~2` video parts have none, so they are never imported.
- Media files with no sidecar are not imported.

### Files missing from the export

Two different photos can share a name and a year folder while the export holds only one file for them: `IMG.JPG` belongs to the first sidecar, and `IMG(1).JPG` does not exist. The second photo has no file anywhere. It is not paired with `IMG.JPG`, which is another photo, and the report lists it under *Album photos with no file in the export*, as `<Album title>: <name>`.

### Export of selected Albums

An export of selected Albums has no year folders, and it brings the sidecars of some photos without their media. When no folder of sidecars sits outside the Albums and at least one Album photo has no file, `read_export` raises `SelectedAlbumsExportError`. The run stops before any write, and the CLI prints the titles of those Albums and asks for a full Takeout Export.

A full export always has year folders, so a few missing files never stop it, even when they are all the photos of a small Album. A ZIP left out of the folder is not refused: its photos show in the report as photos with no file.

## NAS path rule

A photo is stored at:

```
Photos/Google Photos/<year taken>/<original name>__<6 chars>.<ext>
```

- The 6 chars are the first 6 characters of the lowercase base32 encoding of the SHA-256 of the photo's `url`.
- The characters `\ / : * ? " < > |` and control characters in the name are replaced with `_`.

The rule is deterministic: the same photo gets the same path in every export.

## Order of a run

1. Read the export.
2. Upload every photo at its path. An upload to a path that is already taken keeps the file there and returns its id.
3. Create every Album with its Google title and add its photos.
4. Set each Photo Description that differs from the text on the NAS. An empty text clears what is there.
5. Each write is read back right after it is made. A write that does not stick is listed in the report under *Writes that did not stick*.
6. The CLI prints the report and writes it to `report.md` in the folder that holds the export folder (`takeout/report.md` for `takeout/2024-01-01/`).

## Synology Photos client

`SynologyPhotos` speaks NAS paths and item ids:

- `upload(path, data) -> id`, `overwrite(path, data) -> id`, `item_at(path) -> id | None`, `delete_item(id)`;
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

- `tests/takeout_builder.py` builds a synthetic Takeout Export with French names, in one or several ZIPs: Album folders with `métadonnées.json`, Album folders of sidecars only, year folders, sidecars, repeated names with their `(1)` index, `-modifié` files, Motion Photos, and photos with no file.
- `tests/fake_synology.py` is an in-memory fake Synology Photos, true to the behaviour measured on the DS923. Setting `descriptions_stick = False` makes description writes silently not stick.
- `tests/test_contract.py` is the contract of the client. It runs against the fake always, and against the DS923 with `G2S_CONTRACT=1` (see [Synology Photos API](synology-photos-api.md)).
- `tests/test_login.py` runs the login with an in-memory keyring and a fake NAS.

Tests assert on what the Household would see in the fake (paths, Albums, Photo Descriptions) and on the report.
