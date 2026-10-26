# Which Synology Photos API calls does the tool need?

Research for issue #12. Target: Synology Photos 1.9.x on DSM 7.4 (the
maintainer's NAS runs DSM 7.4.1-90080 Update 1 and Photos 1.9.1-10928).
This builds on `docs/research/synology-photos-capabilities.md` (branch
`research/synology-photos-capabilities`), which lists the API families. This
file gives the exact calls, parameters, limits and how stable each call looks.

Confidence labels:

- **Confirmed**: stated in a Synology document, or seen in a recorded real
  request and response on Synology Photos 1.9.1 [M1].
- **Reported**: read in the source code of a client library or in a
  community report, but not recorded on Photos 1.9.x.
- **Uncertain**: inferred, or no source found. Test on the NAS first.

The best primary source found is the capture file of
[cmeans/mcp-synology][M1]: real requests and replies recorded on
**DSM 7.2.2 + Synology Photos 1.9.1** (virtual DSM, 2026-10-17), with a
written spec of the quirks [M2]. It is a small project (about 12 stars), but
every claim in it has a recorded reply. It was not recorded on DSM 7.4, so
re-check the calls on the DS923+ once.

## Summary

| Need | Call (API, method, version) | Confidence | Used by |
| --- | --- | --- | --- |
| Log in | `SYNO.API.Auth` `login` v6 (`format=sid`, `enable_syno_token=yes`, 2FA via `otp_code` / `device_id`) | Confirmed [A1] | all clients |
| Folder from path | `SYNO.Foto.Browse.Folder` `get` v2 with `name="/rel/path"` | Confirmed (Personal) [M1]; Uncertain (Shared) | mcp-synology |
| Items of a folder | `SYNO.Foto.Browse.Item` `list` v1/v2 with `folder_id`, `offset`, `limit` | Confirmed [M1] | N4S4, synophotos, PhotoMigrator, npflood |
| Read an item | `SYNO.Foto.Browse.Item` `get` v2, `id=[..]`, `additional=["description",...]` | Confirmed [M1] | N4S4, synophotos, mcp-synology |
| Set Description | `SYNO.Foto.Browse.Item` `set` v2, `id=[..]`, `description="\"text\""` | Confirmed for photos [M1]; Uncertain for videos | N4S4 (since 2026-06), mcp-synology |
| Shared Space items | same calls with `SYNO.FotoTeam.Browse.*` | Confirmed [M1] | N4S4, mcp-synology, npflood |
| Create Album | `SYNO.Foto.Browse.NormalAlbum` `create` v1, `name`, `item=[..]` | Confirmed [M1] | N4S4, synophotos, PhotoMigrator, npflood |
| Find Album by name | `SYNO.Foto.Browse.Album` `list` v2 (paginate, filter by name in the tool) | Confirmed [M1] | all |
| Add items to Album | `SYNO.Foto.Browse.NormalAlbum` `add_item` v1, `id`, `item=[..]` | Confirmed [M1] | synophotos, PhotoMigrator, npflood |
| List Album items | `SYNO.Foto.Browse.Item` `list` with `album_id` | Confirmed [M1] | N4S4, synophotos, PhotoMigrator |
| Set Album cover | `SYNO.Foto.Browse.Album` `set_cover` v1, `id`, `id_item` (scalar) | Confirmed [M1] | mcp-synology only |
| Indexing status | `SYNO.Foto.Index` `get` v1 (pending counts per stage) | Confirmed [M1] | N4S4, mcp-synology, synology-butler |
| Trigger re-index | `SYNO.Foto.Index` `reindex` v1 (whole space) | Reported [S2][Y1][D1] | synology-native-photos, synology-butler |
| Upload with known id (option) | `SYNO.Foto.Upload.Item` `upload_to_folder` v1 | Confirmed [M1] | mcp-synology, N4S4, PhotoMigrator |

Three findings matter most for the design:

1. **There is no "get item by file path" call.** The tool finds the folder by
   its path (one call), then lists that folder's items and matches the
   `filename`. This works in both spaces.
2. **Albums exist only in the Personal Space API.** There is no
   `SYNO.FotoTeam.Browse.Album` or `NormalAlbum` (checked in the 2021 and
   1.9.1 API lists [Z1][Z2][M1]). An Album belongs to the logged-in user. How
   to put a Shared Space item into an Album through the API is not proven.
3. **Several writes answer "success" and do nothing**: unknown ids, or a
   Shared Space item the user has no right to edit [M2]. The tool must read
   back after each write.

## 0. Common rules for every call

- **URL**: `https://<nas>:5001/webapi/entry.cgi`. `SYNO.API.Info` (`query.cgi`)
  reports `path: entry.cgi` for every Photos API (Confirmed [S1][M1]).
- **Form POST**, with `api`, `method` and `version` **in the body**. A POST
  with them only in the query string and an empty body fails with error 101
  (Confirmed [M2]). GET also works, but puts descriptions and passwords in
  access logs [M2].
- **Every parameter value is JSON-encoded**, strings included:
  `name="\"My album\""`, `id="[30]"`. All `SYNO.Foto*` APIs report
  `requestFormat: JSON` (Confirmed [M1][Z1]). An unquoted value that looks
  like JSON is read as a number: a folder renamed `2024` gets a number
  (Reported [M2]); album names like `2025.09 Trip` sent without quotes fail
  with `120 name/type` (Reported [B1]). Use `json.dumps(value)` for every
  value. Do **not** copy N4S4's `'"' + text + '"'` (it breaks on `"` and `\`
  in a Caption) [N1].
- **Versions**: Photos 1.9.1 registers high versions (`Browse.Item` 1-7,
  `Browse.Album` 1-5, `NormalAlbum` 1-4, `Browse.Folder` 1-2, `Index` 1-1,
  `Upload.Item` 1-8) (Confirmed [M1]). The 1.9.1 web client itself uses lower
  versions; the versions in this file are the ones recorded working on 1.9.1.
  Do not send the max version blindly [M2].
- **Ids belong to a space.** Personal ids go to `SYNO.Foto.*`, Shared Space
  ids to `SYNO.FotoTeam.*`. A Shared Space id sent to `SYNO.Foto.Browse.Item
  get` returns an empty list, not an error (Confirmed [M1]
  `team_team-item-via-personal-api`). `owner_user_id: 0` means Shared Space.
- **Error codes seen**: 101 bad request, 103 no such method, 105 no
  permission, 106 session timeout, 119 invalid session, 120 bad parameter
  (`errors.name` says which) [A1][M1]; Photos-specific: 160 user has no
  Synology Photos privilege, 602 no Personal Space (user home off), 801 Shared
  Space off or not granted, 803 no permission on that Shared Space folder
  (Confirmed [M1][M2]).

## 1. Log in

**Call** (Confirmed, Synology's own guide [A1]):

```
POST /webapi/entry.cgi
api=SYNO.API.Auth  version=6  method=login
account=<user>  passwd=<password>
session=SynologyPhotos   (any name; N4S4 uses "webui")
format=sid               (session id returned in JSON; pass _sid=<sid> on each call)
enable_syno_token=yes    (returns "synotoken", the CSRF token)
```

Reply: `{"data": {"sid": "...", "did": "...", "synotoken": "..."}}`.
Logout: `method=logout`. Version 6 is "recommended" by Synology [A1]; N4S4
and PhotoMigrator also use v6/v7 [N2][P1].

- **Session use**: send `_sid=<sid>` (or the `id=<sid>` cookie) and the header
  `X-SYNO-TOKEN: <synotoken>` on every call (Reported [N2][P1]). The
  mcp-synology author saw DSM misread some sids passed as `_sid`, and moved to
  the `id` cookie (Reported [M2] open item 2). Use the cookie.
- **Session end**: error 106 (timeout) or 119 (invalid session) means log in
  again and retry once [A1][M2].
- **2FA** (Confirmed [A1]): if the account has 2FA, the first login answers
  403 ("2FA code required"); 404 means wrong code; 406 means 2FA is enforced
  but not set up. To avoid typing a code on every run: log in once with
  `otp_code=<code>&enable_device_token=yes&device_name=<name>`, store the
  returned `did`, then log in with `device_name=<name>&device_id=<did>` and no
  code. N4S4 implements exactly this [N2].
- **Dedicated user** (Recommended, Reported [S1][M2]): a normal (not admin)
  DSM user, for example `photos-import`, with:
  - the Synology Photos application privilege (else every call answers 160);
  - User Home enabled, if the Library is in its Personal Space (else 602);
  - for a Shared Space Library: Shared Space access and the **Manager** role
    on the target folder (or Full Access). With only view rights,
    `Browse.Item set` answers success and changes nothing (Confirmed [M2],
    recorded on 1.9.1).
  - Albums are owned by the user who creates them. If the dedicated user
    creates the Albums, they are that user's Albums and must be shared with
    the Household (see the capabilities research, section 4).

## 2. Find an indexed item from its file path

No API takes a file path and returns an item (Confirmed by absence: not in
the method lists [Z1][M1], and no client has one). The working recipe has two
steps.

**Step A: folder path to folder id** (Confirmed for Personal Space [M1]
`folder-get-by-name`):

```
api=SYNO.Foto.Browse.Folder  method=get  version=2  name="\"/2024/Trip to Rome\""
-> {"data": {"folder": {"id": 21, "name": "/2024/Trip to Rome", "parent": 3, ...}}}
```

The path is relative to the space root: `/` is `/homes/<user>/Photos` for
Personal Space and the `photo` shared folder for Shared Space [M2]. Root:
`get` with `id=0` (Personal root id varies; Shared root is id 1) [M1].

- Shared Space: `SYNO.FotoTeam.Browse.Folder get` v2 exists and answered with
  `id=0` (Confirmed [M1] `team_team-root`). `get` by `name` in Shared Space
  was not recorded: **Uncertain**, very likely the same.
- Fallback if `get` by `name` fails: walk the tree with `Browse.Folder list`
  (`id`, `offset`, `limit`) one level at a time and compare `name` (each
  folder's `name` is its full path, like `/2024/Trip to Rome`). This is what
  N4S4 `lookup_folder` and npflood do (Reported [N1][B1]). N4S4's
  `lookup_folder` had a typo in the API name until 2026-02 (commit `a0356a3`),
  so do not rely on it blindly.

**Step B: list the folder's items, match the file name** (Confirmed [M1]):

```
api=SYNO.Foto.Browse.Item  method=list  version=2
folder_id=21  offset=0  limit=500  sort_by="\"filename\""  sort_direction="\"asc\""
additional=["description"]
-> {"data": {"list": [{"id": 24, "filename": "IMG_0001.jpg", "filesize": 51305,
     "time": 1720121400, "indexed_time": 1792256687958, "folder_id": 21,
     "type": "photo", "additional": {"description": ""}}, ...]}}
```

- `offset` and `limit` are **required** (error 120 without them, Confirmed
  [M1]). Page until a page is shorter than `limit`. Total:
  `Browse.Item count` with `folder_id` [M1].
- The list holds only the folder's direct children, not sub-folders.
- `type` is `photo`, `video` or `live` [N3].
- Shared Space: `SYNO.FotoTeam.Browse.Item list` with the same parameters
  (Confirmed [M1] `team_team-item-list`).
- Not suitable: `SYNO.Foto.Search.Search list_item` matches filename
  *substrings* and tags, only after indexing (Confirmed [M1][M2]).
- Item ids are not stable forever: a file deleted and indexed again gets a new
  id (Confirmed on DSM 7.3.2 [S1]), and tag ids changed after a re-index on
  1.9.1 [M2]. Re-resolve ids by path on each run; do not keep them as the
  source of truth.
- Cost: one `Folder get` per Album folder plus one `Item list` per 500 items.
  With a cache per folder, a Library of tens of thousands of files needs only
  a few hundred calls.

## 3. Set an item's Description (photo and video)

**Call** (Confirmed on 1.9.1, photo [M1] `item-set-description`):

```
api=SYNO.Foto.Browse.Item  method=set  version=2
id=[30]  description="\"Sunset at the beach\""
-> {"success": true, "data": {"error_list": []}}
```

- Several ids in one call are accepted (`id=[30, 27]`). The web client sends
  at most 100 ids per call (`BATCH_UPDATE_SIZE`) (Reported [M2]). One Caption
  per item means in practice one call per item, unless several items share
  the same text.
- `description=""` clears it [N1].
- Other fields can go in the same `set` (`rating`) (Confirmed [M1]).
- Read back with `Browse.Item get` v2, `id=[..]`,
  `additional=["description"]` (Confirmed [M1] `item-get-after-edits`).
- **The write rewrites JPG files.** Photos writes the Description into the
  original file and re-indexes it, so its size and modification time change
  (Confirmed [M2]; matches the DS923+ test). The Refresh must not treat this
  as a new file.
- **Silent no-op**: for an unknown id, or a Shared Space item without Manager
  rights, the reply is still `success` with an empty `error_list`, and nothing
  changes (Confirmed [M2]). Always `get` the ids first, and read back after.
- Shared Space: `SYNO.FotoTeam.Browse.Item set` v2 (recorded with `rating`,
  Confirmed [M1] `team_team-item-set-rating`; with `description`, Reported by
  the same API).
- **Videos: Uncertain.** No source recorded `set description` on a video.
  Synology says video Descriptions are "edited within the package" and not
  written into the file [K1], and the web UI edits them through this same
  item API, so it very likely works. Test on the NAS: set a Description on an
  MP4 with this call, read it back, re-index, read it again.
- Non-ASCII text (French accents): `json.dumps` sends `é` escapes by
  default. DSM's JSON parser should accept them, but no capture shows it:
  **Uncertain**, test once (or send UTF-8 with `ensure_ascii=False`).
- Stability: N4S4 added `set_item_description` in 2026-06 (commit `d55fe40`,
  release v0.9.1, 2026-07-03) [N1]. `Browse.Item set` is in the 2021 API list
  of Photos 1.0 [Z1], so the method itself has existed since the first
  release.

## 4. Albums: create, find by name, add items, list items

All Album calls are **Personal Space APIs** (`SYNO.Foto.*`). Shared Space has
no Album API (Confirmed [Z2][M1]; npflood gets error 102 for
`SYNO.FotoTeam.Browse.Album` [B1]).

**Create** (Confirmed [M1] `album-create`):

```
api=SYNO.Foto.Browse.NormalAlbum  method=create  version=1
name="\"Trip to Rome\""  item=[30]
-> {"data": {"album": {"id": 9, "name": "Trip to Rome", "item_count": 1,
     "type": "normal", ...}}}
```

`item` can be empty (`[]`) (Reported [F1]; Confirmed [M1]
`album-create-duplicate-name`).

**Find by name** (Confirmed [M1] `album-list`): there is no lookup by name.
List all Albums and filter in the tool:

```
api=SYNO.Foto.Browse.Album  method=list  version=2
offset=0  limit=100  sort_by="\"create_time\""  sort_direction="\"desc\""
-> {"data": {"list": [{"id": 9, "name": "Trip to Rome", "type": "normal",
     "item_count": 2, "owner_user_id": 2, "shared": false, ...}]}}
```

- **Album names are not unique.** `create` with an existing name makes a
  second Album with the same name (Confirmed [M1]). So the tool must look up
  before it creates, and should remember the Album id it created (for example
  in its own state file), because a Household member can create an Album with
  the same name.
- Albums shared *with* the user need `category="normal_share_with_me"`
  (Reported [F1]).
- `Search.Search list_album` answers 103 on 1.9.1 (Confirmed [M2]).
- Page size: clients use 100 [N1][F1]; no maximum is documented.

**Add items** (Confirmed [M1] `album-add-item`):

```
api=SYNO.Foto.Browse.NormalAlbum  method=add_item  version=1
id=9  item=[27, 28, 29]
-> {"success": true, "data": {"error_list": []}}
```

- An unknown id in `item` is silently ignored with `success` (Confirmed [M1]:
  `[27, 999999]` returned success).
- Batch size: npflood sends 100 per call, PhotoMigrator 500 (Reported
  [B1][P1]); mcp-synology caps at 1,000 per call [M2]. Use 100.
- Adding an item already in the Album: no recorded error. PhotoMigrator treats
  a "duplicate/already" error as success (Reported [P1]).
- Remove: `NormalAlbum delete_item` v1, `id`, `item=[..]` (Confirmed [M1]).
- N4S4 has `create_normal_album` but no `add_item` helper [N1].

**List the Album's items** (Confirmed [M1] `item-list-album`):

```
api=SYNO.Foto.Browse.Item  method=list  version=1
album_id=9  offset=0  limit=100
```

N4S4 sends `id=<album_id>` with `version=7` instead (Reported [N1][N3]);
`album_id` is the recorded one. Count: `Browse.Item count` with `album_id`
(Reported [F2]).

**Shared Space items in an Album: Uncertain.** The web UI can add Shared
Space photos to an Album (Synology KB, in the capabilities research). In the
1.9.1 captures, Personal and Shared Space items share one id sequence
(Personal 24-30, Shared 32-34, Personal 36-37 [M1]), which suggests one item
table, so `add_item` with a Shared Space id may work. No source shows it.
**Test on the NAS** before choosing where the Library lives.

## 5. Set an Album cover

**Call** (Confirmed on 1.9.1 [M1] `album-set-cover`):

```
api=SYNO.Foto.Browse.Album  method=set_cover  version=1
id=9  id_item=27
-> {"success": true}
```

- `id_item` is a **single number**, not a list (unlike `Browse.Folder
  set_cover`, which takes a list) [M2].
- The item must be in the Album (assumed; mcp-synology checks the id first and
  refuses unknown ids [M2]). Read back with `Browse.Album get` v1,
  `id=[9]`, `additional=["thumbnail"]`: `thumbnail.unit_id` is the cover item
  (Confirmed [M1] `album-get`).
- Stability: `set_cover` is in the 2021 Photos 1.0 API list [Z1] and still
  works on 1.9.1. Only mcp-synology uses it; N4S4 and synophotos do not.
  Low risk, but not widely used.

## 6. Indexing of newly copied files

**Status** (Confirmed [M1] `index-get`, `index-get-after-upload`):

```
api=SYNO.Foto.Index  method=get  version=1
-> {"data": {"basic": 0, "metadata": 1, "metadata_updating": 3,
     "thumbnail": 6, "geo_coding": 2, "face_extraction": 0,
     "concept_detection": 0, "person_clustering": 0}}
```

Each number is the count of pending jobs for that stage, for the whole space
(Shared Space: `SYNO.FotoTeam.Index get`). There is no per-file status.

**When is one item indexed?** (Confirmed [M1][M2]):

- The item appears in `Browse.Item list` of its folder as soon as basic
  indexing is done. Before metadata indexing ends, `time` is the file mtime
  and `resolution` is 0x0; thumbnails say `converting`.
- Practical rule for the tool: poll every few seconds until (a) every
  expected file name is in the folder's `Item list`, and (b) `Index get`
  shows `basic == 0` and `metadata == 0` and `metadata_updating == 0`. Then
  set Descriptions. Waiting for thumbnails or faces is not needed.
- Setting a Description while metadata indexing still runs could be
  overwritten by the indexer reading the file (a date edit was undone this
  way on 1.9.1; ratings and descriptions were not) [M2]. Waiting for
  `metadata == 0` avoids the risk.
- Files copied over SMB/rsync are picked up by DSM's file change
  notification; writes that bypass DSM (Docker bind mounts) are not (earlier
  research, community reports).
- Also available: `SYNO.Foto.Browse.Diff get_version` / `get` gives changes
  since a version number (Reported [N1]); not needed for a first version.

**Trigger a re-index** (Reported):

```
api=SYNO.Foto.Index  method=reindex  version=1      (no parameters)
```

- Sent without parameters by synology-native-photos (on DSM 7.3.2) and
  synology-butler (Reported [S2][Y1]); with `type=basic` through
  `synowebapi` on the NAS (Reported [D1]). Method listed since Photos 1.0
  [Z1][Z2]. Shared Space: `SYNO.FotoTeam.Index reindex` (likely needs Shared
  Space Full Access or admin: **Uncertain**).
- It re-indexes the **whole space**; no per-folder re-index call was found
  (Uncertain). On a large Library it is slow, so use it only as a fallback
  when copied files do not show up.
- Re-index re-reads file metadata. Descriptions set through the UI survive a
  re-index (DS923+ test). For videos (database only) this is the same test as
  in section 3.

**Option: upload through the API instead of copying files** (Confirmed [M1]
`upload-beach-sunset`):

```
multipart POST, api=SYNO.Foto.Upload.Item  method=upload_to_folder  version=1
target_folder_id=21  name="\"IMG_0001.jpg\""  duplicate="\"ignore\""
mtime=1720121400  file=<binary>
-> {"data": {"action": "new", "id": 24, "unit_id": 24}}
```

The reply gives the item id at once, so there is no path lookup and no wait
for basic indexing. `duplicate="ignore"` returns the existing id with
`action: "ignore"` (Confirmed [M1]). Shared Space:
`SYNO.FotoTeam.Upload.Item`. PhotoMigrator, a maintained Takeout-to-Synology
tool, uploads this way (with `upload` v1 to `PhotoLibrary`) [P1]. Cost: every
byte goes through HTTP, slower than a local copy on the NAS.

## 7. Limits, rates and stability

- **Rate limits**: none documented and none reported by any client. Clients
  call one request after another. DSM's Auto Block (failed logins) applies to
  the login call: a wrong password in a loop can block the tool's IP.
- **Batch sizes**: up to 100 ids per write, as the web client (Reported
  [M2]); item lists of 500-5,000 per page are used (PhotoMigrator uses 5,000
  for `list_with_filter` [P1]; mcp-synology caps at 500). Use 500.
- **Request size**: use POST, so long id lists do not hit URL length limits
  (a 414 was seen with GET on another DSM API [M2]).
- **Known breakage across versions**:
  - Photos 1.6.2 broke folder browsing in synophotos (issue #51, 2024-01)
    [F3]. synophotos now pins higher versions (`get` v4/v5) [F1].
  - Photos 1.9.0/1.9.1 added `Browse.Item` v7 for favorites; v1-v6 answer
    120 for the favorite fields. 1.9.1 renumbered tag ids on re-index [M2].
  - `SYNO.Foto.Favorite list` works on 1.3.4 and answers 103 on 1.9.1 [M2].
  - Every call in this file was recorded working on both Photos 1.3.4 (2022)
    and 1.9.1 (2026) with the same versions [M2], and all methods are in the
    2021 API list [Z1]. So the core calls have been stable for five years.
- **Client libraries**:
  - N4S4/synology-api (Python, MIT, about 600 stars, release v0.9.4
    2026-10-03): Photos module since 2021-10; `set_item_description`,
    `create_normal_album`, `get_index_status`, upload added 2026-06. No
    `add_item`, no `set_cover`, no `reindex`. Personal Space only for
    description and Albums [N1]. Useful as a reference; the tool can call the
    Web API directly with `requests`, a few dozen lines.
  - fortysix2ahead/synophotos (Python, 3 stars, last push 2025-10): Personal
    Space only; has `add_item` [F1][F2].
  - jaimetur/PhotoMigrator (about 270 stars, last push 2026-09): Takeout to
    Synology Photos by upload; no Descriptions [P1].
  - cmeans/mcp-synology: the recorded 1.9.1 captures used here [M1][M2].

## 8. Open questions to test on the DS923+

1. `SYNO.Foto.Browse.Item set description` on a **video**: does it stick, and
   does it survive a re-index?
2. `SYNO.FotoTeam.Browse.Folder get` with `name`: works like Personal Space?
3. `NormalAlbum add_item` with a **Shared Space** item id: accepted, and shown
   in the Album?
4. Accented French text in `description`: correct with `\u` escapes and with
   raw UTF-8?
5. Do item ids stay the same after a full re-index (no file deleted)?
6. Does `SYNO.FotoTeam.Index reindex` work for a non-admin user with Shared
   Space Manager rights?
7. Re-run the calls of this file once on DSM 7.4.1 / Photos 1.9.1-10928 (the
   captures are from DSM 7.2.2).

## Sources

Synology:

- [A1] DSM Login Web API Guide (2023-04-19),
  <https://global.download.synology.com/download/Document/Software/DeveloperGuide/Os/DSM/All/enu/DSM_Login_Web_API_Guide_enu.pdf>
- [K1] What metadata standards does Synology Photos support?,
  <https://kb.synology.com/en-global/DSM/tutorial/What_metadata_standards_does_Synology_Photos_support>

Recorded requests and replies:

- [M1] cmeans/mcp-synology, live captures on DSM 7.2.2 + Photos 1.9.1
  (2026-10-17), key names quoted in the text,
  <https://github.com/cmeans/mcp-synology/blob/main/tests/modules/photos/fixtures/dsm-7.2.2-photos-1.9.1.json>
- [M2] cmeans/mcp-synology, Photos module spec (verified on Photos 1.3.4 and
  1.9.1),
  <https://github.com/cmeans/mcp-synology/blob/main/docs/specs/photos-module-spec.md>
- [S1] sahilagnihotri/synology-native-photos, probe results on a real DS925+
  (DSM 7.3.2, 2026-07),
  <https://github.com/sahilagnihotri/synology-native-photos/blob/main/documentation/phase0-probe-results.md>
- [Z1] zeichensatz/SynologyPhotosAPI, `SYNO.Foto.lib` (WebAPI definition from
  a NAS, 2021),
  <https://github.com/zeichensatz/SynologyPhotosAPI/blob/master/API/SYNO.Foto.lib>
- [Z2] same, `SYNO.FotoTeam.lib`,
  <https://github.com/zeichensatz/SynologyPhotosAPI/blob/master/API/SYNO.FotoTeam.lib>

Client source code:

- [N1] N4S4/synology-api, `synology_api/photos.py`,
  <https://github.com/N4S4/synology-api/blob/master/synology_api/photos.py>
- [N2] N4S4/synology-api, `synology_api/auth.py` (login, 2FA device token),
  <https://github.com/N4S4/synology-api/blob/master/synology_api/auth.py>
- [N3] N4S4/synology-api issue #411 "List photos in album",
  <https://github.com/N4S4/synology-api/issues/411>
- [F1] fortysix2ahead/synophotos, `synophotos/parameters/photos.py`,
  <https://github.com/fortysix2ahead/synophotos/blob/main/synophotos/parameters/photos.py>
- [F2] fortysix2ahead/synophotos, `synophotos/photos.py`,
  <https://github.com/fortysix2ahead/synophotos/blob/main/synophotos/photos.py>
- [F3] fortysix2ahead/synophotos issue #51 "API Change for Synophotos
  1.6.2-0710", <https://github.com/fortysix2ahead/synophotos/issues/51>
- [P1] jaimetur/PhotoMigrator, `ClassSynologyPhotos.py`,
  <https://github.com/jaimetur/PhotoMigrator/blob/main/src/Features/SynologyPhotos/ClassSynologyPhotos.py>
- [B1] npflood/synology-photos-albums-backup, `rebuild_album.py`,
  <https://github.com/npflood/synology-photos-albums-backup/blob/main/rebuild_album.py>
- [S2] sahilagnihotri/synology-native-photos, `recycle.rs` (`trigger_reindex`),
  <https://github.com/sahilagnihotri/synology-native-photos/blob/main/core/synology-api/src/recycle.rs>
- [Y1] lyydhy/synology-butler, `index_service_api.dart`,
  <https://github.com/lyydhy/synology-butler/blob/master/lib/data/api/index_service_api.dart>

Community report:

- [D1] Dave Jansen, "Automatically schedule a Photos re-index on your Synology
  NAS" (2021, updated 2023),
  <https://davejansen.com/automatically-schedule-a-photos-re-index-on-your-synology-nas/>
