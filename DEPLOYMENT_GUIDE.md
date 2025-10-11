# Beacon AI News Desk Deployment

## Prerequisites
- Python 3.10+
- `python3-venv`, `build-essential`, standard C toolchain
- Internet access for RSS feeds and models
- Optional: Docker 24+

## Local Development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api:app --reload
```

FastAPI runs at `http://127.0.0.1:8000/api/stories`.

## Server Deployment (systemd)
1. Copy project to `/opt/ai-news`
2. Create venv + install deps:
   ```bash
   python3 -m venv /opt/ai-news/venv
   source /opt/ai-news/venv/bin/activate
   pip install -r /opt/ai-news/requirements.txt
   ```
3. Create `/etc/systemd/system/ai-news.service`:
   ```
   [Unit]
   Description=Beacon AI News Desk
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/ai-news
   Environment="PYTHONUNBUFFERED=1"
   ExecStart=/opt/ai-news/venv/bin/uvicorn src.api:app --host 0.0.0.0 --port 8000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
4. Enable + start:
   ```bash
   systemctl daemon-reload
   systemctl enable ai-news.service
   systemctl start ai-news.service
   ```
5. Tail logs: `journalctl -u ai-news.service -f`

## Docker Deployment
```bash
docker build -t beacon-ai-news .
docker run -d --name beacon-ai-news -p 8000:8000 beacon-ai-news
```

## Verification
- `curl http://localhost:8000/api/stories` returns JSON list
- `journalctl -u ai-news.service` shows startup + ingestion
- SQLite lives at `/opt/ai-news/data/news.db` by default

## Operations Notes
- Ingestion pipeline in `src/ingestion/service.py`
- RSS feeds configured via `src/config.py` (`collector_feeds`)
- Use Postgres by setting `BEACON_DATABASE_URL` env
