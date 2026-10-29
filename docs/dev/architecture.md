# Architecture

`g2s import <export folder>` reads a Takeout Export from its ZIPs and builds the NAS Library in Synology Photos. Vocabulary: `CONTEXT.md` at the repository root.

## Modules

All code lives in `src/google_to_synology_photos/`.

| Module | Role |
|---|---|
| `cli.py` | The `g2s` command. Parses arguments, connects to the NAS, runs the import, prints the report and writes `report.md`. |
| `importer.py` | The import use case, `run_import(export_dir, nas) -> Report`. The only entry the CLI calls, and the test seam. |
| `takeout.py` | Takeout reader. Reads every ZIP of the export in place and returns the photos by `url` and the Albums. |
| `paths.py` | NAS path rule. |
| `description.py` | Photo Description builder. Pure. |
| `synology.py` | `SynologyPhotos`, the interface of the Synology Photos client. |
| `report.py` | Counts and lists collected during a run, rendered as Markdown. |

## Reading a Takeout Export

- Album folders are the folders holding a `métadonnées.json` (or `metadata.json`); its `title` is the Album title.
- Each media file has a sidecar `<file name>.supplemental-metadata.json`. A sidecar whose media file is absent is skipped.
- A photo is identified by its sidecar `url`. The same photo appears in its Album folders and in its year folder (`Photos de 2013`); it is read once.
- Only photos that belong to at least one Album are imported.
- The date taken is the sidecar `photoTakenTime.timestamp`, in UTC. The Caption is the sidecar `description`.
- Google writes a non-breaking space in `Google Photos` and in `Photos de <year>`.

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
4. Set each Photo Description (the Caption).
5. Each write is read back right after it is made. A write that does not stick is listed in the report under *Writes that did not stick*.
6. The CLI prints the report and writes it to `report.md` in the folder that holds the export folder (`takeout/report.md` for `takeout/2024-01-01/`).

## Synology Photos client

`SynologyPhotos` speaks NAS paths and item ids:

- `upload(path, data) -> id`, `item_at(path) -> id | None`;
- `set_description(id, text)`, `description(id)`;
- `create_album(name) -> id`, `add_to_album(album_id, item_ids)`, `album_items(album_id)`.

Album names are not unique, so Albums are only found by id. Writes answer success even when nothing changed, so the import reads every write back.

`g2s import` has no NAS client and stops with a message before touching the NAS.

## Tests

Tests run the import use case, or the `g2s` CLI, on synthetic data only:

- `tests/takeout_builder.py` builds a synthetic Takeout Export ZIP with French names: Album folders with `métadonnées.json`, year folders, sidecars.
- `tests/fake_synology.py` is an in-memory fake Synology Photos. It returns ids at upload, keeps the existing file on an upload to a taken path, accepts duplicate Album names, and answers success on unknown ids without doing anything. Setting `descriptions_stick = False` makes description writes silently not stick.

Tests assert on what the Household would see in the fake (paths, Albums, Photo Descriptions) and on the report.
