"""The g2s command line."""

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from google_to_synology_photos.importer import run_import
from google_to_synology_photos.synology import SynologyPhotos


REPORT_NAME = "report.md"


def connect_to_nas() -> SynologyPhotos:
    """Log in to the NAS; there is no real client, so stop with a message."""
    raise SystemExit("g2s: logging in to the NAS is not available yet.")


def main(
    argv: Sequence[str] | None = None,
    connect: Callable[[], SynologyPhotos] = connect_to_nas,
) -> int:
    """Run g2s with argv; connect gives the Synology Photos client."""
    parser = argparse.ArgumentParser(
        prog="g2s",
        description="Turn a Google Photos Takeout Export into a NAS Library "
        "in Synology Photos.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    import_cmd = commands.add_parser(
        "import", help="Import a Takeout Export (a folder of ZIPs)."
    )
    import_cmd.add_argument("export", type=Path, help="Folder of the Takeout ZIPs.")
    args = parser.parse_args(argv)

    export: Path = args.export
    if not export.is_dir():
        parser.error(f"{export} is not a folder")

    report = run_import(export, connect()).render()
    print(report)
    # The report sits next to the export folder, beside the other exports.
    (export.resolve().parent / REPORT_NAME).write_text(report, encoding="utf-8")
    return 0
