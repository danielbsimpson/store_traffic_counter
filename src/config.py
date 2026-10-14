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
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.25
# YOLO inference resolution. Frames are letterboxed to this long-edge size
# before inference; larger values recover small, distant people in high-res
# (e.g. 4K) scenes at the cost of speed. 0 keeps Ultralytics' 640 default.
DEFAULT_YOLO_IMGSZ: int = 1280

# Tracking defaults
TRACKER_MAX_DISTANCE: float = 50.0  # max centroid distance (px) to match an existing track
TRACKER_MAX_DISAPPEARED: int = 30  # frames a track may be unseen before deregistration

# Static-object suppression. A low confidence threshold admits fixed scene
# objects that look person-like - store-window mannequins, promotional
# standees, posters, signage - as phantom detections. Unlike pedestrians they
# barely move, so a long-lived track whose foot point stays within
# ``TRACK_STATIC_MAX_DISPLACEMENT`` px over the last ``TRACK_STATIC_WINDOW``
# frames is flagged ``is_static`` and excluded from counting and overlays.
TRACK_STATIC_WINDOW: int = 20  # trailing frames of motion history to assess
TRACK_STATIC_MAX_DISPLACEMENT: float = 40.0  # net px over the window below which a track is static

# Tripwire counting defaults
TRIPWIRE_POSITION: float = 0.5  # fraction of frame height for the default horizontal line
TRIPWIRE_HYSTERESIS: int = 5  # px past the line required before a crossing counts
TRIPWIRE_DEBOUNCE_FRAMES: int = 3  # consecutive frames on the new side before a crossing counts

# Doorway reinforcement (storefront counters only). People entering a store
# walk up to the door and their detection vanishes; people exiting materialize
# at the door and walk out. A track that disappears within
# ``TRIPWIRE_DOOR_BAND_PX`` of the line (and stays gone for
# ``TRIPWIRE_DISAPPEAR_FRAMES`` frames) is counted IN; a track that first
# appears within that band and steps to the outside is counted OUT. These catch
# entries/exits that never complete a clean two-sided crossing at the threshold.
TRIPWIRE_DOOR_BAND_PX: int = 90  # distance to the line segment that counts as "at the door"
# Matches TRACKER_MAX_DISAPPEARED so the counter only finalizes a vanish once
# the tracker itself would drop the track; shorter windows reset a track's
# crossing history across brief occlusions on busy frontages.
TRIPWIRE_DISAPPEAR_FRAMES: int = TRACKER_MAX_DISAPPEARED  # frames gone before counting IN
# Guards against false reinforcement on busy frontages: ignore appear/disappear
# within this margin of the frame border (people entering/leaving the camera's
# field of view, not a store), and require a disappearing track to have moved at
# least this far *toward* the store (inward perpendicular travel) to count IN -
# which rejects occlusion dropouts of people walking parallel to the frontage.
TRIPWIRE_FRAME_EDGE_MARGIN_PX: int = 80  # border band where FOV entry/exit is assumed
TRIPWIRE_DOOR_APPROACH_PX: int = 25  # min inward travel to treat a vanish as an entry
TRIPWIRE_DOOR_MOTION_WINDOW: int = 6  # trailing foot points used to gauge approach direction

# Storefront (multi-tripwire) counting
# Each storefront owns its own named tripwire and independent in/out tally. The
# ``<video-stem>.storefronts.json`` convention lets a sibling file beside an
# input video define its storefronts without passing --storefronts explicitly.
STOREFRONTS_SUFFIX: str = ".storefronts.json"

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

# Per-storefront tripwire colors, cycled in order so each named line is visually
# distinct from its neighbours (BGR).
VIS_STOREFRONT_COLORS: tuple[tuple[int, int, int], ...] = (
    (0, 0, 255),      # red
    (0, 200, 255),    # amber
    (0, 220, 0),      # green
    (255, 128, 0),    # blue
    (255, 0, 200),    # magenta
    (220, 220, 0),    # cyan
)
VIS_STOREFRONT_LABEL_FONT_SCALE: float = 0.7  # ~21px storefront name labels

# Logging
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
