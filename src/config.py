"""Configuration constants and defaults for the Store Traffic Counter pipeline."""

from __future__ import annotations

from pathlib import Path

# Project paths
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
OUTPUT_DIR: Path = PROJECT_ROOT / "output"
MODELS_DIR: Path = PROJECT_ROOT / "models"

# Supported input formats
VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".avi", ".mov", ".mkv")
IMAGE_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png")

# MOT17 image-sequence conventions
MOT_IMAGE_SUBDIR: str = "img1"
MOT_SEQINFO_FILE: str = "seqinfo.ini"
MOT_FILENAME_PATTERN: str = "%06d"  # e.g. 000001.jpg

# Frame validation defaults
DEFAULT_FRAME_RATE: float = 30.0
MIN_FRAME_WIDTH: int = 320
MIN_FRAME_HEIGHT: int = 240

# Detection defaults
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5

# Tracking defaults
TRACKER_MAX_DISTANCE: float = 50.0  # max centroid distance (px) to match an existing track
TRACKER_MAX_DISAPPEARED: int = 30  # frames a track may be unseen before deregistration

# Tripwire counting defaults
TRIPWIRE_POSITION: float = 0.5  # fraction of frame height for the default horizontal line
TRIPWIRE_HYSTERESIS: int = 5  # px past the line required before a crossing counts
TRIPWIRE_DEBOUNCE_FRAMES: int = 3  # consecutive frames on the new side before a crossing counts

# Visualization
VIS_BOX_THICKNESS: int = 2
VIS_ID_FONT_SCALE: float = 0.6  # ~18px track-ID labels
VIS_HUD_FONT_SCALE: float = 0.8  # ~24px heads-up display text
VIS_FONT_THICKNESS: int = 2
VIS_TRIPWIRE_COLOR: tuple[int, int, int] = (0, 0, 255)  # BGR red
VIS_TRIPWIRE_THICKNESS: int = 3
VIS_HUD_COLOR: tuple[int, int, int] = (255, 255, 255)  # BGR white
VIS_HUD_BG_COLOR: tuple[int, int, int] = (0, 0, 0)  # BGR black
ESC_KEY: int = 27

# Tripwire-proximity box coloring: grey by default, blue near the line, then
# green/red briefly after a crossing (direction-dependent).
VIS_COLOR_DEFAULT: tuple[int, int, int] = (160, 160, 160)  # BGR grey
VIS_COLOR_NEAR_TRIPWIRE: tuple[int, int, int] = (255, 0, 0)  # BGR blue
VIS_COLOR_IN: tuple[int, int, int] = (0, 200, 0)  # BGR green
VIS_COLOR_OUT: tuple[int, int, int] = (0, 0, 255)  # BGR red
# The blue-highlight band scales with depth: narrow for far people (top of
# frame) and wide for near people (bottom), since a fixed pixel distance maps
# to very different real-world distances under perspective.
VIS_TRIPWIRE_PROXIMITY_MIN_PX: int = 30  # band far from camera (top of frame)
VIS_TRIPWIRE_PROXIMITY_MAX_PX: int = 110  # band near the camera (bottom of frame)
VIS_CROSSING_HIGHLIGHT_FRAMES: int = 20  # frames to hold the green/red highlight after a crossing

# Logging
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
