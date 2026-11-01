# Run the first import

## Plan for it

The first import takes about **3 to 5 hours** for an export of about 80 GB. Start it in the evening, and connect the computer to the network with an **Ethernet cable**. Stop the computer from going to sleep if you can.

If it stops, nothing is lost: run the same command again, and it continues where it stopped. You can even continue from another computer.

## Start the import

Give `g2s import` the folder of the export:

=== "Windows"

    ```powershell
    g2s import Z:\2026-01-15
    ```

=== "macOS"

    ```bash
    g2s import /Volumes/takeout/2026-01-15
    ```

=== "Linux"

    ```bash
    g2s import /mnt/takeout/2026-01-15
    ```

## Log in

The first time, the tool asks:

1. The NAS address, such as `https://192.168.1.20:5001`.
2. The NAS Account user name.
3. Whether to trust the NAS certificate. Most NAS have a self-signed certificate, so the tool shows its fingerprint. You can compare it with the one in DSM, in **Control Panel > Security > Certificate**. Type `yes`.
4. The NAS Account password. It does not show as you type.
5. A 2FA code, if 2FA is on.

Later runs ask nothing. The password stays in the keyring of your computer, and never in a file. To change these answers, run `g2s login`.

## Watch it run

The tool first reads all the ZIPs, which can take some minutes with nothing on the screen. Then it shows three steps, one after the other:

```text
Photos and videos: 1250/48210
Albums: 12/180
Photo Descriptions: 3000/48210
```

## Read the report

At the end, the tool prints a report, and saves it as `report.md` in the `takeout` folder. Each new run replaces that file, so keep a copy if you want to compare.

The first lines count what the run did. Then come lists, and most of them should say "None."

| Section | What it means | What to do |
|---|---|---|
| **Writes that did not stick** | The NAS did not keep something. | Run the same command again. |
| **Files sent without their missing date or position** | ExifTool could not write into this file. It is on the NAS, and may show the wrong date. | Nothing to fix with the tool. |
| **Videos that failed to convert, not uploaded** | This video is not on the NAS. | Each run tries it again. It stays safe in the ZIPs. |
| **Album photos with no file in the export** | An Album lists this photo, but no ZIP holds it. | Check that you copied every ZIP. |
| **Comments that match no photo** | The photo of this Comment is not in the export. The Comment shows in the text of its Album when its Album is known. | Usually, make an Album Download. |
| **Shared Albums where photos are surely missing** | Other people added photos here, and they are not in the export. | [Make an Album Download](album-downloads.md). |
| **Album Downloads** | The ZIPs used, and how many photos each added. | Nothing. |
| **Album Downloads that match no Album** | No Album was found for this ZIP. | Check that it is the right ZIP. |
| **Album Download files with no date, not added** | The tool cannot tell when this photo was taken. | Nothing to fix with the tool. |

!!! warning "The report is private"
    It holds Album titles and people's names and messages. If you report a bug, share only the counts.

Next: [add Album Downloads](album-downloads.md), or [browse the NAS Library](browsing.md).
