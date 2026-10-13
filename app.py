#!/usr/bin/env python3
# app.py — YouTube Downloader (Flask + yt-dlp)
# Render.com deploy

import os, tempfile, threading, logging
import yt_dlp
from flask import Flask, request, jsonify, send_file, render_template_string

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YT Downloader</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#0f0f0f;color:#f1f1f1;
         min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
    .card{background:#1e1e1e;border:1px solid #333;border-radius:12px;
          padding:40px;width:100%;max-width:500px}
    h1{font-size:22px;margin-bottom:6px;color:#ff4444}
    .sub{color:#888;font-size:13px;margin-bottom:28px}
    label{display:block;font-size:13px;color:#aaa;margin-bottom:6px}
    input,select{width:100%;padding:12px 14px;border-radius:8px;border:1px solid #333;
                 background:#111;color:#f1f1f1;font-size:14px;margin-bottom:16px;outline:none}
    input:focus,select:focus{border-color:#ff4444}
    button{width:100%;padding:13px;background:#ff4444;color:#fff;
           font-size:15px;font-weight:600;border:none;border-radius:8px;cursor:pointer}
    button:disabled{background:#444;cursor:not-allowed}
    #st{margin-top:18px;font-size:13px;color:#aaa;text-align:center;min-height:20px;word-break:break-word}
    #st.err{color:#ff6b6b} #st.ok{color:#51cf66}
    .sp{display:inline-block;width:13px;height:13px;border:2px solid #555;
        border-top-color:#ff4444;border-radius:50%;animation:spin .7s linear infinite;
        vertical-align:middle;margin-right:5px}
    @keyframes spin{to{transform:rotate(360deg)}}
  </style>
</head>
<body>
<div class="card">
  <h1>▶ YT Downloader</h1>
  <p class="sub">YouTube video / audio downloader</p>

  <label>YouTube URL</label>
  <input id="url" type="text" placeholder="https://youtube.com/watch?v=...">

  <label>Quality</label>
  <select id="q">
    <option value="best">Best (Auto)</option>
    <option value="720" selected>720p</option>
    <option value="480">480p</option>
    <option value="360">360p</option>
    <option value="audio">Audio only (MP3)</option>
  </select>

  <button id="btn" onclick="go()">Download</button>
  <div id="st"></div>
</div>
<script>
async function go(){
  const url=document.getElementById('url').value.trim();
  const q=document.getElementById('q').value;
  const btn=document.getElementById('btn');
  if(!url){setSt('URL dao.','err');return;}
  btn.disabled=true;
  setSt('<span class="sp"></span>Downloading... wait koro (1-2 min lagbe)','');
  try{
    const r=await fetch('/download',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({url,quality:q})
    });
    if(!r.ok){
      const e=await r.json().catch(()=>({error:'Unknown'}));
      setSt('Error: '+e.error,'err');
      btn.disabled=false;return;
    }
    const blob=await r.blob();
    const cd=r.headers.get('Content-Disposition')||'';
    const m=cd.match(/filename="?([^"\\n]+)"?/);
    const fn=m?m[1]:'video.mp4';
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=fn;
    document.body.appendChild(a);a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    setSt('✓ Done!','ok');
  }catch(e){setSt('Error: '+e.message,'err');}
  btn.disabled=false;
}
function setSt(m,c){const e=document.getElementById('st');e.innerHTML=m;e.className=c;}
</script>
</body></html>"""

# Quality → format string
# "best" fallback at every level so "format not available" never fires
def get_fmt(quality):
    if quality == "audio":
        return "bestaudio/best"
    if quality == "best":
        return "best"
    h = quality  # "720","480","360"
    return f"best[height<={h}]/best"

def find_cookie():
    for p in [
        os.environ.get("COOKIE_FILE",""),
        "/etc/secrets/cookies.txt",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
        "cookies.txt",
    ]:
        if p and os.path.isfile(p):
            log.info(f"cookie: {p} ({os.path.getsize(p)}B)")
            return p
    log.warning("no cookie")
    return None

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/debug")
def debug():
    c = find_cookie()
    return jsonify({
        "cookie": c,
        "cookie_ok": bool(c),
        "cookie_bytes": os.path.getsize(c) if c else 0,
        "cwd": os.getcwd(),
        "ls": os.listdir("."),
    })

@app.route("/download", methods=["POST"])
def download():
    data    = request.get_json(silent=True) or {}
    url     = data.get("url","").strip()
    quality = data.get("quality","720")
    if not url:
        return jsonify({"error":"URL nai"}), 400

    audio  = quality == "audio"
    fmt    = get_fmt(quality)
    tmpdir = tempfile.mkdtemp()
    cookie = find_cookie()

    opts = {
        "format":              fmt,
        "outtmpl":             os.path.join(tmpdir, "%(title)s.%(ext)s"),
        "merge_output_format": "mp4" if not audio else None,
        "quiet":               False,
        "socket_timeout":      60,
        "retries":             5,
        "fragment_retries":    5,
        "http_headers":{
            "User-Agent":(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language":"en-US,en;q=0.9",
        },
        "extractor_args":{
            "youtube":{"player_client":["android","web"]}
        },
    }
    if cookie:
        opts["cookiefile"] = cookie
    if audio:
        opts["postprocessors"] = [{
            "key":"FFmpegExtractAudio",
            "preferredcodec":"mp3",
            "preferredquality":"192",
        }]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info  = ydl.extract_info(url, download=True)
            title = info.get("title","video")

        files = [f for f in os.listdir(tmpdir) if not f.endswith(".part")]
        if not files:
            return jsonify({"error":"File generate hoyni"}), 500

        fpath  = os.path.join(tmpdir, files[0])
        ext    = os.path.splitext(files[0])[1]
        safe   = "".join(c for c in title if c.isalnum() or c in " _-")[:80].strip()
        dlname = f"{safe}{ext}"

        def _rm():
            try: os.remove(fpath); os.rmdir(tmpdir)
            except: pass

        resp = send_file(fpath, as_attachment=True, download_name=dlname)
        threading.Thread(target=_rm, daemon=True).start()
        return resp

    except yt_dlp.utils.DownloadError as e:
        log.error(str(e))
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log.error(str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
