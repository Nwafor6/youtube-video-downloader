# YouTube Video & Playlist Downloader

A lightweight, web-based tool for downloading YouTube videos and playlists, powered by [FastAPI](https://fastapi.tiangolo.com/) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Features

- **Web UI:** A simple HTML/JS interface to start downloads without needing the command line.
- **Real-Time Logs:** View download progress, status, and error logs directly in the browser via Server-Sent Events (SSE).
- **Folder Picker:** Native folder selection dialog (using `tkinter`) to easily choose where to save your videos.
- **Smart Resuming:** Keeps a `.download_archive.txt` to automatically skip already downloaded videos in a playlist.
- **Auto-Updates:** Automatically checks and updates `yt-dlp` to the latest version before downloading, minimizing 403 Forbidden errors.
- **Background Tasks:** Downloads happen in the background, keeping the UI responsive.

## Prerequisites

- Python 3.7+
- (Optional but recommended) [FFmpeg](https://ffmpeg.org/download.html) installed on your system for merging high-quality video and audio formats.

## Installation

1. **Clone or navigate to the directory:**
   ```bash
   cd fast-api-youtub-playlist-downloader
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn yt-dlp python-multipart
   ```

## Usage

1. **Start the server:**
   ```bash
   python main.py
   ```
   *(Alternatively, use `uvicorn main:app --reload` for development)*

2. **Open the Web UI:**
   Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser.

3. **Download:**
   - Paste a YouTube video or playlist URL.
   - Click **Browse...** to select your output folder.
   - Click **Start Download**.
   - Watch the logs stream in real-time as your videos are saved!

