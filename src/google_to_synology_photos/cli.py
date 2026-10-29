"""The g2s command line."""

import argparse
import ssl
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
from google_to_synology_photos.synology import SynologyPhotos
from google_to_synology_photos.synology_client import SynologyPhotosClient


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
    args = parser.parse_args(argv)

    if args.command == "login":
        connect(True)
        print("Logged in to the NAS.")
        return 0

    export: Path = args.export
    if not export.is_dir():
        parser.error(f"{export} is not a folder")

    report = run_import(export, connect(False)).render()
    print(report)
    # The report sits next to the export folder, beside the other exports.
    (export.resolve().parent / REPORT_NAME).write_text(report, encoding="utf-8")
    return 0
