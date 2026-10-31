# Synology Photos API

The tool talks to Synology Photos through the undocumented DSM Web API, at `https://<NAS>:5001/webapi/entry.cgi`, as the NAS Account, in its Personal Space. This page lists the calls it uses and the behaviour measured on a DS923+.

The NAS Account needs the Synology Photos and File Station applications: File Station is the only way to overwrite a file.

## Paths

A NAS path such as `Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG` is:

- in Synology Photos, the file `IMG_0001__yxk3qp.JPG` in the folder `/Google Photos/2013` of the Personal Space;
- in File Station, `/home/Photos/Google Photos/2013/IMG_0001__yxk3qp.JPG`.

## Calls

Parameters are sent as a form POST. Values of the `SYNO.Foto.*` calls are JSON-encoded.

| Need | Call | Notes |
|---|---|---|
| Login | `SYNO.API.Auth login` v6, `session=webui`, `enable_syno_token=yes`, `enable_device_token=yes` | `session=SynologyPhotos` is refused with 402 for a non-admin user. The `synotoken` goes in the `X-SYNO-TOKEN` header. |
| Folder by path | `SYNO.Foto.Browse.Folder get` v2, `name="/Google Photos/2013"` | No `name`: the root of the Personal Space. Error 642: no such folder. |
| Create a folder | `SYNO.Foto.Browse.Folder create` v1, `target_id`, `name` | One level at a time. Error 641: it exists. |
| Items of a folder | `SYNO.Foto.Browse.Item list` v2, `folder_id`, `offset`, `limit` | Items have `id`, `filename`, `filesize`, `type` (`photo`, `video`). |
| Upload | `SYNO.Foto.Upload.Item upload_to_folder` v1, multipart, `target_folder_id`, `name`, `duplicate`, `mtime` | Returns the item `id` at once, and `action` (`new`, `ignore`, `rename`). |
| Overwrite | `SYNO.FileStation.Upload upload` v2, multipart, `path`, `overwrite=true` | Keeps the item id. |
| Delete an item | `SYNO.Foto.Browse.Item delete` v1, `id=[...]` | Deletes the file too. |
| Set a Photo Description | `SYNO.Foto.Browse.Item set` v2, `id=[...]`, `description` | Works on photos and videos. |
| Read an item | `SYNO.Foto.Browse.Item get` v2, `id=[...]`, `additional=["description"]` | An unknown id gives an empty `list`. |
| Create an Album | `SYNO.Foto.Browse.NormalAlbum create` v1, `name`, `item=[]` | |
| Add to an Album | `SYNO.Foto.Browse.NormalAlbum add_item` v1, `id`, `item=[...]` | Sent in batches of 100. |
| Rename an Album | `SYNO.Foto.Browse.Album set_name` v1, `id`, `name` | `set` and `rename` do not exist (error 103). |
| List Albums | `SYNO.Foto.Browse.Album list` v2, `offset`, `limit` | |
| Items of an Album | `SYNO.Foto.Browse.Item list` v2, `album_id`, `offset`, `limit` | |
| Index status | `SYNO.Foto.Index get` v1 | Counts of pending work: `basic`, `metadata`, `metadata_updating`, `thumbnail`… |

## Behaviour

- **Upload ids.** `upload_to_folder` returns the item id at once, before indexing ends.
- **`duplicate`.** Only `ignore` and `rename` are accepted, in every version of `Upload.Item`. `ignore` skips an identical file only: a different file under a taken name is stored as a renamed copy (`x_1.jpg`). The client therefore keeps a listing of each folder it uploads to, and never uploads to a taken path. If the path was taken after the listing, the upload answers `action: "rename"`: the client deletes that copy and returns the item already at the path.
- **Overwrite.** `Upload.Item` cannot overwrite. File Station `overwrite=true` replaces the file and keeps the item id. Synology Photos then reads the file again: the new size shows first, then the metadata, and the Photo Description becomes the one in the new file. The client waits until the item has the new size and the index has no `basic`, `metadata` or `metadata_updating` work left, for up to 10 minutes.
- **Photo Description.** Accents, emoji and line breaks are kept exactly, in texts of at least 6,699 characters. An empty text clears the description. A description written just after the upload is sometimes dropped while the call still answers success; written again a little later, it sticks. The client reads each description back and writes it again after 1, 2, 4 and 8 seconds until it sticks. A description that still has not stuck is left to the import's read-back, which lists it in the report.
- **Unknown items.** `Browse.Item set` and `Browse.Item delete` answer success on an unknown id and do nothing. `NormalAlbum add_item` skips unknown items silently.
- **Unknown Albums.** `NormalAlbum add_item` and `Album set_name` fail with error 609.
- **Album names** are not unique: creating an Album with a taken name gives a second Album.
- **Device token.** The login returns a device token (`did`), even without 2FA. Given back as `device_id`, it spares the 2FA code. A login without the password fails (error 400) even with a device token.
- **Login errors.** 400: wrong user name or password. 403: a 2FA code is needed (`otp_code`). 404: wrong 2FA code.
- **Certificate.** DSM serves a self-signed certificate on its LAN address. The client pins it (see [Architecture](architecture.md#login)). When DSM renews it, the pinned certificate no longer matches: `g2s` stops and asks to run `g2s login`, which shows the new fingerprint.

## Contract test

`tests/test_contract.py` checks the behaviour above against the in-memory fake on every test run. With `G2S_CONTRACT=1`, it also runs against the DS923:

```bash
G2S_CONTRACT=1 uv run pytest tests/test_contract.py
```

- It logs in as the test user of `data/raw/nas-api-test.env` (git-ignored, keys `NAS_URL`, `NAS_USER`, `NAS_PASSWORD`).
- It needs `ffmpeg` to make tiny synthetic photos and videos.
- Each test works in its own folder `Photos/g2s-contract-<random>` of the test user's Personal Space, and deletes that folder and the Albums it created at the end.
- Without `G2S_CONTRACT=1`, as in CI, the NAS variants are skipped.
