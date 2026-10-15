# What a Google Photos Takeout Export contains

Research for issue #2. Checked on 2026-10-15.

Question: which content and metadata a Google Takeout Export of Google Photos
contains, what is missing, which bugs are known, and whether another official
route exists to get Comments and Likes.

Confidence labels used below:

- **Confirmed**: stated by Google, or visible in a real export file or in the
  source code of a maintained parser.
- **Reported**: seen by several users in GitHub issues, not stated by Google.
- **Uncertain**: a single report, or an inference. Check it on our own Takeout
  Export.

## Summary

| Item | In the Takeout Export? | Where | Confidence |
|---|---|---|---|
| Original photos and videos (own uploads) | Yes | media files in year and Album folders | Confirmed |
| Edited versions | Yes, next to the original | `<name>-edited.<ext>` (suffix translated) | Confirmed |
| Caption (owner's text) | Yes | `description` in the photo sidecar JSON | Confirmed |
| Comment on a photo in a shared Album | Yes | `sharedAlbumComments[]` in the photo sidecar of the Album folder | Confirmed |
| Comment on a shared Album | Yes | `sharedAlbumComments[]` in the Album `metadata.json` | Confirmed |
| Like on a photo | Yes | `sharedAlbumComments[]` entry with `"liked": true` and no `text` | Confirmed (one sample) |
| Author and date of a Comment or Like | Display name and timestamp only | `contentOwnerName`, `creationTime` | Confirmed |
| Album title | Yes | Album folder name and `title` in `metadata.json` | Confirmed |
| Album description | Yes | `description` in `metadata.json`; text blocks in `enrichments` | Confirmed (field); Uncertain (mapping) |
| Photos added by other Contributors to an Album | **No**, unless saved to the Household Account's library | | Reported |
| Albums shared with the account by others | **No** | | Reported |
| Date taken, upload date | Yes | `photoTakenTime`, `creationTime` (Unix seconds, UTC) | Confirmed |
| GPS | Yes | `geoData`, `geoDataExif` (0.0 when absent) | Confirmed |
| People names (face groups the user named) | Yes | `people[].name` | Confirmed |
| Favourite, archived, trashed | Yes | `favorited`, `archived`, `trashed` | Confirmed |
| Origin (phone, web, partner, shared Album) | Yes | `googlePhotosOrigin` | Confirmed |
| Picasa Web comments, tags, +1s | **No** (dropped in 2016) | | Confirmed |
| Comments or Likes through an API | **No** official API | | Confirmed |

## 1. Layout of the export

**Confirmed** from a real export attached to
[immich-go issue #434](https://github.com/simulot/immich-go/issues/434)
(`takeout-20240814T150101Z-001.zip`), from export paths in
[immich-go issue #932](https://github.com/simulot/immich-go/issues/932), and from the
parsers listed in section 8:

```
takeout-<date>T<time>Z-001.zip, -002.zip, ...
└── Takeout/
    ├── archive_browser.html
    └── Google Photos/                 # folder name is translated, e.g. "Google Снимки"
        ├── Photos from 2025/          # one folder per year
        │   ├── PXL_..._003831326.MP.jpg
        │   └── PXL_..._003831326.MP.jpg.supplemental-met.json
        ├── <Album title>/             # one folder per Album
        │   ├── metadata.json          # Album metadata, name is translated
        │   ├── IMG_1234.jpg
        │   ├── IMG_1234-edited.jpg
        │   └── IMG_1234.jpg.supplemental-metadata.json
        ├── Untitled(15)/              # Albums without title, name translated
        ├── Archive/, Trash/, ...      # special folders
        └── print-subscriptions.json, shared_album_comments.json, user-generated-memory-titles.json, ...
```

- A photo in an Album appears in the Album folder **and** in its `Photos from YYYY`
  folder, each with its own sidecar JSON. Exporting both gives duplicates
  ([Picasa resources](https://sites.google.com/site/picasaresources/google-photos-1/how-to-download-all-autobackupped-pictures);
  [GPTH Neo README](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo/blob/master/README.md)).
- Some files exist **only** in an Album folder. GPTH Neo warns that its
  `ignore` mode deletes these "album-only" files
  ([GPTH Neo README](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo/blob/master/README.md)).
- Google gives no Album ID. An Album is a folder. Folder name and `title` can
  differ. Two Albums can have the same title. immich-go uses the folder name
  when `title` is empty
  ([immich-go `googlephotos.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/googlephotos.go)).
- A big export is split into many ZIP files. A media file and its sidecar JSON
  can be in different ZIPs
  ([immich-go issue #1453](https://github.com/simulot/immich-go/issues/1453)).
- Root-level JSON files (`print-subscriptions.json`,
  `shared_album_comments.json`, `user-generated-memory-titles.json`) exist but are
  not documented. Parsers skip them
  ([timelinize `takeoutarchive.go`](https://github.com/timelinize/timelinize/blob/main/datasources/googlephotos/takeoutarchive.go);
  [potluck `photos.py`](https://github.com/DoubleGremlin181/potluck/blob/main/src/potluck/ingest/sources/photos.py)).
  In one real sample, `shared_album_comments.json` repeats the Comments without
  saying which photo they belong to. The per-photo sidecars are the useful source
  ([immich-go issue #434](https://github.com/simulot/immich-go/issues/434)).
  **Uncertain** whether this holds for all exports.

## 2. Photo sidecar JSON

Google states: "Any additional metadata that isn't from the original file, like
comments within Google Photos, ... are downloaded to a secondary JSON file"
([Google Account Help, Download your data](https://support.google.com/accounts/answer/3024190)).
Google does not document the fields.

The fields below come from a real export
([immich-go issue #434](https://github.com/simulot/immich-go/issues/434)) and from the
structs in the immich-go, timelinize and takeout-rater parsers. Names of people
are replaced by placeholders.

```json
{
  "title": "IMG_1234.jpg",
  "description": "",
  "imageViews": "13",
  "creationTime":   { "timestamp": "1723494028", "formatted": "Aug 12, 2024, 8:20:28 PM UTC" },
  "photoTakenTime": { "timestamp": "1721062427", "formatted": "Jul 15, 2024, 4:53:47 PM UTC" },
  "photoLastModifiedTime": { "timestamp": "...", "formatted": "..." },
  "geoData":     { "latitude": 0.0, "longitude": 0.0, "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0 },
  "geoDataExif": { "latitude": 0.0, "longitude": 0.0, "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0 },
  "people": [ { "name": "<person>" } ],
  "url": "https://photos.google.com/photo/AF1Qip...",
  "favorited": true,
  "archived": true,
  "trashed": true,
  "sharedAlbumComments": [
    { "text": "Nice record", "creationTime": { "timestamp": "1723629473", "formatted": "..." }, "contentOwnerName": "<Contributor>" },
    { "creationTime": { "timestamp": "1723630522", "formatted": "..." }, "contentOwnerName": "<Contributor>", "liked": true }
  ],
  "googlePhotosOrigin": {
    "mobileUpload": { "deviceFolder": { "localFolderName": "" }, "deviceType": "ANDROID_PHONE" }
  },
  "appSource": { "androidPackageName": "..." }
}
```

What each field means for us:

- `title`: the **original file name**. Use it to rebuild names that Takeout
  truncated (see section 4).
- `description`: the **Caption**. Empty string when there is none.
- `photoTakenTime.timestamp`: date taken, in Unix seconds, UTC. `creationTime`
  is the upload time. The `formatted` string is translated, so do not parse it.
  timelinize notes these times can be wrong by hours or days and prefers the
  EXIF date
  ([timelinize `takeoutarchive.go`](https://github.com/timelinize/timelinize/blob/main/datasources/googlephotos/takeoutarchive.go)).
- `geoData` / `geoDataExif`: always present, with `0.0` when there is no
  location. takeout-rater measured `geoDataExif` in about 51 % of sidecars
  ([takeout-rater design](https://github.com/FelixDombek/takeout-rater/blob/main/docs/design.md)).
  immich-go uses `geoDataExif` first, then `geoData`. **Uncertain**: the common
  belief is that `geoData` holds a location edited in Google Photos and
  `geoDataExif` holds the camera value. No primary source says so.
- `people[].name`: names the user gave to face groups.
- `googlePhotosOrigin`: the first key tells where the item came from:
  `mobileUpload`, `webUpload`, `driveSync`, `fromPartnerSharing`,
  `fromSharedAlbum`, `composition`
  ([takeout-rater design](https://github.com/FelixDombek/takeout-rater/blob/main/docs/design.md)).
- `sharedAlbumComments`: Comments and Likes. See section 5.
- The Takeout Export does **not** write Captions, dates or GPS into the media
  file. They stay in the JSON. The file system date is the download date
  ([Google Account Help](https://support.google.com/accounts/answer/3024190);
  [Picasa resources](https://sites.google.com/site/picasaresources/google-photos-1/how-to-download-all-autobackupped-pictures)).

## 3. Album `metadata.json`

One `metadata.json` per Album folder. The file name is translated, for example
`метаданни.json` for a Bulgarian account
([immich-go issue #791](https://github.com/simulot/immich-go/issues/791)). Real
sample from [immich-go issue #434](https://github.com/simulot/immich-go/issues/434):

```json
{
  "title": "Testing Album",
  "description": "",
  "access": "",
  "date": { "timestamp": "0", "formatted": "Jan 1, 1970, 12:00:00 AM UTC" },
  "sharedAlbumComments": [
    { "text": "What is the meaning of life?", "creationTime": { "timestamp": "1723489439", "formatted": "..." }, "contentOwnerName": "<Contributor>" }
  ]
}
```

Other fields seen in parsers: `geoData` (timelinize), `enrichments` with
`narrativeEnrichment.text` and `locationEnrichment.location[]` (text and place
blocks added inside an Album; immich-go uses them as the Album description).
Some files are wrapped in an `albumData` object
([immich-go `json.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/json.go)).

- `title` can be empty or the file can be `{}`. immich-go then uses the folder
  name. Do not detect the file by name. Detect it by content: a JSON without
  `photoTakenTime` and with a `title` is an Album
  ([immich-go issue #791](https://github.com/simulot/immich-go/issues/791)).
- `date` was `0` (1970) in the sample. Do not trust it.
- `access`: meaning not documented. **Uncertain.**
- The only sign that an Album is shared is the presence of
  `sharedAlbumComments`. Migris uses that key as its only marker and says so
  ([Migris `albums.rs`](https://github.com/coderhisham/Migris/blob/main/crates/providers/google-photos/src/albums.rs)).
  A shared Album with no Comment may look like a private one. **Uncertain.**

## 4. File names: truncation, `(N)`, edited versions

None of this is documented by Google. All rules come from parser code.

- **Sidecar name**: `<media name>.supplemental-metadata.json`. Older exports
  (2024 sample) used `<media name>.json`.
- **Truncation**: the sidecar name (without `.json` and `(N)`) is cut at
  **46 characters**, so the suffix becomes `.supplemental-met.json`, `.sup.json`,
  `..json`, or the media extension itself is cut. potluck measured 46 on 208
  real truncated names
  ([potluck `photos.py`](https://github.com/DoubleGremlin181/potluck/blob/main/src/potluck/ingest/sources/photos.py));
  immich-go uses 46 characters
  ([immich-go `matchers.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/matchers.go));
  timelinize uses 47 characters without the extension for the **media** name
  ([timelinize `takeoutarchive.go`](https://github.com/timelinize/timelinize/blob/main/datasources/googlephotos/takeoutarchive.go)).
  Long media names are also truncated, as the 2024 sample shows
  (`1721062427198-e4bf178b-d904-4571-b597-63cd4f5a9.jpg`, full `title` ends in
  `...63cd4f5a928d.jpg`). Matching rule used by potluck: the sidecar stem must be a
  prefix of `<media>.supplemental-metadata` in the same folder; the longest
  match wins.
- **Same name twice** in a folder: media `IMG_1234(1).jpg`, sidecar
  `IMG_1234.jpg.supplemental-metadata(1).json` (old form `IMG_1234.jpg(1).json`).
  The `(N)` moves.
- **Characters**: timelinize replaces `&` and `?` by `_` when it rebuilds names.
- **Edited versions**: `<name>-edited.<ext>`, next to the original, without its
  own sidecar. The suffix is **translated**: `-modifié` (French),
  `-bearbeitet`, `-bewerkt`, `-modificato`, `-editado`, `-編集済み` and more
  ([GPTH Neo `extra_formats.dart`](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo/blob/master/lib/common/constants/extra_formats.dart)).
  Other generated variants: `-effects`, `-motion`, `-animation`, `-smile`,
  `-collage`, `-mix`.
- **Motion photos / Live Photos**: a still image plus a video
  (`.MP.jpg` + `.MP`/`.MP4`, or `.HEIC` + `.MOV`). Matching the video to the
  sidecar fails in some cases
  ([immich-go issue #1321](https://github.com/simulot/immich-go/issues/1321)).
- **Videos** are exported as files with their sidecar. A `Failed Videos` folder
  can exist; immich-go skips it
  ([immich-go `googlephotos.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/googlephotos.go)).

## 5. Comments and Likes

**Confirmed** from the real export in
[immich-go issue #434](https://github.com/simulot/immich-go/issues/434), produced on
purpose by two users (Album owner and the immich-go maintainer):

- **Comment on an Album** → `sharedAlbumComments[]` in the Album `metadata.json`.
- **Comment on a photo** → `sharedAlbumComments[]` in that photo's sidecar,
  **in the Album folder only**. The comment belongs to the photo inside that
  Album, not to the photo in general. The year-folder copy may not have it.
- **Like** → an entry with `"liked": true`, no `text`, plus `contentOwnerName` and
  `creationTime`. The sample shows Likes on photos. **Uncertain**: whether Likes
  on the Album itself appear in `metadata.json`; the sample has none.
- Each entry has `text`, `creationTime` (Unix seconds) and
  `contentOwnerName`. There is **no e-mail and no user ID**, only a display name.
  Two people with the same display name cannot be told apart. A renamed
  account may appear under a new name.
- A user confirmed the same layout on an export of April 2026
  ([immich-go issue #434](https://github.com/simulot/immich-go/issues/434)).
- Google confirms only "comments within Google Photos" go into the JSON
  ([Google Account Help](https://support.google.com/accounts/answer/3024190)).
- **Uncertain**: in the sample, one Album Comment is exactly 60 characters and
  ends mid-sentence, while photo Comments of 90 characters are complete. Album
  Comments may be truncated at 60 characters. Check on our own export.
- **Missing**: Comments on Albums shared **with** the Household Account by
  others are not exported (see section 6).
- Google's direct transfer tool (not the ZIP export) lists "comments added to a
  photo" as **not transferred**
  ([Google Account Help, transfer to another service](https://support.google.com/accounts/answer/9666875)).
  This applies to that transfer only, not to the ZIP.

## 6. Photos from other Contributors

**Reported** (no Google statement found):

- In an Album owned by the Household Account, photos added by **other
  Contributors are not exported**. One user saw about 1 500 files in Takeout for an
  Album of 3 500+ photos; "Download all" from the web gave the full set
  ([immich-go discussion #71](https://github.com/simulot/immich-go/discussions/71)).
  Same statement in
  [Picasa resources](https://sites.google.com/site/picasaresources/google-photos-1/how-to-download-all-autobackupped-pictures).
- Albums shared **with** the account by others are not exported
  ([immich-go discussion #71](https://github.com/simulot/immich-go/discussions/71)).
- Workaround: in the shared Album, use the "save to library" cloud icon. Saved
  photos then appear in the export
  ([Illinois Tech guide](https://www.iit.edu/ots/google-microsoft-365/use-google-takeout-export-google-photos)).
  Their sidecar then has `googlePhotosOrigin.fromSharedAlbum`
  ([takeout-rater design](https://github.com/FelixDombek/takeout-rater/blob/main/docs/design.md)).
  **Uncertain**: whether a saved photo keeps the original Contributor's name and
  whether it then shows in the Album folder.
- "Download all" on the web gives files without sidecar JSON, so without Captions,
  Comments, and possibly without the Google dates
  ([immich-go discussion #71](https://github.com/simulot/immich-go/discussions/71)).
- Partner sharing: since end of 2024 only photos taken with the device are
  shared with the partner
  ([Picasa resources](https://sites.google.com/site/picasaresources/google-photos-1/how-to-download-all-autobackupped-pictures)).
  Partner items carry `googlePhotosOrigin.fromPartnerSharing`.

This is the largest gap for the NAS Library. It must be measured on our own
Household Account: count photos per Album in Google Photos vs. in the export.

## 7. Picasa Web albums

- Albums synced to Picasa Web Albums were moved into Google Photos as normal
  Albums. Captions moved. **Tags, Comments and +1s did not move**
  ([Picasa Help, "What's happening to Picasa?"](https://support.google.com/picasa/answer/6383491)).
- So Picasa-era Comments cannot be in any Takeout Export today. Picasa-era
  Captions should be in `description`. **Uncertain**: no source shows a Picasa-era
  sidecar.

## 8. Other known bugs

- **Orphan JSON**: a photo in several Albums is sometimes exported once, with only
  the sidecar in the other folders. Albums then look incomplete
  ([immich-go issue #1014](https://github.com/simulot/immich-go/issues/1014)).
- **Different bytes for the same photo**: the Album copy and the year copy of a
  photo had different sizes (2.1 MB vs 3.7 MB) in one log
  ([immich-go issue #932](https://github.com/simulot/immich-go/issues/932)).
  **Uncertain** cause; deduplicate by content hash, not by name.
- **Translated names**: the `Google Photos` folder, `metadata.json`, `Untitled`,
  `Photos from` and the `-edited` suffix all follow the account language.
- **Edited file ordering**: `-edited` files can be mistaken for duplicates or
  matched to the wrong sidecar
  ([immich-go issue #877](https://github.com/simulot/immich-go/issues/877),
  [#1011](https://github.com/simulot/immich-go/issues/1011),
  [#1419](https://github.com/simulot/immich-go/issues/1419),
  [#1422](https://github.com/simulot/immich-go/issues/1422)).
- **Items being deleted** and changes made after the request are not in the
  archive ([Google Account Help](https://support.google.com/accounts/answer/3024190)).

## 9. Other official routes for Comments and Likes

None gives Comments or Likes.

- **Google Photos Library API**: since **31 March 2025** the scopes
  `photoslibrary.readonly`, `photoslibrary.sharing` and `photoslibrary` are
  removed. "You can now only list, search, and retrieve albums and media items
  that were created by your app." Shared-album methods return
  `403 PERMISSION_DENIED`
  ([Library API updates](https://developers.google.com/photos/support/updates)).
  Even before, the `MediaItem` resource had `description` and `contributorInfo`
  (Contributor name) but **no Comments or Likes**
  ([MediaItem reference](https://developers.google.com/photos/library/reference/rest/v1/mediaItems)).
- **Google Photos Picker API**: the user picks items; each item has `id`,
  `createTime`, file name, MIME type, width, height and camera data. **No Caption, no
  Album, no Comments**
  ([Picker mediaItems reference](https://developers.google.com/photos/picker/reference/rest/v1/mediaItems)).
- **Data Portability API**: no Google Photos resource group. The only scope with
  "photos" in its name is `dataportability.maps.photos_videos` (photos posted on
  Maps)
  ([Data Portability scopes](https://developers.google.com/data-portability/user-guide/scopes)).
- **Takeout scheduled export**: when Google Photos is the only product
  selected, Takeout can "schedule automatic exports for new and updated data",
  every 2 months for one year. Not available with Advanced Protection
  ([Google Account Help](https://support.google.com/accounts/answer/3024190)).
  Useful for Refresh. **Uncertain**: whether "new and updated" means a full or a
  partial archive.

So the Takeout Export is the only official source of Comments and Likes.

## 10. Consequences for the project

- Parse sidecars by content and with prefix matching, never by exact name.
- Read Comments and Likes from the **Album folder** copies, not the year folders.
- Store the Contributor as a display name only; there is no stable ID.
- Deduplicate media by content hash across year and Album folders and across
  ZIPs.
- Plan a separate step for photos of other Contributors (save to library before
  each export, or download them another way), and measure the gap first.
- Handle translated folder and file names (the Household Account language).

## Open checks on our own Takeout Export

1. Count per Album: Google Photos vs. export, for one Album with several
   Contributors.
2. Is a Like on an Album exported? Are Album Comments truncated at 60 characters?
3. Are Captions from Picasa-era Albums in `description`?
4. Does a scheduled export contain the full library or only changes?
5. What does `access` in `metadata.json` contain for a shared Album?

## Sources

Google (primary):

- [Google Account Help: Download your data](https://support.google.com/accounts/answer/3024190)
- [Google Account Help: Transfer a copy of photos and videos to another service](https://support.google.com/accounts/answer/9666875)
- [Picasa Help: What's happening to Picasa?](https://support.google.com/picasa/answer/6383491)
- [Google Photos APIs: updates (31 March 2025 changes)](https://developers.google.com/photos/support/updates)
- [Library API: MediaItem](https://developers.google.com/photos/library/reference/rest/v1/mediaItems)
- [Picker API: mediaItems](https://developers.google.com/photos/picker/reference/rest/v1/mediaItems)
- [Data Portability API: scopes](https://developers.google.com/data-portability/user-guide/scopes)

Parser source code:

- [immich-go `json.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/json.go),
  [`matchers.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/matchers.go),
  [`googlephotos.go`](https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/googlephotos.go)
- [timelinize `takeoutarchive.go`](https://github.com/timelinize/timelinize/blob/main/datasources/googlephotos/takeoutarchive.go)
- [GooglePhotosTakeoutHelper Neo](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo)
- [potluck `photos.py`](https://github.com/DoubleGremlin181/potluck/blob/main/src/potluck/ingest/sources/photos.py)
- [takeout-rater design](https://github.com/FelixDombek/takeout-rater/blob/main/docs/design.md)
- [Migris `albums.rs`](https://github.com/coderhisham/Migris/blob/main/crates/providers/google-photos/src/albums.rs)

Issues and reports:

- immich-go [#434](https://github.com/simulot/immich-go/issues/434) (real export with Comments and Likes),
  [#791](https://github.com/simulot/immich-go/issues/791),
  [#932](https://github.com/simulot/immich-go/issues/932),
  [#1014](https://github.com/simulot/immich-go/issues/1014),
  [#1321](https://github.com/simulot/immich-go/issues/1321),
  [#1453](https://github.com/simulot/immich-go/issues/1453),
  [discussion #71](https://github.com/simulot/immich-go/discussions/71)
- [Picasa resources: download photos/videos](https://sites.google.com/site/picasaresources/google-photos-1/how-to-download-all-autobackupped-pictures) (community site)
- [Illinois Tech: Use Google Takeout to export Google Photos](https://www.iit.edu/ots/google-microsoft-365/use-google-takeout-export-google-photos)
