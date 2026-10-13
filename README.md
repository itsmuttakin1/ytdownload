# YT Downloader

YouTube video downloader web app — Flask + yt-dlp.

## Deploy on Render (Free)

1. GitHub a upload koro
2. [render.com](https://render.com) a login koro
3. **New → Web Service → Connect GitHub repo**
4. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`
5. **Deploy** click koro

Live URL pabe: `https://yt-downloader-xxxx.onrender.com`

## Local run

```bash
pip install -r requirements.txt
python app.py
```

Open: http://localhost:5000
