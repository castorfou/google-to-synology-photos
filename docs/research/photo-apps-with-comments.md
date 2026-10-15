# Photo apps on a DS923+ that show Comments next to photos

Research for issue #4 (part of #1). Sources checked on 2026-10-15. Claims are
taken from official docs and source code unless marked **(uncertain)**.

## Question

Which self-hosted photo apps that run on a DS923+ (Container Manager / Docker,
AMD Ryzen R1600 with 2 cores, no iGPU, 4 GB RAM by default) show Comments next to
each photo and also support Albums, Captions and Likes? For each app: Comments
with author and date, importing Comments through an API (with the original author
and date, or only as the API user), Captions, Album descriptions, Takeout Export
import, multi-user, resources, external library (files that Synology Photos can
also index), and maturity.

## Short answer

- Only three of the candidates show per-photo Comments with author and date in
  their UI: **Immich** (activity on Albums), **Piwigo** (classic comments under
  the photo) and **Ente** (shared albums only, end-to-end encrypted). **Nextcloud
  + Memories** also qualifies, through the Nextcloud Files comments tab.
  PhotoPrism, LibrePhotos, Lychee and Photoview have no Comments: each has an
  open feature request and nothing built.
- No app's public API lets you set a Comment's **date**. Each one stamps the
  Comment with the server's current time. Only **Piwigo** lets the API set a
  free-text **author name**, and only when the caller is not logged in. In
  Immich and Nextcloud the author is always the logged-in API user.
  Keeping both the original author and the original date takes either
  one account per Comment author plus a direct database write for the date
  (Immich), or a direct SQL insert (Piwigo, where the `comments` table stores
  `author` as plain text and `date` as a column).
- **Immich is the strongest fit overall.** It has Albums, Captions, Album
  descriptions, Likes and Comments, it is very actively maintained, and
  `immich-go` imports a Takeout Export (but not its Comments). On a DS923+ it
  needs a RAM upgrade, or machine learning turned off.
- **Piwigo is the lightest option and has the most flexible Comment model.** It
  has no Takeout importer and no Likes as such (it has favorites and star ratings
  instead).

## Comparison

| App | Comments next to photo (author + date) | Import Comments via API | Caption | Album description | Likes | Takeout Export import | Multi-user | External library (shared with Synology Photos) | DS923+ fit | Maintenance |
|---|---|---|---|---|---|---|---|---|---|---|
| Immich | Yes, in Albums with activity enabled [I1][I4] | Yes, but always as the API user and with the server's time [I1][I2][I3] | Yes, `description` [I5] | Yes [I6] | Yes, one per user per photo [I3] | Yes, `immich-go` (no Comments) [G1][G2] | Yes | Yes, read-only mount; Immich-only metadata stays in Immich's database [I8] | Needs 6 GB minimum, 8 GB recommended; 4 GB only with ML off [I7] | Very active (v3.3.3, 2026-10-14) [I9] |
| Piwigo | Yes, under the photo [P2][P3] | Yes. Free-text author only for guest callers, server's time [P1][P2] | Yes, the photo "description" (uncertain field naming) | Yes, the album "description" (uncertain field naming) | No; favorites and ratings instead (uncertain) | None found; would need a custom script | Yes, with per-album permissions | Yes, "physical albums" synced from `galleries/` [P5] | Light (PHP + MariaDB) | Active (16.4.0, 2026-05-03) [P4] |
| Ente (self-hosted) | Yes, shared albums only, E2E-encrypted [E1] | Impractical (end-to-end encryption) **(uncertain)** | Yes **(uncertain)** | **(uncertain)** | Yes [E1] | Desktop app reads Takeout **(uncertain)** | Yes | No: files sit encrypted in object storage **(uncertain)** | Medium | Active [E2] |
| Nextcloud + Memories | Yes, Files comments tab in the Memories sidebar [N1] | Yes, as the API user and with the server's time [N2]; a custom PHP app could set both [N3] | Through the file's metadata **(uncertain)** | No **(uncertain)** | No (favorites only) **(uncertain)** | No first-party importer **(uncertain)** | Yes | Yes, through External Storage **(uncertain)** | Heavy (full Nextcloud stack) | Active (Memories v10.1.0, 2026-10-14) [N4] |
| PhotoPrism | No; open request #143 since 2019 [PP1] | n/a | Yes | Yes | No (favorites) | No first-party importer | Account UI is a paid-edition feature [PP2] | Yes, indexes originals in place | 3 GB RAM, 2 cores, 4 GB swap [PP3] | Active [PP4] |
| LibrePhotos | No; open request #262 "Comments and likes" [L1] | n/a | Yes | (uncertain) | No | No | Yes | Yes, scans a directory | Heavy machine learning | Active (1.3.0, 2026-10-11) [L1] |
| Lychee | No; open request #281 "Public Comments" [Y1] | n/a | Yes | Yes | No | No | Yes | Import from server **(uncertain)** | Light (PHP) | Active (v7.11.1, 2026-10-13) [Y1] |
| Photoview | No; open request #884 [V1] | n/a | No | No (Albums are folders) | No | No | Yes | Yes, read-only folder scan | Light | Last release v2.4.0 (2024-06-23) [V1] |

## Details

### Immich

- **Comments and Likes.** An "activity" row holds either a Comment or a Like
  (`comment` text or `isLiked`). Each row is tied to an Album, a user, and
  optionally a photo, and has a `createdAt` [I3]. The web viewer shows the
  author's name and avatar, and a relative time with the full date on hover
  [I4]. Comments exist only inside an Album: a photo that belongs to no Album
  cannot have one.
- **Who can comment.** The user must be a member of the Album (the owner is a
  member too, with role `owner`), and the Album must have `isActivityEnabled`
  turned on [I2][I6].
- **Import through the API.** `POST /activities` accepts only `albumId`,
  `assetId`, `type` and `comment` [I1]. The server sets
  `userId: auth.user.id` [I1b], and `createdAt` is a database default [I3]. So:
  - **Author.** Create one Immich user per Comment author (admin API), add each
    one to the Album, and post with that user's API key. These can be accounts
    that never log in.
  - **Date.** The API cannot set it. The only route is a direct SQL `UPDATE` of
    `activity."createdAt"` in Postgres, which is unsupported and may break on
    upgrades **(uncertain how safe this is in practice)**.
- **Captions.** `asset_exif.description` ("or caption") [I5]. `immich-go` fills
  it from the Takeout JSON `description` [G2].
- **Album descriptions.** `album.description` [I6]. `immich-go` fills it from
  the Album JSON's `enrichments` text, not from a top-level `description` field
  [G3] **(check against a real Takeout Export)**.
- **Takeout Export.** `immich-go` (7k stars, v0.32.0, 2026-06-25) reads titles,
  descriptions, dates, GPS, favorites, archived and trashed state, people and
  partner sharing [G1][G2]. It does **not** read Comments.
- **External library.** It works with read-only mounts. Album membership and
  descriptions are stored only in Immich. Moving a file outside Immich makes it
  a new asset, which loses that metadata (and so would lose its Comments). Each
  library belongs to one user, and that cannot be changed later. File watching
  probably fails on network drives, so it relies on the nightly scan [I8].
  `immich-go` uploads copies instead, so using one set of files for both Immich
  and Synology Photos would require external libraries plus API calls for Albums
  and Captions.
- **DS923+.** Requires at least 6 GB RAM (8 GB recommended) and at least 2 cores
  (4 recommended). With 4 GB, machine learning must be disabled. Postgres must be
  on local storage, never a network share. Since v3 the ML container needs an
  x86-64-v2 CPU [I7]. The R1600 is a Zen core, so it should qualify
  **(uncertain, not tested)**.

### Piwigo

- **Comments.** The `comments` table has `author` (free text), `author_id`
  (nullable), `date`, `content` and `validated` [P3]. The photo page lists
  Comments with author and date. These are per photo; Album-level Comments
  would need a plugin **(uncertain)**.
- **Import through the API.** `pwg.images.addComment(image_id, author, content,
  key)` [P1]:
  - For a logged-in user, the author is forced to that user's username.
  - For a guest, any name is accepted unless it matches an existing username,
    which is rejected.
  - The date is always `NOW()`.
  - The call needs an ephemeral `key`, and Comments must be enabled globally and
    on the Album [P2].

  Because `author` and `date` are plain columns, a direct SQL `INSERT` can store
  the original author and date without creating accounts. This is unsupported
  but simple.
- **External files.** "Physical albums" mirror the folder tree under
  `galleries/` and are refreshed by a "synchronize" step that can also read
  EXIF/IPTC. Moving files at the OS level loses metadata stored in Piwigo [P5].
  Album structure would follow the folders, not the Google Albums. Virtual
  Albums can still group photos **(uncertain)**.
- **Likes.** None. The closest features are per-user favorites and star ratings
  **(uncertain whether these are a good stand-in)**.

### Ente

Ente added likes and comments on shared albums and public links in 2026. They
are end-to-end encrypted with the album key, are not available on unshared
albums, and appear in a sidebar on the web [E1]. Encryption means a server-side
import of Comments would have to reimplement the client's crypto. The original
files are stored encrypted in S3-compatible storage, so Synology Photos cannot
index them **(uncertain, from the architecture; not verified in the self-host
docs)**.

### Nextcloud + Memories

The Memories sidebar loads the regular Nextcloud Files sidebar tabs, Comments
included [N1]. The WebDAV comment API sets `actorId` to the session user, and
the server stamps the date [N2]. The PHP interface `OCP\Comments\IComment` has
`setActor()` and `setCreationDateTime()` [N3], so a small custom app or `occ`
script could import the original author and date. Running a full Nextcloud on
the DS923+ is heavy for this one need.

## Open points for later tickets

- Check whether a real Takeout Export contains Comments and Likes at all, and in
  what format. Neither `immich-go` nor any other importer reads them.
- Immich: test whether setting `activity."createdAt"` in SQL survives an upgrade
  and displays correctly.
- Synology Photos' own Comment support is out of scope here.

## Sources

- [I1] Immich, `ActivityCreateDto`: https://github.com/immich-app/immich/blob/main/server/src/dtos/activity.dto.ts
- [I1b] Immich, `ActivityService.create`: https://github.com/immich-app/immich/blob/main/server/src/services/activity.service.ts
- [I2] Immich, `ActivityAccess.checkCreateAccess`: https://github.com/immich-app/immich/blob/main/server/src/repositories/access.repository.ts
- [I3] Immich, `activity` table: https://github.com/immich-app/immich/blob/main/server/src/schema/tables/activity.table.ts
- [I4] Immich, web `ActivityViewer.svelte`: https://github.com/immich-app/immich/blob/main/web/src/lib/components/asset-viewer/ActivityViewer.svelte
- [I5] Immich, `asset_exif` table: https://github.com/immich-app/immich/blob/main/server/src/schema/tables/asset-exif.table.ts
- [I6] Immich, `album` and `album_user` tables: https://github.com/immich-app/immich/blob/main/server/src/schema/tables/album.table.ts
- [I7] Immich, requirements: https://docs.immich.app/install/requirements
- [I8] Immich, external libraries: https://docs.immich.app/features/libraries
- [I9] Immich, releases: https://github.com/immich-app/immich/releases
- [G1] immich-go: https://github.com/simulot/immich-go
- [G2] immich-go, Google Photos JSON: https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/json.go
- [G3] immich-go, Album handling: https://github.com/simulot/immich-go/blob/main/adapters/googlePhotos/googlephotos.go
- [P1] Piwigo, `ws.php` (`pwg.images.addComment`): https://github.com/Piwigo/Piwigo/blob/master/ws.php
- [P2] Piwigo, `functions_comment.inc.php`: https://github.com/Piwigo/Piwigo/blob/master/include/functions_comment.inc.php
- [P3] Piwigo, database schema: https://github.com/Piwigo/Piwigo/blob/master/install/piwigo_structure-mysql.sql
- [P4] Piwigo, releases: https://github.com/Piwigo/Piwigo/releases
- [P5] Piwigo, import and synchronization: https://doc.piwigo.org/self-hosting-piwigo/importing-and-synchronizing-ftp-photos
- [E1] Ente, comments and likes: https://ente.com/help/photos/features/sharing-and-collaboration/comments-and-likes
- [E2] Ente, repository: https://github.com/ente-io/ente
- [N1] Memories, `Sidebar.vue`: https://github.com/pulsejet/memories/blob/master/src/components/Sidebar.vue
- [N2] Nextcloud, `CommentsPlugin::createComment`: https://github.com/nextcloud/server/blob/master/apps/dav/lib/Comments/CommentsPlugin.php
- [N3] Nextcloud, `OCP\Comments\IComment`: https://github.com/nextcloud/server/blob/master/lib/public/Comments/IComment.php
- [N4] Memories, releases: https://github.com/pulsejet/memories/releases
- [PP1] PhotoPrism, issue #143: https://github.com/photoprism/photoprism/issues/143
- [PP2] PhotoPrism, users: https://docs.photoprism.app/user-guide/users/
- [PP3] PhotoPrism, getting started: https://docs.photoprism.app/getting-started/
- [PP4] PhotoPrism, repository: https://github.com/photoprism/photoprism
- [L1] LibrePhotos, issue #262: https://github.com/LibrePhotos/librephotos/issues/262
- [Y1] Lychee, issue #281: https://github.com/LycheeOrg/Lychee/issues/281
- [V1] Photoview, issue #884: https://github.com/photoview/photoview/issues/884
