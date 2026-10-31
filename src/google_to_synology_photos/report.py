"""Report of a run: counts and lists collected during the run, rendered as Markdown.

It holds NAS paths and Album titles, so it stays on the user's machine.
"""

from dataclasses import dataclass, field


@dataclass
class Report:
    """What a run did, and what did not reach the NAS Library."""

    uploaded: int = 0
    videos_converted: int = 0
    albums_created: int = 0
    descriptions_written: int = 0
    comments_written: int = 0
    likes_written: int = 0
    failed_writes: list[str] = field(default_factory=list)
    metadata_not_written: list[str] = field(default_factory=list)
    failed_conversions: list[str] = field(default_factory=list)
    no_file: list[str] = field(default_factory=list)
    orphan_comments: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Return the report as Markdown."""
        lines = [
            "# Import report",
            "",
            f"- Photos and videos uploaded: {self.uploaded}",
            f"- Videos converted: {self.videos_converted}",
            f"- Albums created: {self.albums_created}",
            f"- Photo Descriptions written: {self.descriptions_written}",
            f"- Comments written: {self.comments_written}",
            f"- Likes written: {self.likes_written}",
            "",
            "## Writes that did not stick",
            "",
        ]
        lines += [f"- {w}" for w in self.failed_writes] or ["None."]
        lines += ["", "## Files sent without their missing date or position", ""]
        lines += [f"- {p}" for p in self.metadata_not_written] or ["None."]
        lines += ["", "## Videos that failed to convert, not uploaded", ""]
        lines += [f"- {m}" for m in self.failed_conversions] or ["None."]
        lines += ["", "## Album photos with no file in the export", ""]
        lines += [f"- {n}" for n in self.no_file] or ["None."]
        lines += ["", "## Comments that match no photo", ""]
        # One list item each: the line breaks of a Comment stay in the NAS Library.
        lines += [f"- {c}".replace("\n", " ") for c in self.orphan_comments] or [
            "None."
        ]
        return "\n".join(lines) + "\n"
