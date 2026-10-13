#!/usr/bin/env python3
# app.py — YouTube Downloader Web App (Flask + yt-dlp)
# Deploy: Render.com

import os
import tempfile
import threading
import logging
import yt_dlp
from flask import Flask, request, jsonify, send_file, render_template_string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
      padding: 20px;
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
    }
    button:disabled { background: #444; cursor: not-allowed; }
    #status {
      margin-top: 18px;
      font-size: 13px;
      color: #aaa;
      text-align: center;
      min-height: 20px;
      word-break: break-word;
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
    <option value="best">Best Available (Auto)</option>
    <option value="1080">1080p</option>
    <option value="720" selected>720p</option>
    <option value="480">480p</option>
    <option value="360">360p</option>
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

  if (!url) { setStatus('URL dao.', 'error'); return; }

  btn.disabled = true;
  setStatus('<span class="spinner"></span> Downloading... wait koro', '');

  try {
    const res = await fetch('/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, quality })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      setStatus('Error: ' + err.error, 'error');
      btn.disabled = false;
      return;
    }

    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const match = cd.match(/filename[^;=\\n]*=(['""]?)([^'"";\\n]+)\\1/);
    const filename = match ? match[2] : 'video.mp4';

    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);

    setStatus('✓ Download complete!', 'success');
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
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

# Cookie — multiple paths check
COOKIE_PATHS = [
    "/etc/secrets/cookies.txt",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
    "cookies.txt",
]

def find_cookie_file():
    env = os.environ.get("COOKIE_FILE")
    if env and os.path.exists(env):
        return env
    for p in COOKIE_PATHS:
        if os.path.exists(p):
            logger.info(f"Cookie: {p}")
            return p
    logger.warning("No cookie file found")
    return None


def build_format(quality: str) -> str:
    """
    Fallback chain: requested height → lower heights → any mp4 → best.
    This prevents 'Requested format not available'.
    """
    if quality == "best":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    if quality == "audio":
        return "bestaudio[ext=m4a]/bestaudio/best"

    h = quality  # "1080", "720", "480", "360"
    return (
        f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={h}]+bestaudio"
        f"/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo+bestaudio"
        f"/best[height<={h}]"
        f"/best"
    )


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/debug")
def debug():
    cookie = find_cookie_file()
    size = os.path.getsize(cookie) if cookie else 0
    return jsonify({
        "cookie_file": cookie,
        "cookie_size_bytes": size,
        "cwd": os.getcwd(),
        "files_in_cwd": os.listdir("."),
    })


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url     = data.get("url", "").strip()
    quality = data.get("quality", "720")

    if not url:
        return jsonify({"error": "URL nai"}), 400

    fmt        = build_format(quality)
    audio_only = quality == "audio"
    tmp_dir    = tempfile.mkdtemp()
    cookie     = find_cookie_file()

    ydl_opts = {
        "format":               fmt,
        "outtmpl":              os.path.join(tmp_dir, "%(title)s.%(ext)s"),
        "merge_output_format":  "mp4" if not audio_only else None,
        "quiet":                False,
        "no_warnings":          False,
        "socket_timeout":       60,
        "retries":              5,
        "fragment_retries":     5,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    if cookie:
        ydl_opts["cookiefile"] = cookie

    if audio_only:
        ydl_opts["postprocessors"] = [{
            "key":              "FFmpegExtractAudio",
            "preferredcodec":   "mp3",
            "preferredquality": "192",
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        files = [f for f in os.listdir(tmp_dir) if not f.endswith(".part")]
        if not files:
            return jsonify({"error": "File generate hoyni — format issue"}), 500

        filepath = os.path.join(tmp_dir, files[0])
        ext      = os.path.splitext(files[0])[1]
        safe     = "".join(c for c in title if c.isalnum() or c in " _-")[:80].strip()
        dl_name  = f"{safe}{ext}"

        def _rm():
            try: os.remove(filepath); os.rmdir(tmp_dir)
            except: pass

        resp = send_file(filepath, as_attachment=True, download_name=dl_name)
        threading.Thread(target=_rm, daemon=True).start()
        return resp

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"server: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
