import re
from urllib.parse import urlsplit


SPOTIFY_TYPES = "track|album|playlist"
SPOTIFY_ID = "[A-Za-z0-9]{22}"
SPOTIFY_PATH = re.compile(
    rf"/(?:intl-[a-zA-Z-]+/)?(?:embed/)?({SPOTIFY_TYPES})/({SPOTIFY_ID})/?"
)
SPOTIFY_URI = re.compile(rf"spotify:({SPOTIFY_TYPES}):({SPOTIFY_ID})")

def parse_spotify_link(link):
    """Return an item type and ID, or None for a different music source."""
    if link.lower().startswith("spotify:"):
        match = SPOTIFY_URI.fullmatch(link)
    else:
        url = urlsplit(link)
        if url.hostname not in {"open.spotify.com", "spotify.link", "spotify.com", "www.spotify.com"}:
            return None
        match = (
            SPOTIFY_PATH.fullmatch(url.path)
            if url.scheme == "https" and url.netloc.lower() == "open.spotify.com"
            else None
        )

    if not match:
        raise ValueError("Paste a full Spotify track, album, or playlist link.")
    return match.groups()


