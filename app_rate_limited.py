"""
Rate-Limited Beacon App
Respects API rate limits with 1 API call per minute
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

# Import our rate-limited components
from rate_limited_collector import RateLimitedNewsCollector
from topic_processor_local_fixed import TopicProcessor
from topic_storage import TopicStorage
from enhanced_title_generator import enhanced_title_generator

app = FastAPI(title="Beacon Rate Limited", description="AI-powered news aggregation with proper rate limiting")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize rate-limited components
news_collector = RateLimitedNewsCollector()
topic_processor = TopicProcessor()
topic_storage = TopicStorage()

# Global state
topics_db = {}
background_task_running = False
task_lock = asyncio.Lock()

@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    print("🚀 Starting Rate-Limited Beacon News Aggregation System")
    print("📋 Architecture: Rate-Limited News Collection → Local LLM Topic Processing → Topic Storage → API")
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

@app.get("/api/topics")
async def get_topics():
    """Get all topics with error handling"""
    try:
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
    """Generate LLM summary for a specific topic with timeout"""
    topic = topics_db.get(topic_id)
    if not topic:
        return {"error": "Topic not found"}
    
    try:
        # Add timeout protection
        summary = await asyncio.wait_for(
            topic_processor.generate_llm_summary(topic),
            timeout=30.0  # 30 second timeout
        )
        return {"topic_id": topic_id, "summary": summary}
    except asyncio.TimeoutError:
        return {"error": "Summary generation timed out"}
    except Exception as e:
        return {"error": f"Failed to generate summary: {e}"}

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
                except asyncio.TimeoutError:
                    print("⏰ Article collection timed out, skipping this cycle")
                    await asyncio.sleep(60)
                    continue
                except Exception as e:
                    print(f"❌ Error collecting articles: {e}")
                    await asyncio.sleep(60)
                    continue
                
                if articles:
                    # Step 2: Process articles with timeout and error handling
                    try:
                        topics = await asyncio.wait_for(
                            topic_processor.process_articles(articles),
                            timeout=180.0  # 3 minute timeout for topic processing
                        )
                        print(f"🧠 Processed into {len(topics)} topics")
                        
                        # Step 3: Store topics
                        for topic in topics:
                            topics_db[topic['id']] = topic
                        
                        print(f"💾 Stored {len(topics)} topics")
                        print(f"📊 Total topics in system: {len(topics_db)}")
                        
                    except asyncio.TimeoutError:
                        print("⏰ Topic processing timed out, skipping this cycle")
                    except Exception as e:
                        print(f"❌ Error processing topics: {e}")
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
    background_task_running = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
