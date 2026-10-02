# Store Traffic Counter

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-In%20Development-yellow?style=flat-square)](#)

*Real-time customer counting system for retail analytics using computer vision and object tracking.*

<div align="center">
  <p><strong>Detect • Track • Count • Analyze</strong></p>
</div>

## Overview

Store Traffic Counter is a proof-of-concept system for counting customers entering and exiting a retail space using computer vision. It processes video feeds (or image sequences) to detect individuals, tracks them across frames, and visualizes the results in real time. Virtual tripwire crossing and in/out counting are the next milestone.

This project leverages modern deep learning models (YOLOv8, OpenCV) combined with centroid-based tracking. It is developed against the MOT17 pedestrian benchmark and designed with containerization in mind for easy deployment.

## Features

**Implemented:**
- **Person Detection** - Interchangeable detectors: YOLOv8 (Ultralytics) or OpenCV's built-in HOG + SVM pedestrian detector
- **Multi-Object Tracking** - Centroid-based tracking for consistent person IDs across frames, with distance gating and a disappearance timeout
- **Flexible Input** - Standard video files (MP4, AVI, MOV, MKV) *and* MOT17-style image sequences (`img1/%06d.jpg` + `seqinfo.ini`)
- **Real-time Visualization** - Live window and/or saved annotated video with ID-colored boxes, confidence labels, and a heads-up display (frame number, FPS, track counts)

**In progress / planned:**
- **Virtual Tripwire Counting** - Entry/exit counting from line crossings (overlay hooks already in place)
- **Metrics Logging** - CSV event logs and JSON summary metrics
- **Docker Support** - Containerized deployment for reproducibility
- **Family Detection** - Grouping related individuals to improve conversion metrics
- **Heatmaps** - Spatial analysis of customer movement patterns

## Tech Stack

- **Language:** Python 3.12+ (runs on 3.10+)
- **Vision Models:** YOLOv8 via [Ultralytics](https://docs.ultralytics.com/), or OpenCV HOG + SVM
- **Core Libraries:**
  - `opencv-python` - Video/image I/O, tracking math, and visualization
  - `numpy` - Numerical computing
  - `ultralytics` - YOLOv8 detection (pulls in `torch`)
- **Input:** Video files (MP4, AVI, MOV, MKV) or MOT17 image sequences
- **Output:** Real-time display and/or annotated MP4; structured logs planned

## Architecture

The system follows a classic computer vision pipeline:

```
Video / Image Sequence Input
    ↓
[Person Detection] → Bounding boxes with confidence scores
    ↓
[Centroid Tracking] → Unique ID assignment per person
    ↓
[Visualization] → Live display + annotated video
    ↓
[Tripwire Crossing + Logging] → In/out counts + data export (planned)
```

**Key Components:**
- **Detector** (`detector.py`): Identifies people in each frame (YOLOv8 or OpenCV HOG)
- **Tracker** (`tracker.py`): Associates detections across frames using centroid distance
- **Visualizer** (`visualizer.py`): Renders overlays for live display and annotated video
- **Counter / Logger** *(planned)*: Tripwire crossing detection and structured data export

## Getting Started

### Prerequisites

- Python 3.12+ (tested on 3.10)
- Docker (optional; planned)
- A video file or a MOT17-style image-sequence directory

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/danielbsimpson/store_traffic_counter.git
   cd store_traffic_counter
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   The YOLO weights (`yolov8n.pt`) download automatically on first run.

### Docker Setup (Optional)

> [!NOTE]
> Docker packaging is planned (see the roadmap). For now, run the pipeline directly in a virtual environment.

## Usage

### Basic Example

Process a video file or image-sequence directory and display the annotated stream:

```bash
python src/main.py --video path/to/video.mp4 --display
```

### Command-Line Options

```
python src/main.py [OPTIONS]

OPTIONS:
  --video PATH              Video file or MOT17 image-sequence directory (required)
  --output DIR              Output directory (default: ./output)
  --model {yolo,opencv}     Detector to use (default: yolo)
  --confidence FLOAT        Detection confidence threshold 0.0-1.0 (default: 0.5)
  --device {cpu,gpu}        Processing device for YOLO (default: cpu)
  --display                 Show the real-time window (press ESC to quit)
  --save-video              Save an annotated MP4 to the output directory
  --max-frames INT          Process at most N frames (0 = all; useful for quick checks)
  --verbose                 Enable DEBUG-level logging
  --help                    Show this help message
```

### Example Workflows

**Run on the MOT17 demo sequence and watch live:**
```bash
python src/main.py --video data/MOT17-09-DPM --display
```

**Save a short annotated clip for review:**
```bash
python src/main.py --video data/MOT17-09-DPM --save-video --max-frames 60
```

**Compare detectors / tune accuracy:**
```bash
python src/main.py --video footage.mp4 --model opencv --confidence 0.6
python src/main.py --video footage.mp4 --model yolo --device gpu
```

## Demo Dataset

The pipeline is developed and demoed against the [MOT17](https://motchallenge.net/data/MOT17) pedestrian tracking benchmark. Sequences are provided as numbered JPEG frames plus a `seqinfo.ini`; the loader reads them directly (no conversion needed).

- **MOT17-09** - static camera, moderate density (primary demo)
- **MOT17-04** - elevated viewpoint
- **MOT17-11** - busy shopping mall

> [!NOTE]
> MOT17 is licensed CC BY-NC-SA (non-commercial). Credit **MOTChallenge** when embedding demo clips, and keep usage non-commercial.

## Output Format

### Real-time Display / Annotated Video

With `--display` and/or `--save-video`, each frame is overlaid with:
- Person bounding boxes, color-coded per tracking ID
- Track ID and detection confidence labels
- A heads-up display: active/total track counts (top-left), frame number and processing FPS (top-right)

Saved videos are written to `output/annotated_<name>.mp4`.

### Data Export (planned)

CSV event logs and a JSON metrics summary are planned alongside tripwire counting:

```csv
timestamp,event_type,person_id,direction,cumulative_in,cumulative_out
```

```json
{ "total_in": 0, "total_out": 0, "net_occupancy": 0 }
```

## Performance

The PoC prioritizes **accuracy over speed**. Observed on the MOT17-09 sequence (1920×1080):
- **YOLOv8n inference:** ~45 ms/frame on CPU (~240 ms/frame for larger input batches); real-time on GPU
- **Typical scene:** 6-8 tracked persons per frame
- **Tracking:** stable IDs via centroid matching with a 50px gate and 30-frame disappearance timeout

For production, consider GPU acceleration, model optimization (quantization/pruning) for edge devices, and calibration per store layout.

## Project Structure

```
store_traffic_counter/
├── src/
│   ├── main.py           # CLI entry point and pipeline orchestration
│   ├── config.py         # Constants and defaults
│   ├── video_loader.py   # VideoProcessor: video files + MOT17 image sequences
│   ├── detector.py       # Detector base class, YOLODetector, OpenCVDetector
│   ├── tracker.py        # CentroidTracker for multi-object tracking
│   └── visualizer.py     # VideoVisualizer overlay rendering
├── tests/                # Pytest unit tests
├── plan/                 # Implementation plan
├── data/                 # Input video / image-sequence samples (gitignored)
├── output/               # Generated annotated videos and logs (gitignored)
├── requirements.txt      # Python dependencies
├── TODO.md               # Progress tracker
└── README.md             # This file
```

## Future Roadmap

- [ ] Family grouping algorithm using spatial proximity and temporal consistency
- [ ] Heatmap generation from trajectory data
- [ ] REST API for remote processing requests
- [ ] Web-based analytics dashboard
- [ ] Multi-camera support with cross-camera tracking
- [ ] Model fine-tuning on retail-specific datasets
- [ ] Performance benchmarking on edge devices (Jetson, RPi)

## Troubleshooting

> [!TIP]
> Enable debug logging for detailed troubleshooting:
> ```bash
> python src/main.py --video footage.mp4 --verbose
> ```

**Issue: Low detection accuracy**
- Increase `--confidence` threshold incrementally
- Ensure adequate lighting in video
- Test with different model options (`yolo` vs `opencv`)

**Issue: Memory errors with large videos**
- Process in chunks or reduce video resolution
- Switch to lightweight model (YOLOv8n instead of YOLOv8s)

**Issue: Tracking ID changes rapidly**
- Adjust the centroid distance threshold (`TRACKER_MAX_DISTANCE`) in `src/config.py`
- Check for occlusion or lighting changes in footage

**Issue: `module 'cv2' has no attribute 'HOGDescriptor'`**
- OpenCV 5.0 removed the HOG pedestrian detector; this project pins `opencv-python>=4.8,<5`. Reinstall with `pip install -r requirements.txt`.

**Issue: YOLO is slow**
- Use `--device gpu` if a CUDA GPU is available, or `--max-frames` for quick checks
- The lightweight `yolov8n` weights are used by default

## Disclaimer

This is a proof-of-concept project for portfolio demonstration. The system has been tested on retail footage but may require calibration for specific store layouts, camera angles, and lighting conditions. Accuracy may vary depending on:
- Video quality and resolution
- Lighting conditions
- Store layout and camera placement
- Customer density and clothing colors

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

## Connect

- GitHub: [@danielbsimpson](https://github.com/danielbsimpson)
- Portfolio: [danielbsimpson.com](https://danielbsimpson.com)

---

**Inspired by previous work:** [Facial Recognition and Mask Detection](https://github.com/danielbsimpson/facial_recognition_and_mask_detection) - Using CV2 for detection and CNN classifiers.
