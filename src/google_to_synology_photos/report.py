"""Report of a run: counts and lists collected during the run, rendered as Markdown.

It holds NAS paths and Album titles, so it stays on the user's machine.
"""

from dataclasses import dataclass, field


@dataclass
class Report:
    """What a run did, the writes that did not stick, the files Google left out."""

    uploaded: int = 0
    albums_created: int = 0
    descriptions_written: int = 0
    failed_writes: list[str] = field(default_factory=list)
    no_file: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Return the report as Markdown."""
        lines = [
            "# Import report",
            "",
            f"- Photos and videos uploaded: {self.uploaded}",
            f"- Albums created: {self.albums_created}",
            f"- Photo Descriptions written: {self.descriptions_written}",
            "",
            "## Writes that did not stick",
            "",
        ]
        lines += [f"- {w}" for w in self.failed_writes] or ["None."]
        lines += ["", "## Album photos with no file in the export", ""]
        lines += [f"- {n}" for n in self.no_file] or ["None."]
        return "\n".join(lines) + "\n"
