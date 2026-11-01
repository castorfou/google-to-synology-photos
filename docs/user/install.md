# Install the tool

Do these steps on the computer that will run the import.

## Install uv

`uv` installs `g2s` and the Python version it needs.

=== "Linux and macOS"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    In PowerShell:

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

Close the terminal and open a new one.

## Install ffmpeg and ExifTool

`g2s` needs two other programs. `ffmpeg` converts videos, and ExifTool writes missing dates and places into photos.

=== "Debian and Ubuntu"

    ```bash
    sudo apt install ffmpeg libimage-exiftool-perl
    ```

=== "macOS"

    With [Homebrew](https://brew.sh):

    ```bash
    brew install ffmpeg exiftool
    ```

=== "Windows"

    In PowerShell:

    ```powershell
    winget install Gyan.FFmpeg
    winget install OliverBetz.ExifTool
    ```

Close the terminal and open a new one, then check that both work:

```bash
ffmpeg -version
exiftool -ver
```

On another system, get them from [ffmpeg.org](https://ffmpeg.org) and [exiftool.org](https://exiftool.org). Both must work from any folder.

## Install g2s

```bash
uv tool install git+https://github.com/castorfou/google-to-synology-photos
```

Check that it works:

```bash
g2s --help
```

If the command is not found, run `uv tool update-shell`, and open a new terminal.

To get a newer version later:

```bash
uv tool upgrade google-to-synology-photos
```

## Connect the `takeout` folder to your computer

The tool reads the ZIPs where they are on the NAS, so your computer must see the `takeout` folder. Sign in with the NAS Account when asked. Replace `nas` with the name or address of your NAS.

=== "Windows"

    1. In File Explorer, right-click **This PC**, and choose **Map network drive**.
    2. Choose the letter `Z:`.
    3. In **Folder**, type `\\nas\takeout`.
    4. Tick **Connect using different credentials**, and click **Finish**.

    The folder is now `Z:\`.

=== "macOS"

    1. In Finder, choose **Go > Connect to Server**.
    2. Type `smb://nas/takeout`, and click **Connect**.

    The folder is now `/Volumes/takeout`.

=== "Linux"

    Install the tools, then mount the folder. Replace `photos` with the name of the NAS Account.

    ```bash
    sudo apt install cifs-utils
    sudo mkdir -p /mnt/takeout
    sudo mount -t cifs //nas/takeout /mnt/takeout -o username=photos,uid=$(id -u),gid=$(id -g)
    ```

    The folder is now `/mnt/takeout`.

If the computer cannot connect, check in DSM that **Control Panel > File Services > SMB** is on.

Next: [get the Takeout Export](takeout-export.md).
