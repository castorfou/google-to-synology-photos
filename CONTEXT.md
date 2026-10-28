# Google to Synology Photos

Copying a family's Google Photos history (albums, photos, captions, comments) onto a Synology NAS, where the household can browse it privately, while Google Photos stays in use.

## Language

### Places

**Google Photos**:
The live source of truth, where photos are added, captioned and commented, and where albums are shared with Family.
_Avoid_: Google, the cloud, Picasa (Picasa Web is its predecessor; its old albums are treated as Google Photos content)

**NAS Library**:
The copy of the Google Photos content kept on the Synology NAS and browsed by the Household.
_Avoid_: backup, archive, mirror

**Household Account**:
The single Google account shared by the Household, which owns the Albums and from which every Takeout Export is made.
_Avoid_: my account, the Google account

**Takeout Export**:
One download of the Household Account's Google Photos content produced by Google Takeout; the main input to the NAS Library.
_Avoid_: dump, backup, archive

**Album Download**:
The files of one shared Album downloaded from Google Photos ("Download all"), used only to add the photos other Contributors put in that Album, which are missing from the Takeout Export. Optional, and added whenever the user wants.
_Avoid_: album export, album takeout

**Refresh**:
Bringing the NAS Library up to date from a newer Takeout Export. Imported content follows Google Photos and may overwrite changes made on the NAS. No photo or Album that once existed is removed, but text (Captions, Comments, Likes) follows the latest Takeout Export: a Comment deleted in Google Photos disappears from the NAS Library.
_Avoid_: sync, re-import, update

**Switch-over**:
The moment the NAS Library becomes the main place and Refreshes stop; after it, changes made on the NAS are never overwritten.
_Avoid_: migration, cut-over

### People

**Household**:
The people living in the home (spouse, kids) who get access to the NAS Library.
_Avoid_: family, users

**Family**:
Relatives and friends outside the Household who see and comment on albums in Google Photos only; they never access the NAS.
_Avoid_: household, guests

### Content

**Album**:
A named group of photos and videos created in Google Photos (or earlier in Picasa Web), possibly shared with Family. Its photos may come from any Contributor.

**Contributor**:
Any Google account that added a photo to an Album: the Household Account itself, the personal account of a Household member, or a Family member's account. Only photos in the Household Account's library are in a Takeout Export.
_Avoid_: uploader, owner

**Caption**:
The text written on one photo by its owner, in Google Photos the photo's description.
_Avoid_: description, title, comment

**Comment**:
A message posted by any person (often Family) on a photo or Album in a shared Album.
_Avoid_: caption, remark

**Like**:
A heart that a person puts on a photo in a shared Album.
_Avoid_: favourite (a favourite is the owner's star, not a Like)

**Photo Description**:
The text shown with a photo in the NAS Library: its Caption, followed by its Comments and Likes written out as text (author, date), from every Album the photo is in. The oldest photo of an Album also carries the Album's own description, Comments and Likes.
_Avoid_: caption, comment
