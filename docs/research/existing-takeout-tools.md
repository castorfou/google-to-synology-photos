# Existing tools for Takeout Export to NAS Library

Research for issue #5 ("Which tools already exist for Takeout to NAS?").
Sources were read on 2026-10-15. Repository facts (licence, language, last
release) come from the GitHub API for each repository. Claims marked
**(uncertain)** were not verified in source code.

## Question

Which existing tools turn a Google Photos Takeout Export into an organised
library? For each: what it handles (Album structure, Captions written into
EXIF/XMP, dates and GPS from JSON, JSON-to-file matching including truncated
names and `-edited` files, duplicates, re-runs / incremental Refresh), what it
misses (Comments, Likes), licence, language, maintenance and whether it can run
in Docker on a Synology DS923+. Can we reuse one instead of building from
scratch?

## Short answer

- No tool covers the whole job. **None of them keeps Comments or Likes**, and
  **none is built for a Refresh** that merges a new Takeout Export into an
  existing NAS Library without duplicates.
- **GPTH Neo** (the maintained fork of Google Photos Takeout Helper) is the
  best "fix the files" step: it matches JSON to media (truncated names,
  `-edited`, numbered duplicates, `supplemental-metadata.json`, non-English
  exports), writes dates, GPS and Captions into the files with ExifTool,
  removes duplicates by content hash and can emit Album membership as JSON.
  It is a Dart CLI with a static Linux x64 binary, usable as a subprocess step.
- **immich-go** is the best choice **if the target becomes Immich**: it
  uploads straight from the Takeout ZIPs, creates Albums, sets Captions as
  Immich descriptions, and skips files the server already has (so re-runs
  are safe). It does not write metadata into files.
- **PhotoMigrator** is the only tool found that talks to **Synology Photos**
  (unofficial `SYNO.Foto.*` web API) and wraps GPTH for the Takeout step. It
  can create Albums in Synology Photos, but does not set Album descriptions,
  Comments or Likes there **(uncertain: from a grep of its Synology client)**.
- What is left for us: Comments and Likes (read from the Album
  `metadata.json` files), Album descriptions, the Refresh logic (identity of
  an item across exports, "add only, never remove"), and pushing Albums and
  descriptions into Synology Photos.

## Comparison table

| Tool | Language / licence | Last release | Albums | Caption into file | Dates + GPS from JSON | Truncated / `-edited` matching | Duplicates | Re-run / Refresh | Comments / Likes | Docker on DS923+ |
|---|---|---|---|---|---|---|---|---|---|---|
| GPTH original (TheLastGimbus) | Dart, Apache-2.0 | v3.4.3, 2023-09-24 | Folders / symlinks | No | Date as file mtime only (reads EXIF, writes none); no GPS | Yes, basic | Hash-based | No | No | No image; static binary |
| GPTH Neo (Xentraxx) | Dart, Apache-2.0 | v6.4.0, 2026-09-23 | Symlink, copy, or `albums-info.json` | Yes, EXIF `ImageDescription` | Yes, via ExifTool | Yes, extensive | Content hash | Resume only; not a merge | No | No image; static Linux x64/arm64 binary |
| immich-go (simulot) | Go, AGPL-3.0 | v0.32.0, 2026-06-25 | Creates Immich Albums | No (sets Immich description) | Yes (sent to Immich) | Yes | Server-side check | Yes, skips existing assets | No | Static binary; no Docker needed |
| google-photos-migrate (garzj) | TypeScript, MIT | v2.12.3, 2026-02-02 | Album folders | Yes, `Description`, `Caption-Abstract`, `ImageDescription` | Yes, via ExifTool | Partial | Moved to own folder | No (`--force` overwrites) | No | Dockerfile, build it yourself |
| google-photos-exif (mattwilson1024) | TypeScript, MIT | No releases; last push 2024-05-06 | No | No **(uncertain)** | Date only | Partial | No | No | No | No |
| PhotoMigrator (jaimetur) | Python, GPL-3.0 | v4.7.0, 2026-09-19 | Folders + uploads Albums to Synology / Immich | Through GPTH | Through GPTH | Through GPTH | Through GPTH, plus server-side cleanup | Not described | No | Yes, Docker CLI and web images |
| ExifTool recipes (m1rkwood and forum threads) | Shell + ExifTool | Not versioned (last push 2024-04-29) | Manual | Possible with extra tags | Yes | Manual rename scripts | No | No | No | ExifTool runs anywhere |

## Tools in detail

### Google Photos Takeout Helper (original, TheLastGimbus)

- Repository: <https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper>.
  Dart, Apache-2.0, about 5,950 stars. Last release v3.4.3 on 2023-09-24,
  last push 2025-01-29 (GitHub API).
- Purpose, in its own words: "organizes the Google Takeout archive into one
  big chronological folder"; it sets "`file last modified` correctly" and
  suggests running ExifTool afterwards to copy that date into
  `DateTimeOriginal` ([README](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper#how-to-use)).
- The README mentions Synology only for the non-interactive mode
  ("if you want to run it on Synology … look at Running manually with cmd").
- No release for three years. The maintained work continues in the Neo fork
  below. Not a good base on its own.

### GPTH Neo (Xentraxx/GooglePhotosTakeoutHelper, now `GooglePhotosTakeoutHelper_Neo`)

- Repository: <https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo>
  (the old `Xentraxx/GooglePhotosTakeoutHelper` URL redirects there).
  Dart, Apache-2.0. Releases are frequent: v6.2.0, v6.2.1, v6.3.0 (August
  2026), v6.4.0 (2026-09-23). Release assets include
  `gpth_neo-6.4.0-release-linux-x64.bin` and a linux-arm64 build
  ([releases](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo/releases)).
- **Albums**: six modes (`shortcut`, `reverse-shortcut`, `duplicate-copy`,
  `json`, `nothing`, `ignore`). The `json` mode writes one `ALL_PHOTOS`
  folder plus `albums-info.json` listing the Albums each file belongs to,
  which is the easiest output for a program to consume. `ignore` deletes
  Album-only files and must be avoided
  ([README, Album Handling Options](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo#album-handling-options)).
- **Captions**: read from the JSON `description` field and written to EXIF
  `ImageDescription`. JPEGs use a built-in writer; other formats need
  ExifTool. The README says "`XMP-dc:Description` is implemented but
  currently not written"
  ([README, Caption/Description Metadata Writing](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo#captiondescription-metadata-writing)).
- **Dates and GPS**: from JSON first, then EXIF, file name patterns, and the
  "Photos from YYYY" folder. Written with ExifTool for all formats, JPEG only
  without it ([README, Date Extraction](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo#-date-extraction)).
- **JSON matching**:
  [`json_metadata_matcher_service.dart`](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo/blob/master/lib/common/services/json_metadata_services/json_metadata_matcher_service.dart)
  tries strategies "from least to most aggressive": exact name,
  `.supplemental-metadata.json`, names truncated to 51 characters, bracket
  swap (`IMG(1).jpg` vs `IMG.jpg(1).json`), numbered forms, `-edited`
  removal, and cross-extension matches. Heuristic matches are flagged
  `isOwnSidecar == false` and their date and GPS are dropped, so an edited
  copy does not take GPS from another photo. Non-English `-edited` suffixes
  and folder names are listed in `lib/common/constants/constants.dart`.
- **Duplicates**: "Removes identical files using content hashing";
  `--keep-duplicates` moves them to `_Duplicates` instead.
  `--skip-extras` drops `-edited` versions.
- **Re-runs**: "Auto-Resume" restarts an interrupted run from
  `progress.json` in the output folder. The README does not describe merging
  a second Takeout Export into an existing output **(uncertain: no such
  option found)**. By default GPTH **moves** files out of the input
  (`--keep-input` works on a copy).
- **Not handled**: Comments, Likes, Album descriptions. A search of `lib/`
  for `favorit`, `sharedAlbumComments` and Album `description` found nothing.
- **Docker**: no Dockerfile in the repository. The static Linux x64 binary
  plus ExifTool can run in any small container or over SSH on DSM.
- **Reuse**: as a CLI step, called with `--albums json --keep-input`. Not a
  library: it is a Dart program, not a Python package.

### immich-go (simulot)

- Repository: <https://github.com/simulot/immich-go>. Go, AGPL-3.0, about
  7,000 stars. Last release v0.32.0 on 2026-06-25. The README says
  "Compatible with Immich V2 and V3" and "No NodeJS or Docker required"
  ([README](https://github.com/simulot/immich-go#readme)).
- **Input**: reads Takeout ZIPs directly
  (`immich-go upload from-google-photos … /path/to/takeout-*.zip`).
- **Albums**: `--sync-albums` (default true) creates Immich Albums;
  `--include-untitled-albums`, `--from-album-name`, `--partner-shared-album`
  ([docs/commands/upload.md](https://github.com/simulot/immich-go/blob/main/docs/commands/upload.md)).
  The Album description comes from the `enrichments` of the Album JSON
  (narrative text and location names), not from a top-level `description`
  field ([`googlephotos.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/googlephotos.go),
  [`json.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/json.go)).
- **Captions, dates, GPS, favourites, people**: parsed from the photo JSON
  (`description`, `photoTakenTime`, `geoData`, `favorited`, `people`) and
  sent to Immich as asset metadata. People names become tags
  (`--people-tag`). Files themselves are not rewritten.
- **JSON matching**:
  [`matchers.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/matchers.go)
  handles `supplemental-metadata` (also truncated), names cut at 46
  characters, numbered duplicates `(1)`, and edited names in several
  languages (`-modifié`, …).
- **Duplicates and re-runs**: the server is checked before upload, so
  "Interrupted uploads can be safely restarted" and "Same photos from
  different sources handled gracefully"
  ([docs/technical.md, Duplicate Detection](https://github.com/simulot/immich-go/blob/main/docs/technical.md#duplicate-detection)).
  This is the only tool that supports a Refresh out of the box, and only
  with Immich as the target.
- **`archive from-google-photos --write-to-folder`** writes a
  `YYYY/YYYY-MM/` tree with an immich-go `.JSON` sidecar per file
  ([docs/commands/archive.md](https://github.com/simulot/immich-go/blob/main/docs/commands/archive.md)).
  The metadata is not embedded in the files, so Synology Photos would not
  read it. If a file name already exists, the writer adds `~1`, `~2`, …
  ([`writeFolder.go`](https://github.com/simulot/immich-go/blob/main/adapters/folder/writeFolder.go)),
  so re-running into the same folder appears to create copies
  **(uncertain: not tested)**.
- **Not handled**: Comments and Likes. The Album JSON in its own test data
  contains `sharedAlbumComments` entries with `contentOwnerName` and
  `"liked": true` ([`json_test.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/json_test.go)),
  but the parser struct has no field for them, so they are ignored.
- **Docker on DS923+**: not needed; a single Linux amd64 binary. Immich
  itself would run in Container Manager.

### google-photos-migrate (garzj)

- Repository: <https://github.com/garzj/google-photos-migrate>. TypeScript
  (Node 18+), MIT. Last release v2.12.3 on 2026-02-02.
- `full` mode keeps the Album folder structure; `flat` ignores Albums.
  Failed files go to an `error` folder; duplicates are moved to their own
  folder; file names are recovered from the JSON `title`; wrong extensions
  are fixed ([README](https://github.com/garzj/google-photos-migrate#project-info)).
- **Captions**: writes the JSON `description` into `Description`,
  `Caption-Abstract` and `ImageDescription`; also dates and GPS, through
  `exiftool-vendored`
  ([`apply-meta-file.ts`](https://github.com/garzj/google-photos-migrate/blob/master/src/meta/apply-meta-file.ts)).
  Writing `Description` gives XMP `dc:description`, which GPTH Neo does not
  write.
- **Matching**: indexes all JSON by `title`, then tries `name.ext.json`,
  `(n)` counters, `-edited` suffixes in 10 languages
  ([`find-meta-file.ts`](https://github.com/garzj/google-photos-migrate/blob/master/src/meta/find-meta-file.ts),
  [`langs.ts`](https://github.com/garzj/google-photos-migrate/blob/master/src/config/langs.ts)).
  No explicit truncation rule; the `title` index covers some truncated cases
  **(uncertain)**.
- **Re-runs**: refuses non-empty output unless `--force`, which overwrites.
  No Refresh.
- **Docker**: a Dockerfile is provided; "no pre-built images are provided".

### google-photos-exif (mattwilson1024)

- Repository: <https://github.com/mattwilson1024/google-photos-exif>.
  TypeScript, MIT, last push 2024-05-06, no GitHub releases.
- Scope: "populate missing `DateTimeOriginal` EXIF metadata … using Google's
  JSON metadata" (repository description). google-photos-migrate reuses its
  matching code. Superseded; listed only for completeness.

### PhotoMigrator (jaimetur)

- Repository: <https://github.com/jaimetur/PhotoMigrator>. Python, GPL-3.0.
  Last release v4.7.0 on 2026-09-19. The GPTH Neo README lists it as a
  related project that "uses GPTH 6.x.x".
- **Google Takeout Fixing**: runs GPTH, then organises (Year/Month folders,
  symlinked Albums, Album renaming, duplicate removal)
  ([help/04-google-takeout.md](https://github.com/jaimetur/PhotoMigrator/blob/main/help/04-google-takeout.md)).
- **Synology Photos**: logs in with a user name and password (with OTP for
  2FA) and can upload Albums, upload everything, download, merge or remove
  duplicate Albums, and remove duplicate assets
  ([help/07-synology-photos.md](https://github.com/jaimetur/PhotoMigrator/blob/main/help/07-synology-photos.md)).
  The client
  ([`ClassSynologyPhotos.py`](https://github.com/jaimetur/PhotoMigrator/blob/main/src/Features/SynologyPhotos/ClassSynologyPhotos.py))
  calls the undocumented DSM web API: `SYNO.API.Auth`,
  `SYNO.Foto.Upload.Item`, `SYNO.Foto.Browse.Album`,
  `SYNO.Foto.Browse.NormalAlbum`, `SYNO.Foto.Browse.Item`,
  `SYNO.FotoTeam.Browse.Item`. Its duplicate detection on Synology is "by
  exact filename and file size".
- The client never mentions `description` or `comment`, so it does not set
  Album descriptions, Comments or Likes **(uncertain: based on a grep, not a
  full read)**.
- **Docker**: ships `docker-cli/` and `docker-web/` (Compose) images that
  run on any architecture.
- **Reuse**: its Synology client is the best existing map of the Synology
  Photos web API. Being GPL-3.0, copying its code would make our project
  GPL; running it as a separate tool or reading it as documentation does not.

### ExifTool recipes

- [m1rkwood/google-photos-takeout-scripts](https://github.com/m1rkwood/google-photos-takeout-scripts)
  (no licence, last push 2024-04-29) shows the classic command:
  `exiftool -r -d %s -tagsfromfile "%d/%F.json" "-DateTimeOriginal<PhotoTakenTimeTimestamp" --ext json -overwrite_original <dir>`,
  run a second time with `%f.json` for files whose JSON drops the extension.
- The same guide fixes `-edited` files by copying the original's JSON and
  fixes truncated names by renaming to 46 characters, both by hand.
- The ExifTool forum has many threads on this, for example
  [msg=80927](https://exiftool.org/forum/index.php?msg=80927),
  [msg=69653](https://exiftool.org/forum/index.php?msg=69653) (Takeout puts
  the `(1)` in the wrong place in JSON names). The forum was not reachable
  during this research, so these threads were not reread.
- Takeaway: ExifTool is the right writer, but the matching must be done by a
  program. All serious tools above wrap ExifTool.

### Synology-specific scripts

- A GitHub search for "google takeout synology" returned no repositories.
  Apart from PhotoMigrator, no maintained Takeout-to-Synology-Photos tool was
  found.

## Running on the DS923+

- The DS923+ uses an AMD Ryzen R1600 (2 cores, 4 threads, x86-64), 4 GB RAM
  as shipped, up to 32 GB
  ([Synology datasheet](https://cndl.synology.cn/download/Document/Hardware/DataSheet/DiskStation/23-year/DS923%2B/chs/Synology_DS923%2B_Data_Sheet_chs.pdf)).
- All the tools above have Linux x86-64 builds (GPTH Neo, immich-go) or run
  in a container (google-photos-migrate, PhotoMigrator). Container Manager is
  the DSM Docker package; that it is offered for the DS923+ was not
  confirmed on Synology's site during this research **(uncertain, but it is
  generally available on x86 "plus" models)**.
- GPTH Neo has `--limit-filesize` for low-RAM systems; 4 GB may be tight for
  very large exports **(uncertain)**.

## What the Takeout Export holds that no tool uses

From the immich-go test data (a sample of a real Album JSON):

```json
"sharedAlbumComments": [{
  "creationTime": {"timestamp": "1596183682", "formatted": "Jul 31, 2020, 8:21:22 AM UTC"},
  "contentOwnerName": "My_Name_On_GP",
  "liked": true
}]
```

So the Album `metadata.json` carries Comments and Likes with their
Contributor name and time. Every tool reviewed drops them.

## Conclusion: reuse or build?

Reuse one tool as a **step**, build the rest.

1. **Fix-the-files step: reuse GPTH Neo** (Apache-2.0, active, static binary)
   with `--albums json --keep-input`. It gives dated files with GPS and
   Captions in EXIF, duplicates removed, and `albums-info.json`.
   google-photos-migrate is the fallback; it also writes XMP
   `dc:description`.
2. **If the target is Immich: reuse immich-go** for upload, Albums, Captions
   and safe re-runs. Only Comments and Likes would remain to build.
3. **If the target is Synology Photos, we must build:**
   - reading Album `metadata.json` for Album titles, descriptions,
     Comments, Likes and Contributors, and storing them (sidecar, Caption
     appendix, or the Synology Photos API, to be decided in another ticket);
   - the **Refresh**: a stable identity for an item across two exports
     (content hash, or JSON `url`/`title` + `photoTakenTime`), "add only,
     never delete", and adding new photos to existing Albums;
   - writing Captions also to XMP `dc:description` if Synology Photos reads
     that rather than EXIF `ImageDescription` (open question, see the
     Synology Photos metadata ticket);
   - creating Albums and setting their descriptions in Synology Photos,
     using PhotoMigrator's client as a guide to the unofficial
     `SYNO.Foto.*` API (without copying GPL code).

## Open questions for later tickets

- Which fields does Synology Photos import from EXIF/XMP (Caption, GPS,
  keywords)? This decides whether GPTH Neo's `ImageDescription` is enough.
- Where does Takeout put an Album's own description in `metadata.json`
  (top-level `description` or `enrichments`)? immich-go uses only
  `enrichments`.
- How stable are file names and JSON between two Takeout Exports of the same
  account? This decides the Refresh key.
