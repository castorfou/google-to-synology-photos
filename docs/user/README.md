# Start here

This guide takes you from nothing to your Google Photos Albums in Synology Photos on your own NAS, with their Captions and Comments.

You need to be able to follow commands in a terminal. You do not need to write code.

## What the tool does

`g2s` is a command-line tool. It runs on your computer (Linux, macOS or Windows), not on the NAS. It reads a Takeout Export and builds a private copy of your Albums in Synology Photos:

- Every Album keeps its title and its photos and videos.
- A photo in several Albums shows in each of them, and is stored once.
- Each photo gets its real date and its place, even when the file has lost them.
- Videos that Synology Photos cannot play become MP4 files.
- Captions, Comments and Likes show in the Photo Description of each photo, with names and dates.

Google Photos stays in use. A few times a year, you bring the copy up to date with a newer download.

## What the tool does not copy

- Photos that are in no Album.
- Albums owned by another Google account.
- Faces, favourites and archived photos.

A Takeout Export holds only the photos in the Household Account's library. Photos that other people added to a shared Album are missing from it. [Album Downloads](album-downloads.md) bring them back.

## Words used in this guide

| Word | Meaning |
|---|---|
| **Household** | The people at home who will see the photos. |
| **Household Account** | The one Google account that owns the Albums. |
| **NAS Account** | The one account on the NAS shared by the Household. |
| **NAS Library** | The copy of your Albums in Synology Photos. |
| **Takeout Export** | One full download of your Google Photos, as ZIP files. |
| **Album Download** | The ZIP you get with "Download all" on one shared Album. |
| **Refresh** | Bringing the NAS Library up to date from a newer Takeout Export. |
| **Caption** | The text the owner wrote on a photo. |
| **Comment**, **Like** | What people wrote or hearted on a photo or Album in a shared Album. |
| **Photo Description** | The text shown with a photo on the NAS: its Caption, then its Comments and Likes. |

## What you need

- A Synology NAS with DSM 7 and the **Synology Photos** package, and an administrator login.
- Free space on the NAS for about twice the size of your Google Photos: one copy for the NAS Library, and one for the ZIPs, which you keep.
- The login of the Household Account.
- A computer on the same network as the NAS, with a few GB free for the videos being converted.

## The steps

1. [Prepare the NAS](nas-setup.md): the NAS Account, the `takeout` folder and the Recycle Bin.
2. [Install the tool](install.md): `g2s`, `ffmpeg` and ExifTool.
3. [Get the Takeout Export](takeout-export.md) and copy the ZIPs to the NAS.
4. [Run the first import](first-import.md) and read the report.
5. [Add Album Downloads](album-downloads.md) for the Albums the report lists.
6. [Browse the NAS Library](browsing.md) with the NAS Account.
7. [Run a Refresh](refresh.md) when you want to catch up with Google Photos.

If something goes wrong, see [Problems and solutions](troubleshooting.md).
