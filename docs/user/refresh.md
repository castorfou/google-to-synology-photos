# Run a Refresh

A Refresh brings the NAS Library up to date with Google Photos. Do one whenever you want, for example once or twice a year.

## Steps

1. [Request a new Takeout Export](takeout-export.md#request-the-export). It must be a full one, like the first.
2. Copy its ZIPs into a new dated folder in `takeout`, next to the older ones.
3. Run the same command on the new folder.

```text
takeout/
├── 2026-01-15/         keep it
├── 2026-07-15/         the new export
├── album-downloads/
└── report.md
```

=== "Windows"

    ```powershell
    g2s import Z:\2026-07-15
    ```

=== "macOS"

    ```bash
    g2s import /Volumes/takeout/2026-07-15
    ```

=== "Linux"

    ```bash
    g2s import /mnt/takeout/2026-07-15
    ```

The tool finds the older export by itself, and sends only what is new or changed. It is faster than the first import. Then [read the report](first-import.md#read-the-report), as after the first import.

Any computer can run a Refresh, as long as it has the tool and sees the `takeout` folder. As with the first import, you can stop and run the same command again.

!!! danger "Never delete an old export"
    The new export is compared with the older ones. Keep them all, even after a Refresh that went well.

## What happens to your photos

**Google Photos wins.** Imported content follows Google Photos, and changes made on the NAS to that content are put back.

| In Google Photos | On the NAS after a Refresh |
|---|---|
| New photo or new Album | Added |
| Album renamed | Renamed, not duplicated, unless its photos at least doubled: then the tool creates a new Album, and the old one stays |
| Caption changed, or new Comments and Likes | Updated |
| Comment deleted | Removed from the text |
| Photo edited | Replaced by the new version, in the same Albums |
| Date of a photo fixed | Moved to the folder of its year, not duplicated. If the file holds its own date, Synology Photos may keep showing that one |
| Photo removed from an Album | Stays in the Album |
| Photo or Album deleted | Stays on the NAS |

| On the NAS | After a Refresh |
|---|---|
| Photo Description changed | Put back as in Google Photos |
| Photo deleted | Sent again |
| Album deleted | Created again |
| Album renamed | Renamed back |
| Your own Album, with photos from outside `Google Photos` | Left alone, except that a photo that moves keeps its place in it |

So make your changes in Google Photos, not on the NAS. Nothing that was ever copied is removed from the NAS Library, except that the text follows Google Photos.

Two Albums with the same title stay two separate Albums.
