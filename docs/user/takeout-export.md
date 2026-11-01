# Get the Takeout Export

## Request the export

1. Go to [takeout.google.com](https://takeout.google.com), signed in with the Household Account.
2. Click **Deselect all**.
3. Find **Google Photos**, and tick it.
4. Leave **All photo albums included** as it is. The tool refuses an export of selected Albums.
5. Click **Next step**.
6. Choose **Send download link via email**, **Export once**, and the file type **.zip**.
7. Choose a large file size, such as 10 GB or more, so that you get fewer files.
8. Click **Create export**.

Google can take hours or days. It sends an email when the export is ready. The links in that email expire after about a week.

## Download the ZIPs

Download **every** ZIP. A large library gives dozens of them.

!!! warning "Do not unzip"
    Keep the ZIPs exactly as Google made them. The tool reads inside them. On a Mac, turn off **Open "safe" files after downloading** in Safari, or Safari may unzip them.

## Copy the ZIPs to the NAS

In the `takeout` folder, make a folder named with the date of the export, as `YYYY-MM-DD`. Copy all the ZIPs into it.

```text
takeout/
└── 2026-01-15/
    ├── takeout-20260115T101500Z-001.zip
    ├── takeout-20260115T101500Z-002.zip
    └── ...
```

The name matters: the tool uses it to tell which export is older. Each Takeout Export gets its own folder.

Check that the number of ZIPs in the folder matches the number in Google's email. A ZIP left out is not an error for the tool: the photos in it are simply missing, and the report lists them.

!!! danger "Never delete an old export"
    Keep every Takeout Export on the NAS, even after a Refresh. The tool compares each new export with the one before it to find what changed. Old exports also hold your original videos and the earlier versions of edited photos.

Next: [run the first import](first-import.md).
