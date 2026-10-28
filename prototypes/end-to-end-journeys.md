# PROTOTYPE — end-to-end journeys (throwaway, never merged)

Question: *What end-to-end experience does the user get?* Two shapes, written as
the user would live them. Numbers are rough estimates for the real export
(82 GB, 39 ZIPs, ~67.7k photos, 252 Albums, ~410 videos to convert, 6.5 GB of
them) on a DS923+ (AMD Ryzen R1600, 2 cores, no hardware video encoder, 4 GB
RAM) and a laptop on Wi-Fi at ~35 MB/s.

Common to both, already decided: Synology Photos only, Photo Descriptions
written through the API, video conversion to H.264 MP4, the report, optional
Album Downloads, never delete old Takeout Exports.

---

## Journey A — a command-line tool run on a computer

### First time (≈ 1 evening of setup + ~3 h unattended)

1. **On the NAS (once):** create the user `photos-library` (non-admin, Synology
   Photos + File Station rights). Create the shared folder `takeout`.
2. **On the computer (once):** install `uv`, then
   `uv tool install google-to-synology-photos`. Linux, macOS or Windows.
3. **Google Takeout:** request Google Photos only, ZIP, 50 GB parts. Download
   the 39 ZIPs in the browser (a few hours, on Google's side and the download).
4. **Copy the ZIPs to the NAS** into `takeout/2026-10-24/` (File Station upload,
   or a network drive): 82 GB at 35 MB/s ≈ **40 min**.
5. **Run:** `g2s import //nas/takeout/2026-10-24`
   - It asks once for the NAS address, user, password and 2FA code. It stores a
     device token in the computer's keyring, so no password is stored in a file.
   - It reads the ZIPs **over Wi-Fi** (≈ 40 min), converts the videos **on the
     laptop** (≈ 30–60 min, it has a fast CPU), and writes the media into the
     NAS Library folder **over Wi-Fi** (≈ 75 GB, ≈ 40 min).
   - It waits for Synology Photos to index (the NAS makes thumbnails, ≈ 1–3 h
     for 67k photos, in the background), then creates Albums and sets Photo
     Descriptions (≈ 70k API calls, ≈ 30–60 min).
   - The laptop must stay awake and on the network the whole time
     (**≈ 3–5 h**). If it stops, running the same command again continues.
6. **Read the report** in the terminal (and in `report.md` next to the export):
   counts, Albums to complete with an Album Download, Comments with no photo.

### Refresh (once or twice a year, ≈ 1 h of the user's time)

Steps 3, 4 and 5 with the new export folder. Only new or changed things are
written, but the tool still reads the whole 82 GB export over Wi-Fi (≈ 40 min).

### What the user needs to know
Open a terminal, paste a command, type a password. Keep the laptop awake.

---

## Journey B — a container on the NAS (Container Manager)

### First time (≈ 30 min of setup + ~2–4 h unattended)

1. **On the NAS (once):** same user `photos-library` and shared folder `takeout`.
2. **On the NAS (once):** install **Container Manager** from Package Center.
   Create a **Project** and paste the `compose.yaml` given in the guide. It
   mounts `takeout` read-only and the NAS Library folder read-write. Set the
   NAS user and password in the project's environment fields. 2FA is not
   required for this user (see *Test the Synology Photos API on the DS923*).
3. **Google Takeout:** same as A.
4. **Copy the ZIPs to the NAS:** same as A (≈ 40 min).
5. **Run:** in Container Manager, start the project (or **Action → Run**).
   - Everything happens **on the NAS**: reading the ZIPs from local disk
     (minutes), converting videos on the R1600 (≈ 1–3 h for 410 old SD videos,
     slower for the ~12 HEVC ones), copying into the Library on the same
     disk, waiting for indexing, then the API calls to `localhost`.
   - The computer can be switched off. Progress shows in the container's
     **Log** tab.
6. **Read the report:** `takeout/report-2026-10-24.md` in File Station (or
   the last lines of the log).

### Refresh (≈ 15 min of the user's time)

Download and copy the new export (step 3, 4), change one line in the project
(the export folder, or a `latest` folder), start the project, read the report.

### What the user needs to know
Install a package, paste a file into a form, read a log. No terminal.

---

## Side by side

| | A — tool on a computer | B — container on the NAS |
|---|---|---|
| User skills | terminal, install `uv` | Container Manager, paste `compose.yaml` |
| Where the work runs | laptop (data over Wi-Fi twice) | NAS (all local) |
| Video conversion | fast (laptop CPU) | slow (R1600, no hardware encoder) |
| Unattended time, first import | ≈ 3–5 h, laptop awake | ≈ 2–4 h, laptop off |
| Credentials | asked once, device token in the computer's keyring | in the project's environment (password readable by NAS admins) |
| Refresh effort | download, copy, one command | download, copy, start a project |
| Works on other Synology models | yes | only x86 models with Container Manager |
| Maintainer effort | Python package on PyPI | + a container image on a registry |
| Development and tests | same CLI in the devcontainer | same CLI, wrapped in an image |

Both are **the same CLI**: B is A packaged in a container. A can be shipped
first and B added later without changing the tool.

## Not chosen here
- A Synology package (`.spk`): more work to build and sign, for little gain over
  Container Manager.
- A web page in the container (forms, buttons): the log and `report.md` are
  enough for once or twice a year.
- Running the CLI over SSH on the NAS without a container: DSM has no `uv`,
  and installing Python tools on DSM is fragile.
