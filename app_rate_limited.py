"""
Rate-Limited Beacon App
Respects API rate limits with 1 API call per minute
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlalchemy.orm import joinedload

# Import our rate-limited components
from rate_limited_collector import RateLimitedNewsCollector
from topic_processor_local_fixed import TopicProcessor
from topic_storage import TopicStorage
from enhanced_title_generator import enhanced_title_generator
from monitoring import ingestion_metrics
from monitoring.alerts import alert_manager
from logging_config import setup_logging
from storage.database import get_session
from storage.models import Story, StoryArticle
import concurrent.futures

app = FastAPI(title="Beacon Rate Limited", description="AI-powered news aggregation with proper rate limiting")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize rate-limited components
news_collector = RateLimitedNewsCollector()
topic_processor = TopicProcessor()
topic_storage = TopicStorage()

# Global state
topics_db: Dict[str, Any] = {}
background_task_running = False
task_lock = asyncio.Lock()
topics_lock = asyncio.Lock()
articles_lock = asyncio.Lock()
latest_articles_debug: List[Dict[str, Any]] = []
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _process_articles_sync(articles):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(topic_processor.process_articles(articles))
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    setup_logging()
    print("🚀 Starting Rate-Limited Beacon News Aggregation System")
    print("📋 Architecture: Rate-Limited News Collection → Topic Processing → Topic Storage → API")
    print("⏰ Rate Limiting: 1 API call per minute per service")
    
    # Start background news aggregation with rate limiting
    global background_task_running
    if not background_task_running:
        background_task_running = True
        asyncio.create_task(rate_limited_news_aggregation_task())

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/debug", response_class=HTMLResponse)
async def debug_dashboard(request: Request):
    """Serve the debug dashboard"""
    with open("debug_dashboard.html", "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get("/api/debug/articles")
async def debug_articles():
    async with articles_lock:
        articles_copy = list(latest_articles_debug)
    return {
        "articles": articles_copy,
        "metrics": ingestion_metrics.snapshot(),
        "alerts": alert_manager.get_recent_alerts(),
    }


def _story_to_dict(story: Story) -> Dict[str, Any]:
    articles_data = []
    for link in story.articles:
        article = link.article
        articles_data.append({
            "id": article.id,
            "title": article.title,
            "source": article.source,
            "url": article.url,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "snippet": (article.body_text or "")[:280],
        })

    return {
        "id": story.id,
        "title": story.title,
        "summary": story.summary,
        "topic_key": story.topic_key,
        "status": story.status,
        "confidence_score": story.confidence_score,
        "created_at": story.created_at.isoformat() if story.created_at else None,
        "updated_at": story.updated_at.isoformat() if story.updated_at else None,
        "article_count": len(articles_data),
        "articles": articles_data,
    }


@app.get("/api/stories")
async def get_stories() -> Dict[str, Any]:
    with get_session() as session:
        stories = (
            session.query(Story)
            .options(joinedload(Story.articles).joinedload(StoryArticle.article))
            .order_by(Story.updated_at.desc())
            .limit(50)
            .all()
        )
        return {"stories": [_story_to_dict(story) for story in stories]}


@app.get("/api/stories/{story_id}")
async def get_story(story_id: int) -> Dict[str, Any]:
    with get_session() as session:
        story = (
            session.query(Story)
            .options(joinedload(Story.articles).joinedload(StoryArticle.article))
            .filter(Story.id == story_id)
            .first()
        )
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        return {"story": _story_to_dict(story)}

@app.get("/api/topics")
async def get_topics():
    """Get all topics with error handling"""
    try:
        async with topics_lock:
            topics = list(topics_db.values())
        return {"topics": topics}
    except Exception as e:
        print(f"❌ Error getting topics: {e}")
        return {"topics": [], "error": str(e)}

@app.get("/api/topics/{topic_id}")
async def get_topic(topic_id: str):
    """Get a specific topic by ID"""
    topic = topics_db.get(topic_id)
    if not topic:
        return {"error": "Topic not found"}
    return {"topic": topic}

@app.get("/api/topics/{topic_id}/summary")
async def get_topic_summary(topic_id: str):
    """Generate summary for a specific topic"""
    topic = topics_db.get(topic_id)
    if not topic:
        return {"error": "Topic not found"}

    summaries = [source.get('summary', '') for source in topic.get('sources', [])]
    summary = enhanced_title_generator.build_topic_summary(topic.get('title', ''), summaries)
    return {"topic_id": topic_id, "summary": summary}

async def rate_limited_news_aggregation_task():
    """Rate-limited background task with 1 API call per minute"""
    global topics_db
    
    while True:
        try:
            # Use lock to prevent concurrent execution
            async with task_lock:
                print("🔄 Starting rate-limited news aggregation cycle...")
                
                # Step 1: Collect articles with rate limiting
                try:
                    articles = await asyncio.wait_for(
                        news_collector.collect_articles(),
                        timeout=120.0  # 2 minute timeout for article collection
                    )
                    print(f"📰 Collected {len(articles)} articles")

                    article_debug_snapshot = [
                        {
                            "title": getattr(a, 'title', ''),
                            "source": getattr(a, 'source', ''),
                            "url": getattr(a, 'url', ''),
                            "content_length": len(getattr(a, 'content', '') or ""),
                            "preview": (getattr(a, 'content', '') or "")[:280]
                        }
                        for a in articles
                    ]
                    async with articles_lock:
                        latest_articles_debug.clear()
                        latest_articles_debug.extend(article_debug_snapshot)

                    short_articles = [info for info in latest_articles_debug if info["content_length"] < 400]
                    if short_articles:
                        print(f"ℹ️ {len(short_articles)} articles have <400 chars of content")
                        for info in short_articles[:5]:
                            print(f"   - {info['source']}: {info['title']} ({info['content_length']} chars)")
                    if len(articles) < 10:
                        alert_manager.record_low_volume(len(articles), 10)
                except asyncio.TimeoutError:
                    print("⏰ Article collection timed out, skipping this cycle")
                    await asyncio.sleep(60)
                    continue
                except Exception as e:
                    print(f"❌ Error collecting articles: {e}")
                    alert_manager.record_failure("collector", str(e))
                    await asyncio.sleep(60)
                    continue
                
                if articles:
                    # Step 2: Process articles with timeout and error handling
                    try:
                        loop = asyncio.get_running_loop()

                        topics = await asyncio.wait_for(
                            loop.run_in_executor(executor, _process_articles_sync, articles),
                            timeout=240.0  # 4 minute timeout for topic processing
                        )
                        print(f"🧠 Processed into {len(topics)} stories")
                        
                        # Step 3: Store topics
                        async with topics_lock:
                            topics_db = {topic['id']: topic for topic in topics}
                        
                        print(f"💾 Stored {len(topics)} stories")
                        print(f"📊 Total stories in system: {len(topics_db)}")
                        
                    except asyncio.TimeoutError:
                        print("⏰ Topic processing timed out, skipping this cycle")
                        alert_manager.record_failure("topic_processor", "timeout")
                    except Exception as e:
                        print(f"❌ Error processing topics: {e}")
                        alert_manager.record_failure("topic_processor", str(e))
                        import traceback
                        traceback.print_exc()
                
                # Wait 10 minutes between cycles to respect rate limits
                print("⏰ Waiting 3 minutes before next cycle to respect rate limits...")
                await asyncio.sleep(180)  # 3 minutes between cycles
                
        except Exception as e:
            print(f"❌ Critical error in news aggregation: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(120)  # Wait 2 minutes on critical error

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down Beacon Rate Limited...")
    global background_task_running
    executor.shutdown(wait=False)
    background_task_running = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
