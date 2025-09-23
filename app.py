"""
Beacon - AI-Powered News Aggregation System
Main FastAPI application implementing the architecture from ARCHITECTURE.md
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request

# Import our core components
from news_collector import NewsCollector
from topic_processor import TopicProcessor
from topic_storage import TopicStorage

app = FastAPI(title="Beacon", description="AI-powered news aggregation with neutral fact synthesis")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize core components
news_collector = NewsCollector()
topic_processor = TopicProcessor()
topic_storage = TopicStorage()

# Global state
topics_db = {}
background_task_running = False

@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    print("🚀 Starting Beacon News Aggregation System")
    print("📋 Architecture: News Collection → Topic Processing → Topic Storage → API")
    
    # Start background news aggregation
    global background_task_running
    if not background_task_running:
        background_task_running = True
        asyncio.create_task(news_aggregation_task())

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Topic Discovery & Analysis",
        "subtitle": "AI-powered news aggregation with neutral fact synthesis"
    })

@app.get("/api/topics")
async def get_topics():
    """Get all topics with their aggregated sources"""
    topics = topic_storage.get_all_topics()
    return {"topics": topics}

@app.get("/api/topics/{topic_id}")
async def get_topic(topic_id: str):
    """Get a specific topic by ID"""
    topic = topic_storage.get_topic(topic_id)
    if not topic:
        return {"error": "Topic not found"}
    return {"topic": topic}

async def news_aggregation_task():
    """Background task that continuously aggregates news and processes topics"""
    global background_task_running
    
    while background_task_running:
        try:
            print("🔄 Starting news aggregation cycle...")
            
            # Step 1: Collect news articles
            print("📰 Collecting news articles...")
            articles = await news_collector.collect_articles()
            print(f"✅ Collected {len(articles)} articles")
            
            if articles:
                # Step 2: Process articles into topics using LLM
                print("🧠 Processing articles into topics...")
                topics = await topic_processor.process_articles(articles)
                print(f"✅ Processed into {len(topics)} topics")
                
                # Step 3: Store topics
                print("💾 Storing topics...")
                for topic in topics:
                    topic_storage.store_topic(topic)
                    print(f"📋 Stored topic: {topic['title']} ({topic['source_count']} sources)")
                
                # Update global state
                global topics_db
                topics_db = topic_storage.get_all_topics()
                print(f"📊 Total topics in system: {len(topics_db)}")
            
            # Wait before next cycle
            await asyncio.sleep(300)  # 5 minutes between cycles
            
        except Exception as e:
            print(f"❌ Error in news aggregation: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global background_task_running
    background_task_running = False
    print("🛑 Shutting down Beacon system")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
