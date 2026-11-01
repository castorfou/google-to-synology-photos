"""Report of a run: counts and lists collected during the run, rendered as Markdown.

It holds NAS paths and Album titles, so it stays on the user's machine.
"""

from dataclasses import dataclass, field


ASK_FOR_ALBUM_DOWNLOAD = (
    'Use "Download all" on these Albums in Google Photos, put each ZIP in the '
    "`album-downloads` folder next to the export folders, and run g2s again."
)


@dataclass
class Report:
    """What a run did, and what did not reach the NAS Library."""

    uploaded: int = 0
    replaced: int = 0
    moved: int = 0
    already_on_nas: int = 0
    videos_converted: int = 0
    albums_created: int = 0
    albums_renamed: int = 0
    descriptions_written: int = 0
    descriptions_rewritten: int = 0
    comments_written: int = 0
    likes_written: int = 0
    failed_writes: list[str] = field(default_factory=list)
    metadata_not_written: list[str] = field(default_factory=list)
    failed_conversions: list[str] = field(default_factory=list)
    no_file: list[str] = field(default_factory=list)
    orphan_comments: list[str] = field(default_factory=list)
    sure_gaps: list[str] = field(default_factory=list)
    # How many photos joined the Album of each Album Download, by its name.
    album_downloads: dict[str, int] = field(default_factory=dict)
    unknown_album_downloads: list[str] = field(default_factory=list)
    undated_files: list[str] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        """Tell whether the run left nothing to try again."""
        return not (self.failed_writes or self.failed_conversions)

    def render(self) -> str:
        """Return the report as Markdown."""
        lines = [
            "# Import report",
            "",
            f"- Photos and videos uploaded: {self.uploaded}",
            f"- Files replaced: {self.replaced}",
            f"- Files moved: {self.moved}",
            f"- Already on the NAS: {self.already_on_nas}",
            f"- Videos converted: {self.videos_converted}",
            f"- Albums created: {self.albums_created}",
            f"- Albums renamed: {self.albums_renamed}",
            f"- Photo Descriptions written: {self.descriptions_written}",
            f"- Photo Descriptions rewritten: {self.descriptions_rewritten}",
            f"- Comments written: {self.comments_written}",
            f"- Likes written: {self.likes_written}",
            f"- Album Downloads used: {len(self.album_downloads)}",
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
        lines += ["", "## Shared Albums where photos are surely missing", ""]
        if self.sure_gaps:
            lines += [ASK_FOR_ALBUM_DOWNLOAD, ""]
        lines += [f"- {a}" for a in self.sure_gaps] or ["None."]
        lines += ["", "## Album Downloads", ""]
        lines += [
            f"- {folder} (photos added: {added})"
            for folder, added in self.album_downloads.items()
        ] or ["None."]
        lines += ["", "## Album Downloads that match no Album", ""]
        lines += [f"- {f}" for f in self.unknown_album_downloads] or ["None."]
        lines += ["", "## Album Download files with no date, not added", ""]
        lines += [f"- {f}" for f in self.undated_files] or ["None."]
        return "\n".join(lines) + "\n"
