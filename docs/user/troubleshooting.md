# Problems and solutions

## The run stopped

Run the same command again. It continues where it stopped, and sends nothing twice. If you changed nothing, a second run on a finished export writes nothing to the NAS.

A stop during a Refresh may replace the same changed files again at the next run. This takes time, but the result is the same.

## Messages from g2s

| Message | What to do |
|---|---|
| `g2s: command not found` | Run `uv tool update-shell`, and open a new terminal. |
| `... is not a folder` | Check the path of the export. See [connect the `takeout` folder](install.md#connect-the-takeout-folder-to-your-computer). |
| `ExifTool was not found` | [Install ExifTool](install.md#install-ffmpeg-and-exiftool). Nothing was uploaded. |
| `ffmpeg was not found` | [Install ffmpeg](install.md#install-ffmpeg-and-exiftool), with its `ffprobe`. Nothing was uploaded. |
| `this looks like an export of selected Albums` | Request a [full Takeout Export](takeout-export.md#request-the-export), with all photo albums. Nothing was imported. |
| `Wrong user name or password.` | Run the command again and type the password. To change the user name, run `g2s login`. |
| `The NAS refused the login (error ...)` | Check that the NAS Account is active and may use Synology Photos. Error 404 means a wrong 2FA code. |
| `The NAS certificate was not trusted.` | Run `g2s login`, and answer `yes` if the fingerprint is the right one. |
| `the NAS certificate is not the one trusted before` | Run `g2s login` to check and trust the new certificate. This happens when DSM renews it. |
| `cannot reach the NAS` | Check that the NAS is on, that the address is right, and that you are on its network or VPN. |
| `the OS keyring cannot be used` | `g2s` keeps the password in the keyring of your computer. On Linux, you need a running keyring, such as GNOME Keyring or KWallet, so run `g2s` in a desktop session. |
| `the run stopped (...)` | Run the same command again. |

## Questions

**A photo is missing from an Album.**
Another person probably added it. See [Album Downloads](album-downloads.md).

**The whole Album is missing.**
The tool imports only Albums the Household Account owns. Check that the Album appears in the export.

**A Comment disappeared from the NAS.**
It was deleted in Google Photos: the text follows Google.

**A date looks wrong.**
Fix it in Google Photos. The next Refresh moves the photo to the right date.

**I deleted a photo on the NAS by mistake.**
If it is still in Google Photos, the next Refresh sends it again, and runs on the same export do too. If you need it now, get it from the [Recycle Bin](nas-setup.md#turn-on-the-homes-recycle-bin).

**Can I use another export instead of the newest older one?**
Yes: `g2s import <new export> --previous <older export>`. You rarely need this.

## Reporting a bug

Open an issue on [GitHub](https://github.com/castorfou/google-to-synology-photos/issues). Share the message and the counts of the report only: the lists hold people's names and messages.
