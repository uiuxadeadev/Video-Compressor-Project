# Video Processing Service

Video processing service with client/server architecture.

## Features

- Video compression
- Resolution change
- Aspect ratio change
- Audio extraction
- GIF creation
- WebM creation

## Installation

```bash
pip install -e .
```

## Usage

### Server

```bash
python server/server.py
```

### Client

```bash
python client/client.py video.mp4 --type compress
```

## Requirements

- Python 3.8+
- FFmpeg