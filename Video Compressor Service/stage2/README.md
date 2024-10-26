# Video Processing Service

Video processing service with client/server architecture for handling various video processing tasks with TCP-based communication.

## Features

- Video compression (automatic optimization)
- Resolution change (custom width and height)
- Aspect ratio change (e.g., 16:9, 4:3)
- Audio extraction to MP3
- GIF creation from video segments
- WebM creation from video segments

## Requirements

- Python 3.8+
- FFmpeg
- psutil>=5.9.0
- ffmpeg-python>=0.2.0
- python-daemon>=3.0.1

## Installation

1. Install FFmpeg:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from FFmpeg official website
```

2. Install Python package:
```bash
# Clone repository
git clone [repository-url]
cd video-processing-service

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate    # Windows

# Install package
pip install -e .
```

## Usage

### Server

1. Start the server:
```bash
python server/server.py
```

2. Server options:
```bash
# Run in foreground mode
python server/server.py --foreground

# Stop the server
python server/server.py --stop
```

### Client

Basic command structure:
```bash
python client/client.py <input_file> --type <process_type> [options]
```

#### 1. Video Compression
```bash
# Basic compression
python client/client.py video.mp4 --type compress

# Specify output file
python client/client.py video.mp4 --type compress --output compressed.mp4
```

#### 2. Resolution Change
```bash
# Convert to 720p
python client/client.py video.mp4 --type resolution --width 1280 --height 720

# Convert to 480p
python client/client.py video.mp4 --type resolution --width 854 --height 480 --output resized.mp4
```

#### 3. Aspect Ratio Change
```bash
# Convert to 16:9
python client/client.py video.mp4 --type aspect_ratio --aspect-ratio "16:9"

# Convert to 4:3
python client/client.py video.mp4 --type aspect_ratio --aspect-ratio "4:3"
```

#### 4. Audio Extraction
```bash
# Basic extraction
python client/client.py video.mp4 --type extract_audio

# Specify output file
python client/client.py video.mp4 --type extract_audio --output audio.mp3
```

#### 5. GIF Creation
```bash
# Create GIF from first 5 seconds
python client/client.py video.mp4 --type gif --start-time 0 --duration 5

# Create GIF from specific segment
python client/client.py video.mp4 --type gif --start-time 10 --duration 3 --output clip.gif
```

#### 6. WebM Creation
```bash
# Create WebM from first 10 seconds
python client/client.py video.mp4 --type webm --start-time 0 --duration 10

# Create WebM from specific segment
python client/client.py video.mp4 --type webm --start-time 30 --duration 5 --output clip.webm
```

#### Additional Client Options
```bash
--output           # Specify output file path
--host            # Server hostname (default: localhost)
--port            # Server port number (default: 9999)
--check-interval  # Progress check interval in seconds (default: 60)
--max-wait-time   # Maximum wait time in seconds (default: 3600)
```

## Performance Requirements

The service ensures:
- Processing of at least 5,000 packets (1,400 bytes each) per second
- 60% CPU resources reserved for video processing
- Automatic storage management (up to 4TB)
- One task per IP address limit

## System Architecture

```
video_processing/
├── common/           # Shared components
│   ├── mmp_protocol.py
│   └── logging_config.py
├── server/          # Server components
│   ├── performance_manager.py
│   ├── video_processor.py
│   ├── task_processor.py
│   ├── storage_manager.py
│   └── server.py
└── client/         # Client components
    └── client.py
```

## Error Handling

Common error messages and solutions:
1. Width and height required for resolution change:
   ```bash
   # Correct usage
   python client/client.py video.mp4 --type resolution --width 1280 --height 720
   ```

2. Aspect ratio format:
   ```bash
   # Correct usage (with quotes)
   python client/client.py video.mp4 --type aspect_ratio --aspect-ratio "16:9"
   ```

3. GIF/WebM time parameters:
   ```bash
   # Both start-time and duration are required
   python client/client.py video.mp4 --type gif --start-time 0 --duration 5
   ```

## Logs

Log files are stored in the `logs` directory:
- `server.log`: Server operations
- `video_processor.log`: Processing operations
- `performance.log`: Performance metrics
- `client.log`: Client operations

## Development

For development installation:
```bash
pip install -e ".[dev]"
```

This includes additional development dependencies for testing and code quality tools.