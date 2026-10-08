"""Paths and constants for beat50. One place to tune the settings."""
import os
from pathlib import Path

# User data lives outside the code so it survives app updates. BEAT50_DATA overrides it for development.
# The folder keeps the app's name before 3.0 (beatcrate), so the data of earlier versions is still found.
DATA = Path(os.environ.get("BEAT50_DATA") or Path.home() / "Library" / "Application Support" / "beatcrate")
SESSION_FILE = DATA / "session.json"
LIBRARY_FILE = DATA / "library.json"
PROFILE_FILE = DATA / "profile.json"
CANDIDATES_FILE = DATA / "candidates.json"
CRATES_DIR = DATA / "crates"
MARKS_DIR = DATA / "marks"
STATE_FILE = DATA / "state.json"
LOCK_FILE = DATA / ".lock"
CONSENT_FILE = DATA / "consent.json"

# Local app: reachable from this Mac only
APP_HOST = "127.0.0.1"
APP_PORT = 8765

API = "https://api.beatport.com/v4"
STORE = "https://www.beatport.com"

# Discovery
WINDOW_DAYS = 31
PER_PAGE = 1000
TOP_LABELS = 50
TOP_ARTISTS = 100
TOP_GENRES = 5  # top-100 chart per genre
MAX_REQUESTS = 60  # a safety net, not an operating limit: comma-separated filters need few requests

# Selection
CRATE_SIZE = 50
MAX_PER_LABEL = 3
MAX_PER_ARTIST = 2

# Genre preferences (the Genres dialog): what each level multiplies a genre's profile weight by. 0 leaves it out.
GENRE_LEVELS = (0, 0.5, 1, 2, 4)
GENRES_SHOWN = 10  # the profile's top genres listed in the dialog

# Profile
HALFLIFE_MONTHS = 18
ORIGIN_PURCHASE = 1.0
ORIGIN_PLAYLIST = 0.6

# Score
W_LABEL = 0.35
W_ARTIST = 0.30
W_GENRE = 0.20  # Beatport's fine-grained genre; sub_genre is almost always null
W_BPM = 0.10
W_KEY = 0.05
