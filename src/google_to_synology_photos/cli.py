"""The g2s command line."""

import argparse
import http.client
import json
import ssl
import sys
import urllib.error
from collections.abc import Callable, Sequence
from pathlib import Path

import keyring.errors
import platformdirs

from google_to_synology_photos.importer import run_import
from google_to_synology_photos.login import (
    DsmGateway,
    KeyringSecrets,
    LoginFailedError,
    TerminalUser,
    login,
)
from google_to_synology_photos.media import ExifToolMissingError, FfmpegMissingError
from google_to_synology_photos.synology import SynologyError, SynologyPhotos
from google_to_synology_photos.synology_client import SynologyPhotosClient
from google_to_synology_photos.takeout import SelectedAlbumsExportError, older_export


REPORT_NAME = "report.md"


def connect_to_nas(ask_again: bool) -> SynologyPhotos:
    """Log in to the NAS as the NAS Account; ask_again forgets what was kept."""
    try:
        session = login(
            platformdirs.user_config_path("g2s"),
            KeyringSecrets(),
            TerminalUser(),
            DsmGateway(),
            ask_again=ask_again,
        )
    except LoginFailedError as error:
        raise SystemExit(f"g2s: {error}") from error
    except OSError as error:
        raise SystemExit(f"g2s: {_network_problem(error)}") from error
    except keyring.errors.KeyringError as error:
        raise SystemExit(
            f"g2s: the OS keyring cannot be used ({error}). "
            "g2s keeps the NAS password there, never in a file."
        ) from error
    return SynologyPhotosClient(session)


def _network_problem(error: OSError) -> str:
    """Explain why the NAS could not be reached."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, ssl.SSLCertVerificationError):
        return (
            "the NAS certificate is not the one trusted before. If it was "
            "renewed in DSM, run `g2s login` to check and trust the new one."
        )
    return f"cannot reach the NAS ({reason})."


def _show_progress(step: str, number: int, total: int) -> None:
    """Show the step of a run on one line, which each number overwrites."""
    end = "\n" if number == total else ""
    print(f"\r{step}: {number}/{total}", end=end, file=sys.stderr, flush=True)


def main(
    argv: Sequence[str] | None = None,
    connect: Callable[[bool], SynologyPhotos] = connect_to_nas,
) -> int:
    """Run g2s with argv; connect(ask_again) gives the Synology Photos client."""
    parser = argparse.ArgumentParser(
        prog="g2s",
        description="Turn a Google Photos Takeout Export into a NAS Library "
        "in Synology Photos.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "login", help="Ask again for the NAS address, user name and password."
    )
    import_cmd = commands.add_parser(
        "import", help="Import a Takeout Export (a folder of ZIPs)."
    )
    import_cmd.add_argument("export", type=Path, help="Folder of the Takeout ZIPs.")
    import_cmd.add_argument(
        "--previous",
        type=Path,
        help="Export to compare with, to find changed files. "
        "Default: the newest older export next to it.",
    )
    args = parser.parse_args(argv)

    if args.command == "login":
        connect(True)
        print("Logged in to the NAS.")
        return 0

    export: Path = args.export
    if not export.is_dir():
        parser.error(f"{export} is not a folder")
    previous: Path | None = args.previous
    if previous is None:
        previous = older_export(export)
    elif not previous.is_dir():
        parser.error(f"{previous} is not a folder")

    try:
        report = run_import(export, connect(False), _show_progress, previous).render()
    except (
        SelectedAlbumsExportError,
        ExifToolMissingError,
        FfmpegMissingError,
    ) as error:
        raise SystemExit(f"g2s: {error}") from error
    except (
        SynologyError,
        OSError,
        http.client.HTTPException,
        json.JSONDecodeError,
    ) as error:
        print(file=sys.stderr)
        raise SystemExit(
            f"g2s: the run stopped ({error}). Run g2s again: it continues where "
            "it stopped."
        ) from error
    print(report)
    # The report sits next to the export folder, beside the other exports.
    (export.resolve().parent / REPORT_NAME).write_text(report, encoding="utf-8")
    return 0
