# KlickPin Scraper — Production Web Scraping Solution

A robust, production-grade scraper for klickpin.com with a Flask API backend
and a polished frontend downloader UI.

---

## 📁 Project Structure

```
klickpin-scraper/
├── server.py           # Flask API + Playwright scraper (main backend)
├── scraper_test.py     # Standalone CLI test (no server needed)
├── requirements.txt    # Python dependencies
├── frontend/
│   └── index.html      # Downloader UI (open in browser)
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- pip

### Step 1 — Install Python Dependencies

```bash
cd klickpin-scraper
pip install -r requirements.txt
```

### Step 2 — Install Playwright Browsers

```bash
playwright install chromium
playwright install-deps chromium    # Linux only (installs system deps)
```

---

## 🚀 Running the Backend API

```bash
python server.py
```

The server starts on **http://localhost:5000**

Optional environment variables:
```bash
PORT=8080 DEBUG=true python server.py
```

---

## 🧪 Testing the API

### Health Check
```bash
curl http://localhost:5000/api/health
```
Response:
```json
{ "status": "ok", "service": "klickpin-scraper" }
```

### Download Endpoint
```bash
curl "http://localhost:5000/api/download?url=https%3A%2F%2Fklickpin.com%2Fsome-post"
```

Successful response:
```json
{
  "success": true,
  "videoUrl": "https://cdn.klickpin.com/videos/example.mp4",
  "quality": "1080p",
  "filename": "example.mp4",
  "images": ["https://..."],
  "metadata": {
    "title": "Post Title",
    "description": "...",
    "canonical": "https://klickpin.com/..."
  },
  "allVideoSources": [
    { "url": "https://...", "quality": "1080p" },
    { "url": "https://...", "quality": "720p" }
  ]
}
```

Error response:
```json
{
  "success": false,
  "error": "No downloadable media found on this page."
}
```

---

## 🖥️ Using the Frontend UI

1. Make sure the backend is running (`python server.py`)
2. Open `frontend/index.html` in your browser
3. Paste any `klickpin.com` URL
4. Click **Fetch Media** — the UI will show progress and then display download links

> To serve the frontend properly (avoids CORS issues in some browsers):
> ```bash
> cd frontend
> python -m http.server 3000
> # Then open http://localhost:3000
> ```

---

## 🔬 CLI Test (no server needed)

```bash
python scraper_test.py https://klickpin.com/some-post
```

This runs the scraper directly and prints the JSON result to the terminal.

---

## 🛡️ Anti-Bot Techniques Used

| Technique | Implementation |
|---|---|
| Stealth browser flags | `--disable-blink-features=AutomationControlled` |
| `navigator.webdriver` removal | `add_init_script` patch |
| Realistic User-Agent | Chrome 124 on Windows 10 |
| Human-like delays | `random.uniform()` between actions |
| Progressive scrolling | `simulate_scroll()` with per-step delays |
| Play button click | Triggers video URL network requests |
| Network interception | Captures CDN media URLs in real-time |
| Cookie/session support | Playwright context persists cookies |

---

## 🔄 Retry Logic

```
Attempt 1 → fail → wait 2s
Attempt 2 → fail → wait 4s
Attempt 3 → fail → raise RuntimeError
```

Exponential backoff: `delay = RETRY_DELAY * (2 ** (attempt - 1))`

---

## 🌐 Deploying to Production

### Option A — Gunicorn (Linux VPS)
```bash
pip install gunicorn
gunicorn server:app --workers 2 --bind 0.0.0.0:5000
```

### Option B — Docker
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libgbm1 --no-install-recommends
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium && playwright install-deps chromium
COPY . .
EXPOSE 5000
CMD ["python", "server.py"]
```

```bash
docker build -t klickpin-scraper .
docker run -p 5000:5000 klickpin-scraper
```

---

## ⚖️ Legal Notes

- This scraper respects standard crawl delays and does not hammer servers
- Only one request is made per user action
- No aggressive parallel scraping
- Always check a site's Terms of Service before scraping in production
- For personal/educational use only

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `playwright install` fails | Run `playwright install-deps chromium` on Linux |
| CORS errors in browser | Serve frontend via `python -m http.server` |
| All retries fail | Target page may require login or have strong bot protection |
| No video found | Page may use encrypted HLS streams — check `allVideoSources` array |
| `ModuleNotFoundError` | Re-run `pip install -r requirements.txt` |
