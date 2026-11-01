# Add Album Downloads

A Takeout Export holds only the photos in the Household Account's library. When a relative adds a photo to a shared Album, that photo is missing from the export. An Album Download fills the gap.

This step is optional, and you can do it at any time.

## Which Albums need one

The report lists them under **Shared Albums where photos are surely missing**. These are the Albums with Comments on photos the export does not hold.

The tool can only see a gap when a Comment reveals it. If you know that other people added photos to a shared Album, make its Album Download too, even if the report does not list it.

## Make an Album Download

1. Sign in to [photos.google.com](https://photos.google.com) with the Household Account.
2. Open the shared Album.
3. Click the three dots at the top right, and choose **Download all**.
4. Save the ZIP. A large Album can give several ZIPs: keep them all.

## Add it to the NAS

Put the ZIPs, without unzipping, in a folder named `album-downloads` inside the `takeout` folder. Do not rename them.

```text
takeout/
├── 2026-01-15/
├── album-downloads/
│   ├── Summer at the lake-1-001.zip
│   └── Summer at the lake-1-002.zip
└── report.md
```

Then run the same command as before:

```bash
g2s import /mnt/takeout/2026-01-15
```

The tool adds only the photos the Album lacks, so nothing is imported twice. The Album leaves the report's list. It comes back only if a later Refresh brings a newer Comment on a missing photo.

## What to expect

- A photo that comes only from an Album Download has no Caption, no Comments and no place on the NAS: the ZIP does not hold them.
- A photo needs a date to be added. The tool takes it from the file, or from a date in the file name. The report lists the files with neither.
- A photo the Household Account also saved to its own library joins the Album with its Caption.

!!! tip "Keep the ZIPs"
    Leave the ZIPs in `album-downloads`. They tell the tool which Albums are covered, and which photo is which at the next Refresh. A photo already added stays on the NAS even if its ZIP is removed, but its Album comes back to the report's list.

Next: [browse the NAS Library](browsing.md).
