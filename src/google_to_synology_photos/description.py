"""Photo Description builder: the text shown with a photo in the NAS Library.

The layout is fixed here, and pinned by tests. A Photo Description is made of
blocks separated by one blank line: the Album text on an Album's oldest photo,
then the Caption, then the Comments and Likes. Album texts, and Comments and
Likes, get a line with their Album's title only when more than one Album brings
some.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass

from google_to_synology_photos.takeout import Album, Comment, Export, Reactions


BLOCK_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class PhotoDescription:
    """The text of a photo, and how many Comments and Likes it holds."""

    text: str
    comments: int
    likes: int


def comment_line(comment: Comment) -> str:
    """Return a Comment as `<author>, <YYYY-MM-DD>: <text>`, in UTC.

    A Comment with no author starts at its date.
    """
    date = f"{comment.when:%Y-%m-%d}"
    head = f"{comment.author}, {date}" if comment.author else date
    return f"{head}: {comment.text}"


def _reaction_lines(reactions: Reactions) -> list[str]:
    """Return the lines of the Comments, then the line of the Likes."""
    lines = [comment_line(c) for c in reactions.comments]
    if reactions.likes:
        lines.append(f"❤️ {', '.join(reactions.likes)}")
    return lines


def _album_text(album: Album) -> str:
    """Return the Album's description, its Comments, Likes and orphan Comments."""
    orphans = [comment_line(c) for c in album.orphans]
    lines = "\n".join([*_reaction_lines(album.reactions), *orphans])
    return BLOCK_SEPARATOR.join(filter(None, [album.description, lines]))


def _titled_blocks(blocks: list[tuple[str, str]]) -> list[str]:
    """Return one block per Album, under its title if there are several."""
    if len(blocks) == 1:
        return [blocks[0][1]]
    return [f"{title}\n{block}" for title, block in blocks]


def photo_descriptions(export: Export) -> dict[str, PhotoDescription]:
    """Return the Photo Description of every photo of export, by url.

    The oldest photo of an Album is chosen by date taken, then by url, so that
    the same export always gives the same text.
    """
    album_texts_of: dict[str, list[tuple[str, str]]] = defaultdict(list)
    reactions_of: dict[str, list[tuple[str, str]]] = defaultdict(list)
    comments: Counter[str] = Counter()
    likes: Counter[str] = Counter()
    for album in export.albums:
        if album.urls and (text := _album_text(album)):
            oldest = min(album.urls, key=lambda u: (export.photos[u].taken, u))
            album_texts_of[oldest].append((album.title, text))
            comments[oldest] += len(album.reactions.comments) + len(album.orphans)
            likes[oldest] += len(album.reactions.likes)
        for url, reactions in album.photo_reactions.items():
            lines = "\n".join(_reaction_lines(reactions))
            reactions_of[url].append((album.title, lines))
            comments[url] += len(reactions.comments)
            likes[url] += len(reactions.likes)

    descriptions = {}
    for url, photo in export.photos.items():
        blocks = [
            *_titled_blocks(album_texts_of[url]),
            photo.caption,
            *_titled_blocks(reactions_of[url]),
        ]
        text = BLOCK_SEPARATOR.join(filter(None, blocks))
        descriptions[url] = PhotoDescription(text, comments[url], likes[url])
    return descriptions
