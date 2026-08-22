#!/usr/bin/env python3
"""
YouTube Playlist Downloader
Playlist ID: PLdpzxOOAlwvIc1TjTwopNSjRJkzES2ZXk

Requirements:
    pip install yt-dlp fastapi uvicorn python-multipart

Optional (for better audio conversion):
    Install ffmpeg: https://ffmpeg.org/download.html
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import uuid

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()

active_tasks = {}

def seed_archive_from_existing(playlist_url, output_dir, logger=print):
    """
    One-time scan: match existing downloaded files against the playlist
    and write their video IDs into the archive file so yt-dlp skips them.
    """
    os.makedirs(output_dir, exist_ok=True)
    archive_file = os.path.join(output_dir, ".download_archive.txt")

    # If archive already exists, nothing to seed
    if os.path.exists(archive_file):
        return

    # Get list of existing files (ignore .part files — those are incomplete)
    existing_files = [
        f for f in os.listdir(output_dir)
        if not f.endswith(".part") and os.path.isfile(os.path.join(output_dir, f))
    ]
    if not existing_files:
        return

    print("Seeding download archive from existing files...")
    print(f"  Found {len(existing_files)} completed file(s) on disk.")

    # Extract playlist index numbers from filenames (e.g. "012 - Title.mp4" → "12")
    existing_indices = set()
    for f in existing_files:
        match = re.match(r"^(\d+)\s*-\s*", f)
        if match:
            existing_indices.add(int(match.group(1)))

    if not existing_indices:
        logger("  Could not match any files to playlist indices — skipping seed.")
        return

    # Fetch playlist metadata (flat = fast, no downloading)
    logger("  Fetching playlist metadata to look up video IDs...")
    result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", playlist_url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger("  ⚠ Could not fetch playlist info — skipping seed.")
        return

    playlist_info = json.loads(result.stdout)
    entries = playlist_info.get("entries", [])

    # Match and write
    matched = []
    for entry in entries:
        idx = entry.get("playlist_index") or entry.get("playlist_autonumber")
        vid_id = entry.get("id")
        if idx is not None and int(idx) in existing_indices and vid_id:
            matched.append(f"youtube {vid_id}")

    if matched:
        with open(archive_file, "w") as f:
            f.write("\n".join(matched) + "\n")
        logger(f"  ✓ Wrote {len(matched)} video(s) to archive — they will be skipped.\n")
    else:
        logger("  No matches found between existing files and playlist.\n")


def check_yt_dlp(logger=print):
    """Check if yt-dlp is installed and up to date, install/upgrade if needed."""
    try:
        logger("Checking for yt-dlp updates...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], capture_output=True, check=True)
        logger("✓ yt-dlp is installed and up to date.")
    except Exception as e:
        logger(f"Error checking/updating yt-dlp: {str(e)}")


def download_playlist(
    playlist_url,
    output_dir,
    format_choice="video",   # "video", "audio", or "best"
    quality="best",          # "best", "1080", "720", "480", "360"
    add_metadata=True,
    add_thumbnail=True,
    skip_existing=True,
    logger=print
):
    """
    Download a YouTube playlist.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Output filename template
    output_template = os.path.join(output_dir, "%(playlist_index)s - %(title)s.%(ext)s")

    cmd = [sys.executable, "-m", "yt_dlp", playlist_url, "-o", output_template]

    # Format selection
    if format_choice == "audio":
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    elif format_choice == "video":
        if quality == "best":
            cmd += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]
        else:
            cmd += ["-f", f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]"]
        cmd += ["--merge-output-format", "mp4"]
    else:
        cmd += ["-f", "best"]

    # Metadata & thumbnail
    if add_metadata:
        cmd += ["--add-metadata"]
    if add_thumbnail:
        cmd += ["--embed-thumbnail"]

    # Skip already downloaded files
    if skip_existing:
        cmd += ["--no-overwrites", "--continue"]
        # Archive file tracks downloaded video IDs — enables instant resume
        archive_file = os.path.join(output_dir, ".download_archive.txt")
        cmd += ["--download-archive", archive_file]

    # Progress and retries
    cmd += [
        "--retries", "5",
        "--fragment-retries", "5",
        "--newline",          # One progress line per fragment (cleaner output)
        "--ignore-errors",    # Skip unavailable videos instead of stopping
    ]

    logger(f"\n{'='*60}")
    logger(f"Downloading to: {os.path.abspath(output_dir)}")
    logger(f"Format: {format_choice} | Quality: {quality}")
    logger(f"{'='*60}\n")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    
    for line in iter(process.stdout.readline, ''):
        logger(line.rstrip('\n'))

    process.wait()

    if process.returncode == 0:
        logger("\n✓ Download complete!")
    else:
        logger("\n⚠ Download finished with some errors (skipped videos may be unavailable).")


def run_download_task(task_id: str, url: str, folder: str, loop, q: asyncio.Queue):
    def logger(msg):
        print(msg)
        asyncio.run_coroutine_threadsafe(q.put(msg), loop)
        
    try:
        check_yt_dlp(logger=logger)
        seed_archive_from_existing(url, folder, logger=logger)
        download_playlist(
            playlist_url=url,
            output_dir=folder,
            format_choice="video",
            quality="best",
            add_metadata=True,
            add_thumbnail=True,
            skip_existing=True,
            logger=logger,
        )
    except Exception as e:
        logger(f"Exception during download: {str(e)}")
    finally:
        asyncio.run_coroutine_threadsafe(q.put(None), loop)


html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background-color: #f9f9f9; }
        .container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h2 { margin-top: 0; color: #333; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        input[type="text"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; font-size: 16px; }
        .folder-row { display: flex; gap: 8px; }
        .folder-row input { flex: 1; }
        .folder-row button { width: auto; padding: 10px 16px; background-color: #555; }
        .folder-row button:hover { background-color: #333; }
        button { padding: 12px 20px; background-color: #ff0000; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { background-color: #cc0000; }
        #message { margin-top: 20px; font-weight: bold; color: #28a745; text-align: center; }
        #error { margin-top: 20px; font-weight: bold; color: #dc3545; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h2>YouTube Downloader</h2>
        <form id="downloadForm">
            <div class="form-group">
                <label for="url">YouTube Link (Video or Playlist):</label>
                <input type="text" id="url" name="url" required placeholder="https://www.youtube.com/watch?v=...">
            </div>
            <div class="form-group">
                <label for="folder">Output Folder:</label>
                <div class="folder-row">
                    <input type="text" id="folder" name="folder" required value="./downloads">
                    <button type="button" id="browseBtn">Browse...</button>
                </div>
            </div>
            <button type="submit">Start Download</button>
        </form>
        <div id="message"></div>
        <div id="error"></div>
        <pre id="logs" style="background: #eee; padding: 10px; height: 300px; overflow-y: scroll; display: none; font-size: 12px; white-space: pre-wrap; margin-top: 20px;"></pre>
    </div>

    <script>
        document.getElementById('browseBtn').addEventListener('click', async () => {
            const errEl = document.getElementById('error');
            const msgEl = document.getElementById('message');
            errEl.textContent = "";
            msgEl.textContent = "Opening folder picker...";
            try {
                const response = await fetch('/browse-folder', { method: 'POST' });
                const result = await response.json();
                msgEl.textContent = "";
                if (response.ok && result.folder) {
                    document.getElementById('folder').value = result.folder;
                } else if (result.detail) {
                    errEl.textContent = result.detail;
                }
                // If user cancelled the dialog, result.folder will be empty — leave input untouched.
            } catch (error) {
                msgEl.textContent = "";
                errEl.textContent = "Could not open folder picker: " + error.message;
            }
        });

        document.getElementById('downloadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = document.getElementById('url').value;
            const folder = document.getElementById('folder').value;
            const msgEl = document.getElementById('message');
            const errEl = document.getElementById('error');
            const logsEl = document.getElementById('logs');

            msgEl.textContent = "Starting download...";
            errEl.textContent = "";
            logsEl.style.display = "block";
            logsEl.textContent = "";

            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({url, folder})
                });
                const result = await response.json();

                if (response.ok) {
                    msgEl.textContent = result.message;
                    
                    if (result.task_id) {
                        const evtSource = new EventSource(`/stream/${result.task_id}`);
                        evtSource.onmessage = function(event) {
                            const data = JSON.parse(event.data);
                            logsEl.textContent += data.log + "\\n";
                            logsEl.scrollTop = logsEl.scrollHeight;
                        };
                        evtSource.onerror = function() {
                            evtSource.close();
                        };
                    }
                } else {
                    errEl.textContent = result.detail || "An error occurred";
                    msgEl.textContent = "";
                }
            } catch (error) {
                errEl.textContent = "An error occurred: " + error.message;
                msgEl.textContent = "";
            }
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    return html_content

@app.post("/download")
async def start_download(background_tasks: BackgroundTasks, url: str = Form(...), folder: str = Form(...)):
    task_id = str(uuid.uuid4())
    q = asyncio.Queue()
    active_tasks[task_id] = q
    loop = asyncio.get_running_loop()
    background_tasks.add_task(run_download_task, task_id, url, folder, loop, q)
    return {"message": f"Download started in the background! Saving to '{folder}'.", "task_id": task_id}

@app.get("/stream/{task_id}")
async def stream_logs(task_id: str):
    q = active_tasks.get(task_id)
    if not q:
        raise HTTPException(status_code=404, detail="Task not found")

    async def log_generator():
        try:
            while True:
                msg = await q.get()
                if msg is None:
                    active_tasks.pop(task_id, None)
                    break
                yield f"data: {json.dumps({'log': msg})}\n\n"
        except asyncio.CancelledError:
            active_tasks.pop(task_id, None)

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.post("/browse-folder")
async def browse_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog

        # Hide the main window
        root = tk.Tk()
        root.withdraw()
        # Bring to front
        root.attributes('-topmost', True)
        
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        root.destroy()
        
        if folder_path:
            return {"folder": folder_path}
        else:
            return {"folder": ""}
    except ImportError:
        raise HTTPException(status_code=501, detail="tkinter is not installed or available for folder browsing. Please type the path manually.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open folder picker: {str(e)}")

if __name__ == "__main__":
    print("Starting server at http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
