from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import httpx
import asyncio
from datetime import datetime
import json

app = FastAPI(title="Beacon - Simple News")

# Simple in-memory storage
topics = []

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Beacon News</title></head>
    <body>
        <h1>Beacon News Aggregation</h1>
        <div id="topics"></div>
        <script>
            fetch('/api/topics')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('topics').innerHTML = 
                        data.map(t => `<div><h3>${t.title}</h3><p>${t.summary}</p></div>`).join('');
                });
        </script>
    </body>
    </html>
    """

@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/api/topics")
async def get_topics():
    return topics

async def fetch_news():
    """Simple news fetcher"""
    try:
        async with httpx.AsyncClient() as client:
            # NewsAPI call
            response = await client.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "apiKey": "d69a3b23cad345b898a6ee4d6303c69b",
                    "country": "us",
                    "pageSize": 5
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                for article in data.get('articles', []):
                    if article.get('title'):
                        topics.append({
                            "id": len(topics) + 1,
                            "title": article['title'],
                            "summary": article.get('description', 'No description'),
                            "source": article['source']['name'],
                            "url": article['url'],
                            "published": article['publishedAt']
                        })
                print(f"Added {len(data.get('articles', []))} articles")
            else:
                print(f"NewsAPI error: {response.status_code}")
                
    except Exception as e:
        print(f"Error: {e}")

@app.on_event("startup")
async def startup():
    print("Starting Beacon...")
    await fetch_news()
    print(f"Loaded {len(topics)} topics")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
