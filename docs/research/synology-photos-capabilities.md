# What can Synology Photos store and show?

Research for issue #3. Scope: a DS923+ on DSM 7.2+ running Synology Photos
1.9.x (latest release at the time of writing: 1.9.1-10928, 2026-07-07, which
requires DSM 7.2 or later [R1]). The question is which parts of a Takeout Export
(Captions, Comments, Likes, Album titles and descriptions, dates, GPS,
Contributors) Synology Photos can hold for the Household, and how the NAS
Library can be built and refreshed by a script.

Confidence markers used below:

- **Confirmed**: stated by a Synology primary source (Knowledge Center, release
  notes, product spec).
- **Source code**: read from a community API client; the API is not documented
  by Synology, so it can change with any package update.
- **Uncertain**: inferred, community report only, or not found. Needs a test on
  the NAS before we rely on it.

## Summary

| Takeout Export data | Synology Photos support | Confidence |
| --- | --- | --- |
| Caption on a photo | Yes, as the item **Description**. Read/written as Exif `ImageDescription`. Editable in the UI and searchable. | Confirmed |
| Caption on a video | Shown and editable inside Synology Photos only (database). Not read from, and not written to, the video file. | Confirmed |
| Comments | No comment feature at all. Photo Station's Shared Album comments were dropped. | Confirmed (absence) |
| Likes | No likes. Closest: per-photo **Rating** (0-5) and **Favorites** (1.9.0). | Confirmed (absence); favorite scope uncertain |
| Album title | Yes (manual "normal" albums and conditional albums). | Confirmed |
| Album description | No album-level description. Photo Station album descriptions were dropped. | Confirmed (dropped), no later re-add found |
| Date taken | Yes. Exif `DateTime`/`DateTimeOriginal`; IPTC and XMP dates read since 1.9.0. Falls back to modification time. | Confirmed |
| GPS | Yes for photos (Places album, map, reverse geocoding). Video location is not read from files. | Confirmed |
| Tags / keywords | Yes: **General tag** = XMP `Subject` / IPTC `Keywords`. | Confirmed |
| Photos from several people | Yes: an Album can mix items from several Personal Spaces and the Shared Space; shared-album "Provider" role lets others add. API exposes `provider_user_id` per item. | Confirmed (UI); `provider_user_id` display in UI uncertain |
| Programmatic import | No official Synology Photos API. The undocumented `SYNO.Foto.*` / `SYNO.FotoTeam.*` Web API can create albums, add items, set descriptions, tags, ratings, favorites, share albums and trigger re-index. | Source code |

Consequence for the design: Captions map cleanly onto Description (write it
into the file *and/or* set it via API). Comments, Likes and Album descriptions
have no native home and must be folded into something that exists (for example
appended to the photo Description, turned into General tags, or put into a
per-Album cover/README item). That choice belongs to a later ticket.

## 1. Metadata: Captions, dates, GPS, tags

The Knowledge Center article "What metadata standards does Synology Photos
support?" [K1] is the authoritative source. It says Synology Photos supports
XMP, Exif and IPTC, and gives this write/search table:

| Type | Edit | Search | XMP | Exif | IPTC |
| --- | --- | --- | --- | --- | --- |
| General tag | V | V | V | - | V |
| Description | V | V | - | V | - |
| Rating | V | - | V | V | - |
| Photo rotation | V | - | - | V | - |
| Date taken | V | V | V | V | V |

Notes from the same article [K1]:

- "**Description** equals the **ImageDescription** tag in the Exif standard."
- "**General tag** equals the **Subject** tag in the XMP standard and the
  **Keywords** tag in the IPTC standard. If both values exist, the value of
  Subject will take effect and be applied to both standards."
- Rating maps to Exif `Image.Rating`/`Image.RatingPercent` and XMP `Rating`,
  `RatingPercent`, `MicrosoftPhoto` tags.
- Date taken edits are written back to Exif `DateTime` and `DateTimeOriginal`.
- Writing edits back into the file is only supported for jpg, jpeg, jpe, png
  and cr2. For heic, cr3 and x3f, General tag, Description and Rating "can only
  be edited within the package" (kept in the Synology Photos database).
- **Cannot be read** by Synology Photos: General tag, Description and Rating of
  cr3/x3f photos, and "the General tag, Description, Rating, and Location of
  videos".
- "Synology Photos does not support writing General tag, Description, Date
  taken, and Rating edits to the original video."

Release notes add:

- 1.7.0 (2024-08-26): "Supports reading and writing XMP and IPTC metadata"
  [R1].
- 1.9.0 (2026-04-21): "Supports using IPTC and XMP metadata to display the date
  taken" [R1].
- 1.9.1 (2026-07-07): fixed "photo descriptions might not be searchable or
  available as criteria in conditional albums" [R1]. So descriptions are a
  valid conditional-album criterion.

The help page "Manage Photos" [K2] confirms the Information panel lets users
"view and edit description, date and time, recognized faces", keyword search
covers "Tags, file names, description, people and objects, dates", and "If the
capture date and time cannot be found, the most recent modification time will
be used." GPS is shown through reverse geocoding with OpenStreetMap [K2], and
the Places auto album groups photos by capture location [K3].

**Uncertain:**

- Whether Description is also *read* from XMP `dc:description` or IPTC
  `Caption-Abstract` when Exif `ImageDescription` is empty. [K1] only names
  Exif `ImageDescription`; the 1.7.0 "reading XMP and IPTC" note does not say
  which fields. Safe choice: write the Caption to all three
  (`EXIF:ImageDescription`, `XMP-dc:Description`, `IPTC:Caption-Abstract`) and
  verify on the NAS with a test image.
- Character encoding of non-ASCII Captions in Exif `ImageDescription` (French
  accents). Needs a test.
- For videos and HEIC, a Caption can only live in the Synology Photos database,
  so it must be set via the UI or the Web API (section 5), and it would be lost
  on a database rebuild unless re-applied by the Refresh.

Side effect to keep in mind for the Refresh: editing Description, tags, rating
or date in Synology Photos on a jpg/png modifies the original file [K1]. A
Refresh that compares file checksums must expect that.

## 2. Comments and Likes

**Comments: not supported.** The Knowledge Center comparison article lists,
under features dropped when migrating from Photo Station: "Comments, color
labels, and area highlight tools in Shared Albums" [K4]. No Synology Photos
release note from 1.0.0 (2021) through 1.9.1 (2026-07) mentions a comment
feature [R1]. The help pages for sharing [K5] and albums [K3] describe no
comment function. The only free text attached to a photo is the Description.

**Likes: not supported.** Nothing in the help pages, spec or release notes
mentions likes or reactions. What exists instead:

- **Rating** (0-5 stars), since 1.1.0 [R1], stored in the file for jpg/png per
  [K1], filterable [K2].
- **Favorites**, since 1.9.0 web portal: "Supports marking photos as favorites
  and viewing them in the Favorites album" [R1]. The `SYNO.Foto.Favorite` list
  API and `set_item_favorite` exist in the N4S4 client [C1].
  **Uncertain:** whether a favorite is per user (like a Google Photos Like) or
  global per item. Needs a test with two accounts.

Photo Station (DSM 6) had comments [K4], but it is "not available on DSM 7.0"
[S2], so it is not an option on a DSM 7.2 NAS.

## 3. Albums

The "Manage Albums" help page [K3]:

- **Auto-created albums**: Recently Added, People, Subjects, Similar Items,
  Places, Tags, Videos.
- **Manually created albums** ("normal" albums): virtual collections; items are
  not duplicated ("Adds photos to multiple albums without duplicates" [S1]).
- **Conditional albums**: "Both existing and future items that match these
  conditions will be included" (folder source, file type, date taken, rating,
  and more). Using Shared Space as a source requires Full Access.
- When a user's Shared Space permission is downgraded, "any items they added
  from Shared Space to albums will be removed as well".
- "When uploading items to an album shared by others, the actual files will be
  saved in their home folder `/home/Photos/PhotoLibrary`."

**Album description:** none. Photo Station's "Descriptions, hit counts, and
watermarks of albums" are listed as dropped features [K4], with the note that
"some of the removed features may be redesigned and relaunched", but no release
note through 1.9.1 re-adds them [R1]. The `SYNO.Foto.Browse.NormalAlbum`
`create` call takes only `name` and `item` [C1][C2], and the only album
mutators seen in the clients are `set_name`, `add_item`, `delete` and
condition setters [C1][C2]. Album title is supported; album description is not.

**Several people in one Album:** albums can combine items from Personal Space
and Shared Space ("You can now add photos from both Personal Space and Shared
Space ... to the same album") [K6]. Shared Space albums "belong to their
creators" [K6]. Item listings can request `provider_user_id` [C1], so the
system tracks who added an item. **Uncertain:** whether the web UI shows that
Contributor next to the photo.

## 4. Personal Space, Shared Space, and sharing with the Household

From the help pages [K2][K7] and the Shared Space permission article [K8]:

| | Personal Space | Shared Space |
| --- | --- | --- |
| Folder on disk | `/home/Photos` of each user | shared folder `/photo` |
| Enabled by | DSM Control Panel > User & Group > Advanced > User Home | Synology Photos > Settings > Shared Space |
| Who sees it | only the owner | users granted Full Access, or Custom + per-folder roles |
| Timeline View | yes | "only available to users with Full Access permission" [K2] |
| Search/filters | yes | "Only users with Full Access permission can search and select filters from Shared Space" [K2] |
| People/Subjects auto albums | yes (if enabled) | Full Access only [K3][K8] |

Shared Space access levels [K8]: **Full Access** (administrator-like, can set
permissions, sees face/object albums) or **Custom** (sees only folders granted
individually). Folder roles for Custom users: Viewer, Downloader, Uploader,
Manager. Only Manager can "Edit dates, times, ratings, and tags", delete and
move [K5][K8]. Permissions can be set only on first- and second-level folders
under `/photo`; deeper folders inherit [K7]. Folder permissions set in File
Station are not applied to Synology Photos [K6][K7].

Album sharing [K5]: an album owner enables sharing, picks Public (link) or
Private, and adds DSM users or groups to an Invitee List with role **Viewer**
(view), **Downloader** (+ download) or **Provider** (+ add files, remove
self-added files). Conditional albums only offer Viewer and Downloader. Shared
albums appear for the recipient under Sharing > Shared With Me and, since
1.4.0, in the Albums tab [R1]. Non-admin users can share only if the admin
ticks "Allow non-admin users to share photos" [K7].

Implications for the NAS Library (not decisions, just constraints):

- Putting the NAS Library in Shared Space with Custom/Viewer for spouse and
  kids keeps it read-only for them, but they lose Timeline, search and filters
  in Shared Space. Albums shared to them still work.
- Giving the Household Full Access restores Timeline and search but also grants
  edit/delete rights everywhere in Shared Space.
- A Personal Space of one "library" account plus albums shared to each
  Household member is another layout; others cannot browse a different user's
  Personal Space directly (community report [S3], consistent with [K2]).

## 5. Web API (undocumented) and Python clients

Synology publishes no official Synology Photos API documentation (no official
developer guide was found; the community docs [C3] exist precisely because of
that). The web portal uses the DSM Web API (`/webapi/entry.cgi`) with two
families: `SYNO.Foto.*` for Personal Space and `SYNO.FotoTeam.*` for Shared
Space [C3]. Treat every endpoint below as **Source code** level: verified from
client code, not from Synology.

| Need | API / method | Where seen |
| --- | --- | --- |
| Log in | `SYNO.API.Auth` `login` | [C3] |
| Discover APIs and versions | `SYNO.API.Info` `query` | [C3][C2] |
| List folders | `SYNO.Foto.Browse.Folder` / `SYNO.FotoTeam.Browse.Folder` `list`, `get`, `count` | [C1][C3] |
| List items | `SYNO.Foto.Browse.Item` / `SYNO.FotoTeam.Browse.Item` `list` (with `additional` = `description`, `tag`, `exif`, `gps`, `provider_user_id`, ...) | [C1][C3] |
| Upload a file | `SYNO.Foto.Upload.Item` `upload` (Personal) / team equivalent | [C1] |
| Create album | `SYNO.Foto.Browse.NormalAlbum` `create` (`name`, `item` = JSON id list) | [C1][C2] |
| Add items to album | `SYNO.Foto.Browse.NormalAlbum` `add_item` (`id`, `item`) | [C2] |
| Rename / delete album | `SYNO.Foto.Browse.Album` `set_name` / `delete` | [C1] |
| Conditional album | `SYNO.Foto.Browse.ConditionAlbum` `create` / `set_condition` | [C1] |
| Set Description | `SYNO.Foto.Browse.Item` `set` with `description` | [C1] |
| Rating / favorite | `SYNO.Foto.Browse.Item` `set` (`rating`, favorite flag) | [C1] |
| Tags | `SYNO.Foto.Browse.GeneralTag` `create`/`get`; item `add_tag` exists | [C1][C3] |
| Share album to users | `SYNO.Foto.Sharing.Passphrase` `set_shared` then `update` with a permission list (`role`, `member` user/group) | [C1][C2] |
| Re-index | `SYNO.Foto.Index` / `SYNO.FotoTeam.Index` `reindex` (`type=basic`) | [S4]; status in [C1] |

Python clients:

- **N4S4/synology-api** (`synology_api.photos`, MIT, ~600 stars, actively
  maintained, `photos.py` last changed 2026-06-10) [C1]. Broadest coverage:
  albums, items, description, rating, favorite, tags, sharing, upload, index
  status. It has no "add items to existing album" helper, and it builds the
  `description` parameter by naive string quoting (`'"' + description + '"'`),
  so a Caption containing `"` or `\` should be JSON-encoded by the caller.
- **fortysix2ahead/synophotos** (CLI + library, MIT, small, last push
  2025-10) [C2]. Has `add_item` for albums and album sharing.
- **zeichensatz/SynologyPhotosAPI** (community Markdown docs, ~330 stars) [C3].
  Lists API names and a few documented methods; not a client.
- **python-photostation** targets the old Photo Station and is archived; not
  usable with Synology Photos.

Re-index can also be scripted on the NAS itself with
`synowebapi --exec api=SYNO.Foto.Index method=reindex version=1 runner=<user> type=basic`
(and `SYNO.FotoTeam.Index` for Shared Space) [S4] (community, 2021, updated
2023).

## 6. Indexing from files

- Files can be added through the web portal, the mobile app, or directly
  "via File Station on DSM or other file sharing protocols to upload files to
  `/home/Photos` folder (Personal Space) or `/photo` folder (Shared Space)"
  [K2]. Folder View mirrors the real folder hierarchy and operations are
  synchronised with File Station [K2][K6].
- Uploads in Timeline View go to `PhotoLibrary` and are sorted into
  auto-created date subfolders [K2].
- Manual re-index: "Account icon > Settings > Personal (Personal Space)/Shared
  Space > Indexing > click Re-index" [K2].
- Renaming the `Photos` folder breaks access; re-indexing is required after
  renaming it back [K2].
- Files whose extensions are listed in Settings > Global > File Extensions
  Exclusion are not uploaded or displayed [K2].
- Photo Request uploads lose original metadata [K5]; not a usable import path.
- 1.6.2 fixed "re-indexing Motion Photo might not be able to generate metadata"
  [R1], so re-index re-reads metadata from files.

**Uncertain (community reports only):**

- Automatic detection of new or changed files relies on file-system change
  notification: changes over SMB, File Station or rsync-like protocols are
  picked up, but writes that bypass DSM services (for example a Docker bind
  mount, or `mount --bind`) are not, and need a manual or scheduled re-index
  [S5][S3].
- Whether metadata edited externally in an already-indexed file (for example a
  Caption rewritten by the Refresh) is picked up automatically or only after a
  re-index. Must be tested; a scheduled re-index after each Refresh is the safe
  default.
- Whether a re-index preserves database-only data (Description on video/HEIC,
  album membership, favorites) for files that were rewritten. Must be tested.

## 7. Open questions to test on the DS923+

1. Write a jpg with only `XMP-dc:Description`, another with only
   `IPTC:Caption-Abstract`: does Synology Photos show either as Description?
2. Accented French Caption in Exif `ImageDescription`: displayed correctly?
3. Favorites: per user or shared between accounts?
4. Is the album Contributor (`provider_user_id`) visible in the UI?
5. Rewrite the Caption of an indexed jpg over SMB: updated without re-index?
6. After re-index, are API-set Descriptions on videos kept?

## Sources

Synology primary sources:

- [R1] Synology Photos release notes (all DSM 7 versions, 1.0.0 to 1.9.1),
  <https://www.synology.com/en-global/releaseNote/SynologyPhotos> (data read
  from `https://www.synology.com/api/releaseNote/findChangeLog?identify=SynologyPhotos&lang=en-us`).
- [K1] What metadata standards does Synology Photos support?,
  <https://kb.synology.com/en-global/DSM/tutorial/What_metadata_standards_does_Synology_Photos_support>
- [K2] Synology Photos help: Manage Photos,
  <https://kb.synology.com/en-global/DSM/help/SynologyPhotos/managing_photos?version=7>
- [K3] Synology Photos help: Manage Albums,
  <https://kb.synology.com/en-global/DSM/help/SynologyPhotos/managing_albums?version=7>
- [K4] Feature comparison between Synology Photos, Photo Station, and Synology
  Moments,
  <https://kb.synology.com/en-global/DSM/tutorial/What_are_the_differences_between_Photos_Photo_Station_Moments>
- [K5] Synology Photos help: Sharing,
  <https://kb.synology.com/en-global/DSM/help/SynologyPhotos/sharing?version=7>
- [K6] What functions have changed after Photo Station and Synology Moments
  upgraded to Synology Photos?,
  <https://kb.synology.com/en-global/DSM/tutorial/Frequently_asked_questions_about_Synology_Photos>
- [K7] Synology Photos help: overview,
  <https://kb.synology.com/en-global/DSM/help/SynologyPhotos/photos_desc?version=7>
- [K8] How do I set access permissions for Synology Photos Shared Space?,
  <https://kb.synology.com/en-global/DSM/tutorial/How_do_I_set_access_permissions_for_Synology_Photos_Shared_Space>
- [S1] Synology Photos software specifications (DSM 7.2),
  <https://www.synology.com/en-global/dsm/7.2/software_spec/synology_photos>
- [S2] Photo Station feature page ("not available on DSM 7.0"),
  <https://www.synology.com/en-global/dsm/feature/photo_station>

Community source code and docs (API is undocumented by Synology):

- [C1] N4S4/synology-api, `synology_api/photos.py`,
  <https://github.com/N4S4/synology-api/blob/master/synology_api/photos.py>
- [C2] fortysix2ahead/synophotos, `synophotos/photos.py` and
  `synophotos/parameters/photos.py`,
  <https://github.com/fortysix2ahead/synophotos>
- [C3] zeichensatz/SynologyPhotosAPI (unofficial API documentation),
  <https://github.com/zeichensatz/SynologyPhotosAPI>

Community reports (lower trust, used only where marked Uncertain):

- [S3] How to include photos from multiple Personal Spaces in the Synology
  Photos Timeline View (2025-06-08),
  <https://johnstonsoftwaresolutions.com/2025/06/08/how-to-include-photos-from-multiple-personal-spaces-in-the-synology-photos-timeline-view/>
- [S4] Automatically schedule a Photos re-index on your Synology NAS (2021,
  updated 2023),
  <https://davejansen.com/automatically-schedule-a-photos-re-index-on-your-synology-nas/>
- [S5] Syncthing forum: getting Synology Photos auto index working with
  Syncthing,
  <https://forum.syncthing.net/t/share-my-solution-to-get-synology-photos-auto-index-working-with-syncthing/21410>
