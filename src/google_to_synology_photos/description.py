"""Photo Description builder: the text shown with a photo in the NAS Library."""

from google_to_synology_photos.takeout import Photo


def photo_description(photo: Photo) -> str:
    """Return the Photo Description of photo: its Caption."""
    return photo.caption
