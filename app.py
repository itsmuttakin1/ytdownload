#!/usr/bin/env python3
# app.py — YouTube Downloader Web App (Flask + yt-dlp)
# Deploy: Render.com (free tier)

import os
import tempfile
import threading
import yt_dlp
from flask import Flask, request, jsonify, send_file, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YT Downloader</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', sans-serif;
      background: #0f0f0f;
      color: #f1f1f1;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card {
      background: #1e1e1e;
      border: 1px solid #333;
      border-radius: 12px;
      padding: 40px;
      width: 100%;
      max-width: 520px;
    }
    h1 { font-size: 22px; margin-bottom: 8px; color: #ff4444; }
    p.sub { color: #888; font-size: 13px; margin-bottom: 28px; }
    label { display: block; font-size: 13px; color: #aaa; margin-bottom: 6px; }
    input[type=text], select {
      width: 100%;
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid #333;
      background: #111;
      color: #f1f1f1;
      font-size: 14px;
      margin-bottom: 16px;
      outline: none;
    }
    input[type=text]:focus, select:focus { border-color: #ff4444; }
    button {
      width: 100%;
      padding: 13px;
      background: #ff4444;
      color: white;
      font-size: 15px;
      font-weight: 600;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.2s;
    }
    button:hover { background: #cc3333; }
    button:disabled { background: #555; cursor: not-allowed; }
    #status {
      margin-top: 18px;
      font-size: 13px;
      color: #aaa;
      text-align: center;
      min-height: 20px;
    }
    #status.error { color: #ff6b6b; }
    #status.success { color: #51cf66; }
    .spinner {
      display: inline-block;
      width: 14px; height: 14px;
      border: 2px solid #555;
      border-top-color: #ff4444;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      vertical-align: middle;
      margin-right: 6px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
<div class="card">
  <h1>▶ YT Downloader</h1>
  <p class="sub">YouTube video/audio direct download</p>

  <label>YouTube URL</label>
  <input type="text" id="url" placeholder="https://youtube.com/watch?v=..." />

  <label>Quality</label>
  <select id="quality">
    <option value="best">Best Quality (MP4)</option>
    <option value="1080">1080p (MP4)</option>
    <option value="720" selected>720p (MP4)</option>
    <option value="480">480p (MP4)</option>
    <option value="audio">Audio Only (MP3)</option>
  </select>

  <button id="btn" onclick="startDownload()">Download</button>
  <div id="status"></div>
</div>

<script>
async function startDownload() {
  const url = document.getElementById('url').value.trim();
  const quality = document.getElementById('quality').value;
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');

  if (!url) {
    setStatus('URL dao first.', 'error');
    return;
  }

  btn.disabled = true;
  setStatus('<span class="spinner"></span> Fetching video info...', '');

  try {
    const res = await fetch('/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, quality })
    });

    if (!res.ok) {
      const err = await res.json();
      setStatus('Error: ' + err.error, 'error');
      btn.disabled = false;
      return;
    }

    setStatus('<span class="spinner"></span> Downloading...', '');

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const nameMatch = disposition.match(/filename="?(.+?)"?$/);
    const filename = nameMatch ? nameMatch[1] : 'video.mp4';

    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);

    setStatus('Download complete!', 'success');
  } catch (e) {
    setStatus('Network error. Try again.', 'error');
  }

  btn.disabled = false;
}

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  el.innerHTML = msg;
  el.className = cls;
}
</script>
</body>
</html>
"""

QUALITY_MAP = {
    "best":  "bestvideo+bestaudio/best",
    "1080":  "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720":   "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480":   "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio": "bestaudio/best",
}


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    quality = (data or {}).get("quality", "720")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    fmt = QUALITY_MAP.get(quality, QUALITY_MAP["720"])
    audio_only = quality == "audio"

    tmp_dir = tempfile.mkdtemp()

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(tmp_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4" if not audio_only else None,
    }

    if audio_only:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        # Find the downloaded file
        files = os.listdir(tmp_dir)
        if not files:
            return jsonify({"error": "Download failed — no file produced"}), 500

        filepath = os.path.join(tmp_dir, files[0])
        ext = os.path.splitext(files[0])[1]
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:80]
        download_name = f"{safe_title}{ext}"

        def cleanup():
            try:
                os.remove(filepath)
                os.rmdir(tmp_dir)
            except Exception:
                pass

        response = send_file(
            filepath,
            as_attachment=True,
            download_name=download_name,
        )
        threading.Thread(target=cleanup, daemon=True).start()
        return response

    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
